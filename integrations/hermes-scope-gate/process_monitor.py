"""Deterministic monitoring for degenerate binary decision processes.

The monitor never interprets a verdict.  It validates event integrity, joins a
registered expected population to JSON booleans, evaluates a fixed rolling
window, and writes idempotent outbox records.  Delivery is deliberately
separate so a failed Kanban sink cannot alter the original decision path.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INGRESS_MONITOR_ID = "process-monitor.ingress-integrity"
DEFAULT_WINDOW_SECONDS = 72 * 60 * 60
DEFAULT_MIN_SAMPLES = 10
DEFAULT_THRESHOLD = 0.95


@dataclass(frozen=True)
class MonitorDefinition:
    monitor_id: str
    display_name: str
    window_seconds: int = DEFAULT_WINDOW_SECONDS
    min_samples: int = DEFAULT_MIN_SAMPLES
    threshold: float = DEFAULT_THRESHOLD
    authority_source: str = "docs/design/process-degeneration-monitor.md"


INITIAL_MONITORS = (
    MonitorDefinition(
        "scope.prework.additional-assurance-required",
        "Terra事前評価の追加保証フラグ",
    ),
    MonitorDefinition(
        "scope.final.final-scope-conformant",
        "最終スコープ監査ゲート",
    ),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(*parts: object) -> str:
    encoded = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    return value if isinstance(value, dict) else {}


class ProcessMonitorStore:
    """SQLite-backed registry, event store, evaluator, and durable outbox."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        register_initial: bool = True,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self._initialize()
        if register_initial:
            for definition in INITIAL_MONITORS:
                self.register_monitor(definition)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS pm_registry (
                    monitor_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    window_seconds INTEGER NOT NULL CHECK(window_seconds > 0),
                    min_samples INTEGER NOT NULL CHECK(min_samples > 0),
                    threshold REAL NOT NULL CHECK(threshold > 0 AND threshold <= 1),
                    authority_source TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pm_envelopes (
                    ingress_id TEXT PRIMARY KEY,
                    source_stream_id TEXT NOT NULL,
                    source_position TEXT NOT NULL,
                    raw_payload_digest TEXT NOT NULL,
                    accepted_at REAL NOT NULL,
                    control_sequence INTEGER NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS pm_expected (
                    monitor_id TEXT NOT NULL,
                    join_key TEXT NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    occurred_at REAL NOT NULL,
                    due_at REAL NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (monitor_id, join_key),
                    FOREIGN KEY (monitor_id) REFERENCES pm_registry(monitor_id)
                );
                CREATE TABLE IF NOT EXISTS pm_decisions (
                    event_id TEXT PRIMARY KEY,
                    monitor_id TEXT NOT NULL,
                    join_key TEXT NOT NULL,
                    verdict INTEGER NOT NULL CHECK(verdict IN (0, 1)),
                    occurred_at REAL NOT NULL,
                    accepted_at REAL NOT NULL,
                    control_sequence INTEGER NOT NULL UNIQUE,
                    payload_digest TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (monitor_id) REFERENCES pm_registry(monitor_id)
                );
                CREATE INDEX IF NOT EXISTS pm_decisions_join
                    ON pm_decisions(monitor_id, join_key, control_sequence);
                CREATE INDEX IF NOT EXISTS pm_decisions_window
                    ON pm_decisions(monitor_id, occurred_at);
                CREATE TABLE IF NOT EXISTS pm_state (
                    monitor_id TEXT PRIMARY KEY,
                    last_trigger INTEGER NOT NULL DEFAULT 0 CHECK(last_trigger IN (0, 1)),
                    episode_generation INTEGER NOT NULL DEFAULT 0,
                    episode_id TEXT,
                    dominant_value INTEGER CHECK(dominant_value IN (0, 1)),
                    recovered_at REAL,
                    last_evaluated_at REAL,
                    FOREIGN KEY (monitor_id) REFERENCES pm_registry(monitor_id)
                );
                CREATE TABLE IF NOT EXISTS pm_failures (
                    episode_id TEXT PRIMARY KEY,
                    monitor_id TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    subject_key TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
                    first_seen_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL,
                    UNIQUE(monitor_id, failure_type, subject_key)
                );
                CREATE TABLE IF NOT EXISTS pm_outbox (
                    outbox_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    monitor_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    delivered_task_id TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS process_monitor_health (
                    event_id TEXT PRIMARY KEY,
                    failure_type TEXT NOT NULL,
                    subject_key TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS owner_alert_outbox (
                    alert_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    acknowledged_at REAL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            outbox_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(pm_outbox)").fetchall()
            }
            if "delivered_payload_digest" not in outbox_columns:
                connection.execute(
                    "ALTER TABLE pm_outbox ADD COLUMN delivered_payload_digest TEXT"
                )

    def register_monitor(self, definition: MonitorDefinition) -> None:
        if not definition.monitor_id.strip():
            raise ValueError("monitor_id is required")
        if definition.min_samples < 1:
            raise ValueError("min_samples must be positive")
        if not 0 < definition.threshold <= 1:
            raise ValueError("threshold must be in (0, 1]")
        payload = (
            definition.display_name,
            definition.window_seconds,
            definition.min_samples,
            definition.threshold,
            definition.authority_source,
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM pm_registry WHERE monitor_id = ?",
                (definition.monitor_id,),
            ).fetchone()
            if existing is not None:
                current = (
                    existing["display_name"],
                    int(existing["window_seconds"]),
                    int(existing["min_samples"]),
                    float(existing["threshold"]),
                    existing["authority_source"],
                )
                if current != payload:
                    raise ValueError(
                        f"monitor registration drift for {definition.monitor_id}; "
                        "registry changes require an owner-governed migration"
                    )
                return
            connection.execute(
                """
                INSERT INTO pm_registry (
                    monitor_id, display_name, window_seconds, min_samples,
                    threshold, authority_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (definition.monitor_id, *payload, self.clock()),
            )
            connection.execute(
                "INSERT INTO pm_state (monitor_id) VALUES (?)",
                (definition.monitor_id,),
            )

    def list_monitors(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM pm_registry ORDER BY monitor_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def _require_monitor(self, connection: sqlite3.Connection, monitor_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM pm_registry WHERE monitor_id = ?", (monitor_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unregistered monitor: {monitor_id}")
        return row

    @staticmethod
    def _next_sequence(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            """
            SELECT MAX(value) FROM (
                SELECT COALESCE(MAX(control_sequence), 0) AS value FROM pm_envelopes
                UNION ALL
                SELECT COALESCE(MAX(control_sequence), 0) AS value FROM pm_decisions
            )
            """
        ).fetchone()
        return int(row[0] or 0) + 1

    def record_expected(
        self,
        *,
        monitor_id: str,
        join_key: str,
        event_id: str,
        occurred_at: float,
        due_at: float,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not join_key or not event_id:
            raise ValueError("join_key and event_id are required")
        if due_at < occurred_at:
            raise ValueError("due_at must not precede occurred_at")
        encoded = _canonical(dict(metadata or {}))
        with self._connect() as connection:
            self._require_monitor(connection, monitor_id)
            existing = connection.execute(
                "SELECT * FROM pm_expected WHERE monitor_id = ? AND join_key = ?",
                (monitor_id, join_key),
            ).fetchone()
            if existing is not None:
                current = (
                    existing["event_id"],
                    float(existing["occurred_at"]),
                    float(existing["due_at"]),
                    existing["metadata_json"],
                )
                proposed = (event_id, float(occurred_at), float(due_at), encoded)
                if current != proposed:
                    raise ValueError("expected event drift for existing join_key")
                return dict(existing)
            connection.execute(
                """
                INSERT INTO pm_expected (
                    monitor_id, join_key, event_id, occurred_at, due_at,
                    metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    monitor_id,
                    join_key,
                    event_id,
                    float(occurred_at),
                    float(due_at),
                    encoded,
                    self.clock(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM pm_expected WHERE monitor_id = ? AND join_key = ?",
                (monitor_id, join_key),
            ).fetchone()
        return dict(row)

    def record_decision(
        self,
        *,
        monitor_id: str,
        join_key: str,
        event_id: str,
        verdict: bool,
        occurred_at: float,
        accepted_at: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if type(verdict) is not bool:  # JSON booleans only; integers are not verdicts.
            raise ValueError("verdict must be a JSON boolean")
        if not join_key or not event_id:
            raise ValueError("join_key and event_id are required")
        accepted = self.clock() if accepted_at is None else float(accepted_at)
        metadata_json = _canonical(dict(metadata or {}))
        payload_digest = _digest(
            monitor_id,
            join_key,
            event_id,
            verdict,
            float(occurred_at),
            accepted,
            metadata_json,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_monitor(connection, monitor_id)
            existing = connection.execute(
                "SELECT * FROM pm_decisions WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                if existing["payload_digest"] != payload_digest:
                    self._record_failure_in_txn(
                        connection,
                        monitor_id=monitor_id,
                        failure_type="conflicting-duplicate",
                        subject_key=event_id,
                        details={"event_id": event_id, "reason": "event id payload drift"},
                    )
                connection.commit()
                return dict(existing)
            sequence = self._next_sequence(connection)
            connection.execute(
                """
                INSERT INTO pm_decisions (
                    event_id, monitor_id, join_key, verdict, occurred_at,
                    accepted_at, control_sequence, payload_digest, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    monitor_id,
                    join_key,
                    int(verdict),
                    float(occurred_at),
                    accepted,
                    sequence,
                    payload_digest,
                    metadata_json,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM pm_decisions WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(row)

    def ingest_raw_decision(
        self,
        raw: Mapping[str, Any],
        *,
        source_stream_id: str,
        source_position: str,
        accepted_at: float | None = None,
    ) -> dict[str, Any]:
        raw_dict = dict(raw)
        raw_payload_digest = hashlib.sha256(_canonical(raw_dict).encode("utf-8")).hexdigest()
        ingress_id = _digest(source_stream_id, source_position, raw_payload_digest)
        accepted = self.clock() if accepted_at is None else float(accepted_at)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM pm_envelopes WHERE ingress_id = ?", (ingress_id,)
            ).fetchone()
            if existing is None:
                sequence = self._next_sequence(connection)
                connection.execute(
                    """
                    INSERT INTO pm_envelopes (
                        ingress_id, source_stream_id, source_position,
                        raw_payload_digest, accepted_at, control_sequence
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ingress_id,
                        source_stream_id,
                        source_position,
                        raw_payload_digest,
                        accepted,
                        sequence,
                    ),
                )
            else:
                accepted = float(existing["accepted_at"])
            monitor_id = raw_dict.get("monitor_id")
            registered = (
                isinstance(monitor_id, str)
                and connection.execute(
                    "SELECT 1 FROM pm_registry WHERE monitor_id = ?", (monitor_id,)
                ).fetchone()
                is not None
            )
            required_valid = (
                registered
                and isinstance(raw_dict.get("event_id"), str)
                and bool(raw_dict.get("event_id"))
                and isinstance(raw_dict.get("join_key"), str)
                and bool(raw_dict.get("join_key"))
                and type(raw_dict.get("verdict")) is bool
                and isinstance(raw_dict.get("occurred_at"), (int, float))
            )
            if not required_valid:
                failure_monitor = str(monitor_id) if registered else INGRESS_MONITOR_ID
                failure_type = (
                    "invalid-verdict" if registered else "unattributed-invalid-event"
                )
                self._record_failure_in_txn(
                    connection,
                    monitor_id=failure_monitor,
                    failure_type=failure_type,
                    subject_key=ingress_id,
                    details={
                        "ingress_id": ingress_id,
                        "claimed_monitor_id": raw_dict.get("monitor_id"),
                    },
                )
                connection.commit()
                return {"ingress_id": ingress_id, "accepted": False}
            connection.commit()
        decision = self.record_decision(
            monitor_id=str(raw_dict["monitor_id"]),
            join_key=str(raw_dict["join_key"]),
            event_id=str(raw_dict["event_id"]),
            verdict=raw_dict["verdict"],
            occurred_at=float(raw_dict["occurred_at"]),
            accepted_at=accepted,
            metadata=raw_dict.get("metadata") if isinstance(raw_dict.get("metadata"), dict) else {},
        )
        return {"ingress_id": ingress_id, "accepted": True, "decision": decision}

    def _enqueue_outbox_in_txn(
        self,
        connection: sqlite3.Connection,
        *,
        kind: str,
        monitor_id: str,
        episode_id: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> str:
        outbox_id = _digest("outbox", idempotency_key)
        encoded = _canonical(dict(payload))
        payload_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        now = self.clock()
        connection.execute(
            """
            INSERT INTO pm_outbox (
                outbox_id, idempotency_key, kind, monitor_id, episode_id,
                payload_json, payload_digest, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(idempotency_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                payload_digest = excluded.payload_digest,
                updated_at = excluded.updated_at
            """,
            (
                outbox_id,
                idempotency_key,
                kind,
                monitor_id,
                episode_id,
                encoded,
                payload_digest,
                now,
                now,
            ),
        )
        return outbox_id

    def _record_failure_in_txn(
        self,
        connection: sqlite3.Connection,
        *,
        monitor_id: str,
        failure_type: str,
        subject_key: str,
        details: Mapping[str, Any],
    ) -> str:
        episode_id = _digest(monitor_id, failure_type, subject_key)
        now = self.clock()
        encoded = _canonical(dict(details))
        connection.execute(
            """
            INSERT INTO pm_failures (
                episode_id, monitor_id, failure_type, subject_key,
                details_json, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                details_json = excluded.details_json,
                last_seen_at = excluded.last_seen_at,
                active = 1
            """,
            (episode_id, monitor_id, failure_type, subject_key, encoded, now, now),
        )
        self._enqueue_outbox_in_txn(
            connection,
            kind="telemetry-failure",
            monitor_id=monitor_id,
            episode_id=episode_id,
            idempotency_key=(
                f"process-telemetry/{monitor_id}/{failure_type}/{episode_id}"
            ),
            payload={
                "title": f"判定テレメトリ失敗: {failure_type}",
                "monitor_id": monitor_id,
                "failure_type": failure_type,
                "subject_key": subject_key,
                "details": dict(details),
                "original_decision_unchanged": True,
                "automatic_assignment": False,
            },
        )
        return episode_id

    def _record_failure(
        self,
        *,
        monitor_id: str,
        failure_type: str,
        subject_key: str,
        details: Mapping[str, Any],
    ) -> str:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            episode_id = self._record_failure_in_txn(
                connection,
                monitor_id=monitor_id,
                failure_type=failure_type,
                subject_key=subject_key,
                details=details,
            )
            connection.commit()
        return episode_id

    def evaluate(self, monitor_id: str, *, cutoff: float | None = None) -> dict[str, Any]:
        evaluated_at = self.clock() if cutoff is None else float(cutoff)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            registry = self._require_monitor(connection, monitor_id)
            expected_rows = connection.execute(
                "SELECT * FROM pm_expected WHERE monitor_id = ? ORDER BY join_key",
                (monitor_id,),
            ).fetchall()
            expected_keys = {str(row["join_key"]) for row in expected_rows}
            true_count = 0
            false_count = 0
            failure_count = 0
            window_start = evaluated_at - int(registry["window_seconds"])

            orphan_rows = connection.execute(
                "SELECT DISTINCT join_key FROM pm_decisions WHERE monitor_id = ?",
                (monitor_id,),
            ).fetchall()
            for orphan in orphan_rows:
                key = str(orphan["join_key"])
                if key not in expected_keys:
                    self._record_failure_in_txn(
                        connection,
                        monitor_id=monitor_id,
                        failure_type="invalid-verdict",
                        subject_key=key,
                        details={"join_key": key, "reason": "no expected population event"},
                    )
                    failure_count += 1

            for expected in expected_rows:
                join_key = str(expected["join_key"])
                decisions = connection.execute(
                    """
                    SELECT * FROM pm_decisions
                    WHERE monitor_id = ? AND join_key = ?
                    ORDER BY control_sequence, event_id
                    """,
                    (monitor_id, join_key),
                ).fetchall()
                due_at = float(expected["due_at"])
                on_time = [row for row in decisions if float(row["accepted_at"]) <= due_at]
                late = [row for row in decisions if float(row["accepted_at"]) > due_at]
                for row in late:
                    self._record_failure_in_txn(
                        connection,
                        monitor_id=monitor_id,
                        failure_type="late-decision",
                        subject_key=join_key,
                        details={"join_key": join_key, "event_id": row["event_id"]},
                    )
                    failure_count += 1
                if not on_time:
                    if evaluated_at >= due_at:
                        self._record_failure_in_txn(
                            connection,
                            monitor_id=monitor_id,
                            failure_type="missing-decision",
                            subject_key=join_key,
                            details={"join_key": join_key, "due_at": due_at},
                        )
                        failure_count += 1
                    continue
                if len(on_time) > 1:
                    self._record_failure_in_txn(
                        connection,
                        monitor_id=monitor_id,
                        failure_type="duplicate-decision",
                        subject_key=join_key,
                        details={
                            "join_key": join_key,
                            "event_ids": [str(row["event_id"]) for row in on_time],
                        },
                    )
                    failure_count += 1
                conflict_subjects = [join_key] + [str(row["event_id"]) for row in on_time]
                conflict_placeholders = ",".join("?" for _ in conflict_subjects)
                existing_conflict = connection.execute(
                    f"""
                    SELECT 1 FROM pm_failures
                    WHERE monitor_id = ? AND failure_type = 'conflicting-duplicate'
                      AND active = 1 AND subject_key IN ({conflict_placeholders})
                    LIMIT 1
                    """,
                    (monitor_id, *conflict_subjects),
                ).fetchone()
                if existing_conflict is not None:
                    failure_count += 1
                    continue
                verdicts = {int(row["verdict"]) for row in on_time}
                if len(verdicts) != 1:
                    self._record_failure_in_txn(
                        connection,
                        monitor_id=monitor_id,
                        failure_type="conflicting-duplicate",
                        subject_key=join_key,
                        details={
                            "join_key": join_key,
                            "event_ids": [str(row["event_id"]) for row in on_time],
                        },
                    )
                    failure_count += 1
                    continue
                canonical = on_time[0]
                occurred_at = float(canonical["occurred_at"])
                if window_start < occurred_at <= evaluated_at:
                    if bool(canonical["verdict"]):
                        true_count += 1
                    else:
                        false_count += 1

            sample_count = true_count + false_count
            dominance = (
                max(true_count, false_count) / sample_count if sample_count else None
            )
            trigger = bool(
                sample_count >= int(registry["min_samples"])
                and dominance is not None
                and dominance >= float(registry["threshold"])
            )
            dominant_value: bool | None = None
            if sample_count:
                dominant_value = true_count >= false_count

            state = connection.execute(
                "SELECT * FROM pm_state WHERE monitor_id = ?", (monitor_id,)
            ).fetchone()
            last_trigger = bool(state["last_trigger"])
            generation = int(state["episode_generation"])
            episode_id = state["episode_id"]
            if trigger and not last_trigger:
                generation += 1
                episode_id = _digest(monitor_id, generation, int(bool(dominant_value)))
                connection.execute(
                    """
                    UPDATE pm_state SET last_trigger = 1,
                        episode_generation = ?, episode_id = ?, dominant_value = ?,
                        recovered_at = NULL, last_evaluated_at = ?
                    WHERE monitor_id = ?
                    """,
                    (
                        generation,
                        episode_id,
                        int(bool(dominant_value)),
                        evaluated_at,
                        monitor_id,
                    ),
                )
            elif trigger:
                connection.execute(
                    "UPDATE pm_state SET last_evaluated_at = ? WHERE monitor_id = ?",
                    (evaluated_at, monitor_id),
                )
            elif last_trigger:
                connection.execute(
                    """
                    UPDATE pm_state SET last_trigger = 0, recovered_at = ?,
                        last_evaluated_at = ? WHERE monitor_id = ?
                    """,
                    (evaluated_at, evaluated_at, monitor_id),
                )
            else:
                connection.execute(
                    "UPDATE pm_state SET last_evaluated_at = ? WHERE monitor_id = ?",
                    (evaluated_at, monitor_id),
                )

            if trigger and episode_id:
                self._enqueue_outbox_in_txn(
                    connection,
                    kind="degeneration",
                    monitor_id=monitor_id,
                    episode_id=str(episode_id),
                    idempotency_key=(
                        f"process-degeneration/{monitor_id}/{episode_id}"
                    ),
                    payload={
                        "title": f"判定プロセス失敗疑い: {registry['display_name']}",
                        "monitor_id": monitor_id,
                        "display_name": registry["display_name"],
                        "window_start": window_start,
                        "window_end": evaluated_at,
                        "true_count": true_count,
                        "false_count": false_count,
                        "N": sample_count,
                        "dominance": dominance,
                        "dominant_value": dominant_value,
                        "min_samples": int(registry["min_samples"]),
                        "threshold": float(registry["threshold"]),
                        "telemetry_failure_count": failure_count,
                        "original_decision_unchanged": True,
                        "automatic_assignment": False,
                    },
                )
            connection.commit()

        return {
            "monitor_id": monitor_id,
            "cutoff": evaluated_at,
            "window_start": window_start,
            "true_count": true_count,
            "false_count": false_count,
            "N": sample_count,
            "dominance": dominance,
            "dominant_value": dominant_value,
            "trigger": trigger,
            "episode_id": str(episode_id) if trigger and episode_id else None,
            "telemetry_failure_count": failure_count,
        }

    def reconcile(self, *, cutoff: float | None = None) -> list[dict[str, Any]]:
        evaluated_at = self.clock() if cutoff is None else float(cutoff)
        return [
            self.evaluate(item["monitor_id"], cutoff=evaluated_at)
            for item in self.list_monitors()
        ]

    def list_failures(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM pm_failures ORDER BY first_seen_at, episode_id"
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = _json_object(item.pop("details_json"))
            result.append(item)
        return result

    def pending_outbox(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM pm_outbox
                WHERE delivered_task_id IS NULL
                   OR delivered_payload_digest IS NULL
                   OR delivered_payload_digest != payload_digest
                ORDER BY created_at, outbox_id
                """
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _json_object(item.pop("payload_json"))
            result.append(item)
        return result

    def mark_delivered(self, outbox_id: str, task_id: str) -> None:
        if not task_id:
            raise ValueError("task_id is required")
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE pm_outbox SET delivered_task_id = ?,
                    delivered_payload_digest = payload_digest,
                    attempts = attempts + 1,
                    last_error = NULL, updated_at = ? WHERE outbox_id = ?
                """,
                (task_id, self.clock(), outbox_id),
            )
            if updated.rowcount != 1:
                raise ValueError(f"unknown outbox id: {outbox_id}")
            health_rows = connection.execute(
                """
                SELECT event_id FROM process_monitor_health
                WHERE failure_type = 'sink-delivery-failed'
                  AND subject_key = ? AND active = 1
                """,
                (outbox_id,),
            ).fetchall()
            connection.execute(
                """
                UPDATE process_monitor_health SET active = 0, updated_at = ?
                WHERE failure_type = 'sink-delivery-failed' AND subject_key = ?
                """,
                (self.clock(), outbox_id),
            )
            for row in health_rows:
                connection.execute(
                    """
                    UPDATE owner_alert_outbox SET acknowledged_at = ?, updated_at = ?
                    WHERE alert_id = ?
                    """,
                    (self.clock(), self.clock(), row["event_id"]),
                )

    def mark_delivery_failed(self, outbox_id: str, error: str) -> str:
        now = self.clock()
        event_id = _digest("sink-delivery-failed", outbox_id)
        payload = {
            "failure_type": "sink-delivery-failed",
            "outbox_id": outbox_id,
            "error": str(error)[:1000],
        }
        encoded = _canonical(payload)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE pm_outbox SET attempts = attempts + 1, last_error = ?,
                    updated_at = ? WHERE outbox_id = ?
                """,
                (str(error)[:1000], now, outbox_id),
            )
            connection.execute(
                """
                INSERT INTO process_monitor_health (
                    event_id, failure_type, subject_key, details_json,
                    created_at, updated_at
                ) VALUES (?, 'sink-delivery-failed', ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    details_json = excluded.details_json,
                    active = 1,
                    updated_at = excluded.updated_at
                """,
                (event_id, outbox_id, encoded, now, now),
            )
            connection.execute(
                """
                INSERT INTO owner_alert_outbox (
                    alert_id, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (event_id, encoded, now, now),
            )
            connection.commit()
        return event_id

    def integrity_check(self) -> str:
        with self._connect() as connection:
            return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
