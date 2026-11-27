#!/usr/bin/env python3
"""台帳に残っている出した一通を、正本のJevの問いに通し直して、規則ごとに外れにした数を出す (確かめ用)。

    replay_norms.py <台帳のSQLite> [<台帳のSQLite> ...]
    replay_norms.py --codex <通数> <間隔の秒> <台帳のSQLite> [...]

--codex は、新しい一通から <通数> 通を、Codexの問い (依頼と返事だけで判定できるもの) に通す。
Codexの呼び出しの制限に当たらないよう、1通ごとに <間隔の秒> だけ待つ。

判定を台帳に残すだけの規則を、差し戻しに使うかを決める材料にする。台帳は開くだけで、変えない。
"""
import asyncio
import collections
import json
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pda_pipeline import config, gates, norms  # noqa: E402


async def codex_replay(cfg, rules, turns, gap):
    usable = [r for r in rules["codex"] if r["trigger"] not in ("document", "files", "pre")
              and "tool_calls" not in r["question"] and "ツールの記録" not in r["question"]]
    ids = [r["id"] for r in usable]
    fails, sem = collections.Counter(), asyncio.Semaphore(1)
    for n, (request, reply) in enumerate(turns):
        if n:
            await asyncio.sleep(gap)
        args = {"checklist": gates.codex_checklist(rules, ids), "request": request, "context": "(なし)",
                "tool_log": "(この通し直しでは、ツールの記録を渡していない。完了判定は pass とする)", "draft": reply,
                "document": "なし"}
        verdict = await gates.codex_gate(cfg, sem, args, ids, time.monotonic() + 600, 1)
        for r in verdict["results"]:
            if not r["pass"]:
                fails[r["id"]] += 1
                print("FAIL", r["id"], "|", r["quote"][:60], "|", r["reason"][:120], flush=True)
        print("done", n + 1, "seconds", verdict.get("seconds"), flush=True)
    print(json.dumps({"turns": len(turns), "ids": ids, "fails": dict(fails)}, ensure_ascii=False))


def main():
    cfg = config.load()
    if sys.argv[1] == "--codex":
        count, gap, paths = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
        turns = []
        for path in paths:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            turns += db.execute("SELECT request, final_text FROM turns WHERE outcome='released' AND final_text IS NOT"
                                " NULL AND requester='owner' ORDER BY length(final_text) DESC LIMIT ?", (count,)).fetchall()
        asyncio.run(codex_replay(cfg, norms.load().rules, turns[:count], gap))
        return
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
