import json, glob, os, re, time, collections, random

ROOT = os.path.expanduser("~/.claude/projects")
SINCE = time.time() - 60 * 86400
PATS = {
    "列": re.compile(r"(?<![行配系並序羅陳整直])列(?![挙車島記])"),
    "書き戻し": re.compile(r"書き戻"),
    "一覧": re.compile(r"一覧"),
    "表": re.compile(r"(?<![発公代図付辞年意報別裏予時一])表(?![示現記明情面紙題彰層せさしす])"),
    "段": re.compile(r"(?<![手階値普特一別算前後各上下中])段(?![階落取ボ])"),
    "窓": re.compile(r"窓"),
}


def text_of(e):
    m = e.get("message") or {}
    c = m.get("content")
    if isinstance(c, str):
        return [("text", c)]
    out = []
    for b in c or []:
        if b.get("type") == "text":
            out.append(("text", b["text"]))
        elif b.get("type") == "tool_use":
            out.append(("tool_use", json.dumps(b.get("input"), ensure_ascii=False)))
        elif b.get("type") == "tool_result":
            cc = b.get("content")
            if isinstance(cc, list):
                cc = " ".join(x.get("text", "") for x in cc if isinstance(x, dict))
            out.append(("tool_result", str(cc)))
    return out


first = collections.defaultdict(list)
sessions = 0
for f in glob.glob(f"{ROOT}/*/*.jsonl"):
    if os.path.getmtime(f) < SINCE:
        continue
    sessions += 1
    seen = set()
    prev = []
    for line in open(f, errors="ignore"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        role = (e.get("message") or {}).get("role")
        blocks = text_of(e) if e.get("type") in ("user", "assistant") else []
        for kind, t in blocks:
            t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S)
            if role == "assistant" and kind == "text":
                for w, p in PATS.items():
                    if w in seen:
                        continue
                    m = p.search(t)
                    if m:
                        seen.add(w)
                        first[w].append({"file": f, "ctx": t[max(0, m.start() - 80):m.end() + 60],
                                         "before": [(k, x[:300]) for k, x in prev[-3:]]})
            prev.append((("U:" if role == "user" else "A:") + kind, t))
            prev = prev[-6:]
random.seed(1)
print("sessions", sessions)
for w, v in first.items():
    print(f"\n##### {w}: sessions with assistant use = {len(v)}")
    for x in random.sample(v, min(6, len(v))):
        print("--- ctx:", x["ctx"].replace("\n", " "))
        for k, b in x["before"]:
            print("    before", k, b.replace("\n", " ")[:200])
