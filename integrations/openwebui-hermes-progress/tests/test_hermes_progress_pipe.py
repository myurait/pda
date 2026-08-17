import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

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
    pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
    pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"
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
async def test_notification_completion_lookup_is_scoped_to_authenticated_owner(monkeypatch):
    requested = []

    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id, user_id):
            requested.append(("chat", chat_id, user_id))
            if user_id == "owner-user":
                return SimpleNamespace(title="所有者だけのタイトル")
            return None

        @staticmethod
        async def get_message_by_id_and_message_id(chat_id, message_id):
            requested.append(("message", chat_id, message_id))
            return {
                "role": "assistant",
                "done": True,
                "content": "所有者の保存済み回答",
            }

    monkeypatch.setattr(
        module.importlib,
        "import_module",
        lambda name: SimpleNamespace(Chats=FakeChats),
    )

    pipe = Pipe()
    assert await pipe._load_openwebui_completion(
        "saved-chat", "assistant-message", "owner-user"
    ) == ("所有者だけのタイトル", True, "所有者の保存済み回答")
    assert await pipe._load_openwebui_completion(
        "saved-chat", "assistant-message", "other-user"
    ) is None
    assert requested == [
        ("chat", "saved-chat", "owner-user"),
        ("message", "saved-chat", "assistant-message"),
        ("chat", "saved-chat", "other-user"),
    ]


@pytest.mark.asyncio
async def test_unowned_chat_has_no_exportable_persisted_completion(monkeypatch):
    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(_chat_id, _user_id):
            return None

    monkeypatch.setattr(
        module.importlib,
        "import_module",
        lambda name: SimpleNamespace(Chats=FakeChats),
    )
    pipe = Pipe()
    assert await pipe._await_openwebui_completion(
        "other-users-chat", "assistant-message", "authenticated-user"
    ) is None


@pytest.mark.asyncio
async def test_completion_notification_is_limited_to_configured_user():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def persisted(_chat_id, _message_id, _user_id):
            return "所有者のチャット", "回答"

        pipe._await_openwebui_completion = persisted
        common = {
            "session_id": "owui_0123456789abcdef0123456789abcdef",
            "chat_id": "2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            "message_id": "assistant-message-owner-check",
        }

        await pipe._publish_completion_notification(
            **common,
            user_id="other-user",
        )
        await pipe._publish_completion_notification(
            **common,
            user_id="owner-user",
        )

        assert len(ntfy.messages) == 1
        assert ntfy.messages[0]["headers"]["Title"] == "所有者のチャット"
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_completion_notification_waits_for_openwebui_host_task_before_export():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"
        persisted_answer = {"value": "フィルター適用前の回答"}

        async def finish_openwebui_postprocessing():
            await asyncio.sleep(0)
            persisted_answer["value"] = "フィルター適用後の回答"

        host_task = asyncio.create_task(finish_openwebui_postprocessing())

        async def persisted(_chat_id, _message_id, _user_id):
            assert host_task.done()
            return "保存後のタイトル", persisted_answer["value"]

        pipe._await_openwebui_completion = persisted
        await pipe._publish_completion_notification(
            "owui_0123456789abcdef0123456789abcdef",
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-post-outlet",
            host_task=host_task,
        )

        assert len(ntfy.messages) == 1
        assert ntfy.messages[0]["body"] == "フィルター適用後の回答"
        assert "フィルター適用前" not in json.dumps(
            ntfy.messages[0], ensure_ascii=False
        )
    finally:
        await ntfy.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("host_outcome", ["cancelled", "failed"])
