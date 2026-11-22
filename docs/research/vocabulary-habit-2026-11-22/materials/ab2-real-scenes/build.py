import json, re, sys, os

path, turn_start, cut, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
rows = [json.loads(l) for l in open(path) if l.strip()]
SR = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def render(e, tr_cap, tu_cap):
    t = e.get("type")
    if e.get("isMeta"):
        return ""
    c = (e.get("message") or {}).get("content")
    out = []
    if t == "user":
        if isinstance(c, str):
            s = SR.sub("", c).strip()
            if s:
                out.append("【ユーザー】\n" + s)
        elif isinstance(c, list):
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    s = SR.sub("", b.get("text", "")).strip()
                    if s:
                        out.append("【ユーザー】\n" + s)
                elif b.get("type") == "tool_result":
                    cc = b.get("content")
                    if isinstance(cc, list):
                        cc = "\n".join(x.get("text", "") for x in cc if isinstance(x, dict))
                    cc = SR.sub("", str(cc or ""))
                    if len(cc) > tr_cap:
                        cc = cc[:tr_cap] + f"\n…(以下 {len(cc) - tr_cap} 字省略)"
                    out.append("【ツールの結果】\n" + cc)
    elif t == "assistant" and isinstance(c, list):
        for b in c:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                out.append("【アシスタント】\n" + b["text"].strip())
            elif b.get("type") == "tool_use":
                s = json.dumps(b.get("input"), ensure_ascii=False)
                if len(s) > tu_cap:
                    s = s[:tu_cap] + f"…(以下 {len(s) - tu_cap} 字省略)"
                out.append(f"【アシスタントのツール呼び出し: {b.get('name')}】\n" + s)
    return "\n\n".join(out)


hist = "\n\n".join(x for x in (render(e, 1500, 1500) for e in rows[:turn_start]) if x)
turn = "\n\n".join(x for x in (render(e, 20000, 4000) for e in rows[turn_start:cut]) if x)
os.makedirs(out, exist_ok=True)
open(out + "/history.txt", "w").write(hist)
open(out + "/turn.txt", "w").write(turn)
print("history chars", len(hist), "turn chars", len(turn))
