"""オーナーの規約の正本 (norms/rules.json) から、役の指示・報告係の指示・ゲートの問いを組む。

正本の 1 件は規則 1 つで、載せるか (load)、どの判定器で確かめるか (judge)、外れを差し戻すか (enforce) を持つ。
"""
import json
import pathlib

NORMS_DIR = pathlib.Path(__file__).resolve().parent.parent / "norms"
RULES_FILE = NORMS_DIR / "rules.json"

WORKER_HEAD = ("## オーナーの規約 (作業の進め方と、作る物)\n\n"
               "次は、オーナーが決めた規則です。作業と、作るファイル・資料・依頼文に当てはめます。"
               "規則の文の「Artifact」「判断の資料」は、道具 `attach_document` で返事に付ける資料のことです。\n")
REPORTER_HEAD = ("## オーナーの規約 (返事の書き方)\n\n"
                 "次は、オーナーが決めた、返事の書き方の規則です。一通を書くときに当てはめます。\n")

_cache = {}


class Norms:
    def __init__(self, entries):
        self.entries = entries
        self.loaded = [e for e in entries if e.get("load")]
        self.rules = self._compile()
        self.pre = [e for e in self.loaded if e.get("judge") == "pre"]

    def instructions(self, kind):
        """kind は worker か reporter。載せる規則の文を、役の指示につなぐ節にする。"""
        lines = [f"- {e['rule']}" + (" (セッションが足した規則)" if e.get("origin") == "agent" else "")
                 for e in self.loaded if e.get("role") == kind]
        if not lines:
            return ""
        return (WORKER_HEAD if kind == "worker" else REPORTER_HEAD) + "\n" + "\n".join(lines) + "\n"

    def _compile(self):
        script, questions, jev_rules, triggers, codex = [], {}, [], {}, []
        for e in self.loaded:
            judge, rid, enforce = e.get("judge"), str(e.get("key") or e["id"]), bool(e.get("enforce"))
            if e.get("see") is not None:
                continue  # 別の規則の問いにまとめて判定する
            if judge == "script":
                script.append({"id": rid, "name": e["rule"], "check": e["script"], "enforce": enforce})
            elif judge == "jev":
                if e.get("questions"):
                    questions.update(e["questions"])
                    fail_when = e["fail_when"]
                else:
                    fail_when = []
                    if e.get("applies"):
                        questions[f"a{rid}"] = {"type": "noul", "instructions": e["applies"]}
                        fail_when.append([f"a{rid}", ">=", 0.7])
                    questions[f"v{rid}"] = {"type": "noul", "instructions": e["violates"]}
                    fail_when.append([f"v{rid}", ">=", 0.8])
                jev_rules.append({"id": rid, "name": e["rule"], "fail_when": fail_when, "fix": e["fix"],
                                  "enforce": enforce})
            elif judge in ("codex", "pre"):
                trig = e.get("trigger") or {"kind": "pre" if judge == "pre" else "always"}
                kind = trig["kind"]
                if kind == "jev":
                    questions[f"t{rid}"] = {"type": "noul", "instructions": trig["question"]}
                    triggers[f"t{rid}"] = [f"t{rid}", ">=", 0.5]
                    name = f"t{rid}"
                elif kind == "words":
                    name = "words:" + trig["pattern"]
                else:
                    name = trig.get("name") or kind
                codex.append({"id": rid, "name": e["rule"], "trigger": name, "unit": e["unit"], "reader": e["reader"],
                              "question": e["question"], "enforce": enforce})
        for name, spec in (self._extra_triggers() or {}).items():
            questions.update(spec["questions"])
            triggers[name] = spec["trigger"]
        return {"script": script, "jev": {"questions": questions, "rules": jev_rules, "triggers": triggers},
                "codex": codex}

    def _extra_triggers(self):
        for e in self.entries:
            if e.get("id") == "triggers":
                return e["triggers"]
        return {}

    def pre_questions(self):
        return {f"p{e['id']}": {"type": "noul", "instructions": e["applies"]} for e in self.pre}

    def coverage(self):
        """載せる規則ごとの載せ先。照合の試験と記録に使う。"""
        out = {}
        for e in self.loaded:
            if not isinstance(e["id"], int):
                continue
            out[e["id"]] = {"instruction": e.get("role") in ("worker", "reporter"),
                            "judge": e.get("judge"), "enforce": bool(e.get("enforce"))}
        return out


def load(path=None, overlay=None):
    """正本と、エージェントが足し引きした分 (overlay) を重ねて返す。どちらかが変わったら組み直す。"""
    path = pathlib.Path(path or RULES_FILE)
    overlay = pathlib.Path(overlay) if overlay else None
    stamp = (path.stat().st_mtime_ns, overlay.stat().st_mtime_ns if overlay and overlay.is_file() else 0)
    key = (str(path), str(overlay))
    hit = _cache.get(key)
    if not hit or hit[0] != stamp:
        entries = json.loads(path.read_text(encoding="utf-8"))
        if stamp[1]:
            entries = merge(entries, json.loads(overlay.read_text(encoding="utf-8")))
        hit = (stamp, Norms(entries))
        _cache[key] = hit
    return hit[1]


