"""環境変数のセット (env/、dev-pc/env/) と、環境を組む処理 (pda_pipeline/envset.py、dev-pc/pda-bridge) の試験。

    python3 -m unittest discover -s deploy/pda-pipeline/tests
"""
import importlib.machinery
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pda_pipeline import envset  # noqa: E402

MINI_DIR, DEV_DIR = ROOT / "env", ROOT / "dev-pc" / "env"
SECRET = re.compile(r"KEY|TOKEN|PASSWORD|PASSWD|SECRET|CREDENTIAL|AUTH", re.I)
ENVIRON = {"HOME": "/home/u", "USER": "u", "LOGNAME": "u", "SHELL": "/bin/bash", "LANG": "ja_JP.UTF-8",
           "LC_ALL": "ja_JP.UTF-8", "XDG_RUNTIME_DIR": "/run/user/1", "DBUS_SESSION_BUS_ADDRESS": "unix:x",
           "SSH_AUTH_SOCK": "/run/ssh", "XDG_DATA_DIRS": "/usr/share", "TMPDIR": "/tmp/x", "PATH": "/opt/other",
           "ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "http://x", "CLAUDE_CODE_ENTRYPOINT": "claude-desktop",
           "CLAUDE_CODE_ARTIFACT": "1", "PDA_JUNK": "1"}
CFG = {"claude_config_dir": "/home/u/pda/secrets/claude", "codex_home": None}


