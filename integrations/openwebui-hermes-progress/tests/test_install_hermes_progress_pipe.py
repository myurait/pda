import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "install_hermes_progress_pipe.py"
SPEC = importlib.util.spec_from_file_location("install_hermes_progress_pipe_local", MODULE_PATH)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_ntfy_topic_validation_accepts_only_runtime_safe_topics():
    assert installer.validate_ntfy_topic("pda-chat_0123456789") == "pda-chat_0123456789"

    for value in ("", "space topic", "../escape", "a" * 65):
        with pytest.raises(installer.InstallError):
            installer.validate_ntfy_topic(value)


def test_sensitive_notification_urls_require_credential_free_https():
    assert installer.validate_https_url("https://ntfy.sh/", "ntfy") == "https://ntfy.sh"
    assert (
        installer.validate_https_url(
            "https://pda-web.example.ts.net", "Open WebUI"
        )
        == "https://pda-web.example.ts.net"
    )

    for value in (
        "http://ntfy.sh",
        "https://user:pass@ntfy.sh",
        "https://ntfy.sh?topic=secret",
        "https://ntfy.sh/#fragment",
        "https://exa mple.com",
        "https://example.com\x7f",
        "https://example.com\\evil",
        "https://%65xample.com",
        "https://-bad.example",
        "https://bad-.example",
        "https://exa_mple.com",
        "https://example.com:99999",
        "not-a-url",
    ):
        with pytest.raises(installer.InstallError):
            installer.validate_https_url(value, "test")


def test_ntfy_server_validation_matches_runtime_loopback_policy():
    assert (
        installer.validate_https_url(
            "http://127.0.0.1:8080/", "ntfy", allow_loopback_http=True
        )
        == "http://127.0.0.1:8080"
    )
    assert (
        installer.validate_https_url(
            "http://localhost:8080", "ntfy", allow_loopback_http=True
        )
        == "http://localhost:8080"
    )

    with pytest.raises(installer.InstallError):
        installer.validate_https_url(
            "http://notify.example.com", "ntfy", allow_loopback_http=True
        )


def test_default_install_valves_enable_semantic_progress_without_tool_log_noise():
    valves = installer.build_valves_payload(
        hermes_url="http://host.docker.internal:8642/v1",
        hermes_key="test-key",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="test-topic",
        allowed_user_id="owner-user",
        openwebui_public_url="https://pda-web.example.ts.net",
    )

    assert valves["PROGRESS_HEARTBEAT_SECONDS"] == 300
    assert valves["PROGRESS_STALL_SECONDS"] == 600
    assert valves["SHOW_TOOL_ACTIVITY"] is False
    assert valves["SHOW_REASONING_STATUS"] is False
    assert valves["RUN_TIMEOUT_SECONDS"] == 0


@pytest.mark.asyncio
async def test_new_function_rollback_deletes_only_its_own_install_transaction():
    source = f"# {installer.OWNERSHIP_MARKER}\n# current source\n"
    nonce = "installer-run-a"

    class FakeClient:
        def __init__(self):
            self.deleted = False

        async def request(self, method, path, *, payload=None, expected={200}):
            if method == "GET":
                return 200, {
                    "id": installer.FUNCTION_ID,
                    "content": source,
                    "meta": {"manifest": {installer.INSTALL_NONCE_KEY: nonce}},
                }
            if method == "DELETE":
                self.deleted = True
                return 200, True
            raise AssertionError(f"unexpected request: {method} {path}")

    client = FakeClient()
    assert await installer.remove_created_function_if_owned(
        client, source, nonce
    ) is True
    assert client.deleted is True


@pytest.mark.asyncio
async def test_new_function_rollback_preserves_concurrently_replaced_function():
    source = f"# {installer.OWNERSHIP_MARKER}\n# current source\n"

    class FakeClient:
        def __init__(self):
            self.deleted = False

        async def request(self, method, path, *, payload=None, expected={200}):
            if method == "GET":
                return 200, {
                    "id": installer.FUNCTION_ID,
                    "content": source,
                    "meta": {
                        "manifest": {
                            installer.INSTALL_NONCE_KEY: "different-installer-run"
                        }
                    },
                }
            if method == "DELETE":
                self.deleted = True
                raise AssertionError("a concurrently replaced Function must not be deleted")
            raise AssertionError(f"unexpected request: {method} {path}")

    client = FakeClient()
    assert await installer.remove_created_function_if_owned(
        client, source, "installer-run-a"
    ) is False
    assert client.deleted is False


