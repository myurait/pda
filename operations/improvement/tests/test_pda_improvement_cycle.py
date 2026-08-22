from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hermes_cli import kanban_db

import operations.improvement.pda_improvement_cycle as cycle_module
from operations.improvement.pda_improvement_cycle import CycleError, _route_task, run_cycle


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "pda"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "pda-test@example.invalid")
    _git(repo, "config", "user.name", "PDA Test")
    (repo / "README.md").write_text("pda\n", encoding="utf-8")
    (repo / "continuity").mkdir()
    (repo / "continuity" / "autonomous-improvement.json").write_text(
        json.dumps({"schema_version": 1, "enabled": True}), encoding="utf-8"
    )
    _git(repo, "add", "README.md", "continuity")
    _git(repo, "commit", "-m", "base")
    return repo


def _set_committed_policy(repo: Path, *, enabled: bool) -> None:
    (repo / "continuity" / "autonomous-improvement.json").write_text(
        json.dumps({"schema_version": 1, "enabled": enabled}), encoding="utf-8"
    )


def _config(tmp_path: Path, repo: Path, *, enabled: bool = True, max_wip: int = 1) -> Path:
    path = tmp_path / "cycle.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "enabled": enabled,
                "tenant": "pda-improvement",
                "assignee": "default",
                "repo_root": str(repo),
                "worktrees_root": str(tmp_path / "worktrees"),
                "base_branch": "main",
                "max_wip": max_wip,
                "max_assignments_per_tick": 1,
                "require_profile_on_disk": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def _task(conn, title: str, *, priority: int, status: str = "ready", assignee=None):
    task_id = kanban_db.create_task(
        conn,
        title=title,
        body="目的と完了条件が定義済み",
        tenant="pda-improvement",
        priority=priority,
        assignee=assignee,
        workspace_kind="dir",
        workspace_path="/placeholder",
    )
    if status == "review":
        assert kanban_db.request_review(
            conn,
            task_id,
            summary="pending approval",
            metadata={"pda_approval": {"schema_version": 1}},
        )
    return task_id


def test_tampered_runtime_config_cannot_outrank_committed_policy(tmp_path, monkeypatch):
    # Adversarial replay: the rendered runtime config is user-writable, so a
    # stray writer can flip its "enabled" to true. The committed repository
    # policy is the single source of truth; the router must stay a noop.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=False)
    config = _config(tmp_path, repo, enabled=True)

    result = run_cycle(config)

    assert result == {
        "ok": True,
        "enabled": False,
        "assigned": [],
        "reason": "disabled-by-committed-policy",
    }
    assert not (tmp_path / "worktrees").exists()


def test_disabled_cycle_is_a_true_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    config = _config(tmp_path, repo, enabled=False)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "ready", priority=10)

    result = run_cycle(config)

    assert result == {"ok": True, "enabled": False, "assigned": [], "reason": "disabled"}
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.assignee is None
    assert not (tmp_path / "worktrees").exists()


def test_cycle_routes_highest_priority_ready_card_to_isolated_worktree(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        low = _task(conn, "low", priority=1)
        high = _task(conn, "high", priority=100)

    result = run_cycle(config)

    assert result["ok"] is True
    assert result["assigned"] == [high]
    with kanban_db.connect() as conn:
        selected = kanban_db.get_task(conn, high)
        untouched = kanban_db.get_task(conn, low)
        assert selected is not None
        assert selected.assignee == "default"
        assert selected.status == "ready"
        assert selected.workspace_kind == "dir"
        assert selected.workspace_path == str(tmp_path / "worktrees" / high)
        assert selected.branch_name == f"pda-auto/{high}"
        assert "pda-autonomous-improvement" in (selected.skills or [])
        assert untouched is not None and untouched.assignee is None
        comment = conn.execute(
            "SELECT body FROM task_comments WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (high,),
        ).fetchone()["body"]
        assert "隔離worktree" in comment
        assert "最終承認" in comment
    assert _git(Path(selected.workspace_path), "branch", "--show-current") == f"pda-auto/{high}"


def test_pending_review_consumes_wip_and_prevents_new_assignment(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    config = _config(tmp_path, repo, max_wip=1)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        pending = _task(
            conn,
            "awaiting owner approval",
            priority=100,
            status="review",
            assignee="default",
        )
        candidate = _task(conn, "candidate", priority=50)

    result = run_cycle(config)

    assert result["assigned"] == []
    assert result["reason"] == "wip-limit"
    assert result["wip"] == 1
    with kanban_db.connect() as conn:
        assert kanban_db.get_task(conn, pending).status == "review"
        assert kanban_db.get_task(conn, candidate).assignee is None


def test_atomic_route_never_overwrites_a_concurrent_assignment(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "race", priority=100)
        stale = kanban_db.get_task(conn, task_id)
        assert stale is not None
        assert kanban_db.assign_task(conn, task_id, "other-worker")
        monkeypatch.setattr(cycle_module.kanban_db, "get_task", lambda conn, task_id: stale)

        with pytest.raises(CycleError) as raised:
            _route_task(
                conn,
                stale,
                tmp_path / "isolated",
                f"pda-auto/{task_id}",
                "default",
            )
        assert raised.value.kind == "claim-race"

        row = conn.execute(
            "SELECT assignee, workspace_path, branch_name, skills FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        comment_count = conn.execute(
            "SELECT COUNT(*) FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, "pda-improvement-cycle"),
        ).fetchone()[0]
        assert row["assignee"] == "other-worker"
        assert row["workspace_path"] == "/placeholder"
        assert row["branch_name"] is None
        assert row["skills"] is None
        assert comment_count == 0


def test_cycle_adopts_exact_existing_branch_but_rejects_path_collision(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "collision", priority=100)
    collision = tmp_path / "worktrees" / task_id
    collision.mkdir(parents=True)
    (collision / "foreign.txt").write_text("not a worktree\n", encoding="utf-8")

    result = run_cycle(config)

    assert result["ok"] is False
    assert result["assigned"] == []
    assert result["error_kind"] == "workspace-collision"
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.assignee is None


def test_stopped_or_non_ready_cards_are_never_routed(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        stopped = _task(conn, "【停止中】do not run", priority=100)
        todo = _task(conn, "not ready", priority=90)
        conn.execute("UPDATE tasks SET status = 'todo' WHERE id = ?", (todo,))
        conn.commit()

    result = run_cycle(config)

    assert result["assigned"] == []
    assert result["reason"] == "no-eligible-task"
    with kanban_db.connect() as conn:
        assert kanban_db.get_task(conn, stopped).assignee is None
        assert kanban_db.get_task(conn, todo).assignee is None
