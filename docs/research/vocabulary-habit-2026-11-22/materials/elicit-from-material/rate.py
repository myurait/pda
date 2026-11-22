import json, glob, os, re, collections

D = os.path.dirname(os.path.abspath(__file__))
TARGET = {"db_column": "列", "db_table": "表", "write_back": "書き戻", "step": "段",
          "time_range": "窓", "collection": "一覧"}
EN = {"db_column": r"\bcolumns?\b", "db_table": r"\btables?\b", "write_back": r"writ\w* (it |them |\w+ )?back|saves? (it |them )?back",
      "step": r"\b(stages?|steps?)\b", "time_range": r"\bwindows?\b", "collection": r"\blists?\b"}

tot = collections.Counter()
hit = collections.Counter()
by_task = collections.defaultdict(collections.Counter)
examples = collections.defaultdict(list)
en_draft = collections.Counter()
for f in sorted(glob.glob(f"{D}/judge/*.json")):
    j = json.load(open(f))
    if j["items"] is None:
        print("PARSE_ERROR", j["file"])
        continue
    for it in j["items"]:
        c = it.get("concept")
        if c not in TARGET:
            continue
        w = it.get("word") or ""
        if not w:
            continue
        key = (j["cond"], c)
        tot[key] += 1
        if (re.search(r"(?<!手)段(?![階落])", w) if c == "step" else TARGET[c] in w):
            hit[key] += 1
            by_task[(j["cond"], j["id"])][c] += 1
            examples[key].append(f"{j['file']}: {it.get('quote')}")
    if j["cond"] == "tr":
        draft = json.load(open(f"{D}/out/{j['file']}"))["result"].split("## 日本語")[0]
        for c, p in EN.items():
            if re.search(p, draft, re.I):
                en_draft[c] += 1

for c in TARGET:
    row = []
    for cond in ["en", "tr", "ja"]:
        if tot[(cond, c)]:
            row.append(f"{cond}: {hit[(cond, c)]}/{tot[(cond, c)]} ({100 * hit[(cond, c)] / tot[(cond, c)]:.0f}%)")
    print(f"{c} [{TARGET[c]}]", " | ".join(row), f"| tr英語下書きに出た回数 {en_draft[c]}")
print()
for k, v in examples.items():
    print("##", k)
    for e in v[:8]:
        print("  ", e)
