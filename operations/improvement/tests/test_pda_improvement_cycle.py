from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_cli import kanban_db

import operations.improvement.pda_improvement_cycle as cycle_module
from operations.improvement.pda_improvement_cycle import CycleError, _route_task, run_cycle

REPO_ROOT = Path(__file__).resolve().parents[3]


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
    # The router resolves both the scope gate and the seed helper from the
    # repository root it was configured with, so a fixture repository that
    # lacks them cannot exercise the seeded assignment path at all. The files
    # are copied from this repository rather than stubbed: a stub would let the
    # cycle-level test agree with a gate that no longer exists.
    for relative in (
        Path("integrations") / "hermes-scope-gate" / "scope_gate.py",
        Path("operations") / "improvement" / "scope_seed.py",
    ):
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPO_ROOT / relative).read_bytes())
    # The gate resolves its contract schema relative to its own module file.
    schemas = REPO_ROOT / "integrations" / "hermes-scope-gate" / "schemas"
    shutil.copytree(schemas, repo / "integrations" / "hermes-scope-gate" / "schemas")
    _git(repo, "add", "README.md", "continuity", "integrations", "operations")
    _git(repo, "commit", "-m", "base")
    return repo


def _set_committed_policy(
    repo: Path, *, enabled: bool, scope_seed: bool | None = None
) -> None:
    policy: dict = {"schema_version": 1, "enabled": enabled}
    if scope_seed is not None:
        policy["scope_seed"] = {"enabled": scope_seed}
    (repo / "continuity" / "autonomous-improvement.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )


def _config(
    tmp_path: Path,
    repo: Path,
    *,
    enabled: bool = True,
    max_wip: int = 1,
    per_tick: int = 1,
) -> Path:
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
                "max_assignments_per_tick": per_tick,
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
                scope_seed_enabled=False,
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


def _scope_state(tmp_path: Path) -> Path:
    return (
        tmp_path
        / "home"
        / "plugin-data"
        / "pda-scope-gate"
        / "scope-gate.db"
    )


def test_the_seed_path_is_inert_while_the_committed_policy_omits_it(
    tmp_path, monkeypatch
):
    """Default false: a card with no scope declaration still routes, and no
    seed store is created (D-S3-8; activation is the next gate's decision)."""

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "宣言のないカード", priority=100)

    result = run_cycle(config)

    assert result["assigned"] == [task_id]
    assert not _scope_state(tmp_path).exists()


def test_an_explicitly_disabled_seed_policy_records_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=True, scope_seed=False)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "宣言のないカード", priority=100)

    result = run_cycle(config)

    assert result["assigned"] == [task_id]
    assert not _scope_state(tmp_path).exists()


def test_an_enabled_seed_policy_refuses_a_card_without_a_scope_declaration(
    tmp_path, monkeypatch
):
    """With the switch on, a machine-readable write scope is a Ready-condition:
    an undeclared card is left unassigned with a card comment, rather than
    being handed to a worker under a ceiling nobody chose."""

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=True, scope_seed=True)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "宣言のないカード", priority=100)

    result = run_cycle(config)

    assert result["ok"] is True
    assert result["assigned"] == []
    assert result["refused"] == [
        {"task_id": task_id, "error_kind": "missing-scope-declaration"}
    ]
    assert result["reason"] == "no-routable-task"
    # The card is refused before a workspace is created for it, so an
    # unassignable card leaves no branch or worktree behind.
    assert not (tmp_path / "worktrees" / task_id).exists()
    with kanban_db.connect() as conn:
        assert kanban_db.get_task(conn, task_id).assignee is None
        comments = conn.execute(
            "SELECT body FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, "pda-improvement-cycle"),
        ).fetchall()
        assert len(comments) == 1
        assert "pda-scope" in comments[0]["body"]


def test_an_enabled_seed_policy_seeds_a_declared_card(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=True, scope_seed=True)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = _task(conn, "宣言済みカード", priority=100)
        conn.execute(
            "UPDATE tasks SET body = ? WHERE id = ?",
            (
                "目的: 直す\n\n```pda-scope\n"
                '{"write_paths": ["src/*.py"]}\n```\n',
                task_id,
            ),
        )
        conn.commit()

    result = run_cycle(config)

    assert result["assigned"] == [task_id]
    scope_gate = _load_scope_gate(repo)
    seed = scope_gate.GateStore(_scope_state(tmp_path)).get_contract_seed(task_id)
    assert seed is not None
    assert seed["write_paths"] == ["src/*.py"]
    assert seed["branch"] == f"pda-auto/{task_id}"
    assert seed["git_write"] == ["stage", "commit"]
    # Second layer stays shut and test assets are not writable by default.
    assert seed["execution"] == []
    assert seed["test_paths"] == []


