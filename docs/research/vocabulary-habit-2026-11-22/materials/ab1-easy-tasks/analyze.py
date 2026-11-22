import json, re, difflib, itertools, statistics as st, sys

D = json.load(open(sys.argv[1] + "/blind.json"))
M = json.load(open(sys.argv[1] + "/mapping.json"))
J = {l.split(": ")[0]: l.split(": ")[1] for l in open(sys.argv[1] + "/judgments.txt").read().strip().splitlines()}

DEM = re.compile(r"(これ|それ|あれ|この|その|あの|ここ|そこ|同じ|前述|上記|当該|該当)")
IDIOM = re.compile(r"(そのため|それから|それでも|それぞれ|そのまま|その他|その後|この後|これから|これまで)")

outs = {}
for p in D["pairs"]:
    m = M[p["id"]]
    outs[(p["task"], m["A"], p["id"])] = p["a"]
    outs[(p["task"], m["B"], p["id"])] = p["b"]

def dem(s):
    s2 = IDIOM.sub("", s)
    return len(DEM.findall(s2))

def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

for t in [x["id"] for x in D["tasks"]]:
    print("==", t)
    for c in ["en", "ja"]:
        xs = [v for (tt, cc, _), v in outs.items() if tt == t and cc == c]
        print(c, "len", [len(x) for x in xs], "dem", [dem(x) for x in xs],
              "dem/1000", round(1000 * sum(dem(x) for x in xs) / sum(len(x) for x in xs), 1))
    en = [v for (tt, cc, _), v in outs.items() if tt == t and cc == "en"]
    ja = [v for (tt, cc, _), v in outs.items() if tt == t and cc == "ja"]
    within = [sim(a, b) for a, b in itertools.combinations(en, 2)] + [sim(a, b) for a, b in itertools.combinations(ja, 2)]
    between = [sim(a, b) for a in en for b in ja]
    pair = []
    for p in D["pairs"]:
        if p["task"] == t:
            pair.append(round(sim(p["a"], p["b"]), 2))
    print("sim within-cond", round(st.mean(within), 2), "between-cond", round(st.mean(between), 2), "pair", pair)
    print("votes", [J[p["id"]] for p in D["pairs"] if p["task"] == t])
