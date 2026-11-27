"""常駐が外へ出す呼び出し: T3 Code (MCP と CLI)、ntfy、報告係。"""
import asyncio
import json
import os
import pathlib
import urllib.request
import uuid

SCRUB_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN",
             "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_ENTRYPOINT"]
ROLES_DIR = pathlib.Path(__file__).resolve().parent.parent / "roles"


def claude_env(cfg, extra=None):
    env = dict(os.environ)
    for key in SCRUB_ENV:
        env.pop(key, None)
    env["CLAUDE_CONFIG_DIR"] = cfg["claude_config_dir"]
    env.update(extra or {})
    return env


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


REPORTER_INPUT = """\
## オーナーの依頼
{request}

## 作業するセッションがオーナーに伝えたい内容
{report}
"""
REPORTER_REWRITE = """
## 前の下書き
{draft}

## 前の下書きの直す点
{fixes}

前の下書きを、直す点に沿って直した一通を出力してください。
"""


async def reporter_write(cfg, sem, request, report, draft=None, fixes=None):
    """報告係に一通を書かせる。失敗したときは例外を投げる。"""
    role = cfg["roles"]["reporter"]
    prompt = REPORTER_INPUT.format(request=request, report=report)
    if draft is not None:
        prompt += REPORTER_REWRITE.format(draft=draft, fixes="\n".join(f"- {f}" for f in fixes))
    cmd = [cfg["claude_bin"], "-p", "--model", role["model"], "--effort", role["effort"], "--tools", "",
           "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence", "--output-format", "json",
           "--system-prompt-file", str(ROLES_DIR / "reporter.md")]
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cfg["data_dir"], env=claude_env(cfg), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(prompt.encode("utf-8")), 300)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("reporter timeout") from None
    data = json.loads(out.decode("utf-8"))
    text = (data.get("result") or "").strip()
    if data.get("is_error") or not text:
        raise RuntimeError(f"reporter failed: {out[-300:]!r} {err[-300:]!r}")
    return text
