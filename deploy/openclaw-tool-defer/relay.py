#!/usr/bin/python3
"""OpenClaw の MCP サーバーと Claude Code の間に入る中継。

Claude Code から /p/<上流のポート>/mcp で受けた要求を http://127.0.0.1:<上流のポート>/mcp へそのまま送り、
応答をそのまま返す。tools/list の応答だけは、keep-tools.txt に無いツールに
`_meta["anthropic/alwaysLoad"] = false` を付けてから返す (Claude Code は、その印の付いたツールを
ツール検索の後ろに遅延する)。上流は 127.0.0.1 だけに限る。
"""
import http.client
import http.server
import json
import os
import re
import socketserver
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LISTEN_PORT = int(os.environ.get("TOOL_DEFER_PORT", "37191"))
KEEP_FILE = os.environ.get("TOOL_DEFER_KEEP", os.path.join(HERE, "keep-tools.txt"))
LOG_FILE = os.environ.get("TOOL_DEFER_LOG", "")
PATH_RE = re.compile(r"^/p/(\d{2,5})(/mcp)$")
# ブラウザからの要求 (DNS rebinding を含む) を通さないよう、Host は中継自身だけを受け、Origin の付いた要求は断る
ALLOWED_HOSTS = {f"127.0.0.1:{LISTEN_PORT}", f"localhost:{LISTEN_PORT}"}
# 要求と応答のうち、中継が付け直すもの
HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-connection", "host", "content-length"}


def load_keep():
    try:
        with open(KEEP_FILE) as fh:
            return {line.split("#", 1)[0].strip() for line in fh if line.split("#", 1)[0].strip()}
    except OSError:
        return None


def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n"
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a") as fh:
                fh.write(line)
            return
        except OSError:
            pass
    sys.stderr.write(line)


def mark_tools(message, keep):
    """JSON-RPC の応答 1 件の result.tools に印を付ける。付けた数と残した数を返す。"""
    tools = (message.get("result") or {}).get("tools") if isinstance(message, dict) else None
    if not isinstance(tools, list):
        return 0, 0
    deferred = kept = 0
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("name") in keep:
            kept += 1
            continue
        meta = tool.get("_meta") if isinstance(tool.get("_meta"), dict) else {}
        meta["anthropic/alwaysLoad"] = False
        tool["_meta"] = meta
        deferred += 1
    return deferred, kept


def rewrite_json_body(body, keep):
    data = json.loads(body)
    items = data if isinstance(data, list) else [data]
    total = [0, 0]
    for item in items:
        d, k = mark_tools(item, keep)
        total[0] += d
        total[1] += k
    return json.dumps(data, ensure_ascii=False).encode(), total


def rewrite_sse_body(body, keep):
    out, total = [], [0, 0]
    for line in body.decode("utf-8").split("\n"):
        if line.startswith("data:"):
            raw = line[5:].lstrip()
            try:
                data = json.loads(raw)
            except ValueError:
                out.append(line)
                continue
            d, k = mark_tools(data, keep)
            total[0] += d
            total[1] += k
            line = "data: " + json.dumps(data, ensure_ascii=False)
        out.append(line)
    return "\n".join(out).encode(), total


def is_tools_list(body):
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return False
    items = data if isinstance(data, list) else [data]
    return any(isinstance(i, dict) and i.get("method") == "tools/list" for i in items)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _forward(self):
        if self.headers.get("Host") not in ALLOWED_HOSTS or self.headers.get("Origin") is not None:
            self.send_error(403)
            return
        m = PATH_RE.match(self.path)
        if not m:
            self.send_error(404)
            return
        port, rest = int(m.group(1)), m.group(2)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        headers["Host"] = f"127.0.0.1:{port}"
        listing = self.command == "POST" and body is not None and is_tools_list(body)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3600)
            conn.request(self.command, rest, body=body, headers=headers)
            resp = conn.getresponse()
        except OSError as e:
            log(f"upstream-error port={port} {type(e).__name__}")
            self.send_error(502)
            return
        ctype = resp.getheader("Content-Type", "")
        resp_headers = [(k, v) for k, v in resp.getheaders() if k.lower() not in HOP_HEADERS]
        keep = load_keep() if listing else None
        if listing and keep is not None and resp.status == 200:
            raw = resp.read()
            try:
                if "text/event-stream" in ctype:
                    new, total = rewrite_sse_body(raw, keep)
                else:
                    new, total = rewrite_json_body(raw, keep)
                log(f"tools/list port={port} deferred={total[0]} kept={total[1]}")
            except (ValueError, UnicodeDecodeError) as e:
                log(f"tools/list-unparsed port={port} {type(e).__name__}")
                new = raw
            self.send_response(resp.status)
            for k, v in resp_headers:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(new)))
            self.end_headers()
            self.wfile.write(new)
            conn.close()
            return
        # それ以外はそのまま流す。長さが分かれば付け、分からなければ chunked で流す
        self.send_response(resp.status)
        for k, v in resp_headers:
            self.send_header(k, v)
        clen = resp.getheader("Content-Length")
        if clen is not None:
            self.send_header("Content-Length", clen)
            self.end_headers()
            remaining = int(clen)
            while remaining > 0:
                chunk = resp.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        else:
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                while True:
                    chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
        conn.close()

    do_GET = do_POST = do_DELETE = _forward

    def do_HEAD(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._forward()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    server = Server(("127.0.0.1", LISTEN_PORT), Handler)
    log(f"listening 127.0.0.1:{LISTEN_PORT} keep={sorted(load_keep() or [])}")
    server.serve_forever()


if __name__ == "__main__":
    main()
