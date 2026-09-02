# ruff: noqa: N999 -- Hermes plugin directory ids intentionally use hyphens.
"""Source-bound PDA task-scope control plugin for Hermes Agent."""

from __future__ import annotations

from typing import Any

try:  # Hermes loads plugins as namespaced packages.
    from .plugin_runtime_v2 import ScopeGateV2PluginRuntime, json_result
except ImportError:  # Direct pytest/plugin-doctor file import fallback.
    from plugin_runtime_v2 import ScopeGateV2PluginRuntime, json_result

_RUNTIME: ScopeGateV2PluginRuntime | None = None

_SYSTEM_POLICY = """PDA scope control is a three-phase cognitive loop, not a natural-language classifier.
The current authenticated instruction is authoritative. Before mutation, infer a source-bound
ScopeFrame and plan, submit both plus minimal deterministic containment through `scope_gate` review,
and lock only after the separate Terra review passes. Never infer instruction meaning or risk with
regex, keywords, task classes, or deterministic rules. Work against the reviewed frame, preserve
other worktrees, then call complete with observed effects and the executor's final scope audit.
Deterministic enforcement handles provenance, approval, resource containment, effect matching, and
stale-plan protection only. Review/audit failure blocks effects but never rewrites the instruction.
A prior turn is context, not authority. Read-only answers need no pre-work review."""

_STRING_ARRAY = {"type": "array", "items": {"type": "string"}}
_EFFECT_KINDS = [
    "file-write",
    "git-stage",
    "git-commit",
    "git-push",
    "service-reload",
    "process-manage",
    "external-send",
    "memory-write",
    "schedule-write",
    "skill-write",
    "board-write",
    "code-exec",
]
_SCOPE_FRAME_SCHEMA = {
    "type": "object",
    "properties": {
        "directive_relation": {
            "type": "string",
            "enum": ["new", "continue", "amend", "replace", "report", "stop"],
        },
        "required_outcomes": _STRING_ARRAY,
        "targets": _STRING_ARRAY,
        "allowed_means": _STRING_ARRAY,
        "completion_predicates": _STRING_ARRAY,
        "non_goals": _STRING_ARRAY,
        "uncertainties": _STRING_ARRAY,
        "source_refs": _STRING_ARRAY,
    },
    "required": [
        "directive_relation",
        "required_outcomes",
        "targets",
        "allowed_means",
        "completion_predicates",
        "non_goals",
        "uncertainties",
        "source_refs",
    ],
    "additionalProperties": False,
}
_CONTAINMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "worktrees": {
            **_STRING_ARRAY,
            "description": "Absolute directories the turn may write under (1-8). Required and non-empty.",
        },
        "write_paths": {
            **_STRING_ARRAY,
            "description": (
                "Glob patterns relative to a worktree root, e.g. 'src/**' or 'tmp/out/file.txt'. "
                "Never absolute paths. Do not list the gate's own state files."
            ),
        },
        "test_paths": {**_STRING_ARRAY, "description": "Relative glob patterns for test assets."},
        "allowed_effects": {
            "type": "array",
            "description": "Effect kinds this turn may cause; anything not listed fails closed.",
            "items": {"type": "string", "enum": _EFFECT_KINDS},
        },
        "command_allowlist": _STRING_ARRAY,
        "services": _STRING_ARRAY,
        "remotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "repository": {"type": "string"},
                    "remote": {"type": "string"},
                    "branch": {"type": "string"},
                },
                "required": ["repository", "remote", "branch"],
                "additionalProperties": False,
            },
        },
        "execution": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["focused-test", "syntax-check"],
            },
        },
        "max_tool_calls": {"type": "integer", "minimum": 1, "maximum": 500},
    },
    "required": ["worktrees", "write_paths", "allowed_effects"],
    "additionalProperties": False,
}
_EFFECT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": _EFFECT_KINDS,
            "description": "Effect kind from the shared vocabulary; the gate's own records are not effects.",
        },
        "target": {
            "type": "string",
            "description": "Absolute file path, worktree, service unit, or remote ref the effect touched.",
        },
        "result": {"type": "string"},
    },
    "required": ["kind", "target"],
    "additionalProperties": False,
}
_SCOPE_GATE_SCHEMA = {
    "name": "scope_gate",
    "description": (
        "Review, lock, audit, or inspect the current source-bound PDA scope frame. "
        "Call review before the first mutation, lock after pass, and complete before finalizing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["review", "lock", "complete"],
            },
            "scope_frame": _SCOPE_FRAME_SCHEMA,
            "plan": _STRING_ARRAY,
            "containment": _CONTAINMENT_SCHEMA,
            "status": {
                "type": "string",
                "enum": ["success", "partial", "blocked", "failed", "interrupted"],
            },
            "observed_effects": {"type": "array", "items": _EFFECT_SCHEMA},
            "final_scope_conformant": {"type": "boolean"},
            "completion_summary": {"type": "string"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


def _runtime() -> ScopeGateV2PluginRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = ScopeGateV2PluginRuntime()
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
