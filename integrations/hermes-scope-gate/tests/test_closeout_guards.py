"""Regression guards for the closeout-only invariants of the lock machinery.

These tests are written before the ``lock_turn`` task-class branch is
generalized (design checklist item 7 / R-06). They pin the behaviour that
generalization must not weaken: the closeout lock keeps its own state
machine, its own bounded-discovery candidate requirement, and its own
contract shape, and closeout admission keeps its own code path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin_runtime import ScopeGatePluginRuntime
from scope_gate import GateStore


def _init_git_repo(path: Path, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    if (path / ".git").exists():
        return
    subprocess.run(
        ["git", "init", "-q", "-b", branch, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


def _closeout_turn(tmp_path: Path, *, discover: bool = True) -> GateStore:
    _init_git_repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.start_turn(
        turn_id="turn-closeout",
        session_id="session-closeout",
        task_id="task-closeout",
        user_message="commitしてpushして",
    )
    if discover:
        store.admit_tool(
            turn_id="turn-closeout",
            tool_call_id="discover",
            tool_name="terminal",
            args={"command": "git status --short", "workdir": str(tmp_path)},
        )
    return store


def test_closeout_turn_starts_in_its_own_discovery_state(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path, discover=False)

    turn = store.get_turn("turn-closeout")

    assert turn is not None
    assert turn["task_class"] == "repository-closeout"
    assert turn["state"] == "discovering"
    assert turn["contract_json"] is None


def test_closeout_lock_still_requires_bounded_discovery_candidates(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path, discover=False)

    with pytest.raises(ValueError, match="bounded discovery"):
        store.lock_turn(
            turn_id="turn-closeout",
            repositories=[str(tmp_path)],
            worktrees=[str(tmp_path)],
            branches=["main"],
        )


def test_closeout_lock_rejects_relock_from_a_closed_state(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path)
    store.complete_turn(turn_id="turn-closeout", status="blocked")

    with pytest.raises(ValueError, match="cannot lock from state"):
        store.lock_turn(
            turn_id="turn-closeout",
            repositories=[str(tmp_path)],
            worktrees=[str(tmp_path)],
            branches=["main"],
        )


def test_closeout_lock_is_idempotent_and_keeps_its_contract(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path)
    first = store.lock_turn(
        turn_id="turn-closeout",
        repositories=[str(tmp_path)],
        worktrees=[str(tmp_path)],
        branches=["main"],
    )

    second = store.lock_turn(
        turn_id="turn-closeout",
        repositories=[str(tmp_path)],
        worktrees=[str(tmp_path)],
        branches=["main"],
    )

    assert first == second
    assert first["task_class"] == "repository-closeout"
    assert first["budget"]["max_wall_seconds"] == 900
    assert first["budget"]["max_expansions"] == 0
    # The closeout contract must not grow artifact-change write scope.
    assert "write_paths" not in first["targets"]
    assert "test_paths" not in first["targets"]
    assert "execution" not in first


def test_closeout_lock_rejects_non_absolute_targets(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path)

    with pytest.raises(ValueError, match="absolute paths"):
        store.lock_turn(
            turn_id="turn-closeout",
            repositories=["relative/repo"],
            worktrees=["relative/repo"],
            branches=["main"],
        )


def test_closeout_lock_rejects_multiple_worktrees_without_global_wording(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    _init_git_repo(first)
    _init_git_repo(second)
    store = GateStore(tmp_path / "scope.db")
    store.start_turn(
        turn_id="turn-two",
        session_id="session-two",
        user_message="commitしてpushして",
    )
    for index, target in enumerate((first, second)):
        store.admit_tool(
            turn_id="turn-two",
            tool_call_id=f"discover-{index}",
            tool_name="terminal",
            args={"command": "git status --short", "workdir": str(target)},
        )

    with pytest.raises(ValueError, match="exactly one worktree"):
        store.lock_turn(
            turn_id="turn-two",
            repositories=[str(first), str(second)],
            worktrees=[str(first), str(second)],
            branches=["main"],
        )


def test_worktree_candidate_recording_stays_closeout_only(tmp_path: Path) -> None:
    store = GateStore(tmp_path / "scope.db")
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message="ログイン画面のバグを修正して",
    )

    with pytest.raises(ValueError, match="repository-closeout"):
        store.record_worktree_candidates(
            turn_id="turn-change", paths=[str(tmp_path)]
        )


def test_closeout_admission_keeps_its_own_locked_code_path(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path)
    store.lock_turn(
        turn_id="turn-closeout",
        repositories=[str(tmp_path)],
        worktrees=[str(tmp_path)],
        branches=["main"],
    )

    # Structured write tools are never part of closeout scope, whatever the
    # artifact-change write catalogue later admits.
    denied = store.admit_tool(
        turn_id="turn-closeout",
        tool_call_id="write",
        tool_name="write_file",
        args={"path": str(tmp_path / "a.py"), "content": "x"},
    )
    # Closeout keeps admitting its own bounded verification subset.
    allowed = store.admit_tool(
        turn_id="turn-closeout",
        tool_call_id="verify",
        tool_name="terminal",
        args={"command": "git rev-parse HEAD", "workdir": str(tmp_path)},
    )

    assert denied.allowed is False
    assert denied.action == "expansion-zero"
    assert allowed.allowed is True
    assert allowed.action == "verify-local-head"


def test_closeout_lock_refuses_write_scope_arguments(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path)

    with pytest.raises(ValueError, match="no write scope"):
        store.lock_turn(
            turn_id="turn-closeout",
            repositories=[str(tmp_path)],
            worktrees=[str(tmp_path)],
            branches=["main"],
            write_paths=["src/*.py"],
        )


def test_closeout_still_closes_at_the_audit_hook(tmp_path: Path) -> None:
    # S1 behaviour: the post-LLM audit hook closes a locked closeout turn.
    # The artifact-change closure norm must not change this.
    _init_git_repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    common = {
        "turn_id": "turn-closeout",
        "task_id": "task-closeout",
        "session_id": "session-closeout",
    }
    runtime.pre_llm_call(**common, user_message="commitしてpushして")
    runtime.pre_tool_call(
        **common,
        tool_call_id="discover",
        tool_name="terminal",
        args={"command": "git status --short", "workdir": str(tmp_path)},
    )
    runtime.handle_scope_gate(
        {
            "action": "lock",
            "targets": {
                "repositories": [str(tmp_path)],
                "worktrees": [str(tmp_path)],
                "branches": ["main"],
            },
        },
        **common,
    )

    runtime.post_llm_call(**common)
    turn = runtime.store.get_turn("turn-closeout")

    assert turn is not None
    assert turn["state"] == "completed"
    assert turn["completion_status"] == "partial"


def test_closeout_contract_records_no_execution_opt_in(tmp_path: Path) -> None:
    store = _closeout_turn(tmp_path)
    contract = store.lock_turn(
        turn_id="turn-closeout",
        repositories=[str(tmp_path)],
        worktrees=[str(tmp_path)],
        branches=["main"],
    )
    turn = store.get_turn("turn-closeout")

    assert turn is not None
    stored = json.loads(turn["contract_json"])
    assert stored == contract
    assert stored["actions"]["forbidden"]
    assert "run-broad-tests" in stored["actions"]["forbidden"]
