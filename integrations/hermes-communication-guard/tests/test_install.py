from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import install as install_module
from install import disable_guard, install_guard


def test_install_and_disable_are_idempotent_and_preserve_other_plugins(tmp_path: Path) -> None:
    home = tmp_path / "hermes-home"
    home.mkdir()
    escalation_skill = home / "skills" / "pda-user-escalation" / "SKILL.md"
    improvement_skill = home / "skills" / "pda-autonomous-improvement" / "SKILL.md"
    escalation_skill.parent.mkdir(parents=True)
    improvement_skill.parent.mkdir(parents=True)
    escalation_skill.write_text("previous escalation skill\n", encoding="utf-8")
    improvement_skill.write_text("previous improvement skill\n", encoding="utf-8")
    approval_index = home / "plugins" / "pda-approvals" / "dashboard" / "dist" / "index.js"
    approval_index.parent.mkdir(parents=True)
    approval_index.write_text("previous approval view\n", encoding="utf-8")
    config_path = home / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "plugins": {
                    "enabled": ["existing-plugin"],
                    "entries": {"existing-plugin": {"settings": {"keep": True}}},
                }
            }
        ),
        encoding="utf-8",
    )

    installed = install_guard(home=home, source=ROOT)
    repeated = install_guard(home=home, source=ROOT)

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    plugin_path = home / "plugins" / "pda-communication-guard"
    assert installed["changed"] is True
    assert repeated["changed"] is False
    assert plugin_path.is_symlink()
    assert plugin_path.resolve() == ROOT.resolve()
    assert config["plugins"]["enabled"] == [
        "existing-plugin",
        "pda-communication-guard",
    ]
    assert config["plugins"]["entries"]["existing-plugin"]["settings"]["keep"] is True
    canonical_escalation = (
        ROOT.parents[1]
        / "profiles"
        / "pda"
        / "skills"
        / "pda-user-escalation"
        / "SKILL.md"
    )
    canonical_improvement = (
        ROOT.parents[1]
        / "profiles"
        / "pda"
        / "skills"
        / "pda-autonomous-improvement"
        / "SKILL.md"
    )
    assert escalation_skill.read_bytes() == canonical_escalation.read_bytes()
    assert improvement_skill.read_bytes() == canonical_improvement.read_bytes()
    canonical_approval_index = (
        ROOT.parents[1]
        / "integrations"
        / "hermes-pda-approvals"
        / "dashboard"
        / "dist"
        / "index.js"
    )
    assert approval_index.read_bytes() == canonical_approval_index.read_bytes()

    disabled = disable_guard(home=home, source=ROOT)
    repeated_disable = disable_guard(home=home, source=ROOT)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert disabled["changed"] is True
    assert repeated_disable["changed"] is False
    assert config["plugins"]["enabled"] == ["existing-plugin"]
    assert plugin_path.is_symlink()
    assert escalation_skill.read_text(encoding="utf-8") == "previous escalation skill\n"
    assert improvement_skill.read_text(encoding="utf-8") == "previous improvement skill\n"
    assert approval_index.read_text(encoding="utf-8") == "previous approval view\n"


def test_failed_config_write_rolls_back_new_plugin_link(tmp_path: Path) -> None:
    home = tmp_path / "hermes-home"
    home.mkdir()
    config_path = home / "config.yaml"
    original = yaml.safe_dump({"plugins": {"enabled": ["existing-plugin"]}})
    config_path.write_text(original, encoding="utf-8")

    def fail_write(*_args, **_kwargs):
        raise RuntimeError("simulated write failure")

    with pytest.raises(RuntimeError, match="simulated write failure"):
        install_guard(home=home, source=ROOT, write_fn=fail_write)

    assert config_path.read_text(encoding="utf-8") == original
    assert not (home / "plugins" / "pda-communication-guard").exists()


@pytest.mark.parametrize(
    "skill_id",
    ["pda-user-escalation", "pda-autonomous-improvement"],
)
def test_disable_refuses_to_overwrite_either_concurrently_changed_skill(
    tmp_path: Path,
    skill_id: str,
) -> None:
    home = tmp_path / "hermes-home"
    install_guard(home=home, source=ROOT)
    skill_path = home / "skills" / skill_id / "SKILL.md"
    skill_path.write_text("concurrent worker-contract update\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="concurrently changed"):
        disable_guard(home=home, source=ROOT)

    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert "pda-communication-guard" in config["plugins"]["enabled"]
    assert skill_path.read_text(encoding="utf-8") == "concurrent worker-contract update\n"
    assert (home / "plugin-data" / "pda-communication-guard" / "install-state.json").is_file()


@pytest.mark.parametrize("symlink_kind", ["skill", "approval-asset"])
def test_install_rejects_nested_managed_symlink_before_any_write(
    tmp_path: Path,
    symlink_kind: str,
) -> None:
    home = tmp_path / "hermes-home"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_text("outside unchanged\n", encoding="utf-8")
    if symlink_kind == "skill":
        parent = home / "skills"
        parent.mkdir(parents=True)
        (parent / "pda-user-escalation").symlink_to(outside, target_is_directory=True)
    else:
        parent = home / "plugins" / "pda-approvals"
        parent.mkdir(parents=True)
        (parent / "dashboard").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        install_guard(home=home, source=ROOT)

    assert marker.read_text(encoding="utf-8") == "outside unchanged\n"
    assert not (home / "plugins" / "pda-communication-guard").exists()
    assert not (home / "skills" / "pda-autonomous-improvement" / "SKILL.md").exists()


def test_default_writer_resists_parent_symlink_swap_after_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "hermes-home"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_writer = install_module._secure_atomic_write
    swapped = False

    def swap_then_write(root: Path, path: Path, data: bytes, mode: int) -> None:
        nonlocal swapped
        if not swapped and "pda-user-escalation" in path.parts:
            swapped = True
            path.parent.parent.mkdir(parents=True, exist_ok=True)
            path.parent.symlink_to(outside, target_is_directory=True)
        original_writer(root, path, data, mode)

    monkeypatch.setattr(install_module, "_secure_atomic_write", swap_then_write)

    with pytest.raises((OSError, RuntimeError)):
        install_guard(home=home, source=ROOT)

    assert swapped is True
    assert not (outside / "SKILL.md").exists()
    assert not (home / "plugins" / "pda-communication-guard").exists()
