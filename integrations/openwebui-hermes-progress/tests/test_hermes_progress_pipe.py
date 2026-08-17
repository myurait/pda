import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from aiohttp import web

MODULE_PATH = Path(__file__).parents[1] / "functions" / "hermes_progress_pipe.py"
spec = importlib.util.spec_from_file_location("hermes_progress_pipe_local", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Pipe = module.Pipe


class FakeHermes:
    def __init__(
        self,
        events,
        *,
        event_delay=0,
        approval_status=200,
        approval_error_code="approval_not_active",
    ):
        self.events = events
        self.event_delay = event_delay
        self.approval_status = approval_status
        self.approval_error_code = approval_error_code
        self.approvals = []
        self.stops = []
        self.run_payloads = []
        self.headers = []
        self.runner = None
        self.base_url = None

    async def start(self):
        app = web.Application()
        app.router.add_post("/v1/runs", self.create_run)
        app.router.add_get("/v1/runs/{run_id}/events", self.run_events)
        app.router.add_post("/v1/runs/{run_id}/approval", self.approval)
        app.router.add_post("/v1/runs/{run_id}/stop", self.stop)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}/v1"
        return self

    async def close(self):
        if self.runner:
            await self.runner.cleanup()

    async def create_run(self, request):
        self.headers.append(dict(request.headers))
        self.run_payloads.append(await request.json())
        return web.json_response({"run_id": "run_test", "status": "started"}, status=202)

    async def run_events(self, request):
        response = web.StreamResponse(
            status=200, headers={"Content-Type": "text/event-stream"}
        )
        await response.prepare(request)
        if self.event_delay:
            await asyncio.sleep(self.event_delay)
        for event in self.events:
            try:
                await response.write(
                    f"data: {json.dumps(event)}\n\n".encode("utf-8")
                )
            except ConnectionResetError:
                return response
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass
        return response

    async def approval(self, request):
        self.approvals.append(await request.json())
        if self.approval_status >= 400:
            return web.json_response(
                {
                    "error": {
                        "message": "approval is no longer pending",
                        "code": self.approval_error_code,
                    }
                },
                status=self.approval_status,
            )
        return web.json_response(
            {
                "object": "hermes.run.approval_response",
                "run_id": request.match_info["run_id"],
                "choice": self.approvals[-1]["choice"],
                "resolved": 1,
            }
        )

    async def stop(self, request):
        self.stops.append(request.match_info["run_id"])
        return web.json_response({"run_id": request.match_info["run_id"], "status": "stopping"})


class FakeNtfy:
    def __init__(self, *, status=200):
        self.status = status
        self.messages = []
        self.runner = None
        self.base_url = None

    async def start(self):
        app = web.Application()
        app.router.add_post("/{topic}", self.publish)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        return self

    async def close(self):
        if self.runner:
            await self.runner.cleanup()

    async def publish(self, request):
        self.messages.append(
            {
                "topic": request.match_info["topic"],
                "body": await request.text(),
                "headers": dict(request.headers),
            }
        )
        return web.json_response({"id": "notification-test"}, status=self.status)


def configured_pipe(base_url):
    pipe = Pipe()
    pipe.valves.HERMES_API_URL = base_url
    pipe.valves.HERMES_API_KEY = "x" * 32
    pipe.valves.SHOW_TOOL_PREVIEW = True
    return pipe


def visible_content(chunks):
    parts = []
    for chunk in chunks:
        if not chunk.startswith("data: ") or chunk.startswith("data: [DONE]"):
            continue
        payload = json.loads(chunk[6:].strip())
        delta = payload.get("choices", [{}])[0].get("delta", {})
        parts.append(delta.get("content", ""))
    return "".join(parts)


def status_data(emitted):
    return [event["data"] for event in emitted if event.get("type") == "status"]


async def wait_for_message_count(ntfy, count, timeout=1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while len(ntfy.messages) < count and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)
    return len(ntfy.messages)


def test_run_timeout_defaults_to_unlimited():
    valves = Pipe.Valves()

    assert valves.RUN_TIMEOUT_SECONDS == 0
    assert valves.APPROVAL_TIMEOUT_SECONDS == 55
    assert valves.model_json_schema()["properties"]["RUN_TIMEOUT_SECONDS"]["minimum"] == 0

    timeout = Pipe()._run_client_timeout()
    assert timeout.total is None
    assert timeout.sock_read is None


