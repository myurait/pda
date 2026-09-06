"""Reproduce the live bug, then verify the saved patch on real subprocesses."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/home/user/.hermes/hermes-agent")
PROBE = ROOT / "tests/probe_snapshot_safety.py"
PATCH = ROOT / "0002-fix-delegated-child-shell-snapshot.patch"
TARGET = Path("tools/environments/base.py")


def run_probe(scenario: str, overlay: Path | None = None):
    command = [sys.executable, "-B", str(PROBE), "--source", str(SOURCE), "--scenario", scenario]
    if overlay is not None:
        command += ["--overlay", str(overlay)]
    return subprocess.run(command, capture_output=True, text=True, timeout=90)


@pytest.mark.parametrize("scenario", ["sequential", "failed-command"])
def test_unpatched_shell_rejects_the_real_parent_after_child(scenario):
    result = run_probe(scenario)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "AssertionError: ('parent-after', {'marker': '1', 'kanban_allowed': False" in result.stderr


@pytest.fixture
def patched_overlay(tmp_path):
    destination = tmp_path / TARGET
    destination.parent.mkdir(parents=True)
    shutil.copy2(SOURCE / TARGET, destination)
    result = subprocess.run(["patch", "--batch", "--forward", "-p1", "--input", str(PATCH)], cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    compile(destination.read_text(), str(destination), "exec")
    return tmp_path


@pytest.mark.parametrize("scenario", ["sequential", "failed-command", "context-exception", "child-first", "concurrent"])
def test_patched_shell_keeps_parent_and_child_authority_separate(patched_overlay, scenario):
    result = run_probe(scenario, patched_overlay)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["fresh_child_guard"] == "passed"
    parent_after = [item for item in report["observations"] if item["label"] == "parent-after"]
    assert len(parent_after) == 1 and parent_after[0]["kanban_allowed"] is True


def test_patch_only_changes_snapshot_serialization():
    text = PATCH.read_text()
    assert re.findall(r"^diff --git a/(\S+) b/(\S+)$", text, re.MULTILINE) == [(str(TARGET), str(TARGET))]


def test_combined_manifest_binds_order_and_every_target():
    manifest = json.loads((ROOT / "recovery-manifest.json").read_text())
    assert manifest["base_commit"] == json.loads((ROOT / "manifest.json").read_text())["base_commit"]
    assert [p["file"] for p in manifest["patches"]] == ["0001-fix-delegation-cap-continuation-and-child-context.patch", PATCH.name]
    for patch in manifest["patches"]:
        assert hashlib.sha256((ROOT / patch["file"]).read_bytes()).hexdigest() == patch["sha256"]
    for name, digest in manifest["base_files"].items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest["sha256"]
    assert manifest["live_checkout_modified"] is False
