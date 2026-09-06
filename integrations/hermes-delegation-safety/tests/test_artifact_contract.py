from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERMES_SOURCE = Path("/home/user/.hermes/hermes-agent")
MANIFEST = ROOT / "manifest.json"
README = ROOT / "README.md"
PATCH = ROOT / "0001-fix-delegation-cap-continuation-and-child-context.patch"
EXPECTED_BASE = "5112f51749ac744923a702900730149dfc8634da"
EXPECTED_TARGETS = ["agent/tool_guardrails.py", "tools/delegate_tool.py"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_binds_base_sources_and_patch() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["base_commit"] == EXPECTED_BASE
    assert manifest["contains_secrets"] is False
    assert manifest["application"]["approval_required"] is True
    assert manifest["application"]["live_checkout_modified"] is False

    source_files = manifest["base_files"]
    assert list(source_files) == EXPECTED_TARGETS
    for relative in EXPECTED_TARGETS:
        assert source_files[relative]["sha256"] == _sha256(HERMES_SOURCE / relative)

    assert manifest["patches"] == [
        {
            "file": PATCH.name,
            "sha256": _sha256(PATCH),
            "targets": EXPECTED_TARGETS,
        }
    ]


def test_patch_only_changes_manifest_targets() -> None:
    patch_text = PATCH.read_text(encoding="utf-8")
    targets = re.findall(r"^diff --git a/(\S+) b/(\S+)$", patch_text, re.MULTILINE)
    assert targets == [(target, target) for target in EXPECTED_TARGETS]


def test_readme_documents_bounded_apply_verify_and_rollback() -> None:
    text = README.read_text(encoding="utf-8")

    assert EXPECTED_BASE in text
    for heading in ("## 影響", "## 検証", "## 適用", "## rollback"):
        assert heading in text
    assert "digest-bound" in text
    assert "live Hermes checkoutは未変更" in text
