import json, sys

path, line = sys.argv[1], int(sys.argv[2])
rows = [json.loads(l) for l in open(path) if l.strip()]
for i in range(max(0, line - 3), line + 1):
    e = rows[i]
    u = (e.get("message") or {}).get("usage")
    if u:
        tot = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        print(i, e.get("type"), (e.get("message") or {}).get("model"), "context_tokens", tot)
for i, e in enumerate(rows[:line]):
    if e.get("type") == "system" or e.get("isCompactSummary") or "compact" in json.dumps(e.get("subtype", "")):
        if "compact" in json.dumps(e, ensure_ascii=False)[:400].lower():
            print(i, e.get("type"), e.get("subtype"), json.dumps(e, ensure_ascii=False)[:160])
