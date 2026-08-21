"""PDA owner-approval dashboard API.

This plugin derives its queue from Hermes Kanban review cards in the
``pda-improvement`` tenant.  It does not maintain a second task database.
Owner approval is bound to the latest review handoff by a canonical SHA-256
digest and to the exact clean Git HEAD in the task workspace.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hermes_cli import kanban_db


router = APIRouter()

TENANT = "pda-improvement"
OWNER_APPROVAL_AUTHOR = "pda-owner-approval"
OWNER_CHANGES_AUTHOR = "pda-owner-changes"
APPROVAL_SCHEMA = "PDA_OWNER_APPROVAL_V1"
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
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _ensure_approval_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pda_owner_approvals (
            approval_id   TEXT PRIMARY KEY,
            task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            digest        TEXT NOT NULL,
            head_sha      TEXT NOT NULL,
            review_run_id INTEGER NOT NULL,
            approved_at   INTEGER NOT NULL,
            revoked_at    INTEGER,
            UNIQUE(task_id, review_run_id, digest)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pda_owner_approvals_task "
        "ON pda_owner_approvals(task_id, approved_at DESC)"
    )
    conn.commit()


class ApproveBody(BaseModel):
    digest: str = Field(min_length=64, max_length=64)


class RequestChangesBody(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


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
    if value.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if value.get("task_id") != task_id:
        errors.append("task_id does not match the review card")
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


def verify_workspace(task: kanban_db.Task, approval: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not task.workspace_path:
        return ["task has no workspace_path"]
    path = Path(task.workspace_path).expanduser()
    if not path.is_absolute() or not path.is_dir():
        return ["task workspace is not an existing absolute directory"]
    try:
        top = Path(_git(path, "rev-parse", "--show-toplevel")).resolve()
        if top != path.resolve():
            errors.append("workspace_path is not the Git worktree root")
        head = _git(path, "rev-parse", "HEAD")
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
                    ["git", "-C", str(path), "diff", "--name-only", "-z", base, head],
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
    return errors


def _task_or_404(conn, task_id: str) -> kanban_db.Task:
    task = kanban_db.get_task(conn, task_id)
    if task is None or task.tenant != TENANT:
        raise HTTPException(status_code=404, detail="approval task not found")
    return task


def _existing_approval(conn, task_id: str, digest: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT approval_id, task_id, digest, head_sha, review_run_id, approved_at "
        "FROM pda_owner_approvals WHERE task_id = ? AND digest = ? "
        "AND revoked_at IS NULL ORDER BY approved_at DESC LIMIT 1",
        (task_id, digest),
    ).fetchone()
    return dict(row) if row is not None else None


def _pending_item(conn, task: kanban_db.Task) -> dict[str, Any]:
    handoff = _latest_review_handoff(conn, task.id)
    approval = handoff.get("approval") if handoff else None
    errors = validate_approval(task.id, approval)
    if task.assignee not in (None, "default"):
        errors.append("task is assigned to a non-finalizer profile")
    if not errors and isinstance(approval, dict):
        errors.extend(verify_workspace(task, approval))
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
def approve_task(task_id: str, body: ApproveBody):
    if _DIGEST_RE.fullmatch(body.digest) is None:
        raise HTTPException(status_code=422, detail="digest must be lowercase SHA-256")
    kanban_db.init_db()
    with kanban_db.connect_closing() as conn:
        _ensure_approval_schema(conn)
        task = _task_or_404(conn, task_id)
        existing = _existing_approval(conn, task_id, body.digest)
        if existing is not None and task.status != "review":
            if (
                task.assignee != "default"
                or "pda-autonomous-improvement" not in (task.skills or [])
            ):
                raise HTTPException(
                    status_code=409,
                    detail="prior approval left an incomplete finalizer state",
                )
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
        if errors:
            raise HTTPException(status_code=409, detail={"errors": errors})
        assert isinstance(approval, dict)
        actual_digest = approval_digest(approval)
        if not secrets.compare_digest(actual_digest, body.digest):
            raise HTTPException(status_code=409, detail="approval digest is stale or mismatched")
        workspace_errors = verify_workspace(task, approval)
        if workspace_errors:
            raise HTTPException(status_code=409, detail={"errors": workspace_errors})

        # Prepare the only authorized post-approval execution context while the
        # task is still non-dispatchable in review. Reopen is deliberately last.
        forced_skills = list(task.skills or [])
        if "pda-autonomous-improvement" not in forced_skills:
            forced_skills.append("pda-autonomous-improvement")
            with kanban_db.write_txn(conn):
                updated = conn.execute(
                    "UPDATE tasks SET skills = ? WHERE id = ? AND status = 'review'",
                    (json.dumps(forced_skills, ensure_ascii=False), task_id),
                )
                if updated.rowcount != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="finalizer policy assignment raced with another update",
                    )
        if task.assignee is None:
            if not kanban_db.assign_task(conn, task_id, "default"):
                raise HTTPException(status_code=409, detail="finalizer assignment failed")

        assert handoff is not None and handoff.get("run_id") is not None
        review_run_id = int(handoff["run_id"])
        current_existing = (
            existing
            if existing is not None
            and existing.get("review_run_id") == review_run_id
            and existing.get("head_sha") == approval["head_sha"]
            else None
        )
        approved_at = int(time.time())
        approval_id = (
            str(current_existing["approval_id"])
            if current_existing is not None
            else "pa_"
            + hashlib.sha256(
                f"{task_id}:{actual_digest}:{time.time_ns()}".encode("utf-8")
            ).hexdigest()[:16]
        )
        if current_existing is None:
            with kanban_db.write_txn(conn):
                conn.execute(
                    "INSERT INTO pda_owner_approvals "
                    "(approval_id, task_id, digest, head_sha, review_run_id, approved_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        approval_id,
                        task_id,
                        actual_digest,
                        approval["head_sha"],
                        review_run_id,
                        approved_at,
                    ),
                )
        marker = {
            "schema": APPROVAL_SCHEMA,
            "approval_id": approval_id,
            "task_id": task_id,
            "digest": actual_digest,
            "head_sha": approval["head_sha"],
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
        if not kanban_db.reopen_review_task(conn, task_id):
            raise HTTPException(status_code=409, detail="review state changed during approval")
        reopened = kanban_db.get_task(conn, task_id)
        if (
            reopened is None
            or reopened.assignee != "default"
            or "pda-autonomous-improvement" not in (reopened.skills or [])
        ):
            raise HTTPException(status_code=409, detail="finalizer state verification failed")
        return {
            "ok": True,
            "idempotent": False,
            "task_id": task_id,
            "status": reopened.status if reopened else "ready",
            "approval_id": approval_id,
        }


@router.post("/tasks/{task_id}/request-changes")
def request_changes(task_id: str, body: RequestChangesBody):
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason is required")
    kanban_db.init_db()
    with kanban_db.connect_closing() as conn:
        _ensure_approval_schema(conn)
        task = _task_or_404(conn, task_id)
        if task.status != "review":
            raise HTTPException(status_code=409, detail="task is not awaiting approval")
        handoff = _latest_review_handoff(conn, task_id)
        if handoff is not None and handoff.get("run_id") is not None:
            with kanban_db.write_txn(conn):
                conn.execute(
                    "UPDATE pda_owner_approvals SET revoked_at = ? "
                    "WHERE task_id = ? AND review_run_id = ? AND revoked_at IS NULL",
                    (int(time.time()), task_id, int(handoff["run_id"])),
                )
        kanban_db.add_comment(
            conn,
            task_id,
            OWNER_CHANGES_AUTHOR,
            "差戻し: " + reason,
        )
        if not kanban_db.reopen_review_task(conn, task_id):
            raise HTTPException(status_code=409, detail="review state changed during request")
        reopened = kanban_db.get_task(conn, task_id)
        return {
            "ok": True,
            "task_id": task_id,
            "status": reopened.status if reopened else "ready",
        }
