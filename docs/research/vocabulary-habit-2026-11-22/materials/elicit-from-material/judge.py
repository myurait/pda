import json, subprocess, os, glob, re, concurrent.futures as cf

D = os.path.dirname(os.path.abspath(__file__))
os.makedirs(f"{D}/judge", exist_ok=True)

GUIDE = """次の日本語の文章から、下の6種類の対象を名指している箇所をすべて抜き出してください。

- db_column: データベースのテーブルのカラム
- db_table: データベースのテーブル
- write_back: 先に読んだ値を、データベースや外部へ保存し直す・更新し直す処理
- step: 処理・手順・パイプラインの中の1つのステップ、ジョブ、段階
- time_range: 時間の範囲・幅・期間・すき間
- collection: 配列・リスト・マップ・スライスなどのデータ構造、またはデータを集めて計算した結果の全体

識別子（`post_groups` のようなコード上の名前）だけで指していて日本語の名詞が付いていない箇所は、word を空文字にしてください。
1つの対象が文中で何度も名指されていれば、名指した回数だけ抜き出してください。

出力は JSON の配列だけにしてください。説明や前置きは書かないでください。各要素は次の形です。
{"concept": "db_column", "word": "名指すのに使った日本語の名詞（例: カラム）", "quote": "その箇所を含む40字以内の引用"}

文章:
"""


def ja_part(c, text):
    if c == "tr" and "## 日本語" in text:
        return text.split("## 日本語", 1)[1]
    return text


def judge(path):
    name = os.path.basename(path)
    outp = f"{D}/judge/{name}"
    if os.path.exists(outp):
        return outp + " skip"
    d = json.load(open(path))
    text = ja_part(d["cond"], d["result"] or "")
    cmd = ["claude", "-p", "--setting-sources", "", "--model", "sonnet", "--effort", "low", "--tools", "",
           "--no-session-persistence", "--output-format", "json"]
    r = subprocess.run(cmd, input=GUIDE + text, capture_output=True, text=True, timeout=600)
    res = json.loads(r.stdout).get("result") or ""
    m = re.search(r"\[.*\]", res, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except Exception:
        items = None
    json.dump({"file": name, "cond": d["cond"], "id": d["id"], "i": d["i"], "items": items, "raw": res},
              open(outp, "w"), ensure_ascii=False, indent=1)
    return outp + f" n={len(items) if items is not None else 'PARSE_ERROR'}"


if __name__ == "__main__":
    files = sorted(glob.glob(f"{D}/out/*.json"))
    with cf.ThreadPoolExecutor(6) as ex:
        for f in cf.as_completed([ex.submit(judge, p) for p in files]):
            print(f.result(), flush=True)
