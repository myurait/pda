import json, subprocess, sys, os, concurrent.futures as cf

D = sys.argv[1]
HOME = os.path.expanduser("~/.claude")
base = open(HOME + "/CLAUDE.md").read()
base = base.replace("@memory/communication-index.md", open(HOME + "/memory/communication-index.md").read())
base = base.replace("@MEMORY.md", open(HOME + "/MEMORY.md").read())
assert "- Respond in Japanese." in base
CONDS = {
    "en": base.replace("- Respond in Japanese.", "- Always Think in English, but respond in Japanese."),
    "ja": base,
}
TASKS = ["t1", "t2", "t3"]
RUNS = 2
TAIL = "\n\nここでは、ツールは使えません。ここまでの作業で分かったことをもとに、直前のユーザーの発言への応答を、ユーザーに向けて書いてください。"


def prompt(t):
    s = open(f"{D}/{t}/summary.txt").read()
    turn = open(f"{D}/{t}/turn.txt").read()
    return ("このセッションは、前半の会話をコンテキストの上限のために要約し、その続きから再開しています。\n\n"
            "<前半の会話の要約>\n" + s + "\n</前半の会話の要約>\n\n"
            "<要約の後の会話>\n" + turn + "\n</要約の後の会話>" + TAIL)


def run(c, t, i):
    path = f"{D}/out/{t}.{c}.{i}.json"
    if os.path.exists(path):
        return path
    cmd = ["claude", "-p", "--setting-sources", "", "--model", "opus", "--effort", "medium", "--tools", "",
           "--no-session-persistence", "--output-format", "json", "--append-system-prompt", CONDS[c]]
    r = subprocess.run(cmd, input=prompt(t), capture_output=True, text=True, timeout=1800)
    d = json.loads(r.stdout)
    json.dump({"cond": c, "task": t, "i": i, "result": d.get("result"), "usage": d.get("usage")},
              open(path, "w"), ensure_ascii=False, indent=1)
    return path + f" len={len(d.get('result') or '')}"


if __name__ == "__main__":
    os.makedirs(f"{D}/out", exist_ok=True)
    jobs = [(c, t, i) for t in TASKS for c in CONDS for i in range(RUNS)]
    with cf.ThreadPoolExecutor(6) as ex:
        for f in cf.as_completed([ex.submit(run, *j) for j in jobs]):
            print(f.result(), flush=True)