@pytest.mark.asyncio
async def test_existing_function_rollback_restores_security_sensitive_valves():
    existing = {
        "id": installer.FUNCTION_ID,
        "name": installer.FUNCTION_NAME,
        "content": f"# {installer.OWNERSHIP_MARKER}\n# previous source\n",
        "meta": {"description": "previous"},
        "is_active": True,
    }
    existing_valves = {
        "HERMES_API_URL": "http://host.docker.internal:8642/v1",
        "HERMES_API_KEY": "previous-hermes-key",
        "NTFY_SERVER_URL": "https://ntfy.sh",
        "NTFY_TOPIC": "previous-private-topic",
        "NTFY_ALLOWED_USER_ID": "previous-owner",
        "OPENWEBUI_PUBLIC_URL": "https://previous.example.ts.net",
    }

    class FakeClient:
        def __init__(self):
            self.calls = []
            self.current = {**existing, "is_active": False}
            self.valves = {}

        async def request(self, method, path, *, payload=None, expected={200}):
            self.calls.append((method, path, payload, expected))
            if method == "POST" and path.endswith("/valves/update"):
                assert isinstance(payload, dict)
                self.valves = dict(payload)
                return 200, dict(self.valves)
            if method == "POST" and path.endswith("/update"):
                assert isinstance(payload, dict)
                self.current = {**payload, "is_active": False}
                return 200, dict(self.current)
            if method == "POST" and path.endswith("/toggle"):
                self.current["is_active"] = not self.current["is_active"]
                return 200, dict(self.current)
            if method == "GET" and path.endswith("/valves"):
                return 200, dict(self.valves)
            if method == "GET":
                return 200, dict(self.current)
            raise AssertionError(f"unexpected request: {method} {path}")

    client = FakeClient()
    await installer.restore_existing_function(client, existing, existing_valves)

    assert client.calls[0][0:2] == (
        "POST",
        f"/api/v1/functions/id/{installer.FUNCTION_ID}/update",
    )
    assert client.calls[1][0:2] == (
        "POST",
        f"/api/v1/functions/id/{installer.FUNCTION_ID}/valves/update",
    )
    assert client.calls[1][2] == existing_valves
    assert client.calls[2][0:2] == (
        "GET",
        f"/api/v1/functions/id/{installer.FUNCTION_ID}",
    )
    assert client.calls[3][0:2] == (
        "POST",
        f"/api/v1/functions/id/{installer.FUNCTION_ID}/toggle",
    )
    assert client.current == existing
    assert client.valves == existing_valves


@pytest.mark.asyncio
async def test_existing_function_rollback_fails_if_valves_are_not_restored():
    existing = {
        "id": installer.FUNCTION_ID,
        "name": "Previous Progress Pipe",
        "content": f"# {installer.OWNERSHIP_MARKER}\n# previous source\n",
        "meta": {"description": "previous"},
        "is_active": True,
    }
    existing_valves = {
        "HERMES_API_KEY": "previous-hermes-key",
        "NTFY_TOPIC": "previous-private-topic",
    }

    class SilentRollbackFailureClient:
        async def request(self, method, path, *, payload=None, expected={200}):
            if method == "GET" and path.endswith("/valves"):
                return 200, {
                    **existing_valves,
                    "NTFY_TOPIC": "new-topic-was-not-rolled-back",
                }
            if method == "GET":
                return 200, dict(existing)
            return 200, dict(existing)

    with pytest.raises(installer.InstallError, match="rollback verification"):
        await installer.restore_existing_function(
            SilentRollbackFailureClient(), existing, existing_valves
        )


def test_post_install_verification_checks_source_and_every_desired_valve():
    source = "# source"
    desired = {
        "HERMES_API_KEY": "new-key",
        "NTFY_TOPIC": "new-private-topic",
        "OPENWEBUI_PUBLIC_URL": "https://pda.example.ts.net",
    }
    verified = {"content": source, "is_active": True}

    installer.verify_applied_configuration(verified, source, desired, dict(desired))

    with pytest.raises(installer.InstallError):
        installer.verify_applied_configuration(
            {"content": "# stale", "is_active": True},
            source,
            desired,
            dict(desired),
        )
    with pytest.raises(installer.InstallError):
        installer.verify_applied_configuration(
            verified,
            source,
            desired,
            {**desired, "NTFY_TOPIC": "stale-topic"},
        )
