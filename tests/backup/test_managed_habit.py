from __future__ import annotations

import configparser
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def test_managed_habit_matches_backup_config_and_systemd_schedule() -> None:
    backup_config = json.loads(
        (REPO_ROOT / "continuity/local-backup.json").read_text(encoding="utf-8")
    )
    habits = json.loads(
        (REPO_ROOT / "profiles/pda/managed-habits.json").read_text(encoding="utf-8")
    )
    timer = load_unit(REPO_ROOT / "infra/systemd/pda-local-backup.timer")
    service = load_unit(REPO_ROOT / "infra/systemd/pda-local-backup.service")

    assert backup_config["habit_id"] == "daily-local-continuity-backup"
    assert backup_config["timezone"] == "Asia/Tokyo"
    assert backup_config["retention"]["successful_snapshots"] == 7
    assert backup_config["freshness"]["max_age_hours"] == 36
    assert backup_config["schedule"] == {
        "local_time": "05:00:00",
        "timezone": "Asia/Tokyo",
    }
    assert {source["name"] for source in backup_config["sources"]} == {
        "hermes-home",
        "firecrawl-runtime",
        "openwebui-config",
        "openwebui-data",
        "pda-repository",
        "systemd-user-units",
        "tailscale-pda-state",
    }

    habit = next(
        habit
        for habit in habits["habits"]
        if habit["id"] == "daily-local-continuity-backup"
    )
    assert habit["status"] == "managed-desired-state"
    assert habit["desired_status"] == "active"
    assert habit["observed_status"]["stored_in_git"] is False
    assert set(habit["observed_status"]["activation_requires"]) == {
        "timer-enabled-and-active",
        "current-policy-snapshot-fresh",
        "real-snapshot-restore-drill-passed",
    }
    assert habit["policy_source"] == "continuity/local-backup.json"
    assert habit["self_recognition"]["managed_continuity_asset"] is True
    assert habit["freshness"] == {
        "max_age_hours": 36,
        "stale_is_unhealthy": True,
    }
    assert habit["limitations"]["protects_against_host_or_disk_loss"] is False

    assert timer["Timer"]["OnCalendar"] == "*-*-* 05:00:00 Asia/Tokyo"
    assert timer["Timer"]["Persistent"] == "true"
    assert timer["Timer"]["RandomizedDelaySec"] == "0"
    assert service["Service"]["UMask"] == "0077"
    assert "%h/.config/pda/local-backup.json" in service["Service"]["ExecStart"]
    assert "pda_backup.py run --config" in service["Service"]["ExecStart"]
