"""返信の道具の中の流れ (Turn.submit / _judge / on_stop / release、Daemon の登録と照合) の試験。

    python3 -m unittest discover -s deploy/pda-pipeline/tests
"""
import copy
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pda_pipeline import config  # noqa: E402
from pda_pipeline.daemon import ALREADY, Daemon, Turn  # noqa: E402


class FakeConn:
    """ACP の接続の代わり。update の呼び出しだけを記録する。"""

    def __init__(self):
        self.updates = []

    def update(self, session_id, body):
        self.updates.append((session_id, body))

    def chunks(self):
        return [b for _, b in self.updates if b.get("sessionUpdate") == "agent_message_chunk"]


class ReplyBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def make_daemon(self, fixed, limits=None):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["data_dir"] = self._tmp.name
        cfg["notify"]["enabled"] = False
        cfg["stages"] = {"reporter": False, "jev": False, "codex": True}
        cfg["judge"]["fixed"] = fixed
        cfg["limits"].update(limits or {})
        return Daemon(cfg)

    def make_session(self, daemon, sid="s1", role="main", **kw):
        daemon.ledger.create_session(sid, kw.pop("thread", f"thread-{sid}"), f"c-{sid}", None, **kw)
        daemon.ledger.update_session(sid, role=role)
        return daemon.ledger.session(sid)

    def make_turn(self, daemon, session=None, requester="owner", request="依頼です。"):
        conn = FakeConn()
        session = session or self.make_session(daemon)
        return Turn(daemon, conn, session, request, requester), conn

    def turn_row(self, daemon, turn):
        return daemon.ledger.turn(turn.turn_id)


class SubmitFlow(ReplyBase):
    async def test_always_pass_releases_once(self):
        d = self.make_daemon({"mode": "always_pass"})
        turn, conn = self.make_turn(d)
        ret = await turn.submit("作業が終わりました。")
        self.assertTrue(ret.startswith("送信しました"))
        self.assertEqual(len(conn.chunks()), 1)
        row = self.turn_row(d, turn)
        self.assertEqual(row["outcome"], "released")
        self.assertEqual(row["final_text"], "作業が終わりました。")

    async def test_reject_until_two_then_release(self):
        d = self.make_daemon({"mode": "reject_until", "n": 2})
        turn, conn = self.make_turn(d)
        first = await turn.submit("一回目の文面です。")
        second = await turn.submit("二回目の文面です。")
        self.assertTrue(first.startswith("差し戻し"))
        self.assertTrue(second.startswith("差し戻し"))
        self.assertEqual(conn.updates, [])
        third = await turn.submit("三回目の文面です。")
        self.assertTrue(third.startswith("送信しました"))
        self.assertEqual(self.turn_row(d, turn)["outcome"], "released")
        attempts = d.ledger.attempts(turn.turn_id)
        self.assertEqual([a["decision"] for a in attempts], ["rejected", "rejected", "released"])

    async def test_resubmit_same_text_returns_cached_rejection(self):
        d = self.make_daemon({"mode": "always_reject"})
        turn, _ = self.make_turn(d)
        first = await turn.submit("同じ 文面です。")
        again = await turn.submit("同じ  文面です。")
        spaced = await turn.submit("同じ\n文面です。")
        self.assertEqual(again, first)
        self.assertEqual(spaced, first)
        self.assertEqual(len(d.ledger.attempts(turn.turn_id)), 1)

    async def test_submit_after_release_says_already_delivered(self):
        d = self.make_daemon({"mode": "always_pass"})
        turn, conn = self.make_turn(d)
        await turn.submit("最初の文面です。")
        ret = await turn.submit("二度目の文面です。")
        self.assertIn("すでにオーナーに届いています", ret)
        self.assertEqual(ret, ALREADY)
        self.assertEqual(len(conn.chunks()), 1)

    async def test_completion_rejection_limit_releases_unverified(self):
        d = self.make_daemon({"mode": "always_reject"}, {"completion_rejections": 2})
        turn, conn = self.make_turn(d)
        self.assertTrue((await turn.submit("文面その一です。")).startswith("差し戻し"))
        self.assertTrue((await turn.submit("文面その二です。")).startswith("差し戻し"))
        self.assertEqual(conn.updates, [])
        await turn.submit("文面その三です。")
        row = self.turn_row(d, turn)
        self.assertEqual(row["outcome"], "released_unverified")
        self.assertIn("完了判定を通っていません", row["final_text"])

    async def test_rejection_text_has_no_numbered_count(self):
        d = self.make_daemon({"mode": "always_reject"})
        turn, _ = self.make_turn(d)
        for i in range(3):
            ret = await turn.submit(f"文面{i}です。")
            self.assertTrue(ret.startswith("差し戻し"))
            self.assertIsNone(re.search(r"\d+\s*回目", ret))


