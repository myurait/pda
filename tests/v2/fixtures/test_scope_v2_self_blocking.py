"""Offline witnesses for the old gate; these tests do not repair it."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/v2/m1_scope_repro.py"


def test_actual_gate_exhaustion_blocks_its_control_path() -> None:
    assert RUNNER.is_file(), "M1 offline witness runner is not implemented yet"
    result = subprocess.run(
        [sys.executable, "-B", "-I", str(RUNNER)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["scope"] == "offline-unchanged-gate-witness-not-production-repair"
    assert report["before_exhaustion"]["allowed"] is True
    assert report["remaining_before"] == 0
    assert report["observed_self_blocking"] is True
    assert set(report["after_exhaustion"]) == {
        "read_file", "kanban_heartbeat", "kanban_block", "scope_gate", "delegate_task"
    }
    for decision in report["after_exhaustion"].values():
        assert decision["allowed"] is False
        assert decision["action"] == "tool-budget-exhausted"
    assert report["completion_signal"]["allowed"] is False
    assert report["completion_signal"]["action"] == "final-audit-required"
    assert report["after_reopen"]["allowed"] is False
    assert report["source_unchanged"] is True
    assert report["live_gate_enabled_by_probe"] is False


def test_closure_is_not_an_artifact_of_a_one_call_budget() -> None:
    result = subprocess.run(
        [sys.executable, "-B", "-I", str(RUNNER), "--budget", "8"],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report.get("configured_budget") == 8
    assert report["spent_calls"] == 8
    assert report["all_budgeted_calls_allowed"] is True
    assert report["observed_self_blocking"] is True
    assert report["recorded_external_effects"] == 0


def test_probe_does_not_create_files_in_loaded_source_tree(tmp_path) -> None:
    import shutil
    isolated = tmp_path / "source-copy"
    for relative in (
        "experiments/v2/m1_scope_repro.py",
        "integrations/hermes-scope-gate/scope_v2.py",
        "integrations/hermes-scope-gate/process_monitor.py",
    ):
        destination = isolated / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    before = {str(path.relative_to(isolated)): path.read_bytes() for path in isolated.rglob("*") if path.is_file()}
    # Deliberately omit -B to verify the probe itself suppresses loader writes.
    result = subprocess.run(
        [sys.executable, "-I", str(isolated / "experiments/v2/m1_scope_repro.py")],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    after = {str(path.relative_to(isolated)): path.read_bytes() for path in isolated.rglob("*") if path.is_file()}
    assert after == before, "probe wrote files into its loaded source tree"


def test_rereview_can_lower_cap_below_spent_budget() -> None:
    result = subprocess.run(
        [sys.executable, "-B", "-I", str(RUNNER), "--scenario", "shrink"],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report.get("scenario") == "shrink"
    assert report["cap_before"] == 8
    assert report["cap_after"] == 1
    assert report["remaining_before"] == -1
    assert report["spent_before_rereview"] == 2
    assert report["spent_after_rereview"] == 2
    assert report["rereview_accepted"] is True
    assert report["relock_accepted"] is True
    assert report["observed_self_blocking"] is True
    assert report["recorded_external_effects"] == 0