async def test_finished_openwebui_host_task_outcome_does_not_override_persisted_done(
    host_outcome,
):
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"
        persisted_called = False

        async def finished_host():
            if host_outcome == "cancelled":
                raise asyncio.CancelledError
            raise RuntimeError("outlet failed after the response was saved")

        host_task = asyncio.create_task(finished_host())

        async def persisted(_chat_id, _message_id, _user_id):
            nonlocal persisted_called
            persisted_called = True
            return "保存済み応答", "host終了後もDB上でdoneの回答"

        pipe._await_openwebui_completion = persisted
        await pipe._publish_completion_notification(
            "owui_0123456789abcdef0123456789abcdef",
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-finished-host",
            host_task=host_task,
        )

        assert persisted_called is True
        assert len(ntfy.messages) == 1
        assert ntfy.messages[0]["body"] == "host終了後もDB上でdoneの回答"
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_completion_notification_requires_valid_chat_link():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = ""

        await pipe._publish_completion_notification(
            "owui_0123456789abcdef0123456789abcdef",
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-link-check",
        )

        assert ntfy.messages == []
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_notification_waits_for_generated_openwebui_topic(monkeypatch):
    pipe = Pipe()
    loaded_titles = iter(["New Chat", "新しいチャット", "  PDA通知の改善  "])
    requested = []

    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id, user_id):
            requested.append(("chat", chat_id, user_id))
            return SimpleNamespace(title=next(loaded_titles))

        @staticmethod
        async def get_message_by_id_and_message_id(chat_id, message_id):
            requested.append(("message", chat_id, message_id))
            return {"role": "assistant", "done": True, "content": "回答"}

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(
        module.importlib,
        "import_module",
        lambda name: SimpleNamespace(Chats=FakeChats),
    )
    monkeypatch.setattr(module.asyncio, "sleep", no_delay)

    result = await pipe._await_openwebui_completion(
        "2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
        "assistant-message-title",
        "owner-user",
    )

    assert result == ("PDA通知の改善", "回答")
    assert len(requested) == 6


