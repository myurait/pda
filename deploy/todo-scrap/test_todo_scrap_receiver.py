"""todo-scrap-receiver の、届いた本文から scrap.md の 1 行を作る処理の試験。

実行: python3 -m unittest deploy/todo-scrap/test_todo_scrap_receiver.py
"""

import importlib.machinery
import importlib.util
import json
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).with_name("todo-scrap-receiver")
_loader = importlib.machinery.SourceFileLoader("todo_scrap_receiver", str(SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
receiver = importlib.util.module_from_spec(_spec)
_loader.exec_module(receiver)


def parse(data):
    return receiver.parse(json.dumps(data), "application/json")


class ParseTest(unittest.TestCase):
    def test_x_url_drops_tracking_and_gets_placeholder(self):
        entry = parse({"url": "https://x.com/alezander9/status/2118517491798606140?s=12&t=abc"})
        self.assertEqual(
            entry, "[X: alezander9 の投稿](https://x.com/alezander9/status/2118517491798606140)"
        )
        self.assertIsNotNone(receiver.placeholder_link(entry))

    def test_other_url_drops_utm_and_keeps_other_query(self):
        entry = parse({"url": "https://example.com/a/b?utm_source=x&id=3"})
        self.assertEqual(entry, "[example.com/a/b](https://example.com/a/b?id=3)")

    def test_title_from_shortcut_is_kept_and_not_retitled(self):
        entry = parse({"url": "https://example.com/a", "title": "T ${x} <b>"})
        self.assertEqual(entry, "[T x b](https://example.com/a)")
        self.assertIsNone(receiver.placeholder_link(entry))

    def test_text_shared_in_url_field_stays_text(self):
        self.assertEqual(parse({"url": "see ${x} here"}), "see $ {x} here")

    def test_unsafe_characters_in_url_are_percent_encoded(self):
        entry = parse({"url": "https://evil.example/${a}/b)c"})
        self.assertNotIn("${", entry)
        self.assertTrue(entry.endswith("(https://evil.example/%24%7Ba%7D/b%29c)"))

    def test_empty_body_is_rejected(self):
        self.assertIsNone(parse({}))


class ShortenTest(unittest.TestCase):
    def width(self, text):
        return sum(receiver.char_width(c) for c in text)

    def test_short_text_is_unchanged(self):
        self.assertEqual(receiver.shorten("短い"), "短い")

    def test_half_width_is_cut_to_32(self):
        out = receiver.shorten("Subagents are the biggest cause of AI failures")
        self.assertEqual(out, "Subagents are the biggest caus…")
        self.assertLessEqual(self.width(out), receiver.HEADING_WIDTH)

    def test_full_width_counts_double(self):
        out = receiver.shorten("サブエージェントはAIの失敗の最大の原因である")
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(self.width(out), receiver.HEADING_WIDTH)

    def test_unsafe_characters_are_removed(self):
        self.assertEqual(receiver.shorten("${os.exit()} <b>Hi</b>"), "os.exit() b Hi /b")


class PublicHostTest(unittest.TestCase):
    def test_loopback_and_private_are_not_public(self):
        self.assertFalse(receiver.is_public_host("http://127.0.0.1:18800/"))
        self.assertFalse(receiver.is_public_host("http://192.168.0.59/"))


if __name__ == "__main__":
    unittest.main()
