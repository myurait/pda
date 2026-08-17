from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pda.backup import install
from pda.backup.install import ensure_user_lingering, install_units
from pda.backup.local_snapshot import BackupError

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_canonical_repo(home: Path) -> Path:
    repository = home / "projects/pda"
    unit_dir = repository / "infra/systemd"
    unit_dir.mkdir(parents=True)
    for name in ("pda-local-backup.service", "pda-local-backup.timer"):
        shutil.copy2(REPO_ROOT / "infra/systemd" / name, unit_dir / name)
    policy_dir = repository / "continuity"
    policy_dir.mkdir()
    shutil.copy2(REPO_ROOT / "continuity/local-backup.json", policy_dir / "local-backup.json")
    return repository


def test_install_links_repo_units_creates_private_root_and_enables_timer(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []
    prerequisites: list[str] = []
    repository = make_canonical_repo(tmp_path)

    install_units(
        repo_root=repository,
        home=tmp_path,
        run_systemctl=lambda arguments: calls.append(arguments),
        ensure_linger=lambda: prerequisites.append("linger-verified"),
    )

    unit_dir = tmp_path / ".config/systemd/user"
    for name in ("pda-local-backup.service", "pda-local-backup.timer"):
        deployed = unit_dir / name
        assert deployed.is_symlink()
        assert deployed.resolve() == repository / "infra/systemd" / name
    backup_root = tmp_path / "pda-backups/local-continuity"
    assert backup_root.is_dir()
    assert os.stat(backup_root).st_mode & 0o777 == 0o700
    assert (backup_root / ".pda-local-backup-root.json").is_file()
    runtime_policy = tmp_path / ".config/pda/local-backup.json"
    assert runtime_policy.read_bytes() == (
        repository / "continuity/local-backup.json"
    ).read_bytes()
    assert os.stat(runtime_policy).st_mode & 0o777 == 0o600
    assert prerequisites == ["linger-verified"]
    assert calls == [
        ["daemon-reload"],
        ["enable", "--now", "pda-local-backup.timer"],
        ["is-enabled", "pda-local-backup.timer"],
        ["is-active", "pda-local-backup.timer"],
    ]


def test_install_rejects_noncanonical_repository_path(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="canonical repository path"):
        install_units(
            repo_root=REPO_ROOT,
            home=tmp_path,
            run_systemctl=lambda arguments: None,
            ensure_linger=lambda: None,
        )

    assert not (tmp_path / ".config/systemd/user").exists()


def test_lingering_check_is_bounded_and_requires_explicit_enablement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def disabled_linger(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="no\n", stderr="")

    monkeypatch.setattr(install.subprocess, "run", disabled_linger)

    with pytest.raises(
        BackupError, match=r"sudo loginctl enable-linger backup-user"
    ):
        ensure_user_lingering("backup-user")

    assert calls == [
        (
            [
                "loginctl",
                "show-user",
                "backup-user",
                "--property=Linger",
                "--value",
            ],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "timeout": 30,
            },
        )
    ]


def test_lingering_check_accepts_enabled_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        install.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="yes\n", stderr=""
        ),
    )

    ensure_user_lingering("backup-user")


def test_service_bounds_the_complete_backup_run() -> None:
    service = (REPO_ROOT / "infra/systemd/pda-local-backup.service").read_text(
        encoding="utf-8"
    )

    assert "TimeoutStartSec=18h" in service


def test_service_can_refresh_docker_group_without_automatic_post_commit_retry() -> None:
    service = (REPO_ROOT / "infra/systemd/pda-local-backup.service").read_text(
        encoding="utf-8"
    )

    assert 'ExecStart=/usr/bin/sg docker -c ' in service
    namespace_directives = (
        "PrivateTmp=",
        "PrivateDevices=",
        "ProtectSystem=",
        "ProtectHome=",
        "ProtectControlGroups=",
        "ProtectKernelModules=",
        "ProtectKernelTunables=",
        "ProtectKernelLogs=",
        "RestrictSUIDSGID=",
        "LockPersonality=",
        "RestrictRealtime=",
        "RestrictAddressFamilies=",
        "SystemCallArchitectures=",
    )
    for namespace_directive in namespace_directives:
        assert namespace_directive not in service
    assert "Restart=" not in service
    assert "RestartSec=" not in service
    assert "StartLimitIntervalSec=" not in service
    assert "StartLimitBurst=" not in service


def test_operations_doc_states_lingering_and_catch_up_contract() -> None:
    documentation = (
        REPO_ROOT / "docs/operations/local-continuity-backup.md"
    ).read_text(encoding="utf-8")

    assert "loginctl show-user \"$USER\" --property=Linger --value" in documentation
    assert "sudo loginctl enable-linger \"$USER\"" in documentation
    assert "catch-up" in documentation
    assert "host is running" in documentation
