#!/usr/bin/env python3
"""Deterministically render the Hermes delegation-safety mail patch."""
from __future__ import annotations

import difflib
from pathlib import Path


BASE_COMMIT = "5112f51749ac744923a702900730149dfc8634da"
FILES = (
    Path("agent/tool_guardrails.py"),
    Path("tools/delegate_tool.py"),
)


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one base match, found {count}")
    return text.replace(old, new, 1)


def _patched_guardrails(text: str) -> str:
    text = _replace_once(
        text,
        '''    action: str = "allow"  # allow | warn | block | halt
    code: str = "allow"
    message: str = ""
    tool_name: str = ""
    count: int = 0
    signature: ToolCallSignature | None = None
''',
        '''    action: str = "allow"  # allow | warn | reject | block | halt
    code: str = "allow"
    message: str = ""
    tool_name: str = ""
    count: int = 0
    signature: ToolCallSignature | None = None
    limit: int | None = None
    requested_count: int | None = None
    trigger: str = ""
''',
        label="decision fields",
    )
    text = _replace_once(
        text,
        '''        if self.signature is not None:
            data["signature"] = self.signature.to_metadata()
        return data
''',
        '''        if self.signature is not None:
            data["signature"] = self.signature.to_metadata()
        if self.limit is not None:
            data["limit"] = self.limit
        if self.requested_count is not None:
            data["requested_count"] = self.requested_count
        if self.trigger:
            data["trigger"] = self.trigger
        return data
''',
        label="decision metadata",
    )
    return _replace_once(
        text,
        '''            if self._turn_subagent_count >= cap:
                decision = ToolGuardrailDecision(
                    action="block",
                    code="loop_subagent_cap",
                    message=(
                        f"Blocked delegate_task: this turn has already spawned "
                        f"{self._turn_subagent_count} subagents (limit {cap}). "
                        "This looks like a runaway delegation loop. Finish the "
                        "work with the results you have and answer the user."
                    ),
                    tool_name=tool_name,
                    count=self._turn_subagent_count,
                    signature=signature,
                )
                self._halt_decision = decision
                return decision
''',
        '''            if self._turn_subagent_count + spawn_count > cap:
                decision = ToolGuardrailDecision(
                    action="reject",
                    code="loop_subagent_cap",
                    message=(
                        "Rejected delegate_task spawn before execution: this turn "
                        f"has already spawned {self._turn_subagent_count} subagents "
                        f"(limit {cap}), and this call requested {spawn_count} more. "
                        "No child was started. Continue the current turn without "
                        "another delegate_task spawn: use completed child results or "
                        "another in-scope tool. If direct execution is impossible, "
                        "report the exact unfinished work and blocker once."
                    ),
                    tool_name=tool_name,
                    count=self._turn_subagent_count,
                    signature=signature,
                    limit=cap,
                    requested_count=spawn_count,
                    trigger="before_call",
                )
                return decision
''',
        label="subagent cap",
    )


def _patched_delegate_tool(text: str) -> str:
    text = _replace_once(
        text,
        '''        def _run_with_thread_capture():
            _worker_thread_holder["t"] = threading.current_thread()
            from agent.delegation_context import delegated_child_context

            with delegated_child_context(str(getattr(child, "session_id", "") or "")):
                return child.run_conversation(
                    user_message=goal,
                    task_id=child_task_id,
                    stream_callback=_relay_child_text,
                )

        _child_context = contextvars.copy_context()
''',
        '''        def _run_child_turn(user_message: str):
            from agent.delegation_context import delegated_child_context

            with delegated_child_context(str(getattr(child, "session_id", "") or "")):
                return child.run_conversation(
                    user_message=user_message,
                    task_id=child_task_id,
                    stream_callback=_relay_child_text,
                )

        def _run_with_thread_capture():
            _worker_thread_holder["t"] = threading.current_thread()
            return _run_child_turn(goal)

        _child_context = contextvars.copy_context()
''',
        label="child turn helper",
    )
    return _replace_once(
        text,
        '''                    _retry_result = child.run_conversation(
                        user_message=build_retry_message(_schema_errors),
                        task_id=child_task_id,
                        stream_callback=_relay_child_text,
                    )
''',
        '''                    _retry_result = _run_child_turn(
                        build_retry_message(_schema_errors)
                    )
''',
        label="schema retry context",
    )


def render_patch(source: Path) -> str:
    source = source.resolve()
    transforms = {
        Path("agent/tool_guardrails.py"): _patched_guardrails,
        Path("tools/delegate_tool.py"): _patched_delegate_tool,
    }
    chunks: list[str] = []
    for relative in FILES:
        old = (source / relative).read_text(encoding="utf-8")
        new = transforms[relative](old)
        chunks.append(f"diff --git a/{relative} b/{relative}\n")
        chunks.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
                n=3,
            )
        )
    body = "".join(chunks)
    return (
        "From 0000000000000000000000000000000000000000 Mon Sep 17 00:00:00 2001\n"
        "From: PDA local patch steward <pda-local@example.invalid>\n"
        "Date: Mon, 31 Aug 2026 21:20:00 +0900\n"
        "Subject: [PATCH] fix(delegation): continue after spawn cap rejection\n"
        "\n"
        "Keep the per-turn subagent ceiling as a pre-execution rejection, but do not\n"
        "turn that one policy result into a controlled halt of the parent agent loop.\n"
        "Report the actual completed spawn count, limit, requested increment, and\n"
        "trigger point in structured guardrail metadata, and reject an entire batch\n"
        "when it would cross the ceiling.\n"
        "\n"
        "Also route structured-output retry turns through the same delegated-child\n"
        "ContextVar scope as the initial child turn. This keeps Kanban ownership\n"
        "isolation active during retry and restores the parent context on success,\n"
        "failure, and exception.\n"
        "---\n"
        "\n"
        + body
        + "-- \n2.43.0\n"
    )