@pytest.mark.asyncio
async def test_completed_openwebui_chat_publishes_chat_title_and_answer_preview():
    answer = "結論です。\n\n次はPKB取り込み経路を整備します。"
    hermes = await FakeHermes(
        [
            {"event": "message.delta", "delta": answer},
            {"event": "run.completed", "output": answer},
        ]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def persisted(chat_id, message_id, user_id):
            assert chat_id == "2b7e1516-28ae-4d2a-abf7-158809cf4f3c"
            assert message_id == "assistant-message-stream"
            assert user_id == "owner-user"
            return "PDAの次工程", answer

        pipe._await_openwebui_completion = persisted

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="次の作業を相談する",
                history=[],
                instructions=None,
                session_id="owui_0123456789abcdef0123456789abcdef",
                session_key="openwebui:test",
                event_emitter=lambda event: None,
                event_call=None,
                chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
                user_id="owner-user",
                message_id="assistant-message-stream",
                ui_context=True,
            )
        ]

        assert visible_content(chunks) == answer
        assert chunks[-1] == "data: [DONE]\n\n"
        assert await wait_for_message_count(ntfy, 1) == 1
        notification = ntfy.messages[0]
        assert notification["topic"] == "pda-chat-0123456789abcdef"
        assert notification["body"] == "結論です。 次はPKB取り込み経路を整備します。"
        assert notification["headers"]["Title"] == "PDAの次工程"
        assert notification["headers"]["Priority"] == "default"
        assert "Tags" not in notification["headers"]
        assert notification["headers"]["Click"] == (
            "https://pda-web.example.ts.net/c/2b7e1516-28ae-4d2a-abf7-158809cf4f3c"
        )
        assert "Open WebUIでPDAの応答が完了しました" not in notification["body"]
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_completed_non_streaming_openwebui_chat_also_publishes_preview():
    answer = "非ストリーミングでも回答の冒頭を通知します。"
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": answer}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        async def persisted(_chat_id, message_id, _user_id):
            assert message_id == "assistant-message-blocking"
            return "非ストリーミングの話題", answer

        pipe._await_openwebui_completion = persisted

        response = await pipe._blocking_response(
            message="非ストリーミングで応答して",
            history=[],
            instructions=None,
            session_id="owui_0123456789abcdef0123456789abcdef",
            session_key="openwebui:test",
            event_emitter=None,
            event_call=None,
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-blocking",
            ui_context=True,
        )

        assert response["choices"][0]["message"]["content"] == answer
        assert await wait_for_message_count(ntfy, 1) == 1
        assert ntfy.messages[0]["headers"]["Title"] == "非ストリーミングの話題"
        assert ntfy.messages[0]["body"] == answer
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("terminal_event", "saved_answer"),
    [
        ({"event": "run.failed", "error": "provider failed"}, "Hermesエラー: provider failed"),
        ({"event": "run.cancelled"}, "Hermesの実行はキャンセルされました。"),
        ({"event": "adapter.timeout", "timeout_seconds": 60}, "Hermesの実行時間の上限に達したため停止しました。"),
    ],
)
async def test_user_visible_terminal_outcomes_publish_persisted_completion_preview(
    terminal_event, saved_answer
):
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def run_events(**_kwargs):
            yield terminal_event

        async def persisted(_chat_id, _message_id, _user_id):
            return "完了結果", saved_answer

        pipe._run_events = run_events
        pipe._await_openwebui_completion = persisted
        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="ユーザーチャット",
                history=[],
                instructions=None,
                session_id="owui_0123456789abcdef0123456789abcdef",
                session_key="openwebui:test",
                event_emitter=None,
                event_call=None,
                chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
                user_id="owner-user",
                message_id=f"assistant-message-{terminal_event['event'].replace('.', '-')}",
                ui_context=True,
            )
        ]

        assert chunks[-1] == "data: [DONE]\n\n"
        assert await wait_for_message_count(ntfy, 1) == 1
        assert ntfy.messages[0]["body"] == saved_answer
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_non_streaming_failed_user_chat_publishes_persisted_completion_preview():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def run_events(**_kwargs):
            yield {"event": "run.failed", "error": "provider failed"}

        async def persisted(_chat_id, _message_id, _user_id):
            return "失敗結果", "Hermesエラー: provider failed"

        pipe._run_events = run_events
        pipe._await_openwebui_completion = persisted
        response = await pipe._blocking_response(
            message="ユーザーチャット",
            history=[],
            instructions=None,
            session_id="owui_0123456789abcdef0123456789abcdef",
            session_key="openwebui:test",
            event_emitter=None,
            event_call=None,
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-blocking-failure",
            ui_context=True,
        )

        assert response["choices"][0]["message"]["content"] == "Hermesエラー: provider failed"
        assert await wait_for_message_count(ntfy, 1) == 1
        assert ntfy.messages[0]["body"] == "Hermesエラー: provider failed"
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_non_streaming_title_tag_and_follow_up_tasks_do_not_add_pushes():
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "task result"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        chat_id = "2b7e1516-28ae-4d2a-abf7-158809cf4f3c"

        async def persisted(_chat_id, _message_id, _user_id):
            return "対話チャット", "task result"

        async def emitter(_event):
            return None

        pipe._await_openwebui_completion = persisted
        host_task = asyncio.create_task(asyncio.sleep(0))
        await host_task
        pipe._current_openwebui_host_task = lambda: host_task

        await pipe.pipe(
            {
                "messages": [{"role": "user", "content": "interactive turn"}],
                "stream": False,
            },
            __user__={"id": "owner-user"},
            __chat_id__=chat_id,
            __session_id__="browser-session",
            __message_id__="interactive-assistant-message",
            __event_emitter__=emitter,
            __metadata__={
                "chat_id": chat_id,
                "internal": False,
                "task_id": "openwebui-host-task",
            },
        )
        assert await wait_for_message_count(ntfy, 1) == 1

        for task in ("title_generation", "tags_generation", "follow_up_generation"):
            await pipe.pipe(
                {
                    "messages": [{"role": "user", "content": f"run {task}"}],
                    "stream": False,
                },
                __user__={"id": "owner-user"},
                __chat_id__=chat_id,
                __session_id__=f"task-session-{task}",
                __message_id__=f"task-assistant-{task}",
                __event_emitter__=emitter,
                __metadata__={
                    "chat_id": chat_id,
                    "internal": False,
                    "task": task,
                },
                __request__=SimpleNamespace(
                    url=SimpleNamespace(path="/api/chat/completions"),
                    scope={"path": "/api/chat/completions"},
                ),
            )

        await wait_for_message_count(ntfy, 4, timeout=0.4)
        assert len(ntfy.messages) == 1
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_openwebui_internal_invocation_does_not_publish_completion_notification():
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "internal result"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        response = await pipe.pipe(
            {
                "messages": [{"role": "user", "content": "internal work"}],
                "stream": False,
            },
            __user__={"id": "owner-user"},
            __chat_id__="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            __metadata__={
                "chat_id": "2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
                "internal": True,
            },
        )

        assert response["choices"][0]["message"]["content"] == "internal result"
        assert await wait_for_message_count(ntfy, 1, timeout=0.2) == 0
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "request_path",
    [
        "/api/v1/automations/internal",
        "/api/v1/timers/internal",
        "/api/v1/subagents/internal",
    ],
)
async def test_openwebui_backend_completion_paths_do_not_publish(request_path):
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "background result"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        async def persisted(_chat_id, _message_id, _user_id):
            return "バックエンド処理", "background result"

        async def emitter(_event):
            return None

        pipe._await_openwebui_completion = persisted
        host_task = asyncio.create_task(asyncio.sleep(0))
        await host_task
        pipe._current_openwebui_host_task = lambda: host_task

        await pipe.pipe(
            {
                "messages": [{"role": "user", "content": "background work"}],
                "stream": False,
            },
            __user__={"id": "owner-user"},
            __chat_id__="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            __session_id__="backend-session",
            __message_id__="backend-assistant-message",
            __event_emitter__=emitter,
            __metadata__={"internal": False},
            __request__=SimpleNamespace(
                url=SimpleNamespace(path=request_path),
                scope={"path": request_path},
            ),
        )

        assert await wait_for_message_count(ntfy, 1, timeout=0.2) == 0
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_nested_internal_user_message_metadata_does_not_publish():
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "internal result"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        async def persisted(_chat_id, _message_id, _user_id):
            return "内部継続", "internal result"

        async def emitter(_event):
            return None

        pipe._await_openwebui_completion = persisted
        host_task = asyncio.create_task(asyncio.sleep(0))
        await host_task
        pipe._current_openwebui_host_task = lambda: host_task

        await pipe.pipe(
            {
                "messages": [{"role": "user", "content": "internal work"}],
                "stream": False,
            },
            __user__={"id": "owner-user"},
            __chat_id__="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            __session_id__="internal-session",
            __message_id__="internal-assistant-message",
            __event_emitter__=emitter,
            __metadata__={
                "internal": False,
                "user_message": {"meta": {"internal": True}},
            },
            __request__=SimpleNamespace(
                url=SimpleNamespace(path="/api/chat/completions"),
                scope={"path": "/api/chat/completions"},
            ),
        )

        assert await wait_for_message_count(ntfy, 1, timeout=0.2) == 0
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_stream_cancellation_still_checks_persisted_done_response():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def cancelled_events(**_kwargs):
            yield {"event": "message.delta", "delta": "部分回答"}
            raise asyncio.CancelledError

        async def cancelled_host():
            raise asyncio.CancelledError

        async def persisted(_chat_id, _message_id, _user_id):
            return "キャンセル済み応答", "部分回答"

        host_task = asyncio.create_task(cancelled_host())
        pipe._run_events = cancelled_events
        pipe._await_openwebui_completion = persisted
        stream = pipe._stream_response(
            message="途中で停止",
            history=[],
            instructions=None,
            session_id="owui_0123456789abcdef0123456789abcdef",
            session_key="openwebui:test",
            event_emitter=None,
            event_call=None,
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-cancelled-stream",
            host_task=host_task,
            ui_context=True,
        )

        with pytest.raises(asyncio.CancelledError):
            async for _chunk in stream:
                pass

        assert await wait_for_message_count(ntfy, 1) == 1
        assert ntfy.messages[0]["body"] == "部分回答"
    finally:
        await ntfy.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_after_chunk", ["final_content", "stop"])
