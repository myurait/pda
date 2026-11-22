import json, sys

path, term = sys.argv[1], sys.argv[2]
rows = [json.loads(l) for l in open(path) if l.strip()]
for i, e in enumerate(rows):
    t = e.get("type")
    if t == "system" and e.get("subtype") == "compact_boundary":
        print(i, "COMPACT_BOUNDARY")
        continue
    if e.get("isCompactSummary"):
        print(i, "COMPACT_SUMMARY")
        continue
    msg = e.get("message") or {}
    c = msg.get("content")
    if t == "user" and isinstance(c, str) and not e.get("isMeta"):
        print(i, "USER", c[:60].replace("\n", " "))
    if t == "user" and isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text" and not e.get("isMeta"):
                print(i, "USER", b.get("text", "")[:60].replace("\n", " "))
    if t == "assistant" and isinstance(c, list):
        for b in c:
            if not isinstance(b, dict):
                continue
            kind = b.get("type")
            s = b.get("text") or b.get("thinking") or json.dumps(b.get("input"), ensure_ascii=False) if kind != "tool_result" else ""
            if s and term in s:
                k = s.find(term)
                print(i, "ASSIST", kind, b.get("name", ""), len(s), s[max(0, k - 40):k + 40].replace("\n", " "))
