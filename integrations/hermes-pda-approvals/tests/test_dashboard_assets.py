from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_manifest_registers_approval_tab_and_authenticated_backend():
    agent_manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    assert "name: pda-approvals" in agent_manifest
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "pda-approvals"
    assert manifest["tab"]["path"] == "/pda-approvals"
    assert manifest["tab"]["position"] == "after:kanban"
    assert manifest["api"] == "plugin_api.py"
    assert "header-right" in manifest["slots"]


def test_bundle_uses_digest_bound_actions_and_header_badge():
    source = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")

    assert "/api/plugins/pda-approvals/pending" in source
    assert "/approve" in source
    assert "digest: item.digest" in source
    assert "/request-changes" in source
    assert "window.confirm" in source
    assert "window.prompt" in source
    assert 'register("pda-approvals"' in source
    assert 'registerSlot("pda-approvals", "header-right"' in source
    assert "window.__HERMES_BASE_PATH__" in source
    assert 'href: basePath + "/pda-approvals"' in source
    assert "dangerouslySetInnerHTML" not in source


def test_bundle_shows_only_owner_decision_fields_by_default():
    source = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")

    for field in (
        "approval_subject",
        "purpose",
        "changes_after_approval",
        "risk_and_reversibility",
        "recommendation",
        "action",
    ):
        assert "ownerMessage." + field in source

    for worker_detail in (
        "approval.head_sha",
        "approval.changed_files",
        "approval.verification",
        "finalization.steps",
        'h("code", null, item.task_id)',
        '"変更ファイル"',
        '"検証"',
        '"反映手順"',
        '"HEAD: "',
    ):
        assert worker_detail not in source
