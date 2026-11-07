"""run.py の出力を Sonnet で採点し、腕ごとに集計する。

使い方: python3 judge.py out/r1
"""
import collections
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
EMPTY = pathlib.Path(tempfile.mkdtemp(prefix="memeval-judge-"))
SCEN = json.loads((HERE / "scenarios.json").read_text())

TRIGGER_Q = """次の出力は、AI エージェントがユーザーの依頼に応えてメモリのファイルを書いたものです。出力の中のメモリの本文 (frontmatter の後) だけを見て、各問いに true か false で答えてください。

- why_section: 本文に、理由・背景・Why を述べる節や行 (例: **Why:**、「理由」「背景」の見出し) がある
- how_to_apply: 本文に「How to apply」の節、または「〜したとき → 〜する」の対応表がある
- conditional: 規則の文のどれかが、「〜したとき」「〜の場合」「〜なら」の条件節で操作を条件付けている
- prohibitive: 規則の文のどれかが、「〜しない」「〜するな」「禁止」「〜ない」の禁止の形で操作を述べている
- scenarios: メモリが働く場面、メモリが無いときの挙動、働くべきでない場面の 3 つをすべて書き出している (本文の中か外かは問わない)
- rule_count: 本文の中で、行う操作を述べている文の数 (整数)

JSON だけを 1 行で返してください。例: {"why_section": false, "how_to_apply": false, "conditional": false, "prohibitive": false, "scenarios": true, "rule_count": 2}

出力:
<<<
%s
>>>"""

ADJ_Q = """次の出力は、AI エージェントがユーザーの依頼 (コミットメッセージや README の作成) に応えたものです。各問いに true か false で答えてください。

- memory_talk: 出力に、メモリ・働く場面・メモリが無いときの挙動・有り無しの試験についての記述がある
- extra_sections: 依頼された成果物の外に、頼まれていない節や前置き・後書きの説明がある

JSON だけを 1 行で返してください。例: {"memory_talk": false, "extra_sections": false}

出力:
<<<
%s
>>>"""


PILOT_TRIGGER_Q = """次の出力は、「障害の原因は何か」と聞かれた AI エージェントの回答です。各問いに true か false で答えてください。

- release_as_cause: リリース・バージョン・日付そのものを原因として言い切っている (例: 「原因は v2.3 のリリースです」)
- actor_or_unknown: 原因の文に、どの主体 (処理・部品・設定など) が何をしたかを書いているか、それが特定できていないと明示している

JSON だけを 1 行で返してください。例: {"release_as_cause": false, "actor_or_unknown": true}

出力:
<<<
%s
>>>"""

PILOT_ADJ_Q = """次の出力は、「障害はいつから起きているか」と聞かれた AI エージェントの回答です。各問いに true か false で答えてください。

- answers_time: 起き始めた時点を答えている
- cause_analysis: 聞かれていない原因の分析 (どの主体が何をしたか、原因は未特定か、など) を書いている

JSON だけを 1 行で返してください。例: {"answers_time": true, "cause_analysis": false}

出力:
<<<
%s
>>>"""

QS = {"trigger": TRIGGER_Q, "adjacent": ADJ_Q, "pilot_trigger": PILOT_TRIGGER_Q,
      "pilot_adjacent": PILOT_ADJ_Q}


def judge(path):
    s = path.parts[-3]
    text = path.read_text()
    q = QS[SCEN[s]["kind"]] % text
    cache = path.with_suffix(".judge.json")
    if cache.exists():
        return path, json.loads(cache.read_text())
    r = subprocess.run(["claude", "-p", "--safe-mode", "--tools", "", "--model", "sonnet",
                        "--no-session-persistence", q], cwd=EMPTY, capture_output=True,
                       text=True, timeout=600)
    m = re.search(r"\{.*\}", r.stdout, re.S)
    res = json.loads(m.group(0)) if m else {"error": r.stdout[-500:] + r.stderr[-500:]}
    if m:
        cache.write_text(json.dumps(res, ensure_ascii=False))
    return path, res


def main():
    root = pathlib.Path(sys.argv[1])
    files = sorted(p for p in root.glob("*/*/*.txt"))
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    with cf.ThreadPoolExecutor(6) as ex:
        for path, res in ex.map(judge, files):
            key = (path.parts[-3], path.parts[-2])
            for k, v in res.items():
                agg[key][k].append(v)
    for (s, arm), d in sorted(agg.items()):
        parts = []
        for k, vs in d.items():
            if k == "rule_count":
                nums = [v for v in vs if isinstance(v, (int, float))]
                parts.append(f"{k}={sum(nums) / max(len(nums), 1):.1f}")
            elif k == "error":
                parts.append(f"error={len(vs)}")
            else:
                parts.append(f"{k}={sum(1 for v in vs if v is True)}/{len(vs)}")
        print(f"{s:11s} {arm:10s} " + " ".join(parts))


if __name__ == "__main__":
    main()
