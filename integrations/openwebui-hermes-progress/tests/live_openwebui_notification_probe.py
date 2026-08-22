import asyncio
import json
import stat
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import aiohttp

ROOT = Path(__file__).parents[1]
OPENWEBUI_URL = "http://127.0.0.1:9120"
EXPECTED_ANSWER = "OWUI_PUSH_PREVIEW_OK"
MODEL_ID = "hermes_progress_pipe"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_secret(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RuntimeError(f"Credential file is too permissive: {path} ({mode:04o})")
    return path.read_text(encoding="utf-8").strip()


async def openwebui_json(
    client: aiohttp.ClientSession,
    token: str,
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict:
    async with client.request(
        method,
        f"{OPENWEBUI_URL}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        allow_redirects=False,
    ) as response:
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(
                f"Open WebUI {method} {path} failed ({response.status}): {text[:500]}"
            )
        data = json.loads(text) if text else {}
        if not isinstance(data, dict):
            raise RuntimeError(f"Open WebUI {method} {path} returned non-object JSON")
        return data


async def ntfy_messages(
    client: aiohttp.ClientSession, server: str, topic: str
) -> list[dict]:
    poll_url = f"{server}/{quote(topic, safe='-_')}/json?poll=1&since=all"
    async with client.get(poll_url, allow_redirects=False) as response:
        if response.status != 200:
            raise RuntimeError(f"ntfy poll failed ({response.status})")
        return [
            json.loads(line)
            for line in (await response.text()).splitlines()
            if line.strip()
        ]


def saved_answer(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    parts: list[str] = []

    def visit(value) -> None:
        if isinstance(value, str):
            if value:
                parts.append(value)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        item_type = str(value.get("type") or "").lower()
        if item_type in {"reasoning", "tool", "tool_call", "tool_result"}:
            return
        if item_type in {"output_text", "text"}:
            visit(value.get("text"))
        elif item_type == "message":
            visit(value.get("content"))

    visit(message.get("output"))
    return "".join(parts).strip()


def assistant_message(chat_record: dict, message_id: str) -> dict:
    chat = chat_record.get("chat") or {}
    history = chat.get("history") or {}
    messages = history.get("messages") or {}
    message = messages.get(message_id) or {}
    return message if isinstance(message, dict) else {}


async def main() -> None:
    env = load_env(ROOT / ".env")
    token = read_secret(ROOT / ".admin-api-key")
    ntfy_server = env["PDA_NTFY_SERVER_URL"].rstrip("/")
    ntfy_topic = env["PDA_NTFY_TOPIC"]
    click_url = env["PDA_OPENWEBUI_PUBLIC_URL"].rstrip("/")
    started_at = int(time.time())
    prompt = f"Reply exactly {EXPECTED_ANSWER} and nothing else. Do not use tools."

    timeout = aiohttp.ClientTimeout(total=660, connect=15, sock_read=660)
    chat_id = ""
    keep_chat = False

    async with aiohttp.ClientSession(timeout=timeout) as client:
        try:
            baseline_ids = {
                str(event.get("id"))
                for event in await ntfy_messages(client, ntfy_server, ntfy_topic)
                if event.get("event") == "message" and event.get("id")
            }
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
            accepted = await openwebui_json(
                client,
                token,
                "POST",
                "/api/chat/completions",
                {
                    "stream": True,
                    "model": MODEL_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "session_id": f"pda-live-probe-{uuid.uuid4().hex}",
                    "id": assistant_message_id,
                    "parent_id": None,
                    "message_ids": [
                        {
                            "model_id": MODEL_ID,
                            "message_id": assistant_message_id,
                        }
                    ],
                    "user_message": user_message,
                    "background_tasks": {
                        "title_generation": True,
                        "tags_generation": False,
                        "follow_up_generation": False,
                    },
                },
            )
            if accepted.get("status") is not True:
                raise RuntimeError(f"Open WebUI did not accept the chat task: {accepted}")
            chat_id = str(accepted.get("chat_id") or "")
            if not chat_id:
                raise RuntimeError(f"Open WebUI did not return a chat ID: {accepted}")

            loop = asyncio.get_running_loop()
            deadline = loop.time() + 600
            saved = {}
            while loop.time() < deadline:
                record = await openwebui_json(
                    client, token, "GET", f"/api/v1/chats/{chat_id}"
                )
                saved = assistant_message(record, assistant_message_id)
                if saved.get("done") is True:
                    break
                await asyncio.sleep(0.25)
            if saved.get("done") is not True:
                raise RuntimeError("Open WebUI assistant message did not reach done=true")

            content = saved_answer(saved)
            statuses = saved.get("statusHistory") or []
            status_descriptions = [
                str(item.get("description") or "")
                for item in statuses
                if isinstance(item, dict)
            ]
            expected_click = f"{click_url}/c/{chat_id}"

            new_messages: dict[str, dict] = {}
            expected_seen_at: float | None = None
            deadline = loop.time() + 30
            while loop.time() < deadline:
                events = await ntfy_messages(client, ntfy_server, ntfy_topic)
                for event in events:
                    event_id = str(event.get("id") or "")
                    if (
                        event.get("event") == "message"
                        and event_id
                        and event_id not in baseline_ids
                        and int(event.get("time") or 0) >= started_at
                    ):
                        new_messages[event_id] = event
                matching = [
                    event
                    for event in new_messages.values()
                    if event.get("message") == EXPECTED_ANSWER
                    and event.get("click") == expected_click
                ]
                if matching and expected_seen_at is None:
                    expected_seen_at = loop.time()
                if expected_seen_at is not None and loop.time() - expected_seen_at >= 2:
                    break
                await asyncio.sleep(0.25)

            all_new = list(new_messages.values())
            matching = [
                event
                for event in all_new
                if event.get("message") == EXPECTED_ANSWER
                and event.get("click") == expected_click
            ]
            final_record = await openwebui_json(
                client, token, "GET", f"/api/v1/chats/{chat_id}"
            )
            final_chat = final_record.get("chat") or {}
            saved_chat_title = str(
                final_record.get("title") or final_chat.get("title") or "New Chat"
            ).strip()
            result = {
                "chat_task_accepted": accepted.get("status") is True,
                "saved_answer": content,
                "saved_done": saved.get("done") is True,
                "progress_status_count": len(statuses),
                "progress_has_start": any(
                    "開始処理中／最初の実行イベント待ち" in description
                    for description in status_descriptions
                ),
                "progress_has_done": "完了" in status_descriptions,
                "completion_push_count": len(all_new),
                "completion_push_extra_count": len(all_new) - len(matching),
                "completion_push_title": matching[-1].get("title") if matching else None,
                "completion_push_preview": matching[-1].get("message") if matching else None,
                "completion_push_click_url": matching[-1].get("click") if matching else None,
                "completion_push_tags": matching[-1].get("tags") if matching else None,
                "saved_chat_title": saved_chat_title,
                "test_chat_id": chat_id,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

            assert content == EXPECTED_ANSWER, result
            assert saved.get("done") is True, result
            assert len(statuses) >= 2, result
            assert result["progress_has_start"], result
            assert result["progress_has_done"], result
            assert len(all_new) == 1, result
            assert len(matching) == 1, result
            assert result["completion_push_title"] == saved_chat_title, result
            assert result["completion_push_preview"] == EXPECTED_ANSWER, result
            assert result["completion_push_click_url"] == expected_click, result
            assert not result["completion_push_tags"], result
            keep_chat = True
        finally:
            if chat_id and not keep_chat:
                try:
                    await openwebui_json(
                        client,
                        token,
                        "DELETE",
                        f"/api/v1/chats/{chat_id}",
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
