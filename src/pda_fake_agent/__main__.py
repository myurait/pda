"""A minimal ACP SDK agent for deterministic integration tests."""

import asyncio
import json
import os
import uuid
from typing import Any

from acp import Agent, run_agent, text_block, update_agent_message_text
from acp.schema import (
    AgentThoughtChunk,
    InitializeResponse,
    NewSessionResponse,
    PermissionOption,
    PromptResponse,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
)


class FakeAgent(Agent):
    def __init__(self) -> None:
        self.cancelled: dict[str, asyncio.Event] = {}
        self.conn: Any = None

    def on_connect(self, conn: Any) -> None:
        self.conn = conn

    async def initialize(self, protocol_version: int, **kwargs: Any) -> InitializeResponse:
        return InitializeResponse(protocol_version=protocol_version)

    async def new_session(self, cwd: str, **kwargs: Any) -> NewSessionResponse:
        sid = str(uuid.uuid4())
        self.cancelled[sid] = asyncio.Event()
        return NewSessionResponse(session_id=sid)

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        self.cancelled[session_id].set()

    async def prompt(self, session_id: str, prompt: list[Any], **kwargs: Any) -> PromptResponse:
        mode = os.getenv("FAKE_MODE", "echo")
        await self.conn.session_update(
            session_id=session_id,
            update=AgentThoughtChunk(
                session_update="agent_thought_chunk", content=text_block("入力を確認します。")
            ),
        )
        await self.conn.session_update(
            session_id=session_id,
            update=ToolCallStart(
                session_update="tool_call",
                tool_call_id="read-1",
                kind="read",
                title="read /work/README",
                status="in_progress",
                raw_input={"path": "/work/README"},
            ),
        )
        if mode == "permission":
            await self.conn.request_permission(
                session_id=session_id,
                tool_call=ToolCallUpdate(
                    tool_call_id="read-1", kind="read", title="read /work/README"
                ),
                options=[
                    PermissionOption(option_id="yes", name="Allow once", kind="allow_once"),
                    PermissionOption(option_id="no", name="Reject once", kind="reject_once"),
                ],
            )
        await self.conn.session_update(
            session_id=session_id,
            update=ToolCallProgress(
                session_update="tool_call_update",
                tool_call_id="read-1",
                status="completed",
                raw_output={"text": "fixture README"},
            ),
        )
        if mode == "slow":
            try:
                await asyncio.wait_for(
                    self.cancelled[session_id].wait(),
                    timeout=float(os.getenv("FAKE_SLEEP_SECONDS", "700")),
                )
                return PromptResponse(stop_reason="cancelled")
            except TimeoutError:
                pass
        tail = "".join(getattr(block, "text", "") for block in prompt)[-100:]
        body = {"kind": "bogus" if mode == "invalid" else "input", "payload": {"text": tail}}
        await self.conn.session_update(
            session_id=session_id,
            update=update_agent_message_text(json.dumps(body, ensure_ascii=False)),
        )
        return PromptResponse(stop_reason="end_turn")


if __name__ == "__main__":
    asyncio.run(run_agent(FakeAgent()))
