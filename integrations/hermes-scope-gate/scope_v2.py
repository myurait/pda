"""PDA task-scope control v2.

Natural-language meaning is supplied by the executor as a source-bound
ScopeFrame and reviewed by an independent reviewer.  This module never derives
scope or risk from keywords, regular expressions, or task classes.  It only
binds provenance, persists the reviewed plan, and deterministically contains
subsequent effects.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shlex
import sqlite3
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

try:  # Hermes loads the plugin as a namespaced package.
    from .process_monitor import ProcessMonitorStore
except ImportError:  # Direct CLI/test import from the plugin directory.
    from process_monitor import ProcessMonitorStore


_ALLOWED_STATES = {
    "inference-pending",
    "reviewed",
    "review-blocked",
    "locked",
    "audit-blocked",
    "completed",
}
_ALLOWED_EFFECTS = {
    "file-write",
    "git-stage",
    "git-commit",
    "git-push",
    "service-reload",
    "process-manage",
    "external-send",
    "memory-write",
    "schedule-write",
}
_READ_ONLY_TOOLS = {
    "read_file",
    "search_files",
    "web_search",
    "web_extract",
    "session_search",
    "skill_view",
    "skills_list",
    "vision_analyze",
    "todo",
    "scope_gate",
}
_TERMINAL_READ_ONLY = {
    ("git", "status"),
    ("git", "diff"),
    ("git", "log"),
    ("git", "show"),
    ("git", "branch"),
    ("git", "rev-parse"),
    ("git", "ls-remote"),
    ("git", "worktree", "list"),
    ("systemctl", "--user", "status"),
    ("systemctl", "--user", "show"),
    ("systemctl", "--user", "is-active"),
    ("systemctl", "--user", "is-enabled"),
    ("systemctl", "--user", "list-units"),
    ("systemctl", "--user", "list-unit-files"),
    ("hermes", "status"),
    ("hermes", "plugins", "list"),
    ("hermes", "hooks", "doctor"),
    ("hermes", "config", "get"),
}
_SHELL_CONTROL = {"|", "||", "&&", ";", ">", ">>", "<", "&"}


class ScopeReviewer(Protocol):
    def review(self, request: dict[str, object]) -> dict[str, object]: ...

    def audit(self, request: dict[str, object]) -> dict[str, object]: ...


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    action: str
    reason: str
    resolved_target: str = ""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(*parts: object) -> str:
    return hashlib.sha256(
        "\x1f".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def _instruction_digest(instruction: str) -> str:
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()


def _normalize_patterns(raw: Any, field: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(
        isinstance(item, str) and item.strip() for item in raw
    ):
        raise ValueError(f"{field} must be an array of non-empty strings")
    if len(raw) > 64:
        raise ValueError(f"{field} contains too many patterns")
    result: list[str] = []
    for item in raw:
        value = item.strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        parts = Path(value).parts
        if not value or value.startswith("/") or ".." in parts or any(ord(c) < 32 for c in value):
            raise ValueError(f"unsafe {field} pattern: {item!r}")
        if value not in result:
            result.append(value)
    return result


def _normalize_worktrees(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("containment.worktrees must be a non-empty array")
    if len(raw) > 8:
        raise ValueError("containment.worktrees contains too many entries")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("containment.worktrees must contain non-empty strings")
        path = Path(item).expanduser()
        if not path.is_absolute():
            raise ValueError("containment worktrees must be absolute")
        normalized = str(path.resolve())
        if normalized not in result:
            result.append(normalized)
    return result


def normalize_containment(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("containment must be an object")
    worktrees = _normalize_worktrees(raw.get("worktrees"))
    effects_raw = raw.get("allowed_effects") or []
    if not isinstance(effects_raw, list) or not all(isinstance(item, str) for item in effects_raw):
        raise ValueError("containment.allowed_effects must be a string array")
    effects = sorted(set(effects_raw))
    unknown_effects = sorted(set(effects) - _ALLOWED_EFFECTS)
    if unknown_effects:
        raise ValueError("unknown effect kinds: " + ", ".join(unknown_effects))
    commands = raw.get("command_allowlist") or []
    if not isinstance(commands, list) or not all(
        isinstance(item, str) and item.strip() for item in commands
    ):
        raise ValueError("containment.command_allowlist must be a string array")
    if len(commands) > 32:
        raise ValueError("containment.command_allowlist contains too many commands")
    services = raw.get("services") or []
    if not isinstance(services, list) or not all(
        isinstance(item, str) and item.strip() for item in services
    ):
        raise ValueError("containment.services must be a string array")
    remotes = raw.get("remotes") or []
    if not isinstance(remotes, list) or not all(isinstance(item, dict) for item in remotes):
        raise ValueError("containment.remotes must be an object array")
    normalized_remotes: list[dict[str, str]] = []
    for item in remotes:
        repository = Path(str(item.get("repository") or "")).expanduser()
        remote = str(item.get("remote") or "").strip()
        branch = str(item.get("branch") or "").strip()
        if not repository.is_absolute() or not remote or not branch:
            raise ValueError("each remote requires absolute repository, remote, and branch")
        normalized_remotes.append(
            {
                "repository": str(repository.resolve()),
                "remote": remote,
                "branch": branch,
            }
        )
    execution = raw.get("execution") or []
    if not isinstance(execution, list) or not all(isinstance(item, str) for item in execution):
        raise ValueError("containment.execution must be a string array")
    allowed_execution = {"focused-test", "syntax-check"}
    if set(execution) - allowed_execution:
        raise ValueError("containment.execution has an unknown template")
    max_tool_calls = raw.get("max_tool_calls", 96)
    if not isinstance(max_tool_calls, int) or not 1 <= max_tool_calls <= 500:
        raise ValueError("containment.max_tool_calls must be between 1 and 500")
    return {
        "worktrees": worktrees,
        "write_paths": _normalize_patterns(raw.get("write_paths"), "write_paths"),
        "test_paths": _normalize_patterns(raw.get("test_paths"), "test_paths"),
        "allowed_effects": effects,
        "command_allowlist": [item.strip() for item in commands],
        "services": sorted(set(item.strip() for item in services)),
        "remotes": normalized_remotes,
        "execution": sorted(set(execution)),
        "max_tool_calls": max_tool_calls,
    }


def _pattern_within(candidate: str, ceiling: str) -> bool:
    if candidate == ceiling:
        return True
    if ceiling.endswith("/**"):
        prefix = ceiling[:-3].rstrip("/")
        literal_candidate = candidate.split("*", 1)[0].split("?", 1)[0].rstrip("/")
        return bool(prefix and (literal_candidate == prefix or literal_candidate.startswith(prefix + "/")))
    return False


def _containment_within_seed(containment: Mapping[str, Any], seed: Mapping[str, Any]) -> bool:
    seed_root = str(Path(str(seed.get("worktree") or "")).expanduser().resolve())
    if any(root != seed_root for root in containment["worktrees"]):
        return False
    for field in ("write_paths", "test_paths"):
        ceiling = [str(item) for item in seed.get(field, [])]
        for candidate in containment[field]:
            if not any(_pattern_within(candidate, item) for item in ceiling):
                return False
    effect_map = {"stage": "git-stage", "commit": "git-commit"}
    seeded_effects = {
        effect_map[item]
        for item in seed.get("git_write", [])
        if item in effect_map
    }
    requested_git = {
        item
        for item in containment["allowed_effects"]
        if item in {"git-stage", "git-commit"}
    }
    return requested_git <= seeded_effects


def _path_in_scope(target: str, containment: Mapping[str, Any]) -> tuple[bool, str, str]:
    candidate = Path(target).expanduser()
    if not candidate.is_absolute():
        return False, "", ""
    resolved = candidate.resolve(strict=False)
    patterns = list(containment["write_paths"]) + list(containment["test_paths"])
    for root_text in containment["worktrees"]:
        root = Path(root_text)
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative == ".git" or relative.startswith(".git/"):
            return False, root_text, relative
        if any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns):
            return True, root_text, relative
        # A literal file path is also a valid one-file pattern.
        if relative in patterns:
            return True, root_text, relative
        return False, root_text, relative
    return False, "", ""


def _safe_tokens(command: str) -> list[str] | None:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not tokens or any(token in _SHELL_CONTROL for token in tokens):
        return None
    return tokens


def _terminal_is_read_only(tokens: Sequence[str]) -> bool:
    for prefix in _TERMINAL_READ_ONLY:
        if tuple(tokens[: len(prefix)]) == prefix:
            return True
    if tuple(tokens[:2]) in {("pwd",), ("date",)}:  # pragma: no cover - defensive shape
        return True
    return tokens[0] in {"pwd", "date", "printf"}


def admit_unbound_tool(tool_name: str, args: Mapping[str, Any]) -> GateDecision:
    """Fail closed for effects when no current v2 turn was created."""

    if tool_name in _READ_ONLY_TOOLS:
        return GateDecision(True, "unbound-read", "read-only/control tool")
    if tool_name == "terminal":
        tokens = _safe_tokens(str(args.get("command") or ""))
        if tokens is not None and _terminal_is_read_only(tokens):
            return GateDecision(True, "unbound-read", "deterministic read-only command")
    return GateDecision(
        False,
        "v2-turn-required",
        "mutation requires a current source-bound v2 turn",
    )


class ScopeV2Store:
    def __init__(
        self,
        path: str | Path,
        *,
        monitor: ProcessMonitorStore | None = None,
        clock: Callable[[], float] = time.time,
        seed_loader: Callable[..., dict[str, Any] | None] | None = None,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.monitor = monitor or ProcessMonitorStore(self.path)
        self.seed_loader = seed_loader
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS scope_v2_turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL DEFAULT '',
                    instruction_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    scope_frame_json TEXT,
                    plan_json TEXT,
                    containment_json TEXT,
                    review_json TEXT,
                    additional_assurance_required INTEGER NOT NULL DEFAULT 0,
                    audit_json TEXT,
                    completion_status TEXT,
                    completion_summary TEXT,
                    tool_calls INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS scope_v2_binding
                    ON scope_v2_turns(task_id, session_id, updated_at);
                CREATE TABLE IF NOT EXISTS scope_v2_tool_calls (
                    turn_id TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (turn_id, tool_call_id)
                );
                CREATE TABLE IF NOT EXISTS scope_v2_effects (
                    turn_id TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    result TEXT NOT NULL,
                    evidence_digest TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (turn_id, tool_call_id, kind, target)
                );
                """
            )

    def start_turn(
        self,
        *,
        turn_id: str,
        session_id: str,
        task_id: str = "",
        instruction_sha256: str,
    ) -> dict[str, Any]:
        if not turn_id or not session_id:
            raise ValueError("turn_id and session_id are required")
        if len(instruction_sha256) != 64 or any(c not in "0123456789abcdef" for c in instruction_sha256):
            raise ValueError("instruction_sha256 must be a lowercase SHA-256 digest")
        now = self.clock()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM scope_v2_turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if existing is not None:
                if (
                    existing["instruction_sha256"] != instruction_sha256
                    or existing["session_id"] != session_id
                    or existing["task_id"] != task_id
                ):
                    raise ValueError("turn identity or instruction digest drift")
                return self._decode_turn(existing)
            connection.execute(
                """
                INSERT INTO scope_v2_turns (
                    turn_id, session_id, task_id, instruction_sha256,
                    state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'inference-pending', ?, ?)
                """,
                (turn_id, session_id, task_id, instruction_sha256, now, now),
            )
            row = connection.execute(
                "SELECT * FROM scope_v2_turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
        return self._decode_turn(row)

    @staticmethod
    def _decode_turn(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for source, target in (
            ("scope_frame_json", "scope_frame"),
            ("plan_json", "plan"),
            ("containment_json", "containment"),
            ("review_json", "review"),
            ("audit_json", "audit"),
        ):
            raw = result.pop(source, None)
            result[target] = json.loads(raw) if raw else None
        result["additional_assurance_required"] = bool(
            result["additional_assurance_required"]
        )
        return result

    def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scope_v2_turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
        return self._decode_turn(row) if row is not None else None

    def resolve_turn_id(
        self,
        *,
        turn_id: str = "",
        task_id: str = "",
        session_id: str = "",
    ) -> str:
        with self._connect() as connection:
            if turn_id:
                row = connection.execute(
                    "SELECT turn_id FROM scope_v2_turns WHERE turn_id = ?", (turn_id,)
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
            if task_id:
                row = connection.execute(
                    """
                    SELECT turn_id FROM scope_v2_turns
                    WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1
                    """,
                    (task_id,),
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
            if session_id:
                row = connection.execute(
                    """
                    SELECT turn_id FROM scope_v2_turns
                    WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
        return ""

    @staticmethod
    def _validate_scope_frame(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("scope_frame must be an object")
        required = {
            "directive_relation",
            "required_outcomes",
            "targets",
            "allowed_means",
            "completion_predicates",
            "non_goals",
            "uncertainties",
            "source_refs",
        }
        missing = sorted(required - set(value))
        if missing:
            raise ValueError("scope_frame is missing: " + ", ".join(missing))
        relation = value.get("directive_relation")
        if relation not in {"new", "continue", "amend", "replace", "report", "stop"}:
            raise ValueError("scope_frame.directive_relation is invalid")
        for field in required - {"directive_relation"}:
            item = value.get(field)
            if not isinstance(item, list) or not all(isinstance(part, str) for part in item):
                raise ValueError(f"scope_frame.{field} must be a string array")
        if not value["required_outcomes"] and relation not in {"report", "stop"}:
            raise ValueError("scope_frame.required_outcomes is empty")
        if not value["source_refs"]:
            raise ValueError("scope_frame.source_refs is empty")
        return value

    @staticmethod
    def _validate_review(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("reviewer result must be an object")
        required = {
            "scope_verdict",
            "scope_findings",
            "risk",
            "risk_basis",
            "additional_assurance_required",
            "post_work_audit_must_establish",
            "reviewer_note",
        }
        missing = sorted(required - set(value))
        if missing:
            raise ValueError("reviewer result is missing: " + ", ".join(missing))
        if value["scope_verdict"] not in {"pass", "revise", "block"}:
            raise ValueError("reviewer scope_verdict is invalid")
        if value["risk"] not in {"low", "medium", "high", "critical"}:
            raise ValueError("reviewer risk is invalid")
        if type(value["additional_assurance_required"]) is not bool:
            raise ValueError("reviewer assurance flag must be boolean")
        for field in ("scope_findings", "risk_basis", "post_work_audit_must_establish"):
            if not isinstance(value[field], list):
                raise ValueError(f"reviewer {field} must be an array")
        return dict(value)

    def review_scope(
        self,
        *,
        turn_id: str,
        instruction: str,
        scope_frame: Mapping[str, Any],
        plan: Sequence[str],
        containment: Mapping[str, Any],
        reviewer: ScopeReviewer,
    ) -> dict[str, Any]:
        turn = self.get_turn(turn_id)
        if turn is None:
            raise ValueError("unknown scope turn")
        if turn["state"] not in {"inference-pending", "review-blocked"}:
            raise ValueError(f"turn cannot be reviewed from {turn['state']}")
        if _instruction_digest(instruction) != turn["instruction_sha256"]:
            raise ValueError("current instruction does not match the bound digest")
        frame = self._validate_scope_frame(dict(scope_frame))
        if not isinstance(plan, Sequence) or isinstance(plan, (str, bytes)) or not plan:
            raise ValueError("plan must be a non-empty string array")
        normalized_plan = [str(item).strip() for item in plan]
        if not all(normalized_plan):
            raise ValueError("plan entries must be non-empty")
        normalized_containment = normalize_containment(dict(containment))
        seed = None
        if self.seed_loader is not None and turn["task_id"]:
            seed = self.seed_loader(turn["task_id"], session_id=turn["session_id"])
        if seed is not None and not _containment_within_seed(normalized_containment, seed):
            reason = "reviewed containment would exceed the assignment seed"
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE scope_v2_turns SET state = 'review-blocked',
                        scope_frame_json = ?, plan_json = ?, containment_json = ?,
                        review_json = ?, updated_at = ? WHERE turn_id = ?
                    """,
                    (
                        _canonical(frame),
                        _canonical(normalized_plan),
                        _canonical(normalized_containment),
                        _canonical({"scope_verdict": "block", "reason": reason}),
                        self.clock(),
                        turn_id,
                    ),
                )
            result = self.get_turn(turn_id)
            assert result is not None
            result["reason"] = reason
            return result

        frame_digest = hashlib.sha256(_canonical(frame).encode("utf-8")).hexdigest()
        plan_digest = hashlib.sha256(_canonical(normalized_plan).encode("utf-8")).hexdigest()
        containment_digest = hashlib.sha256(
            _canonical(normalized_containment).encode("utf-8")
        ).hexdigest()
        review_request_id = _hash(turn_id, frame_digest, plan_digest, containment_digest)
        now = self.clock()
        self.monitor.record_expected(
            monitor_id="scope.prework.additional-assurance-required",
            join_key=review_request_id,
            event_id=_hash("scope-prework-request/v1", review_request_id, frame_digest, plan_digest),
            occurred_at=now,
            due_at=now + 300,
            metadata={"turn_id": turn_id},
        )
        request: dict[str, object] = {
            "instruction": instruction,
            "scope_frame": frame,
            "plan": normalized_plan,
            "containment": normalized_containment,
            "review_request_id": review_request_id,
            "requirements": {
                "judge_over_or_under_interpretation": True,
                "assign_risk": True,
                "set_additional_assurance_required": True,
                "natural_language_deterministic_classification_forbidden": True,
            },
        }
        try:
            reviewed = self._validate_review(reviewer.review(request))
        except Exception as exc:
            with self._connect() as connection:
                connection.execute(
                    "UPDATE scope_v2_turns SET state = 'review-blocked', updated_at = ? WHERE turn_id = ?",
                    (self.clock(), turn_id),
                )
            result = self.get_turn(turn_id)
            assert result is not None
            result["reason"] = f"independent review failed closed: {type(exc).__name__}: {exc}"
            return result

        self.monitor.record_decision(
            monitor_id="scope.prework.additional-assurance-required",
            join_key=review_request_id,
            event_id=_hash("scope-prework-completed/v1", review_request_id, _canonical(reviewed)),
            verdict=bool(reviewed["additional_assurance_required"]),
            occurred_at=self.clock(),
            accepted_at=self.clock(),
            metadata={
                "review_id": reviewed.get("review_id"),
                "risk": reviewed["risk"],
                "scope_verdict": reviewed["scope_verdict"],
            },
        )
        self.monitor.evaluate(
            "scope.prework.additional-assurance-required", cutoff=self.clock()
        )
        next_state = "reviewed" if reviewed["scope_verdict"] == "pass" else "review-blocked"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE scope_v2_turns SET state = ?, scope_frame_json = ?,
                    plan_json = ?, containment_json = ?, review_json = ?,
                    additional_assurance_required = ?, updated_at = ?
                WHERE turn_id = ?
                """,
                (
                    next_state,
                    _canonical(frame),
                    _canonical(normalized_plan),
                    _canonical(normalized_containment),
                    _canonical(reviewed),
                    int(bool(reviewed["additional_assurance_required"])),
                    self.clock(),
                    turn_id,
                ),
            )
        result = self.get_turn(turn_id)
        assert result is not None
        return result

    def lock_turn(self, *, turn_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM scope_v2_turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError("unknown scope turn")
            if turn["state"] != "reviewed":
                raise ValueError(f"turn cannot lock from {turn['state']}")
            if not turn["containment_json"] or not turn["review_json"]:
                raise ValueError("reviewed containment is missing")
            connection.execute(
                "UPDATE scope_v2_turns SET state = 'locked', updated_at = ? WHERE turn_id = ?",
                (self.clock(), turn_id),
            )
            connection.commit()
        result = self.get_turn(turn_id)
        assert result is not None
        return result

    @staticmethod
    def _fingerprint(tool_name: str, args: Mapping[str, Any]) -> str:
        return hashlib.sha256(
            _canonical({"tool_name": tool_name, "args": dict(args)}).encode("utf-8")
        ).hexdigest()

    def _reserve_tool_call(
        self,
        connection: sqlite3.Connection,
        *,
        turn: sqlite3.Row,
        tool_call_id: str,
        tool_name: str,
        args: Mapping[str, Any],
    ) -> GateDecision | None:
        fingerprint = self._fingerprint(tool_name, args)
        if tool_call_id:
            existing = connection.execute(
                """
                SELECT fingerprint, decision FROM scope_v2_tool_calls
                WHERE turn_id = ? AND tool_call_id = ?
                """,
                (turn["turn_id"], tool_call_id),
            ).fetchone()
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    return GateDecision(
                        False,
                        "hook-argument-drift",
                        "tool arguments changed after the pre-tool review",
                    )
                return None
        if int(turn["tool_calls"]) >= int(json.loads(turn["containment_json"])["max_tool_calls"]):
            return GateDecision(False, "tool-budget-exhausted", "reviewed tool budget is exhausted")
        connection.execute(
            "UPDATE scope_v2_turns SET tool_calls = tool_calls + 1, updated_at = ? WHERE turn_id = ?",
            (self.clock(), turn["turn_id"]),
        )
        if tool_call_id:
            connection.execute(
                """
                INSERT INTO scope_v2_tool_calls (
                    turn_id, tool_call_id, fingerprint, decision, created_at
                ) VALUES (?, ?, ?, 'reserved', ?)
                """,
                (turn["turn_id"], tool_call_id, fingerprint, self.clock()),
            )
        return None

    def admit_tool(
        self,
        *,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        args: Mapping[str, Any],
    ) -> GateDecision:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM scope_v2_turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                connection.commit()
                return GateDecision(False, "unbound-turn", "no v2 scope turn is bound")
            state = str(turn["state"])
            read_decision: GateDecision | None = None
            if tool_name in _READ_ONLY_TOOLS:
                read_decision = GateDecision(
                    True, "read-or-control", "read-only or scope control tool"
                )
            elif tool_name == "terminal":
                tokens = _safe_tokens(str(args.get("command") or ""))
                if tokens is not None and _terminal_is_read_only(tokens):
                    read_decision = GateDecision(
                        True,
                        "read-only-terminal",
                        "deterministic read-only command",
                    )
            if read_decision is not None:
                if state == "locked":
                    reserved = self._reserve_tool_call(
                        connection,
                        turn=turn,
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        args=args,
                    )
                    if reserved is not None:
                        connection.commit()
                        return reserved
                connection.commit()
                return read_decision
            if state != "locked":
                connection.commit()
                return GateDecision(
                    False,
                    "review-or-lock-required" if state in {"inference-pending", "reviewed"} else "turn-blocked",
                    f"mutation is not admitted while the v2 turn is {state}",
                )
            reserved = self._reserve_tool_call(
                connection,
                turn=turn,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                args=args,
            )
            if reserved is not None:
                connection.commit()
                return reserved
            containment = json.loads(turn["containment_json"])
            decision = self._admit_locked(tool_name, args, containment)
            if tool_call_id:
                connection.execute(
                    """
                    UPDATE scope_v2_tool_calls SET decision = ?
                    WHERE turn_id = ? AND tool_call_id = ?
                    """,
                    (decision.action, turn_id, tool_call_id),
                )
            connection.commit()
            return decision

    def _admit_locked(
        self,
        tool_name: str,
        args: Mapping[str, Any],
        containment: Mapping[str, Any],
    ) -> GateDecision:
        if tool_name in {"write_file", "patch"}:
            if "file-write" not in containment["allowed_effects"]:
                return GateDecision(False, "effect-not-reviewed", "file writes were not reviewed")
            target = str(args.get("path") or "")
            inside, _, _ = _path_in_scope(target, containment)
            if not inside:
                return GateDecision(
                    False,
                    "target-outside-reviewed-scope",
                    "write target is outside the reviewed containment",
                    target,
                )
            return GateDecision(True, "reviewed-file-write", "target is inside reviewed containment", target)
        if tool_name == "terminal":
            return self._admit_terminal(args, containment)
        effect_by_tool = {
            "memory": "memory-write",
            "cronjob": "schedule-write",
        }
        needed = effect_by_tool.get(tool_name)
        if needed and needed in containment["allowed_effects"]:
            return GateDecision(True, needed, "effect kind was independently reviewed")
        return GateDecision(False, "unknown-effect", "tool effect has no reviewed deterministic mapping")

    @staticmethod
    def _admit_terminal(
        args: Mapping[str, Any], containment: Mapping[str, Any]
    ) -> GateDecision:
        command = str(args.get("command") or "").strip()
        tokens = _safe_tokens(command)
        if tokens is None:
            return GateDecision(False, "shell-composition-denied", "compound or invalid shell syntax")
        workdir_raw = str(args.get("workdir") or "").strip()
        workdir = str(Path(workdir_raw).expanduser().resolve()) if workdir_raw else ""
        if workdir and not any(
            workdir == root or workdir.startswith(root + os.sep)
            for root in containment["worktrees"]
        ):
            return GateDecision(False, "workdir-outside-reviewed-scope", "terminal workdir is outside containment")
        if _terminal_is_read_only(tokens):
            return GateDecision(True, "read-only-terminal", "deterministic read-only command", workdir)
        if command in containment["command_allowlist"]:
            if "process-manage" not in containment["allowed_effects"]:
                return GateDecision(
                    False,
                    "effect-not-reviewed",
                    "an exact command also requires the process-manage effect kind",
                )
            return GateDecision(True, "reviewed-exact-command", "exact command was independently reviewed", workdir)
        if tokens[:2] == ["git", "add"]:
            if "git-stage" not in containment["allowed_effects"]:
                return GateDecision(False, "effect-not-reviewed", "git staging was not reviewed")
            paths = [token for token in tokens[2:] if token != "--" and not token.startswith("-")]
            if not paths or not workdir:
                return GateDecision(False, "git-stage-unbounded", "git add requires explicit reviewed paths")
            for item in paths:
                target = item if Path(item).is_absolute() else str(Path(workdir) / item)
                if not _path_in_scope(target, containment)[0]:
                    return GateDecision(False, "target-outside-reviewed-scope", "git add path is outside containment")
            return GateDecision(True, "git-stage", "explicit staged paths are reviewed", workdir)
        if tokens[:2] == ["git", "commit"]:
            if "git-commit" not in containment["allowed_effects"]:
                return GateDecision(False, "effect-not-reviewed", "git commit was not reviewed")
            if any(token in {"--no-verify", "-n", "--amend"} for token in tokens[2:]):
                return GateDecision(False, "git-commit-unsafe", "commit cannot bypass hooks or amend history")
            return GateDecision(True, "git-commit", "local commit was independently reviewed", workdir)
        if tokens[:2] == ["git", "push"]:
            if "git-push" not in containment["allowed_effects"]:
                return GateDecision(False, "effect-not-reviewed", "git push was not reviewed")
            if len(tokens) != 4 or any(token.startswith("-") for token in tokens[2:]):
                return GateDecision(False, "git-push-unbounded", "push requires exact remote and branch")
            remote, branch = tokens[2], tokens[3]
            allowed = any(
                item["repository"] == workdir
                and item["remote"] == remote
                and item["branch"] == branch
                for item in containment["remotes"]
            )
            return GateDecision(
                allowed,
                "git-push" if allowed else "git-push-target-mismatch",
                "exact reviewed remote ref" if allowed else "remote ref was not reviewed",
                workdir,
            )
        service_prefixes = {
            ("systemctl", "--user", "restart"),
            ("systemctl", "--user", "reload"),
            ("systemctl", "--user", "try-restart"),
        }
        if tuple(tokens[:3]) in service_prefixes:
            if "service-reload" not in containment["allowed_effects"]:
                return GateDecision(False, "effect-not-reviewed", "service reload was not reviewed")
            if len(tokens) != 4 or tokens[3] not in containment["services"]:
                return GateDecision(False, "service-target-mismatch", "service unit was not reviewed")
            return GateDecision(True, "service-reload", "exact service unit was reviewed", tokens[3])
        return GateDecision(False, "command-not-reviewed", "command is not in reviewed deterministic containment")

    def record_tool_result(
        self,
        *,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        args: Mapping[str, Any],
        status: str,
        result: Any,
    ) -> None:
        """Persist an observed effect without copying raw tool output."""

        turn = self.get_turn(turn_id)
        if turn is None or turn["containment"] is None:
            return
        kind = ""
        target = ""
        if tool_name in {"write_file", "patch"}:
            kind = "file-write"
            target = str(args.get("path") or "")
        elif tool_name == "terminal":
            command = str(args.get("command") or "").strip()
            tokens = _safe_tokens(command)
            if tokens is None:
                return
            workdir_raw = str(args.get("workdir") or "").strip()
            workdir = str(Path(workdir_raw).expanduser().resolve()) if workdir_raw else ""
            if tokens[:2] == ["git", "add"]:
                kind, target = "git-stage", workdir
            elif tokens[:2] == ["git", "commit"]:
                kind, target = "git-commit", workdir
            elif tokens[:2] == ["git", "push"] and len(tokens) >= 4:
                kind = "git-push"
                target = f"{workdir}::{tokens[2]}::{tokens[3]}"
            elif tuple(tokens[:3]) in {
                ("systemctl", "--user", "restart"),
                ("systemctl", "--user", "reload"),
                ("systemctl", "--user", "try-restart"),
            } and len(tokens) == 4:
                kind, target = "service-reload", tokens[3]
            elif command in turn["containment"]["command_allowlist"]:
                kind, target = "process-manage", "command:" + _hash(command)
        if not kind:
            return
        exit_code = result.get("exit_code") if isinstance(result, dict) else None
        outcome = "ok" if status == "ok" and exit_code in {None, 0} else "failed-or-unresolved"
        evidence_digest = _hash(
            tool_name,
            _canonical(dict(args)),
            status,
            exit_code,
            type(result).__name__,
        )
        stable_call_id = tool_call_id or self._fingerprint(tool_name, args)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scope_v2_effects (
                    turn_id, tool_call_id, kind, target, result,
                    evidence_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_id, tool_call_id, kind, target) DO UPDATE SET
                    result = excluded.result,
                    evidence_digest = excluded.evidence_digest
                """,
                (
                    turn_id,
                    stable_call_id,
                    kind,
                    target,
                    outcome,
                    evidence_digest,
                    self.clock(),
                ),
            )

    def observed_effects(self, turn_id: str) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT kind, target, result, evidence_digest
                FROM scope_v2_effects WHERE turn_id = ?
                ORDER BY created_at, tool_call_id, kind, target
                """,
                (turn_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _effects_conform(
        effects: Sequence[Mapping[str, Any]], containment: Mapping[str, Any]
    ) -> tuple[bool, list[str]]:
        findings: list[str] = []
        for index, effect in enumerate(effects):
            kind = str(effect.get("kind") or "")
            target = str(effect.get("target") or "")
            if kind not in containment["allowed_effects"]:
                findings.append(f"effect[{index}] kind {kind!r} was not reviewed")
                continue
            if kind == "file-write" and not _path_in_scope(target, containment)[0]:
                findings.append(f"effect[{index}] target is outside reviewed paths")
            elif kind in {"git-stage", "git-commit"}:
                resolved = str(Path(target).expanduser().resolve()) if target else ""
                if resolved not in containment["worktrees"]:
                    findings.append(f"effect[{index}] git worktree was not reviewed")
            elif kind == "git-push":
                if not any(
                    target == f"{item['repository']}::{item['remote']}::{item['branch']}"
                    for item in containment["remotes"]
                ):
                    findings.append(f"effect[{index}] remote target was not reviewed")
            elif kind == "service-reload" and target not in containment["services"]:
                findings.append(f"effect[{index}] service target was not reviewed")
        return not findings, findings

    def mark_final_audit_required(self, turn_id: str) -> dict[str, Any]:
        turn = self.get_turn(turn_id)
        if turn is None:
            raise ValueError("unknown scope turn")
        existing_audit = turn.get("audit")
        if isinstance(existing_audit, dict) and existing_audit.get("final_audit_request_id"):
            return existing_audit
        request_id = _hash(
            "scope-final-required",
            turn_id,
            turn["instruction_sha256"],
            turn.get("scope_frame") and _canonical(turn["scope_frame"]),
        )
        now = self.clock()
        self.monitor.record_expected(
            monitor_id="scope.final.final-scope-conformant",
            join_key=request_id,
            event_id=_hash("scope-final-audit-required/v1", turn_id, request_id),
            occurred_at=now,
            due_at=now,
            metadata={"turn_id": turn_id, "implicit_final_boundary": True},
        )
        marker = {"final_audit_request_id": request_id, "required_at": now}
        with self._connect() as connection:
            connection.execute(
                "UPDATE scope_v2_turns SET audit_json = ?, updated_at = ? WHERE turn_id = ?",
                (_canonical(marker), now, turn_id),
            )
        return marker

    def complete_read_only_turn(self, turn_id: str) -> dict[str, Any]:
        turn = self.get_turn(turn_id)
        if turn is None:
            raise ValueError("unknown scope turn")
        if turn["state"] == "completed":
            return turn
        allowed_states = {"inference-pending", "reviewed", "review-blocked"}
        if turn["state"] not in allowed_states or self.observed_effects(turn_id):
            raise ValueError("only a non-terminal no-effect turn can auto-complete")
        completion_status = (
            "blocked"
            if turn["state"] == "review-blocked"
            else "partial" if turn["state"] == "reviewed" else "success"
        )
        marker = self.mark_final_audit_required(turn_id)
        request_id = str(marker["final_audit_request_id"])
        now = self.clock()
        self.monitor.record_decision(
            monitor_id="scope.final.final-scope-conformant",
            join_key=request_id,
            event_id=_hash("scope-final-audit-completed/v1", request_id, True, "no-effects"),
            verdict=True,
            occurred_at=now,
            accepted_at=now,
            metadata={"turn_id": turn_id, "no_effects": True},
        )
        self.monitor.evaluate("scope.final.final-scope-conformant", cutoff=now)
        audit = {
            **marker,
            "executor_final_scope_conformant": True,
            "mechanically_conformant": True,
            "final_scope_conformant": True,
            "observed_effects": [],
        }
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE scope_v2_turns SET state = 'completed', audit_json = ?,
                    completion_status = ?, completion_summary = 'no effects',
                    updated_at = ? WHERE turn_id = ?
                """,
                (_canonical(audit), completion_status, now, turn_id),
            )
        result = self.get_turn(turn_id)
        assert result is not None
        return result

    def complete_turn(
        self,
        *,
        turn_id: str,
        status: str,
        observed_effects: Sequence[Mapping[str, Any]],
        final_scope_conformant: bool,
        completion_summary: str,
        instruction: str,
        reviewer: ScopeReviewer,
    ) -> dict[str, Any]:
        if status not in {"success", "partial", "blocked", "failed", "interrupted"}:
            raise ValueError("invalid completion status")
        if type(final_scope_conformant) is not bool:
            raise ValueError("final_scope_conformant must be boolean")
        if not isinstance(observed_effects, Sequence) or isinstance(observed_effects, (str, bytes)):
            raise ValueError("observed_effects must be an array")
        if not completion_summary.strip():
            raise ValueError("completion_summary is required")
        turn = self.get_turn(turn_id)
        if turn is None:
            raise ValueError("unknown scope turn")
        if turn["state"] != "locked":
            raise ValueError(f"turn cannot complete from {turn['state']}")
        if _instruction_digest(instruction) != turn["instruction_sha256"]:
            raise ValueError("current instruction does not match the bound digest")
        claimed_effects = [dict(item) for item in observed_effects]
        actual_effects = self.observed_effects(turn_id)
        effects_by_key: dict[tuple[str, str], dict[str, Any]] = {
            (str(item.get("kind") or ""), str(item.get("target") or "")): item
            for item in claimed_effects
        }
        for item in actual_effects:
            effects_by_key[(item["kind"], item["target"])] = item
        effects = list(effects_by_key.values())
        mechanically_conformant, mechanical_findings = self._effects_conform(
            effects, turn["containment"]
        )
        claimed_conformant = bool(final_scope_conformant and mechanically_conformant)
        frame_digest = hashlib.sha256(
            _canonical(turn["scope_frame"]).encode("utf-8")
        ).hexdigest()
        audit_request_id = _hash("scope-final-audit", turn_id, frame_digest)
        now = self.clock()
        self.monitor.record_expected(
            monitor_id="scope.final.final-scope-conformant",
            join_key=audit_request_id,
            event_id=_hash("scope-final-audit-required/v1", turn_id, frame_digest),
            occurred_at=now,
            due_at=now + 300,
            metadata={"turn_id": turn_id},
        )
        audit: dict[str, Any] | None = None
        independent_pass = True
        if turn["additional_assurance_required"]:
            request: dict[str, object] = {
                "instruction": instruction,
                "reviewed_scope_frame": turn["scope_frame"],
                "reviewed_plan": turn["plan"],
                "reviewed_containment": turn["containment"],
                "prework_review": turn["review"],
                "observed_effects": effects,
                "completion_status": status,
                "completion_summary": completion_summary,
                "executor_final_scope_conformant": final_scope_conformant,
                "mechanical_findings": mechanical_findings,
            }
            try:
                raw_audit = reviewer.audit(request)
                if not isinstance(raw_audit, dict):
                    raise ValueError("independent audit must return an object")
                if raw_audit.get("audit_verdict") not in {"pass", "needs_changes", "block"}:
                    raise ValueError("independent audit verdict is invalid")
                if type(raw_audit.get("scope_conformant")) is not bool:
                    raise ValueError("independent audit scope_conformant must be boolean")
                audit = dict(raw_audit)
                independent_pass = bool(
                    audit["audit_verdict"] == "pass" and audit["scope_conformant"]
                )
            except Exception as exc:
                audit = {
                    "audit_verdict": "block",
                    "scope_conformant": False,
                    "findings": [f"independent audit failed closed: {type(exc).__name__}: {exc}"],
                }
                independent_pass = False
        final_verdict = bool(claimed_conformant and independent_pass)
        self.monitor.record_decision(
            monitor_id="scope.final.final-scope-conformant",
            join_key=audit_request_id,
            event_id=_hash(
                "scope-final-audit-completed/v1",
                audit_request_id,
                _canonical(
                    {
                        "final_verdict": final_verdict,
                        "audit": audit,
                        "mechanical_findings": mechanical_findings,
                    }
                ),
            ),
            verdict=final_verdict,
            occurred_at=self.clock(),
            accepted_at=self.clock(),
            metadata={
                "turn_id": turn_id,
                "independent_audit_id": audit.get("audit_id") if audit else None,
            },
        )
        self.monitor.evaluate("scope.final.final-scope-conformant", cutoff=self.clock())
        next_state = "completed" if final_verdict else "audit-blocked"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE scope_v2_turns SET state = ?, audit_json = ?,
                    completion_status = ?, completion_summary = ?, updated_at = ?
                WHERE turn_id = ?
                """,
                (
                    next_state,
                    _canonical(
                        {
                            "executor_final_scope_conformant": final_scope_conformant,
                            "mechanically_conformant": mechanically_conformant,
                            "mechanical_findings": mechanical_findings,
                            "independent": audit,
                            "final_scope_conformant": final_verdict,
                            "observed_effects": effects,
                        }
                    ),
                    status,
                    completion_summary,
                    self.clock(),
                    turn_id,
                ),
            )
        result = self.get_turn(turn_id)
        assert result is not None
        result["ok"] = next_state == "completed"
        if not result["ok"]:
            result["reason"] = "final scope audit did not pass"
        return result

    def integrity_check(self) -> str:
        with self._connect() as connection:
            return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
