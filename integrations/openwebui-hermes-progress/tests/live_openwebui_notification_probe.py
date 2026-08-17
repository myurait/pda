import asyncio
import json
import stat
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp

ROOT = Path(__file__).parents[1]
OPENWEBUI_URL = "http://127.0.0.1:9120"
EXPECTED_MESSAGE = "Open WebUIでPDAの応答が完了しました。"


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


def extract_delta(event: dict) -> str:
    choices = event.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    delta = choices[0].get("delta") or {}
    return str(delta.get("content") or "") if isinstance(delta, dict) else ""


async def main() -> None:
    env = load_env(ROOT / ".env")
    token = read_secret(ROOT / ".admin-api-key")
    ntfy_server = env["PDA_NTFY_SERVER_URL"].rstrip("/")
    ntfy_topic = env["PDA_NTFY_TOPIC"]
    click_url = env["PDA_OPENWEBUI_PUBLIC_URL"]
    started_at = int(time.time())

    timeout = aiohttp.ClientTimeout(total=600, connect=15, sock_read=600)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = {
        "model": "hermes_progress_pipe",
        "messages": [
            {
                "role": "user",
                "content": "Reply exactly OWUI_PUSH_OK and nothing else. Do not use tools.",
            }
        ],
        "stream": True,
    }

    visible_parts: list[str] = []
    saw_done = False
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.post(
            f"{OPENWEBUI_URL}/api/chat/completions",
            headers=headers,
            json=payload,
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                detail = (await response.text())[:500]
                raise RuntimeError(
                    f"Open WebUI completion probe failed ({response.status}): {detail}"
                )
            async for raw in response.content:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    saw_done = True
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    visible_parts.append(extract_delta(event))

        matching = []
        events = []
        deadline = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < deadline:
            poll_url = (
                f"{ntfy_server}/{quote(ntfy_topic, safe='-_')}"
                f"/json?poll=1&since=all"
            )
            async with client.get(poll_url, allow_redirects=False) as response:
                if response.status != 200:
                    raise RuntimeError(f"ntfy poll failed ({response.status})")
                events = [
                    json.loads(line)
                    for line in (await response.text()).splitlines()
                    if line.strip()
                ]
            matching = [
                event
                for event in events
                if event.get("event") == "message"
                and int(event.get("time") or 0) >= started_at
                and event.get("title") == "PDA"
                and event.get("message") == EXPECTED_MESSAGE
            ]
            if matching:
                break
            await asyncio.sleep(0.25)

    content = "".join(visible_parts).strip()
    result = {
        "openwebui_response": content,
        "saw_done": saw_done,
        "completion_push_count": len(matching),
        "completion_push_content_free": all(
            "OWUI_PUSH_OK" not in json.dumps(item, ensure_ascii=False)
            for item in matching
        ),
        "completion_push_click_url": matching[-1].get("click") if matching else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    assert content == "OWUI_PUSH_OK", result
    assert saw_done, result
    assert len(matching) == 1, result
    assert result["completion_push_content_free"], result
    assert result["completion_push_click_url"] == click_url, result


if __name__ == "__main__":
    asyncio.run(main())
