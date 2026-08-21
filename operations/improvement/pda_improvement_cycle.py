"""Deterministic router for the PDA autonomous improvement lane.

The controller spends no model turns while the queue is empty.  It only selects
eligible Ready cards, creates or adopts a task-specific Git worktree, records
the routing decision, and assigns the configured task-scoped worker lane with a
forced policy skill. The gateway's built-in Kanban dispatcher owns worker launch
and lifecycle after assignment.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from hermes_cli import kanban_db


ACTIVE_STATUSES = ("ready", "running", "review")
STOP_TITLE_PREFIXES = ("【停止中】", "[停止中]", "停止中:", "停止中：")


class CycleError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def _load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise CycleError("invalid-config", "cycle config schema_version must be 1")
    return value


def _absolute_dir(value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CycleError("invalid-config", f"{name} is required")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise CycleError("invalid-config", f"{name} must be absolute")
    return path


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise CycleError("git-error", detail)
    return result


def _validate_repo(repo: Path, base_branch: str) -> None:
    if not repo.is_dir():
        raise CycleError("invalid-config", f"repo_root does not exist: {repo}")
    top = _git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    if Path(top).resolve() != repo.resolve():
        raise CycleError("invalid-config", "repo_root must be the Git toplevel")
    if _git(repo, "rev-parse", "--verify", base_branch, check=False).returncode != 0:
        raise CycleError("invalid-config", f"base_branch does not exist: {base_branch}")


def _profile_exists(config: dict[str, Any]) -> bool:
    if not config.get("require_profile_on_disk", True):
        return True
    assignee = str(config["assignee"])
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    if assignee == "default":
        return home.is_dir()
    return (home / "profiles" / assignee).is_dir()


def _wip_count(conn, tenant: str, assignee: str) -> int:
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    row = conn.execute(
        f"SELECT COUNT(*) FROM tasks WHERE tenant = ? AND assignee = ? "
        f"AND status IN ({placeholders})",
        (tenant, assignee, *ACTIVE_STATUSES),
    ).fetchone()
    return int(row[0])


def _eligible_tasks(conn, tenant: str):
    tasks = kanban_db.list_tasks(
        conn,
        tenant=tenant,
        status="ready",
        order_by="priority",
    )
    return [
        task
        for task in tasks
        if task.assignee is None
        and not any(task.title.startswith(prefix) for prefix in STOP_TITLE_PREFIXES)
    ]


def _branch_for(task_id: str) -> str:
    return f"pda-auto/{task_id}"


def _worktree_is_exact(path: Path, branch: str) -> bool:
    try:
        top = _git(path, "rev-parse", "--show-toplevel").stdout.strip()
        actual_branch = _git(path, "branch", "--show-current").stdout.strip()
    except (CycleError, OSError, subprocess.TimeoutExpired):
        return False
    return Path(top).resolve() == path.resolve() and actual_branch == branch


def _ensure_worktree(repo: Path, root: Path, task_id: str, base_branch: str) -> tuple[Path, str]:
    path = root / task_id
    branch = _branch_for(task_id)
    root.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not _worktree_is_exact(path, branch):
            raise CycleError(
                "workspace-collision",
                f"{path} exists but is not the exact {branch} worktree",
            )
    else:
        branch_exists = _git(
            repo,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
            check=False,
        ).returncode == 0
        args = ("worktree", "add", str(path), branch) if branch_exists else (
            "worktree",
            "add",
            "-b",
            branch,
            str(path),
            base_branch,
        )
        result = _git(repo, *args, check=False)
        if result.returncode != 0:
            raise CycleError(
                "workspace-collision" if branch_exists else "git-error",
                result.stderr.strip() or result.stdout.strip(),
            )
    if _git(path, "status", "--porcelain").stdout.strip():
        raise CycleError("dirty-worktree", f"new task worktree is dirty: {path}")
    return path, branch


def _route_task(conn, task, path: Path, branch: str, assignee: str) -> None:
    current = kanban_db.get_task(conn, task.id)
    if current is None or current.status != "ready" or current.assignee is not None:
        raise CycleError("claim-race", "task changed before routing")
    kanban_db.set_workspace_path(conn, task.id, path)
    kanban_db.set_branch_name(conn, task.id, branch)
    forced_skills = list(current.skills or [])
    if "pda-autonomous-improvement" not in forced_skills:
        forced_skills.append("pda-autonomous-improvement")
        with kanban_db.write_txn(conn):
            updated = conn.execute(
                "UPDATE tasks SET skills = ? WHERE id = ? AND status = 'ready' AND assignee IS NULL",
                (json.dumps(forced_skills, ensure_ascii=False), task.id),
            )
            if updated.rowcount != 1:
                raise CycleError("claim-race", "task changed while forcing worker policy")
    kanban_db.add_comment(
        conn,
        task.id,
        "pda-improvement-cycle",
        "自動改善サイクルがこのカードを隔離worktreeへ割り当てました。"
        "承認前はこのbranch内の実装・検証・ローカルcommitだけを行い、"
        "検証済み成果を最終承認リストへ送ってください。"
        "main統合、push、デプロイ、サービス変更、外部送信は最終承認後だけ実行できます。",
    )
    # Assignment is deliberately last: an unassigned Ready card cannot be
    # claimed by the gateway while the workspace metadata is half-written.
    if not kanban_db.assign_task(conn, task.id, assignee):
        raise CycleError("claim-race", "task assignment failed")


def run_cycle(config_path: str | Path) -> dict[str, Any]:
    config_path = Path(config_path)
    try:
        config = _load_config(config_path)
        if not bool(config.get("enabled", False)):
            return {"ok": True, "enabled": False, "assigned": [], "reason": "disabled"}

        tenant = str(config.get("tenant") or "").strip()
        assignee = str(config.get("assignee") or "").strip()
        if not tenant or not assignee:
            raise CycleError("invalid-config", "tenant and assignee are required")
        if not _profile_exists(config):
            raise CycleError("missing-profile", f"Hermes profile is missing: {assignee}")
        repo = _absolute_dir(config.get("repo_root"), "repo_root")
        root = _absolute_dir(config.get("worktrees_root"), "worktrees_root")
        base_branch = str(config.get("base_branch") or "main").strip()
        max_wip = int(config.get("max_wip", 1))
        per_tick = int(config.get("max_assignments_per_tick", 1))
        if max_wip < 1 or per_tick < 1:
            raise CycleError("invalid-config", "WIP values must be positive")
        _validate_repo(repo, base_branch)

        root.mkdir(parents=True, exist_ok=True)
        lock_path = root / ".cycle.lock"
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            kanban_db.init_db()
            assigned: list[str] = []
            with kanban_db.connect_closing() as conn:
                wip = _wip_count(conn, tenant, assignee)
                if wip >= max_wip:
                    return {
                        "ok": True,
                        "enabled": True,
                        "assigned": [],
                        "reason": "wip-limit",
                        "wip": wip,
                    }
                capacity = min(max_wip - wip, per_tick)
                for task in _eligible_tasks(conn, tenant)[:capacity]:
                    path, branch = _ensure_worktree(repo, root, task.id, base_branch)
                    _route_task(conn, task, path, branch, assignee)
                    assigned.append(task.id)
                return {
                    "ok": True,
                    "enabled": True,
                    "assigned": assigned,
                    "reason": "assigned" if assigned else "no-eligible-task",
                    "wip": wip + len(assigned),
                }
    except CycleError as exc:
        return {
            "ok": False,
            "enabled": bool(locals().get("config", {}).get("enabled", False)),
            "assigned": [],
            "error_kind": exc.kind,
            "error": str(exc),
        }
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "enabled": bool(locals().get("config", {}).get("enabled", False)),
            "assigned": [],
            "error_kind": "runtime-error",
            "error": str(exc),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route PDA improvement cards")
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    result = run_cycle(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
