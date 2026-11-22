import json, os, random, sys

OUT = sys.argv[1]
sys.path.insert(0, os.path.dirname(__file__))
from run import TASKS, RUNS

random.seed(20261122)
pairs, mapping = [], {}
for t, prompt in TASKS.items():
    for i in range(RUNS):
        en = json.load(open(f"{OUT}/{t}.en.{i}.json"))
        ja = json.load(open(f"{OUT}/{t}.ja.{i}.json"))
        pid = f"{t}-{i + 1}"
        if random.random() < 0.5:
            a, b, m = en, ja, {"A": "en", "B": "ja"}
        else:
            a, b, m = ja, en, {"A": "ja", "B": "en"}
        mapping[pid] = m
        pairs.append({"id": pid, "task": t, "a": a["result"], "b": b["result"]})

tasks = [{"id": t, "prompt": p} for t, p in TASKS.items()]
json.dump({"tasks": tasks, "pairs": pairs}, open(f"{OUT}/../blind.json", "w"), ensure_ascii=False, indent=1)
json.dump(mapping, open(f"{OUT}/../mapping.json", "w"), indent=1)
cost = sum(json.load(open(f"{OUT}/{f}"))["cost"] or 0 for f in os.listdir(OUT) if f.endswith(".json"))
print("pairs", len(pairs), "cost", round(cost, 2), "empty", [p["id"] for p in pairs if not p["a"] or not p["b"]])
