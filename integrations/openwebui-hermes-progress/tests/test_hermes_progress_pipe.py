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
        event_delay: float = 0,
        event_delays=None,
        approval_status=200,
        approval_error_code="approval_not_active",
    ):
        self.events = events
        self.event_delay = event_delay
        self.event_delays = list(event_delays or [])
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
        for index, event in enumerate(self.events):
            if index < len(self.event_delays) and self.event_delays[index]:
                await asyncio.sleep(self.event_delays[index])
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


def test_progress_heartbeat_defaults_to_five_minutes_without_tool_log_noise():
    valves = Pipe.Valves()
    schema = valves.model_json_schema()["properties"]["PROGRESS_HEARTBEAT_SECONDS"]
    stall_schema = valves.model_json_schema()["properties"]["PROGRESS_STALL_SECONDS"]

    assert valves.PROGRESS_HEARTBEAT_SECONDS == 300
    assert valves.PROGRESS_STALL_SECONDS == 600
    assert valves.SHOW_TOOL_ACTIVITY is False
    assert valves.SHOW_REASONING_STATUS is False
    assert schema["minimum"] == 0
    assert stall_schema["minimum"] == 0

    disabled = Pipe.Valves(PROGRESS_HEARTBEAT_SECONDS=0, PROGRESS_STALL_SECONDS=0)
    assert disabled.PROGRESS_HEARTBEAT_SECONDS == 0
    assert disabled.PROGRESS_STALL_SECONDS == 0


def test_runs_events_update_progress_state_without_scheduling_a_display():
    pipe = Pipe()
    progress = pipe._initial_progress_state(started_at=1000.0)

    for event in (
        {"event": "tool.started", "tool": "read_file"},
        {"event": "tool.completed", "tool": "read_file", "error": False},
        {"event": "tool.started", "tool": "write_file"},
    ):
        assert pipe._track_progress_event(progress, event, observed_at=1001.0)

    assert progress["last_report_at"] is None
    assert progress["real_event_count"] == 3
    assert pipe._progress_snapshot(progress)["current"] == "実装・文書を更新中"

    pipe._heartbeat_description(elapsed_seconds=1, progress=progress, now=1001.0)

    assert progress["last_report_at"] == 1001.0
    assert progress["last_report_event_count"] == 3


def test_progress_heartbeat_reports_plan_milestone_and_current_work():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "investigate",
                    "content": "通知の発生源を特定",
                    "status": "completed",
                },
                {
                    "id": "outline",
                    "content": "設計の大枠を確定",
                    "status": "completed",
                },
                {
                    "id": "integration",
                    "content": "外部システムとの疎通条件を追加調査中",
                    "status": "in_progress",
                },
                {
                    "id": "verify",
                    "content": "実環境で通知を検証",
                    "status": "pending",
                },
            ],
        },
    )

    description = pipe._heartbeat_description(
        elapsed_seconds=300,
        progress=progress,
    )

    assert description.startswith(
        "[5分経過] 処理中 (50%) - "
        "完了: 設計の大枠を確定。"
        "現在: 外部システムとの疎通条件を追加調査中。"
    )
    assert "\n段階: 外部システムとの疎通条件を追加調査中" in description
    assert "\n変化: 進捗率 初回50%／段階 初回／表示文 初回" in description
    assert "\n最終実進展:" in description
    assert "ツール" not in description


def test_progress_without_plan_reports_event_based_current_work_and_result():
    pipe = Pipe()
    progress = pipe._initial_progress_state()

    pipe._track_progress_event(
        progress,
        {
            "event": "tool.started",
            "tool": "read_file",
            "preview": "PRIVATE_PATH_MUST_NOT_APPEAR",
        },
    )
    active = pipe._heartbeat_description(elapsed_seconds=30, progress=progress)

    assert "作業計画が未登録" not in active
    assert "現在: 対象ファイルの内容を確認中。" in active
    assert "PRIVATE_PATH_MUST_NOT_APPEAR" not in active

    pipe._track_progress_event(
        progress,
        {
            "event": "tool.completed",
            "tool": "read_file",
            "error": False,
            "result": "PRIVATE_RESULT_MUST_NOT_APPEAR",
        },
    )
    completed = pipe._heartbeat_description(elapsed_seconds=45, progress=progress)

    assert "作業計画が未登録" not in completed
    assert "直近結果: 対象ファイルの確認を完了。" in completed
    assert "PRIVATE_RESULT_MUST_NOT_APPEAR" not in completed


