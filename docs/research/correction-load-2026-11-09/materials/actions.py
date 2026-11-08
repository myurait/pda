"""使い方: python3 -I actions.py <元の記録 jsonl> <開始 ISO 時刻> <終了 ISO 時刻>
2 つの時刻の間に Claude が呼んだ道具 (名前と主な引数) を時刻順に出す。サブエージェントの呼び出しは除く。"""
import json, sys

path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
KEYS = ("file_path", "command", "url", "description", "prompt", "title", "action", "skill", "query", "pattern")
for line in open(path, errors="replace"):
    try:
        d = json.loads(line)
    except Exception:
        continue
    ts = d.get("timestamp") or ""
    if d.get("isSidechain") or d.get("type") != "assistant" or not (start <= ts <= end):
        continue
    for b in (d.get("message") or {}).get("content") or []:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            inp = b.get("input") or {}
            parts = []
            for k in KEYS:
                if k in inp and isinstance(inp[k], str):
                    parts.append(f"{k}={inp[k][:160]!r}")
            print(ts[11:19], b.get("name"), " ".join(parts))