def test_context_excludes_openwebui_ui_metadata():
    history, instructions = Pipe._build_context(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello", "statusHistory": [{"description": "secret tool status"}]},
            {"role": "assistant", "content": "world", "tool_calls": [{"name": "terminal"}]},
            {"role": "tool", "content": "must not pass"},
        ]
    )
    assert instructions == "system"
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    assert "secret tool status" not in json.dumps(history)
    assert "must not pass" not in json.dumps(history)


def test_session_scope_is_per_user_and_chat_and_stable():
    a = Pipe._hermes_session_ids(Pipe._scope_key(user_id="u1", chat_id="c1", session_id=None, message_id=None))
    b = Pipe._hermes_session_ids(Pipe._scope_key(user_id="u1", chat_id="c2", session_id=None, message_id=None))
    c = Pipe._hermes_session_ids(Pipe._scope_key(user_id="u2", chat_id="c1", session_id=None, message_id=None))
    again = Pipe._hermes_session_ids(Pipe._scope_key(user_id="u1", chat_id="c1", session_id=None, message_id=None))
    assert a == again
    assert len({a, b, c}) == 3


@pytest.mark.asyncio
async def test_tool_progress_uses_status_not_assistant_content():
    fake = await FakeHermes(
        [
            {"event": "reasoning.available", "text": "private chain of thought"},
            {"event": "tool.started", "tool": "terminal", "preview": "printf SECRET_COMMAND"},
            {"event": "tool.completed", "tool": "terminal", "duration": 0.25, "error": False},
            {"event": "message.delta", "delta": "PIPE_"},
            {"event": "message.delta", "delta": "OK"},
            {"event": "run.completed", "output": "PIPE_OK"},
        ]
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="test",
                history=[],
                instructions=None,
                session_id="owui_test",
                session_key="openwebui:test",
                event_emitter=emitter,
                event_call=None,
            )
        ]

        content = visible_content(chunks)
        statuses = status_data(emitted)
        assert content == "PIPE_OK"
        assert "terminal" not in content
        assert "SECRET_COMMAND" not in content
        assert "private chain of thought" not in content
        assert any("実行中: terminal" in item["description"] for item in statuses)
        assert any("完了: terminal" in item["description"] for item in statuses)
        assert statuses[-1]["description"] == "完了"
        assert statuses[-1]["done"] is True
        assert fake.stops == []
        assert fake.run_payloads[0]["session_id"] == "owui_test"
        assert fake.headers[0]["X-Hermes-Session-Key"] == "openwebui:test"
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_approval_without_event_call_is_denied_and_not_in_content():
    fake = await FakeHermes(
        [
            {
                "event": "approval.request",
                "description": "dangerous operation",
                "command": "rm something",
            },
            {"event": "message.delta", "delta": "Denied safely."},
            {"event": "run.completed", "output": "Denied safely."},
        ]
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="test approval",
                history=[],
                instructions=None,
                session_id="owui_test",
                session_key="openwebui:test",
                event_emitter=emitter,
                event_call=None,
            )
        ]
        content = visible_content(chunks)
        assert fake.approvals == [{"choice": "deny"}]
        assert content == "Denied safely."
        assert "rm something" not in content
        assert status_data(emitted)[-1]["done"] is True
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_interactive_approval_allows_once_only():
    fake = await FakeHermes(
        [
            {"event": "approval.request", "description": "safe test", "command": "printf ok"},
            {"event": "message.delta", "delta": "Approved."},
            {"event": "run.completed", "output": "Approved."},
        ]
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        calls = []

        async def event_call(event):
            calls.append(event)
            return True

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="approve",
                history=[],
                instructions=None,
                session_id="owui_test",
                session_key="openwebui:test",
                event_emitter=None,
                event_call=event_call,
            )
        ]
        assert visible_content(chunks) == "Approved."
        assert fake.approvals == [{"choice": "once"}]
        assert calls[0]["type"] == "confirmation"
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_stale_approval_response_does_not_mask_completed_run():
    fake = await FakeHermes(
        [
            {
                "event": "approval.request",
                "description": "safe test",
                "command": "printf ok",
            },
            {"event": "message.delta", "delta": "Result survived."},
            {"event": "run.completed", "output": "Result survived."},
        ],
        approval_status=409,
        approval_error_code="approval_not_active",
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        emitted = []

        async def emitter(event):
            emitted.append(event)

        async def event_call(_event):
            return True

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="late approval",
                history=[],
                instructions=None,
                session_id="owui_test",
                session_key="openwebui:test",
                event_emitter=emitter,
                event_call=event_call,
            )
        ]

        content = visible_content(chunks)
        assert content == "Result survived."
        assert "Hermesエラー" not in content
        assert fake.approvals == [{"choice": "once"}]
        assert fake.stops == []
        statuses = status_data(emitted)
        assert any("承認の受付は終了" in item["description"] for item in statuses)
        assert statuses[-1]["description"] == "完了"
        assert statuses[-1]["error"] is False
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_missing_terminal_event_reports_error_stops_run_and_closes_status():
    fake = await FakeHermes(
        [
            {"event": "tool.started", "tool": "terminal", "preview": "probe"},
        ]
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="test incomplete stream",
                history=[],
                instructions=None,
                session_id="owui_test",
                session_key="openwebui:test",
                event_emitter=emitter,
                event_call=None,
            )
        ]
        content = visible_content(chunks)
        assert "Hermesエラー:" in content
        assert fake.stops == ["run_test"]
        statuses = status_data(emitted)
        assert statuses[-1]["description"] == "失敗"
        assert statuses[-1]["done"] is True
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_explicit_run_timeout_is_a_neutral_stop_not_a_failure():
    fake = await FakeHermes(
        [{"event": "run.completed", "output": "too late"}],
        event_delay=1.2,
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        # Production configuration uses integer seconds.  One second keeps this
        # integration regression test fast while exercising aiohttp's deadline.
        pipe.valves.RUN_TIMEOUT_SECONDS = 1
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="test timeout",
                history=[],
                instructions=None,
                session_id="owui_test",
                session_key="openwebui:test",
                event_emitter=emitter,
                event_call=None,
            )
        ]

        content = visible_content(chunks)
        assert "Hermesエラー" not in content
        assert "実行時間の上限" in content
        assert fake.stops == ["run_test"]
        statuses = status_data(emitted)
        assert statuses[-1]["description"] == "時間上限で停止"
        assert statuses[-1]["done"] is True
        assert statuses[-1]["error"] is False
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_completed_openwebui_chat_publishes_one_content_free_ntfy_notification():
    hermes = await FakeHermes(
        [
            {"event": "message.delta", "delta": "sensitive response"},
            {"event": "run.completed", "output": "sensitive response"},
        ]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="sensitive user message",
                history=[],
                instructions=None,
                session_id="owui_0123456789abcdef0123456789abcdef",
                session_key="openwebui:test",
                event_emitter=None,
                event_call=None,
            )
        ]

        assert visible_content(chunks) == "sensitive response"
        assert chunks[-1] == "data: [DONE]\n\n"
        assert await wait_for_message_count(ntfy, 1) == 1
        notification = ntfy.messages[0]
        assert notification["topic"] == "pda-chat-0123456789abcdef"
        assert notification["body"] == "Open WebUIでPDAの応答が完了しました。"
        assert notification["headers"]["Title"] == "PDA"
        assert notification["headers"]["Priority"] == "default"
        assert notification["headers"]["Tags"] == "white_check_mark,robot_face"
        assert notification["headers"]["Click"] == "https://pda-web.example.ts.net"
        assert "sensitive" not in json.dumps(notification, ensure_ascii=False)
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_non_openwebui_async_run_does_not_publish_completion_notification():
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "background result"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="background work",
                history=[],
                instructions=None,
                session_id="api-0123456789abcdef",
                session_key="api:background",
                event_emitter=None,
                event_call=None,
            )
        ]

        assert visible_content(chunks) == "background result"
        assert ntfy.messages == []
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_done_terminating_consumer_still_gets_completion_notification():
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "done"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        stream = pipe._stream_response(
            message="interactive chat",
            history=[],
            instructions=None,
            session_id="owui_0123456789abcdef0123456789abcdef",
            session_key="openwebui:test",
            event_emitter=None,
            event_call=None,
        )
        async for chunk in stream:
            if chunk == "data: [DONE]\n\n":
                break
        await stream.aclose()

        assert await wait_for_message_count(ntfy, 1) == 1
    finally:
        await ntfy.close()
        await hermes.close()
