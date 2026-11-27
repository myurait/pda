"""終端のゲートの判定器。どの判定器も、材料を受け取り、問いごとの合否と理由を返す。

戻り値の形: {"gate": 名前, "seconds": 秒, "results": [{"id", "pass", "reason", "fix"}], ...}
"""
import asyncio
import json
import os
import pathlib
import re
import tempfile
import time
import urllib.error
import urllib.request

RULES_FILE = pathlib.Path(__file__).resolve().parent.parent / "rules.json"

# ひらがな・カタカナ (半角を含む)・漢字・繰り返しの記号の範囲
_JA = (f"{chr(0x3005)}{chr(0x3041)}-{chr(0x30FF)}{chr(0x3400)}-{chr(0x4DBF)}"
       f"{chr(0x4E00)}-{chr(0x9FFF)}{chr(0xFF66)}-{chr(0xFF9F)}")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_LINK = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")
_URL = re.compile(r"https?://\S+")
_QUOTED = re.compile(r"「[^」]*」|『[^』]*』|\"[^\"\n]*\"")
_PATH = re.compile(r"[A-Za-z0-9._~\-]*(?:/[A-Za-z0-9._~\-]+)+/?")
_SPACE_GAP = re.compile(rf"[A-Za-z0-9][ \t]+[{_JA}]|[{_JA}][ \t]+[A-Za-z0-9]")
_LIST_HEAD = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_JA_CHAR = re.compile(rf"[{_JA}]")
_EN_WORD = re.compile(r"[A-Za-z]{2,}")
_DEMONSTRATIVE = re.compile(
    r"これ|それ|あれ|この|その|あの|ここ|そこ|同じ|前述|上記|当該|前者|後者|前の|次の|先の|もう[1１一]つの")


class JudgeTimeout(Exception):
    pass


def load_rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def strip_code(text):
    """コードブロックとインラインのコードを除いた行の一覧を返す。"""
    lines, fence = [], None
    for line in text.split("\n"):
        m = _FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            continue
        if fence is not None:
            s = line.strip()
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                fence = None
            continue
        lines.append(_INLINE_CODE.sub("`", line))
    return lines


_SPACING_FIX = re.compile(
    rf"(`[^`\n]+`|!?\[[^\]\n]*\]\([^)\n]*\)|https?://\S+)"
    rf"|([A-Za-z0-9])[ \t]+(?=[{_JA}])|(?<=[{_JA}])[ \t]+(?=[A-Za-z0-9])")


def fix_spacing(text):
    """報告係の下書きの、英字・数字と日本語の間の空白を詰める。コードブロック・コードの要素・リンク・URL は変えない。"""
    out, fence = [], None
    for line in text.split("\n"):
        m = _FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
        elif fence is not None:
            s = line.strip()
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                fence = None
        elif not line.lstrip().startswith((">", "|")):
            line = _SPACING_FIX.sub(lambda g: g.group(1) or g.group(2) or "", line)
        out.append(line)
    return "\n".join(out)


def has_demonstrative(text):
    return bool(_DEMONSTRATIVE.search("\n".join(strip_code(text))))


def script_gate(draft):
    t0 = time.monotonic()
    results = []
    gaps = []
    english = []
    for line in strip_code(draft):
        if line.lstrip().startswith((">", "|")):
            continue
        body = _LIST_HEAD.sub("", _LINK.sub("", _URL.sub("", line)))
        for m in _SPACE_GAP.finditer(body):
            start = max(0, m.start() - 8)
            gaps.append(body[start:m.end() + 8].strip())
        prose = _PATH.sub(" ", _QUOTED.sub(" ", body)).replace("`", " ")
        if not _JA_CHAR.search(prose) and len(_EN_WORD.findall(prose)) >= 4:
            english.append(line.strip()[:80])
    results.append({
        "id": "44", "pass": not gaps,
        "reason": "英字・数字と日本語の間に空白がある: " + " / ".join(f"「{g}」" for g in gaps[:8]) if gaps else "",
        "fix": "挙げた箇所の、英字・数字と日本語の間の空白を消してください。空白を残してよいのは、バッククォートで囲んだコードの要素の前後だけです。" if gaps else "",
    })
    results.append({
        "id": "47", "pass": not english,
        "reason": "英語だけの行がある: " + " / ".join(f"「{e}」" for e in english[:5]) if english else "",
        "fix": "挙げた行を日本語で書き直してください。識別子・コマンド・パス・引用は原文のままでかまいません。" if english else "",
    })
    return {"gate": "script", "seconds": round(time.monotonic() - t0, 3), "results": results}


def _first_sentence(text):
    lines = [ln for ln in strip_code(text) if ln.strip() and not ln.lstrip().startswith("#")]
    head = lines[0].strip() if lines else ""
    m = re.search(r"[。！？!?]", head)
    return head[:m.end()] if m else head


