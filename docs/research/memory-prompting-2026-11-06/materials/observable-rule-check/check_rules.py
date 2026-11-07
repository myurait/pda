"""規則のメモリの各文を、判定手順の表の手順どおりに機械的に検査する。"""
import re
import sys
import pathlib

path = pathlib.Path(sys.argv[1])
text = path.read_text()
_, fm, body = text.split("---\n", 2)

COND = ["とき", "場合", "なら", "たら", "れば", "際に"]
COND_EN = ["if", "when", "unless"]
PROH = ["しない", "禁止", "てはならない"]
PROH_EN = ["never", "not"]
REASON = ["ため", "ので", "理由", "背景"]
REASON_EN = ["because", "why"]
JUDGE = ["重要", "本質", "適切", "妥当", "十分", "必要", "できる", "なるべく", "意識", "注意",
         "心がけ", "感じ", "迷", "気づ", "自問", "水準", "同じ型", "失敗の型", "分類", "避け", "タスクを越え"]
STOPVERB = ["確認する", "検討する", "検証する", "考える", "判断する", "見直す"]
TOKENS = ["先頭", "末尾", "文末", "直後", "行"]


def outside_quotes(s):
    s = re.sub(r"「[^」]*」", "", s)
    return re.sub(r"`[^`]*`", "", s)


def names_object(s):
    return bool(re.search(r"/|\.md|「[^」]*」|`[^`]*`|[0-9]|見出し", s)) or any(t in s for t in TOKENS)


desc = re.search(r"^description: (.*)$", fm, re.M).group(1)
sentences = [("description", None, desc)]
parent = None
for i, line in enumerate(body.splitlines(), start=1):
    if not line.strip():
        continue
    m = re.match(r"^( *)- (.*)$", line)
    if not m:
        sentences.append((f"本文 {i} 行", None, "<<箇条書きでない行>> " + line))
        continue
    if m.group(1) == "":
        parent = m.group(2)
        sentences.append((f"本文 {i} 行", None, m.group(2)))
    else:
        sentences.append((f"本文 {i} 行", parent, m.group(2)))

fails = 0
for where, par, s in sentences:
    out = outside_quotes(s)
    errs = []
    if s.startswith("<<"):
        errs.append("行の形")
    if s[-1] not in "うくぐすつぬぶむる":
        errs.append(f"文末={s[-3:]}")
    if re.search(r"[A-Za-z]{3,} [A-Za-z]{3,} [A-Za-z]{3,}", out):
        errs.append("英語の文")
    for name, words in [("条件", COND), ("禁止", PROH), ("理由", REASON), ("判断", JUDGE)]:
        hit = [w for w in words if w in out]
        if hit:
            errs.append(f"{name}:{hit}")
    for name, words in [("条件EN", COND_EN), ("禁止EN", PROH_EN), ("理由EN", REASON_EN)]:
        hit = [w for w in words if re.search(rf"\b{w}\b", out, re.I)]
        if name == "禁止EN" and "n't" in out:
            hit.append("n't")
        if hit:
            errs.append(f"{name}:{hit}")
    if any(s.endswith(v) for v in STOPVERB):
        errs.append("確認系の文末")
    if not (names_object(s) or (par and names_object(par))):
        errs.append("名指しなし")
    if out.count("。") > (1 if out.endswith("。") else 0):
        errs.append("2 文以上")
    fails += bool(errs)
    print(("NG " if errs else "OK ") + where + " | " + s[:40] + (" | " + ", ".join(errs) if errs else ""))

# frontmatter
keys_ok = all(re.search(rf"^\s*{k}:", fm, re.M) for k in ["name", "description", "node_type", "type"])
name = re.search(r"^name: (.*)$", fm, re.M).group(1)
print("frontmatter 4 キー:", keys_ok)
print("name 形式:", bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)))
print("node_type=memory:", bool(re.search(r"^\s*node_type: memory$", fm, re.M)))
print("type:", re.search(r"^\s*type: (\S+)", fm, re.M).group(1))
print("本文の日付・課題番号:", re.findall(r"\d{4}-\d{2}-\d{2}|\d+ ?月 ?\d+ ?日|[A-Z]+-\d+|#\d+", body))
sys.exit(1 if fails else 0)