# エージェントによるゲートの足し引き。正本のファイルは変えず、常駐のデータの置き場の overlay に持つ。


def merge(entries, overlay):
    by_id = {str(e["id"]): dict(e) for e in entries}
    order = [str(e["id"]) for e in entries]
    for rid, change in overlay.get("changed", {}).items():
        if rid in by_id:
            by_id[rid].update(change)
    for e in overlay.get("added", []):
        by_id[str(e["id"])] = dict(e)
        order.append(str(e["id"]))
    return [by_id[rid] for rid in order]


def _read(overlay):
    overlay = pathlib.Path(overlay)
    if overlay.is_file():
        return json.loads(overlay.read_text(encoding="utf-8"))
    return {"added": [], "changed": {}, "next": 1}


TEXT_FIELDS = ("rule", "applies", "violates", "fix", "unit", "reader", "question")
TEXT_MAX = 1000


def _clean(args):
    """道具に渡された項目の型と長さを確かめ、使う項目だけを返す。"""
    out = {}
    for key in TEXT_FIELDS:
        if args.get(key) is not None:
            if not isinstance(args[key], str) or not args[key].strip() or len(args[key]) > TEXT_MAX:
                raise ValueError(f"{key} は {TEXT_MAX} 文字までの文で渡す")
            out[key] = " ".join(args[key].split())
    if args.get("role") is not None:
        if args["role"] not in ("worker", "reporter"):
            raise ValueError("role は worker か reporter")
        out["role"] = args["role"]
    if args.get("enforce") is not None:
        if not isinstance(args["enforce"], bool):
            raise ValueError("enforce は true か false")
        out["enforce"] = args["enforce"]
    return out


def _write(overlay, data, entries):
    Norms(merge(entries, data))  # 組み直せない変更は、保存する前に断る
    overlay = pathlib.Path(overlay)
    overlay.parent.mkdir(parents=True, exist_ok=True)
    tmp = overlay.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(overlay)


def add_rule(overlay, entries, args):
    """規則を足す。violates があれば Jev、question があれば Codex が判定する。どちらも無ければ役の指示にだけ載る。"""
    args = _clean(args)
    rule = args.get("rule")
    if not rule:
        raise ValueError("規則の文が空")
    role = args.get("role", "reporter")
    data = _read(overlay)
    entry = {"id": f"A{data['next']}", "rule": rule, "fire": "reply", "role": role, "load": True, "enforce": True,
             "origin": "agent"}
    if args.get("violates"):
        entry.update(judge="jev", violates=str(args["violates"]),
                     fix=str(args.get("fix") or f"次の規則に合うように直してください: {rule}"))
        if args.get("applies"):
            entry["applies"] = str(args["applies"])
    elif args.get("question"):
        entry.update(judge="codex", question=str(args["question"]), unit=str(args.get("unit") or "返事全体"),
                     reader=str(args.get("reader") or "依頼をしたオーナー"))
        if args.get("applies"):
            entry["trigger"] = {"kind": "jev", "question": str(args["applies"])}
    else:
        entry.update(judge=None, note="役の指示にだけ載せる規則")
    data["added"].append(entry)
    data["next"] += 1
    _write(overlay, data, entries)
    return entry


def change_rule(overlay, entries, rid, args, unload=False):
    """規則を変える。足した規則はそのものを、正本の規則は変える項目だけを overlay に持つ。"""
    rid = str(rid)
    target = next((e for e in entries if str(e["id"]) == rid), None)
    if not target or target.get("role") == "pipeline" or rid == "triggers":
        raise ValueError(f"変えられる規則が無い: {rid}")
    change = _clean(args)
    if unload:
        change.update(load=False, skip="removed_by_agent")
    if not change:
        raise ValueError("変える項目が無い")
    data = _read(overlay)
    added = next((e for e in data["added"] if str(e["id"]) == rid), None)
    if added:
        added.update(change)
    else:
        data["changed"].setdefault(rid, {}).update(change)
    _write(overlay, data, entries)
    return change


def remove_rule(overlay, entries, rid):
    """規則を消す。足した規則は overlay から消し、正本の規則は載せない設定にする。"""
    rid = str(rid)
    data = _read(overlay)
    if any(str(e["id"]) == rid for e in data["added"]):
        data["added"] = [e for e in data["added"] if str(e["id"]) != rid]
        _write(overlay, data, [e for e in entries if str(e["id"]) != rid])
        return "added"
    change_rule(overlay, entries, rid, {}, unload=True)
    return "unloaded"
