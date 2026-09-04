from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pda.report.daily_delivery import (
    DeliveryError,
    extract_response,
    load_policy,
    read_env_value,
    run,
    status,
    validate_server_url,
    validate_topic,
)

JST = ZoneInfo("Asia/Tokyo")
JOB_ID = "abc123"


def write_policy(tmp_path: Path, *, output_root: Path, env_file: Path) -> Path:
    path = tmp_path / "daily-report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "habit_id": "daily-owner-state-report-delivery",
                "timezone": "Asia/Tokyo",
                "report": {
                    "job_id": JOB_ID,
                    "output_root": str(output_root),
                    "response_heading": "## Response",
                    "not_before_local_time": "07:45:00",
                },
                "wait": {"max_seconds": 60, "poll_seconds": 30},
                "state_path": str(tmp_path / "state.json"),
                "notification": {
                    "env_file": str(env_file),
                    "server_url_variable": "PDA_NTFY_SERVER_URL",
                    "topic_variable": "PDA_NTFY_TOPIC",
                    "title": "PDA日次状態報告",
                    "max_body_chars": 40,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def write_env(tmp_path: Path, *, topic: str = "pda-chat_1234") -> Path:
    path = tmp_path / "openwebui.env"
    path.write_text(
        "\n".join(
            [
                "# settings",
                "OTHER=ignored",
                "PDA_NTFY_SERVER_URL=https://ntfy.example",
                f'PDA_NTFY_TOPIC="{topic}"',
            ]
        ),
        encoding="utf-8",
    )
    return path


def write_run(output_root: Path, *, name: str, body: str, written: datetime) -> Path:
    directory = output_root / JOB_ID
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"# Cron Job\n\n## Prompt\n\nread state\n\n## Response\n\n{body}\n", encoding="utf-8")
    stamp = written.timestamp()
    os.utime(path, (stamp, stamp))
    return path


class Recorder:
    def __init__(self, status_code: int = 200) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.status_code = status_code

    def __call__(self, url: str, title: str, body: str) -> int:
        self.calls.append((url, title, body))
        return self.status_code


def test_todays_report_is_pushed_once(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    env_file = write_env(tmp_path)
    policy = load_policy(write_policy(tmp_path, output_root=output_root, env_file=env_file))
    now = datetime(2026, 9, 5, 7, 50, tzinfo=JST)
    write_run(output_root, name="2026-09-05.md", body="本日の状態です。", written=now - timedelta(minutes=3))
    poster = Recorder()

    first = run(policy, now=lambda: now, sleep=lambda _: None, post=poster)
    assert first["delivered"] is True
    assert poster.calls[0][0] == "https://ntfy.example/pda-chat_1234"
    assert poster.calls[0][1] == "PDA日次状態報告"
    assert poster.calls[0][2] == "本日の状態です。"

    second = run(policy, now=lambda: now, sleep=lambda _: None, post=poster)
    assert second["delivered"] is False
    assert second["reason"] == "already-delivered"
    assert len(poster.calls) == 1


def test_yesterdays_report_is_not_sent_as_todays(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    env_file = write_env(tmp_path)
    policy = load_policy(write_policy(tmp_path, output_root=output_root, env_file=env_file))
    now = datetime(2026, 9, 5, 7, 50, tzinfo=JST)
    write_run(
        output_root,
        name="2026-09-04.md",
        body="昨日の状態です。",
        written=datetime(2026, 9, 4, 7, 46, tzinfo=JST),
    )
    poster = Recorder()

    result = run(policy, now=lambda: now, sleep=lambda _: None, post=poster)
    assert result["ok"] is False
    assert result["reason"] == "no-run-in-window"
    assert poster.calls == []


def test_a_late_run_is_waited_for(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    env_file = write_env(tmp_path)
    policy = load_policy(write_policy(tmp_path, output_root=output_root, env_file=env_file))
    now = datetime(2026, 9, 5, 7, 50, tzinfo=JST)
    poster = Recorder()
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 2:
            write_run(output_root, name="late.md", body="遅れて出た報告です。", written=now)

    result = run(policy, now=lambda: now, sleep=sleep, post=poster)
    assert result["delivered"] is True
    assert waits == [30, 30]


def test_a_long_report_is_truncated_rather_than_dropped(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    env_file = write_env(tmp_path)
    policy = load_policy(write_policy(tmp_path, output_root=output_root, env_file=env_file))
    now = datetime(2026, 9, 5, 7, 50, tzinfo=JST)
    write_run(output_root, name="long.md", body="あ" * 200, written=now)
    poster = Recorder()

    result = run(policy, now=lambda: now, sleep=lambda _: None, post=poster)
    assert result["truncated"] is True
    assert poster.calls[0][2].endswith("…")
    assert len(poster.calls[0][2]) == 41


def test_status_reports_an_undelivered_run(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    env_file = write_env(tmp_path)
    policy = load_policy(write_policy(tmp_path, output_root=output_root, env_file=env_file))
    now = datetime(2026, 9, 5, 7, 55, tzinfo=JST)
    write_run(output_root, name="2026-09-05.md", body="本日の状態です。", written=now)

    before = status(policy, now=lambda: now)
    assert before["ok"] is False
    assert before["last_delivered_run"] is None

    run(policy, now=lambda: now, sleep=lambda _: None, post=Recorder())
    after = status(policy, now=lambda: now)
    assert after["ok"] is True
    assert after["last_delivered_run"] == "2026-09-05.md"


def test_push_settings_are_validated(tmp_path: Path) -> None:
    env_file = write_env(tmp_path, topic="not a topic")
    assert read_env_value(env_file, "PDA_NTFY_SERVER_URL") == "https://ntfy.example"
    with pytest.raises(DeliveryError):
        validate_topic(read_env_value(env_file, "PDA_NTFY_TOPIC"))
    with pytest.raises(DeliveryError):
        read_env_value(env_file, "MISSING")
    with pytest.raises(DeliveryError):
        validate_server_url("http://ntfy.example")
    assert validate_server_url("http://127.0.0.1:8080/") == "http://127.0.0.1:8080"


def test_a_run_file_without_a_response_section_is_an_error() -> None:
    with pytest.raises(DeliveryError):
        extract_response("# Cron Job\n\n## Prompt\n\nread state\n", "## Response")


def test_job_id_must_stay_a_single_path_component(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "timezone": "Asia/Tokyo",
                "report": {"job_id": "../../etc"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DeliveryError):
        load_policy(path)
