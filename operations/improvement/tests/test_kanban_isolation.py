"""Regression tests for incident t_4a78c98b (production kanban leak).

The incident: a dispatcher-managed worker environment carried
``HERMES_KANBAN_DB`` pinned to the production board, which outranked the
``HERMES_HOME``-only isolation used by every test, so synthetic test cards
were written to the production kanban DB.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hermes_cli import kanban_db

import operations.improvement.install as install_module
from operations.improvement.install import KANBAN_ENV_OVERRIDES, RuntimePaths


def test_session_environment_carries_no_ambient_kanban_overrides():
    # conftest.py scrubs these at import time; a worker/delegate environment
    # must not be able to redirect the whole test session.
    for name in KANBAN_ENV_OVERRIDES:
        assert name not in os.environ


def test_worker_pinned_production_board_is_unreachable(
    tmp_path, monkeypatch, kanban_guard
):
    # Replay the incident: the environment pins a "production" board at the
    # highest resolution precedence. The session guard must fail closed
    # before any schema write happens.
    production = kanban_guard.deny(tmp_path / "production-kanban.db")
    monkeypatch.setenv("HERMES_KANBAN_DB", str(production))

    with pytest.raises(RuntimeError, match="fail-closed"):
        kanban_db.init_db()
    with pytest.raises(RuntimeError, match="fail-closed"):
        kanban_db.connect()

    assert not production.exists()


def test_default_env_strips_ambient_kanban_overrides(tmp_path, monkeypatch):
    for name in KANBAN_ENV_OVERRIDES:
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    paths = RuntimePaths(
        home=tmp_path / "user",
        hermes_home=tmp_path / "user" / ".hermes",
        python_executable=Path("/usr/bin/python3"),
    )

    env = install_module._default_env(paths)

    assert env["HERMES_HOME"] == str(paths.hermes_home)
    for name in KANBAN_ENV_OVERRIDES:
        assert name not in env


def test_control_board_neutralizes_ambient_pin_and_restores_it(
    tmp_path, monkeypatch
):
    ambient = tmp_path / "ambient-kanban.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(ambient))
    paths = RuntimePaths(
        home=tmp_path / "user",
        hermes_home=tmp_path / "user" / ".hermes",
        python_executable=Path("/usr/bin/python3"),
    )
    paths.hermes_home.mkdir(parents=True)

    with install_module._control_board(paths):
        # Inside the control-board context the ambient pin must be gone and
        # resolution must land on the control-owned HERMES_HOME board.
        assert "HERMES_KANBAN_DB" not in os.environ
        resolved = kanban_db.kanban_db_path()
        assert resolved == paths.hermes_home / "kanban.db"

    assert os.environ.get("HERMES_KANBAN_DB") == str(ambient)
    assert not ambient.exists()


def test_kanban_db_contract_env_pin_has_highest_precedence(tmp_path, monkeypatch):
    # Contract test against the external hermes_cli.kanban_db module: our
    # guards and installer hardening assume HERMES_KANBAN_DB outranks
    # HERMES_HOME. If a Hermes upgrade changes that, this test must fail
    # loudly instead of the assumption drifting silently.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    pinned = tmp_path / "pinned" / "kanban.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(pinned))

    assert kanban_db.kanban_db_path() == pinned

    monkeypatch.delenv("HERMES_KANBAN_DB")
    resolved = kanban_db.kanban_db_path(board="default")
    assert str(resolved).startswith(str(tmp_path / "home"))
