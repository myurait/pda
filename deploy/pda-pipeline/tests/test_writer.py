"""報告係のコンポーネント (writer.py) と、材料で預かった資料の流れの試験。中のエージェントは、固定の文を返す実装を使う。

    python3 -m unittest discover -s deploy/pda-pipeline/tests
"""
import copy
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pda_pipeline import config, writer  # noqa: E402
from pda_pipeline.daemon import Daemon, Turn  # noqa: E402

HTML = "<!doctype html><html><head><title>試験の資料</title></head><body><p>本文</p></body></html>"


class FakeConn:
    def __init__(self):
        self.updates = []

    def update(self, session_id, body):
        self.updates.append((session_id, body))

    def chunks(self):
        return [b for _, b in self.updates if b.get("sessionUpdate") == "agent_message_chunk"]


def make_cfg(tmp, fixed=None, reporter=True):
    cfg = copy.deepcopy(config.DEFAULTS)
    cfg["data_dir"] = tmp
    cfg["notify"]["enabled"] = False
    cfg["norms"]["enabled"] = False
    cfg["stages"] = {"reporter": reporter, "jev": False, "codex": True}
    cfg["judge"]["fixed"] = {"mode": "always_pass"}
    cfg["roles"]["reporter"].update({"agent": "fixed", "retry_wait_sec": 0})
    cfg["roles"]["reporter"]["agents"]["fixed"] = dict(fixed or {})
    return cfg


class CleanHtml(unittest.TestCase):
    def test_takes_html_out_of_fence_and_preamble(self):
        self.assertEqual(writer.clean_html(f"```html\n{HTML}\n```", "題"), HTML)
        self.assertEqual(writer.clean_html(f"資料です。\n{HTML}\n以上です。", "題"), HTML)

    def test_adds_title_when_missing(self):
        out = writer.clean_html("<html><head></head><body><p>本文</p></body></html>", "A<B")
        self.assertIn("<head><title>A&lt;B</title>", out)

    def test_rejects_text_that_is_not_html(self):
        with self.assertRaises(ValueError):
            writer.clean_html("資料は作れませんでした。", "題")


class RunAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.sems = {"default": __import__("asyncio").Semaphore(2)}

    async def test_retries_then_returns(self):
        cfg = make_cfg(self._tmp.name, {"fail": 2, "reply": "直した返信です。"})
        text = await writer.write_reply(cfg, self.sems, "依頼", "内容", time.monotonic() + 30)
        self.assertEqual(text, "直した返信です。")

    async def test_gives_up_after_attempts(self):
        cfg = make_cfg(self._tmp.name, {"fail": 99})
        with self.assertRaises(writer.WriterError) as ctx:
            await writer.write_reply(cfg, self.sems, "依頼", "内容", time.monotonic() + 30)
        self.assertEqual(ctx.exception.args[0]["agent"], "fixed")
        self.assertEqual(len(ctx.exception.args[0]["errors"]), 3)

    async def test_document_is_cleaned(self):
        cfg = make_cfg(self._tmp.name, {"document": f"```html\n{HTML}\n```"})
        out = await writer.write_document(cfg, self.sems, "依頼", "試験の資料", "材料", "内容", time.monotonic() + 30)
        self.assertEqual(out, HTML)

    async def test_document_that_is_not_html_fails(self):
        cfg = make_cfg(self._tmp.name, {"document": "作れませんでした。"})
        with self.assertRaises(writer.WriterError):
            await writer.write_document(cfg, self.sems, "依頼", "試験の資料", "材料", "内容", time.monotonic() + 30)


class MaterialFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def make_turn(self, cfg):
        d = Daemon(cfg)
        d.ledger.create_session("s1", "thread-s1", "c-s1", None)
        d.ledger.update_session("s1", role="main")
        conn = FakeConn()
        return d, Turn(d, conn, d.ledger.session("s1"), "依頼です。", "owner"), conn

    def events(self, d, kind):
        rows = d.ledger.db.execute("SELECT kind FROM events").fetchall()
        return [r for r in rows if r[0] == kind]

    async def test_reporter_writes_reply_and_document(self):
        cfg = make_cfg(self._tmp.name, {"reply": "報告係の返信です。", "document": HTML})
        d, turn, conn = self.make_turn(cfg)
        ret = await turn.attach_document({"title": "試験の資料", "material": "材料の文"})
        self.assertIn("材料を預かりました", ret)
        await turn.submit("作業するセッションの文です。")
        row = d.ledger.turn(turn.turn_id)
        self.assertEqual(row["outcome"], "released")
        self.assertEqual(row["final_text"].split("\n\n※")[0], "報告係の返信です。")
        doc = turn.documents["試験の資料"]
        self.assertEqual(doc["html"], HTML)
        self.assertEqual(pathlib.Path(doc["copy"]).read_text(encoding="utf-8"), HTML)
        self.assertTrue(pathlib.Path(doc["base"] + ".material.txt").is_file())
        self.assertEqual(len(self.events(d, "document_written")), 1)

    async def test_reporter_failure_releases_marked_text(self):
        cfg = make_cfg(self._tmp.name, {"fail": 99})
        d, turn, conn = self.make_turn(cfg)
        await turn.submit("作業するセッションの文です。")
        row = d.ledger.turn(turn.turn_id)
        self.assertEqual(row["outcome"], "released_unverified")
        self.assertIn("作業するセッションの文です。", row["final_text"])
        self.assertIn("報告係が文を整えられなかった", row["final_text"])

    async def test_document_failure_is_noted_in_reply(self):
        cfg = make_cfg(self._tmp.name, {"reply": "報告係の返信です。", "document": "作れませんでした。"})
        d, turn, conn = self.make_turn(cfg)
        await turn.attach_document({"title": "試験の資料", "material": "材料の文"})
        await turn.submit("作業するセッションの文です。")
        row = d.ledger.turn(turn.turn_id)
        self.assertEqual(row["outcome"], "released")
        self.assertIn("資料「試験の資料」は、報告係が作成できませんでした。", row["final_text"])

    async def test_without_reporter_material_is_shown_as_is(self):
        cfg = make_cfg(self._tmp.name, reporter=False)
        d, turn, conn = self.make_turn(cfg)
        await turn.attach_document({"title": "試験の資料", "material": "材料 <b>"})
        await turn.submit("作業するセッションの文です。")
        self.assertIn("材料 &lt;b&gt;", turn.documents["試験の資料"]["html"])


if __name__ == "__main__":
    unittest.main()