@pytest.mark.parametrize(
    ("tool", "current_work", "completed_result"),
    [
        ("search_files", "関連コード・記録を検索中", "関連コード・記録の検索を完了"),
        ("terminal", "コマンドで実装・検証中", "コマンド実行を完了"),
        ("patch", "実装・文書を更新中", "実装・文書の更新を完了"),
        ("web_search", "公開情報を調査中", "公開情報の調査を完了"),
        ("computer_use", "画面上の対象を操作・確認中", "画面上の操作・確認を完了"),
        ("todo", "作業段階を更新中", "作業段階の更新を完了"),
        ("delegate_task", "並行作業を実行中", "並行作業を完了"),
        ("kanban_comment", "作業記録を更新中", "作業記録の更新を完了"),
    ],
)
def test_event_based_progress_maps_tools_to_owner_readable_work(
    tool, current_work, completed_result
):
    pipe = Pipe()
    progress = pipe._initial_progress_state()

    pipe._track_progress_event(progress, {"event": "tool.started", "tool": tool})
    active = pipe._progress_snapshot(progress)
    pipe._track_progress_event(
        progress,
        {"event": "tool.completed", "tool": tool, "error": False},
    )
    completed = pipe._progress_snapshot(progress)

    assert active["current"] == current_work
    assert completed["recent_result"] == completed_result


def test_completed_tool_result_does_not_fall_back_to_instruction_like_plan_as_current_work():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    instruction_like_stage = "依頼された画面改善を実施する"
    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "implement",
                    "content": instruction_like_stage,
                    "status": "in_progress",
                }
            ],
        },
    )
    pipe._track_progress_event(
        progress,
        {"event": "tool.started", "tool": "search_files"},
    )
    pipe._track_progress_event(
        progress,
        {"event": "tool.completed", "tool": "search_files", "error": False},
    )

    snapshot = pipe._progress_snapshot(progress)

    assert snapshot["stage"] == instruction_like_stage
    assert snapshot["current"] == "次の処理を判断中"
    assert snapshot["recent_result"] == "関連コード・記録の検索を完了"


@pytest.mark.asyncio
async def test_progress_status_preserves_full_multiline_description_without_ellipsis():
    pipe = Pipe()
    emitted = []
    description = "現在: " + ("具体的な確認作業" * 200) + "\n直近結果: 検証を完了。"

    async def emitter(event):
        emitted.append(event)

    await pipe._emit_status(emitter, description, done=False, heartbeat=True)

    assert emitted[0]["data"]["description"] == description
    assert "…" not in emitted[0]["data"]["description"]


def test_progress_plan_preserves_full_multiline_text_beyond_old_display_limit():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    long_content = ("狭い画面でも省略せず読める具体的な作業内容。" * 40) + "\n第二段落も保持する。"

    accepted = pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "long-current-work",
                    "content": long_content,
                    "status": "in_progress",
                }
            ],
        },
    )
    description = pipe._heartbeat_description(
        elapsed_seconds=300,
        progress=progress,
    )

    assert accepted is True
    assert long_content in description
    assert "…" not in description


def test_progress_delta_and_stall_use_last_real_event_not_repeated_heartbeat():
    pipe = Pipe()
    progress = pipe._initial_progress_state(started_at=1_000.0)
    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "timestamp": 1_000.0,
            "items": [
                {
                    "id": "verify",
                    "content": "対象環境で表示を検証中",
                    "status": "in_progress",
                }
            ],
        },
        observed_at=1_000.0,
    )

    first = pipe._heartbeat_description(
        elapsed_seconds=300,
        progress=progress,
        now=1_300.0,
        stall_seconds=600,
    )
    unchanged_busy = pipe._heartbeat_description(
        elapsed_seconds=599,
        progress=progress,
        now=1_599.0,
        stall_seconds=600,
    )
    stalled = pipe._heartbeat_description(
        elapsed_seconds=600,
        progress=progress,
        now=1_600.0,
        stall_seconds=600,
    )

    assert "状態: 実行中" in first
    assert "前回表示: 初回" in first
    assert "実作業イベント +1" in first
    assert "状態: 実行中" in unchanged_busy
    assert "進捗率 ±0pt" in unchanged_busy
    assert "段階 同一" in unchanged_busy
    assert "表示文 同一" in unchanged_busy
    assert "実作業イベント +0" in unchanged_busy
    assert "状態: 停滞" in stalled
    assert "最終実進展:" in stalled
    assert "（10分前）" in stalled

    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "timestamp": 1_700.0,
            "items": [
                {
                    "id": "verify",
                    "content": "対象環境で表示を検証中",
                    "status": "completed",
                }
            ],
        },
        observed_at=1_700.0,
    )
    advanced = pipe._heartbeat_description(
        elapsed_seconds=700,
        progress=progress,
        now=1_700.0,
        stall_seconds=600,
    )

    assert "状態: 実行中" in advanced
    assert "進捗率 +100pt" in advanced
    assert "段階 変更" in advanced
    assert "表示文 変更" in advanced
    assert "実作業イベント +1" in advanced

    pipe._track_progress_event(
        progress,
        {"event": "tool.started", "tool": "terminal", "timestamp": 2_200.0},
        observed_at=2_200.0,
    )
    pipe._heartbeat_description(
        elapsed_seconds=1_200,
        progress=progress,
        now=2_200.0,
        stall_seconds=600,
    )
    pipe._track_progress_event(
        progress,
        {"event": "tool.started", "tool": "terminal", "timestamp": 2_700.0},
        observed_at=2_700.0,
    )
    same_text_real_work = pipe._heartbeat_description(
        elapsed_seconds=1_800,
        progress=progress,
        now=2_800.0,
        stall_seconds=600,
    )

    assert "状態: 実行中" in same_text_real_work
    assert "進捗率 ±0pt" in same_text_real_work
    assert "段階 同一" in same_text_real_work
    assert "表示文 同一" in same_text_real_work
    assert "実作業イベント +1" in same_text_real_work


