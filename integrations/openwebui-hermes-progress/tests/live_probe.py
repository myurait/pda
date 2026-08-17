import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "functions" / "hermes_progress_pipe.py"
spec = importlib.util.spec_from_file_location("hermes_progress_pipe_live", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Pipe = module.Pipe


def load_env(path):
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def extract_visible_content(chunks):
    parts = []
    for chunk in chunks:
        if not chunk.startswith("data: ") or chunk.startswith("data: [DONE]"):
            continue
        payload = json.loads(chunk[6:].strip())
        delta = payload.get("choices", [{}])[0].get("delta", {})
        parts.append(delta.get("content", ""))
    return "".join(parts)


async def main():
    env = load_env(ROOT / ".env")
    key = env["HERMES_API_KEY"]
    base = "http://127.0.0.1:8642/v1"
    session_id = f"owui_pipe_live_probe_{int(time.time())}"
    session_key = "openwebui:live-probe"

    pipe = Pipe()
    pipe.valves.HERMES_API_URL = base
    pipe.valves.HERMES_API_KEY = key
    pipe.valves.HERMES_MODEL = "hermes-agent"
    pipe.valves.SHOW_TOOL_PREVIEW = False

    emitted = []

    async def emitter(event):
        emitted.append(event)

    chunks = [
        chunk
        async for chunk in pipe._stream_response(
            message=(
                "Use the terminal tool to run printf 'HERMES_PROGRESS_PIPE_PROBE\\n'. "
                "After the tool succeeds, reply exactly PIPE_LIVE_OK and nothing else."
            ),
            history=[],
            instructions=None,
            session_id=session_id,
            session_key=session_key,
            event_emitter=emitter,
            event_call=None,
        )
    ]
    content = extract_visible_content(chunks)
    statuses = [
        event.get("data", {})
        for event in emitted
        if event.get("type") == "status"
    ]

    transcript = None
    transcript_status = None
    headers = {"Authorization": f"Bearer {key}"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
        async with client.get(
            f"http://127.0.0.1:8642/api/sessions/{session_id}/messages",
            headers=headers,
        ) as response:
            transcript_status = response.status
            if response.status == 200:
                transcript = await response.json()

    transcript_text = json.dumps(transcript, ensure_ascii=False) if transcript is not None else ""
    result = {
        "visible_content": content,
        "status_descriptions": [item.get("description") for item in statuses],
        "saw_tool_started": any(
            str(item.get("description", "")).startswith("実行中:") for item in statuses
        ),
        "saw_tool_completed": any(
            str(item.get("description", "")).startswith("完了:") for item in statuses
        ),
        "final_status_done": bool(statuses and statuses[-1].get("done") is True),
        "assistant_content_has_status_marker": any(
            marker in content for marker in ("実行中:", "完了: terminal", "Hermesが処理を開始")
        ),
        "transcript_http_status": transcript_status,
        "transcript_has_ui_status_marker": any(
            marker in transcript_text
            for marker in ("実行中:", "完了: terminal", "Hermesが処理を開始しました")
        ),
        "session_id": session_id,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    assert content.strip() == "PIPE_LIVE_OK", result
    assert result["saw_tool_started"], result
    assert result["saw_tool_completed"], result
    assert result["final_status_done"], result
    assert not result["assistant_content_has_status_marker"], result
    assert transcript_status == 200, result
    assert not result["transcript_has_ui_status_marker"], result


if __name__ == "__main__":
    asyncio.run(main())
