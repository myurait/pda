# ruff: noqa: N999 -- Hermes plugin directory ids intentionally use hyphens.
"""PDA communication-quality guard plugin for Hermes Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # Hermes loads plugins as namespaced packages.
    from .communication_guard import CommunicationGuardRuntime
except ImportError:  # Direct pytest/plugin-doctor fallback.
    from communication_guard import CommunicationGuardRuntime

_RUNTIME: CommunicationGuardRuntime | None = None

_SYSTEM_POLICY = """PDA owner communication is a decision boundary, not a worker log.
A direct status or stop request preempts new investigation. Japanese responses retain polite
です・ます style. Approval requests must state, in this order: 承認対象, 目的・成果,
承認後の変化, 主要リスクと可逆性, 推奨, and 一つの操作. Keep worker-only technical
evidence out of owner-visible prose; evidence remains in structured metadata. More detail is harmful
when it does not change the owner's outcome, risk, reversibility, or decision. Before
kanban_request_review executes, render its summary from metadata.pda_approval.owner_message with the fixed
approval template; never send a free-form worker status as the approval request."""


def _default_audit_path() -> Path:
    try:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    except (ImportError, TypeError):
        home = Path.home() / ".hermes"
    return home / "plugin-data" / "pda-communication-guard" / "audit.db"


def _runtime() -> CommunicationGuardRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = CommunicationGuardRuntime(_default_audit_path())
    return _RUNTIME


def _pre_llm_call(**kwargs: Any):
    return _runtime().pre_llm_call(**kwargs)


def _pre_tool_call(**kwargs: Any):
    return _runtime().pre_tool_call(**kwargs)


def _transform_llm_output(**kwargs: Any):
    return _runtime().transform_llm_output(**kwargs)


def _post_llm_call(**kwargs: Any) -> None:
    _runtime().post_llm_call(**kwargs)


def _on_session_end(**kwargs: Any) -> None:
    _runtime().on_session_end(**kwargs)


def register(ctx: Any) -> None:
    ctx.register_system_prompt_section(
        "pda.communication-quality",
        _SYSTEM_POLICY,
        position="after_memory",
        max_chars=1200,
    )
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("transform_llm_output", _transform_llm_output)
    ctx.register_hook("post_llm_call", _post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
