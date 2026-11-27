import json
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pda_pipeline import norms  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
SOURCE = REPO / "docs/claude-unification/rule-gates.json"
SKIPS = {"exclude", "not_a_rule", "dev_pc_tool", "company_account", "frozen_version"}


class NormsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norms = norms.load()
        cls.entries = {e["id"]: e for e in cls.norms.entries}
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_every_source_rule_has_an_entry(self):
        for i, rule in enumerate(self.source):
            self.assertIn(i, self.entries, rule["rule"])
            self.assertEqual(self.entries[i]["rule"], rule["rule"])

    def test_unloaded_rules_have_a_reason(self):
        for e in self.norms.entries:
            if not e.get("load"):
                self.assertIn(e.get("skip"), SKIPS, e["id"])

    def test_source_excludes_are_not_loaded(self):
        for i, rule in enumerate(self.source):
            if rule.get("exclude"):
                self.assertFalse(self.entries[i].get("load"), i)

    def test_every_loaded_rule_is_carried_somewhere(self):
        """載せる規則は、役の指示・報告係の指示・ゲートの問いのどれかに載っている。"""
        worker, reporter = self.norms.instructions("worker"), self.norms.instructions("reporter")
        judged = {r["id"] for r in self.norms.rules["script"]} | {r["id"] for r in self.norms.rules["jev"]["rules"]} \
            | {r["id"] for r in self.norms.rules["codex"]}
        covered = set()
        for rid in judged:
            covered.update(int(x) for x in re.findall(r"\d+", rid))
        for e in self.norms.loaded:
            if not isinstance(e["id"], int):
                continue
            in_text = f"- {e['rule']}\n" in (worker if e["role"] == "worker" else reporter)
            self.assertTrue(in_text or e["id"] in covered, f"{e['id']} {e['rule']}")
            if e.get("judge"):
                self.assertIn(e["id"], covered, f"{e['id']} は判定器に載っていない")
            else:
                self.assertTrue(e.get("note"), f"{e['id']} に、判定しない理由が無い")

    def test_judged_rules_have_complete_questions(self):
        for r in self.norms.rules["jev"]["rules"]:
            self.assertTrue(r["fix"], r["id"])
            for q, op, bound in r["fail_when"]:
                self.assertIn(q, self.norms.rules["jev"]["questions"], r["id"])
        for r in self.norms.rules["codex"]:
            for key in ("unit", "reader", "question", "trigger"):
                self.assertTrue(r[key], f"{r['id']} {key}")
            if r["trigger"].startswith("words:"):
                re.compile(r["trigger"][6:])
            elif r["trigger"] not in ("always", "demonstrative", "document", "files", "pre"):
                self.assertIn(r["trigger"], self.norms.rules["jev"]["triggers"], r["id"])

    def test_no_company_rules_are_loaded(self):
        for e in self.norms.loaded:
            self.assertNotRegex(e["rule"], r"Redash|ドラフト|--draft|PR 作成|PR作成")


if __name__ == "__main__":
    unittest.main()
