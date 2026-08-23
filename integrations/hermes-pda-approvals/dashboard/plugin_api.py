"""PDA owner-approval dashboard API.

This plugin derives its queue from Hermes Kanban review cards in the
``pda-improvement`` tenant.  It does not maintain a second task database.
Owner approval is bound to the configured basic-auth owner identity, the latest
review handoff's canonical SHA-256 digest, and the exact linked task worktree,
branch, and clean Git HEAD.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from hermes_cli import kanban_db


router = APIRouter()

TENANT = "pda-improvement"
OWNER_APPROVAL_AUTHOR = "pda-owner-approval"
OWNER_CHANGES_AUTHOR = "pda-owner-changes"
APPROVAL_SCHEMA = "PDA_OWNER_APPROVAL_V1"

# Bumped to 2 by Judgment A (2026-08-23): the canonical Git directory
# identities left the worker-authored metadata object and are now derived by
# the approval gate. Old workers still emitting version 1 fail validation
# instead of silently having their declarations ignored.
APPROVAL_METADATA_SCHEMA_VERSION = 2

# Keys the gate derives from the workspace. They are stored on the approval
# ledger row and reproduced in the owner marker, but they never appear in the
# worker-authored metadata object, so they are outside the approved digest.
GATE_DERIVED_IDENTITY_KEYS = ("git_common_dir", "git_dir")

_ALLOWED_RISK_CLASSES = {
    "local-reversible",
    "service-restart",
    "external-visible",
    "security-sensitive",
}
_ALLOWED_FINALIZATION_KINDS = {
    "merge-only",
    "merge-and-restart",
    "apply-artifacts",
    "no-runtime-change",
}
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")

# Governance surfaces (ADR D3): a worker finalization may never change the
# rules that judge workers. Changes to these paths are owner-committed only,
# so an approval contract whose diff touches them is refused outright.
GOVERNANCE_PATHS = (
    "pda_charter.md",
    "conftest.py",
    "continuity/autonomous-improvement.json",
    "profiles/pda/managed-habits.json",
    "profiles/pda/skills/pda-autonomous-improvement/",
    "docs/design/self-improvement-governance-adr.md",
    "docs/design/task-scope-admission-gate.md",
    "docs/roadmap/autonomous-improvement-goal.md",
    "docs/roadmap/autonomous-improvement-operating-rules.md",
    "docs/roadmap/current-priority.md",
    "docs/operations/adversarial-suite.md",
    "integrations/hermes-kanban-governance/",
    "integrations/hermes-scope-gate/",
    "integrations/hermes-pda-approvals/",
    "operations/improvement/",
    "infra/systemd/",
)


def _is_governance_path(path: str) -> bool:
    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    # Any conftest.py anywhere is part of the test-isolation guard (C7).
    if Path(normalized).name == "conftest.py":
        return True
    for entry in GOVERNANCE_PATHS:
        if entry.endswith("/"):
            if normalized.startswith(entry):
                return True
        elif normalized == entry:
            return True
    return False


_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _ensure_approval_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pda_owner_approvals (
            approval_id   TEXT PRIMARY KEY,
            task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            digest        TEXT NOT NULL,
            base_sha      TEXT NOT NULL DEFAULT '',
            head_sha      TEXT NOT NULL,
            workspace_path TEXT NOT NULL DEFAULT '',
            branch_name    TEXT NOT NULL DEFAULT '',
            git_common_dir TEXT NOT NULL DEFAULT '',
            git_dir        TEXT NOT NULL DEFAULT '',
            review_run_id INTEGER NOT NULL,
            approved_at   INTEGER NOT NULL,
            approved_by_provider TEXT NOT NULL DEFAULT '',
            approved_by_user_id  TEXT NOT NULL DEFAULT '',
            activation_nonce TEXT,
            activation_started_at INTEGER,
            consumed_at INTEGER,
            revoked_at    INTEGER,
            UNIQUE(task_id, review_run_id, digest)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pda_owner_approvals_task "
        "ON pda_owner_approvals(task_id, approved_at DESC)"
    )
    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(pda_owner_approvals)").fetchall()
    }
    migration_statements = {
        "base_sha": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN base_sha TEXT NOT NULL DEFAULT ''"
        ),
        "workspace_path": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN workspace_path TEXT NOT NULL DEFAULT ''"
        ),
        "branch_name": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN branch_name TEXT NOT NULL DEFAULT ''"
        ),
        "git_common_dir": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN git_common_dir TEXT NOT NULL DEFAULT ''"
        ),
        "git_dir": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN git_dir TEXT NOT NULL DEFAULT ''"
        ),
        "approved_by_provider": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN approved_by_provider TEXT NOT NULL DEFAULT ''"
        ),
        "approved_by_user_id": (
            "ALTER TABLE pda_owner_approvals "
            "ADD COLUMN approved_by_user_id TEXT NOT NULL DEFAULT ''"
        ),
        "activation_nonce": (
            "ALTER TABLE pda_owner_approvals ADD COLUMN activation_nonce TEXT"
        ),
        "activation_started_at": (
            "ALTER TABLE pda_owner_approvals ADD COLUMN activation_started_at INTEGER"
        ),
        "consumed_at": (
            "ALTER TABLE pda_owner_approvals ADD COLUMN consumed_at INTEGER"
        ),
    }
    for column, statement in migration_statements.items():
        if column not in columns:
            conn.execute(statement)
    conn.commit()


class ApproveBody(BaseModel):
    digest: str = Field(min_length=64, max_length=64)


class RequestChangesBody(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


def _configured_basic_owner() -> str:
    env_owner = os.environ.get("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "").strip()
    if env_owner:
        return env_owner
    try:
        from hermes_cli.config import cfg_get, load_config

        section = cfg_get(load_config(), "dashboard", "basic_auth", default=None)
    except Exception:
        return ""
    if not isinstance(section, dict):
        return ""
    return str(section.get("username") or "").strip()


def _require_owner_session(request: Request) -> tuple[str, str]:
    expected_user = _configured_basic_owner()
    if not expected_user:
        raise HTTPException(status_code=503, detail="approval owner identity is not configured")
    session = getattr(request.state, "session", None)
    provider = str(getattr(session, "provider", ""))
    user_id = str(getattr(session, "user_id", ""))
    if provider != "basic" or not secrets.compare_digest(user_id, expected_user):
        raise HTTPException(status_code=403, detail="owner approval is required")
    return provider, user_id


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def approval_digest(approval: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(approval).encode("utf-8")).hexdigest()


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _latest_review_handoff(conn, task_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT id, summary, metadata, ended_at FROM task_runs "
        "WHERE task_id = ? AND outcome = 'review_requested' "
        "ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    metadata = _decode_json(row["metadata"])
    approval = metadata.get("pda_approval") if isinstance(metadata, dict) else None
    return {
        "run_id": int(row["id"]),
        "summary": row["summary"],
        "ended_at": row["ended_at"],
        "approval": approval,
    }


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_nonempty_string(item) for item in value)
    )


def validate_approval(task_id: str, value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["pda_approval metadata is missing"]
    if value.get("schema_version") != APPROVAL_METADATA_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {APPROVAL_METADATA_SCHEMA_VERSION}"
        )
    if value.get("task_id") != task_id:
        errors.append("task_id does not match the review card")
    expected_branch = f"pda-auto/{task_id}"
    if value.get("branch_name") != expected_branch:
        errors.append(f"branch_name must be {expected_branch}")
    declared_workspace = value.get("workspace_path")
    if (
        not _nonempty_string(declared_workspace)
        or not Path(str(declared_workspace)).expanduser().is_absolute()
    ):
        errors.append("workspace_path must be an absolute path")
    # Judgment A (2026-08-23): the canonical Git identities are derived by the
    # approval gate from the workspace itself, never declared by the worker.
    # There is no admitted form inside the first-layer contract for the worker
    # to read them, and a declared value would only be compared against a
    # derivation the gate already performs. Rejecting them when present keeps
    # the audit surface honest: nothing downstream validates these keys any
    # more, so a stale declaration must not travel inside the digest.
    for key in GATE_DERIVED_IDENTITY_KEYS:
        if key in value:
            errors.append(f"{key} must not be declared; the gate derives it")
    for key in ("owner_outcome", "impact"):
        if not _nonempty_string(value.get(key)):
            errors.append(f"{key} is required")
    for key in ("base_sha", "head_sha"):
        sha = value.get(key)
        if not isinstance(sha, str) or _SHA_RE.fullmatch(sha) is None:
            errors.append(f"{key} must be a full hexadecimal Git SHA")
    changed_files = value.get("changed_files")
    if not isinstance(changed_files, list) or not _string_list(changed_files):
        errors.append("changed_files must be a string list")
    elif len(set(changed_files)) != len(changed_files):
        errors.append("changed_files must not contain duplicates")
    else:
        for changed in changed_files:
            path = Path(changed)
            if path.is_absolute() or ".." in path.parts or any(ord(char) < 32 for char in changed):
                errors.append("changed_files contains an unsafe path")
                break
    if isinstance(changed_files, list) and _string_list(changed_files):
        governance_hits = sorted(
            {changed for changed in changed_files if _is_governance_path(changed)}
        )
        if governance_hits:
            errors.append(
                "changed_files touches governance paths (owner-committed "
                "changes only): " + ", ".join(governance_hits[:3])
            )
    if not _string_list(value.get("residual_risks")):
        errors.append("residual_risks must be a string list")
    if value.get("risk_class") not in _ALLOWED_RISK_CLASSES:
        errors.append("risk_class is invalid")

    verification = value.get("verification")
    if not isinstance(verification, list) or not verification:
        errors.append("verification must contain at least one check")
    else:
        for index, check in enumerate(verification):
            if not isinstance(check, dict):
                errors.append(f"verification[{index}] must be an object")
                continue
            if not _nonempty_string(check.get("command")):
                errors.append(f"verification[{index}].command is required")
            if check.get("outcome") != "passed":
                errors.append(f"verification[{index}] must have outcome=passed")


    # ADR D2 (2026-08-22 owner decision): every change carries an independent
    # verification report. NOTE the current guarantee honestly: until the M2
    # verifier stage exists, these are self-declared labels checked for
    # internal consistency (verifier != implementer, verified_head_sha bound
    # to the real Git HEAD) — they do not yet prove a separate principal ran
    # the verification. Task-bound identity cross-checks happen at the
    # pending/approve call sites where the task row is available.
    independent = value.get("independent_verification")
    if not isinstance(independent, dict):
        errors.append("independent_verification is required for every change")
    else:
        for key in ("verifier", "implementer", "summary"):
            if not _nonempty_string(independent.get(key)):
                errors.append(f"independent_verification.{key} is required")
        if (
            _nonempty_string(independent.get("verifier"))
            and _nonempty_string(independent.get("implementer"))
            and str(independent.get("verifier")).strip()
            == str(independent.get("implementer")).strip()
        ):
            errors.append(
                "independent_verification.verifier must differ from the implementer"
            )
        if independent.get("verdict") != "pass":
            errors.append("independent_verification.verdict must be pass")
        if independent.get("verified_head_sha") != value.get("head_sha"):
            errors.append(
                "independent_verification.verified_head_sha must match head_sha"
            )
        if not _string_list(independent.get("checks"), allow_empty=False):
            errors.append(
                "independent_verification.checks must be a non-empty string list"
            )

    finalization = value.get("finalization")
    if not isinstance(finalization, dict):
        errors.append("finalization is required")
    else:
        if finalization.get("kind") not in _ALLOWED_FINALIZATION_KINDS:
            errors.append("finalization.kind is invalid")
        for key in ("targets", "steps", "rollback"):
            if not _string_list(finalization.get(key), allow_empty=False):
                errors.append(f"finalization.{key} must be a non-empty string list")
    return errors


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise ValueError(detail)
    return result.stdout.strip()


@dataclass(frozen=True)
class WorkspaceCheck:
    """Outcome of one workspace verification pass.

    ``identities`` carries the canonical Git directory identities the gate
    derived from the workspace during this very pass (Judgment A). It is
    populated only when the derivation succeeded, so a caller that needs to
    persist or compare the identities must check ``identities`` rather than
    assume the absence of errors implies presence.
    """

    errors: list[str]
    identities: dict[str, str] | None = None


def verify_workspace(task: kanban_db.Task, approval: dict[str, Any]) -> WorkspaceCheck:
    errors: list[str] = []
    identities: dict[str, str] | None = None
    if not task.workspace_path:
        return WorkspaceCheck(["task has no workspace_path"])
    path = Path(task.workspace_path).expanduser()
    if not path.is_absolute() or not path.is_dir():
        return WorkspaceCheck(["task workspace is not an existing absolute directory"])
    try:
        lexical_path = Path(os.path.abspath(path))
        real_path = Path(os.path.realpath(path))
        if lexical_path != real_path:
            errors.append("workspace_path contains a symlink")
        declared_path = Path(str(approval.get("workspace_path") or "")).expanduser()
        if lexical_path != Path(os.path.abspath(declared_path)):
            errors.append("task workspace_path no longer matches the approval request")
        declared_branch = str(approval.get("branch_name") or "")
        if task.branch_name != declared_branch:
            errors.append("task branch_name no longer matches the approval request")
        top = Path(_git(path, "rev-parse", "--show-toplevel")).resolve()
        if top != path.resolve():
            errors.append("workspace_path is not the Git worktree root")
        git_dir = Path(_git(path, "rev-parse", "--git-dir"))
        common_dir = Path(_git(path, "rev-parse", "--git-common-dir"))
        resolved_git_dir = (git_dir if git_dir.is_absolute() else path / git_dir).resolve()
        resolved_common_dir = (
            common_dir if common_dir.is_absolute() else path / common_dir
        ).resolve()
        if resolved_git_dir == resolved_common_dir:
            errors.append("workspace is not a linked worktree")
        else:
            # Judgment A: this derivation is the sole source of the canonical
            # identities. The substantive property (the target is a linked
            # worktree, i.e. not the primary repository) is decided by the
            # comparison above and never consulted a declared value.
            identities = {
                "git_dir": str(resolved_git_dir),
                "git_common_dir": str(resolved_common_dir),
            }
        head = _git(path, "rev-parse", "HEAD")
        actual_branch = _git(path, "branch", "--show-current")
        if actual_branch != declared_branch:
            errors.append("workspace branch no longer matches the approval request")
        if head != approval.get("head_sha"):
            errors.append("workspace HEAD no longer matches the approval request")
        if _git(path, "status", "--porcelain"):
            errors.append("workspace has uncommitted changes")
        base = str(approval.get("base_sha") or "")
        if base and head:
            ancestry = subprocess.run(
                ["git", "-C", str(path), "merge-base", "--is-ancestor", base, head],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            if ancestry.returncode != 0:
                errors.append("base_sha is not an ancestor of head_sha")
            else:
                diff = subprocess.run(
                    ["git", "-C", str(path), "diff", "--no-renames", "--name-only", "-z", base, head],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=15,
                )
                if diff.returncode != 0:
                    errors.append("Git changed-file verification failed")
                else:
                    try:
                        actual_files = [
                            item.decode("utf-8")
                            for item in diff.stdout.split(b"\0")
                            if item
                        ]
                    except UnicodeDecodeError:
                        errors.append("Git diff contains a non-UTF-8 path")
                    else:
                        declared_files = approval.get("changed_files") or []
                        if sorted(actual_files) != sorted(declared_files):
                            errors.append(
                                "changed_files does not exactly match the base-to-head Git diff"
                            )
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        errors.append(f"Git verification failed: {exc}")
        identities = None
    return WorkspaceCheck(errors, identities)


def _task_or_404(conn, task_id: str) -> kanban_db.Task:
    task = kanban_db.get_task(conn, task_id)
    if task is None or task.tenant != TENANT:
        raise HTTPException(status_code=404, detail="approval task not found")
    return task


def _existing_approval(conn, task_id: str, digest: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT approval_id, task_id, digest, base_sha, head_sha, workspace_path, "
        "branch_name, git_common_dir, git_dir, review_run_id, approved_at, "
        "approved_by_provider, approved_by_user_id, activation_nonce, consumed_at "
        "FROM pda_owner_approvals WHERE task_id = ? AND digest = ? "
        "AND revoked_at IS NULL AND consumed_at IS NULL "
        "ORDER BY approved_at DESC LIMIT 1",
        (task_id, digest),
    ).fetchone()
    return dict(row) if row is not None else None


def _ledger_matches_approval(
    row: dict[str, Any],
    approval: dict[str, Any],
    *,
    review_run_id: int,
    owner_provider: str,
    owner_user_id: str,
) -> bool:
    # The canonical Git identities are no longer part of the worker-authored
    # object (Judgment A), so they cannot be cross-checked here. Their drift
    # check lives where their provenance now is: the freshly derived values
    # are compared against the ledger row by the callers of verify_workspace.
    expected = {
        "base_sha": approval.get("base_sha"),
        "head_sha": approval.get("head_sha"),
        "workspace_path": approval.get("workspace_path"),
        "branch_name": approval.get("branch_name"),
        "review_run_id": review_run_id,
        "approved_by_provider": owner_provider,
        "approved_by_user_id": owner_user_id,
    }
    return all(row.get(key) == value for key, value in expected.items())


def _identity_drift_errors(
    row: dict[str, Any], identities: dict[str, str] | None
) -> list[str]:
    """Compare freshly derived Git identities against a stored ledger row.

    Judgment A moved the provenance of these two values from the worker to the
    gate, so the two-point drift check became "derivation at approval time vs
    derivation at this time", mediated by the ledger row. A missing derivation
    is an error rather than a pass: fail closed when the values that bind the
    approval to a specific linked worktree could not be read.
    """
    if not identities:
        return ["workspace Git identities could not be derived"]
    errors: list[str] = []
    for key in GATE_DERIVED_IDENTITY_KEYS:
        if row.get(key) != identities.get(key):
            errors.append(f"workspace {key} no longer matches the approval ledger")
    return errors


def _verification_identity_errors(task, approval: Any) -> list[str]:
    """Cross-check the self-declared verification identities against the task.

    The contract-level check inside validate_approval can only compare the
    two declared strings; here the task row is available, so the declared
    implementer must be the task's assignee profile and the verifier must be
    someone else. Still label-level until the M2 verifier stage.
    """
    if not isinstance(approval, dict):
        return []
    independent = approval.get("independent_verification")
    if not isinstance(independent, dict):
        return []
    errors: list[str] = []
    assignee = str(task.assignee or "default").strip()
    implementer = str(independent.get("implementer") or "").strip()
    verifier = str(independent.get("verifier") or "").strip()
    if implementer and implementer != assignee:
        errors.append(
            "independent_verification.implementer must match the task assignee"
        )
    if verifier and verifier == assignee:
        errors.append(
            "independent_verification.verifier must not be the task assignee"
        )
    return errors


def _pending_item(conn, task: kanban_db.Task) -> dict[str, Any]:
    handoff = _latest_review_handoff(conn, task.id)
    approval = handoff.get("approval") if handoff else None
    errors = validate_approval(task.id, approval)
    errors.extend(_verification_identity_errors(task, approval))
    if task.assignee not in (None, "default"):
        errors.append("task is assigned to a non-finalizer profile")
    if not errors and isinstance(approval, dict):
        errors.extend(verify_workspace(task, approval).errors)
    return {
        "task_id": task.id,
        "title": task.title,
        "body": task.body,
        "priority": task.priority,
        "assignee": task.assignee,
        "workspace_path": task.workspace_path,
        "branch_name": task.branch_name,
        "summary": handoff.get("summary") if handoff else None,
        "review_run_id": handoff.get("run_id") if handoff else None,
        "requested_at": handoff.get("ended_at") if handoff else None,
        "approval": approval,
        "digest": approval_digest(approval) if isinstance(approval, dict) else None,
        "eligible": not errors,
        "errors": errors,
    }


def _atomic_reopen_review_task(conn, task_id: str, status: str) -> bool:
    now = int(time.time())
    kanban_db._reclaim_dangling_run(
        conn,
        task_id,
        statuses=("review",),
        now=now,
        note="invariant recovery on owner approval",
    )
    updated = conn.execute(
        "UPDATE tasks SET status = ?, current_run_id = NULL, claim_lock = NULL, "
        "claim_expires = NULL, worker_pid = NULL "
        "WHERE id = ? AND status = 'review'",
        (status, task_id),
    )
    if updated.rowcount != 1:
        return False
    payload = {"status": status}
    kanban_db._append_event(
        conn,
        task_id,
        "review_reopened",
        payload if status != "ready" else None,
    )
    return True


@router.get("/pending")
def pending_approvals():
    kanban_db.init_db()
    with kanban_db.connect_closing() as conn:
        _ensure_approval_schema(conn)
        tasks = kanban_db.list_tasks(
            conn,
            tenant=TENANT,
            status="review",
            order_by="priority",
        )
        return {"items": [_pending_item(conn, task) for task in tasks]}


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, body: ApproveBody, request: Request):
    owner_provider, owner_user_id = _require_owner_session(request)
    if _DIGEST_RE.fullmatch(body.digest) is None:
        raise HTTPException(status_code=422, detail="digest must be lowercase SHA-256")
    kanban_db.init_db()
    with kanban_db.connect_closing() as conn:
        _ensure_approval_schema(conn)
        task = _task_or_404(conn, task_id)
        existing = _existing_approval(conn, task_id, body.digest)
        if existing is not None and existing.get("activation_nonce"):
            raise HTTPException(status_code=409, detail="approval activation is in progress")
        if existing is not None and task.status != "review":
            if (
                existing.get("approved_by_provider") != owner_provider
                or existing.get("approved_by_user_id") != owner_user_id
            ):
                raise HTTPException(status_code=409, detail="prior approval identity is invalid")
            if (
                task.assignee != "default"
                or "pda-autonomous-improvement" not in (task.skills or [])
            ):
                raise HTTPException(
                    status_code=409,
                    detail="prior approval left an incomplete finalizer state",
                )
            prior_handoff = _latest_review_handoff(conn, task_id)
            prior_approval = prior_handoff.get("approval") if prior_handoff else None
            prior_errors = validate_approval(task_id, prior_approval)
            if (
                prior_handoff is None
                or prior_handoff.get("run_id") != existing.get("review_run_id")
                or not isinstance(prior_approval, dict)
                or not secrets.compare_digest(approval_digest(prior_approval), body.digest)
                or prior_approval.get("head_sha") != existing.get("head_sha")
            ):
                prior_errors.append("prior approval no longer matches the latest review handoff")
            if isinstance(prior_approval, dict) and prior_handoff is not None and not _ledger_matches_approval(
                existing,
                prior_approval,
                review_run_id=int(prior_handoff["run_id"]),
                owner_provider=owner_provider,
                owner_user_id=owner_user_id,
            ):
                prior_errors.append("prior approval ledger identity has drifted")
            if not prior_errors and isinstance(prior_approval, dict):
                prior_check = verify_workspace(task, prior_approval)
                prior_errors.extend(prior_check.errors)
                # Judgment A: the identity drift check that used to compare the
                # derivation against the worker's declaration now compares it
                # against the ledger row written at first approval. Replaying
                # an approval must not succeed against a moved worktree.
                if not prior_errors:
                    prior_errors.extend(
                        _identity_drift_errors(existing, prior_check.identities)
                    )
            if prior_errors:
                raise HTTPException(status_code=409, detail={"errors": prior_errors})
            return {
                "ok": True,
                "idempotent": True,
                "task_id": task_id,
                "status": task.status,
                "approval_id": existing.get("approval_id"),
            }
        if task.status != "review":
            raise HTTPException(status_code=409, detail="task is not awaiting approval")
        if task.assignee not in (None, "default"):
            raise HTTPException(
                status_code=409,
                detail="task is assigned to a non-finalizer profile",
            )
        handoff = _latest_review_handoff(conn, task_id)
        approval = handoff.get("approval") if handoff else None
        errors = validate_approval(task_id, approval)
        errors.extend(_verification_identity_errors(task, approval))
        if errors:
            raise HTTPException(status_code=409, detail={"errors": errors})
        assert isinstance(approval, dict)
        actual_digest = approval_digest(approval)
        if not secrets.compare_digest(actual_digest, body.digest):
            raise HTTPException(status_code=409, detail="approval digest is stale or mismatched")
        workspace_check = verify_workspace(task, approval)
        if workspace_check.errors:
            raise HTTPException(
                status_code=409, detail={"errors": workspace_check.errors}
            )

        assert handoff is not None and handoff.get("run_id") is not None
        review_run_id = int(handoff["run_id"])
        forced_skills = list(task.skills or [])
        if "pda-autonomous-improvement" not in forced_skills:
            forced_skills.append("pda-autonomous-improvement")
        marker: dict[str, Any]
        with kanban_db.write_txn(conn):
            fresh_task = _task_or_404(conn, task_id)
            if fresh_task.status != "review" or fresh_task.assignee not in (None, "default"):
                raise HTTPException(status_code=409, detail="review state changed during approval")
            fresh_handoff = _latest_review_handoff(conn, task_id)
            fresh_approval = fresh_handoff.get("approval") if fresh_handoff else None
            if (
                fresh_handoff is None
                or fresh_handoff.get("run_id") != review_run_id
                or not isinstance(fresh_approval, dict)
                or not secrets.compare_digest(approval_digest(fresh_approval), actual_digest)
            ):
                raise HTTPException(status_code=409, detail="review handoff changed during approval")
            fresh_check = verify_workspace(fresh_task, fresh_approval)
            if fresh_check.errors:
                raise HTTPException(status_code=409, detail={"errors": fresh_check.errors})
            # Judgment A: the identities persisted below come from this
            # in-transaction derivation, not from an earlier pass, so the value
            # written to the ledger is the one verified inside the window that
            # the fresh re-verification exists to close.
            fresh_identities = fresh_check.identities
            if not fresh_identities:
                raise HTTPException(
                    status_code=409,
                    detail="workspace Git identities could not be derived",
                )

            current_existing = _existing_approval(conn, task_id, actual_digest)
            if current_existing is not None and (
                not _ledger_matches_approval(
                    current_existing,
                    approval,
                    review_run_id=review_run_id,
                    owner_provider=owner_provider,
                    owner_user_id=owner_user_id,
                )
                or _identity_drift_errors(current_existing, fresh_identities)
            ):
                raise HTTPException(status_code=409, detail="prior approval identity is invalid")
            approved_at = int(time.time())
            approval_id = (
                str(current_existing["approval_id"])
                if current_existing is not None
                else "pa_"
                + hashlib.sha256(
                    f"{task_id}:{actual_digest}:{time.time_ns()}".encode("utf-8")
                ).hexdigest()[:16]
            )
            updated = conn.execute(
                "UPDATE tasks SET skills = ?, assignee = ? "
                "WHERE id = ? AND status = 'review' "
                "AND (assignee IS NULL OR assignee = ?)",
                (
                    json.dumps(forced_skills, ensure_ascii=False),
                    "default",
                    task_id,
                    "default",
                ),
            )
            if updated.rowcount != 1:
                raise HTTPException(status_code=409, detail="finalizer assignment raced")
            if fresh_task.assignee is None:
                kanban_db._append_event(conn, task_id, "assigned", {"assignee": "default"})
            if current_existing is None:
                conn.execute(
                    "INSERT INTO pda_owner_approvals "
                    "(approval_id, task_id, digest, base_sha, head_sha, workspace_path, "
                    "branch_name, git_common_dir, git_dir, review_run_id, approved_at, "
                    "approved_by_provider, approved_by_user_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        approval_id,
                        task_id,
                        actual_digest,
                        approval["base_sha"],
                        approval["head_sha"],
                        approval["workspace_path"],
                        approval["branch_name"],
                        fresh_identities["git_common_dir"],
                        fresh_identities["git_dir"],
                        review_run_id,
                        approved_at,
                        owner_provider,
                        owner_user_id,
                    ),
                )
            marker = {
                "schema": APPROVAL_SCHEMA,
                "approval_id": approval_id,
                "task_id": task_id,
                "digest": actual_digest,
                "base_sha": approval["base_sha"],
                "head_sha": approval["head_sha"],
                "workspace_path": approval["workspace_path"],
                "branch_name": approval["branch_name"],
                # Gate-derived (Judgment A). On the idempotent replay path the
                # ledger row is authoritative, and the drift check above has
                # already proven the row agrees with this derivation.
                "git_common_dir": (
                    str(current_existing["git_common_dir"])
                    if current_existing is not None
                    else fresh_identities["git_common_dir"]
                ),
                "git_dir": (
                    str(current_existing["git_dir"])
                    if current_existing is not None
                    else fresh_identities["git_dir"]
                ),
                "review_run_id": review_run_id,
                "approved_at": (
                    int(current_existing["approved_at"])
                    if current_existing is not None
                    else approved_at
                ),
            }
            kanban_db.add_comment(
                conn,
                task_id,
                OWNER_APPROVAL_AUTHOR,
                "最終反映を承認しました。次のworker runはこの承認内容だけを実行してください。\n"
                + _canonical_json(marker),
            )
            new_status = kanban_db._landing_status_after_parents(conn, task_id)
            if not _atomic_reopen_review_task(conn, task_id, new_status):
                raise HTTPException(status_code=409, detail="review state changed during approval")
            reopened = kanban_db.get_task(conn, task_id)
            if (
                reopened is None
                or reopened.assignee != "default"
                or "pda-autonomous-improvement" not in (reopened.skills or [])
                or reopened.status != new_status
            ):
                raise HTTPException(status_code=409, detail="finalizer state verification failed")
        kanban_db.notify_task_updated(
            conn,
            task_id,
            ("status", "assignee", "skills", "current_run_id"),
        )
        return {
            "ok": True,
            "idempotent": False,
            "task_id": task_id,
            "status": reopened.status if reopened else "ready",
            "approval_id": approval_id,
        }


@router.post("/tasks/{task_id}/request-changes")
def request_changes(task_id: str, body: RequestChangesBody, request: Request):
    _require_owner_session(request)
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason is required")
    kanban_db.init_db()
    with kanban_db.connect_closing() as conn:
        _ensure_approval_schema(conn)
        task = _task_or_404(conn, task_id)
        if task.status != "review":
            raise HTTPException(status_code=409, detail="task is not awaiting approval")
        with kanban_db.write_txn(conn):
            fresh_task = _task_or_404(conn, task_id)
            if fresh_task.status != "review":
                raise HTTPException(status_code=409, detail="review state changed during request")
            handoff = _latest_review_handoff(conn, task_id)
            if handoff is not None and handoff.get("run_id") is not None:
                review_run_id = int(handoff["run_id"])
                active = conn.execute(
                    "SELECT 1 FROM pda_owner_approvals WHERE task_id = ? "
                    "AND review_run_id = ? AND revoked_at IS NULL AND consumed_at IS NULL "
                    "AND activation_nonce IS NOT NULL LIMIT 1",
                    (task_id, review_run_id),
                ).fetchone()
                if active is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="approval activation is in progress",
                    )
                conn.execute(
                    "UPDATE pda_owner_approvals SET revoked_at = ? "
                    "WHERE task_id = ? AND review_run_id = ? AND revoked_at IS NULL "
                    "AND activation_nonce IS NULL AND consumed_at IS NULL",
                    (int(time.time()), task_id, review_run_id),
                )
            kanban_db.add_comment(
                conn,
                task_id,
                OWNER_CHANGES_AUTHOR,
                "差戻し: " + reason,
            )
            new_status = kanban_db._landing_status_after_parents(conn, task_id)
            if not _atomic_reopen_review_task(conn, task_id, new_status):
                raise HTTPException(status_code=409, detail="review state changed during request")
            reopened = kanban_db.get_task(conn, task_id)
            if reopened is None or reopened.status != new_status:
                raise HTTPException(status_code=409, detail="request-changes state verification failed")
        kanban_db.notify_task_updated(
            conn,
            task_id,
            ("status", "current_run_id"),
        )
        return {
            "ok": True,
            "task_id": task_id,
            "status": reopened.status,
        }