def _load_scope_gate(repo: Path):
    import importlib.util

    path = REPO_ROOT / "integrations" / "hermes-scope-gate" / "scope_gate.py"
    spec = importlib.util.spec_from_file_location("cycle_test_scope_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys as _sys

    _sys.modules["cycle_test_scope_gate"] = module
    spec.loader.exec_module(module)
    return module


_DECLARED_BODY = '目的: 直す\n\n```pda-scope\n{"write_paths": ["src/*.py"]}\n```\n'


def _declare(conn, task_id: str, body: str = _DECLARED_BODY) -> None:
    conn.execute("UPDATE tasks SET body = ? WHERE id = ?", (body, task_id))


def test_an_undeclared_card_does_not_block_the_cards_behind_it(tmp_path, monkeypatch):
    """A card that cannot be routed must not become a queue-wide outage.

    The eligible list is priority-ordered and the same card leads it every
    tick, so ending the tick on the first refusal would let one unqualified
    card hold every other eligible card indefinitely. That is the shape the
    first day of activation would produce, because no card carried the
    declaration field before it existed.
    """

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=True, scope_seed=True)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        blocked = _task(conn, "宣言のないカード", priority=100)
        routable = _task(conn, "宣言済みカード", priority=50)
        _declare(conn, routable)

    result = run_cycle(config)

    assert result["ok"] is True
    assert result["assigned"] == [routable]
    assert result["refused"] == [
        {"task_id": blocked, "error_kind": "missing-scope-declaration"}
    ]
    with kanban_db.connect() as conn:
        assert kanban_db.get_task(conn, routable).assignee == "default"
        assert kanban_db.get_task(conn, blocked).assignee is None


def test_a_refusal_after_an_assignment_still_reports_the_assignment(
    tmp_path, monkeypatch
):
    """Work already committed to the board must appear in the result.

    Discarding the accumulated list on the way out reported "nothing was
    assigned" for a tick whose assignment had in fact been made, notified, and
    seeded, which is the one thing the return value exists to state.
    """

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=True, scope_seed=True)
    config = _config(tmp_path, repo, max_wip=3, per_tick=2)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        first = _task(conn, "宣言済みカード", priority=100)
        _declare(conn, first)
        second = _task(conn, "宣言のないカード", priority=50)
        third = _task(conn, "二枚目の宣言済みカード", priority=10)
        _declare(conn, third)

    result = run_cycle(config)

    assert result["ok"] is True
    assert result["assigned"] == [first, third]
    assert result["refused"] == [
        {"task_id": second, "error_kind": "missing-scope-declaration"}
    ]
    assert result["wip"] == 2


@pytest.mark.parametrize(
    "pattern",
    [
        # Breadth written in a spelling the leading-wildcard rule does not
        # compare, measured against the tree instead.
        "?*/**",
        # A governance surface, which the activation path refuses outright.
        "operations/improvement/*.py",
    ],
)
def test_an_overbroad_declaration_is_refused_before_a_workspace_exists(
    tmp_path, monkeypatch, pattern
):
    """The measured ceiling is enforced where the card can still be fixed.

    Both refusals happen in the pre-check, so the card leaves no branch and no
    worktree behind, and the card behind it is still routed.
    """

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    _set_committed_policy(repo, enabled=True, scope_seed=True)
    config = _config(tmp_path, repo)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        wide = _task(conn, "広すぎる宣言のカード", priority=100)
        _declare(
            conn,
            wide,
            '目的: 直す\n\n```pda-scope\n{"write_paths": ["' + pattern + '"]}\n```\n',
        )
        routable = _task(conn, "宣言済みカード", priority=50)
        _declare(conn, routable)

    result = run_cycle(config)

    assert result["ok"] is True
    assert result["assigned"] == [routable]
    assert result["refused"] == [
        {"task_id": wide, "error_kind": "invalid-scope-declaration"}
    ]
    assert not (tmp_path / "worktrees" / wide).exists()