def test_identical_plan_event_counts_as_real_work_and_clears_stall():
    pipe = Pipe()
    progress = pipe._initial_progress_state(started_at=1_000.0)
    event = {
        "event": "plan.updated",
        "timestamp": 1_000.0,
        "items": [
            {
                "id": "verify",
                "content": "同じ段階で検証を継続中",
                "status": "in_progress",
            }
        ],
    }
    pipe._track_progress_event(progress, event, observed_at=1_000.0)
    pipe._heartbeat_description(
        elapsed_seconds=600,
        progress=progress,
        now=1_600.0,
        stall_seconds=600,
    )

    repeated = pipe._track_progress_event(
        progress,
        event,
        observed_at=1_700.0,
    )
    description = pipe._heartbeat_description(
        elapsed_seconds=701,
        progress=progress,
        now=1_701.0,
        stall_seconds=600,
    )

    assert repeated is True
    assert "状態: 実行中" in description
    assert "進捗率 ±0pt" in description
    assert "段階 同一" in description
    assert "表示文 同一" in description
    assert "実作業イベント +1" in description


def test_delayed_event_uses_observation_time_to_clear_stall():
    pipe = Pipe()
    progress = pipe._initial_progress_state(started_at=1_000.0)
    pipe._track_progress_event(
        progress,
        {"event": "tool.started", "tool": "terminal", "timestamp": 1_000.0},
        observed_at=1_000.0,
    )
    pipe._heartbeat_description(
        elapsed_seconds=600,
        progress=progress,
        now=1_600.0,
        stall_seconds=600,
    )

    pipe._track_progress_event(
        progress,
        {"event": "tool.started", "tool": "terminal", "timestamp": 1_000.0},
        observed_at=2_000.0,
    )
    description = pipe._heartbeat_description(
        elapsed_seconds=1_001,
        progress=progress,
        now=2_001.0,
        stall_seconds=600,
    )

    assert "状態: 実行中" in description
    assert "最終実進展: 1970-01-01T00:33:20Z（1秒前）" in description


def test_malformed_plan_update_does_not_clear_last_valid_progress():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    valid = {
        "event": "plan.updated",
        "items": [
            {
                "id": "integration",
                "content": "外部システムとの疎通を追加調査中",
                "status": "in_progress",
            }
        ],
    }
    pipe._track_progress_event(progress, valid)

    pipe._track_progress_event(progress, {"event": "plan.updated", "items": {}})
    assert progress["plan_items"] == valid["items"]

    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [{"id": "bad", "content": "bad", "status": "unknown"}],
        },
    )
    assert progress["plan_items"] == valid["items"]

    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {"id": str(index), "content": "oversized", "status": "pending"}
                for index in range(101)
            ],
        },
    )
    assert progress["plan_items"] == valid["items"]

    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {"id": "same", "content": "工程A", "status": "completed"},
                {"id": "same", "content": "工程B", "status": "pending"},
            ],
        },
    )
    assert progress["plan_items"] == valid["items"]

    pipe._track_progress_event(progress, {"event": "plan.updated", "items": []})
    assert progress["plan_items"] == []