async def test_stream_close_after_terminal_chunks_still_checks_persisted_done(
    close_after_chunk,
):
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def completed_events(**_kwargs):
            yield {"event": "run.completed", "output": "最終回答"}

        async def persisted(_chat_id, _message_id, _user_id):
            return "途中close", "最終回答"

        host_task = asyncio.create_task(asyncio.sleep(0))
        await host_task
        pipe._run_events = completed_events
        pipe._await_openwebui_completion = persisted
        stream = pipe._stream_response(
            message="完了直後にclose",
            history=[],
            instructions=None,
            session_id="owui_0123456789abcdef0123456789abcdef",
            session_key="openwebui:test",
            event_emitter=None,
            event_call=None,
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id=f"assistant-message-close-{close_after_chunk}",
            host_task=host_task,
            ui_context=True,
        )

        role_chunk = await anext(stream)
        assert '"role": "assistant"' in role_chunk
        final_content = await anext(stream)
        assert "最終回答" in final_content
        if close_after_chunk == "stop":
            stop_chunk = await anext(stream)
            assert '"finish_reason": "stop"' in stop_chunk
        await stream.aclose()

        assert await wait_for_message_count(ntfy, 1) == 1
        assert ntfy.messages[0]["body"] == "最終回答"
    finally:
        await ntfy.close()


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

        async def persisted(_chat_id, _message_id, _user_id):
            return "通知保持テスト", "done"

        pipe._await_openwebui_completion = persisted

        stream = pipe._stream_response(
            message="interactive chat",
            history=[],
            instructions=None,
            session_id="owui_0123456789abcdef0123456789abcdef",
            session_key="openwebui:test",
            event_emitter=None,
            event_call=None,
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-close",
            ui_context=True,
        )
        async for chunk in stream:
            if chunk == "data: [DONE]\n\n":
                break
        await stream.aclose()

        assert await wait_for_message_count(ntfy, 1) == 1
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_direct_api_call_without_ui_message_context_does_not_publish():
    hermes = await FakeHermes(
        [{"event": "run.completed", "output": "direct result"}]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        await pipe.pipe(
            {
                "messages": [{"role": "user", "content": "direct API"}],
                "stream": False,
            },
            __user__={"id": "owner-user"},
            __chat_id__="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            # A direct API caller may supply a real owned chat ID, but does not
            # have the frontend's session/message/event-emitter context.
            __metadata__={"chat_id": "2b7e1516-28ae-4d2a-abf7-158809cf4f3c"},
        )

        await wait_for_message_count(ntfy, 1, timeout=0.2)
        assert ntfy.messages == []
    finally:
        await ntfy.close()
        await hermes.close()


@pytest.mark.asyncio
async def test_duplicate_completion_for_same_ui_message_publishes_once():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def persisted(_chat_id, _message_id, _user_id):
            return "重複抑止", "一度だけ送る"

        pipe._await_openwebui_completion = persisted
        kwargs = {
            "session_id": "owui_0123456789abcdef0123456789abcdef",
            "chat_id": "2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            "user_id": "owner-user",
            "message_id": "assistant-message-1",
            "ui_context": True,
        }
        pipe._schedule_completion_notification(**kwargs)
        pipe._schedule_completion_notification(**kwargs)

        assert await wait_for_message_count(ntfy, 2, timeout=0.5) == 1
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_untitled_owned_chat_never_exports_prompt_as_notification_title(monkeypatch):
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def persisted(_chat_id, _message_id, _user_id):
            return "New Chat", "回答"

        pipe._await_openwebui_completion = persisted
        await pipe._publish_completion_notification(
            "owui_0123456789abcdef0123456789abcdef",
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-untitled",
        )

        assert len(ntfy.messages) == 1
        assert ntfy.messages[0]["headers"]["Title"] == "New Chat"
        assert "ユーザー入力" not in json.dumps(ntfy.messages[0], ensure_ascii=False)
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_empty_persisted_answer_does_not_publish_placeholder_preview():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        async def persisted(_chat_id, _message_id, _user_id):
            return "空回答", " \n\t "

        pipe._await_openwebui_completion = persisted
        await pipe._publish_completion_notification(
            "owui_0123456789abcdef0123456789abcdef",
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
            message_id="assistant-message-empty-answer",
        )

        assert ntfy.messages == []
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_external_plain_http_ntfy_destination_is_rejected(monkeypatch):
    pipe = Pipe()
    pipe.valves.NTFY_SERVER_URL = "http://notify.example.com"
    pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
    pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
    pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"
    opened = []

    class ForbiddenSession:
        def __init__(self, *args, **kwargs):
            opened.append((args, kwargs))
            raise AssertionError("plain HTTP destination must be rejected before network I/O")

    monkeypatch.setattr(module.aiohttp, "ClientSession", ForbiddenSession)

    await pipe._publish_completion_notification(
        "owui_0123456789abcdef0123456789abcdef",
        chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
        user_id="owner-user",
        message_id="assistant-message-http",
    )
    assert opened == []


@pytest.mark.asyncio
async def test_malformed_runtime_notification_urls_fail_closed_without_raising():
    pipe = Pipe()
    pipe.valves.NTFY_SERVER_URL = "https://ntfy.sh"
    pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
    pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
    pipe.valves.OPENWEBUI_PUBLIC_URL = "https://[broken"

    await pipe._publish_completion_notification(
        "owui_0123456789abcdef0123456789abcdef",
        chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
        user_id="owner-user",
        message_id="assistant-message-malformed-url",
    )


@pytest.mark.parametrize(
    "value",
    [
        "https://exa mple.com",
        "https://example.com\x7f",
        "https://example.com\\evil",
        "https://%65xample.com",
        "https://-bad.example",
        "https://bad-.example",
        "https://exa_mple.com",
        "https://example.com:99999",
    ],
)
def test_runtime_notification_url_validator_rejects_malformed_hosts(value):
    assert Pipe._validated_notification_url(value) is None


@pytest.mark.asyncio
async def test_notification_sink_requires_persisted_assistant_message_id():
    ntfy = await FakeNtfy().start()
    try:
        pipe = Pipe()
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"
        pipe.valves.NTFY_ALLOWED_USER_ID = "owner-user"
        pipe.valves.OPENWEBUI_PUBLIC_URL = "https://pda-web.example.ts.net"

        await pipe._publish_completion_notification(
            "owui_0123456789abcdef0123456789abcdef",
            chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
            user_id="owner-user",
        )

        await wait_for_message_count(ntfy, 1, timeout=0.2)
        assert ntfy.messages == []
    finally:
        await ntfy.close()


@pytest.mark.asyncio
async def test_notification_waits_for_persisted_owned_assistant_answer(monkeypatch):
    pipe = Pipe()
    calls = []
    messages = iter(
        [
            {
                "role": "assistant",
                "done": False,
                "content": "",
                "output": [],
            },
            {
                "role": "assistant",
                "done": True,
                "content": "",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "DBへ保存された最終回答",
                            }
                        ],
                    }
                ],
            },
        ]
    )

    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id, user_id):
            calls.append(("chat", chat_id, user_id))
            return SimpleNamespace(title="保存済みトピック")

        @staticmethod
        async def get_message_by_id_and_message_id(chat_id, message_id):
            calls.append(("message", chat_id, message_id))
            return next(messages)

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(
        module.importlib,
        "import_module",
        lambda name: SimpleNamespace(Chats=FakeChats),
    )
    monkeypatch.setattr(module.asyncio, "sleep", no_delay)

    result = await pipe._await_openwebui_completion(
        "2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
        "assistant-message-1",
        "owner-user",
    )

    assert result == ("保存済みトピック", "DBへ保存された最終回答")
    assert calls == [
        ("chat", "2b7e1516-28ae-4d2a-abf7-158809cf4f3c", "owner-user"),
        ("message", "2b7e1516-28ae-4d2a-abf7-158809cf4f3c", "assistant-message-1"),
        ("chat", "2b7e1516-28ae-4d2a-abf7-158809cf4f3c", "owner-user"),
        ("message", "2b7e1516-28ae-4d2a-abf7-158809cf4f3c", "assistant-message-1"),
    ]


