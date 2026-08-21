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
