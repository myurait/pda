from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from process_monitor import (
    INITIAL_MONITORS,
    ProcessMonitorStore,
)


NOW = 1_788_240_000.0


def _decision(
    store: ProcessMonitorStore,
    *,
    monitor_id: str,
    index: int,
    verdict: bool,
    occurred_at: float = NOW,
    accepted_at: float = NOW,
) -> None:
    join_key = f"run-{index}"
    store.record_expected(
        monitor_id=monitor_id,
        join_key=join_key,
        event_id=f"expected-{index}",
        occurred_at=occurred_at - 1,
        due_at=occurred_at + 60,
    )
    store.record_decision(
        monitor_id=monitor_id,
        join_key=join_key,
        event_id=f"decision-{index}",
        verdict=verdict,
        occurred_at=occurred_at,
        accepted_at=accepted_at,
    )


def test_initial_registry_has_two_generic_monitors_and_ten_sample_floor(tmp_path: Path) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)

    registered = store.list_monitors()

    assert {item["monitor_id"] for item in registered} == {
        "scope.prework.additional-assurance-required",
        "scope.final.final-scope-conformant",
    }
    assert all(item["window_seconds"] == 72 * 60 * 60 for item in registered)
    assert all(item["min_samples"] == 10 for item in registered)
    assert all(item["threshold"] == 0.95 for item in registered)
    assert len(INITIAL_MONITORS) == 2


def test_nine_never_triggers_but_tenth_dominant_decision_does(tmp_path: Path) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    monitor_id = INITIAL_MONITORS[0].monitor_id
    for index in range(9):
        _decision(store, monitor_id=monitor_id, index=index, verdict=True)

    below = store.evaluate(monitor_id, cutoff=NOW)

    assert below["N"] == 9
    assert below["dominance"] == 1.0
    assert below["trigger"] is False
    assert store.pending_outbox() == []

    _decision(store, monitor_id=monitor_id, index=9, verdict=True)
    at_floor = store.evaluate(monitor_id, cutoff=NOW)

    assert at_floor["N"] == 10
    assert at_floor["trigger"] is True
    assert at_floor["dominant_value"] is True
    outbox = store.pending_outbox()
    assert len(outbox) == 1
    assert outbox[0]["idempotency_key"].startswith(
        "process-degeneration/scope.prework.additional-assurance-required/"
    )


def test_threshold_is_inclusive_in_both_directions_and_episode_is_idempotent(
    tmp_path: Path,
) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    monitor_id = INITIAL_MONITORS[1].monitor_id
    for index in range(20):
        _decision(store, monitor_id=monitor_id, index=index, verdict=index == 0)

    first = store.evaluate(monitor_id, cutoff=NOW)
    second = store.evaluate(monitor_id, cutoff=NOW)

    assert first["N"] == 20
    assert first["dominance"] == 0.95
    assert first["dominant_value"] is False
    assert first["trigger"] is True
    assert second["episode_id"] == first["episode_id"]
    assert len(store.pending_outbox()) == 1


def test_duplicate_conflict_and_missing_are_not_silently_counted(tmp_path: Path) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    monitor_id = INITIAL_MONITORS[0].monitor_id
    _decision(store, monitor_id=monitor_id, index=0, verdict=True)
    store.record_decision(
        monitor_id=monitor_id,
        join_key="run-0",
        event_id="decision-duplicate",
        verdict=True,
        occurred_at=NOW,
        accepted_at=NOW,
    )
    store.record_decision(
        monitor_id=monitor_id,
        join_key="run-0",
        event_id="decision-conflict",
        verdict=False,
        occurred_at=NOW,
        accepted_at=NOW,
    )
    store.record_expected(
        monitor_id=monitor_id,
        join_key="missing",
        event_id="expected-missing",
        occurred_at=NOW - 120,
        due_at=NOW - 60,
    )

    result = store.evaluate(monitor_id, cutoff=NOW)
    failures = {item["failure_type"] for item in store.list_failures()}

    assert result["N"] == 0
    assert "duplicate-decision" in failures
    assert "conflicting-duplicate" in failures
    assert "missing-decision" in failures


def test_same_event_id_payload_drift_excludes_original_from_ratio(tmp_path: Path) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    monitor_id = INITIAL_MONITORS[0].monitor_id
    _decision(store, monitor_id=monitor_id, index=0, verdict=True)
    store.record_decision(
        monitor_id=monitor_id,
        join_key="run-0",
        event_id="decision-0",
        verdict=False,
        occurred_at=NOW,
        accepted_at=NOW,
    )

    result = store.evaluate(monitor_id, cutoff=NOW)

    assert result["N"] == 0
    assert any(
        item["failure_type"] == "conflicting-duplicate"
        for item in store.list_failures()
    )


def test_window_expiry_recovers_and_recurrence_gets_new_episode_after_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "monitor.db"
    store = ProcessMonitorStore(path, clock=lambda: NOW)
    monitor_id = INITIAL_MONITORS[0].monitor_id
    for index in range(10):
        _decision(store, monitor_id=monitor_id, index=index, verdict=True)
    first = store.evaluate(monitor_id, cutoff=NOW)

    recovered = store.evaluate(monitor_id, cutoff=NOW + 72 * 60 * 60 + 1)
    reopened = ProcessMonitorStore(path, clock=lambda: NOW + 72 * 60 * 60 + 2)
    for index in range(10, 20):
        _decision(
            reopened,
            monitor_id=monitor_id,
            index=index,
            verdict=True,
            occurred_at=NOW + 72 * 60 * 60 + 2,
            accepted_at=NOW + 72 * 60 * 60 + 2,
        )
    second = reopened.evaluate(monitor_id, cutoff=NOW + 72 * 60 * 60 + 2)

    assert recovered["trigger"] is False
    assert second["trigger"] is True
    assert second["episode_id"] != first["episode_id"]