class StopHook(ReplyBase):
    async def test_blocks_before_reply_then_releases_unverified(self):
        d = self.make_daemon({"mode": "always_reject"}, {"stop_hook_blocks": 2})
        turn, _ = self.make_turn(d)
        out = await turn.on_stop()
        self.assertEqual(out["decision"], "block")
        turn, _ = self.make_turn(d, self.make_session(d, "s2"))
        draft = "最後に送った文面です。"
        self.assertTrue((await turn.submit(draft)).startswith("差し戻し"))
        self.assertEqual((await turn.on_stop())["decision"], "block")
        self.assertEqual((await turn.on_stop())["decision"], "block")
        self.assertEqual(await turn.on_stop(), {})
        row = self.turn_row(d, turn)
        self.assertEqual(row["outcome"], "released_unverified")
        self.assertIn(draft, row["final_text"])
        self.assertIn("点検を通っていません", row["final_text"])

    async def test_no_submit_ends_as_failed(self):
        d = self.make_daemon({"mode": "always_pass"}, {"stop_hook_blocks": 2})
        turn, _ = self.make_turn(d)
        await turn.on_stop()
        await turn.on_stop()
        self.assertEqual(await turn.on_stop(), {})
        self.assertEqual(self.turn_row(d, turn)["outcome"], "failed")


class ConventionGate(ReplyBase):
    async def test_space_gap_rejected_up_to_rewrite_limit_then_passes(self):
        d = self.make_daemon({"mode": "always_pass"})
        self.assertEqual(d.cfg["limits"]["reporter_rewrites"], 2)
        turn, conn = self.make_turn(d)
        for name in ("memo.txt", "memo1.txt"):
            ret = await turn.submit(f"{name} を作りました。")
            self.assertTrue(ret.startswith("差し戻し"))
        self.assertEqual(conn.updates, [])
        ret = await turn.submit("memo2.txt を作りました。")
        self.assertTrue(ret.startswith("送信しました"))
        self.assertEqual(self.turn_row(d, turn)["outcome"], "released")


class ReportToParent(ReplyBase):
    def family(self, daemon):
        parent = self.make_session(daemon, "parent", "main", thread="thread-parent")
        child = self.make_session(daemon, "child", "worker", thread="thread-child", parent="parent")
        return parent, child

    async def test_worker_reports_to_parent_only_when_requested_by_session(self):
        d = self.make_daemon({"mode": "always_pass"})
        parent, child = self.family(d)
        with mock.patch("pda_pipeline.services.t3_thread_send", new=mock.AsyncMock()) as send:
            turn, _ = self.make_turn(d, child, requester="session:parent")
            await turn.submit("作業が終わりました。")
            send.assert_awaited_once()
            self.assertEqual(send.await_args.args[1], "thread-parent")
            row = self.turn_row(d, turn)
            self.assertEqual(row["reported_to"], "parent")
            self.assertIsNone(row["notified_at"])

        with mock.patch("pda_pipeline.services.t3_thread_send", new=mock.AsyncMock()) as send:
            turn, _ = self.make_turn(d, child, requester="owner")
            await turn.submit("作業が終わりました。")
            send.assert_not_awaited()


class Injection(ReplyBase):
    async def test_match_consumes_registration(self):
        d = self.make_daemon({"mode": "always_pass"})
        d.register_injection("t1", "報告です  本文", "session:abc")
        self.assertEqual(d.match_injection("t1", "報告です\n本文", False), "session:abc")
        self.assertEqual(d.match_injection("t1", "報告です 本文", False), "owner")

    async def test_unregistered_thread_is_owner_even_via_tools(self):
        d = self.make_daemon({"mode": "always_pass"})
        self.assertEqual(d.match_injection("none", "何か", True), "owner")

    async def test_via_tools_matches_registration_with_different_text(self):
        d = self.make_daemon({"mode": "always_pass"})
        d.register_injection("t1", "登録した文", "session:abc")
        self.assertEqual(d.match_injection("t1", "別の文", False), "owner")
        self.assertEqual(d.match_injection("t1", "さらに別の文", True), "session:abc")


if __name__ == "__main__":
    unittest.main()