def test_mixed_valid_and_invalid_plan_update_fails_closed_without_progress():
    pipe = Pipe()
    progress = pipe._initial_progress_state(started_at=1_000.0)
    baseline = {
        "event": "plan.updated",
        "items": [
            {
                "id": "baseline",
                "content": "既存の有効な段階",
                "status": "in_progress",
            }
        ],
    }
    pipe._track_progress_event(progress, baseline, observed_at=1_000.0)
    event_count = progress["real_event_count"]

    accepted = pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "replacement",
                    "content": "置換候補",
                    "status": "in_progress",
                },
                {
                    "id": "oversized",
                    "content": "x" * 4_001,
                    "status": "pending",
                },
            ],
        },
        observed_at=2_000.0,
    )

    assert accepted is False
    assert progress["plan_items"] == baseline["items"]
    assert progress["real_event_count"] == event_count
    assert progress["last_real_progress_at"] == 1_000.0


def test_all_cancelled_plan_does_not_invent_a_percentage():
    pipe = Pipe()
    progress = {
        "plan_items": [
            {"id": "obsolete", "content": "不要になった工程", "status": "cancelled"}
        ]
    }

    description = pipe._heartbeat_description(
        elapsed_seconds=300,
        progress=progress,
    )

    assert "進捗率未算出" in description
    assert "(0%)" not in description


def test_plan_progress_redacts_credential_urls_at_the_pipe_boundary():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "remote",
                    "content": (
                        "open https://user:password@example.com/path?token="
                        "secret-token-value-1234567890"
                    ),
                    "status": "in_progress",
                }
            ],
        },
    )

    description = pipe._heartbeat_description(
        elapsed_seconds=300,
        progress=progress,
    )

    assert "password" not in description
    assert "secret-token-value" not in description
    assert "https://user:***@example.com/path?token=***" in description


def test_plan_progress_redacts_secret_url_fragment_at_the_pipe_boundary():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    pipe._track_progress_event(
        progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "callback",
                    "content": (
                        "確認 https://example.com/callback#access%5Ftoken%3D"
                        "ACCESS_FRAGMENT_MUST_NOT_APPEAR "
                        "https://example.com/refresh#refresh%5Ftoken%3D"
                        "REFRESH_FRAGMENT_MUST_NOT_APPEAR "
                        "https://example.com/client?client%5Fsecret%3D"
                        "CLIENT_SECRET_MUST_NOT_APPEAR"
                    ),
                    "status": "in_progress",
                }
            ],
        },
    )

    description = pipe._heartbeat_description(
        elapsed_seconds=300,
        progress=progress,
    )

    assert "ACCESS_FRAGMENT_MUST_NOT_APPEAR" not in description
    assert "REFRESH_FRAGMENT_MUST_NOT_APPEAR" not in description
    assert "CLIENT_SECRET_MUST_NOT_APPEAR" not in description
    assert "https://example.com/callback#access%5Ftoken%3D***" in description
    assert "https://example.com/refresh#refresh%5Ftoken%3D***" in description
    assert "https://example.com/client?client%5Fsecret%3D***" in description


def test_progress_heartbeat_does_not_treat_active_tool_as_user_progress():
    pipe = Pipe()
    progress = pipe._initial_progress_state()

    pipe._track_progress_event(
        progress,
        {
            "event": "tool.started",
            "tool": "terminal",
            "preview": "SECRET_COMMAND_MUST_NOT_APPEAR",
        },
    )
    description = pipe._heartbeat_description(
        elapsed_seconds=900,
        progress=progress,
    )

    assert description.startswith("[15分経過] 処理中 (進捗率未算出)")
    assert "terminal" not in description
    assert "SECRET_COMMAND_MUST_NOT_APPEAR" not in description


def test_progress_heartbeat_uses_generic_label_for_untrusted_tool_name():
    pipe = Pipe()
    progress = pipe._initial_progress_state()
    event = {
        "event": "tool.started",
        "tool": "terminal — USER_INPUT_SECRET_7f9c",
        "preview": "ANOTHER_SECRET",
    }

    pipe._track_progress_event(progress, event)
    heartbeat = pipe._heartbeat_description(
        elapsed_seconds=900,
        progress=progress,
    )
    immediate = pipe._tool_description(event, completed=False)

    assert "ツールを実行中" not in heartbeat
    assert immediate == "実行中: ツール"
    assert "USER_INPUT_SECRET_7f9c" not in heartbeat
    assert "USER_INPUT_SECRET_7f9c" not in immediate
    assert "ANOTHER_SECRET" not in heartbeat
    assert "ANOTHER_SECRET" not in immediate


def test_legacy_tool_preview_valve_never_exposes_preview_or_user_input():
    pipe = Pipe()
    pipe.valves.SHOW_TOOL_PREVIEW = True
    pipe.valves.TOOL_PREVIEW_CHARS = 1000
    description = pipe._tool_description(
        {
            "event": "tool.started",
            "tool": "terminal",
            "preview": "USER_INPUT_AND_TOKEN_MUST_NEVER_APPEAR token=secret-value",
        },
        completed=False,
    )

    assert description == "実行中: terminal"
    assert "USER_INPUT" not in description
    assert "secret-value" not in description


