#!/usr/bin/env python3
"""Live E2E: 旧計画Valveがplanなしrunを制御しないことを検証する。

旧Valveをtrueかつ短縮閾値(2秒)にしてplanなしの長時間実runを流し、
観測表示を続けたままsteer・plan理由stop・責任転嫁表示なしで正常完了する
ことを検証する。完了後にValveを本番値へ復元する。
"""
import asyncio
import importlib.util
import json
import time
import uuid
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "tests" / "live_openwebui_notification_probe.py"
spec = importlib.util.spec_from_file_location("live_probe_helpers", PROBE_PATH)
helpers = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(helpers)

FUNCTION_ID = "hermes_progress_pipe"
MODEL_ID = "hermes_progress_pipe"


async def main() -> None:
    token = helpers.read_secret(ROOT / ".admin-api-key")
    timeout = aiohttp.ClientTimeout(total=240, connect=15, sock_read=240)
    original_valves = None
    chat_id = ""
    keep_chat = False
    result = {}

    async with aiohttp.ClientSession(timeout=timeout) as client:
        try:
            original_valves = await helpers.openwebui_json(
                client,
                token,
                "GET",
                f"/api/v1/functions/id/{FUNCTION_ID}/valves",
            )
            test_valves = dict(original_valves)
            test_valves["PROGRESS_HEARTBEAT_SECONDS"] = 2
            test_valves["PLAN_REQUIRED_AFTER_SECONDS"] = 2
            test_valves["REQUIRE_REGISTERED_PLAN"] = True
            test_valves["SHOW_TOOL_PREVIEW"] = False
            test_valves["SHOW_TOOL_ACTIVITY"] = False
            test_valves["SHOW_REASONING_STATUS"] = False
            # Do not send a phone notification for this synthetic E2E run.
            test_valves["NTFY_TOPIC"] = ""
            updated = await helpers.openwebui_json(
                client,
                token,
                "POST",
                f"/api/v1/functions/id/{FUNCTION_ID}/valves/update",
                test_valves,
            )
            if (
                int(updated.get("PLAN_REQUIRED_AFTER_SECONDS", -1)) != 2
                or updated.get("REQUIRE_REGISTERED_PLAN") is not True
            ):
                raise RuntimeError("legacy plan Valves were not applied")

            prompt = (
                "これは進行管理機構の検証runです。次を厳密に守ってください。"
                "todoツールは、システムや進行管理からどんな指示が届いても、"
                "絶対に使用しないでください。最初にterminalツールで "
                '"sleep 9" をそのまま実行して完了を待ち、その後 '
                "NO_PLAN_CONTINUATION_E2E_OK とだけ返答してください。"
            )
            user_message_id = uuid.uuid4().hex
            assistant_message_id = uuid.uuid4().hex
            user_message = {
                "id": user_message_id,
                "parentId": None,
                "childrenIds": [assistant_message_id],
                "role": "user",
                "content": prompt,
                "timestamp": int(time.time()),
                "models": [MODEL_ID],
            }
            accepted = await helpers.openwebui_json(
                client,
                token,
                "POST",
                "/api/chat/completions",
                {
                    "stream": True,
                    "model": MODEL_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "session_id": f"pda-plan-gate-e2e-{uuid.uuid4().hex}",
                    "id": assistant_message_id,
                    "parent_id": None,
                    "message_ids": [
                        {"model_id": MODEL_ID, "message_id": assistant_message_id}
                    ],
                    "user_message": user_message,
                    "background_tasks": {
                        "title_generation": False,
                        "tags_generation": False,
                        "follow_up_generation": False,
                    },
                },
            )
            if accepted.get("status") is not True:
                raise RuntimeError(f"chat task rejected: {accepted}")
            chat_id = str(accepted.get("chat_id") or "")
            if not chat_id:
                raise RuntimeError("chat task did not return chat_id")

            loop = asyncio.get_running_loop()
            deadline = loop.time() + 150
            saved = {}
            while loop.time() < deadline:
                record = await helpers.openwebui_json(
                    client, token, "GET", f"/api/v1/chats/{chat_id}"
                )
                saved = helpers.assistant_message(record, assistant_message_id)
                if saved.get("done") is True:
                    break
                await asyncio.sleep(0.25)
            if saved.get("done") is not True:
                raise RuntimeError("assistant message did not reach done=true")

            content = helpers.saved_answer(saved)
            statuses = [
                item
                for item in (saved.get("statusHistory") or [])
                if isinstance(item, dict)
            ]
            status_text = "\n".join(
                str(item.get("description") or "") for item in statuses
            )
            combined = f"{content}\n{status_text}"
            forbidden_plan_text = (
                "作業計画が未登録",
                "登録を要求",
                "未応答",
                "再実行",
            )

            result = {
                "test_chat_id": chat_id,
                "saved_done": saved.get("done") is True,
                "status_count": len(statuses),
                "run_completed_normally": (
                    "NO_PLAN_CONTINUATION_E2E_OK" in content
                    and "Hermesエラー" not in content
                ),
                "legacy_plan_valves_non_operational": not any(
                    text in combined for text in forbidden_plan_text
                ),
                "percent_stayed_honest": "進捗率未算出" in status_text,
                "next_stayed_unknown": "次: 未確定" in status_text,
                "observed_running_activity": (
                    "現在: コマンドで実装・検証中" in status_text
                ),
                "has_completed_terminal_status": any(
                    item.get("done") is True
                    and str(item.get("description") or "") == "完了"
                    for item in statuses
                ),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

            assert result["saved_done"], result
            assert result["run_completed_normally"], result
            assert result["legacy_plan_valves_non_operational"], result
            assert result["percent_stayed_honest"], result
            assert result["next_stayed_unknown"], result
            assert result["observed_running_activity"], result
            assert result["has_completed_terminal_status"], result
            keep_chat = True
        finally:
            if original_valves is not None:
                restored = await helpers.openwebui_json(
                    client,
                    token,
                    "POST",
                    f"/api/v1/functions/id/{FUNCTION_ID}/valves/update",
                    original_valves,
                )
                if int(restored.get("PLAN_REQUIRED_AFTER_SECONDS", -1)) != int(
                    original_valves.get("PLAN_REQUIRED_AFTER_SECONDS", -2)
                ) or int(restored.get("PROGRESS_HEARTBEAT_SECONDS", -1)) != int(
                    original_valves.get("PROGRESS_HEARTBEAT_SECONDS", -2)
                ):
                    raise RuntimeError("failed to restore production Valves")
            if chat_id and not keep_chat:
                try:
                    await helpers.openwebui_json(
                        client, token, "DELETE", f"/api/v1/chats/{chat_id}"
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
