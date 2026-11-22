import json, random, sys

D = sys.argv[1]
TASKS = {
    "t1": "10月28日: 投稿の編集と SyncGbp の書き戻しが重なる事象を、Backlog の課題の本文の案にまとめる場面",
    "t2": "9月16日: 夜間同期が処理能力の上限に当たらない理由を、実測の数値で報告する場面",
    "t3": "11月22日: 振り返りのスキルの出口が「既存の行を書き換えたら OK」という雑なゴールになっていないかを答える場面",
}
random.seed(20261123)
pairs, mapping = [], {}
for t in TASKS:
    for i in range(2):
        en = json.load(open(f"{D}/out/{t}.en.{i}.json"))["result"]
        ja = json.load(open(f"{D}/out/{t}.ja.{i}.json"))["result"]
        pid = f"{t}-{i + 1}"
        if random.random() < 0.5:
            a, b, m = en, ja, {"A": "en", "B": "ja"}
        else:
            a, b, m = ja, en, {"A": "ja", "B": "en"}
        mapping[pid] = m
        pairs.append({"id": pid, "task": t, "a": a, "b": b})
last_user = {}
for t in TASKS:
    turn = open(f"{D}/{t}/turn.txt").read()
    k = turn.find("【ユーザー】\n")
    last_user[t] = turn[k + 7:].split("\n\n【")[0] if k >= 0 else ""
tasks = [{"id": t, "prompt": TASKS[t] + "\n\n直前のユーザーの発言:\n" + last_user[t]} for t in TASKS]
json.dump({"tasks": tasks, "pairs": pairs}, open(f"{D}/blind.json", "w"), ensure_ascii=False, indent=1)
json.dump(mapping, open(f"{D}/mapping.json", "w"), indent=1)
print("pairs", len(pairs), "empty", [p["id"] for p in pairs if not p["a"] or not p["b"]])
