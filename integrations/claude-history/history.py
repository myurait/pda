#!/usr/bin/env python3
"""Read stored Claude Code transcripts without starting Claude or writing data."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 8 * 1024 * 1024


def _text(record, include_tools=False):
    message = record.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif include_tools and block.get("type") == "tool_use":
            parts.append("[tool_use %s %s] %s" % (block.get("name", ""), block.get("id", ""), json.dumps(block.get("input"), ensure_ascii=False)))
        elif include_tools and block.get("type") == "tool_result":
            body = block.get("content", "")
            if not isinstance(body, str):
                body = _text({"message": {"content": body}})
            parts.append("[tool_result %s] %s" % (block.get("tool_use_id", ""), body))
    return "\n".join(parts)


def _load(path, warnings, deadline, include_tools=False):
    messages = []
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > MAX_FILE_BYTES:
            raise ValueError("transcript exceeds size limit")
        for line_no, line in enumerate(iter(lambda: stream.readline(MAX_LINE_BYTES + 1), b""), 1):
            if time.monotonic() > deadline:
                raise TimeoutError("history scan deadline exceeded")
            if len(line) > MAX_LINE_BYTES or stream.tell() > MAX_FILE_BYTES:
                raise ValueError("transcript exceeds size limit")
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record is not an object")
            except (ValueError, UnicodeError):
                if len(warnings) >= 1000:
                    raise ValueError("too many malformed transcript records")
                warnings.append({"source": str(path), "line": line_no, "reason": "malformed record skipped (possibly still being written)"})
                continue
            if record.get("type") in ("user", "assistant") and _text(record, include_tools):
                messages.append({"line": line_no, "role": record["type"],
                                 "text": _text(record, include_tools), "timestamp": record.get("timestamp"),
                                 "uuid": record.get("uuid"), "parent_uuid": record.get("parentUuid"),
                                 "cwd": record.get("cwd"), "is_sidechain": record.get("isSidechain", False)})
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            warnings.append({"source": str(path), "reason": "transcript changed during read"})
    return messages


def query(root, action="list", limit=20, offset=0, session_id=None, project=None,
          text_offset=0, text_limit=12000, search="", include_tools=False):
    if action not in ("list", "read", "search"):
        raise ValueError("unsupported action")
    if not 1 <= limit <= 100 or offset < 0 or not 1 <= text_limit <= 100000 or text_offset < 0:
        raise ValueError("invalid pagination limits")
    if action == "search" and not search.strip():
        raise ValueError("nonempty search is required")
    root = Path(root).expanduser().absolute()
    if not root.is_dir():
        raise FileNotFoundError("Claude projects root does not exist")
    if root.resolve() != root:
        raise ValueError("projects root must not contain symlinks")
    warnings = []
    deadline = time.monotonic() + 30
    files = []
    total_bytes = 0
    for folder in root.iterdir():
        if folder.is_symlink() or not folder.is_dir() or (project and folder.name != project):
            continue
        for path in folder.glob("*.jsonl"):
            if path.is_symlink() or not path.is_file() or (session_id and path.stem != session_id):
                continue
            total_bytes += path.stat().st_size
            files.append(path)
            if len(files) > 10000 or total_bytes > 1024 * 1024 * 1024:
                raise ValueError("scan size limit exceeded; narrow by project or session")
            if time.monotonic() > deadline:
                raise TimeoutError("history scan deadline exceeded")
    if action == "read":
        if not session_id:
            raise ValueError("session_id is required for read")
        if len(files) != 1:
            raise ValueError("session not found or ambiguous; specify project")
        messages = _load(files[0], warnings, deadline, include_tools)
        items = []
        for index in range(offset, min(offset + limit, len(messages))):
            row = dict(messages[index])
            text = row["text"]
            start = text_offset if index == offset else 0
            row.update(index=index, source=str(files[0]), text_length=len(text),
                       text_offset=start, text=text[start:start + text_limit],
                       text_next_offset=start + text_limit if start + text_limit < len(text) else None)
            items.append(row)
        return {"ok": True, "action": action, "coverage_complete": not warnings, "warnings": warnings, "total": len(messages), "items": items,
                "next_offset": offset + len(items) if offset + len(items) < len(messages) else None}
    items = []
    for path in files:
        messages = _load(path, warnings, deadline, include_tools)
        if action == "search":
            for index, message in enumerate(messages):
                match = re.search(re.escape(search), message["text"], re.IGNORECASE)
                if match:
                    pos = match.start()
                    items.append({"session_id": path.stem, "project": path.parent.name,
                                  "source": str(path), "line": message["line"],
                                  "message_index": index, "role": message["role"],
                                  "timestamp": message["timestamp"],
                                  "snippet": message["text"][max(0, pos - 80):pos + len(search) + 160],
                                  "modified_ns": path.stat().st_mtime_ns})
            continue
        items.append({"session_id": path.stem, "project": path.parent.name,
                      "title": next((m["text"][:200] for m in messages if m["role"] == "user"), ""),
                      "messages": len(messages), "source": str(path),
                      "modified_ns": path.stat().st_mtime_ns})
    items.sort(key=lambda item: (-item["modified_ns"], item["source"]))
    return {"ok": True, "action": action, "coverage_complete": not warnings, "warnings": warnings, "total": len(items), "items": items[offset:offset + limit],
            "next_offset": offset + limit if offset + limit < len(items) else None}


def remote_query(config, request, runner=None):
    """Use an explicitly configured SSH principal, never infer or fall back."""
    import base64
    import re
    import shlex
    import subprocess
    host, user = config.get("host", ""), config.get("user", "")
    if not isinstance(host, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.:-]*", host):
        raise ValueError("connection requires a valid explicit host")
    if not isinstance(user, str) or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", user):
        raise ValueError("connection requires an explicit SSH user")
    port = config.get("port", 22)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("invalid SSH port")
    identity = config.get("identity_file")
    if not isinstance(identity, str) or not identity.strip() or not Path(identity).expanduser().is_file():
        raise ValueError("connection requires an explicit existing identity_file")
    argv = ["/usr/bin/ssh", "-F", "/dev/null", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no", "-o", "IdentitiesOnly=yes",
            "-o", "ClearAllForwardings=yes", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
            "-p", str(port), "-l", user]
    argv += ["-i", str(Path(identity).expanduser())]
    if config.get("known_hosts_file"):
        argv += ["-o", "UserKnownHostsFile=" + str(Path(config["known_hosts_file"]).expanduser())]
    if config.get("host_key_alias"):
        alias = config["host_key_alias"]
        if not isinstance(alias, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]+", alias):
            raise ValueError("invalid host key alias")
        argv += ["-o", "HostKeyAlias=" + alias]
    if config.get("tailscale_binary"):
        proxy = [config["tailscale_binary"], "--socket=" + config["tailscale_socket"], "nc", "%h", "%p"]
        argv += ["-o", "ProxyCommand=" + shlex.join(proxy)]
    payload = base64.b64encode(json.dumps(request).encode()).decode()
    command = [config.get("remote_python", "python3"), "-I", "-B", "-", "--request", payload]
    argv += [host, shlex.join(command)]
    try:
        process = (runner or subprocess.run)(argv, input=Path(__file__).read_text(encoding="utf-8"),
                                             text=True, capture_output=True, timeout=45)
    except subprocess.TimeoutExpired as error:
        raise TimeoutError("remote history read exceeded 45 seconds; no local fallback") from error
    try:
        result = json.loads(process.stdout)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError("invalid result envelope")
    except (ValueError, TypeError) as error:
        raise RuntimeError("SSH history read failed (exit %s): %s" % (process.returncode, process.stderr[:1000])) from error
    if process.returncode and result["ok"]:
        raise RuntimeError("SSH exited unsuccessfully despite a success payload")
    result.update(transport="ssh", host=host, user=user, port=port)
    return result


def main(argv=None):
    import argparse
    import sys
    if argv is None and len(sys.argv) == 3 and sys.argv[1] == "--request":
        import base64
        try:
            result = query(**json.loads(base64.b64decode(sys.argv[2])))
        except (OSError, ValueError, TypeError) as error:
            result = {"ok": False, "error": str(error), "error_type": type(error).__name__}
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "search", "read"))
    parser.add_argument("--root", default="~/.claude/projects", help="projects directory on selected host")
    parser.add_argument("--connection", type=Path, help="explicit SSH connection JSON; never falls back to local")
    parser.add_argument("--project", help="exact project directory name from list")
    parser.add_argument("--session-id")
    parser.add_argument("--search", default="", help="literal, case-insensitive search")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--text-offset", type=int, default=0, help="character offset of first returned message")
    parser.add_argument("--text-limit", type=int, default=12000)
    parser.add_argument("--include-tools", action="store_true", help="include tool calls/results; never thinking blocks")
    args = vars(parser.parse_args(argv))
    try:
        connection = args.pop("connection")
        if connection:
            result = remote_query(json.loads(connection.expanduser().read_text()), args)
        else:
            result = query(**args)
            result["transport"] = "local"
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        result = {"ok": False, "error": str(error), "error_type": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