def test_unknown_monitor_is_attributed_to_ingress_integrity_once(tmp_path: Path) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    raw = {
        "monitor_id": "unknown.monitor",
        "event_id": "event-1",
        "join_key": "run-1",
        "verdict": True,
        "occurred_at": NOW,
    }

    first = store.ingest_raw_decision(
        raw,
        source_stream_id="test",
        source_position="1",
        accepted_at=NOW,
    )
    second = store.ingest_raw_decision(
        raw,
        source_stream_id="test",
        source_position="1",
        accepted_at=NOW + 1,
    )

    assert first["ingress_id"] == second["ingress_id"]
    failures = store.list_failures()
    assert len(failures) == 1
    assert failures[0]["monitor_id"] == "process-monitor.ingress-integrity"
    assert failures[0]["failure_type"] == "unattributed-invalid-event"


def test_delivered_episode_is_requeued_only_when_payload_changes(tmp_path: Path) -> None:
    store = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    monitor_id = INITIAL_MONITORS[0].monitor_id
    for index in range(10):
        _decision(store, monitor_id=monitor_id, index=index, verdict=True)
    store.evaluate(monitor_id, cutoff=NOW)
    first = store.pending_outbox()
    assert len(first) == 1
    failure_event = store.mark_delivery_failed(first[0]["outbox_id"], "temporary")
    store.mark_delivered(first[0]["outbox_id"], "t_existing")
    with store._connect() as connection:
        assert connection.execute(
            "SELECT active FROM process_monitor_health WHERE event_id = ?",
            (failure_event,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT acknowledged_at FROM owner_alert_outbox WHERE alert_id = ?",
            (failure_event,),
        ).fetchone()[0] is not None
    assert store.pending_outbox() == []

    _decision(store, monitor_id=monitor_id, index=10, verdict=True)
    store.evaluate(monitor_id, cutoff=NOW)
    update = store.pending_outbox()

    assert len(update) == 1
    assert update[0]["delivered_task_id"] == "t_existing"
    assert update[0]["outbox_id"] == first[0]["outbox_id"]


def test_monitor_cli_reconcile_no_delivery_isolated_from_kanban(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "pda-scope-gate"
    state = tmp_path / "scope.db"
    env = {
        **os.environ,
        "HERMES_HOME": str(tmp_path / ".hermes"),
        "PDA_SCOPE_GATE_STATE": str(state),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    doctor = subprocess.run(
        [sys.executable, str(script), "doctor"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    reconcile = subprocess.run(
        [sys.executable, str(script), "monitor-reconcile", "--no-delivery"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert doctor.returncode == 0, doctor.stderr
    assert json.loads(doctor.stdout)["min_samples"] == 10
    assert reconcile.returncode == 0, reconcile.stderr
    result = json.loads(reconcile.stdout)
    assert result["delivered"] == 0
    assert len(result["evaluations"]) == 2


def test_telemetry_failures_share_one_outbox_row_per_failure_type_and_legacy_rows_coalesce(
    tmp_path,
) -> None:
    import json
    import sqlite3

    from process_monitor import ProcessMonitorStore

    now = 1_788_240_000.0
    path = tmp_path / "monitor.db"
    store = ProcessMonitorStore(path, clock=lambda: now)
    monitor_id = "scope.final.final-scope-conformant"
    for index in range(3):
        store.record_expected(
            monitor_id=monitor_id,
            join_key=f"run-{index}",
            event_id=f"expected-{index}",
            occurred_at=now - 1000,
            due_at=now - 500,
        )
    store.evaluate(monitor_id, cutoff=now)

    pending = store.pending_outbox()
    telemetry = [row for row in pending if row["kind"] == "telemetry-failure"]
    assert len(telemetry) == 1
    assert telemetry[0]["payload"]["failure_type"] == "missing-decision"
    assert telemetry[0]["payload"]["active_episodes"] == 3
    assert len(store.list_failures()) == 3, "per-subject episodes are still recorded"

    # Legacy per-subject rows from the previous key scheme fold into one row.
    with sqlite3.connect(path) as connection:
        for index in range(2):
            connection.execute(
                """
                INSERT INTO pm_outbox (
                    outbox_id, idempotency_key, kind, monitor_id, episode_id,
                    payload_json, payload_digest, created_at, updated_at
                ) VALUES (?, ?, 'telemetry-failure', ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"legacy-{index}",
                    f"process-telemetry/{monitor_id}/late-decision/ep{index}",
                    monitor_id,
                    f"ep{index}",
                    json.dumps({"failure_type": "late-decision", "subject_key": f"s{index}"}),
                    f"digest{index}",
                    now + index,
                    now + index,
                ),
            )
    reopened = ProcessMonitorStore(path, clock=lambda: now + 10)
    late = [
        row
        for row in reopened.pending_outbox()
        if row["payload"].get("failure_type") == "late-decision"
    ]
    assert len(late) == 1
    assert late[0]["payload"]["coalesced_legacy_rows"] == 2
    assert late[0]["payload"]["subject_key"] == "s1"
