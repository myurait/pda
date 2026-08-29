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
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
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


_BASE_COMMIT_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _assignment_base_commit(repo: Path, branch: str, base_branch: str) -> str:
    """The commit the assigned branch starts from, resolved by the router.

    The merge base rather than the tip of ``base_branch``: for a branch just
    created from it the two are the same commit, and for a branch that already
    existed the merge base is where the work actually diverged. It is also the
    stable choice -- ``base_branch`` moving on does not change it -- so a
    later tick that re-derives the seed states the same base instead of
    colliding with the recorded one.

    This is the value the audit range is taken over, and it is resolved here
    precisely so it is never the executing agent's own claim about its base.
    """

    result = _git(repo, "merge-base", base_branch, branch, check=False)
    base = result.stdout.strip()
    if result.returncode != 0 or not _BASE_COMMIT_RE.match(base):
        raise CycleError(
            "git-error",
            "could not resolve the assignment base commit for "
            f"{branch}: {result.stderr.strip() or base or 'no common ancestor'}",
        )
    return base


def _ensure_worktree(
    repo: Path, root: Path, task_id: str, base_branch: str
) -> tuple[Path, str, str]:
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
    return path, branch, _assignment_base_commit(repo, branch, base_branch)


SCOPE_SEED_AUTHOR = "pda-improvement-cycle"

# How many refused cards one tick will walk past looking for a routable one.
# Skipping refusals is what keeps a single unqualified card from blocking the
# queue, but the work per refusal is a card comment, so the scan is bounded
# rather than proportional to the board. The bound is far above the size this
# lane runs at; it exists so a pathological board cannot make one tick
# unbounded.
MAX_REFUSALS_PER_TICK = 50


