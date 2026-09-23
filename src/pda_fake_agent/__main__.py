import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import acp
from acp.schema import (
    InitializeResponse,
    NewSessionResponse,
    PermissionOption,
    PromptResponse,
    ToolCallUpdate,
)


class FakeAgent(acp.Agent):
    def __init__(self) -> None:
        self.cancelled = asyncio.Event()

    def on_connect(self, conn: acp.Client) -> None:
        self.client = conn

    async def initialize(self, protocol_version: int, **kwargs: Any) -> InitializeResponse:
        return InitializeResponse(protocol_version=protocol_version, agent_capabilities={})

    async def new_session(self, cwd: str, **kwargs: Any) -> NewSessionResponse:
        self.cancelled.clear()
        return NewSessionResponse(session_id=str(uuid4()))

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        self.cancelled.set()

    async def prompt(self, session_id: str, prompt: list, **kwargs: Any) -> PromptResponse:
        mode = os.environ.get("FAKE_MODE", "echo")
        await self.client.session_update(
            session_id=session_id, update=acp.update_agent_thought_text("入力を確認します。")
        )
        tool = acp.start_read_tool_call("read-1", "read /work/README", "/work/README")
        await self.client.session_update(session_id=session_id, update=tool)
        await self.client.session_update(
            session_id=session_id,
            update=acp.update_tool_call(
                "read-1", status="completed", raw_output={"text": "fixture README"}
            ),
        )
        if mode == "permission":
            await self.client.request_permission(
                session_id=session_id,
                tool_call=ToolCallUpdate(
                    tool_call_id="read-1", kind="read", title="read /work/README"
                ),
                options=[
                    PermissionOption(option_id="allow", name="Allow once", kind="allow_once"),
                    PermissionOption(option_id="reject", name="Reject once", kind="reject_once"),
                ],
            )
        if mode == "slow":
            try:
                await asyncio.wait_for(
                    self.cancelled.wait(), float(os.environ.get("FAKE_SLEEP_SECONDS", "700"))
                )
                return PromptResponse(stop_reason="cancelled")
            except TimeoutError:
                pass
        text = "".join(getattr(block, "text", "") for block in prompt)
        if mode == "echo":
            Path("note.txt").write_text(text[-100:])
        body = json.dumps(
            {"kind": "bogus" if mode == "invalid" else "input", "payload": {"text": text[-100:]}},
            ensure_ascii=False,
        )
        await self.client.session_update(
            session_id=session_id, update=acp.update_agent_message_text(body)
        )
        return PromptResponse(stop_reason="end_turn")


if __name__ == "__main__":
    asyncio.run(acp.run_agent(FakeAgent()))