def _cmp(value, op, bound):
    return value >= bound if op == ">=" else value < bound


def _jev_call(cfg, state, questions):
    key = None
    for line in pathlib.Path(cfg["credentials"]).read_text(encoding="utf-8").splitlines():
        name, _, value = line.strip().partition("=")
        if name.strip() == "API_KEY":
            key = value.strip().strip("'\"")
    body = json.dumps({"state": state, "model": cfg["model"], "questions": questions}, ensure_ascii=False)
    req = urllib.request.Request(cfg["endpoint"], data=body.encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "jev-adapter/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


async def jev_gate(cfg, rules, request, draft):
    """Jev の規則を判定し、Codex の規則が当たるかの見分けも返す。失敗したときは外れなしとして記録だけ残す。"""
    t0 = time.monotonic()
    spec = rules["jev"]
    state = {"owner_request": request[:6000], "reply": draft[:6000], "first_sentence": _first_sentence(draft)}
    out = {"gate": "jev", "results": [], "triggers": {name: True for name in spec["triggers"]}}
    try:
        response = await asyncio.to_thread(_jev_call, cfg, state, spec["questions"])
        scores = {qid: ans.get("noul", 0.0) for qid, ans in response["answers"].items()}
    except Exception as exc:  # noqa: BLE001
        out.update({"error": f"{type(exc).__name__}: {exc}", "seconds": round(time.monotonic() - t0, 2)})
        return out
    out["scores"] = scores
    for rule in spec["rules"]:
        failed = all(_cmp(scores.get(q, 0.0), op, bound) for q, op, bound in rule["fail_when"])
        out["results"].append({"id": rule["id"], "pass": not failed,
                               "reason": rule["name"] if failed else "", "fix": rule["fix"] if failed else ""})
    out["triggers"] = {name: _cmp(scores.get(q, 1.0), op, bound) for name, (q, op, bound) in spec["triggers"].items()}
    out["seconds"] = round(time.monotonic() - t0, 2)
    return out


CODEX_SCHEMA = {
    "type": "object",
    "properties": {
        "completion": {"type": "object", "properties": {
            "pass": {"type": "boolean"}, "reasons": {"type": "array", "items": {"type": "string"}}},
            "required": ["pass", "reasons"], "additionalProperties": False},
        "rules": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "verdict": {"type": "string", "enum": ["pass", "fail", "n/a"]},
            "quote": {"type": "string"}, "reason": {"type": "string"}, "fix": {"type": "string"}},
            "required": ["id", "verdict", "quote", "reason", "fix"], "additionalProperties": False}},
    },
    "required": ["completion", "rules"], "additionalProperties": False,
}

CODEX_PROMPT = """\
あなたは、作業するAIがオーナーに送ろうとしている返事を、外から点検する点検役です。下の材料だけで判定し、指定のJSONだけを返してください。ファイルを開いたり、命令を実行したりしないでください。判定に要る材料はすべてこの入力にあります。

# 判定1: 完了判定 (completion)

- 単位: 返事が「した」「終わった」「できた」「確かめた」と述べている作業の1つずつ。
- 問い: その作業が、「ツールの記録」の呼び出しと結果で確かめられるか。
- pass を false にするのは、次の3つのどれかが1つでもあるときだけにする。
  - (a) 返事が行ったと述べている作業の呼び出しが、ツールの記録に無い。
  - (b) 返事が述べている値・状態が、ツールの記録の結果と食い違っている。
  - (c) ツールの記録の結果がエラーか失敗なのに、返事が成功したと述べている。
- ツールの記録にある結果を、返事が要約・言い換え・推論して述べている部分は、(a)〜(c) に当たらない限り外れにしない。提案や見解の当否は判定しない。
- オーナーの依頼が作業を求めておらず、問いへの答えや会話だけを求めているときは、返事が依頼に答えていれば pass を true にする。知識で答えられる問いに、ツールの記録は要らない。
- 返事が、終わっていないこととその理由を、終わっていないと分かる形で述べている部分は、外れとして数えない。
- pass が false のときは、reasons に、作業するAIが次に何をすればよいかを、日本語で、具体的に書く (どの作業を行うか、何を確かめて示すか)。pass が true のときは reasons を空にする。

# 判定2: 伝え方の規約 (rules)

下の問いごとに、verdict を pass・fail・n/a のどれかで返す。fail のときは、quote に返事の該当箇所をそのまま写し、reason に外れている点を、fix に直し方を日本語で書く。pass と n/a のときは quote・reason・fix を空の文字列にする。挙げた問いだけを判定し、ほかの観点の指摘は足さない。

{checklist}

# 材料

## オーナーの依頼
{request}

## 同じセッションの直前のやり取り (古い順)
{context}

## このターンのツールの記録 (呼び出し → 結果)
{tool_log}

## 作業するAIがオーナーに送ろうとしている返事
{draft}
"""


