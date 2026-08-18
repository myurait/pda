from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin_runtime import ScopeGatePluginRuntime


def _init_git_repo(path: Path, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", branch, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_runtime_builds_contract_then_blocks_incident_expansion(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    context = runtime.pre_llm_call(
        turn_id="turn-1",
        task_id="task-1",
        session_id="session-1",
        user_message="未commit資源をcommitしてpushして",
    )

    assert context is not None
    assert "repository-closeout" in context["context"]
    assert runtime.pre_tool_call(
        turn_id="turn-1",
        task_id="task-1",
        session_id="session-1",
        tool_call_id="discover",
        tool_name="terminal",
        args={"command": "git status --short", "workdir": str(tmp_path)},
    ) is None
    assert runtime.pre_tool_call(
        turn_id="turn-1",
        task_id="task-1",
        session_id="session-1",
        tool_call_id="lock-call",
        tool_name="scope_gate",
        args={
            "action": "lock",
            "targets": {
                "repositories": [str(tmp_path)],
                "worktrees": [str(tmp_path)],
                "branches": ["main"],
            },
        },
    ) is None

    locked = runtime.handle_scope_gate(
        {
            "action": "lock",
            "targets": {
                "repositories": [str(tmp_path)],
                "worktrees": [str(tmp_path)],
                "branches": ["main"],
            },
        },
        task_id="task-1",
        session_id="session-1",
    )
    blocked = runtime.pre_tool_call(
        turn_id="turn-1",
        task_id="task-1",
        session_id="session-1",
        tool_call_id="patch",
        tool_name="patch",
        args={"path": str(tmp_path / "file"), "old_string": "a", "new_string": "b"},
    )

    assert locked["ok"] is True
    assert blocked is not None
    assert blocked["action"] == "block"


def test_execution_middleware_rechecks_post_hook_modified_arguments(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    common = {
        "turn_id": "turn-drift",
        "task_id": "task-drift",
        "session_id": "session-drift",
    }
    runtime.pre_llm_call(**common, user_message="commitだけして")
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
        task_id="task-drift",
        session_id="session-drift",
    )
    safe_args = {"command": "git status --short", "workdir": str(tmp_path)}
    runtime.pre_tool_call(
        **common,
        tool_call_id="modified",
        tool_name="terminal",
        args=safe_args,
    )
    executed: list[dict[str, str]] = []

    result = runtime.tool_execution_middleware(
        **common,
        tool_call_id="modified",
        tool_name="terminal",
        args={"command": "git reset --hard", "workdir": str(tmp_path)},
        next_call=lambda args: executed.append(args) or {"ok": True},
    )

    assert executed == []
    assert "hook-argument-drift" in result["error"]


class _FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}
        self.hooks: list[str] = []
        self.middleware: list[str] = []
        self.sections: list[str] = []

    def register_tool(self, **kwargs: object) -> None:
        self.tools[str(kwargs["name"])] = kwargs

    def register_hook(self, name: str, callback: object) -> None:
        del callback
        self.hooks.append(name)

    def register_middleware(self, name: str, callback: object) -> None:
        del callback
        self.middleware.append(name)

    def register_system_prompt_section(self, section_id: str, content: str, **kwargs: object) -> None:
        del content, kwargs
        self.sections.append(section_id)


