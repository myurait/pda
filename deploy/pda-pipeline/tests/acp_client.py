#!/usr/bin/env python3
"""T3 Code の代わりに ACP の口を起こし、依頼を 1 つ送って、届いた出来事を 1 行ずつ出す (確かめ用)。

    acp_client.py <スレッドの ID> <依頼の文> [--deny] [--session <ACP の sessionId>] [--cwd <dir>]

承認の要求には許可を返す (--deny なら拒否)。sessionId を渡すと session/load から始める。
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

SHIM = pathlib.Path(__file__).resolve().parent.parent / "pda-shim"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("thread")
    ap.add_argument("request")
    ap.add_argument("--deny", action="store_true")
    ap.add_argument("--session")
    ap.add_argument("--cwd", default=os.getcwd())
    args = ap.parse_args()
    env = dict(os.environ, T3CODE_THREAD_ID=args.thread)
    proc = subprocess.Popen([sys.executable, str(SHIM), "acp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            env=env, text=True, bufsize=1)
    t0 = time.monotonic()

    def send(obj):
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", **obj}, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    def wait(rid):
        for line in proc.stdout:
            msg = json.loads(line)
            el = round(time.monotonic() - t0, 1)
            if msg.get("method") == "session/update":
                up = msg["params"]["update"]
                kind = up.get("sessionUpdate")
                if kind == "agent_message_chunk":
                    print(el, "MESSAGE", json.dumps(up["content"]["text"], ensure_ascii=False), flush=True)
                else:
                    print(el, kind, up.get("status"), json.dumps(up.get("title") or "", ensure_ascii=False)[:160],
                          flush=True)
            elif msg.get("method") == "session/request_permission":
                print(el, "PERMISSION", json.dumps(msg["params"]["toolCall"].get("title"), ensure_ascii=False),
                      flush=True)
                option = "reject-once" if args.deny else "allow-once"
                send({"id": msg["id"], "result": {"outcome": {"outcome": "selected", "optionId": option}}})
            elif msg.get("id") == rid:
                return msg
        raise SystemExit("常駐との接続が閉じた")

    send({"id": 1, "method": "initialize", "params": {"protocolVersion": 1}})
    wait(1)
    if args.session:
        send({"id": 2, "method": "session/load", "params": {"sessionId": args.session, "cwd": args.cwd,
                                                            "mcpServers": []}})
        wait(2)
        session = args.session
    else:
        send({"id": 2, "method": "session/new", "params": {"cwd": args.cwd, "mcpServers": []}})
        session = wait(2)["result"]["sessionId"]
    print("SESSION", session, flush=True)
    send({"id": 3, "method": "session/prompt", "params": {"sessionId": session, "prompt": [
        {"type": "text", "text": args.request}]}})
    print(round(time.monotonic() - t0, 1), "DONE", json.dumps(wait(3), ensure_ascii=False), flush=True)
    proc.stdin.close()


if __name__ == "__main__":
    main()
