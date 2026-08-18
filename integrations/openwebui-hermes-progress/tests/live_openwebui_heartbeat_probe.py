#!/usr/bin/env python3
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
EXPECTED = "HEARTBEAT_E2E_OK"
PRIVATE_TOOL_INPUT = "HEARTBEAT_PRIVATE_TOOL_INPUT_9d31"


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
            test_valves["SHOW_TOOL_PREVIEW"] = False
            # Do not send a phone notification for this synthetic E2E run.
            test_valves["NTFY_TOPIC"] = ""
            updated = await helpers.openwebui_json(
                client,
                token,
                "POST",
                f"/api/v1/functions/id/{FUNCTION_ID}/valves/update",
                test_valves,
            )
            if int(updated.get("PROGRESS_HEARTBEAT_SECONDS", -1)) != 2:
                raise RuntimeError("short heartbeat Valve was not applied")

            prompt = (
                "Use the terminal tool exactly once. Run this exact command and wait for it: "
                f"python3 -c \"import time; time.sleep(7); print('{PRIVATE_TOOL_INPUT}')\". "
                f"After the tool finishes, reply with exactly {EXPECTED} and nothing else."
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
                    "session_id": f"pda-heartbeat-e2e-{uuid.uuid4().hex}",
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
            deadline = loop.time() + 180
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
            heartbeats = [
                item
                for item in statuses
                if item.get("heartbeat") is True
                or str(item.get("description") or "").startswith("⏳")
            ]
            heartbeat_text = "\n".join(
                str(item.get("description") or "") for item in heartbeats
            )
            heartbeat_count_at_done = len(heartbeats)

            await asyncio.sleep(3)
            final_record = await helpers.openwebui_json(
                client, token, "GET", f"/api/v1/chats/{chat_id}"
            )
            final_saved = helpers.assistant_message(final_record, assistant_message_id)
            final_heartbeats = [
                item
                for item in (final_saved.get("statusHistory") or [])
                if isinstance(item, dict)
                and (
                    item.get("heartbeat") is True
                    or str(item.get("description") or "").startswith("⏳")
                )
            ]

            result = {
                "chat_task_accepted": True,
                "test_chat_id": chat_id,
                "saved_done": saved.get("done") is True,
                "answer_contains_expected": EXPECTED in content,
                "status_count": len(statuses),
                "heartbeat_count": heartbeat_count_at_done,
                "heartbeat_count_after_terminal_wait": len(final_heartbeats),
                "heartbeat_has_elapsed": all(
                    "開始から" in str(item.get("description") or "")
                    for item in heartbeats
                ),
                "heartbeat_has_safe_tool_name": any(
                    "terminal" in str(item.get("description") or "")
                    for item in heartbeats
                ),
                "private_tool_input_absent": PRIVATE_TOOL_INPUT not in heartbeat_text,
                "prompt_absent": "python3 -c" not in heartbeat_text,
                "all_heartbeat_done_false": all(
                    item.get("done") is False for item in heartbeats
                ),
                "has_terminal_status": any(
                    item.get("done") is True
                    and str(item.get("description") or "") == "完了"
                    for item in statuses
                ),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

            assert result["saved_done"], result
            assert result["answer_contains_expected"], result
            assert result["heartbeat_count"] >= 2, result
            assert (
                result["heartbeat_count_after_terminal_wait"]
                == result["heartbeat_count"]
            ), result
            assert result["heartbeat_has_elapsed"], result
            assert result["heartbeat_has_safe_tool_name"], result
            assert result["private_tool_input_absent"], result
            assert result["prompt_absent"], result
            assert result["all_heartbeat_done_false"], result
            assert result["has_terminal_status"], result
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
                if int(restored.get("PROGRESS_HEARTBEAT_SECONDS", -1)) != int(
                    original_valves.get("PROGRESS_HEARTBEAT_SECONDS", -2)
                ):
                    raise RuntimeError("failed to restore production heartbeat Valve")
            if chat_id and not keep_chat:
                try:
                    await helpers.openwebui_json(
                        client, token, "DELETE", f"/api/v1/chats/{chat_id}"
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
