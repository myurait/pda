from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

from .daily_delivery import DeliveryError, load_policy

SystemctlRunner = Callable[[list[str]], None]
SYSTEMCTL_TIMEOUT_SECONDS = 60
UNIT_NAMES = (
    "pda-daily-report-delivery.service",
    "pda-daily-report-delivery.timer",
)


def install_units(
    *,
    repo_root: Path,
    home: Path,
    run_systemctl: SystemctlRunner,
) -> None:
    repository = repo_root.resolve()
    user_home = home.resolve()
    canonical_repository = user_home / "projects/pda"
    if repository != canonical_repository:
        raise DeliveryError(
            "delivery units require the canonical repository path: "
            f"{canonical_repository}"
        )

    policy_source = repository / "continuity/daily-report.json"
    if not policy_source.is_file() or policy_source.is_symlink():
        raise DeliveryError(f"managed delivery policy is missing or unsafe: {policy_source}")
    policy = load_policy(policy_source)
    # Refuse to arm a timer whose push settings cannot be read: a delivery that
    # can only fail at 07:50 is worse than an install that fails now.
    from .daily_delivery import read_env_value, validate_server_url, validate_topic

    validate_server_url(read_env_value(policy.env_file, policy.server_url_variable))
    validate_topic(read_env_value(policy.env_file, policy.topic_variable))

    policy_dir = user_home / ".config/pda"
    policy_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(policy_dir, 0o700)
    policy_destination = policy_dir / "daily-report.json"
    temporary_policy = policy_dir / f".daily-report-{uuid.uuid4().hex}.tmp"
    temporary_policy.write_bytes(policy_source.read_bytes())
    os.chmod(temporary_policy, 0o600)
    os.replace(temporary_policy, policy_destination)

    unit_dir = user_home / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name in UNIT_NAMES:
        source = repository / "infra/systemd" / name
        if not source.is_file():
            raise DeliveryError(f"managed systemd unit is missing: {source}")
        destination = unit_dir / name
        if destination.is_symlink() and destination.resolve() == source:
            continue
        if destination.exists() or destination.is_symlink():
            raise DeliveryError(f"refusing to replace unmanaged systemd unit: {destination}")
        destination.symlink_to(source)

    run_systemctl(["daemon-reload"])
    run_systemctl(["enable", "--now", "pda-daily-report-delivery.timer"])
    run_systemctl(["is-enabled", "pda-daily-report-delivery.timer"])
    run_systemctl(["is-active", "pda-daily-report-delivery.timer"])


def systemctl_user(arguments: list[str]) -> None:
    command = ["systemctl", "--user", *arguments]
    try:
        subprocess.run(command, check=True, timeout=SYSTEMCTL_TIMEOUT_SECONDS)
    except FileNotFoundError as error:
        raise DeliveryError("systemctl is required to install the delivery timer") from error
    except subprocess.CalledProcessError as error:
        raise DeliveryError(
            f"systemctl command failed with exit code {error.returncode}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise DeliveryError("systemctl command timed out") from error
