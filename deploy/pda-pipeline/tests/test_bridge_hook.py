"""開発 PC のブリッジの、Artifact の道具の hook (pda-bridge --artifact-hook) の試験。

    python3 -m unittest discover -s deploy/pda-pipeline/tests
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

BRIDGE = str(pathlib.Path(__file__).resolve().parent.parent / "dev-pc" / "pda-bridge")
URL = "https://claude.ai/artifact/AbCdEf0123456789"


class ArtifactHook(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.file = str(pathlib.Path(self._tmp.name, "document.html"))
        pathlib.Path(self.file).write_text("<p>x</p>", encoding="utf-8")

    def run_hook(self, tool_input, url="-", tool_name="Artifact", raw=None):
        stdin = raw if raw is not None else json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run([sys.executable, BRIDGE, "--artifact-hook", self.file, url], input=stdin,
                              capture_output=True, text=True)

    def assert_allowed(self, out):
        self.assertEqual((out.returncode, out.stdout), (0, ""))

    def assert_denied(self, out):
        self.assertEqual(out.returncode, 2)
        self.assertEqual(json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_allows_new_publish_of_the_file(self):
        self.assert_allowed(self.run_hook({"file_path": self.file, "icon": "document"}))
        self.assert_allowed(self.run_hook({"action": "publish", "file_path": self.file, "description": "d"}))

    def test_allows_update_of_own_url_only(self):
        self.assert_allowed(self.run_hook({"file_path": self.file, "url": URL}, url=URL))
        self.assert_denied(self.run_hook({"file_path": self.file, "url": URL + "x"}, url=URL))
        self.assert_denied(self.run_hook({"file_path": self.file, "url": URL}))

    def test_denies_other_actions(self):
        for action in ("list", "delete", "open", "pin", "unpin", "quickstart"):
            self.assert_denied(self.run_hook({"action": action, "url": URL}, url=URL))

    def test_read_of_own_url_before_update_only(self):
        self.assert_allowed(self.run_hook({"action": "read", "url": URL}, url=URL))
        self.assert_denied(self.run_hook({"action": "read", "url": URL}))
        self.assert_denied(self.run_hook({"action": "read", "url": URL + "x"}, url=URL))
        self.assert_denied(self.run_hook({"action": "read"}, url=URL))
        for extra in ({"path": "index.html"}, {"paths": ["a"]}, {"out_dir": "/tmp"}, {"page": True}):
            self.assert_denied(self.run_hook({"action": "read", "url": URL, **extra}, url=URL))

    def test_denies_other_files_and_extra_arguments(self):
        other = str(pathlib.Path(self._tmp.name, "other.html"))
        self.assert_denied(self.run_hook({"file_path": other}))
        self.assert_denied(self.run_hook({"file_path": "/etc/hosts"}))
        self.assert_denied(self.run_hook({}))
        self.assert_denied(self.run_hook({"file_path": self.file, "files": {"a.js": other}}))
        self.assert_denied(self.run_hook({"file_path": self.file, "asset": True, "url": URL}, url=URL))
        self.assert_denied(self.run_hook({"file_path": self.file, "from_url": URL}))

    def test_denies_other_tools_and_broken_input(self):
        for name in ("ArtifactData", "ArtifactComments", "Write", "Bash", "mcp__claude_ai_Slack__slack_send_message"):
            self.assert_denied(self.run_hook({"file_path": self.file, "url": URL}, url=URL, tool_name=name))
        self.assert_denied(self.run_hook(None, raw="not json"))
        self.assert_denied(self.run_hook(None, raw=json.dumps({"tool_name": "Artifact", "tool_input": "x"})))

    def test_read_is_limited_to_the_file(self):
        self.assert_allowed(self.run_hook({"file_path": self.file}, tool_name="Read"))
        self.assert_denied(self.run_hook({"file_path": "/etc/hosts"}, tool_name="Read"))
        self.assert_denied(self.run_hook({}, tool_name="Read"))

    def test_missing_arguments_deny(self):
        out = subprocess.run([sys.executable, BRIDGE, "--artifact-hook"], input="{}", capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
