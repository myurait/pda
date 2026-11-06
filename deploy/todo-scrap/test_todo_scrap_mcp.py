"""todo-scrap-mcp の、todo.md と scrap.md を読み書きする部分の試験。

実行: python3 -m unittest deploy/todo-scrap/test_todo_scrap_mcp.py
"""

import importlib.machinery
import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).with_name("todo-scrap-mcp")
_loader = importlib.machinery.SourceFileLoader("todo_scrap_mcp", str(SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
mcp = importlib.util.module_from_spec(_spec)
_loader.exec_module(mcp)

TODO = """# todo

## 仕事
- [ ] 報告を書く
- [x] レビューに返事する

## PDA の開発

## 自分のこと
- [ ] 部屋を片付ける
"""

SCRAP = """# スクラップ

説明。

- [ ] 2026-11-07 09:00 [新しい記事](https://example.com/new) メモ
- [x] 2026-11-06 20:00 [読んだ記事](https://example.com/old)
- [ ] 2026-11-06 19:00 ただのテキスト
"""


class TodoTest(unittest.TestCase):
    def test_items_keep_section_and_state(self):
        items = mcp.todo_items(TODO)
        self.assertEqual(items[0], {"section": "仕事", "text": "報告を書く", "done": False})
        self.assertEqual(items[1]["done"], True)
        self.assertEqual(items[2]["section"], "自分のこと")

    def test_add_goes_to_top_of_named_section(self):
        out = mcp.add_todo_text(TODO, "歯医者", "自分のこと")
        self.assertIn("## 自分のこと\n- [ ] 歯医者\n- [ ] 部屋を片付ける\n", out)

    def test_add_without_section_goes_to_first_section(self):
        out = mcp.add_todo_text(TODO, "新しい仕事")
        self.assertIn("## 仕事\n- [ ] 新しい仕事\n- [ ] 報告を書く\n", out)

    def test_add_to_empty_section(self):
        out = mcp.add_todo_text(TODO, "MCP を作る", "PDA の開発")
        self.assertIn("## PDA の開発\n- [ ] MCP を作る\n", out)

    def test_add_to_unknown_section_fails(self):
        with self.assertRaises(ValueError):
            mcp.add_todo_text(TODO, "x", "無い節")

    def test_complete_one_matching_item(self):
        out = mcp.set_task_done(TODO, lambda line: "部屋" in line)
        self.assertIn("- [x] 部屋を片付ける", out)

    def test_complete_ambiguous_fails(self):
        with self.assertRaises(ValueError):
            mcp.set_task_done(TODO, lambda line: "- [ ]" in line)

    def test_reopen_done_item(self):
        out = mcp.set_task_done(TODO, lambda line: "レビュー" in line, done=False)
        self.assertIn("- [ ] レビューに返事する", out)


class ScrapTest(unittest.TestCase):
    def test_items_parse_link_and_note(self):
        items = mcp.scrap_items(SCRAP)
        self.assertEqual(
            items[0],
            {"read": False, "added": "2026-11-07 09:00", "title": "新しい記事", "url": "https://example.com/new", "note": "メモ"},
        )
        self.assertTrue(items[1]["read"])
        self.assertIsNone(items[2]["url"])

    def test_mark_read_by_url(self):
        out = mcp.set_task_done(SCRAP, lambda line: "(https://example.com/new)" in line, True, mcp.SCRAP)
        self.assertIn("- [x] 2026-11-07 09:00 [新しい記事]", out)


if __name__ == "__main__":
    unittest.main()
