#!/usr/bin/env python3
"""Install/update the audited Hermes Progress Pipe through Open WebUI's admin API.

The script deliberately reads credentials from local mode-0600 files and never
prints them.  It is idempotent and refuses to overwrite an unrelated Function.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import aiohttp

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / ".admin-api-key"
ENV_FILE = ROOT / ".env"
FUNCTION_FILE = ROOT / "functions" / "hermes_progress_pipe.py"
FUNCTION_ID = "hermes_progress_pipe"
FUNCTION_NAME = "Hermes Agent (Progress)"
OPENWEBUI_URL = "http://127.0.0.1:9120"
OWNERSHIP_MARKER = "openwebui-hermes-progress/2.1-local"


class InstallError(RuntimeError):
    pass


def validate_ntfy_topic(value: str) -> str:
    topic = str(value or "").strip()
    if not re.fullmatch(r"[-_A-Za-z0-9]{1,64}", topic):
        raise InstallError("PDA_NTFY_TOPIC must match [-_A-Za-z0-9]{1,64}")
    return topic


def validate_https_url(
    value: str, label: str, *, allow_loopback_http: bool = False
) -> str:
    supplied = str(value or "")
    if supplied != supplied.strip():
        raise InstallError(f"{label} must not contain surrounding whitespace")
    url = supplied.rstrip("/")
    if (
        not url
        or "\\" in url
        or "%" in url
        or any(
            char.isspace() or ord(char) < 33 or ord(char) == 127
            for char in url
        )
    ):
        raise InstallError(f"{label} is malformed")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
    except (TypeError, ValueError):
        parsed = None
        hostname = None
        valid_port = False
    if parsed is None or not hostname:
        raise InstallError(f"{label} must be a credential-free notification URL")
    try:
        ipaddress.ip_address(hostname)
        valid_hostname = True
    except ValueError:
        try:
            ascii_hostname = hostname.rstrip(".").encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise InstallError(f"{label} has an invalid hostname") from exc
        labels = ascii_hostname.split(".")
        valid_hostname = (
            0 < len(ascii_hostname) <= 253
            and all(
                re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
                    item,
                )
                for item in labels
            )
        )
    loopback = hostname in {"127.0.0.1", "localhost", "::1"}
    valid_scheme = parsed.scheme == "https" or (
        allow_loopback_http and parsed.scheme == "http" and loopback
    )
    if (
        not valid_scheme
        or not valid_hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not valid_port
    ):
        raise InstallError(f"{label} must be a credential-free notification URL")
    return url


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_secret(path: Path) -> str:
    if not path.is_file():
        raise InstallError(f"Missing credential file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise InstallError(f"Credential file must be mode 0600 (currently {mode:04o}): {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise InstallError(f"Credential file is empty: {path}")
    return value


class OpenWebUIClient:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60, connect=10, sock_read=60)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        assert self.session
        await self.session.close()

    async def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        expected: set[int] = {200},
    ) -> tuple[int, Any]:
        assert self.session
        async with self.session.request(
            method,
            f"{OPENWEBUI_URL}{path}",
            headers=self.headers,
            json=payload,
            allow_redirects=False,
        ) as response:
            text = await response.text()
            try:
                data: Any = json.loads(text) if text else None
            except json.JSONDecodeError:
                data = text
            if response.status not in expected:
                detail = data
                if isinstance(data, dict):
                    detail = data.get("detail") or data.get("error") or data
                raise InstallError(
                    f"Open WebUI {method} {path} failed with HTTP {response.status}: "
                    f"{str(detail)[:500]}"
                )
            return response.status, data


def verify_applied_configuration(
    verified_function: dict[str, Any],
    expected_source: str,
    expected_valves: dict[str, Any],
    applied_valves: dict[str, Any],
) -> None:
    if not bool(verified_function.get("is_active")):
        raise InstallError("Function exists but is not active after installation")
    if str(verified_function.get("content") or "") != expected_source:
        raise InstallError("Function source did not match after installation")
    if applied_valves != expected_valves:
        # Never include security-sensitive Valve keys or values in this error.
        raise InstallError("Function Valves did not exactly match after installation")


def build_valves_payload(
    *,
    hermes_url: str,
    hermes_key: str,
    ntfy_server: str,
    ntfy_topic: str,
    allowed_user_id: str,
    openwebui_public_url: str,
) -> dict[str, Any]:
    return {
        "HERMES_API_URL": hermes_url,
        "HERMES_API_KEY": hermes_key,
        "HERMES_MODEL": "hermes-agent",
        # Hermes is routinely used for multi-hour agent work. Let user or
        # client cancellation own run lifetime by default.
        "RUN_TIMEOUT_SECONDS": 0,
        # Emit a model-invisible Open WebUI status while a long run remains
        # active. Set this Valve to 0 to disable periodic heartbeat statuses.
        "PROGRESS_HEARTBEAT_SECONDS": 900,
        # Hermes owns the canonical approval deadline (60s by default).
        # Expire the UI first so its deny reaches an active session.
        "APPROVAL_TIMEOUT_SECONDS": 55,
        "SHOW_TOOL_PREVIEW": False,
        "TOOL_PREVIEW_CHARS": 160,
        "SHOW_REASONING_STATUS": True,
        "NTFY_SERVER_URL": ntfy_server,
        "NTFY_TOPIC": ntfy_topic,
        "NTFY_ALLOWED_USER_ID": allowed_user_id,
        "OPENWEBUI_PUBLIC_URL": openwebui_public_url,
    }


async def main() -> None:
    token = read_secret(TOKEN_FILE)
    env = load_env(ENV_FILE)
    hermes_key = env.get("HERMES_API_KEY", "").strip()
    hermes_url = env.get("HERMES_API_BASE_URL", "").strip().rstrip("/")
    ntfy_server = validate_https_url(
        env.get("PDA_NTFY_SERVER_URL", "https://ntfy.sh"),
        "PDA_NTFY_SERVER_URL",
        allow_loopback_http=True,
    )
    ntfy_topic = validate_ntfy_topic(env.get("PDA_NTFY_TOPIC", ""))
    openwebui_public_url = validate_https_url(
        env.get("PDA_OPENWEBUI_PUBLIC_URL", ""),
        "PDA_OPENWEBUI_PUBLIC_URL",
    )
    if not hermes_key:
        raise InstallError("HERMES_API_KEY is missing from Open WebUI .env")
    if not hermes_url.endswith("/v1"):
        raise InstallError("HERMES_API_BASE_URL must end with /v1")
    source = FUNCTION_FILE.read_text(encoding="utf-8")
    if OWNERSHIP_MARKER not in source:
        raise InstallError("Function source is missing the local ownership marker")

    async with OpenWebUIClient(token) as client:
        _, identity = await client.request("GET", "/api/v1/auths/")
        if not isinstance(identity, dict) or identity.get("role") != "admin":
            raise InstallError("The supplied Open WebUI API key does not belong to an admin user")
        allowed_user_id = str(identity.get("id") or "").strip()
        if not allowed_user_id:
            raise InstallError("The supplied Open WebUI API key has no user ID")

        existing = None
        status, data = await client.request(
            "GET",
            f"/api/v1/functions/id/{FUNCTION_ID}",
            expected={200, 401},
        )
        if status == 200:
            existing = data
            old_source = str((existing or {}).get("content") or "")
            if OWNERSHIP_MARKER not in old_source:
                raise InstallError(
                    f"Refusing to overwrite unrelated existing Function '{FUNCTION_ID}'"
                )
        form = {
            "id": FUNCTION_ID,
            "name": FUNCTION_NAME,
            "content": source,
            "meta": {
                "description": (
                    "Hermes Runs API adapter with model-invisible tool status, "
                    "per-chat sessions, fail-safe approvals, and topic-titled "
                    "Open WebUI completion previews."
                ),
                # Open WebUI replaces this with the Function frontmatter.
                "manifest": {},
            },
        }

        valves_payload = build_valves_payload(
            hermes_url=hermes_url,
            hermes_key=hermes_key,
            ntfy_server=ntfy_server,
            ntfy_topic=ntfy_topic,
            allowed_user_id=allowed_user_id,
            openwebui_public_url=openwebui_public_url,
        )

        created_new = existing is None
        try:
            if created_new:
                _, function = await client.request(
                    "POST", "/api/v1/functions/create", payload=form
                )
            else:
                _, function = await client.request(
                    "POST",
                    f"/api/v1/functions/id/{FUNCTION_ID}/update",
                    payload=form,
                )

            await client.request(
                "POST",
                f"/api/v1/functions/id/{FUNCTION_ID}/valves/update",
                payload=valves_payload,
            )

            active = bool((function or {}).get("is_active"))
            if not active:
                _, function = await client.request(
                    "POST", f"/api/v1/functions/id/{FUNCTION_ID}/toggle"
                )

            _, verified = await client.request(
                "GET", f"/api/v1/functions/id/{FUNCTION_ID}"
            )
            _, applied_valves = await client.request(
                "GET", f"/api/v1/functions/id/{FUNCTION_ID}/valves"
            )
            if not isinstance(verified, dict) or not isinstance(applied_valves, dict):
                raise InstallError("Function verification returned an invalid response")
            verify_applied_configuration(
                verified,
                source,
                valves_payload,
                applied_valves,
            )

            _, functions = await client.request("GET", "/api/v1/functions/list")
            found = any(
                isinstance(item, dict)
                and item.get("id") == FUNCTION_ID
                and item.get("is_active") is True
                for item in (functions or [])
            )
            if not found:
                raise InstallError("Installed Function was not present in the active function list")

        except Exception:
            # Open WebUI's Function API has no revision/CAS precondition for
            # update or delete. A destructive automatic rollback could erase a
            # concurrent admin/API change. Leave the observed state untouched;
            # the installer is idempotent, so a controlled rerun is the safe
            # recovery path after diagnosing the original error.
            print(
                "WARNING: installation was not verified; no automatic rollback "
                "was attempted. Rerun the installer to reconcile the Function.",
                file=sys.stderr,
            )
            raise

    print(
        json.dumps(
            {
                "installed": True,
                "function_id": FUNCTION_ID,
                "model_name": FUNCTION_NAME,
                "created_new": created_new,
                "tool_preview": False,
                "completion_push": True,
                "completion_push_chat_title": True,
                "completion_push_answer_preview": True,
                "completion_push_owner_scoped": True,
                "admin_token_file": str(TOKEN_FILE),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except InstallError as exc:
        print(f"INSTALL_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
