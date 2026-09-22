"""ACP SDK client: one subprocess and one session for each task."""

import asyncio
import contextlib
import os
from typing import Any

from acp import Client, spawn_agent_process, text_block
from acp.connection import StreamEvent
from acp.exceptions import RequestError
from acp.schema import AllowedOutcome, DeniedOutcome, RequestPermissionResponse

from pda_wrapper.drivers import RuntimeFailure
from pda_wrapper.events import Events, json_text, map_update, raw_json


def permission_option(tool: dict, options: list[dict], policy: dict) -> tuple[str | None, str]:
    wanted = (
        "reject_once"
        if tool.get("kind") in policy.get("deny_kinds", [])
        else policy.get("default", "allow_once")
    )
    return next((o["optionId"] for o in options if o["kind"] == wanted), None), wanted


class PDAClient(Client):
    def __init__(self, events: Events, policy: dict):
        self.events = events
        self.policy = policy
        self.messages: list[str] = []
        self.permission_requested = False

    def observe(self, event: StreamEvent) -> None:
        # Observe before SDK validation so future/unknown sessionUpdate types are not lost.
        if event.direction.value != "incoming":
            return
        message = event.message
        if message.get("method") != "session/update":
            return
        update = message.get("params", {}).get("update", {})
        kind, attrs = map_update(update)
        self.events.emit(kind, **attrs)
        if update.get("sessionUpdate") == "agent_message_chunk":
            content = update.get("content", {})
            if content.get("type") == "text":
                self.messages.append(content["text"])

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        pass  # Raw notifications are handled once by observe().

    async def request_permission(
        self, session_id: str, tool_call: Any, options: list[Any], **kwargs: Any
    ) -> RequestPermissionResponse:
        self.permission_requested = True
        tool = tool_call.model_dump(by_alias=True, exclude_none=True)
        choices = [o.model_dump(by_alias=True, exclude_none=True) for o in options]
        self.events.emit(
            "permission.request",
            **{"pda.tool_call_id": tool.get("toolCallId", ""), "pda.options": json_text(choices)},
        )
        option, wanted = permission_option(tool, choices, self.policy)
        self.events.emit(
            "permission.response", **{"pda.option_id": option or "cancelled", "pda.policy": wanted}
        )
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=option)
            if option
            else DeniedOutcome(outcome="cancelled")
        )

    async def ext_notification(self, method: str, params: dict) -> None:
        self.events.emit("unknown", **{"pda.raw": raw_json({"method": method, "params": params})})


async def run(
    declaration: dict, prompt: str, events: Events, workdir: str = "/work"
) -> tuple[str, str]:
    adapter = declaration["adapter"]
    command = adapter["command"]
    client = PDAClient(events, declaration["permissions"])
    env = {**os.environ, **adapter.get("env", {})}
    try:
        async with spawn_agent_process(
            client, command[0], *command[1:], env=env, observers=[client.observe]
        ) as (conn, process):

            async def drain_stderr() -> None:
                if process.stderr:
                    while line := await process.stderr.readline():
                        events.emit(
                            "unknown",
                            **{
                                "pda.raw": raw_json(
                                    {"adapter_stderr": line.decode(errors="replace")}
                                )
                            },
                        )

            stderr_task = asyncio.create_task(drain_stderr())
            session_id = None
            try:
                await conn.initialize(protocol_version=1)
                session = await conn.new_session(cwd=workdir, mcp_servers=[])
                session_id = session.session_id
                response = await conn.prompt(session_id=session_id, prompt=[text_block(prompt)])
                events.emit("turn.end", **{"pda.stop_reason": response.stop_reason})
                if response.usage:
                    usage = response.usage.model_dump(by_alias=True, exclude_none=True)
                    attrs = {
                        f"gen_ai.usage.{dst}": usage[src]
                        for src, dst in [
                            ("inputTokens", "input_tokens"),
                            ("outputTokens", "output_tokens"),
                        ]
                        if src in usage
                    }
                    if attrs:
                        events.emit("usage", **attrs)
                return "".join(client.messages), response.stop_reason
            except asyncio.CancelledError:
                if session_id:
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(conn.cancel(session_id=session_id), timeout=2)
                events.emit("turn.end", **{"pda.stop_reason": "cancelled"})
                raise
            finally:
                stderr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await stderr_task
    except (OSError, ConnectionError, EOFError, RequestError) as exc:
        raise RuntimeFailure(f"acp_runtime:{type(exc).__name__}:{exc}") from exc
