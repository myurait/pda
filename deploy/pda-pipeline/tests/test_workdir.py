import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pda_pipeline import workdir  # noqa: E402


class WorkdirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_relative_against_base(self):
        os.makedirs(os.path.join(self.root, "a/b"))
        self.assertEqual(workdir.resolve("b", os.path.join(self.root, "a")), os.path.join(self.root, "a/b"))

    def test_resolve_keeps_absolute(self):
        self.assertEqual(workdir.resolve(self.root, "/nonexistent"), self.root)

    def test_notes_without_instructions(self):
        text = workdir.notes(self.root)
        self.assertIn(f"`{self.root}`", text)
        self.assertNotIn("リポジトリの指示", text)

    def test_notes_layers_repo_root_and_subdir(self):
        repo = os.path.join(self.root, "repo")
        sub = os.path.join(repo, "pkg")
        os.makedirs(os.path.join(repo, ".git"))
        os.makedirs(sub)
        pathlib.Path(repo, "CLAUDE.md").write_text("ROOT-RULE", encoding="utf-8")
        pathlib.Path(sub, "AGENTS.md").write_text("SUB-RULE", encoding="utf-8")
        text = workdir.notes(sub)
        self.assertIn("ROOT-RULE", text)
        self.assertIn("SUB-RULE", text)
        self.assertLess(text.index("いまの作業ディレクトリ"), text.index("ROOT-RULE"))

    def test_notes_skips_link_to_outside(self):
        repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(repo, ".git"))
        outside = pathlib.Path(self.root, "outside.txt")
        outside.write_text("OUTSIDE-TEXT", encoding="utf-8")
        os.symlink(outside, os.path.join(repo, "CLAUDE.md"))
        pathlib.Path(repo, "AGENTS.md").write_text("INSIDE-RULE", encoding="utf-8")
        text = workdir.notes(repo)
        self.assertNotIn("OUTSIDE-TEXT", text)
        self.assertIn("INSIDE-RULE", text)

    def test_notes_reads_link_inside_once(self):
        repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(repo, ".git"))
        pathlib.Path(repo, "AGENTS.md").write_text("INSIDE-RULE", encoding="utf-8")
        os.symlink("AGENTS.md", os.path.join(repo, "CLAUDE.md"))
        self.assertEqual(workdir.notes(repo).count("INSIDE-RULE"), 1)

    def test_notes_drops_previous_repo(self):
        one, two = os.path.join(self.root, "one"), os.path.join(self.root, "two")
        for d, rule in ((one, "ONE-RULE"), (two, "TWO-RULE")):
            os.makedirs(os.path.join(d, ".git"))
            pathlib.Path(d, "CLAUDE.md").write_text(rule, encoding="utf-8")
        self.assertNotIn("ONE-RULE", workdir.notes(two))


if __name__ == "__main__":
    unittest.main()