def test_progress_heartbeat_does_not_report_tool_count_or_reasoning_activity():
    pipe = Pipe()
    progress = pipe._initial_progress_state()

    pipe._track_progress_event(
        progress,
        {"event": "tool.started", "tool": "web_search"},
    )
    pipe._track_progress_event(
        progress,
        {
            "event": "tool.completed",
            "tool": "web_search",
            "error": False,
            "result": "SECRET_RESULT_MUST_NOT_APPEAR",
        },
    )
    pipe._track_progress_event(
        progress,
        {
            "event": "reasoning.available",
            "text": "PRIVATE_REASONING_MUST_NOT_APPEAR",
        },
    )
    description = pipe._heartbeat_description(
        elapsed_seconds=1800,
        progress=progress,
    )

    assert description.startswith("[30分経過] 処理中 (進捗率未算出)")
    assert "完了したツール" not in description
    assert "Hermesが考えています" not in description
    assert "SECRET_RESULT_MUST_NOT_APPEAR" not in description
    assert "PRIVATE_REASONING_MUST_NOT_APPEAR" not in description


@pytest.mark.parametrize(
    ("event", "expected_activity"),
    [
        (
            {"event": "message.delta", "delta": "PRIVATE_DRAFT_MUST_NOT_APPEAR"},
            "回答を生成中",
        ),
        (
            {"event": "approval.request", "command": "SECRET_COMMAND"},
            "ユーザーの承認待ち",
        ),
    ],
)
def test_progress_heartbeat_does_not_expose_message_or_approval_payload(
    event, expected_activity
):
    pipe = Pipe()
    progress = pipe._initial_progress_state()

    pipe._track_progress_event(progress, event)
    description = pipe._heartbeat_description(
        elapsed_seconds=3600,
        progress=progress,
    )

    assert description.startswith("[1時間経過] 処理中 (進捗率未算出)")
    assert expected_activity not in description
    assert "PRIVATE_DRAFT_MUST_NOT_APPEAR" not in description
    assert "SECRET_COMMAND" not in description


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
async def test_tool_lifecycle_is_suppressed_from_status_and_content_by_default():
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
        assert not any(
            item["description"].startswith("実行中:") for item in statuses
        )
        assert not any(
            item["description"].startswith("完了: terminal") for item in statuses
        )
        assert not any("考えています" in item["description"] for item in statuses)
        assert statuses[-1]["description"] == "完了"
        assert statuses[-1]["done"] is True
        assert fake.stops == []
        assert fake.run_payloads[0]["session_id"] == "owui_test"
        assert fake.headers[0]["X-Hermes-Session-Key"] == "openwebui:test"
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_periodic_display_reports_event_based_work_without_raw_log_text():
    fake = await FakeHermes(
        [
            {
                "event": "tool.started",
                "tool": "read_file",
                "preview": "PRIVATE_PATH_MUST_NOT_APPEAR",
            },
            {
                "event": "tool.completed",
                "tool": "read_file",
                "error": False,
                "result": "PRIVATE_RESULT_MUST_NOT_APPEAR",
            },
            {"event": "run.completed", "output": "EVENT_PROGRESS_OK"},
        ],
        event_delays=[0.2, 1.2, 1.2],
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 1
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="event progress",
                history=[],
                instructions=None,
                session_id="owui_event_progress",
                session_key="openwebui:event-progress",
                event_emitter=emitter,
                event_call=None,
            )
        ]

        semantic = [
            item
            for item in status_data(emitted)
            if item.get("progress_update") or item.get("heartbeat")
        ]
        descriptions = [item["description"] for item in semantic]
        assert visible_content(chunks) == "EVENT_PROGRESS_OK"
        assert sum(1 for item in semantic if item.get("heartbeat")) >= 2
        assert any("現在: 対象ファイルの内容を確認中" in text for text in descriptions)
        assert any("直近結果: 対象ファイルの確認を完了" in text for text in descriptions)
        assert all("変化:" in text for text in descriptions)
        assert all("最終実進展:" in text for text in descriptions)
        assert not any(text == "実行中: read_file" for text in descriptions)
        assert "PRIVATE_PATH_MUST_NOT_APPEAR" not in "\n".join(descriptions)
        assert "PRIVATE_RESULT_MUST_NOT_APPEAR" not in "\n".join(descriptions)
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_dense_tool_events_do_not_outpace_the_display_interval():
    fake = await FakeHermes(
        [
            {"event": "tool.started", "tool": "read_file"},
            {"event": "tool.completed", "tool": "read_file", "error": False},
            {"event": "tool.started", "tool": "search_files"},
            {"event": "tool.completed", "tool": "search_files", "error": False},
            {"event": "tool.started", "tool": "write_file"},
            {"event": "tool.completed", "tool": "write_file", "error": False},
            {"event": "run.completed", "output": "RATE_LIMIT_OK"},
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
                message="dense events",
                history=[],
                instructions=None,
                session_id="owui_dense_events",
                session_key="openwebui:dense-events",
                event_emitter=emitter,
                event_call=None,
            )
        ]

        semantic = [
            item for item in status_data(emitted) if item.get("progress_update")
        ]

        assert visible_content(chunks) == "RATE_LIMIT_OK"
        assert pipe.valves.PROGRESS_HEARTBEAT_SECONDS == 300
        assert len(semantic) == 1
        assert semantic[0]["event_type"] == "run.started"
        assert "現在: 開始処理中／最初の実行イベント待ち" in semantic[0]["description"]
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_run_start_reports_waiting_for_first_observable_event():
    fake = await FakeHermes(
        [{"event": "run.completed", "output": "START_STATUS_OK"}],
        event_delay=0.05,
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="start status",
                history=[],
                instructions=None,
                session_id="owui_start_status",
                session_key="openwebui:start-status",
                event_emitter=emitter,
                event_call=None,
            )
        ]

        statuses = status_data(emitted)
        assert visible_content(chunks) == "START_STATUS_OK"
        assert statuses[0]["description"].startswith(
            "[0秒経過] 処理中 (進捗率未算出) - "
            "現在: 開始処理中／最初の実行イベント待ち。"
        )
        assert statuses[0]["progress_update"] is True
        assert "前回表示: 初回" in statuses[0]["description"]
        assert "作業計画が未登録" not in statuses[0]["description"]
        assert "Hermesが処理を開始しました" not in statuses[0]["description"]
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_interim_assistant_message_is_visible_before_final_answer():
    fake = await FakeHermes(
        [
            {
                "event": "message.interim",
                "content": "短い計画：状態を確認してから修正します。",
            },
            {"event": "tool.started", "tool": "terminal"},
            {"event": "tool.completed", "tool": "terminal", "error": False},
            {"event": "message.delta", "delta": "修正と検証が完了しました。"},
            {"event": "run.completed", "output": "修正と検証が完了しました。"},
        ]
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        stream = pipe._stream_response(
            message="修正して",
            history=[],
            instructions=None,
            session_id="owui_interim",
            session_key="openwebui:interim",
            event_emitter=None,
            event_call=None,
        )

        role_chunk = await anext(stream)
        interim_chunk = await anext(stream)
        remaining = [chunk async for chunk in stream]

        assert visible_content([role_chunk]) == ""
        assert visible_content([interim_chunk]) == (
            "短い計画：状態を確認してから修正します。\n\n"
        )
        assert visible_content([interim_chunk, *remaining]) == (
            "短い計画：状態を確認してから修正します。\n\n"
            "修正と検証が完了しました。"
        )
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_long_run_emits_periodic_status_only_and_stops_after_terminal_event():
    fake = await FakeHermes(
        [
            {
                "event": "plan.updated",
                "items": [
                    {
                        "id": "design",
                        "content": "設計の大枠を確定",
                        "status": "completed",
                    },
                    {
                        "id": "integration",
                        "content": "外部システムとの疎通条件を追加調査中",
                        "status": "in_progress",
                    },
                ],
            },
            {"event": "run.completed", "output": "LONG_RUN_OK"},
        ],
        event_delays=[0, 1.2],
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 1
        emitted = []

        async def emitter(event):
            emitted.append(event)

        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="long run",
                history=[],
                instructions=None,
                session_id="owui_long_run",
                session_key="openwebui:long-run",
                event_emitter=emitter,
                event_call=None,
            )
        ]

        content = visible_content(chunks)
        heartbeats = [item for item in status_data(emitted) if item.get("heartbeat")]
        assert content == "LONG_RUN_OK"
        assert "開始から" not in content
        assert len(heartbeats) == 1
        assert heartbeats[0]["description"].startswith("[1秒経過] 処理中 (50%)")
        assert "完了: 設計の大枠を確定。" in heartbeats[0]["description"]
        assert (
            "現在: 外部システムとの疎通条件を追加調査中。"
            in heartbeats[0]["description"]
        )
        assert heartbeats[0]["done"] is False
        assert heartbeats[0]["run_id"] == "run_test"
        assert status_data(emitted)[-1]["description"] == "完了"

        emitted_count = len(emitted)
        await asyncio.sleep(1.1)
        assert len(emitted) == emitted_count
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_zero_progress_heartbeat_interval_does_not_start_background_task():
    fake = await FakeHermes(
        [{"event": "run.completed", "output": "HEARTBEAT_DISABLED_OK"}]
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 0
        heartbeat_started = False

        async def unexpected_heartbeat(**_kwargs):
            nonlocal heartbeat_started
            heartbeat_started = True

        pipe._progress_heartbeat = unexpected_heartbeat
        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="disabled heartbeat",
                history=[],
                instructions=None,
                session_id="owui_disabled_heartbeat",
                session_key="openwebui:disabled-heartbeat",
                event_emitter=lambda _event: asyncio.sleep(0),
                event_call=None,
            )
        ]

        assert visible_content(chunks) == "HEARTBEAT_DISABLED_OK"
        assert heartbeat_started is False
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_cancelled_run_stops_heartbeat_before_delayed_tick():
    fake = await FakeHermes(
        [{"event": "run.completed", "output": "too late"}],
        event_delay=2,
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 1
        emitted = []

        async def emitter(event):
            emitted.append(event)

        async def consume():
            return [
                chunk
                async for chunk in pipe._stream_response(
                    message="cancel heartbeat",
                    history=[],
                    instructions=None,
                    session_id="owui_cancel_heartbeat",
                    session_key="openwebui:cancel-heartbeat",
                    event_emitter=emitter,
                    event_call=None,
                )
            ]

        consumer = asyncio.create_task(consume())
        deadline = asyncio.get_running_loop().time() + 1
        while not emitted and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        assert emitted

        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer

        statuses = status_data(emitted)
        assert statuses[-1]["description"] == "キャンセル済み"
        assert fake.stops == ["run_test"]
        emitted_count = len(emitted)
        await asyncio.sleep(1.1)
        assert len(emitted) == emitted_count
        assert not any(item.get("heartbeat") for item in status_data(emitted))
    finally:
        await fake.close()


@pytest.mark.asyncio
async def test_stream_aclose_waits_for_inner_run_and_heartbeat_cleanup():
    fake = await FakeHermes(
        [
            {"event": "message.delta", "delta": "partial"},
            {"event": "run.completed", "output": "partial"},
        ]
    ).start()
    stream = None
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 1
        emitted = []

        async def emitter(event):
            emitted.append(event)

        stream = pipe._stream_response(
            message="close stream",
            history=[],
            instructions=None,
            session_id="owui_close_heartbeat",
            session_key="openwebui:close-heartbeat",
            event_emitter=emitter,
            event_call=None,
        )
        await anext(stream)
        assert visible_content([await anext(stream)]) == "partial"
        await asyncio.sleep(1.1)
        assert any(item.get("heartbeat") for item in status_data(emitted))

        await stream.aclose()

        active_heartbeats = [
            task
            for task in asyncio.all_tasks()
            if not task.done()
            and task.get_name().startswith("hermes-progress-heartbeat-")
        ]
        assert active_heartbeats == []
        assert status_data(emitted)[-1]["description"] == "キャンセル済み"
        assert fake.stops == ["run_test"]
        emitted_count = len(emitted)
        await asyncio.sleep(1.1)
        assert len(emitted) == emitted_count
    finally:
        if stream is not None:
            await stream.aclose()
        leftovers = [
            task
            for task in asyncio.all_tasks()
            if not task.done()
            and task.get_name().startswith("hermes-progress-heartbeat-")
        ]
        for task in leftovers:
            task.cancel()
        if leftovers:
            await asyncio.gather(*leftovers, return_exceptions=True)
        await fake.close()


@pytest.mark.asyncio
async def test_concurrent_progress_heartbeats_keep_run_state_isolated():
    pipe = Pipe()
    terminal_progress = pipe._initial_progress_state()
    search_progress = pipe._initial_progress_state()
    pipe._track_progress_event(
        terminal_progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "local",
                    "content": "ローカル設定を確認中",
                    "status": "in_progress",
                }
            ],
        },
    )
    pipe._track_progress_event(
        search_progress,
        {
            "event": "plan.updated",
            "items": [
                {
                    "id": "sources",
                    "content": "一次情報を確認",
                    "status": "completed",
                },
                {
                    "id": "compare",
                    "content": "候補を比較中",
                    "status": "in_progress",
                },
            ],
        },
    )

    emitted = {"run_terminal": [], "run_search": []}

    async def terminal_emitter(event):
        emitted["run_terminal"].append(event)

    async def search_emitter(event):
        emitted["run_search"].append(event)

    stop_terminal = asyncio.Event()
    stop_search = asyncio.Event()
    started_at = asyncio.get_running_loop().time() - 900
    tasks = [
        asyncio.create_task(
            pipe._progress_heartbeat(
                emitter=terminal_emitter,
                run_id="run_terminal",
                interval_seconds=0.01,
                started_at=started_at,
                progress=terminal_progress,
                stop_event=stop_terminal,
            )
        ),
        asyncio.create_task(
            pipe._progress_heartbeat(
                emitter=search_emitter,
                run_id="run_search",
                interval_seconds=0.01,
                started_at=started_at,
                progress=search_progress,
                stop_event=stop_search,
            )
        ),
    ]
    try:
        deadline = asyncio.get_running_loop().time() + 1
        while (
            not emitted["run_terminal"] or not emitted["run_search"]
        ) and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        assert emitted["run_terminal"] and emitted["run_search"]
    finally:
        stop_terminal.set()
        stop_search.set()
        await asyncio.gather(*tasks)

    terminal_status = status_data(emitted["run_terminal"])[0]
    search_status = status_data(emitted["run_search"])[0]
    assert terminal_status["run_id"] == "run_terminal"
    assert "ローカル設定を確認中" in terminal_status["description"]
    assert "一次情報を確認" not in terminal_status["description"]
    assert search_status["run_id"] == "run_search"
    assert "一次情報を確認" in search_status["description"]
    assert "候補を比較中" in search_status["description"]
    assert "ローカル設定を確認中" not in search_status["description"]