def test_plugin_registers_one_control_tool_and_enforcement_hooks() -> None:
    init_path = ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "pda_scope_gate_plugin",
        init_path,
        submodule_search_locations=[str(ROOT)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    context = _FakeContext()

    module.register(context)

    assert set(context.tools) == {"scope_gate"}
    assert set(context.hooks) == {
        "pre_llm_call",
        "pre_tool_call",
        "post_tool_call",
        "post_llm_call",
        "on_session_end",
    }
    assert context.sections == ["pda.scope-admission"]
    assert context.middleware == ["tool_execution"]


def test_explicit_all_worktree_inventory_freezes_post_tool_candidates(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    _init_git_repo(first, "main")
    _init_git_repo(second, "feature")
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    runtime.pre_llm_call(
        turn_id="turn-global",
        task_id="task-global",
        session_id="session-global",
        user_message="全てのworktreeの未commit資源をcommitしてpushして",
    )
    allowed = runtime.pre_tool_call(
        turn_id="turn-global",
        task_id="task-global",
        session_id="session-global",
        tool_call_id="inventory",
        tool_name="terminal",
        args={"command": "git worktree list --porcelain", "workdir": str(first)},
    )
    runtime.post_tool_call(
        turn_id="turn-global",
        task_id="task-global",
        session_id="session-global",
        tool_call_id="inventory",
        tool_name="terminal",
        args={"command": "git worktree list --porcelain", "workdir": str(first)},
        result={"output": f"worktree {first}\nHEAD abc\n\nworktree {second}\nHEAD def\n"},
        status="ok",
    )

    locked = runtime.handle_scope_gate(
        {
            "action": "lock",
            "targets": {
                "repositories": [str(first), str(second)],
                "worktrees": [str(first), str(second)],
                "branches": ["main", "feature"],
            },
        },
        task_id="task-global",
        session_id="session-global",
    )

    assert allowed is None
    assert locked["ok"] is True
    assert locked["contract"]["budget"]["max_tool_calls"] == 14


def test_post_llm_does_not_claim_uncompleted_closeout_success(tmp_path: Path) -> None:
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    runtime.pre_llm_call(
        turn_id="turn-partial",
        task_id="task-partial",
        session_id="session-partial",
        user_message="commitしてpushして",
    )

    runtime.post_llm_call(
        turn_id="turn-partial",
        task_id="task-partial",
        session_id="session-partial",
    )

    turn = runtime.store.get_turn("turn-partial")
    assert turn is not None
    assert turn["completion_status"] == "partial"


def test_success_completion_is_rejected_without_executed_evidence(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    runtime.pre_llm_call(
        turn_id="turn-evidence",
        task_id="task-evidence",
        session_id="session-evidence",
        user_message="commitしてpushして",
    )
    runtime.pre_tool_call(
        turn_id="turn-evidence",
        task_id="task-evidence",
        session_id="session-evidence",
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
        task_id="task-evidence",
        session_id="session-evidence",
    )

    result = runtime.handle_scope_gate(
        {"action": "complete", "status": "success"},
        task_id="task-evidence",
        session_id="session-evidence",
    )

    assert result["ok"] is False
    assert "evidence" in result["error"]
    turn = runtime.store.get_turn("turn-evidence")
    assert turn is not None
    assert turn["state"] == "locked"


def test_terminal_result_without_explicit_zero_exit_is_not_completion_evidence(
    tmp_path: Path,
) -> None:
    _init_git_repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    common = {
        "turn_id": "turn-exit",
        "task_id": "task-exit",
        "session_id": "session-exit",
    }
    runtime.pre_llm_call(**common, user_message="commitだけして")
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
        task_id="task-exit",
        session_id="session-exit",
    )
    commit_args = {"command": "git commit -m save", "workdir": str(tmp_path)}
    runtime.pre_tool_call(
        **common,
        tool_call_id="commit",
        tool_name="terminal",
        args=commit_args,
    )
    runtime.post_tool_call(
        **common,
        tool_call_id="commit",
        tool_name="terminal",
        args=commit_args,
        result={"output": "looks successful but has no exit status"},
        status="ok",
    )

    result = runtime.handle_scope_gate(
        {"action": "complete", "status": "success"},
        task_id="task-exit",
        session_id="session-exit",
    )

    assert result["ok"] is False
    assert "commit-existing-content" in result["error"]


def test_success_completion_requires_commit_push_and_later_ref_verification(
    tmp_path: Path,
) -> None:
    _init_git_repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    common = {
        "turn_id": "turn-complete",
        "task_id": "task-complete",
        "session_id": "session-complete",
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
        task_id="task-complete",
        session_id="session-complete",
    )

    expected_head = "a" * 40
    for call_id, command, output in (
        ("commit", "git commit -m save", "ok"),
        ("push", "git push origin main", "ok"),
        ("verify-local", "git rev-parse HEAD", expected_head),
        (
            "verify-remote",
            "git ls-remote --heads origin main",
            f"{'b' * 40}\trefs/heads/main",
        ),
    ):
        args = {"command": command, "workdir": str(tmp_path)}
        assert runtime.pre_tool_call(
            **common,
            tool_call_id=call_id,
            tool_name="terminal",
            args=args,
        ) is None
        runtime.post_tool_call(
            **common,
            tool_call_id=call_id,
            tool_name="terminal",
            args=args,
            result={"output": output, "exit_code": 0},
            status="ok",
        )

    mismatch = runtime.handle_scope_gate(
        {"action": "complete", "status": "success"},
        task_id="task-complete",
        session_id="session-complete",
    )
    assert mismatch["ok"] is False
    assert "remote-ref-equals-local-head" in mismatch["error"]

    correct_args = {
        "command": "git ls-remote --heads origin main",
        "workdir": str(tmp_path),
    }
    assert runtime.pre_tool_call(
        **common,
        tool_call_id="verify-remote-correct",
        tool_name="terminal",
        args=correct_args,
    ) is None
    runtime.post_tool_call(
        **common,
        tool_call_id="verify-remote-correct",
        tool_name="terminal",
        args=correct_args,
        result={"output": f"{expected_head}\trefs/heads/main", "exit_code": 0},
        status="ok",
    )

    result = runtime.handle_scope_gate(
        {"action": "complete", "status": "success"},
        task_id="task-complete",
        session_id="session-complete",
    )

    assert result == {"ok": True, "state": "completed", "completion_status": "success"}
