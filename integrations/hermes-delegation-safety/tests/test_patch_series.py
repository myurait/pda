from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "probe_delegation_safety.py"
PATCH = ROOT / "0001-fix-delegation-cap-continuation-and-child-context.patch"
HERMES_SOURCE = Path("/home/user/.hermes/hermes-agent")
BASE_COMMIT = "5112f51749ac744923a702900730149dfc8634da"
PATCHED_FILES = (
    Path("agent/tool_guardrails.py"),
    Path("tools/delegate_tool.py"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_head_without_git(source: Path) -> str:
    git_dir = source / ".git"
    if git_dir.is_file():
        marker = git_dir.read_text(encoding="utf-8").strip()
        prefix = "gitdir: "
        assert marker.startswith(prefix), marker
        git_dir = (source / marker[len(prefix) :]).resolve()
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:]
    loose = git_dir / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip()
    for line in (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "^")):
            commit, name = line.split(" ", 1)
            if name == ref:
                return commit
    raise AssertionError(f"cannot resolve {ref}")


def _diagnose_patch_context() -> str:
    lines = PATCH.read_text(encoding="utf-8").splitlines()
    current: Path | None = None
    reports: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("--- a/"):
            current = Path(line[6:])
        match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if match and current is not None:
            start = int(match.group(1))
            declared = int(match.group(2) or "1")
            old_lines: list[str] = []
            new_lines: list[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate.startswith(("@@ ", "diff --git ", "--- a/", "-- ")):
                    index -= 1
                    break
                if candidate.startswith((" ", "-")):
                    old_lines.append(candidate[1:])
                if candidate.startswith((" ", "+")):
                    new_lines.append(candidate[1:])
                index += 1
            actual = (HERMES_SOURCE / current).read_text(encoding="utf-8").splitlines()[
                start - 1 : start - 1 + len(old_lines)
            ]
            mismatch = next(
                (
                    f"line {start + offset}: expected={expected!r} actual={found!r}"
                    for offset, (expected, found) in enumerate(zip(old_lines, actual))
                    if expected != found
                ),
                "none",
            )
            declared_new = int(match.group(4) or "1")
            reports.append(
                f"{current}@{start}: declared_old={declared} parsed_old={len(old_lines)} "
                f"declared_new={declared_new} parsed_new={len(new_lines)} "
                f"first_mismatch={mismatch}"
            )
        index += 1
    return "\n".join(reports)


def _run_probe(*, overlay: Path | None, scratch: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(PROBE),
        "--source",
        str(HERMES_SOURCE),
    ]
    if overlay is not None:
        command.extend(("--overlay", str(overlay)))
    command.extend(("--scratch", str(scratch)))
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def test_unpatched_base_reproduces_all_three_regressions() -> None:
    scratch = ROOT / ".probe-base-pytest"
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        result = _run_probe(overlay=None, scratch=scratch)
        assert result.returncode == 1, result.stdout + result.stderr
        for label in (
            "cap primitive",
            "agent-loop continuation",
            "child retry context and parent Kanban mutation",
        ):
            assert f"FAIL: {label}" in result.stderr
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_patch_series_applies_and_probe_passes() -> None:
    assert _read_head_without_git(HERMES_SOURCE) == BASE_COMMIT
    overlay = ROOT / ".patched-overlay"
    scratch = ROOT / ".probe-pytest"
    shutil.rmtree(overlay, ignore_errors=True)
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        for relative in PATCHED_FILES:
            destination = overlay / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERMES_SOURCE / relative, destination)

        applied = subprocess.run(
            ["patch", "--batch", "--forward", "-p1", "--input", str(PATCH)],
            cwd=overlay,
            text=True,
            capture_output=True,
            check=False,
        )
        assert applied.returncode == 0, (
            applied.stdout + applied.stderr + "\n" + _diagnose_patch_context()
        )

        for relative in PATCHED_FILES:
            path = overlay / relative
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

        result = _run_probe(overlay=overlay, scratch=scratch)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "All 3 focused delegation-safety checks passed." in result.stdout

        print(f"base_commit={BASE_COMMIT}")
        for relative in PATCHED_FILES:
            print(f"base_sha256[{relative}]={_sha256(HERMES_SOURCE / relative)}")
        print(f"patch_sha256={_sha256(PATCH)}")
    finally:
        shutil.rmtree(overlay, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)