@pytest.mark.asyncio
async def test_heartbeat_and_event_statuses_use_serial_emitter_calls():
    fake = await FakeHermes(
        [
            {"event": "tool.started", "tool": "terminal"},
            {"event": "run.completed", "output": "SERIAL_STATUS_OK"},
        ],
        event_delay=1.05,
    ).start()
    release_heartbeat = asyncio.Event()
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 1
        active_calls = 0
        max_active_calls = 0
        heartbeat_entered = asyncio.Event()

        async def emitter(event):
            nonlocal active_calls, max_active_calls
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
            try:
                data = event.get("data") or {}
                if data.get("heartbeat") and not heartbeat_entered.is_set():
                    heartbeat_entered.set()
                    await release_heartbeat.wait()
                await asyncio.sleep(0)
            finally:
                active_calls -= 1

        async def release_after_overlap_window():
            await asyncio.wait_for(heartbeat_entered.wait(), timeout=2)
            await asyncio.sleep(0.15)
            release_heartbeat.set()

        releaser = asyncio.create_task(release_after_overlap_window())
        chunks = [
            chunk
            async for chunk in pipe._stream_response(
                message="serialize statuses",
                history=[],
                instructions=None,
                session_id="owui_serial_status",
                session_key="openwebui:serial-status",
                event_emitter=emitter,
                event_call=None,
            )
        ]
        await releaser

        assert visible_content(chunks) == "SERIAL_STATUS_OK"
        assert max_active_calls == 1
    finally:
        release_heartbeat.set()
        await fake.close()


