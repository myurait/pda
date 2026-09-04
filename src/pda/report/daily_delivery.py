"""Deliver the scheduled PDA state report to the owner's push topic.

The report itself is produced by the Hermes scheduled job: the job writes the
run into an output file and then tries to hand it back to the conversation it
was created from. That conversation is served by the Open WebUI request path,
which has no channel for pushing a message the owner did not ask for, so the
report is written but never reaches anyone.

This module closes that gap without changing how the report is produced. It
reads the newest run written for the configured job, checks that the run
belongs to today's schedule and has not already been sent, and posts the
report body to the push topic the PDA already uses for Open WebUI completion
notices. Sending twice is prevented by a state file rather than by timing, so
a retry, a catch-up activation, or a manual run cannot repeat a delivery.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time as clock_time, timedelta, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
RESULT_SCHEMA = "pda.daily-report-delivery/v1"
_TOPIC_PATTERN = re.compile(r"[-_A-Za-z0-9]{1,64}")
_ENV_LINE_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_REQUEST_TIMEOUT_SECONDS = 10.0


class DeliveryError(Exception):
    """A condition that prevents delivery and must be visible in the journal."""


@dataclass(frozen=True)
class Policy:
    job_id: str
    output_root: Path
    response_heading: str
    not_before: clock_time
    timezone: tzinfo
    max_wait_seconds: int
    poll_seconds: int
    state_path: Path
    env_file: Path
    server_url_variable: str
    topic_variable: str
    title: str
    max_body_chars: int


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def _parse_clock(value: str, *, field: str) -> clock_time:
    try:
        return clock_time.fromisoformat(value)
    except ValueError as error:
        raise DeliveryError(f"{field} is not a local time: {value!r}") from error


def load_policy(path: str | Path) -> Policy:
    policy_path = _expand(str(path))
    try:
        document = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DeliveryError(f"delivery policy is missing: {policy_path}") from error
    except json.JSONDecodeError as error:
        raise DeliveryError(f"delivery policy is not valid JSON: {policy_path}") from error
    if document.get("schema_version") != SCHEMA_VERSION:
        raise DeliveryError(
            f"unsupported delivery policy schema_version: {document.get('schema_version')!r}"
        )
    report = document.get("report") or {}
    wait = document.get("wait") or {}
    notification = document.get("notification") or {}
    job_id = str(report.get("job_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
        # The job id is a path component under the output root.
        raise DeliveryError(f"report.job_id is not a safe identifier: {job_id!r}")
    try:
        zone = ZoneInfo(str(document.get("timezone") or "Asia/Tokyo"))
    except Exception as error:  # noqa: BLE001 -- surfaced as a policy error.
        raise DeliveryError(f"unknown timezone: {document.get('timezone')!r}") from error
    return Policy(
        job_id=job_id,
        output_root=_expand(str(report.get("output_root") or "~/.hermes/cron/output")),
        response_heading=str(report.get("response_heading") or "## Response"),
        not_before=_parse_clock(
            str(report.get("not_before_local_time") or "00:00:00"),
            field="report.not_before_local_time",
        ),
        timezone=zone,
        max_wait_seconds=int(wait.get("max_seconds") or 0),
        poll_seconds=max(1, int(wait.get("poll_seconds") or 30)),
        state_path=_expand(
            str(document.get("state_path") or "~/.local/state/pda/daily-report-delivery.json")
        ),
        env_file=_expand(str(notification.get("env_file") or "~/openwebui/.env")),
        server_url_variable=str(notification.get("server_url_variable") or "PDA_NTFY_SERVER_URL"),
        topic_variable=str(notification.get("topic_variable") or "PDA_NTFY_TOPIC"),
        title=str(notification.get("title") or "PDA state report"),
        max_body_chars=max(1, int(notification.get("max_body_chars") or 1200)),
    )


def read_env_value(env_file: Path, name: str) -> str:
    """Read one variable out of a KEY=VALUE file without executing it."""

    try:
        content = env_file.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise DeliveryError(f"notification settings file is missing: {env_file}") from error
    for line in content.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = _ENV_LINE_PATTERN.match(line)
        if match is None or match.group(1) != name:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value
    raise DeliveryError(f"{name} is not set in {env_file}")


def validate_server_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if url.startswith("https://") and len(url) > len("https://"):
        return url
    if re.fullmatch(r"http://(?:127\.0\.0\.1|localhost)(?::\d{1,5})?", url):
        return url
    raise DeliveryError("push server URL must be https, or http on loopback")


def validate_topic(value: str) -> str:
    topic = value.strip()
    if _TOPIC_PATTERN.fullmatch(topic) is None:
        raise DeliveryError("push topic contains characters that are not allowed")
    return topic


def extract_response(document: str, heading: str) -> str:
    """Return the report body, which follows the run file's response heading."""

    marker = f"\n{heading}"
    position = document.find(marker)
    if position < 0:
        if document.startswith(heading):
            return document[len(heading) :].strip()
        raise DeliveryError(f"run file has no {heading!r} section")
    return document[position + len(marker) :].strip()


