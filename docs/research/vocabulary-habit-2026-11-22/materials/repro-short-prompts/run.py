import json, subprocess, sys, os, concurrent.futures as cf

D = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~/.claude")
base = open(HOME + "/CLAUDE.md").read()
base = base.replace("@memory/communication-index.md", open(HOME + "/memory/communication-index.md").read())
base = base.replace("@MEMORY.md", open(HOME + "/MEMORY.md").read())
LINE = "- Respond in Japanese."
assert LINE in base
CONDS = {
    "ja": base,
    "en": base.replace(LINE, "- Always Think in English, but respond in Japanese."),
    "tr": base.replace(LINE, "- Write the answer in English first, then translate it into Japanese. "
                             "Output both: the English draft under the heading '## English', "
                             "then the Japanese translation under the heading '## 日本語'."),
}
RUNS = int(os.environ.get("RUNS", "4"))
TASKS = json.load(open(f"{D}/" + os.environ.get("TASKS_FILE", "tasks.json")))


def run(c, t, i):
    path = f"{D}/out/{t['id']}.{c}.{i}.json"
    if os.path.exists(path):
        return path + " skip"
    cmd = ["claude", "-p", "--setting-sources", "", "--model", "opus", "--effort", "low", "--tools", "",
           "--no-session-persistence", "--output-format", "json", "--append-system-prompt", CONDS[c]]
    r = subprocess.run(cmd, input=t["prompt"], capture_output=True, text=True, timeout=900)
    d = json.loads(r.stdout)
    if d.get("is_error"):
        return path + " ERROR " + str(d.get("result"))[:200]
    json.dump({"cond": c, "id": t["id"], "i": i, "result": d.get("result"), "usage": d.get("usage")},
              open(path, "w"), ensure_ascii=False, indent=1)
    return path + f" len={len(d.get('result') or '')}"


if __name__ == "__main__":
    os.makedirs(f"{D}/out", exist_ok=True)
    jobs = [(c, t, i) for t in TASKS for c in CONDS for i in range(RUNS)]
    with cf.ThreadPoolExecutor(6) as ex:
        for f in cf.as_completed([ex.submit(run, *j) for j in jobs]):
            print(f.result(), flush=True)
