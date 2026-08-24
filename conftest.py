"""Repository-wide pytest guardrails for Kanban isolation.

Incident t_4a78c98b: dispatcher-managed worker environments carry
``HERMES_KANBAN_DB`` pinned to the production board, which outranks the
``HERMES_HOME``-based isolation every test in this repository relied on.
Twelve synthetic cards leaked into the production board that way.

This conftest makes that class of leak impossible for anything run under
pytest from the repository root:

1. The ambient ``HERMES_KANBAN_*`` override variables are scrubbed from the
   process environment before any test or fixture can inherit them, so a
   worker/delegate environment cannot silently redirect test traffic.
2. The production board paths observed at session start are recorded, and
   ``hermes_cli.kanban_db`` path resolution (used by ``connect``,
   ``connect_closing`` and ``init_db``) fails closed if any test would
   resolve to one of them.

``HERMES_KANBAN_TASK`` joins the scrub for the same reason at a different
target: the dispatcher exports the card id it spawned a worker for, and the
scope gate reads it as the authoritative task binding. Left ambient it would
outrank the explicit identifiers every gate test passes in, so a suite run
inside a worker environment would silently exercise one binding while
asserting another.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

KANBAN_ENV_OVERRIDES = (
    "HERMES_KANBAN_DB",
    "HERMES_KANBAN_HOME",
    "HERMES_KANBAN_BOARD",
    "HERMES_KANBAN_WORKSPACES_ROOT",
    "HERMES_KANBAN_ATTACHMENTS_ROOT",
    "HERMES_KANBAN_TASK",
)


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser()


def _capture_production_kanban_paths() -> set[Path]:
    paths: set[Path] = set()
    pinned = os.environ.get("HERMES_KANBAN_DB", "").strip()
    if pinned:
        paths.add(_safe_resolve(Path(pinned)))
    roots = {Path.home() / ".hermes"}
    ambient_home = os.environ.get("HERMES_HOME", "").strip()
    if ambient_home:
        roots.add(Path(ambient_home).expanduser())
    for root in roots:
        paths.add(_safe_resolve(root / "kanban.db"))
    return paths


PRODUCTION_KANBAN_PATHS = frozenset(_capture_production_kanban_paths())

# Scrub ambient overrides at import time: a worker environment must never be
# able to redirect a test at higher precedence than the test's own fixtures.
for _name in KANBAN_ENV_OVERRIDES:
    os.environ.pop(_name, None)


class KanbanGuard:
    """Deny-list of kanban DB paths tests must never resolve to."""

    def __init__(self) -> None:
        self.denied: set[Path] = set(PRODUCTION_KANBAN_PATHS)

    def deny(self, path: Path | str) -> Path:
        resolved = _safe_resolve(Path(path))
        self.denied.add(resolved)
        return resolved


_GUARD = KanbanGuard()


@pytest.fixture
def kanban_guard() -> KanbanGuard:
    return _GUARD


@pytest.fixture(scope="session", autouse=True)
def _fail_closed_on_production_kanban():
    try:
        from hermes_cli import kanban_db
    except Exception:
        yield
        return

    original = kanban_db.kanban_db_path

    def guarded_kanban_db_path(board=None):
        resolved = original(board)
        if _safe_resolve(resolved) in _GUARD.denied:
            raise RuntimeError(
                "fail-closed: test resolved a production kanban DB "
                f"({resolved}); see incident t_4a78c98b"
            )
        return resolved

    kanban_db.kanban_db_path = guarded_kanban_db_path
    try:
        yield
    finally:
        kanban_db.kanban_db_path = original