def latest_run_file(policy: Policy) -> Path | None:
    directory = policy.output_root / policy.job_id
    if not directory.is_dir():
        return None
    candidates = sorted(
        (path for path in directory.glob("*.md") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _window_start(policy: Policy, now: datetime) -> datetime:
    """The earliest moment a run may have been written for today's schedule."""

    start = datetime.combine(now.astimezone(policy.timezone).date(), policy.not_before)
    start = start.replace(tzinfo=policy.timezone)
    if start > now:
        # Activated before today's window: the run being waited for is
        # yesterday's, so accept a file from the previous window instead of
        # reporting a gap that is only an artefact of the activation time.
        start -= timedelta(days=1)
    return start


def _load_state(policy: Policy) -> dict[str, Any]:
    try:
        return json.loads(policy.state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(policy: Policy, state: dict[str, Any]) -> None:
    policy.state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = policy.state_path.with_name(f".{policy.state_path.name}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, policy.state_path)


def post_to_topic(url: str, *, title: str, body: str) -> int:
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Title": title,
            "Priority": "default",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status)
    except urllib.error.HTTPError as error:
        raise DeliveryError(f"push rejected with HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise DeliveryError(f"push could not be sent: {error.reason}") from error


Poster = Callable[[str, str, str], int]


def run(
    policy: Policy,
    *,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    post: Poster | None = None,
) -> dict[str, Any]:
    """Send today's report once, waiting for it if the run is still going."""

    clock = now or (lambda: datetime.now(policy.timezone))
    sender = post or (lambda url, title, body: post_to_topic(url, title=title, body=body))
    started = clock()
    window_start = _window_start(policy, started)
    state = _load_state(policy)

    deadline_checks = max(1, policy.max_wait_seconds // policy.poll_seconds + 1)
    candidate: Path | None = None
    for attempt in range(deadline_checks):
        candidate = latest_run_file(policy)
        if candidate is not None:
            written = datetime.fromtimestamp(candidate.stat().st_mtime, policy.timezone)
            if written >= window_start:
                break
        candidate = None
        if attempt + 1 < deadline_checks:
            sleep(policy.poll_seconds)

    if candidate is None:
        return {
            "schema": RESULT_SCHEMA,
            "ok": False,
            "delivered": False,
            "reason": "no-run-in-window",
            "window_start": window_start.isoformat(),
            "job_id": policy.job_id,
        }

    if state.get("last_delivered_run") == candidate.name:
        return {
            "schema": RESULT_SCHEMA,
            "ok": True,
            "delivered": False,
            "reason": "already-delivered",
            "run": candidate.name,
            "job_id": policy.job_id,
        }

    body = extract_response(candidate.read_text(encoding="utf-8"), policy.response_heading)
    if not body:
        return {
            "schema": RESULT_SCHEMA,
            "ok": False,
            "delivered": False,
            "reason": "empty-report",
            "run": candidate.name,
            "job_id": policy.job_id,
        }
    truncated = len(body) > policy.max_body_chars
    if truncated:
        body = body[: policy.max_body_chars].rstrip() + "…"

    server = validate_server_url(read_env_value(policy.env_file, policy.server_url_variable))
    topic = validate_topic(read_env_value(policy.env_file, policy.topic_variable))
    status = sender(f"{server}/{topic}", policy.title, body)

    delivered_at = clock()
    _save_state(
        policy,
        {
            "schema_version": SCHEMA_VERSION,
            "job_id": policy.job_id,
            "last_delivered_run": candidate.name,
            "last_delivered_at": delivered_at.isoformat(),
        },
    )
    return {
        "schema": RESULT_SCHEMA,
        "ok": True,
        "delivered": True,
        "run": candidate.name,
        "job_id": policy.job_id,
        "http_status": status,
        "truncated": truncated,
        "characters": len(body),
    }


def status(policy: Policy, *, now: Callable[[], datetime] | None = None) -> dict[str, Any]:
    clock = now or (lambda: datetime.now(policy.timezone))
    current = clock()
    state = _load_state(policy)
    candidate = latest_run_file(policy)
    latest_name = candidate.name if candidate is not None else None
    latest_written = (
        datetime.fromtimestamp(candidate.stat().st_mtime, policy.timezone).isoformat()
        if candidate is not None
        else None
    )
    return {
        "schema": RESULT_SCHEMA,
        "ok": bool(latest_name) and state.get("last_delivered_run") == latest_name,
        "job_id": policy.job_id,
        "window_start": _window_start(policy, current).isoformat(),
        "latest_run": latest_name,
        "latest_run_written_at": latest_written,
        "last_delivered_run": state.get("last_delivered_run"),
        "last_delivered_at": state.get("last_delivered_at"),
    }
