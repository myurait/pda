#!/usr/bin/env python3
"""台帳に残っている出した一通を、正本のJevの問いに通し直して、規則ごとに外れにした数を出す (確かめ用)。

    replay_norms.py <台帳のSQLite> [<台帳のSQLite> ...]

判定を台帳に残すだけの規則を、差し戻しに使うかを決める材料にする。台帳は開くだけで、変えない。
"""
import collections
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pda_pipeline import config, gates, norms  # noqa: E402


def main():
    cfg = config.load()
    rules = norms.load().rules
    spec = rules["jev"]
    turns = []
    for path in sys.argv[1:]:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        turns += db.execute("SELECT request, final_text FROM turns WHERE outcome='released' AND final_text IS NOT NULL"
                            " AND requester='owner'").fetchall()
    fails, examples = collections.Counter(), {}
    for request, reply in turns:
        state = {"owner_request": request[:6000], "reply": reply[:6000],
                 "first_sentence": gates._first_sentence(reply), "document": "", "tool_calls": ""}
        scores = {q: a.get("noul", 0.0) for q, a in gates._jev_call(cfg["jev"], state, spec["questions"])["answers"].items()}
        for rule in spec["rules"]:
            if all(gates._cmp(scores.get(q, 0.0), op, bound) for q, op, bound in rule["fail_when"]):
                fails[rule["id"]] += 1
                examples.setdefault(rule["id"], reply[:120].replace("\n", " "))
    out = [{"id": r["id"], "enforce": r["enforce"], "fails": fails[r["id"]], "name": r["name"],
            "example": examples.get(r["id"], "")} for r in spec["rules"]]
    print(json.dumps({"turns": len(turns), "rules": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
