"""報告係のコンポーネント。オーナーに届く返信と資料を、中のエージェントに作らせる。

中のエージェントとの取り決めは、指示文と入力文を渡すと、文が返ることだけである。
入力文の組み立てと、返った文の整え方は、このモジュールが受け持つ。
呼び出し方・認証・モデルの指定は、エージェントごとの関数 (AGENTS) に閉じ込める。
"""
import asyncio
import html
import json
import os
import pathlib
import re
import tempfile
import time

from . import services

DOCUMENT_ROLE = "reporter-document.md"
DOCUMENT_MAX_BYTES = 2 * 1024 * 1024
MATERIAL_MAX_CHARS = 200000

REPLY_INPUT = """\
## オーナーの依頼
{request}

## 作業するセッションがオーナーに伝えたい内容
{report}
"""
REPLY_REWRITE = """
## 前の下書き
{draft}

## 前の下書きの直す点
{fixes}

前の下書きを、直す点に沿って直した一通を出力してください。
"""
DOCUMENT_INPUT = """\
## オーナーの依頼
{request}

## 資料の題名
{title}

## 作業するセッションが渡した、資料の材料
{material}

## 作業するセッションがオーナーに伝えたい内容 (返信の材料。資料と食い違わないようにする)
{report}
"""
DOCUMENT_REWRITE = """
## 前に作った資料のHTML
{draft}

## 前に作った資料の直す点
{fixes}

前に作った資料を、直す点に沿って直したHTMLの全文を出力してください。
"""
FALLBACK_HTML = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>body{{margin:16px;font-family:sans-serif;line-height:1.7}}pre{{white-space:pre-wrap;word-break:break-word}}</style>
</head><body><h1>{title}</h1><pre>{material}</pre></body></html>
"""


class WriterError(RuntimeError):
    """中のエージェントが、期限までに文を返さなかった。"""


def agent_conf(cfg):
    """(中のエージェントの名前, その設定) を返す。"""
    role = cfg["roles"]["reporter"]
    name = role.get("agent", "claude")
    conf = (role.get("agents") or {}).get(name)
    if conf is None:
        conf = {k: v for k, v in role.items() if k not in ("agent", "agents")}
    return name, conf


async def _communicate(cmd, cwd, env, prompt, timeout):
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(prompt.encode("utf-8")), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("timeout") from None
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


async def _claude(cfg, conf, system, prompt, timeout, kind):
    with tempfile.TemporaryDirectory(prefix="pda-writer-") as tmp:
        role_file = pathlib.Path(tmp, "system.md")
        role_file.write_text(system, encoding="utf-8")
        cmd = [cfg["claude_bin"], "-p", "--model", conf["model"], "--effort", conf.get("effort", "low"),
               "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
               "--output-format", "json", "--system-prompt-file", str(role_file)]
        code, out, err = await _communicate(cmd, cfg["data_dir"], services.claude_env(cfg), prompt, timeout)
    try:
        data = json.loads(out)
    except ValueError:
        raise RuntimeError(f"exit={code} {out[-300:]!r} {err[-300:]!r}") from None
    text = (data.get("result") or "").strip()
    if data.get("is_error") or not text:
        raise RuntimeError(f"exit={code} {out[-300:]!r} {err[-300:]!r}")
    return text


async def _codex(cfg, conf, system, prompt, timeout, kind):
    with tempfile.TemporaryDirectory(prefix="pda-writer-") as tmp:
        result = pathlib.Path(tmp, "out.txt")
        cmd = [cfg["codex_bin"], "exec", "-", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
               "--sandbox", "read-only", *services.CODEX_NO_TOOLS, "-m", conf["model"],
               "-c", f"model_reasoning_effort={conf.get('effort', 'low')}", "-o", str(result)]
        env = services.codex_env(cfg)
        # Codex には指示文を渡す引数が無いので、入力文の前に置く
        full = (f"# 指示\n\n{system}\n\n# 入力\n\n{prompt}\n\n"
                "指示に従い、出力だけを返してください。ファイルの操作とコマンドの実行はしません。")
        code, _, err = await _communicate(cmd, tmp, env, full, timeout)
        text = result.read_text(encoding="utf-8").strip() if result.is_file() else ""
    if not text:
        raise RuntimeError(f"exit={code} {err[-300:]!r}")
    return text


async def _fixed(cfg, conf, system, prompt, timeout, kind):
    """試験用。設定の文をそのまま返す。fail の回数だけ、先に失敗する。"""
    await asyncio.sleep(conf.get("delay", 0))
    conf["_calls"] = conf.get("_calls", 0) + 1
    if conf["_calls"] <= conf.get("fail", 0):
        raise RuntimeError("fixed failure")
    return conf.get(kind) or ("<!doctype html><title>固定の資料</title><p>固定の資料</p>" if kind == "document"
                              else "固定の返信です。")


AGENTS = {"claude": _claude, "codex": _codex, "fixed": _fixed}


async def run_agent(cfg, sems, system, prompt, deadline, kind):
    """中のエージェントに文を作らせる。失敗したら期限まで再試行し、それでも返らなければ WriterError を投げる。"""
    name, conf = agent_conf(cfg)
    role = cfg["roles"]["reporter"]
    per_call, attempts = role.get("timeout_sec", 300), role.get("attempts", 3)
    errors = []
    for i in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            errors.append("deadline")
            break
        try:
            async with sems.get(name) or sems["default"]:
                return await AGENTS[name](cfg, conf, system, prompt, min(per_call, remaining), kind)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}"[:300])
            if i + 1 < attempts:
                await asyncio.sleep(min(role.get("retry_wait_sec", 10), max(0, deadline - time.monotonic())))
    raise WriterError({"agent": name, "kind": kind, "errors": errors})


def _system(name, extra=""):
    text = (services.ROLES_DIR / name).read_text(encoding="utf-8")
    return f"{text}\n\n{extra}" if extra else text


async def write_reply(cfg, sems, request, report, deadline, draft=None, fixes=None, extra=""):
    """返信の一通を作らせる。extra は、役の指示のあとに置く、規約の節。"""
    prompt = REPLY_INPUT.format(request=request, report=report)
    if draft is not None:
        prompt += REPLY_REWRITE.format(draft=draft, fixes="\n".join(f"- {f}" for f in fixes or []))
    return await run_agent(cfg, sems, _system("reporter.md", extra), prompt, deadline, "reply")


_FENCE = re.compile(r"^```[a-zA-Z]*\n(.*?)\n```\s*$", re.S)
_START = re.compile(r"<!doctype html|<html[\s>]", re.I)


def clean_html(text, title):
    """中のエージェントが返した文から、HTML の全文を取り出す。HTML でなければ ValueError を投げる。"""
    text = text.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1).strip()
    m = _START.search(text)
    if m:
        text = text[m.start():]
    end = text.lower().rfind("</html>")
    if end != -1:
        text = text[:end + len("</html>")]
    if not re.search(r"<(body|main|section|div|p|h1|table|svg)[\s>]", text, re.I):
        raise ValueError("HTML の本文が無い")
    if not re.search(r"<title[\s>]", text, re.I):
        head = re.search(r"<head[^>]*>", text, re.I)
        tag = f"<title>{html.escape(title)}</title>"
        text = text[:head.end()] + tag + text[head.end():] if head else tag + "\n" + text
    if len(text.encode("utf-8")) > DOCUMENT_MAX_BYTES:
        raise ValueError("HTML が大きすぎる")
    return text


def fallback_html(title, material):
    """報告係を使わない設定のときの資料。材料をそのまま出す。"""
    return FALLBACK_HTML.format(title=html.escape(title), material=html.escape(material))


async def write_document(cfg, sems, request, title, material, report, deadline, draft=None, fixes=None, extra=""):
    """資料の HTML を作らせる。"""
    prompt = DOCUMENT_INPUT.format(request=request, title=title, material=material, report=report)
    if draft is not None:
        prompt += DOCUMENT_REWRITE.format(draft=draft, fixes="\n".join(f"- {f}" for f in fixes or []))
    system = _system(DOCUMENT_ROLE, extra)
    errors = []
    for _ in range(2):
        text = await run_agent(cfg, sems, system, prompt, deadline, "document")
        try:
            return clean_html(text, title)
        except ValueError as exc:
            errors.append(str(exc))
    raise WriterError({"agent": agent_conf(cfg)[0], "kind": "document", "errors": errors})
