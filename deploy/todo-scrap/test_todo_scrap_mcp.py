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

- [ ] 報告を書く [category: 仕事]
- [x] レビューに返事する [category: 仕事]
- [ ] 部屋を片付ける [category: プライベート]
"""

OLD_TODO = """# todo

## 仕事
- [ ] 報告を書く
- [x] レビューに返事する [project: 案件A]

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
    def test_items_keep_category_and_state(self):
        items = mcp.todo_items(TODO)
        self.assertEqual(
            items[0],
            {"text": "報告を書く", "category": "仕事", "project": None, "due": None, "status": None, "weight": None,
             "done": False},
        )
        self.assertEqual(items[1]["done"], True)
        self.assertEqual(items[2]["category"], "プライベート")

    def test_add_goes_to_top_of_list(self):
        out = mcp.add_todo_text(TODO, "歯医者 [category: プライベート]")
        self.assertTrue(out.startswith("# todo\n\n- [ ] 歯医者 [category: プライベート]\n- [ ] 報告を書く"))

    def test_add_to_empty_list(self):
        self.assertEqual(mcp.add_todo_text("# todo\n", "歯医者"), "# todo\n- [ ] 歯医者\n")

    def test_sections_become_categories(self):
        out = mcp.sections_to_categories(OLD_TODO, {"仕事": "仕事", "PDA の開発": "個人開発", "自分のこと": "プライベート"})
        self.assertEqual(
            out,
            "# todo\n\n"
            "- [ ] 報告を書く [category: 仕事]\n"
            "- [x] レビューに返事する [category: 仕事] [project: 案件A]\n"
            "- [ ] 部屋を片付ける [category: プライベート]\n",
        )

    def test_sections_without_mapping_fail(self):
        with self.assertRaises(ValueError):
            mcp.sections_to_categories(OLD_TODO, {"仕事": "仕事"})

    def test_complete_one_matching_item(self):
        out = mcp.set_task_done(TODO, lambda line: "部屋" in line)
        self.assertIn("- [x] 部屋を片付ける", out)

    def test_complete_ambiguous_fails(self):
        with self.assertRaises(ValueError):
            mcp.set_task_done(TODO, lambda line: "- [ ]" in line)

    def test_reopen_done_item(self):
        out = mcp.set_task_done(TODO, lambda line: "レビュー" in line, done=False)
        self.assertIn("- [ ] レビューに返事する", out)

    def test_replace_keeps_category_and_state(self):
        out, old = mcp.edit_todo_text(TODO, "部屋", "部屋と台所を片付ける")
        self.assertEqual(old, "部屋を片付ける")
        self.assertIn("- [ ] 部屋と台所を片付ける [category: プライベート]\n", out)
        self.assertNotIn("部屋を片付ける", out)

    def test_replace_done_item_stays_done(self):
        out, _ = mcp.edit_todo_text(TODO, "レビュー", "レビューに返事した")
        self.assertIn("- [ ] 報告を書く [category: 仕事]\n- [x] レビューに返事した [category: 仕事]\n", out)

    def test_delete_one_item(self):
        out, old = mcp.edit_todo_text(TODO, "報告")
        self.assertEqual(old, "報告を書く")
        self.assertIn("# todo\n\n- [x] レビューに返事する", out)

    def test_delete_last_line_without_newline(self):
        out, _ = mcp.edit_todo_text(TODO.rstrip("\n"), "部屋")
        self.assertTrue(out.endswith("- [x] レビューに返事する [category: 仕事]\n"))

    def test_edit_matches_body_only(self):
        with self.assertRaises(ValueError):
            mcp.edit_todo_text(TODO, "[ ]")

    def test_edit_ambiguous_or_missing_fails(self):
        with self.assertRaises(ValueError):
            mcp.edit_todo_text(TODO, "る", "x")
        with self.assertRaises(ValueError):
            mcp.edit_todo_text(TODO, "無い項目")


