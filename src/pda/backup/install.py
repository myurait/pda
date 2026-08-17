from __future__ import annotations

import os
import pwd
import re
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

from .local_snapshot import BackupError, initialize_backup_root

SystemctlRunner = Callable[[list[str]], None]
LingerVerifier = Callable[[], None]
LOGINCTL_TIMEOUT_SECONDS = 30
SYSTEMCTL_TIMEOUT_SECONDS = 60


def ensure_user_lingering(username: str | None = None) -> None:
    user = username or pwd.getpwuid(os.getuid()).pw_name
    if re.fullmatch(r"[A-Za-z0-9_.-]+", user) is None:
        raise BackupError(f"cannot verify lingering for invalid user name: {user!r}")
    command = [
        "loginctl",
        "show-user",
        user,
        "--property=Linger",
        "--value",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=LOGINCTL_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise BackupError("loginctl is required to verify user lingering") from error
    except subprocess.TimeoutExpired as error:
        raise BackupError("loginctl timed out while verifying user lingering") from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "loginctl failed").strip()
        raise BackupError(f"could not verify user lingering: {detail}")
    if completed.stdout.strip().lower() != "yes":
        raise BackupError(
            "user lingering is required for unattended 05:00 execution; "
            f"enable it explicitly with: sudo loginctl enable-linger {user}"
        )


def install_units(
    *,
    repo_root: Path,
    home: Path,
    run_systemctl: SystemctlRunner,
    ensure_linger: LingerVerifier = ensure_user_lingering,
) -> None:
    repository = repo_root.resolve()
    user_home = home.resolve()
    canonical_repository = user_home / "projects/pda"
    if repository != canonical_repository:
        raise BackupError(
            "backup units require the canonical repository path: "
            f"{canonical_repository}"
        )
    ensure_linger()
    policy_source = repository / "continuity/local-backup.json"
    if not policy_source.is_file() or policy_source.is_symlink():
        raise BackupError(f"managed backup policy is missing or unsafe: {policy_source}")
    policy_dir = user_home / ".config/pda"
    policy_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(policy_dir, 0o700)
    policy_destination = policy_dir / "local-backup.json"
    temporary_policy = policy_dir / f".local-backup-{uuid.uuid4().hex}.tmp"
    temporary_policy.write_bytes(policy_source.read_bytes())
    os.chmod(temporary_policy, 0o600)
    os.replace(temporary_policy, policy_destination)
    unit_dir = user_home / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name in ("pda-local-backup.service", "pda-local-backup.timer"):
        source = repository / "infra/systemd" / name
        if not source.is_file():
            raise BackupError(f"managed systemd unit is missing: {source}")
        destination = unit_dir / name
        if destination.is_symlink() and destination.resolve() == source:
            continue
        if destination.exists() or destination.is_symlink():
            raise BackupError(
                f"refusing to replace unmanaged systemd unit: {destination}"
            )
        destination.symlink_to(source)

    backup_root = user_home / "pda-backups/local-continuity"
    initialize_backup_root(backup_root)
    run_systemctl(["daemon-reload"])
    run_systemctl(["enable", "--now", "pda-local-backup.timer"])
    run_systemctl(["is-enabled", "pda-local-backup.timer"])
    run_systemctl(["is-active", "pda-local-backup.timer"])


def systemctl_user(arguments: list[str]) -> None:
    command = ["systemctl", "--user", *arguments]
    try:
        subprocess.run(command, check=True, timeout=SYSTEMCTL_TIMEOUT_SECONDS)
    except FileNotFoundError as error:
        raise BackupError(
            "systemctl is required to install the backup timer"
        ) from error
    except subprocess.CalledProcessError as error:
        raise BackupError(
            f"systemctl command failed with exit code {error.returncode}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise BackupError("systemctl command timed out") from error
