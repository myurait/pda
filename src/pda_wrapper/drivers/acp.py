import asyncio
import contextlib
import os
import signal
from collections import deque
from typing import Any

import acp
from acp.schema import RequestPermissionResponse

from pda_wrapper.drivers import RuntimeFailure, RuntimeOutput
from pda_wrapper.events import TaskEvents, json_text, log


class AcpClient(acp.Client):
    def __init__(self, declaration: dict, events: TaskEvents) -> None:
        self.declaration = declaration
        self.events = events
        self.chunks: list[str] = []

    def on_connect(self, conn: acp.Agent) -> None:
        pass

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        pass

    def observe(self, event: Any) -> None:
        if event.direction.value != "incoming":
            return
        message: dict = event.message
        if message.get("method") == "session/update":
            self.update(message.get("params", {}).get("update", {}))

    def update(self, update: dict) -> None:
        kind = update.get("sessionUpdate")
        if kind in {"agent_message_chunk", "agent_thought_chunk"}:
            content = update.get("content", {})
            if content.get("type") != "text":
                self.events.emit("unknown", **{"pda.raw": update})
                return
            text = content.get("text", "")
            if kind == "agent_message_chunk":
                self.chunks.append(text)
            self.events.emit(
                "message.output" if kind == "agent_message_chunk" else "reasoning",
                **{"pda.chars": len(text)},
            )
        elif kind == "tool_call":
            self.events.emit(
                "tool.call",
                **{
                    "pda.tool_call_id": update.get("toolCallId", ""),
                    "pda.tool_kind": update.get("kind", ""),
                    "pda.tool_title": update.get("title", ""),
                    "pda.raw_input": json_text(update.get("rawInput")),
                },
            )
        elif kind == "tool_call_update":
            self.events.emit(
                "tool.result",
                **{
                    "pda.tool_call_id": update.get("toolCallId", ""),
                    "pda.tool_status": update.get("status", ""),
                    "pda.raw_output": json_text(update.get("rawOutput", update.get("content"))),
                },
            )
        elif kind == "plan":
            self.events.emit("plan", **{"pda.items": len(update.get("entries", []))})
        elif kind == "usage_update":
            self.usage(update)
        else:
            self.events.emit("unknown", **{"pda.raw": update})

    def usage(self, usage: dict) -> None:
        mapping = {
            "inputTokens": "gen_ai.usage.input_tokens",
            "outputTokens": "gen_ai.usage.output_tokens",
            "used": "pda.context_used",
            "size": "pda.context_size",
        }
        self.events.emit(
            "usage",
            **{target: usage[source] for source, target in mapping.items() if source in usage},
        )

    async def request_permission(
        self, session_id: str, tool_call: Any, options: list, **kwargs: Any
    ) -> RequestPermissionResponse:
        tool = tool_call.model_dump(by_alias=True, exclude_none=True)
        choices = [option.model_dump(by_alias=True, exclude_none=True) for option in options]
        self.events.emit(
            "permission.request",
            **{"pda.tool_call_id": tool.get("toolCallId", ""), "pda.options": json_text(choices)},
        )
        permissions = self.declaration["permissions"]
        deny = tool.get("kind") in permissions["deny_kinds"]
        policy = "reject_once" if deny else permissions["default"]
        choice = next((option for option in choices if option["kind"] == policy), None)
        option_id = choice["optionId"] if choice else "cancelled"
        self.events.emit(
            "permission.response", **{"pda.option_id": option_id, "pda.policy": policy}
        )
        outcome = (
            {"outcome": "selected", "optionId": option_id} if choice else {"outcome": "cancelled"}
        )
        return RequestPermissionResponse.model_validate({"outcome": outcome})


async def _stderr(process: asyncio.subprocess.Process, tail: deque) -> None:
    if process.stderr:
        while line := await process.stderr.readline():
            text = line.decode(errors="replace").rstrip()
            tail.append(text)
            log("runtime.stderr", text=text)


async def _terminate(process: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), 2)
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await process.wait()


async def run(
    declaration: dict, prompt: str, events: TaskEvents, workdir: str = "/work"
) -> RuntimeOutput:
    client = AcpClient(declaration, events)
    command = declaration["adapter"]["command"]
    env = {**os.environ, **declaration["adapter"].get("env", {})}
    tail: deque[str] = deque(maxlen=20)
    try:
        async with acp.spawn_agent_process(
            client,
            "setsid",
            *command,
            env=env,
            cwd=workdir,
            observers=[client.observe],
        ) as (conn, process):
            reader = asyncio.create_task(_stderr(process, tail))
            session_id = None
            pending = None
            try:
                await conn.initialize(protocol_version=acp.PROTOCOL_VERSION)
                session = await conn.new_session(cwd=workdir, mcp_servers=[])
                session_id = session.session_id
                pending = asyncio.create_task(
                    conn.prompt(session_id=session_id, prompt=[acp.text_block(prompt)])
                )
                response = await asyncio.shield(pending)
                result = response.model_dump(by_alias=True, exclude_none=True)
                if isinstance(result.get("usage"), dict):
                    client.usage(result["usage"])
                stop_reason = result["stopReason"]
                events.emit("turn.end", **{"pda.stop_reason": stop_reason})
                return RuntimeOutput("".join(client.chunks), stop_reason)
            except asyncio.CancelledError:
                if session_id:
                    with contextlib.suppress(Exception):
                        async with asyncio.timeout(2):
                            await conn.cancel(session_id=session_id)
                            if pending:
                                await asyncio.shield(pending)
                events.emit("turn.end", **{"pda.stop_reason": "cancelled"})
                raise
            finally:
                if pending and not pending.done():
                    pending.cancel()
                if pending:
                    await asyncio.gather(pending, return_exceptions=True)
                await _terminate(process)
                await reader
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        events.emit(
            "unknown",
            **{
                "pda.raw": {
                    "reason": "acp_runtime_failed",
                    "error": str(exc),
                    "stderr_tail": list(tail),
                }
            },
        )
        raise RuntimeFailure("acp_runtime_failed") from exc