def _load_scope_seed(repo: Path):
    """Load the scope seed helper, anchored at the repository root.

    The installer deploys this router as a standalone script into
    ``~/.local/libexec/pda``, so a package-relative import would resolve during
    tests and fail at runtime.  The repository is the anchor the router already
    trusts for the committed activation policy, so the helper is loaded from
    there by path.  When the repository copy is absent — running from a source
    checkout as a package — the package import is used instead.
    """

    module_path = repo / "operations" / "improvement" / "scope_seed.py"
    if module_path.is_file():
        # Keyed by resolved path: two repository roots in one process must not
        # share the first one's module object.
        name = "pda_scope_seed_" + hashlib.sha256(
            str(module_path.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        cached = sys.modules.get(name)
        if cached is not None:
            return cached
        spec = importlib.util.spec_from_file_location(name, module_path)
        if spec is None or spec.loader is None:
            raise CycleError(
                "invalid-config", f"scope seed helper is not importable: {module_path}"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(name, None)
            raise CycleError("invalid-config", f"scope seed helper failed to load: {exc}") from exc
        return module
    try:
        from operations.improvement import scope_seed as module  # noqa: PLC0415
    except ImportError as exc:
        raise CycleError(
            "invalid-config", f"scope seed helper not found: {module_path}"
        ) from exc
    return module


def _comment_once(conn, task_id: str, author: str, body: str) -> None:
    """Leave a card comment unless an identical one is already present.

    The router runs on a timer, so a card that stays unroutable would collect
    one copy of the same diagnostic per tick without this guard.
    """

    with kanban_db.write_txn(conn):
        existing = conn.execute(
            "SELECT 1 FROM task_comments WHERE task_id = ? AND author = ? "
            "AND body = ? LIMIT 1",
            (task_id, author, body),
        ).fetchone()
        if existing is None:
            kanban_db.add_comment(conn, task_id, author, body)


def _record_scope_seed(
    conn,
    task,
    path: Path,
    branch: str,
    repo: Path,
    base_commit: str,
    state_path: Path | None,
    max_top_level_entries: int | None = None,
) -> None:
    """Record the assignment-time scope seed before the task is claimed.

    Ordering rationale: the seed store and the Kanban board are separate
    databases and cannot share a transaction, so the failure mode is handled by
    ordering instead.  The seed is written first, so a worker can never be
    started by the assignment notification without its ceiling already in
    place.  The converse ordering would allow a seedless worker on the
    autonomous lane, which is the configuration this wiring exists to prevent.

    A seed left behind by a later claim race is harmless: it is a ceiling keyed
    by task id, an unassigned task having a ceiling constrains nothing, and the
    next tick re-derives the identical payload and passes the gate's idempotent
    path.
    """

    scope_seed = _load_scope_seed(repo)
    try:
        scope_seed.record_seed(
            repo_root=repo,
            task_id=task.id,
            body=task.body,
            worktree=path,
            branch=branch,
            base_commit=base_commit,
            state_path=state_path,
            max_top_level_entries=max_top_level_entries,
        )
    except scope_seed.ScopeSeedError as exc:
        _refuse_for_scope(conn, task.id, scope_seed, exc)


def _refuse_for_scope(conn, task_id: str, scope_seed, exc) -> None:
    """Comment the reason once, then raise the routing refusal."""

    if exc.kind == "scope-seed-base-mismatch":
        # The declaration is not what was refused, so the comment must not
        # send the owner to edit it. The recorded seed belongs to a workspace
        # that started at another commit -- or to a row written before the
        # base was recorded -- and only retiring that row clears it.
        body = (
            "自動改善サイクルはこのカードを割り当てませんでした。"
            "書込スコープ宣言には問題ありません。"
            "このtaskには既存の契約seedが残っており、割当時のbase commitが"
            f"記録値と一致しません: {exc}"
            "カード本文を直しても解消しません。"
            "既存seedの失効（retention経過またはオーナーによる削除）が必要です。"
        )
    elif exc.kind == "missing-scope-declaration":
        body = (
            "自動改善サイクルはこのカードを割り当てませんでした。"
            "機械可読な書込スコープ宣言が本文にありません。"
            f"```{scope_seed.SCOPE_BLOCK_INFO}``` ブロックへ write_paths を宣言してください"
            "（必要なら test_paths / execution / git_write も宣言できます。"
            "git_write はクラス既定からの縮小のみ可能です）。"
        )
    else:
        body = (
            "自動改善サイクルはこのカードを割り当てませんでした。"
            f"書込スコープ宣言をゲートが受理しませんでした: {exc}"
            "宣言を修正するか、スコープを変更する場合は新しいカードへ分けてください。"
        )
    _comment_once(conn, task_id, SCOPE_SEED_AUTHOR, body)
    raise CycleError(exc.kind, str(exc)) from exc


def _check_scope_declaration(
    conn, task, repo: Path, max_top_level_entries: int | None = None
) -> None:
    """Refuse an undeclarable or over-broad card before a workspace exists.

    Running here keeps a card that will not be assigned from leaving a branch
    and a worktree behind, and it bounds the cost of walking past refusals to
    look for a routable card. The breadth is measured against the primary
    repository, because the worktree this card would get is a checkout of it
    and does not exist yet; ``record_seed`` re-measures against the worktree
    itself once it does, and that later measurement is the one the recorded
    ceiling is taken with. Both are refusal-side, so the earlier one being an
    approximation cannot widen anything.
    """

    scope_seed = _load_scope_seed(repo)
    try:
        scope_seed.derive_seed_payload(
            task_id=task.id,
            body=task.body,
            tree_root=repo,
            gate_root=repo,
            max_top_level_entries=max_top_level_entries,
        )
    except scope_seed.ScopeSeedError as exc:
        _refuse_for_scope(conn, task.id, scope_seed, exc)


def _route_task(
    conn,
    task,
    path: Path,
    branch: str,
    assignee: str,
    *,
    scope_seed_enabled: bool,
    repo: Path | None = None,
    base_commit: str | None = None,
    scope_seed_state_path: Path | None = None,
    scope_max_top_level_entries: int | None = None,
) -> None:
    # ``scope_seed_enabled`` has no default on purpose. Whether this
    # assignment records the ceiling that puts the turn under hard enforcement
    # is not a detail a caller may leave out: an omitted keyword would route
    # the task unenforced and report success. Without a default the omission
    # is a loud failure at the call instead of a silent unenforced assignment.
    current = kanban_db.get_task(conn, task.id)
    if current is None or current.status != "ready" or current.assignee is not None:
        raise CycleError("claim-race", "task changed before routing")
    if scope_seed_enabled:
        if repo is None:
            raise CycleError(
                "invalid-config", "scope seed recording requires the repository root"
            )
        if not base_commit:
            # The base is resolved when the workspace is created, and the seed
            # is the only place it is recorded. Routing without it would store
            # a ceiling that says nothing about the commit its work started
            # from, so the omission fails the assignment instead.
            raise CycleError(
                "invalid-config",
                "scope seed recording requires the assignment-time base commit",
            )
        # Seed -> assignment CAS -> notification. The notification is what wakes
        # the gateway's Kanban dispatcher, so it stays last.
        _record_scope_seed(
            conn,
            current,
            path,
            branch,
            repo,
            base_commit,
            scope_seed_state_path,
            scope_max_top_level_entries,
        )
    forced_skills = list(current.skills or [])
    if "pda-autonomous-improvement" not in forced_skills:
        forced_skills.append("pda-autonomous-improvement")
    comment = (
        "自動改善サイクルがこのカードを隔離worktreeへ割り当てました。"
        "承認前はこのbranch内の実装・検証・ローカルcommitだけを行い、"
        "検証済み成果を最終承認リストへ送ってください。"
        "main統合、push、デプロイ、サービス変更、外部送信は最終承認後だけ実行できます。"
    )
    with kanban_db.write_txn(conn):
        # The comment helper composes through a savepoint. Nothing becomes
        # visible unless the assignment CAS below succeeds and the outer
        # transaction commits.
        kanban_db.add_comment(
            conn,
            task.id,
            "pda-improvement-cycle",
            comment,
        )
        updated = conn.execute(
            "UPDATE tasks SET workspace_path = ?, branch_name = ?, skills = ?, "
            "assignee = ?, consecutive_failures = 0, last_failure_error = NULL "
            "WHERE id = ? AND status = 'ready' AND assignee IS NULL",
            (
                str(path),
                branch,
                json.dumps(forced_skills, ensure_ascii=False),
                assignee,
                task.id,
            ),
        )
        if updated.rowcount != 1:
            raise CycleError("claim-race", "task changed during atomic routing")
        kanban_db._append_event(conn, task.id, "assigned", {"assignee": assignee})
    kanban_db.notify_task_updated(
        conn,
        task.id,
        ("workspace_path", "branch_name", "skills", "assignee"),
    )


def run_cycle(config_path: str | Path) -> dict[str, Any]:
    config_path = Path(config_path)
    try:
        config = _load_config(config_path)
        if not bool(config.get("enabled", False)):
            return {"ok": True, "enabled": False, "assigned": [], "reason": "disabled"}

        # The committed repository policy is the single source of truth for
        # whether the cycle may run (see continuity/autonomous-improvement.json
        # and the installer's activation gate). The rendered runtime config is
        # derived state: if it disagrees with the policy — e.g. it was edited
        # directly instead of going through owner-approved activation — the
        # router fails closed instead of trusting the tampered copy.
        policy_path = (
            _absolute_dir(config.get("repo_root"), "repo_root")
            / "continuity"
            / "autonomous-improvement.json"
        )
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CycleError(
                "policy-unreadable",
                f"committed policy could not be read: {policy_path}: {exc}",
            ) from exc
        if not bool(policy.get("enabled", False)):
            return {
                "ok": True,
                "enabled": False,
                "assigned": [],
                "reason": "disabled-by-committed-policy",
            }

        # The seed switch is read from the committed policy, not the rendered
        # runtime config, for the same reason the activation gate above is:
        # recording a seed is what puts the autonomous lane under hard
        # enforcement (D-S3-8), so the decision must live in an owner-committed
        # file rather than in derived state that can be edited in place.
        # Default false: this wiring ships inert, and turning it on is the next
        # gate's approval.
        scope_seed_policy = policy.get("scope_seed")
        scope_seed_enabled = bool(
            isinstance(scope_seed_policy, dict)
            and scope_seed_policy.get("enabled", False)
        )
        # How many top-level entries of the tree one card's declared scope may
        # reach. Owner-committed for the same reason as the switch: it is the
        # mechanical limit on the declared ceiling, so a lane cannot widen it
        # from derived state. Absent means the module default.
        scope_max_top_level_entries = None
        if isinstance(scope_seed_policy, dict):
            raw_limit = scope_seed_policy.get("max_top_level_entries")
            if raw_limit is not None:
                try:
                    scope_max_top_level_entries = int(raw_limit)
                except (TypeError, ValueError) as exc:
                    raise CycleError(
                        "invalid-config",
                        "scope_seed.max_top_level_entries must be an integer",
                    ) from exc
                if scope_max_top_level_entries < 1:
                    raise CycleError(
                        "invalid-config",
                        "scope_seed.max_top_level_entries must be positive",
                    )

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
                # Per-card recovery. A card that fails its own admission is a
                # fact about that card, not about the cycle: letting it end the
                # tick would let the highest-priority unqualified card block
                # every other eligible card indefinitely, since the queue is
                # priority-ordered and the same card leads it next tick. The
                # refusal stays visible in two places -- the one-time card
                # comment the router writes, and ``refused`` below -- so
                # continuing past it is not the same as ignoring it.
                refused: list[dict[str, str]] = []
                for task in _eligible_tasks(conn, tenant):
                    if len(assigned) >= capacity:
                        break
                    if len(refused) >= MAX_REFUSALS_PER_TICK:
                        break
                    try:
                        if scope_seed_enabled:
                            _check_scope_declaration(
                                conn, task, repo, scope_max_top_level_entries
                            )
                        path, branch, base_commit = _ensure_worktree(
                            repo, root, task.id, base_branch
                        )
                        _route_task(
                            conn,
                            task,
                            path,
                            branch,
                            assignee,
                            repo=repo,
                            base_commit=base_commit,
                            scope_seed_enabled=scope_seed_enabled,
                            scope_max_top_level_entries=scope_max_top_level_entries,
                        )
                    except CycleError as exc:
                        refused.append({"task_id": task.id, "error_kind": exc.kind})
                        continue
                    assigned.append(task.id)
                if assigned:
                    reason = "assigned"
                elif refused:
                    reason = "no-routable-task"
                else:
                    reason = "no-eligible-task"
                return {
                    "ok": True,
                    "enabled": True,
                    "assigned": assigned,
                    "refused": refused,
                    "reason": reason,
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
