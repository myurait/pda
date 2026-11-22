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


class AddToTopTest(unittest.TestCase):
    HEAD = "# スクラップ\n\n説明。\n\n"

    def test_new_line_goes_above_existing_entries(self):
        text = self.HEAD + "- [ ] 2026-11-06 20:07 old\n- [x] 2026-11-05 10:00 older\n"
        out = receiver.add_to_top(text, "- [ ] 2026-11-07 09:00 new")
        self.assertEqual(
            out,
            self.HEAD + "- [ ] 2026-11-07 09:00 new\n- [ ] 2026-11-06 20:07 old\n- [x] 2026-11-05 10:00 older\n",
        )

    def test_first_entry_goes_after_header(self):
        out = receiver.add_to_top(self.HEAD, "- [ ] 2026-11-07 09:00 new")
        self.assertEqual(out, self.HEAD + "- [ ] 2026-11-07 09:00 new\n")


class AlreadyListedTest(unittest.TestCase):
    TEXT = (
        "- [ ] 2026-11-07 12:25 [スライド](https://example.com/deck) [topic: AI]\n"
        "- [x] 2026-11-06 09:00 [読んだ記事](https://example.com/old)\n"
    )

    def test_open_scrap_with_same_url_is_listed(self):
        self.assertTrue(receiver.already_listed(self.TEXT, parse({"url": "https://example.com/deck?utm_source=x"})))

    def test_completed_scrap_can_be_sent_again(self):
        self.assertFalse(receiver.already_listed(self.TEXT, parse({"url": "https://example.com/old"})))

    def test_plain_text_is_never_listed(self):
        self.assertFalse(receiver.already_listed(self.TEXT, parse({"text": "メモ"})))


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


def oembed(body):
    return json.dumps({"html": f'<blockquote class="twitter-tweet"><p lang="en" dir="ltr">{body}</p>&mdash; A</blockquote>'})


class XHeadingTest(unittest.TestCase):
    URL = "https://x.com/someone/status/2119332146485891501"
    ARTICLE_LINK = '<a href="https://t.co/KD5BxbuZ5Q">https://t.co/KD5BxbuZ5Q</a>'

    def setUp(self):
        self.original = receiver.http_get
        self.requested = []
        self.addCleanup(setattr, receiver, "http_get", self.original)

    def serve(self, post, fx):
        def fake(url, headers=None, timeout=20):
            self.requested.append(url)
            if url.startswith(receiver.X_OEMBED):
                return oembed(post)
            if isinstance(fx, Exception):
                raise fx
            return json.dumps(fx)

        receiver.http_get = fake

    def test_article_post_gets_article_title(self):
        self.serve(self.ARTICLE_LINK, {"status": {"article": {"title": "Your coding agents made you a manager"}}})
        self.assertEqual(receiver.fetch_heading(self.URL), "Your coding agents made you a…")
        self.assertEqual(self.requested[-1], receiver.FXTWITTER + "2119332146485891501")

    def test_article_title_wins_over_post_text(self):
        self.serve(f"Best article {self.ARTICLE_LINK}", {"status": {"article": {"title": "Agents"}}})
        self.assertEqual(receiver.fetch_heading(self.URL), "Agents")

    def test_link_without_article_keeps_post_text(self):
        self.serve(f"see {self.ARTICLE_LINK}", {"status": {"text": "see"}})
        self.assertEqual(receiver.fetch_heading(self.URL), "see https://t.co/KD5BxbuZ5Q")

    def test_fxtwitter_failure_keeps_post_text(self):
        self.serve(self.ARTICLE_LINK, OSError("down"))
        self.assertEqual(receiver.fetch_heading(self.URL), "https://t.co/KD5BxbuZ5Q")

    def test_post_without_link_does_not_call_fxtwitter(self):
        self.serve("hello", {})
        self.assertEqual(receiver.fetch_heading(self.URL), "hello")
        self.assertEqual(len(self.requested), 1)


if __name__ == "__main__":
    unittest.main()