@pytest.mark.asyncio
async def test_internal_openwebui_task_does_not_emit_progress_statuses():
    fake = await FakeHermes(
        [{"event": "run.completed", "output": "internal result"}],
        event_delay=1.2,
    ).start()
    try:
        pipe = configured_pipe(fake.base_url)
        pipe.valves.PROGRESS_HEARTBEAT_SECONDS = 1
        emitted = []

        async def emitter(event):
            emitted.append(event)

        response = await pipe.pipe(
            {
                "messages": [{"role": "user", "content": "generate a title"}],
                "stream": False,
            },
            __user__={"id": "owner-user"},
            __chat_id__="heartbeat-internal-chat",
            __session_id__="heartbeat-internal-session",
            __message_id__="heartbeat-internal-message",
            __event_emitter__=emitter,
            __metadata__={"task": "title_generation", "internal": False},
        )

        assert response["choices"][0]["message"]["content"] == "internal result"
        assert emitted == []
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
    interim = "短い計画：状態を確認してから作業します。"
    answer = "結論です。\n\n次はPKB取り込み経路を整備します。"
    saved_answer = f"{interim}\n\n{answer}"
    hermes = await FakeHermes(
        [
            {"event": "message.interim", "content": interim},
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
            return "PDAの次工程", saved_answer

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

        assert visible_content(chunks) == saved_answer
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
                __metadata__={
                    "chat_id": chat_id,
                    "internal": False,
                    "task": task,
                },
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
