import json, glob, os, re, collections

D = os.path.dirname(os.path.abspath(__file__))
IDS = {"m01", "m02", "m03", "m04", "m09", "m10"}
TARGET = {"db_column": "列", "write_back": "書き戻", "collection": "一覧"}

tot = collections.Counter()
hit = collections.Counter()
task = collections.defaultdict(lambda: [0, 0])
outs_with = collections.Counter()
outs = collections.Counter()
for f in sorted(glob.glob(f"{D}/judge/*.json")):
    j = json.load(open(f))
    if j["id"] not in IDS or j["cond"] not in ("en", "ja") or j["i"] > 4:
        continue
    if j["items"] is None:
        print("PARSE_ERROR", j["file"])
        continue
    outs[j["cond"]] += 1
    any_hit = set()
    for it in j["items"]:
        c, w = it.get("concept"), it.get("word") or ""
        if c not in TARGET or not w:
            continue
        tot[(j["cond"], c)] += 1
        task[(j["cond"], j["id"], c)][1] += 1
        if TARGET[c] in w:
            hit[(j["cond"], c)] += 1
            task[(j["cond"], j["id"], c)][0] += 1
            any_hit.add(c)
    for c in any_hit:
        outs_with[(j["cond"], c)] += 1

print("outputs", dict(outs))
for c, w in TARGET.items():
    print(f"\n{c} [{w}]")
    for cond in ["en", "ja"]:
        t = tot[(cond, c)]
        print(f"  {cond}: {hit[(cond, c)]}/{t} ({100 * hit[(cond, c)] / t:.0f}%)" if t else f"  {cond}: 0/0",
              f" 出力のうち1回以上使った数 {outs_with[(cond, c)]}/{outs[cond]}")
    for tid in sorted(IDS):
        row = [f"{cond} {task[(cond, tid, c)][0]}/{task[(cond, tid, c)][1]}" for cond in ["en", "ja"] if task[(cond, tid, c)][1]]
        if row:
            print("   ", tid, " | ".join(row))
