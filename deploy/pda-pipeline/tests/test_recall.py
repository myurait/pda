import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pda_pipeline import recall  # noqa: E402
from pda_pipeline.ledger import Ledger  # noqa: E402


class RecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = os.path.realpath(self.tmp.name)
        self.repo = os.path.join(root, "alpha-repo")
        os.makedirs(os.path.join(self.repo, ".git"))
        os.makedirs(os.path.join(self.repo, "sub"))
        self.ledger = Ledger(pathlib.Path(root, "ledger.sqlite"))
        self.ledger.db.executescript(recall.SCHEMA)
        self.ledger.create_session("s1", "t1", "c1", os.path.join(self.repo, "sub"), "main", None, "最初の作業")
        turn = self.ledger.start_turn("s1", "owner", "青い案件の設定を直して")
        self.ledger.finish_turn(turn, "released", "設定を直しました。")
        self.turn = turn

    def tearDown(self):
        self.ledger.db.close()
        self.tmp.cleanup()

    def test_knowledge_is_shared_inside_the_repository(self):
        recall.remember(self.ledger, os.path.join(self.repo, "sub"), "文は英語で書く", "s1", self.turn)
        self.assertIn("文は英語で書く", recall.notes(self.ledger, self.repo))
        self.assertEqual(recall.notes(self.ledger, "/"), "")

    def test_search_needs_every_word(self):
        self.assertIn("設定を直しました", recall.search(self.ledger, "青い 設定"))
        self.assertEqual(recall.search(self.ledger, "青い 存在しない語"), "当たるやり取りはありません。")

    def test_find_project_by_directory_name_and_by_history(self):
        by_name = json.loads(recall.find_project(self.ledger, "alpha", []))
        self.assertEqual(by_name[0]["path"], self.repo)
        self.assertEqual(by_name[0]["sessions"][0]["id"], "s1")
        by_history = json.loads(recall.find_project(self.ledger, "青い案件", []))
        self.assertEqual(by_history[0]["path"], self.repo)
        self.assertEqual(by_history[0]["matched_by"], "history")

    def test_overview_lists_last_exchange(self):
        rows = json.loads(recall.overview(self.ledger))
        self.assertEqual(rows[0]["last_reply"], "設定を直しました。")


if __name__ == "__main__":
    unittest.main()
