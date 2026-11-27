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
        lines = [f"- {e['rule']}" for e in self.loaded if e.get("role") == kind]
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


def load(path=None):
    path = pathlib.Path(path or RULES_FILE)
    mtime = path.stat().st_mtime_ns
    hit = _cache.get(str(path))
    if not hit or hit[0] != mtime:
        hit = (mtime, Norms(json.loads(path.read_text(encoding="utf-8"))))
        _cache[str(path)] = hit
    return hit[1]
