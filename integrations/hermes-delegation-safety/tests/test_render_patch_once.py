from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from render_patch import render_patch  # noqa: E402


def test_canonical_patch_matches_renderer() -> None:
    source = Path("/home/user/.hermes/hermes-agent")
    destination = ROOT / "0001-fix-delegation-cap-continuation-and-child-context.patch"
    rendered = render_patch(source)
    assert destination.read_text(encoding="utf-8") == rendered
