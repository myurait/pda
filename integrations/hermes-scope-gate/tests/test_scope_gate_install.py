from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import install as installer
from install import install_scope_gate


def test_installer_is_idempotent_and_preserves_existing_hook_config(tmp_path: Path) -> None:
    home = tmp_path / ".hermes"
    home.mkdir()
    config_path = home / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "plugins": {"enabled": ["existing-plugin"]},
                "hooks": {
                    "pre_tool_call": [
                        {
                            "matcher": "terminal",
                            "command": "/trusted/existing-hook",
                            "timeout": 5,
                            "fail_closed": True,
                        }
                    ]
                },
                "agent": {"max_turns": 500},
            },
            sort_keys=False,
        )
    )

    first = install_scope_gate(home=home, source=ROOT)
    second = install_scope_gate(home=home, source=ROOT)
    config = yaml.safe_load(config_path.read_text())

    assert first["changed"] is True
    assert second["changed"] is False
    assert config["plugins"]["enabled"] == ["existing-plugin", "pda-scope-gate"]
    assert config["agent"]["max_turns"] == 500
    hooks = config["hooks"]["pre_tool_call"]
    assert hooks[0]["command"] == "/trusted/existing-hook"
    assert hooks[1] == {
        "matcher": ".*",
        "command": f"{home / 'plugins' / 'pda-scope-gate' / 'pda-scope-gate'} validate-tool",
        "timeout": 3,
        "fail_closed": True,
    }
    assert (home / "plugins" / "pda-scope-gate").resolve() == ROOT.resolve()


def test_installer_rejects_source_missing_runtime_module(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(ROOT, source)
    (source / "plugin_runtime.py").unlink()

    with pytest.raises(ValueError, match="plugin_runtime.py"):
        install_scope_gate(home=tmp_path / "home", source=source)


def test_installer_rolls_back_config_allowlist_and_plugin_on_failure(
    tmp_path: Path,
) -> None:
    home = tmp_path / ".hermes"
    plugin = home / "plugins" / "pda-scope-gate"
    plugin.mkdir(parents=True)
    (plugin / "owner-marker").write_text("preserve")
    config = home / "config.yaml"
    allowlist = home / "shell-hooks-allowlist.json"
    config.write_text("agent:\n  max_turns: 500\n")
    allowlist.write_text('{"approvals": []}\n')
    original_config = config.read_bytes()
    original_allowlist = allowlist.read_bytes()
    real_atomic_write = installer._atomic_write

    def fail_allowlist(path: Path, data: bytes, mode: int) -> None:
        if path == allowlist:
            raise RuntimeError("simulated allowlist write failure")
        real_atomic_write(path, data, mode)

    with pytest.raises(RuntimeError, match="simulated"):
        install_scope_gate(home=home, source=ROOT, write_fn=fail_allowlist)

    assert config.read_bytes() == original_config
    assert allowlist.read_bytes() == original_allowlist
    assert not plugin.is_symlink()
    assert (plugin / "owner-marker").read_text() == "preserve"


def test_installer_never_overwrites_concurrent_config_during_rollback(
    tmp_path: Path,
) -> None:
    home = tmp_path / ".hermes"
    home.mkdir()
    config = home / "config.yaml"
    allowlist = home / "shell-hooks-allowlist.json"
    config.write_text("agent:\n  max_turns: 500\n")
    allowlist.write_text('{"approvals": []}\n')
    concurrent = b"agent:\n  max_turns: 999\n"
    real_atomic_write = installer._atomic_write

    def conflict_then_fail(path: Path, data: bytes, mode: int) -> None:
        if path == allowlist:
            config.write_bytes(concurrent)
            raise RuntimeError("simulated failure after concurrent edit")
        real_atomic_write(path, data, mode)

    with pytest.raises(RuntimeError, match="rollback conflict"):
        install_scope_gate(home=home, source=ROOT, write_fn=conflict_then_fail)

    assert config.read_bytes() == concurrent
