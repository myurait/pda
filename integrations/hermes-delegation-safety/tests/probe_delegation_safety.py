#!/usr/bin/env python3
"""Focused executable regression probe for the Hermes delegation safety patch.

The probe deliberately avoids pytest so it can run with the installed Hermes
runtime Python.  It exercises the production modules from ``--source``; when
``--overlay`` is supplied, only the patched files in that minimal shadow tree
replace their base counterparts.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import shutil
import sys
import traceback
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _load_override(module_name: str, path: Path):
    """Load one patched module while resolving its dependencies from base."""
    parent_name = module_name.rsplit(".", 1)[0]
    importlib.import_module(parent_name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_modules(source: Path, overlay: Path | None):
    sys.path.insert(0, str(source))
    if overlay is None:
        guardrails = importlib.import_module("agent.tool_guardrails")
    else:
        guardrails = _load_override(
            "agent.tool_guardrails", overlay / "agent" / "tool_guardrails.py"
        )
    run_agent = importlib.import_module("run_agent")
    if overlay is None:
        delegate_tool = importlib.import_module("tools.delegate_tool")
    else:
        delegate_tool = _load_override(
            "tools.delegate_tool", overlay / "tools" / "delegate_tool.py"
        )
    return guardrails, run_agent, delegate_tool


def _check_cap_primitive(guardrails) -> None:
    cfg = guardrails.ToolCallGuardrailConfig(
        hard_stop_enabled=False,
        loop_caps=guardrails.LoopCapConfig(max_subagents=3),
    )
    controller = guardrails.ToolCallGuardrailController(cfg)

    first = controller.before_call(
        "delegate_task",
        {"tasks": [{"goal": "independent-a"}, {"goal": "independent-b"}]},
    )
    assert first.action == "allow"

    overflow = controller.before_call(
        "delegate_task",
        {"tasks": [{"goal": "independent-c"}, {"goal": "independent-d"}]},
    )
    assert overflow.action == "reject", overflow.to_metadata()
    assert overflow.allows_execution is False
    assert overflow.should_halt is False
    assert controller.halt_decision is None
    metadata = overflow.to_metadata()
    assert metadata["code"] == "loop_subagent_cap"
    assert metadata["count"] == 2
    assert metadata["limit"] == 3
    assert metadata["requested_count"] == 2
    assert metadata["trigger"] == "before_call"
    assert "repeated non-progressing" not in metadata["message"]
    assert "No child was started" in metadata["message"]

    # A rejected two-child batch must not consume the remaining slot.
    assert controller.before_call("delegate_task", {"goal": "independent-c"}).action == "allow"
    final_rejection = controller.before_call(
        "delegate_task", {"goal": "independent-d"}
    )
    assert final_rejection.action == "reject"
    assert final_rejection.count == 3

    # Control actions remain available at the cap.
    assert controller.before_call("delegate_task", {"action": "list"}).action == "allow"
    assert (
        controller.before_call(
            "delegate_task", {"action": "stop", "subagent_id": "sa-1"}
        ).action
        == "allow"
    )

    # The unrelated repeated-failure hard stop remains a hard stop.
    hard_cfg = guardrails.ToolCallGuardrailConfig(
        hard_stop_enabled=True,
        exact_failure_warn_after=1,
        exact_failure_block_after=1,
        same_tool_failure_halt_after=99,
        loop_caps=guardrails.LoopCapConfig(max_subagents=3),
    )
    hard = guardrails.ToolCallGuardrailController(hard_cfg)
    args = {"query": "same"}
    assert hard.before_call("web_search", args).action == "allow"
    hard.after_call("web_search", args, '{"error":"boom"}', failed=True)
    repeated = hard.before_call("web_search", args)
    assert repeated.code == "repeated_exact_failure_block"
    assert repeated.should_halt is True


def _make_tool_defs(*names: str) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _mock_tool_call(name: str, arguments: str, call_id: str):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _mock_response(*, content: str, finish_reason: str, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def _make_agent(run_agent):
    config = {
        "tool_loop_guardrails": {
            "hard_stop_enabled": False,
            "loop_caps": {"max_subagents": 1},
        }
    }
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("delegate_task")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("hermes_cli.config.load_config", return_value=config),
        patch("hermes_cli.config.load_config_readonly", return_value=config),
        patch("run_agent.OpenAI"),
    ):
        agent = run_agent.AIAgent(
            api_key="test-key-not-a-secret",
            base_url="https://example.invalid/v1",
            max_iterations=8,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    agent.client = MagicMock()
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.compression_enabled = False
    agent.save_trajectories = False
    agent.skip_background_review = True
    return agent


def _check_agent_loop_continues(run_agent) -> None:
    agent = _make_agent(run_agent)
    first_args = {"goal": "independent result one"}
    capped_args = {"goal": "independent result two"}
    agent.client.chat.completions.create.side_effect = [
        _mock_response(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                _mock_tool_call("delegate_task", json.dumps(first_args), "c-first")
            ],
        ),
        _mock_response(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                _mock_tool_call("delegate_task", json.dumps(capped_args), "c-capped")
            ],
        ),
        _mock_response(
            content="Used the completed child result directly.",
            finish_reason="stop",
            tool_calls=None,
        ),
    ]

    with (
        patch.object(
            agent,
            "_dispatch_delegate_task",
            return_value=json.dumps(
                {"results": [{"status": "completed", "summary": "usable"}]}
            ),
        ) as dispatch,
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("delegate bounded work, then finish directly")

    assert dispatch.call_count == 1
    assert result["turn_exit_reason"].startswith("text_response"), result
    assert result["final_response"] == "Used the completed child result directly."
    assert "guardrail" not in result
    assert "repeated non-progressing" not in result["final_response"]
    tool_messages = [m for m in result["messages"] if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    rejected = json.loads(tool_messages[-1]["content"])
    assert rejected["guardrail"]["action"] == "reject"
    assert rejected["guardrail"]["code"] == "loop_subagent_cap"


def _clear_worker_env() -> None:
    for key in tuple(os.environ):
        if key.startswith("HERMES_KANBAN_"):
            os.environ.pop(key, None)
    os.environ.pop("HERMES_DELEGATED_CHILD_CONTEXT", None)
    os.environ.pop("HERMES_KANBAN_BOARD", None)


def _make_running_task(home: Path, mode: str):
    _clear_worker_env()
    home.mkdir(parents=True, exist_ok=True)
    workspace = home / "workspace"
    workspace.mkdir()
    os.environ["HERMES_HOME"] = str(home)
    os.environ["HERMES_PROFILE"] = "parent-worker"
    os.environ["HERMES_KANBAN_WORKSPACE"] = str(workspace)

    from hermes_cli import kanban_db as kb

    kb._INITIALIZED_PATHS.clear()
    kb.init_db()
    conn = kb.connect()
    try:
        task_id = kb.create_task(
            conn,
            title=f"parent-{mode}",
            assignee="parent-worker",
            workspace_kind="scratch",
            workspace_path=str(workspace),
        )
        claim = kb.claim_task(conn, task_id)
        assert claim is not None
    finally:
        conn.close()
    os.environ["HERMES_KANBAN_TASK"] = task_id
    os.environ["HERMES_KANBAN_RUN_ID"] = str(claim.id)
    return kb, task_id


def _check_child_retry_context(delegate_tool, scratch: Path) -> None:
    from agent.delegation_context import (
        DELEGATED_CHILD_ENV_MARKER,
        is_delegated_child_context,
    )
    from tools import kanban_tools

    for mode in ("success", "failure", "exception"):
        kb, task_id = _make_running_task(scratch / f"kanban-{mode}", mode)
        observations: list[tuple[bool, str | None]] = []

        class Parent:
            _current_task_id = task_id

            def _touch_activity(self, _description):
                return None

        class Child:
            tool_progress_callback = None
            _delegate_saved_tool_names: list[str] = []
            _credential_pool = None
            _subagent_id = f"sa-{mode}-{uuid.uuid4().hex[:8]}"
            _delegate_depth = 1
            _parent_subagent_id = None
            _delegate_output_schema = {
                "type": "object",
                "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}},
            }
            session_id = f"child-{mode}"
            model = "test-model"
            session_prompt_tokens = 0
            session_completion_tokens = 0
            session_estimated_cost_usd = 0.0
            session_reasoning_tokens = 0

            def __init__(self):
                self.calls = 0

            def get_activity_summary(self):
                return {"api_call_count": 0, "max_iterations": 2, "current_tool": None}

            def run_conversation(self, user_message, task_id, **_kwargs):
                del user_message, task_id
                observations.append(
                    (
                        is_delegated_child_context(),
                        os.environ.get(DELEGATED_CHILD_ENV_MARKER),
                    )
                )
                self.calls += 1
                if self.calls == 1:
                    return {
                        "final_response": "not valid structured output",
                        "completed": True,
                        "api_calls": 1,
                        "messages": [],
                    }
                if mode == "success":
                    return {
                        "final_response": '{"ok": true}',
                        "completed": True,
                        "api_calls": 1,
                        "messages": [],
                    }
                if mode == "failure":
                    return {
                        "final_response": "",
                        "completed": False,
                        "api_calls": 1,
                        "messages": [],
                        "error": "retry failed",
                    }
                raise RuntimeError("retry exploded")

            def close(self):
                return None

        result = delegate_tool._run_single_child(
            0,
            "return structured output",
            Child(),
            Parent(),
        )
        assert result["status"] in {"completed", "failed", "error"}
        assert observations == [(True, None), (True, None)], (mode, observations)
        assert is_delegated_child_context() is False
        assert os.environ.get(DELEGATED_CHILD_ENV_MARKER) is None

        parent_mutation = json.loads(
            kanban_tools._handle_comment(
                {"task_id": task_id, "body": f"parent remains owner after {mode}"}
            )
        )
        assert parent_mutation["ok"] is True, parent_mutation
        conn = kb.connect()
        try:
            comments = kb.list_comments(conn, task_id)
        finally:
            conn.close()
        assert any(f"after {mode}" in comment.body for comment in comments)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    overlay = args.overlay.resolve() if args.overlay else None
    scratch = args.scratch.resolve()
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    _clear_worker_env()
    os.environ["HERMES_HOME"] = str(scratch / "hermes-home")
    os.environ["HERMES_PROFILE"] = "delegation-safety-probe"

    checks = []
    failures = []
    try:
        guardrails, run_agent, delegate_tool = _install_modules(source, overlay)
        checks = [
            ("cap primitive", lambda: _check_cap_primitive(guardrails)),
            ("agent-loop continuation", lambda: _check_agent_loop_continues(run_agent)),
            (
                "child retry context and parent Kanban mutation",
                lambda: _check_child_retry_context(delegate_tool, scratch),
            ),
        ]
        for label, check in checks:
            try:
                check()
            except Exception:
                failures.append(label)
                print(f"FAIL: {label}", file=sys.stderr)
                traceback.print_exc()
            else:
                print(f"PASS: {label}")
    finally:
        # Keep the isolated home alive until interpreter shutdown so Hermes's
        # asynchronous logging listener can flush without reopening deleted
        # log paths. The parent patch-series test removes it after this
        # subprocess exits.
        _clear_worker_env()

    if failures:
        print("FAILED checks: " + ", ".join(failures), file=sys.stderr)
        return 1
    print(f"All {len(checks)} focused delegation-safety checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
