"""claude-login-expiry-notify の判定の試験。

実行: python3 -m unittest deploy/claude-remote-control/test_claude_login_expiry_notify.py
"""

import datetime
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("claude-login-expiry-notify")
_loader = importlib.machinery.SourceFileLoader("claude_login_expiry_notify", str(SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
notify = importlib.util.module_from_spec(_spec)
_loader.exec_module(notify)

NOW = datetime.datetime(2026, 11, 20, 10, 30, tzinfo=notify.JST)


class BuildNoticeTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._saved = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self._dir.name

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self._saved
        self._dir.cleanup()

    def write_credentials(self, expiry, refresh_token="rt"):
        expires_ms = int(expiry.timestamp() * 1000) if expiry else 0
        data = {"claudeAiOauth": {"refreshToken": refresh_token, "refreshTokenExpiresAt": expires_ms}}
        pathlib.Path(self._dir.name, ".credentials.json").write_text(json.dumps(data))

    def test_more_than_notify_days_left_sends_nothing(self):
        self.write_credentials(NOW + datetime.timedelta(days=notify.NOTIFY_DAYS, hours=1))
        self.assertIsNone(notify.build_notice(NOW))

    def test_within_notify_days_reports_days_left(self):
        self.write_credentials(NOW + datetime.timedelta(days=2, hours=5))
        title, message = notify.build_notice(NOW)
        self.assertIn("あと 2 日", title)
        self.assertIn("claude auth login", message)

    def test_less_than_a_day_reports_hours_left(self):
        self.write_credentials(NOW + datetime.timedelta(hours=9, minutes=40))
        title, _ = notify.build_notice(NOW)
        self.assertIn("あと 9 時間", title)

    def test_past_expiry_reports_expired(self):
        self.write_credentials(NOW - datetime.timedelta(hours=1))
        title, _ = notify.build_notice(NOW)
        self.assertIn("切れています", title)

    def test_cleared_tokens_report_expired(self):
        self.write_credentials(None, refresh_token="")
        title, _ = notify.build_notice(NOW)
        self.assertIn("切れています", title)

    def test_missing_credentials_still_notifies(self):
        title, _ = notify.build_notice(NOW)
        self.assertIn("確認できません", title)


if __name__ == "__main__":
    unittest.main()
