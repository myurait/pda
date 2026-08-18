#!/usr/bin/env python3
"""Verify that Open WebUI persists an interim plan before a tool-bound run ends."""

import asyncio
import importlib.util
import json
import time
import uuid
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
HELPERS_PATH = ROOT / "tests" / "live_openwebui_notification_probe.py"
spec = importlib.util.spec_from_file_location("live_probe_helpers", HELPERS_PATH)
assert spec and spec.loader
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)

FUNCTION_ID = "hermes_progress_pipe"
MODEL_ID = "hermes_progress_pipe"
PLAN = "INTERIM_PLAN_VISIBLE_BEFORE_TOOL"
FINAL = "INTERIM_FINAL_VISIBLE_AFTER_TOOL"
TOOL_SLEEP_SECONDS = 5


async def main() -> None:
    token = helpers.read_secret(ROOT / ".admin-api-key")
    timeout = aiohttp.ClientTimeout(total=180, connect=15, sock_read=180)
    original_valves = None
    chat_id = ""
    keep_chat = False

    async with aiohttp.ClientSession(timeout=timeout) as client:
        try:
            original_valves = await helpers.openwebui_json(
                client,
                token,
                "GET",
                f"/api/v1/functions/id/{FUNCTION_ID}/valves",
            )
            test_valves = dict(original_valves)
            # This is a synthetic timing probe, not a user completion.
            test_valves["NTFY_TOPIC"] = ""
            await helpers.openwebui_json(
                client,
                token,
                "POST",
                f"/api/v1/functions/id/{FUNCTION_ID}/valves/update",
                test_valves,
            )

            prompt = (
                f"First emit exactly {PLAN} as a short user-visible assistant "
                "commentary/progress message. In that same response, without waiting "
                "for another user turn, call the terminal tool exactly once with: "
                f"python3 -c \"import time; time.sleep({TOOL_SLEEP_SECONDS}); "
                "print('INTERIM_TOOL_OK')\". After the tool returns, reply exactly "
                f"{FINAL}. Do not omit the first commentary message."
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
            loop = asyncio.get_running_loop()
            submitted_at = loop.time()
            accepted = await helpers.openwebui_json(
                client,
                token,
                "POST",
                "/api/chat/completions",
                {
                    "stream": True,
                    "model": MODEL_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "session_id": f"pda-interim-e2e-{uuid.uuid4().hex}",
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

            plan_seen_at = None
            plan_seen_while_running = False
            final_seen_at = None
            saved = {}
            deadline = loop.time() + 150
            while loop.time() < deadline:
                record = await helpers.openwebui_json(
                    client, token, "GET", f"/api/v1/chats/{chat_id}"
                )
                saved = helpers.assistant_message(record, assistant_message_id)
                content = helpers.saved_answer(saved)
                now = loop.time()
                if plan_seen_at is None and PLAN in content:
                    plan_seen_at = now
                    plan_seen_while_running = saved.get("done") is not True
                if FINAL in content and saved.get("done") is True:
                    final_seen_at = now
                    break
                await asyncio.sleep(0.1)

            content = helpers.saved_answer(saved)
            plan_seconds = (
                round(plan_seen_at - submitted_at, 3)
                if plan_seen_at is not None
                else None
            )
            final_seconds = (
                round(final_seen_at - submitted_at, 3)
                if final_seen_at is not None
                else None
            )
            visible_gap_seconds = (
                round(final_seen_at - plan_seen_at, 3)
                if plan_seen_at is not None and final_seen_at is not None
                else None
            )
            result = {
                "chat_task_accepted": True,
                "test_chat_id": chat_id,
                "plan_seen_while_running": plan_seen_while_running,
                "plan_seconds_after_submit": plan_seconds,
                "final_seconds_after_submit": final_seconds,
                "visible_gap_seconds": visible_gap_seconds,
                "saved_done": saved.get("done") is True,
                "plan_precedes_final": (
                    content.find(PLAN) >= 0
                    and content.find(FINAL) > content.find(PLAN)
                ),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

            assert result["plan_seen_while_running"], result
            assert result["saved_done"], result
            assert result["plan_precedes_final"], result
            assert visible_gap_seconds is not None, result
            assert visible_gap_seconds >= TOOL_SLEEP_SECONDS - 1, result
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
                if restored.get("NTFY_TOPIC") != original_valves.get("NTFY_TOPIC"):
                    raise RuntimeError("failed to restore production ntfy Valve")
            if chat_id and not keep_chat:
                try:
                    await helpers.openwebui_json(
                        client, token, "DELETE", f"/api/v1/chats/{chat_id}"
                    )
                except Exception as exc:
                    print(f"warning: failed to delete unsuccessful test chat: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
