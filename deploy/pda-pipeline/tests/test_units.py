"""依頼の取り出し・スクリプトの判定・台帳・差し戻しの文の試験。

    python3 -m unittest discover -s deploy/pda-pipeline/tests
"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pda_pipeline import gates  # noqa: E402
from pda_pipeline.ledger import Ledger  # noqa: E402
from pda_pipeline.prompt import extract_request, text_key  # noqa: E402

MARK = "[T3 Code: this message came through T3 Code's tools, not from the user typing in this chat.]"


def blocks(text):
    return [{"type": "text", "text": text}]


class ExtractRequest(unittest.TestCase):
    def test_first_prompt_drops_t3_instructions(self):
        raw = ("<t3_code_instructions>\nspawn_agent を使う\n</t3_code_instructions>\n\n<user_request>\n"
               "設計の要点を返してください。\n</user_request>\n<runtime_info>x</runtime_info>")
        self.assertEqual(extract_request(blocks(raw)), ("設計の要点を返してください。", False))

    def test_tool_marker_is_removed_and_reported(self):
        self.assertEqual(extract_request(blocks(f"{MARK}\n\n続きの依頼です。")), ("続きの依頼です。", True))

    def test_handoff_takes_last_user_message(self):
        raw = ("<user_request>\nContext handoff (delta):\n[Historical user]\n古い依頼\n\nUser message:\n"
               f"{MARK}\n\n新しい依頼です。\n</user_request>")
        self.assertEqual(extract_request(blocks(raw)), ("新しい依頼です。", True))

    def test_plain_followup(self):
        self.assertEqual(extract_request(blocks("もう一度お願いします。")), ("もう一度お願いします。", False))

    def test_text_key_ignores_whitespace(self):
        self.assertEqual(text_key("a  b\nc"), text_key("a b c"))


class ScriptGate(unittest.TestCase):
    def result(self, text, rule):
        return next(r for r in gates.script_gate(text)["results"] if r["id"] == rule)

    def test_space_between_ascii_and_japanese_fails(self):
        self.assertFalse(self.result("memo.txt を作りました。", "44")["pass"])
        self.assertFalse(self.result("ミニ PC で動かしました。", "44")["pass"])

    def test_no_space_passes(self):
        self.assertTrue(self.result("memo.txtを作りました。3件あります。", "44")["pass"])

    def test_code_and_lists_are_ignored(self):
        text = "- `memo.txt` を作りました。\n1. 手順を進めます。\n```\nls -la ファイル\n```"
        self.assertTrue(self.result(text, "44")["pass"])

    def test_english_line_fails(self):
        self.assertFalse(self.result("作業しました。\n\nI have created the file in the working directory.", "47")["pass"])

    def test_identifiers_and_commands_pass(self):
        text = "`git status --short` の出力は空でした。\nclaude-opus-5-5\nhttps://example.com/a/b"
        self.assertTrue(self.result(text, "47")["pass"])

    def test_demonstrative_detection(self):
        self.assertTrue(gates.has_demonstrative("その結果を示します。"))
        self.assertFalse(gates.has_demonstrative("結果を示します。`この` は対象外です。"))


class CodexChecklist(unittest.TestCase):
    def test_rule_ids_follow_triggers(self):
        rules = gates.load_rules()
        ids = gates.codex_rule_ids(rules, "結果は3件です。", {"propose": False})
        self.assertEqual(ids, ["101+102", "205", "P1"])
        ids = gates.codex_rule_ids(rules, "その案を採ります。", {"propose": True})
        self.assertEqual(ids, ["56", "7+19", "101+102", "205", "P1"])

    def test_tool_log_keeps_newest_when_too_long(self):
        log = [{"name": "Bash", "input": {"command": f"echo {i}"}, "result": "x" * 500} for i in range(50)]
        text = gates.format_tool_log(log, {"tool_result_chars": 400, "tool_log_chars": 2000})
        self.assertIn("echo 49", text)
        self.assertNotIn("echo 0\"", text)


class LedgerTest(unittest.TestCase):
    def test_turn_and_attempt_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = Ledger(pathlib.Path(tmp, "l.sqlite"))
            led.create_session("s1", "thread-1", "c1", "/tmp", role="main")
            turn = led.start_turn("s1", "owner", "依頼")
            attempt = led.start_attempt(turn, "下書き")
            led.finish_attempt(attempt, ["下書き"], [{"gate": "script"}], "rejected")
            led.finish_turn(turn, "released", "一通")
            self.assertEqual(led.session_by_thread("thread-1")["id"], "s1")
            self.assertEqual(led.attempts(turn)[0]["verdicts"], [{"gate": "script"}])
            self.assertEqual(led.recent_exchanges("s1", turn + 1), [{"request": "依頼", "final_text": "一通"}])
            led.start_turn("s1", "owner", "途中")
            led.close_dangling_turns()
            self.assertEqual(led.turns("s1")[0]["outcome"], "failed")


if __name__ == "__main__":
    unittest.main()