class TodoAttrTest(unittest.TestCase):
    TEXT = """# todo

- [ ] 設計書を直す [category: 仕事] [project: 案件A] [due: 2026-11-15] [status: 進行中] [weight: 2]
- [ ] 報告を書く
- [x] 期限の近いもの [due:: 2026-11-10]
"""

    def test_items_split_attributes(self):
        items = mcp.todo_items(self.TEXT)
        self.assertEqual(
            items[0],
            {"text": "設計書を直す", "category": "仕事", "project": "案件A", "due": "2026-11-15",
             "status": "進行中", "weight": 2, "done": False},
        )
        self.assertIsNone(items[1]["status"])
        self.assertEqual(items[2]["due"], "2026-11-10")  # SilverBullet の `::` の書き方も読む

    def test_sort_by_due_puts_no_due_last(self):
        texts = [i["text"] for i in mcp.sort_by_due(mcp.todo_items(self.TEXT))]
        self.assertEqual(texts, ["期限の近いもの", "設計書を直す", "報告を書く"])

    def test_set_attrs_writes_in_fixed_order(self):
        out, body = mcp.set_todo_attrs_text(self.TEXT, "報告", {"weight": 1, "due": "2026-12-01", "project": "案件B"})
        self.assertEqual(body, "報告を書く")
        self.assertIn("- [ ] 報告を書く [project: 案件B] [due: 2026-12-01] [weight: 1]\n", out)

    def test_set_attrs_empty_removes_and_none_keeps(self):
        out, _ = mcp.set_todo_attrs_text(self.TEXT, "設計書", {"status": "", "due": None})
        self.assertIn("- [ ] 設計書を直す [category: 仕事] [project: 案件A] [due: 2026-11-15] [weight: 2]\n", out)

    def test_set_attrs_rejects_values_out_of_range(self):
        for changes in ({"status": "完了"}, {"weight": 4}, {"due": "11/15"}, {"due": "20261115"}):
            with self.assertRaises(ValueError):
                mcp.set_todo_attrs_text(self.TEXT, "報告", changes)

    def test_project_value_cannot_break_attribute(self):
        out, _ = mcp.set_todo_attrs_text(self.TEXT, "報告", {"project": "案件[x]"})
        self.assertIn("- [ ] 報告を書く [project: 案件 x]\n", out)

    def test_match_ignores_attributes(self):
        with self.assertRaises(ValueError):
            mcp.set_todo_attrs_text(self.TEXT, "案件A", {"weight": 1})

    def test_replace_keeps_attributes(self):
        out, old = mcp.edit_todo_text(self.TEXT, "設計書", "設計書を最新化する")
        self.assertEqual(old, "設計書を直す")
        self.assertIn("- [ ] 設計書を最新化する [category: 仕事] [project: 案件A] [due: 2026-11-15] [status: 進行中] [weight: 2]\n", out)

    def test_replace_moves_prefix_to_project(self):
        out, _ = mcp.edit_todo_text(self.TEXT, "報告", "報告を書く [project: 案件B]")
        self.assertIn("- [ ] 報告を書く [project: 案件B]\n", out)

    def test_add_with_attributes(self):
        item = mcp.join_attrs("歯医者", mcp.apply_attrs({}, {"due": "2026-11-20", "weight": None}), mcp.TODO_ATTRS)
        self.assertIn("# todo\n\n- [ ] 歯医者 [due: 2026-11-20]\n- [ ] 設計書を直す", mcp.add_todo_text(self.TEXT, item))

    def test_complete_matches_body_with_attributes(self):
        out = mcp.set_task_done(
            self.TEXT, lambda line: "設計書" in mcp.split_attrs(mcp.TASK.match(line.rstrip("\n")).group(2))[0]
        )
        self.assertIn("- [x] 設計書を直す [category: 仕事] [project: 案件A]", out)


class ScrapTest(unittest.TestCase):
    def test_items_parse_link_and_note(self):
        items = mcp.scrap_items(SCRAP)
        self.assertEqual(
            items[0],
            {"done": False, "added": "2026-11-07 09:00", "title": "新しい記事", "url": "https://example.com/new",
             "note": "メモ", "topic": None, "aicheck": "未チェック"},
        )
        self.assertTrue(items[1]["done"])
        self.assertIsNone(items[2]["url"])

    def test_items_read_attributes_after_link(self):
        text = "- [ ] 2026-11-07 09:00 [X: foo の投稿](https://x.com/foo/status/1) [topic: AI] [aicheck: 反映待ち]\n"
        item = mcp.scrap_items(text)[0]
        self.assertEqual((item["title"], item["topic"], item["aicheck"], item["note"]), ("X: foo の投稿", "AI", "反映待ち", ""))

    def test_set_attributes_by_url_keeps_checkbox(self):
        out = mcp.set_scrap_text(SCRAP, "https://example.com/new", {"aicheck": "反映待ち", "topic": "開発ツール"})
        self.assertIn("- [ ] 2026-11-07 09:00 [新しい記事](https://example.com/new) メモ [topic: 開発ツール] [aicheck: 反映待ち]\n", out)

    def test_set_attributes_rejects_unknown_topic(self):
        with self.assertRaises(ValueError):
            mcp.set_scrap_text(SCRAP, "https://example.com/new", {"topic": "音楽"})

    def test_complete_waiting_scrap_returns_to_checked(self):
        text = mcp.set_scrap_text(SCRAP, "https://example.com/new", {"aicheck": "反映待ち"})
        out = mcp.complete_scrap_text(text, "https://example.com/new")
        self.assertIn("- [x] 2026-11-07 09:00 [新しい記事](https://example.com/new) メモ [aicheck: チェック済み]\n", out)

    def test_complete_and_reopen(self):
        out = mcp.complete_scrap_text(SCRAP, "https://example.com/new")
        self.assertIn("- [x] 2026-11-07 09:00 [新しい記事](https://example.com/new) メモ\n", out)
        out = mcp.complete_scrap_text(SCRAP, "https://example.com/old", done=False)
        self.assertIn("- [ ] 2026-11-06 20:00 [読んだ記事](https://example.com/old)\n", out)

    def test_unknown_url_fails(self):
        with self.assertRaises(ValueError):
            mcp.set_scrap_text(SCRAP, "https://example.com/none", {"topic": "AI"})


if __name__ == "__main__":
    unittest.main()
