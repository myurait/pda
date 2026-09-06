#!/usr/bin/env python3
"""Reconstruct the exact recovery series in a disposable clone, never live."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def checked(command: list[str], cwd: Path | None = None, timeout: int = 60) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{command!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--upstream-tests", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    manifest = json.loads((ROOT / "recovery-manifest.json").read_text())
    assert checked(["git", "rev-parse", "HEAD"], source) == manifest["base_commit"]
    for path, record in manifest["base_files"].items():
        assert hashlib.sha256((source / path).read_bytes()).hexdigest() == record["sha256"], path
    for patch in manifest["patches"]:
        assert hashlib.sha256((ROOT / patch["file"]).read_bytes()).hexdigest() == patch["sha256"]
    with tempfile.TemporaryDirectory(prefix="pda-recovery-reconstruct-") as temporary:
        clone = Path(temporary) / "source"
        checked(["git", "clone", "--quiet", "--shared", "--no-checkout", str(source), str(clone)], timeout=90)
        checked(["git", "checkout", "--quiet", "--detach", manifest["base_commit"]], clone)
        for patch in manifest["patches"]:
            checked(["git", "apply", "--check", "--index", str(ROOT / patch["file"])], clone)
            checked(["git", "apply", "--index", str(ROOT / patch["file"])], clone)
        changed = checked(["git", "diff", "--cached", "--name-only"], clone).splitlines()
        assert sorted(changed) == sorted(manifest["base_files"]), changed
        expected_tree = checked(["git", "write-tree"], clone)
        if manifest.get("expected_tree"):
            assert expected_tree == manifest["expected_tree"]
        cap_probe = checked([sys.executable, "-B", str(ROOT / "tests/probe_delegation_safety.py"), "--source", str(clone), "--scratch", str(Path(temporary) / "cap-scratch")])
        snapshot_probes = []
        for scenario in ("sequential", "failed-command", "context-exception", "child-first", "concurrent"):
            snapshot_probes.append(json.loads(checked([sys.executable, "-B", str(ROOT / "tests/probe_snapshot_safety.py"), "--source", str(clone), "--scenario", scenario], timeout=90)))
        upstream = None
        if args.upstream_tests:
            upstream = checked([
                "bash", "scripts/run_tests.sh", "-j", "2", "--file-timeout", "90",
                "tests/tools/test_snapshot_session_id_leak.py",
                "tests/tools/test_snapshot_multiline_session_env_injection.py",
                "tests/tools/test_local_env_session_leak.py",
                "tests/tools/test_hermes_subprocess_env.py",
                "tests/tools/test_delegate_kanban_isolation.py",
            ], clone, timeout=180)
        for patch in reversed(manifest["patches"]):
            checked(["git", "apply", "--reverse", "--check", "--index", str(ROOT / patch["file"])], clone)
            checked(["git", "apply", "--reverse", "--index", str(ROOT / patch["file"])], clone)
        assert checked(["git", "write-tree"], clone) == checked(["git", "rev-parse", "HEAD^{tree}"], clone)
        print(json.dumps({"expected_tree": expected_tree, "changed_files": changed, "cap_probe": cap_probe, "snapshot_scenarios": [p["scenario"] for p in snapshot_probes], "upstream_tests": upstream, "rollback_tree_restored": True, "live_checkout_modified": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
