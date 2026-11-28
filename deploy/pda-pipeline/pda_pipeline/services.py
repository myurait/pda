"""常駐が外へ出す呼び出し: T3 Code (MCP と CLI)、ntfy。報告係は writer.py にある。"""
import asyncio
import json
import pathlib
import urllib.request
import uuid

ROLES_DIR = pathlib.Path(__file__).resolve().parent.parent / "roles"
# Codex を、文を返すだけの形で起動する指定。コマンドの実行と、アプリ・plugin・ブラウザの操作を無効にする。
# 渡す材料には、別の環境から来た文 (開発 PC の返信、Web のページ) が入るので、ミニ PC のファイルを取得させない
CODEX_NO_TOOLS = ["--disable", "shell_tool", "--disable", "unified_exec", "--disable", "apps", "--disable", "plugins",
                  "--disable", "browser_use", "--disable", "computer_use"]


def _mcp_post(endpoint, authorization, body, session=None):
    headers = {"authorization": authorization, "content-type": "application/json",
               "accept": "application/json, text/event-stream"}
    if session:
        headers["mcp-session-id"] = session
    req = urllib.request.Request(endpoint, data=json.dumps({"jsonrpc": "2.0", **body}).encode("utf-8"),
                                 method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=60) as res:
        session = res.headers.get("mcp-session-id") or session
        text = res.read().decode("utf-8")
    if "id" not in body:
        return session, None
    if not text.lstrip().startswith("{"):
        data = [ln[5:].strip() for ln in text.split("\n") if ln.startswith("data:")]
        text = data[-1] if data else "{}"
    return session, json.loads(text)


def _t3_mcp_call(endpoint, authorization, name, arguments):
    session, _ = _mcp_post(endpoint, authorization, {"id": "init", "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "pda-pipeline", "version": "1"}}})
    _mcp_post(endpoint, authorization, {"method": "notifications/initialized"}, session)
    _, out = _mcp_post(endpoint, authorization, {"id": str(uuid.uuid4()), "method": "tools/call",
                                                "params": {"name": name, "arguments": arguments}}, session)
    result = (out or {}).get("result") or {}
    if (out or {}).get("error") or result.get("isError"):
        raise RuntimeError(json.dumps(out, ensure_ascii=False)[:500])
    return result.get("structuredContent") or {}


async def t3_mcp_call(t3, name, arguments):
    return await asyncio.to_thread(_t3_mcp_call, t3["endpoint"], t3["authorization"], name, arguments)


async def t3_thread_send(cfg, thread_id, text):
    proc = await asyncio.create_subprocess_exec(
        cfg["t3_bin"], "thread", "send", "--base-dir", cfg["t3_base_dir"], thread_id, text,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await asyncio.wait_for(proc.communicate(), 60)
    if proc.returncode != 0:
        raise RuntimeError(out.decode("utf-8", "replace")[-400:])


def _ntfy(env_file, title, message, click):
    conf = {}
    for line in pathlib.Path(env_file).read_text(encoding="utf-8").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and not name.startswith("#"):
            conf[name.strip()] = value.strip().strip("'\"")
    payload = {"topic": conf["NTFY_TOPIC"], "title": title, "message": message, "priority": 4}
    if click:
        payload["click"] = click
    req = urllib.request.Request(conf.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/"),
                                 data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.status


async def notify(cfg, title, message):
    n = cfg["notify"]
    if not n["enabled"]:
        return "disabled"
    try:
        return await asyncio.to_thread(_ntfy, n["env_file"], title[:80], message[:400], n.get("click"))
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}: {exc}"
