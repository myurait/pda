"""Deterministic PDA task-scope admission policy.

The module intentionally uses only the Python standard library so the same
validator can run in-process as a Hermes plugin and out-of-process as a
fail-closed shell hook.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

_STATE_MENTION_RE = re.compile(
    r"(?:"
    r"(?:commit|コミット)\s*[,、/]\s*(?:push|プッシュ)していない|"
    r"(?:commit|push)していない|(?:コミット|プッシュ)(?:して|されて)いない|"
    r"未(?:commit|push|コミット|プッシュ)|uncommitted|unpushed"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TaskIntent:
    task_class: str
    allow_commit: bool = False
    allow_push: bool = False
    explicit_global: bool = False


_CLOSEOUT_RE = re.compile(
    r"(?:(?<!未)(?<![A-Za-z0-9_])commit(?![A-Za-z0-9_])|(?<!未)(?<![A-Za-z0-9_])push(?![A-Za-z0-9_])|(?<!未)コミット|(?<!未)プッシュ|保存して|保存せよ|close[ -]?out)",
    re.IGNORECASE,
)
_CHANGE_RE = re.compile(
    r"(?:実装|修正|変更|解消|作成|追加|削除|導入|反映|直して|調査|設計|分析|"
    r"(?<![A-Za-z0-9_])fix(?:ed|es|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])implement(?:ation|ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])resolve(?:d|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])edit(?:ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])refactor(?:ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])test(?:s|ed|ing)?(?![A-Za-z0-9_])|テスト)",
    re.IGNORECASE,
)
_GLOBAL_RE = re.compile(
    r"(?:全(?:て|部)?(?:の)?(?:branch(?:es)?|ブランチ|worktree|作業ツリー|repository|repo|リポジトリ)|"
    r"all\s+(?:branches|worktrees|repositories|repos)|"
    r"every\s+(?:branch|worktree|repository|repo))",
    re.IGNORECASE,
)
# --- S2/S3 rollout, stage G0: deterministic classification only. ---
# The classes below are recorded on the turn contract for audit and gold-set
# calibration; admission keeps treating every non-closeout class as
# not-enforced until their admission functions are activated in a later
# rollout stage.
_BROAD_MISSION_RE = re.compile(
    r"(?:全面|全体|大規模|包括|徹底|作り直|再設計|"
    r"(?<![A-Za-z0-9_])redesign(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])migrat(?:e|ion|ing)(?![A-Za-z0-9_])|移行|"
    r"(?<![A-Za-z0-9_])audit(?![A-Za-z0-9_])|監査)",
    re.IGNORECASE,
)
_BOUNDED_OP_RE = re.compile(
    r"(?:再起動|リスタート|再読込|有効化|無効化|切り?替え|"
    r"(?<![A-Za-z0-9_])restart(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])reload(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])enable(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])disable(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])cutover(?![A-Za-z0-9_]))",
    re.IGNORECASE,
)
_BOUNDED_TARGET_RE = re.compile(
    r"(?:[\w.-]+\.(?:service|timer)|gateway|dashboard|daemon|デーモン|"
    r"サービス|systemd|(?<![A-Za-z0-9_])timer(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])cron(?![A-Za-z0-9_])|valve|pipe|plugin|プラグイン|"
    r"container|コンテナ|docker)",
    re.IGNORECASE,
)
_ARTIFACT_CHANGE_RE = re.compile(
    r"(?:実装|修正|変更|解消|作成|追加|削除|導入|反映|直して|"
    r"(?<![A-Za-z0-9_])fix(?:ed|es|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])implement(?:ation|ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])resolve(?:d|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])edit(?:ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])refactor(?:ed|s|ing)?(?![A-Za-z0-9_]))",
    re.IGNORECASE,
)


def _classify_non_closeout(text: str) -> TaskIntent:
    """Deterministic class for requests that are not repository closeouts.

    Conservative by design: any broad-mission marker keeps the wider
    ``audit-only`` class so a large piece of work is never misfiled into a
    narrow, budget-capped class (design gold-set requirement). Investigation,
    analysis, and design requests also stay ``audit-only``.
    """
    if _BROAD_MISSION_RE.search(text):
        return TaskIntent(task_class="audit-only")
    if (
        _BOUNDED_OP_RE.search(text)
        and _BOUNDED_TARGET_RE.search(text)
        and not _ARTIFACT_CHANGE_RE.search(text)
    ):
        return TaskIntent(task_class="bounded-operation")
    if _ARTIFACT_CHANGE_RE.search(text):
        return TaskIntent(task_class="artifact-change")
    return TaskIntent(task_class="audit-only")


_REPOSITORY_CONTEXT_RE = re.compile(
    r"(?:\bgit\b|repo(?:sitory)?|worktree|branch|origin|remote|changes?|results?|"
    r"リポジトリ|作業ツリー|ブランチ|差分|成果|資源|"
    r"未(?:commit|push|コミット|プッシュ)|uncommitted|unpushed)",
    re.IGNORECASE,
)
_EXPLICIT_ACTION_RE = re.compile(
    r"(?:"
    r"(?:commit|push|コミット|プッシュ).{0,30}(?:してくれ|してください|せよ|しろ|すること|して)|"
    r"(?:please|can\s+you)\s+(?:commit|push)|"
    r"(?:commit|push)\s+(?:this|these|the|current|my)\b|"
    r"^\s*(?:commit|push)(?:\s*(?:and|,|/|&)\s*(?:commit|push))*\s*[.!。]?\s*$"
    r")",
    re.IGNORECASE,
)


def classify_task(user_message: str) -> TaskIntent:
    """Classify the request into a deterministic task class.

    Any explicit content-changing verb wins over commit/push wording, so a
    change request never becomes a closeout. Non-closeout requests are
    classified by :func:`_classify_non_closeout` for audit and gold-set
    calibration; only ``repository-closeout`` is enforced in the current
    rollout stage (every other class stays not-enforced at admission).
    """

    text = user_message or ""
    action_text = _STATE_MENTION_RE.sub("", text)
    if _CHANGE_RE.search(text) or not _CLOSEOUT_RE.search(action_text):
        return _classify_non_closeout(text)

    commit_requested = bool(
        re.search(
            r"(?:(?<!未)(?<![A-Za-z0-9_])commit(?![A-Za-z0-9_])|(?<!未)コミット)",
            action_text,
            re.IGNORECASE,
        )
    )
    push_requested = bool(
        re.search(
            r"(?:(?<!未)(?<![A-Za-z0-9_])push(?![A-Za-z0-9_])|(?<!未)プッシュ)",
            action_text,
            re.IGNORECASE,
        )
    )
    save_requested = bool(
        re.search(r"保存して|保存せよ|close[ -]?out", action_text, re.IGNORECASE)
    )
    repository_context = bool(_REPOSITORY_CONTEXT_RE.search(text))
    explicit_action = bool(_EXPLICIT_ACTION_RE.search(action_text))
    if ("?" in text or "？" in text) and not explicit_action:
        return _classify_non_closeout(text)

    commit_requested = commit_requested and (explicit_action or repository_context)
    push_requested = push_requested and (
        explicit_action or repository_context or commit_requested
    )
    save_requested = save_requested and (
        repository_context
        or bool(re.search(r"close[ -]?out", action_text, re.IGNORECASE))
    )
    if not (commit_requested or push_requested or save_requested):
        return _classify_non_closeout(text)
    return TaskIntent(
        task_class="repository-closeout",
        allow_commit=commit_requested or save_requested,
        allow_push=push_requested,
        explicit_global=bool(_GLOBAL_RE.search(text)),
    )


# G3 expansion review (design doc §6): per-class number of expansion
# reviews a single turn may consume. Classes not listed here have no
# expansion budget. Hard bounds always stay with the deterministic
# validator; an LLM judge is only a pluggable second opinion.
EXPANSION_REVIEW_BUDGET = {
    "repository-closeout": 0,
    "bounded-operation": 1,
    "artifact-change": 2,
}
EXPANSION_PERMIT_TTL_SECONDS = 300.0


def action_fingerprint(tool_name: str, args: dict[str, Any]) -> str:
    """Canonical sha256 fingerprint of a tool action (name + arguments)."""
    return hashlib.sha256(
        json.dumps([tool_name, args], sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    action: str
    reason: str
    resource: str = ""


class GateStore:
    """SQLite-backed, process-safe scope state and budget reservation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=3.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 3000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    origin_sha256 TEXT NOT NULL,
                    task_class TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    allow_commit INTEGER NOT NULL,
                    allow_push INTEGER NOT NULL,
                    explicit_global INTEGER NOT NULL,
                    contract_json TEXT,
                    tool_count INTEGER NOT NULL DEFAULT 0,
                    denied_count INTEGER NOT NULL DEFAULT 0,
                    completion_status TEXT
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    turn_id TEXT NOT NULL,
                    call_key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    execution_status TEXT NOT NULL DEFAULT 'pending',
                    evidence_value TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (turn_id, call_key)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    turn_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (turn_id, path)
                );
                CREATE TABLE IF NOT EXISTS expansion_permits (
                    turn_id TEXT NOT NULL,
                    action_fingerprint TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    outcome_reason TEXT NOT NULL DEFAULT '',
                    estimated_cost_json TEXT NOT NULL DEFAULT '',
                    verdict TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL,
                    PRIMARY KEY (turn_id, action_fingerprint)
                );
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(turns)").fetchall()
            }
            if "task_id" not in columns:
                connection.execute(
                    "ALTER TABLE turns ADD COLUMN task_id TEXT NOT NULL DEFAULT ''"
                )
            decision_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(decisions)").fetchall()
            }
            if "execution_status" not in decision_columns:
                connection.execute(
                    "ALTER TABLE decisions ADD COLUMN execution_status TEXT NOT NULL DEFAULT 'pending'"
                )
            if "evidence_value" not in decision_columns:
                connection.execute(
                    "ALTER TABLE decisions ADD COLUMN evidence_value TEXT NOT NULL DEFAULT ''"
                )

    def purge_expired(
        self,
        *,
        now: float | None = None,
        retention_days: int = 30,
    ) -> int:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        cutoff = (time.time() if now is None else float(now)) - retention_days * 86400
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT turn_id FROM turns
                WHERE started_at < ?
                """,
                (cutoff,),
            ).fetchall()
            turn_ids = [str(row["turn_id"]) for row in rows]
            if turn_ids:
                placeholders = ",".join("?" for _ in turn_ids)
                connection.execute(
                    f"DELETE FROM decisions WHERE turn_id IN ({placeholders})",
                    turn_ids,
                )
                connection.execute(
                    f"DELETE FROM candidates WHERE turn_id IN ({placeholders})",
                    turn_ids,
                )
                connection.execute(
                    f"DELETE FROM turns WHERE turn_id IN ({placeholders})",
                    turn_ids,
                )
            connection.commit()
        return len(turn_ids)

    def start_turn(
        self,
        *,
        turn_id: str,
        session_id: str,
        task_id: str = "",
        user_message: str,
    ) -> TaskIntent:
        self.purge_expired()
        intent = classify_task(user_message)
        state = "discovering" if intent.task_class == "repository-closeout" else "audit"
        digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO turns (
                    turn_id, session_id, task_id, origin_sha256, task_class, state,
                    started_at, allow_commit, allow_push, explicit_global
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_id) DO NOTHING
                """,
                (
                    turn_id,
                    session_id,
                    task_id,
                    digest,
                    intent.task_class,
                    state,
                    time.time(),
                    int(intent.allow_commit),
                    int(intent.allow_push),
                    int(intent.explicit_global),
                ),
            )
        return intent

    def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
        return dict(row) if row is not None else None

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
                    "SELECT turn_id FROM turns WHERE turn_id = ?", (turn_id,)
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
            if task_id:
                row = connection.execute(
                    """
                    SELECT turn_id FROM turns
                    WHERE task_id = ? AND completion_status IS NULL
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (task_id,),
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
            if session_id:
                row = connection.execute(
                    """
                    SELECT turn_id FROM turns
                    WHERE session_id = ? AND completion_status IS NULL
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
        return ""

    def lock_turn(
        self,
        *,
        turn_id: str,
        repositories: list[str],
        worktrees: list[str],
        branches: list[str],
    ) -> dict[str, Any]:
        canonical_repositories = self._canonical_targets(repositories)
        canonical_worktrees = self._canonical_targets(worktrees)
        clean_branches = sorted({str(branch).strip() for branch in branches if str(branch).strip()})
        if not canonical_repositories or not canonical_worktrees or not clean_branches:
            raise ValueError("repository-closeout requires non-empty repositories, worktrees, and branches")
        if any(branch.startswith("-") or any(ch.isspace() for ch in branch) for branch in clean_branches):
            raise ValueError("branch names must be concrete, non-option tokens")

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None or turn["task_class"] != "repository-closeout":
                raise ValueError("turn is not a repository-closeout")
            if turn["state"] == "locked" and turn["contract_json"]:
                connection.commit()
                return json.loads(turn["contract_json"])
            if turn["state"] != "discovering":
                raise ValueError(f"turn cannot lock from state {turn['state']!r}")
            candidate_rows = connection.execute(
                "SELECT path FROM candidates WHERE turn_id = ?", (turn_id,)
            ).fetchall()
            candidates = {row["path"] for row in candidate_rows}
            requested = set(canonical_repositories) | set(canonical_worktrees)
            if not requested.issubset(candidates):
                raise ValueError("targets must come from this turn's bounded discovery")
            if not turn["explicit_global"] and len(canonical_worktrees) != 1:
                raise ValueError("non-global closeout can lock exactly one worktree")
            worktree_branches = _validated_worktree_branches(canonical_worktrees)
            actual_branches = sorted(set(worktree_branches.values()))
            if set(clean_branches) != set(actual_branches):
                raise ValueError(
                    "locked branches must exactly match current worktree branches: "
                    + ", ".join(actual_branches)
                )

            target_count = len(canonical_worktrees)
            max_calls = min(32, 8 + 3 * target_count)
            required = []
            if turn["allow_commit"]:
                required.append("commit-existing-content")
            if turn["allow_push"]:
                required.append("push-requested-commit")
            contract: dict[str, Any] = {
                "schema": "pda.scope-contract/v1",
                "turn_id": turn_id,
                "origin_message_sha256": turn["origin_sha256"],
                "task_class": "repository-closeout",
                "objective": "save only existing commit-ready repository content as requested",
                "targets": {
                    "repositories": canonical_repositories,
                    "worktrees": canonical_worktrees,
                    "branches": clean_branches,
                    "worktree_branches": worktree_branches,
                },
                "actions": {
                    "required": required,
                    "prerequisite": [
                        "inventory-status",
                        "inspect-candidate-diff",
                        "targeted-integrity-check",
                    ],
                    "verification": ["remote-ref-equals-local-head"] if turn["allow_push"] else ["commit-created"],
                    "forbidden": [
                        "edit-content",
                        "resolve-conflict",
                        "run-broad-tests",
                        "create-or-delete-worktree",
                        "wait-unrelated-process",
                        "deploy-or-restart",
                        "delegate-or-background",
                    ],
                },
                "completion": {
                    "all": [
                        "every commit-ready target has the requested commit",
                        *(
                            ["every pushed commit is reachable from its intended remote ref"]
                            if turn["allow_push"]
                            else []
                        ),
                    ],
                    "blocked_targets_may_be_reported": True,
                },
                "budget": {
                    "max_wall_seconds": 900,
                    "max_tool_calls": max_calls,
                    "max_denied_calls": 3,
                    "max_expansions": 0,
                    "background_processes": 0,
                    "subagents": 0,
                },
                "state": "locked",
            }
            _validate_contract_against_schema(contract)
            encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True)
            connection.execute(
                "UPDATE turns SET state = 'locked', contract_json = ? WHERE turn_id = ?",
                (encoded, turn_id),
            )
            connection.commit()
            return contract

    @staticmethod
    def _canonical_targets(targets: list[str]) -> list[str]:
        result: set[str] = set()
        for raw in targets:
            value = str(raw).strip()
            path = Path(value)
            if not value or not path.is_absolute():
                raise ValueError("targets must be absolute paths")
            result.add(str(path.resolve()))
        return sorted(result)

    def record_worktree_candidates(self, *, turn_id: str, paths: list[str]) -> int:
        canonical = self._canonical_targets(paths)
        if len(canonical) > 64:
            raise ValueError("worktree inventory exceeds the bounded 64-target limit")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None or turn["task_class"] != "repository-closeout":
                raise ValueError("unknown repository-closeout turn")
            if turn["state"] != "discovering" or not turn["explicit_global"]:
                raise ValueError("worktree candidates require explicit global discovery")
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO candidates (turn_id, path, source) VALUES (?, ?, ?)",
                [(turn_id, path, "inventory-worktrees-result") for path in canonical],
            )
            added = connection.total_changes - before
            connection.commit()
        return added

    def record_tool_result(
        self,
        *,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        status: str,
        result: Any,
    ) -> None:
        fingerprint = hashlib.sha256(
            json.dumps([tool_name, args], sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        call_key = tool_call_id or fingerprint
        execution_status = (
            "succeeded"
            if _tool_result_succeeded(status, result, tool_name=tool_name)
            else "failed"
        )
        evidence_value = _normalized_git_evidence(
            tool_name=tool_name,
            args=args,
            result=result,
            succeeded=execution_status == "succeeded",
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE decisions SET execution_status = ?, evidence_value = ?
                WHERE turn_id = ? AND call_key = ? AND fingerprint = ?
                """,
                (execution_status, evidence_value, turn_id, call_key, fingerprint),
            )
            connection.commit()

    def request_expansion(
        self,
        *,
        turn_id: str,
        tool_name: str,
        args: dict[str, Any],
        reason: str,
        estimated_cost: dict[str, Any] | None = None,
        judge: Any = None,
        ttl_seconds: float = EXPANSION_PERMIT_TTL_SECONDS,
    ) -> dict[str, Any]:
        """G3 expansion review (design doc §6).

        Review order: (1) deterministic deny — no class budget, budget
        exhausted, or a forbidden/foreign action; (2) deterministic allow —
        the contract already permits the action, so no permit is needed;
        (3) independent judge when the class permits one and a ``judge``
        callable is supplied; (4) otherwise fail closed. Permits are bound
        to the exact action fingerprint, are one-use, and expire after
        ``ttl_seconds``. Hard bounds stay with this deterministic validator:
        a judge can only approve what stages 1-2 did not already settle.
        """
        if not tool_name:
            raise ValueError(
                "expansion review requires a candidate tool_name; "
                "repository-closeout has zero expansion budget and always denies"
            )
        fingerprint = action_fingerprint(tool_name, args)
        now = time.time()
        cost_json = json.dumps(estimated_cost or {}, sort_keys=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                connection.commit()
                raise ValueError("unknown turn")
            prior = connection.execute(
                "SELECT * FROM expansion_permits "
                "WHERE turn_id = ? AND action_fingerprint = ?",
                (turn_id, fingerprint),
            ).fetchone()
            if prior is not None:
                connection.commit()
                return self._render_permit(prior)

            task_class = turn["task_class"]
            budget = int(EXPANSION_REVIEW_BUDGET.get(task_class, 0))
            reviews_used = connection.execute(
                "SELECT COUNT(*) FROM expansion_permits WHERE turn_id = ?",
                (turn_id,),
            ).fetchone()[0]

            verdict, reviewer, outcome_reason = "deny", "deterministic-deny", ""
            already_allowed = False
            if budget <= 0:
                outcome_reason = (
                    f"{task_class} has zero expansion budget; report the blocker"
                )
            elif reviews_used >= budget:
                outcome_reason = (
                    f"expansion review budget exhausted ({reviews_used}/{budget})"
                )
            else:
                # Stage 2 deterministic allow: only meaningful for classes
                # whose admission is enforced (locked closeout today).
                if task_class == "repository-closeout" and turn["state"] == "locked":
                    admitted = self._admit_closeout_locked(turn, tool_name, args)
                    if admitted.allowed:
                        verdict = "allow"
                        reviewer = "deterministic-allow"
                        already_allowed = True
                        outcome_reason = (
                            "the contract already permits this action; no permit needed"
                        )
                if not outcome_reason:
                    if judge is None:
                        reviewer = "fail-closed"
                        outcome_reason = (
                            "no independent scope reviewer is available; "
                            "expansion fails closed"
                        )
                    else:
                        try:
                            payload = {
                                "turn_id": turn_id,
                                "task_class": task_class,
                                "origin_sha256": turn["origin_sha256"],
                                "contract": json.loads(turn["contract_json"])
                                if turn["contract_json"]
                                else None,
                                "tool_name": tool_name,
                                "resource": json.dumps(args, sort_keys=True, default=str)[:500],
                                "reason": reason,
                                "estimated_cost": estimated_cost or {},
                                "action_fingerprint": fingerprint,
                            }
                            result = judge(payload)
                            if isinstance(result, dict) and bool(result.get("allow")):
                                verdict = "allow"
                                reviewer = "judge"
                                outcome_reason = str(
                                    result.get("reason") or "approved by scope reviewer"
                                )
                            else:
                                reviewer = "judge"
                                rejected = (
                                    result.get("reason")
                                    if isinstance(result, dict)
                                    else None
                                )
                                outcome_reason = (
                                    str(rejected)
                                    if rejected
                                    else "rejected by scope reviewer"
                                )
                        except Exception:
                            verdict = "deny"
                            reviewer = "fail-closed"
                            outcome_reason = "scope reviewer failed; expansion fails closed"

            expires_at = now + max(0.0, float(ttl_seconds))
            consumed_at = now if already_allowed else None
            connection.execute(
                """
                INSERT INTO expansion_permits (
                    turn_id, action_fingerprint, tool_name, resource, reason,
                    outcome_reason, estimated_cost_json, verdict, reviewer,
                    created_at, expires_at, consumed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    fingerprint,
                    tool_name,
                    json.dumps(args, sort_keys=True, default=str)[:500],
                    reason,
                    outcome_reason,
                    cost_json,
                    verdict,
                    reviewer,
                    now,
                    expires_at,
                    consumed_at,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM expansion_permits "
                "WHERE turn_id = ? AND action_fingerprint = ?",
                (turn_id, fingerprint),
            ).fetchone()
            return self._render_permit(row)

    @staticmethod
    def _render_permit(row) -> dict[str, Any]:
        return {
            "ok": row["verdict"] == "allow",
            "verdict": row["verdict"],
            "reviewer": row["reviewer"],
            "reason": row["outcome_reason"],
            "action_fingerprint": row["action_fingerprint"],
            "expires_at": row["expires_at"],
            "consumed": row["consumed_at"] is not None,
        }

    def _consume_permit_locked(
        self, connection: sqlite3.Connection, turn_id: str, fingerprint: str
    ) -> bool:
        """One-use consumption inside an open BEGIN IMMEDIATE transaction."""
        cur = connection.execute(
            """
            UPDATE expansion_permits
               SET consumed_at = ?
             WHERE turn_id = ? AND action_fingerprint = ?
               AND verdict = 'allow' AND consumed_at IS NULL
               AND expires_at > ?
            """,
            (time.time(), turn_id, fingerprint, time.time()),
        )
        return cur.rowcount == 1

    def finalize_turn(self, *, turn_id: str, status: str) -> dict[str, Any]:
        if status not in {"success", "partial", "blocked", "failed", "interrupted"}:
            raise ValueError("invalid completion status")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError("unknown scope turn")
            if turn["completion_status"] is not None:
                connection.commit()
                return dict(turn)
            if status == "success" and turn["task_class"] == "repository-closeout":
                evidence = connection.execute(
                    """
                    SELECT action, evidence_value, rowid AS sequence FROM decisions
                    WHERE turn_id = ? AND verdict = 'allow' AND execution_status = 'succeeded'
                    ORDER BY rowid ASC
                    """,
                    (turn_id,),
                ).fetchall()
                latest_by_action: dict[str, tuple[int, str]] = {}
                for row in evidence:
                    latest_by_action[str(row["action"])] = (
                        int(row["sequence"]),
                        str(row["evidence_value"] or ""),
                    )
                required: list[str] = []
                if turn["allow_commit"]:
                    required.append("commit-existing-content")
                if turn["allow_push"]:
                    required.append("push-requested-commit")
                missing = [action for action in required if action not in latest_by_action]
                if not required:
                    missing.append("requested-closeout-action")
                if not missing and turn["allow_push"]:
                    last_required = max(latest_by_action[action][0] for action in required)
                    local = latest_by_action.get("verify-local-head", (0, ""))
                    remote = latest_by_action.get("verify-remote-ref", (0, ""))
                    if local[0] <= last_required or remote[0] <= last_required:
                        missing.append("post-push-ref-verification")
                    elif not local[1] or local[1] != remote[1]:
                        missing.append("remote-ref-equals-local-head")
                if missing:
                    connection.rollback()
                    raise ValueError(
                        "missing successful completion evidence: " + ", ".join(missing)
                    )
            next_state = "completed" if turn["task_class"] == "repository-closeout" else turn["state"]
            connection.execute(
                "UPDATE turns SET state = ?, completion_status = ? WHERE turn_id = ?",
                (next_state, status, turn_id),
            )
            connection.commit()
        result_row = self.get_turn(turn_id)
        if result_row is None:  # pragma: no cover
            raise RuntimeError("scope turn disappeared after finalization")
        return result_row

    def complete_turn(self, *, turn_id: str, status: str) -> dict[str, Any]:
        if status not in {"success", "partial", "blocked", "failed", "interrupted"}:
            raise ValueError("invalid completion status")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError("unknown scope turn")
            if turn["completion_status"] is not None:
                connection.commit()
                return dict(turn)
            if turn["task_class"] == "repository-closeout":
                connection.execute(
                    "UPDATE turns SET state = 'completed', completion_status = ? WHERE turn_id = ?",
                    (status, turn_id),
                )
            else:
                connection.execute(
                    "UPDATE turns SET completion_status = ? WHERE turn_id = ?",
                    (status, turn_id),
                )
            connection.commit()
        result = self.get_turn(turn_id)
        if result is None:  # pragma: no cover - protected by the transaction
            raise RuntimeError("scope turn disappeared after completion")
        return result

    def admit_tool(
        self,
        *,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> GateDecision:
        fingerprint = action_fingerprint(tool_name, args)
        call_key = tool_call_id or fingerprint
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM decisions WHERE turn_id = ? AND call_key = ?",
                (turn_id, call_key),
            ).fetchone()
            if prior is not None:
                if prior["fingerprint"] != fingerprint:
                    connection.execute(
                        "UPDATE turns SET denied_count = denied_count + 1 WHERE turn_id = ?",
                        (turn_id,),
                    )
                    connection.commit()
                    return GateDecision(
                        False,
                        "hook-argument-drift",
                        "the same tool-call id reached the gate with different arguments",
                    )
                connection.commit()
                return GateDecision(
                    allowed=prior["verdict"] == "allow",
                    action=prior["action"],
                    reason=prior["reason"],
                    resource=prior["resource"],
                )
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None or turn["task_class"] != "repository-closeout":
                connection.commit()
                return GateDecision(True, "not-enforced", "initial rollout audits this task class")

            if tool_name == "scope_gate":
                control_action = str(args.get("action") or "")
                if turn["denied_count"] >= 3 and control_action != "complete":
                    decision = GateDecision(
                        False,
                        "deny-budget",
                        "only scope completion is allowed after three denials",
                    )
                elif control_action in {"lock", "review", "complete"}:
                    decision = GateDecision(
                        True,
                        f"scope-{control_action}",
                        "scope control transition",
                    )
                else:
                    decision = GateDecision(
                        False,
                        "scope-control-invalid",
                        "scope_gate action must be lock, review, or complete",
                    )
            elif turn["state"] == "discovering":
                decision = self._admit_closeout_discovery(turn, tool_name, args)
            elif turn["state"] == "locked":
                decision = self._admit_closeout_locked(turn, tool_name, args)
                if not decision.allowed and self._consume_permit_locked(
                    connection, turn_id, fingerprint
                ):
                    decision = GateDecision(
                        True,
                        "expansion-permit",
                        "one-use expansion permit approved for this exact action",
                        decision.resource,
                    )
            else:
                decision = GateDecision(
                    False,
                    "turn-closed",
                    "scope contract is closed; report the result without more tools",
                )
            connection.execute(
                """
                INSERT INTO decisions (
                    turn_id, call_key, fingerprint, verdict, action, reason,
                    resource, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    call_key,
                    fingerprint,
                    "allow" if decision.allowed else "deny",
                    decision.action,
                    decision.reason,
                    decision.resource,
                    time.time(),
                ),
            )
            counter = "tool_count" if decision.allowed else "denied_count"
            connection.execute(
                f"UPDATE turns SET {counter} = {counter} + 1 WHERE turn_id = ?",
                (turn_id,),
            )
            if decision.allowed and decision.resource:
                connection.execute(
                    "INSERT OR IGNORE INTO candidates (turn_id, path, source) VALUES (?, ?, ?)",
                    (turn_id, decision.resource, decision.action),
                )
            connection.commit()
            return decision

    @staticmethod
    def _admit_closeout_discovery(
        turn: sqlite3.Row,
        tool_name: str,
        args: dict[str, Any],
    ) -> GateDecision:
        if turn["state"] != "discovering":
            return GateDecision(False, "state-invalid", "turn is not accepting discovery")
        if turn["tool_count"] >= 3:
            return GateDecision(False, "discovery-budget", "read-only discovery budget exhausted")
        if tool_name != "terminal":
            return GateDecision(False, "lock-required", "lock the closeout target before this tool")
        command = str(args.get("command") or "").strip()
        workdir = str(args.get("workdir") or "").strip()
        if not workdir or not Path(workdir).is_absolute():
            return GateDecision(False, "target-missing", "git discovery requires an absolute workdir")
        if re.fullmatch(r"git status(?:\s+(?:--short|--branch|--porcelain(?:=v1)?))*", command):
            resource = str(Path(workdir).resolve())
            return GateDecision(True, "inventory-status", "bounded target discovery", resource)
        if turn["explicit_global"] and command == "git worktree list --porcelain":
            resource = str(Path(workdir).resolve())
            return GateDecision(True, "inventory-worktrees", "explicit all-worktree discovery", resource)
        return GateDecision(False, "lock-required", "only bounded git status discovery is allowed before lock")

    @staticmethod
    def _admit_closeout_locked(
        turn: sqlite3.Row,
        tool_name: str,
        args: dict[str, Any],
    ) -> GateDecision:
        contract = json.loads(turn["contract_json"] or "{}")
        budget = contract.get("budget", {})
        if time.time() - float(turn["started_at"]) > int(budget.get("max_wall_seconds", 0)):
            return GateDecision(False, "wall-budget", "repository closeout exceeded 15 minutes")
        if turn["tool_count"] >= int(budget.get("max_tool_calls", 0)):
            return GateDecision(False, "tool-budget", "repository closeout tool budget exhausted")
        if turn["denied_count"] >= int(budget.get("max_denied_calls", 0)):
            return GateDecision(False, "deny-budget", "too many denied expansion attempts")

        targets = [str(Path(path).resolve()) for path in contract["targets"]["worktrees"]]
        worktree_branches = {
            str(Path(path).resolve()): str(branch)
            for path, branch in contract["targets"]["worktree_branches"].items()
        }
        if tool_name in {"read_file", "search_files"}:
            raw_path = str(args.get("path") or "")
            if not raw_path or not Path(raw_path).is_absolute():
                return GateDecision(False, "target-missing", "read-only inspection needs an absolute target path")
            resolved = str(Path(raw_path).resolve())
            if not any(_is_within(resolved, target) for target in targets):
                return GateDecision(False, "target-closed", "read target is outside the locked worktree")
            return GateDecision(True, "inspect-candidate-diff", "read-only inspection inside locked target", resolved)

        if tool_name != "terminal":
            return GateDecision(False, "expansion-zero", f"{tool_name} is outside repository-closeout scope")
        if bool(args.get("background")) or bool(args.get("pty")):
            return GateDecision(False, "background-forbidden", "background and interactive commands are not allowed")
        command = str(args.get("command") or "").strip()
        workdir = str(args.get("workdir") or "").strip()
        if not workdir or not Path(workdir).is_absolute():
            return GateDecision(False, "target-missing", "terminal closeout commands require an absolute workdir")
        resolved_workdir = str(Path(workdir).resolve())
        if resolved_workdir not in targets:
            return GateDecision(False, "target-closed", "terminal workdir is outside the locked target set")
        expected_branch = worktree_branches.get(resolved_workdir)
        if not expected_branch:
            return GateDecision(False, "target-closed", "locked worktree has no branch binding")
        branches = {expected_branch}
        try:
            tokens = _tokenize_single_shell_command(command)
        except PermissionError:
            return GateDecision(False, "compound-command", "compound or shell-composed commands are not admitted")
        except ValueError:
            return GateDecision(False, "command-parse", "terminal command could not be parsed")
        if len(tokens) < 2 or tokens[0] != "git":
            return GateDecision(False, "non-git-command", "only recognized git closeout commands are admitted")
        subcommand = tokens[1]
        tail = tokens[2:]
        if subcommand in {"add", "commit", "push"}:
            try:
                current_branch = _validated_worktree_branches([resolved_workdir])[
                    resolved_workdir
                ]
            except ValueError as exc:
                return GateDecision(False, "target-drift", str(exc))
            if current_branch != expected_branch:
                return GateDecision(
                    False,
                    "target-drift",
                    "worktree branch changed after scope lock",
                )

        if subcommand == "status":
            return GateDecision(True, "inventory-status", "status of locked target", resolved_workdir)
        if subcommand == "diff":
            if not _diff_args_are_bounded(tail):
                return GateDecision(False, "diff-unsafe", "diff arguments can inspect outside the locked candidate")
            return GateDecision(True, "inspect-candidate-diff", "read-only diff of locked target", resolved_workdir)
        if subcommand in {"rev-parse", "ls-remote", "branch", "remote"}:
            verification_action = _verification_action(subcommand, tail, branches)
            if verification_action is None:
                return GateDecision(False, "verify-target", "verification arguments are outside the locked ref")
            return GateDecision(True, verification_action, "read-only closeout verification", resolved_workdir)
        if subcommand == "add":
            if not turn["allow_commit"]:
                return GateDecision(False, "commit-not-requested", "the user requested no commit")
            if not _add_args_are_bounded(tail):
                return GateDecision(False, "stage-unsafe", "stage arguments are outside bounded target paths")
            return GateDecision(True, "stage-existing-content", "stage existing locked-target content", resolved_workdir)
        if subcommand == "commit":
            if not turn["allow_commit"]:
                return GateDecision(False, "commit-not-requested", "the user requested no commit")
            forbidden = {
                "--amend",
                "--fixup",
                "--squash",
                "--no-verify",
                "-n",
                "-C",
                "-c",
                "--reuse-message",
                "--reedit-message",
                "--interactive",
                "-i",
            }
            if any(
                token in forbidden
                or token.startswith(("--fixup=", "--squash="))
                or _short_option_bundle_contains(token, {"n", "C", "c", "i"})
                for token in tail
            ):
                return GateDecision(False, "commit-rewrite", "history rewrite or hook bypass is outside closeout")
            if not _commit_args_are_bounded(tail):
                return GateDecision(False, "commit-unsafe", "commit arguments exceed bounded closeout syntax")
            return GateDecision(True, "commit-existing-content", "create the requested commit", resolved_workdir)
        if subcommand == "push":
            if not turn["allow_push"]:
                return GateDecision(False, "push-not-requested", "the user did not request push")
            forbidden_push = {
                "-f",
                "--force",
                "--force-with-lease",
                "--mirror",
                "--delete",
                "-d",
                "--all",
                "--tags",
                "--prune",
                "--no-verify",
            }
            if any(
                token in forbidden_push
                or token.startswith(("--force-with-lease=", "--delete="))
                or _short_option_bundle_contains(token, {"f", "d"})
                for token in tail
            ):
                return GateDecision(False, "push-destructive", "destructive or hook-bypassing push is outside closeout")
            if not _push_args_match_locked_ref(tail, branches):
                return GateDecision(False, "push-target", "push must name origin and only locked branches")
            return GateDecision(True, "push-requested-commit", "push requested locked-target ref", resolved_workdir)
        return GateDecision(False, "git-subcommand", f"git {subcommand} is outside repository-closeout scope")


def _validate_contract_against_schema(contract: dict[str, Any]) -> None:
    schema_path = Path(__file__).parent / "schemas" / "scope-contract-v1.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = import_module("jsonschema").Draft202012Validator
        validator.check_schema(schema)
        validator(schema).validate(contract)
    except Exception as exc:
        raise ValueError(f"ScopeContract schema validation failed: {exc}") from exc


def _validated_worktree_branches(worktrees: list[str]) -> dict[str, str]:
    branches: dict[str, str] = {}
    for worktree in worktrees:
        try:
            top_level = subprocess.run(
                ["git", "-C", worktree, "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "-C", worktree, "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"cannot verify Git worktree {worktree}: {exc}") from exc
        if str(Path(top_level).resolve()) != str(Path(worktree).resolve()):
            raise ValueError(f"target is not the Git worktree root: {worktree}")
        if not branch:
            raise ValueError(f"detached HEAD is not supported for closeout: {worktree}")
        branches[str(Path(worktree).resolve())] = branch
    return dict(sorted(branches.items()))


def _pathspec_is_bounded(token: str) -> bool:
    path = Path(token)
    return (
        token not in {".", "./"}
        and not any(character in token for character in "*?[")
        and not path.is_absolute()
        and ".." not in path.parts
    )


def _diff_args_are_bounded(args: list[str]) -> bool:
    safe_flags = {
        "--cached",
        "--staged",
        "--check",
        "--stat",
        "--name-only",
        "--name-status",
        "--summary",
        "--no-color",
        "--color=never",
    }
    path_mode = False
    for token in args:
        if token == "--":
            if path_mode:
                return False
            path_mode = True
        elif path_mode:
            if not _pathspec_is_bounded(token):
                return False
        elif token not in safe_flags:
            return False
    return True


def _verification_action(
    subcommand: str,
    args: list[str],
    branches: set[str],
) -> str | None:
    if subcommand == "rev-parse":
        if args in (["HEAD"], ["--verify", "HEAD"]):
            return "verify-local-head"
        if args == ["--abbrev-ref", "HEAD"]:
            return "verify-branch"
        return None
    if subcommand == "branch":
        return "verify-branch" if args == ["--show-current"] else None
    if subcommand == "remote":
        return "verify-remote" if args == ["get-url", "origin"] else None
    if subcommand == "ls-remote":
        filtered = [token for token in args if token == "--heads"]
        positional = [token for token in args if token != "--heads"]
        if len(filtered) != 1 or len(positional) != 2 or positional[0] != "origin":
            return None
        requested = positional[1]
        requested = requested.removeprefix("refs/heads/")
        return "verify-remote-ref" if requested in branches else None
    return None


def _short_option_bundle_contains(token: str, forbidden: set[str]) -> bool:
    return (
        token.startswith("-")
        and not token.startswith("--")
        and len(token) > 1
        and any(character in forbidden for character in token[1:])
    )


def _add_args_are_bounded(args: list[str]) -> bool:
    if args and args[0] == "--":
        args = args[1:]
    return bool(args) and all(
        not token.startswith("-") and _pathspec_is_bounded(token) for token in args
    )


def _commit_args_are_bounded(args: list[str]) -> bool:
    if not args:
        return False
    index = 0
    has_message = False
    single_flags = {"-a", "--all", "-s", "--signoff", "-q", "--quiet"}
    while index < len(args):
        token = args[index]
        if token == "-m":
            if index + 1 >= len(args):
                return False
            has_message = True
            index += 2
            continue
        if token.startswith("--message=") and len(token) > len("--message="):
            has_message = True
            index += 1
            continue
        if token not in single_flags:
            return False
        index += 1
    return has_message


def _push_args_match_locked_ref(args: list[str], branches: set[str]) -> bool:
    allowed_options = {"-u", "--set-upstream", "--porcelain"}
    positional = [token for token in args if token not in allowed_options]
    if len(positional) < 2 or positional[0] != "origin":
        return False
    for refspec in positional[1:]:
        if refspec.startswith("+"):
            return False
        source, separator, destination = refspec.partition(":")
        if not separator:
            if source not in branches:
                return False
            continue
        if source == "HEAD":
            normalized_destination = destination.removeprefix("refs/heads/")
            if normalized_destination not in branches:
                return False
            continue
        normalized_source = source.removeprefix("refs/heads/")
        normalized_destination = destination.removeprefix("refs/heads/")
        if normalized_source not in branches or normalized_destination not in branches:
            return False
    return True


def _tokenize_single_shell_command(command: str) -> list[str]:
    if "\n" in command or "\r" in command:
        raise PermissionError("multi-line shell command")
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    operators = set("|&;<>")
    for token in tokens:
        if token and all(character in operators for character in token):
            raise PermissionError("shell composition")
        if "$" in token or "`" in token or token.startswith("#"):
            raise PermissionError("shell expansion")
    return tokens


def _result_mapping(result: Any) -> dict[str, Any] | None:
    parsed = result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _normalized_git_evidence(
    *,
    tool_name: str,
    args: dict[str, Any],
    result: Any,
    succeeded: bool,
) -> str:
    if not succeeded or tool_name != "terminal":
        return ""
    command = str(args.get("command") or "")
    try:
        tokens = _tokenize_single_shell_command(command)
    except (PermissionError, ValueError):
        return ""
    if tokens[:2] == ["git", "rev-parse"]:
        if tokens[2:] not in (["HEAD"], ["--verify", "HEAD"]):
            return ""
    elif tokens[:2] == ["git", "ls-remote"]:
        if len(tokens) < 4:
            return ""
    else:
        return ""
    parsed = _result_mapping(result)
    output = parsed.get("output") if parsed is not None else None
    if not isinstance(output, str) or not output.strip():
        return ""
    candidate = output.splitlines()[0].split()[0].lower()
    return candidate if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", candidate) else ""


def _tool_result_succeeded(status: str, result: Any, *, tool_name: str) -> bool:
    if status != "ok":
        return False
    parsed = _result_mapping(result)
    if parsed is None or parsed.get("error"):
        return False
    if tool_name == "terminal":
        exit_value = parsed.get("exit_code", parsed.get("returncode"))
        return type(exit_value) is int and exit_value == 0
    if parsed.get("success") is False or parsed.get("ok") is False:
        return False
    return parsed.get("success") is True or parsed.get("ok") is True


def _is_within(path: str, root: str) -> bool:
    try:
        Path(path).relative_to(Path(root))
        return True
    except ValueError:
        return False


def default_state_path(hermes_home: str | Path | None = None) -> Path:
    if hermes_home is None:
        import os

        raw_home = os.environ.get("HERMES_HOME", "").strip()
        home = Path(raw_home).expanduser() if raw_home else Path.home() / ".hermes"
    else:
        home = Path(hermes_home).expanduser()
    return home.resolve() / "plugin-data" / "pda-scope-gate" / "scope-gate.db"


def validate_shell_payload(
    payload: dict[str, Any],
    *,
    state_path: str | Path | None = None,
) -> dict[str, str]:
    """Validate Hermes shell-hook JSON and return its stdout directive."""

    if not isinstance(payload, dict):
        raise TypeError("hook payload must be an object")
    if payload.get("hook_event_name") != "pre_tool_call":
        raise ValueError("validator accepts only pre_tool_call payloads")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    extra = payload.get("extra")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("hook payload requires tool_name")
    if not isinstance(tool_input, dict) or not isinstance(extra, dict):
        raise TypeError("hook payload requires object tool_input and extra")

    store = GateStore(state_path or default_state_path())
    resolved_turn = store.resolve_turn_id(
        turn_id=str(extra.get("turn_id") or ""),
        task_id=str(extra.get("task_id") or ""),
        session_id=str(payload.get("session_id") or ""),
    )
    if not resolved_turn:
        return {}
    decision = store.admit_tool(
        turn_id=resolved_turn,
        tool_call_id=str(extra.get("tool_call_id") or ""),
        tool_name=tool_name,
        args=tool_input,
    )
    if decision.allowed:
        return {}
    return {
        "action": "block",
        "message": f"PDA scope gate [{decision.action}]: {decision.reason}",
    }
