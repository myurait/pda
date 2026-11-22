import json, glob, os, collections

D = os.path.dirname(os.path.abspath(__file__))
TASKS = {t["id"]: t for f in ["tasks.json", "tasks2.json"] for t in json.load(open(f"{D}/{f}"))}


def ja_part(c, text):
    if c == "tr" and "## 日本語" in text:
        return text.split("## 日本語", 1)[1]
    return text


hits = collections.defaultdict(list)
n = collections.Counter()
think = collections.defaultdict(list)
for f in sorted(glob.glob(f"{D}/out/*.json")):
    d = json.load(open(f))
    t, c = TASKS[d["id"]], d["cond"]
    text = ja_part(c, d["result"] or "")
    n[(t["id"], c)] += 1
    tt = ((d.get("usage") or {}).get("output_tokens_details") or {}).get("thinking_tokens")
    think[c].append(tt)
    found = sorted({p for p in t["patterns"] if p in text})
    if found:
        hits[(t["id"], c)].append((d["i"], found))

for tid, t in TASKS.items():
    row = []
    for c in ["ja", "en", "tr"]:
        row.append(f"{c}={len(hits[(tid, c)])}/{n[(tid, c)]}")
    print(tid, t["word"], " ".join(row), {c: hits[(tid, c)] for c in ["ja", "en", "tr"] if hits[(tid, c)]})
for c, v in think.items():
    v = [x for x in v if x is not None]
    print("thinking_tokens", c, "mean", round(sum(v) / len(v), 1) if v else None, "max", max(v) if v else None)