def codex_checklist(rules, rule_ids):
    items = []
    for rule in rules["codex"]:
        if rule["id"] in rule_ids:
            items.append(f"- id: {rule['id']}\n  - 単位: {rule['unit']}\n  - 読み手: {rule['reader']}\n"
                         f"  - 問い: {rule['question']}")
    return "\n".join(items) or "(問いなし。rules は空の配列で返す)"


def codex_rule_ids(rules, draft, triggers):
    ids = []
    for rule in rules["codex"]:
        trig = rule["trigger"]
        if trig == "always" or (trig == "demonstrative" and has_demonstrative(draft)) or triggers.get(trig, False):
            ids.append(rule["id"])
    return ids


def format_tool_log(tool_log, limits):
    lines = []
    for i, call in enumerate(tool_log, 1):
        inp = json.dumps(call.get("input"), ensure_ascii=False)[:1500]
        res = call.get("result")
        res = "(結果はまだ無い)" if res is None else str(res)[:limits["tool_result_chars"]]
        mark = " [エラー]" if call.get("is_error") else ""
        lines.append(f"{i}. {call['name']} {inp}\n   →{mark} {res}")
    text = "\n".join(lines)
    if len(text) > limits["tool_log_chars"]:
        text = "(古い記録は省いた)\n" + text[-limits["tool_log_chars"]:]
    return text or "(このターンにツールの呼び出しは無い)"


async def _fixed(fixed, attempt_no):
    await asyncio.sleep(fixed.get("delay", 0))
    mode = fixed["mode"]
    reject = mode == "always_reject" or (mode == "reject_until" and attempt_no <= fixed.get("n", 0))
    reasons = ["試験用の固定の判定: 文面を少し変えて、もう一度送ってください。"] if reject else []
    return {"completion": {"pass": not reject, "reasons": reasons}, "rules": []}


async def codex_gate(cfg, sem, prompt_args, rule_ids, deadline, attempt_no):
    """完了判定と規約の問いを 1 回の呼び出しで判定する。待つ上限を超えたら JudgeTimeout を投げる。"""
    t0 = time.monotonic()
    judge = cfg["judge"]
    out = {"gate": "codex", "model": judge["codex_model"], "effort": judge["codex_effort"], "rule_ids": rule_ids,
           "calls": 0, "errors": []}
    if judge.get("fixed"):
        try:
            verdict = await asyncio.wait_for(_fixed(judge["fixed"], attempt_no), max(1, deadline - time.monotonic()))
        except asyncio.TimeoutError:
            out["errors"].append("timeout")
            raise JudgeTimeout(out) from None
        out.update({"model": "fixed", "seconds": round(time.monotonic() - t0, 2), **_codex_results(verdict)})
        return out
    prompt = CODEX_PROMPT.format(**prompt_args)
    with tempfile.TemporaryDirectory(prefix="pda-judge-") as tmp:
        schema = pathlib.Path(tmp, "schema.json")
        schema.write_text(json.dumps(CODEX_SCHEMA), encoding="utf-8")
        result = pathlib.Path(tmp, "out.json")
        cmd = [cfg["codex_bin"], "exec", "-", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
               "--sandbox", "read-only", "-m", judge["codex_model"],
               "-c", f"model_reasoning_effort={judge['codex_effort']}",
               "--output-schema", str(schema), "-o", str(result)]
        env = dict(os.environ)
        if cfg.get("codex_home"):
            env["CODEX_HOME"] = cfg["codex_home"]
        async with sem:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise JudgeTimeout(out)
                out["calls"] += 1
                result.unlink(missing_ok=True)
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=tmp, env=env, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
                try:
                    _, err = await asyncio.wait_for(proc.communicate(prompt.encode("utf-8")), remaining)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    out["errors"].append("timeout")
                    raise JudgeTimeout(out) from None
                try:
                    verdict = json.loads(result.read_text(encoding="utf-8"))
                    out.update({"seconds": round(time.monotonic() - t0, 2), **_codex_results(verdict)})
                    return out
                except Exception as exc:  # noqa: BLE001
                    out["errors"].append(f"exit={proc.returncode} {type(exc).__name__}: "
                                         f"{err.decode('utf-8', 'replace')[-300:]}")
                    await asyncio.sleep(min(15, max(0, deadline - time.monotonic())))


def _codex_results(verdict):
    results = [{"id": r["id"], "pass": r["verdict"] != "fail", "verdict": r["verdict"], "quote": r.get("quote", ""),
                "reason": r.get("reason", ""), "fix": r.get("fix", "")} for r in verdict.get("rules", [])]
    return {"completion": verdict["completion"], "results": results}
