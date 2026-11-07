#!/usr/bin/env python3
"""memory-style-gate.py のテスト。Jev は呼ばず、語の形での検査 (MEMORY_STYLE_GATE_NO_JEV=1) で動かす。"""

import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import shutil
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
TMP = tempfile.mkdtemp()
os.environ["MEMORY_STYLE_GATE_NO_JEV"] = "1"
os.environ["MEMORY_STYLE_GATE_STATE_DIR"] = TMP
os.environ["MEMORY_STYLE_GATE_TRACE"] = os.path.join(TMP, "trace.log")

# 対象の判定は /tmp/ を含むパスを除くので、テストのファイルはこのディレクトリの下に作って最後に消す
DATA = HERE / ".testdata"


def tearDownModule():
    shutil.rmtree(DATA, ignore_errors=True)


def fresh_dir() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(dir=_ensure(DATA)))


def _ensure(p: pathlib.Path) -> pathlib.Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


spec = importlib.util.spec_from_file_location("gate", HERE / "memory-style-gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

OLD = """---
name: sample-old
description: 古い形のサンプル
metadata:
  type: feedback
---

コミットは確認要求を挟まずに実行する。事例で書かない。

**Why:**

索引に載っていないメモリは読み込まれないため、索引を更新する。

| 発火する事象 | 実行する操作 |
|---|---|
| メモリを**書いた** | 索引を更新する |
"""

NEW = """---
name: sample-new
description: 新しい形のサンプル。各ルールを言い切りの命令文で書く
metadata:
  type: feedback
---

- 各ルールを、する操作を言い切る命令文 1 文で書く
- 書き換えたすべてのメモリの索引行を、同じ操作で書き換える
- 「X したとき Y する」 → 「X したすべての Z に Y する」
- 関連メモリは本文の末尾に `[[name]]` で並べる
"""


def write(dirpath: pathlib.Path, name: str, text: str) -> pathlib.Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / name
    p.write_text(text, encoding="utf-8")
    return p


class Target(unittest.TestCase):
    def test_memory_and_skill_are_targets(self):
        self.assertTrue(gate.is_target(pathlib.Path("/x/.claude/memory/a.md")))
        self.assertTrue(gate.is_target(pathlib.Path("/x/docs/jev/skills/jev/SKILL.md")))
        self.assertTrue(gate.is_target(pathlib.Path("/x/.claude/projects/p/memory/MEMORY.md")))

    def test_excluded_paths(self):
        self.assertFalse(gate.is_target(pathlib.Path("/x/.claude/skills/synced/a/SKILL.md")))
        self.assertFalse(gate.is_target(pathlib.Path("/x/docs/tmp/memory/a.md")))
        self.assertFalse(gate.is_target(pathlib.Path("/x/src/readme.md")))
        self.assertFalse(gate.is_target(pathlib.Path("/x/.claude/memory/a.py")))


class Check(unittest.TestCase):
    def setUp(self):
        self.dir = fresh_dir() / "skills" / "s"

    def test_old_style_is_reported(self):
        p = write(self.dir, "SKILL.md", OLD)
        lines = "\n".join(gate.check_file(p))
        self.assertIn("(emphasis)", lines)
        self.assertIn("(heading)", lines)
        self.assertIn("(table)", lines)
        self.assertIn("(prohibitive)", lines)
        self.assertIn("(rationale)", lines)

    def test_new_style_passes(self):
        p = write(self.dir, "SKILL.md", NEW)
        self.assertEqual(gate.check_file(p), [])


class Hook(unittest.TestCase):
    def run_hook(self, func, payload):
        buf = io.StringIO()
        with redirect_stdout(buf):
            func(payload)
        out = buf.getvalue().strip()
        return json.loads(out) if out else None

    def test_post_tool_use_blocks_twice_then_passes(self):
        p = write(fresh_dir() / "skills" / "s", "SKILL.md", OLD)
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(p)}, "session_id": "t1"}
        first = self.run_hook(gate.post_tool_use, payload)
        second = self.run_hook(gate.post_tool_use, payload)
        third = self.run_hook(gate.post_tool_use, payload)
        self.assertEqual(first["decision"], "block")
        self.assertIn("feedback_memory_writing_rules.md", first["reason"])
        self.assertEqual(second["decision"], "block")
        self.assertIsNone(third)

    def test_post_tool_use_ignores_other_files(self):
        p = write(fresh_dir() / "src", "notes.md", OLD)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}, "session_id": "t2"}
        self.assertIsNone(self.run_hook(gate.post_tool_use, payload))

    def test_post_tool_use_ignores_other_tools(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/x/.claude/memory/a.md"}, "session_id": "t3"}
        self.assertIsNone(self.run_hook(gate.post_tool_use, payload))

    def test_stop_passes_when_already_stopped(self):
        self.assertIsNone(self.run_hook(gate.stop, {"stop_hook_active": True, "session_id": "t4"}))


if __name__ == "__main__":
    unittest.main()