def load_bridge():
    loader = importlib.machinery.SourceFileLoader("pda_bridge", str(ROOT / "dev-pc" / "pda-bridge"))
    spec = importlib.util.spec_from_loader("pda_bridge", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


bridge = load_bridge()


def write_set(directory, name, data):
    pathlib.Path(directory, f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


class RepositorySets(unittest.TestCase):
    def all_sets(self):
        return [(d, p.stem) for d in (MINI_DIR, DEV_DIR) for p in sorted(d.glob("*.json"))]

    def test_expected_sets_exist_and_load(self):
        self.assertEqual(sorted(p.stem for p in MINI_DIR.glob("*.json")), ["codex", "reporter-claude", "session"])
        self.assertEqual(sorted(p.stem for p in DEV_DIR.glob("*.json")), ["publish", "request"])
        for directory, name in self.all_sets():
            spec = envset.load_set(name, directory)
            self.assertIn("PATH", spec["set"], name)
            self.assertNotIn("PATH", spec["inherit"], name)
            for var, entry in spec["set"].items():
                self.assertTrue(entry.get("effect"), f"{name} {var} に説明が無い")

    def test_fixed_values_are_not_secrets(self):
        for directory, name in self.all_sets():
            for var in envset.load_set(name, directory)["set"]:
                self.assertIsNone(SECRET.search(var), f"{name} の set に秘密を表す名前がある: {var}")

    def test_session_set(self):
        env = envset.build("session", CFG, {"PDA_SOCKET": "/s", "PDA_TURN_TOKEN": "t"}, ENVIRON, MINI_DIR)
        self.assertEqual(sorted(env), sorted([
            "PATH", "CLAUDE_CODE_STOP_HOOK_BLOCK_CAP", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS", "HOME", "USER",
            "LOGNAME", "SHELL", "LANG", "LC_ALL", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "SSH_AUTH_SOCK",
            "XDG_DATA_DIRS", "CLAUDE_CONFIG_DIR", "PDA_SOCKET", "PDA_TURN_TOKEN"]))
        self.assertEqual(env["PATH"], "/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], CFG["claude_config_dir"])
        self.assertEqual((env["CLAUDE_CODE_STOP_HOOK_BLOCK_CAP"], env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"]),
                         ("0", "1"))

    def test_session_set_needs_launch_values(self):
        with self.assertRaises(envset.EnvSetError):
            envset.build("session", CFG, {"PDA_SOCKET": "/s"}, ENVIRON, MINI_DIR)

    def test_reporter_and_codex_sets(self):
        self.assertEqual(sorted(envset.build("reporter-claude", CFG, None, ENVIRON, MINI_DIR)),
                         sorted(["PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "CLAUDE_CONFIG_DIR"]))
        self.assertEqual(sorted(envset.build("codex", CFG, None, ENVIRON, MINI_DIR)),
                         sorted(["PATH", "HOME", "LANG", "LC_ALL", "XDG_RUNTIME_DIR"]))
        env = envset.build("codex", {**CFG, "codex_home": "/c"}, None, ENVIRON, MINI_DIR)
        self.assertEqual(env["CODEX_HOME"], "/c")

    def test_dev_pc_sets(self):
        request = envset.build("request", {}, None, ENVIRON, DEV_DIR)
        publish = envset.build("publish", {}, None, ENVIRON, DEV_DIR)
        self.assertEqual(sorted(request), sorted(["PATH", "MCP_CONNECTION_NONBLOCKING", "MCP_CONNECT_TIMEOUT_MS",
                                                  "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR"]))
        self.assertEqual(sorted(publish), sorted([*request, "CLAUDE_CODE_ARTIFACT"]))
        self.assertEqual(publish["CLAUDE_CODE_ARTIFACT"], "1")
        self.assertEqual(request["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")


class Build(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        write_set(self.dir, "ok", {"description": "d", "set": {"A": {"value": "1", "effect": "e"}},
                                   "inherit": ["HOME", "NOT_THERE"], "config": {"B": "b", "C": "c"},
                                   "launch": ["L"]})

    def build_both(self, name, cfg, launch, environ):
        """2 つの実装に同じ入力を渡し、同じ結果か同じ失敗になることを確かめて、結果を返す。"""
        results = []
        for fn in (lambda: envset.build(name, cfg, launch, environ, self.dir),
                   lambda: bridge.build_env(name, {**cfg, "env_dir": self.dir}, launch, environ)):
            try:
                results.append(("ok", fn()))
            except (envset.EnvSetError, bridge.EnvSetError) as exc:
                results.append(("error", type(exc).__name__))
        self.assertEqual(results[0], results[1])
        return results[0]

    def test_builds_from_empty(self):
        kind, env = self.build_both("ok", {"b": "/x", "c": None}, {"L": "v"}, {"HOME": "/h", "OTHER": "o"})
        self.assertEqual((kind, env), ("ok", {"A": "1", "HOME": "/h", "B": "/x", "L": "v"}))

    def test_launch_must_match(self):
        self.assertEqual(self.build_both("ok", {}, {}, {})[0], "error")
        self.assertEqual(self.build_both("ok", {}, {"L": "v", "M": "w"}, {})[0], "error")

    def test_broken_sets_do_not_build(self):
        cases = {
            "dup": {"set": {"A": {"value": "1"}}, "inherit": ["A"]},
            "dup_list": {"inherit": ["HOME", "HOME"]},
            "badvalue": {"set": {"A": {"value": 1}}},
            "badfield": {"set": {}, "env": {}},
            "badname": {"inherit": ["A-B"]},
            "badkey": {"config": {"A": ""}},
        }
        for name, data in cases.items():
            write_set(self.dir, name, data)
            self.assertEqual(self.build_both(name, {}, {}, {})[0], "error", name)
        (pathlib.Path(self.dir) / "broken.json").write_text("{", encoding="utf-8")
        for name in ("broken", "missing", "../ok"):
            self.assertEqual(self.build_both(name, {}, {}, {})[0], "error", name)

    def test_repository_sets_agree(self):
        for directory, cfg in ((MINI_DIR, CFG), (DEV_DIR, {})):
            for path in directory.glob("*.json"):
                spec = envset.load_set(path.stem, directory)
                launch = {name: "v" for name in spec["launch"]}
                self.assertEqual(envset.build(path.stem, cfg, launch, ENVIRON, directory),
                                 bridge.build_env(path.stem, {**cfg, "env_dir": str(directory)}, launch, ENVIRON))


class EntryPoints(unittest.TestCase):
    def test_mini_pc_entry_runs_command_with_built_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = pathlib.Path(tmp, "config.json")
            conf.write_text(json.dumps({"codex_home": "/c"}), encoding="utf-8")
            out = subprocess.run([sys.executable, str(ROOT / "pda_pipeline" / "envset.py"), "codex", "--show"],
                                 capture_output=True, text=True,
                                 env={"HOME": "/h", "PDA_JUNK": "1", "PDA_PIPELINE_CONFIG": str(conf)})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), {"PATH": "/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin",
                                                  "HOME": "/h", "CODEX_HOME": "/c"})

    def test_bridge_entry_runs_command_with_built_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = pathlib.Path(tmp, "config.json")
            conf.write_text(json.dumps({"env_dir": str(DEV_DIR)}), encoding="utf-8")
            code = "import json, os; print(json.dumps(sorted(os.environ)))"
            out = subprocess.run([sys.executable, str(ROOT / "dev-pc" / "pda-bridge"), "--run", "publish", "--",
                                  sys.executable, "-I", "-c", code], capture_output=True, text=True,
                                 env={"HOME": "/h", "PDA_JUNK": "1", "PDA_BRIDGE_CONFIG": str(conf)})
        self.assertEqual(out.returncode, 0, out.stderr)
        names = set(json.loads(out.stdout))
        self.assertTrue({"PATH", "HOME", "CLAUDE_CODE_ARTIFACT", "MCP_CONNECT_TIMEOUT_MS"} <= names, names)
        self.assertNotIn("PDA_JUNK", names)
        self.assertNotIn("PDA_BRIDGE_CONFIG", names)


class BridgeLaunches(unittest.TestCase):
    """ブリッジが claude -p に渡す環境と、公開の結果の読み取り。claude は起こさず、subprocess.run を差し替える。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cfg = {**bridge.DEFAULTS, "env_dir": str(DEV_DIR), "workdir": str(pathlib.Path(self._tmp.name, "w")),
                    "published_file": str(pathlib.Path(self._tmp.name, "published.json")),
                    "allowed_tools_file": str(pathlib.Path(self._tmp.name, "none.txt"))}
        self.calls = []
        self.stdout = ""
        self._orig = bridge.subprocess.run
        bridge.subprocess.run = self.fake_run
        self.addCleanup(setattr, bridge.subprocess, "run", self._orig)
        self._env = dict(bridge.os.environ)
        bridge.os.environ.update({"CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "PDA_JUNK": "1"})
        self.addCleanup(self.restore_environ)

    def restore_environ(self):
        bridge.os.environ.clear()
        bridge.os.environ.update(self._env)

    def fake_run(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        stdout = self.stdout(cmd, kwargs) if callable(self.stdout) else self.stdout
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    def test_request_uses_request_set(self):
        self.stdout = json.dumps({"result": "答え", "is_error": False})
        self.assertEqual(bridge.run_job(self.cfg, "依頼"), (True, "答え"))
        env = self.calls[0][1]["env"]
        self.assertEqual(env, bridge.build_env("request", self.cfg))
        for name in ("CLAUDE_CODE_ARTIFACT", "CLAUDE_CODE_ENTRYPOINT", "PDA_JUNK"):
            self.assertNotIn(name, env)

    def test_missing_set_fails_the_job_only(self):
        self.cfg["env_dir"] = str(pathlib.Path(self._tmp.name, "none"))
        ok, text = bridge.run_job(self.cfg, "依頼")
        self.assertFalse(ok)
        self.assertIn("起動できませんでした", text)
        ok, text = bridge.run_publish(self.cfg, "0" * 36, {"doc": "d", "html": "<p>x</p>"})
        self.assertFalse(ok)
        self.assertEqual(self.calls, [])

    def publish_events(self, url, read_html):
        def make(cmd, kwargs):
            path = str(pathlib.Path(kwargs["cwd"], bridge.PUBLISH_FILE))
            events = [{"type": "system", "subtype": "init", "tools": ["Read", "Artifact", "mcp__x__y"]}]
            if url:
                events += [
                    {"type": "assistant", "message": {"content": [
                        {"type": "tool_use", "id": "r", "name": "Artifact", "input": {"action": "read", "url": url}}]}},
                    {"type": "user", "message": {"content": [
                        {"type": "tool_result", "tool_use_id": "r", "content": read_html}]}}]
            args = {"file_path": path, **({"url": url} if url else {})}
            published = url or "https://claude.ai/artifact/New123"
            events += [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "p", "name": "Artifact", "input": args}]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "p", "content": f"Published document.html at {published}"}]}}]
            return "\n".join(json.dumps(e) for e in events)
        return make

    def test_publish_new_then_update_with_read(self):
        self.stdout = self.publish_events(None, "")
        ok, url = bridge.run_publish(self.cfg, "1" * 36, {"doc": "s:題", "html": "<p>x</p>"})
        self.assertEqual((ok, url), (True, "https://claude.ai/artifact/New123"))
        cmd, kwargs = self.calls[0]
        self.assertEqual(kwargs["env"], bridge.build_env("publish", self.cfg))
        self.assertEqual(kwargs["env"]["CLAUDE_CODE_ARTIFACT"], "1")
        self.assertNotIn("CLAUDE_CODE_ENTRYPOINT", kwargs["env"])
        self.assertIn("ArtifactComments,ArtifactData", cmd)
        self.assertNotIn("action に read", kwargs["input"])
        settings = json.loads(cmd[cmd.index("--settings") + 1])
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["matcher"], "*")

        # 取得の結果の本文に別のリンクがあっても、公開の呼び出しの結果からだけリンクを取る
        self.stdout = self.publish_events(url, "Published x at https://claude.ai/artifact/Other999")
        ok, again = bridge.run_publish(self.cfg, "2" * 36, {"doc": "s:題", "html": "<p>y</p>"})
        self.assertEqual((ok, again), (True, url))
        self.assertIn(f"action に read、url に {url}", self.calls[1][1]["input"])
        self.assertEqual(json.loads(pathlib.Path(self.cfg["published_file"]).read_text()), {"s:題": url})

    def test_read_of_other_artifact_that_slipped_through_fails(self):
        url = "https://claude.ai/artifact/Mine1"
        pathlib.Path(self.cfg["published_file"]).write_text(json.dumps({"s:題": url}))

        def make(cmd, kwargs):
            return json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "r", "name": "Artifact",
                 "input": {"action": "read", "url": "https://claude.ai/artifact/Other"}}]}}) + "\n" + json.dumps(
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "r", "content": "x"}]}})
        self.stdout = make
        ok, text = bridge.run_publish(self.cfg, "3" * 36, {"doc": "s:題", "html": "<p>x</p>"})
        self.assertFalse(ok)
        self.assertIn("外れた", text)


if __name__ == "__main__":
    unittest.main()
