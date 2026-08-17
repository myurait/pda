import asyncio
import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import aiohttp

ROOT = Path(__file__).parents[1]
HERMES_URL = "http://127.0.0.1:8642/v1"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


async def ntfy_message_ids(client, server: str, topic: str) -> set[str]:
    url = f"{server.rstrip('/')}/{quote(topic, safe='-_')}/json?poll=1&since=all"
    async with client.get(url, allow_redirects=False) as response:
        if response.status != 200:
            raise RuntimeError(f"ntfy poll failed ({response.status})")
        events = [
            json.loads(line)
            for line in (await response.text()).splitlines()
            if line.strip()
        ]
    return {
        str(event["id"])
        for event in events
        if event.get("event") == "message"
    }


async def main() -> None:
    env = load_env(ROOT / ".env")
    api_key = env["HERMES_API_KEY"]
    ntfy_server = env["PDA_NTFY_SERVER_URL"]
    ntfy_topic = env["PDA_NTFY_TOPIC"]
    session_id = f"api-notify-probe-{uuid.uuid4().hex[:16]}"
    session_key = f"probe:async:{session_id}"

    timeout = aiohttp.ClientTimeout(total=600, connect=15, sock_read=600)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Hermes-Session-Key": session_key,
    }
    async with aiohttp.ClientSession(timeout=timeout) as client:
        before = await ntfy_message_ids(client, ntfy_server, ntfy_topic)
        async with client.post(
            f"{HERMES_URL}/runs",
            headers=headers,
            json={
                "input": "Reply exactly ASYNC_NO_PUSH_OK and nothing else. Do not use tools.",
                "session_id": session_id,
                "model": "hermes-agent",
            },
            allow_redirects=False,
        ) as response:
            body = await response.text()
            if response.status != 202:
                raise RuntimeError(f"Hermes run creation failed ({response.status}): {body[:500]}")
            run_id = str(json.loads(body)["run_id"])

        event_headers = dict(headers)
        event_headers["Accept"] = "text/event-stream"
        terminal_event = None
        output = ""
        async with client.get(
            f"{HERMES_URL}/runs/{run_id}/events",
            headers=event_headers,
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"Hermes events failed ({response.status})")
            buffer = ""
            async for chunk in response.content.iter_any():
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    event = json.loads(payload)
                    event_type = str(event.get("event") or "")
                    if event_type == "run.completed":
                        output = str(event.get("output") or "")
                    if event_type in {"run.completed", "run.failed", "run.cancelled"}:
                        terminal_event = event_type
                        break
                if terminal_event:
                    break

        await asyncio.sleep(2)
        after = await ntfy_message_ids(client, ntfy_server, ntfy_topic)

    unexpected = after - before
    result = {
        "session_class": "direct_async_api",
        "session_id_has_owui_prefix": session_id.startswith("owui_"),
        "terminal_event": terminal_event,
        "output": output.strip(),
        "new_completion_push_count": len(unexpected),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert terminal_event == "run.completed", result
    assert output.strip() == "ASYNC_NO_PUSH_OK", result
    assert not unexpected, result


if __name__ == "__main__":
    asyncio.run(main())
