# ruff: noqa: N999 -- Hermes plugin directory ids intentionally use hyphens.
"""PDA task-scope admission plugin for Hermes Agent."""

from __future__ import annotations

from typing import Any

try:  # Hermes loads plugins as namespaced packages.
    from .plugin_runtime import ScopeGatePluginRuntime, json_result
except ImportError:  # Direct pytest/plugin-doctor file import fallback.
    from plugin_runtime import ScopeGatePluginRuntime, json_result

_RUNTIME: ScopeGatePluginRuntime | None = None

_SYSTEM_POLICY = """PDA task scope admission is enforced at the tool boundary. Permission is not scope;
confidence-improving work is not scope. For a repository-closeout turn, lock one explicit target,
perform only bounded status/diff/integrity checks, the requested commit/push, and direct ref
verification. Never repair content, conflicts, tests, branches, worktrees, deployments, or unrelated
processes in that turn. Completion closes execution; report blockers instead of expanding the task."""

_SCOPE_GATE_SCHEMA = {
    "name": "scope_gate",
    "description": (
        "Lock, review, or complete the current PDA task-scope contract. "
        "For repository closeout, call lock after bounded read-only target discovery and before mutation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["lock", "review", "complete"],
            },
            "targets": {
                "type": "object",
                "properties": {
                    "repositories": {"type": "array", "items": {"type": "string"}},
                    "worktrees": {"type": "array", "items": {"type": "string"}},
                    "branches": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["repositories", "worktrees", "branches"],
                "additionalProperties": False,
            },
            "status": {
                "type": "string",
                "enum": ["success", "partial", "blocked", "failed", "interrupted"],
            },
            "reason": {
                "type": "string",
                "description": "Why an expansion review is indispensable; review always denies for closeout.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


def _runtime() -> ScopeGatePluginRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = ScopeGatePluginRuntime()
    return _RUNTIME


def _pre_llm_call(**kwargs: Any):
    return _runtime().pre_llm_call(**kwargs)


def _pre_tool_call(**kwargs: Any):
    return _runtime().pre_tool_call(**kwargs)


def _post_tool_call(**kwargs: Any) -> None:
    _runtime().post_tool_call(**kwargs)


def _tool_execution_middleware(**kwargs: Any):
    return _runtime().tool_execution_middleware(**kwargs)


def _post_llm_call(**kwargs: Any) -> None:
    _runtime().post_llm_call(**kwargs)


def _on_session_end(**kwargs: Any) -> None:
    _runtime().on_session_end(**kwargs)


def _handle_scope_gate(params: dict[str, Any], **kwargs: Any) -> str:
    return json_result(_runtime().handle_scope_gate(params, **kwargs))


def register(ctx: Any) -> None:
    ctx.register_system_prompt_section(
        "pda.scope-admission",
        _SYSTEM_POLICY,
        position="after_memory",
        max_chars=1000,
    )
    ctx.register_tool(
        name="scope_gate",
        toolset="scope-control",
        schema=_SCOPE_GATE_SCHEMA,
        handler=_handle_scope_gate,
        description=_SCOPE_GATE_SCHEMA["description"],
    )
    ctx.register_middleware("tool_execution", _tool_execution_middleware)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("post_tool_call", _post_tool_call)
    ctx.register_hook("post_llm_call", _post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