@pytest.mark.asyncio
async def test_stream_notification_uses_persisted_answer_when_terminal_output_differs():
    answer_streamed = "画面に保存される回答"
    answer_terminal = "異なるterminal output"
    answer_persisted = "画面に保存された回答"
    hermes = await FakeHermes(
        [
            {"event": "message.delta", "delta": answer_streamed},
            {"event": "run.completed", "output": answer_terminal},
        ]
    ).start()
    ntfy = await FakeNtfy().start()
    try:
        pipe = configured_pipe(hermes.base_url)
        pipe.valves.NTFY_SERVER_URL = ntfy.base_url
        pipe.valves.NTFY_TOPIC = "pda-chat-0123456789abcdef"

        async def persisted(_chat_id, _message_id, _user_id):
            return "保存済みタイトル", answer_persisted

        async def emitter(_event):
            return None

        pipe._await_openwebui_completion = persisted
        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="質問",
                history=[],
                instructions=None,
                session_id="owui_0123456789abcdef0123456789abcdef",
                session_key="openwebui:test",
                event_emitter=emitter,
                event_call=None,
                chat_id="2b7e1516-28ae-4d2a-abf7-158809cf4f3c",
                user_id="owner-user",
                message_id="assistant-message-1",
                ui_context=True,
            )
        ]

        assert visible_content(chunks) == answer_streamed
        assert await wait_for_message_count(ntfy, 1) == 1
        assert ntfy.messages[0]["headers"]["Title"] == "保存済みタイトル"
        assert ntfy.messages[0]["body"] == answer_persisted
        serialized = json.dumps(ntfy.messages[0], ensure_ascii=False)
        assert answer_terminal not in serialized
        assert "外へ出さない質問" not in serialized
    finally:
        await ntfy.close()
        await hermes.close()
