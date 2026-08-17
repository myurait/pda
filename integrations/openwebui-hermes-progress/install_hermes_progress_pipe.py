#!/usr/bin/env python3
"""Install/update the audited Hermes Progress Pipe through Open WebUI's admin API.

The script deliberately reads credentials from local mode-0600 files and never
prints them.  It is idempotent and refuses to overwrite an unrelated Function.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import time
from pathlib import Path
from typing import Any

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


async def main() -> None:
    token = read_secret(TOKEN_FILE)
    env = load_env(ENV_FILE)
    hermes_key = env.get("HERMES_API_KEY", "").strip()
    hermes_url = env.get("HERMES_API_BASE_URL", "").strip().rstrip("/")
    ntfy_server = env.get("PDA_NTFY_SERVER_URL", "https://ntfy.sh").strip().rstrip("/")
    ntfy_topic = env.get("PDA_NTFY_TOPIC", "").strip()
    openwebui_public_url = env.get("PDA_OPENWEBUI_PUBLIC_URL", "").strip()
    if not hermes_key:
        raise InstallError("HERMES_API_KEY is missing from Open WebUI .env")
    if not hermes_url.endswith("/v1"):
        raise InstallError("HERMES_API_BASE_URL must end with /v1")
    if not ntfy_topic:
        raise InstallError("PDA_NTFY_TOPIC is missing from Open WebUI .env")
    if not openwebui_public_url.startswith("https://"):
        raise InstallError("PDA_OPENWEBUI_PUBLIC_URL must be an HTTPS URL")

    source = FUNCTION_FILE.read_text(encoding="utf-8")
    if OWNERSHIP_MARKER not in source:
        raise InstallError("Function source is missing the local ownership marker")

    async with OpenWebUIClient(token) as client:
        _, identity = await client.request("GET", "/api/v1/auths/")
        if not isinstance(identity, dict) or identity.get("role") != "admin":
            raise InstallError("The supplied Open WebUI API key does not belong to an admin user")

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
                    "per-chat sessions, fail-safe approvals, and content-free "
                    "Open WebUI completion push."
                ),
                "manifest": {},
            },
        }

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
                payload={
                    "HERMES_API_URL": hermes_url,
                    "HERMES_API_KEY": hermes_key,
                    "HERMES_MODEL": "hermes-agent",
                    # Hermes is routinely used for multi-hour agent work.  Let
                    # user or client cancellation own run lifetime by default.
                    "RUN_TIMEOUT_SECONDS": 0,
                    # Hermes owns the canonical approval deadline (60s by
                    # default). Expire the UI first so its deny reaches an
                    # active session rather than racing it afterward.
                    "APPROVAL_TIMEOUT_SECONDS": 55,
                    "SHOW_TOOL_PREVIEW": False,
                    "TOOL_PREVIEW_CHARS": 160,
                    "SHOW_REASONING_STATUS": True,
                    "NTFY_SERVER_URL": ntfy_server,
                    "NTFY_TOPIC": ntfy_topic,
                    "OPENWEBUI_PUBLIC_URL": openwebui_public_url,
                },
            )

            active = bool((function or {}).get("is_active"))
            if not active:
                _, function = await client.request(
                    "POST", f"/api/v1/functions/id/{FUNCTION_ID}/toggle"
                )

            _, verified = await client.request(
                "GET", f"/api/v1/functions/id/{FUNCTION_ID}"
            )
            if not bool((verified or {}).get("is_active")):
                raise InstallError("Function exists but is not active after installation")

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
            # Best-effort rollback.  A newly-created Function is removed.  An
            # existing local Function's source/metadata/active state is restored.
            try:
                if created_new:
                    await client.request(
                        "DELETE",
                        f"/api/v1/functions/id/{FUNCTION_ID}/delete",
                        expected={200},
                    )
                elif isinstance(existing, dict):
                    restore = {
                        "id": existing["id"],
                        "name": existing["name"],
                        "content": existing["content"],
                        "meta": existing.get("meta") or {},
                    }
                    _, restored = await client.request(
                        "POST",
                        f"/api/v1/functions/id/{FUNCTION_ID}/update",
                        payload=restore,
                    )
                    if bool(restored.get("is_active")) != bool(existing.get("is_active")):
                        await client.request(
                            "POST", f"/api/v1/functions/id/{FUNCTION_ID}/toggle"
                        )
            except Exception as rollback_error:
                print(
                    f"WARNING: automatic rollback also failed: {rollback_error}",
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
                "completion_push_content_free": True,
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
