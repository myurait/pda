import json, glob, os

D = os.path.dirname(os.path.abspath(__file__))
tasks = []
for f in ["tasks.json", "tasks2.json"]:
    for t in json.load(open(f"{D}/{f}")):
        outs = {"ja": [], "en": [], "tr": []}
        for p in sorted(glob.glob(f"{D}/out/{t['id']}.*.json")):
            d = json.load(open(p))
            r = (d["result"] or "").strip()
            if r.startswith("---"):
                r = r[3:].strip()
            draft = ""
            if d["cond"] == "tr" and "## 日本語" in r:
                draft, r = r.split("## 日本語", 1)
                draft = draft.replace("## English", "").strip()
                r = r.strip()
            outs[d["cond"]].append({"i": d["i"], "text": r, "draft": draft,
                                    "hits": [x for x in t["patterns"] if x in r]})
        tasks.append({"id": t["id"], "word": t["word"], "source_en": t.get("source_en", ""),
                      "constraint": t.get("constraint", ""), "prompt": t["prompt"],
                      "patterns": t["patterns"], "outs": outs})
json.dump({"tasks": tasks}, open(f"{D}/data.json", "w"), ensure_ascii=False, indent=1)
print(len(tasks), sum(len(v) for t in tasks for v in t["outs"].values()))
