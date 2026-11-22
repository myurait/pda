import json, subprocess, sys, os, concurrent.futures as cf

D = sys.argv[1]
PROMPT = """次の会話記録は、Claude Code のセッションでユーザーとアシスタントが交わしたやり取りです。このセッションはコンテキストの上限に近づいたので、ここまでの内容を要約して、新しいコンテキストで作業を続けます。続きの作業に必要なことが失われないように、次の見出しで要約を書いてください。

1. Primary Request and Intent
2. Key Technical Concepts
3. Files and Code Sections
4. Errors and fixes
5. Problem Solving
6. All user messages（ユーザーの発言を、ツールの結果以外すべて、原文のまま）
7. Pending Tasks
8. Current Work
9. Optional Next Step

要約だけを出力してください。

<会話記録>
"""


def run(t):
    dst = f"{D}/{t}/summary.txt"
    if os.path.exists(dst):
        return dst
    hist = open(f"{D}/{t}/history.txt").read()
    cmd = ["claude", "-p", "--setting-sources", "", "--model", "sonnet", "--tools", "",
           "--no-session-persistence", "--output-format", "json"]
    r = subprocess.run(cmd, input=PROMPT + hist + "\n</会話記録>", capture_output=True, text=True, timeout=1800)
    d = json.loads(r.stdout)
    open(dst, "w").write(d.get("result") or "")
    return dst + f" len={len(d.get('result') or '')}"


with cf.ThreadPoolExecutor(3) as ex:
    for f in cf.as_completed([ex.submit(run, t) for t in ["t1", "t2", "t3"]]):
        print(f.result(), flush=True)
