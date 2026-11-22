import json, subprocess, sys, os, concurrent.futures as cf

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

CONDS = {
    "en": "Always Think in English, but respond in Japanese.",
    "ja": "Respond in Japanese.",
}

TASKS = {
    "t1": "振り返りの手順を書いたスキルがあります。この手順を終えてよい状態を、1文で書いてください。条件は、ユーザーに指摘されたのと同じ失敗が、今後繰り返されないことです。",
    "t2": "次の事実をもとに、チームに向けた障害報告を5文ほどで書いてください。\n- 昨日 14:00〜15:20、商品一覧の価格が古いまま表示された\n- 原因は、価格を更新したときにキャッシュを消す処理が、別の更新処理と同時に走ると消し漏れること\n- 今朝、更新処理を順番に走らせるように直してリリースした\n- 同じことが起きないよう、キャッシュの有効期限も1時間から5分に短くした",
    "t3": "AI エージェントに守らせる規則をファイルに書き溜めています。すでに同じ内容の規則があるのに、エージェントが失敗のたびに新しい規則を作ってしまい、規則が増えすぎて守られなくなりました。なぜこうなるのかと、どうすれば防げるかを、200字ほどで説明してください。",
    "t4": "ジョブの再試行の間隔を、指数バックオフにするか固定間隔にするかを決めたいです。チームのメンバーに、それぞれの良い点と悪い点と、どちらを勧めるかを300字ほどで説明してください。",
    "t5": "次の変更の PR の説明文を書いてください。\n- 変更: ログイン中にセッションの有効期限が切れると、入力途中のフォームの内容が失われていた。期限切れを検知したら入力内容を端末に一時保存し、再ログイン後に戻すようにした\n- 確認したこと: 期限切れの後に再ログインして、入力内容が戻ることを手で確かめた",
}
RUNS = 3


def run(cond, task, i):
    path = os.path.join(OUT, f"{task}.{cond}.{i}.json")
    if os.path.exists(path):
        return path
    cmd = ["claude", "-p", "--setting-sources", "", "--model", "opus", "--tools", "",
           "--no-session-persistence", "--output-format", "json",
           "--append-system-prompt", CONDS[cond], TASKS[task]]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    d = json.loads(r.stdout)
    json.dump({"cond": cond, "task": task, "i": i, "result": d.get("result"),
               "cost": d.get("total_cost_usd"), "usage": d.get("usage")},
              open(path, "w"), ensure_ascii=False, indent=1)
    return path


jobs = [(c, t, i) for t in TASKS for c in CONDS for i in range(RUNS)]
with cf.ThreadPoolExecutor(6) as ex:
    for f in cf.as_completed([ex.submit(run, *j) for j in jobs]):
        print(f.result(), flush=True)
