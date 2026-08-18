import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "install_hermes_progress_pipe.py"
SPEC = importlib.util.spec_from_file_location("install_hermes_progress_pipe_local", MODULE_PATH)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)

RUNTIME_MODULE_PATH = Path(__file__).parents[1] / "functions" / "hermes_progress_pipe.py"
RUNTIME_SPEC = importlib.util.spec_from_file_location(
    "hermes_progress_pipe_installer_contract", RUNTIME_MODULE_PATH
)
assert RUNTIME_SPEC and RUNTIME_SPEC.loader
runtime = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(runtime)

LIVE_PROBE_PATH = Path(__file__).parent / "live_openwebui_notification_probe.py"
LIVE_PROBE_SPEC = importlib.util.spec_from_file_location(
    "live_openwebui_notification_probe_contract", LIVE_PROBE_PATH
)
assert LIVE_PROBE_SPEC and LIVE_PROBE_SPEC.loader
live_probe = importlib.util.module_from_spec(LIVE_PROBE_SPEC)
LIVE_PROBE_SPEC.loader.exec_module(live_probe)


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


def test_ntfy_server_validation_matches_runtime_policy():
    pipe = runtime.Pipe()
    values = (
        "https://ntfy.sh/",
        "http://127.0.0.1:8080/",
        "http://localhost:8080",
        "http://notify.example.com",
        "https://user:pass@ntfy.sh",
        "https://ntfy.sh?topic=secret",
        "https://example.com:99999",
        "not-a-url",
    )

    for value in values:
        try:
            installed = installer.validate_https_url(
                value, "ntfy", allow_loopback_http=True
            )
        except installer.InstallError:
            installed = None
        runtime_value = pipe._validated_notification_url(
            value, allow_loopback_http=True
        )
        assert installed == runtime_value


def test_installer_failure_path_has_no_destructive_function_rollback():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert '"DELETE"' not in source
    assert "/delete" not in source
    assert "restore_existing_function" not in source


def test_default_install_valves_enable_fifteen_minute_progress_heartbeat():
    valves = installer.build_valves_payload(
        hermes_url="http://host.docker.internal:8642/v1",
        hermes_key="test-key",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="test-topic",
        allowed_user_id="owner-user",
        openwebui_public_url="https://pda-web.example.ts.net",
    )

    assert valves["PROGRESS_HEARTBEAT_SECONDS"] == 900
    assert valves["RUN_TIMEOUT_SECONDS"] == 0


@pytest.mark.asyncio
async def test_late_expected_notification_still_gets_full_quiet_window():
    class FakeClock:
        now = 0.0

        def monotonic(self):
            return self.now

        async def sleep(self, seconds):
            self.now += seconds

    clock = FakeClock()
    expected_event = {
        "id": "late-expected",
        "event": "message",
        "time": 100,
        "message": "OWUI_PUSH_PREVIEW_OK",
    }

    async def fetch_events():
        return [expected_event] if clock.now >= 49 else []

    messages, quiet_complete = await live_probe.collect_notification_window(
        fetch_events=fetch_events,
        baseline_ids=set(),
        started_at=100,
        is_expected=lambda event: event.get("id") == "late-expected",
        initial_wait_seconds=50,
        quiet_seconds=22,
        poll_seconds=1,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    assert quiet_complete is True
    assert set(messages) == {"late-expected"}
    assert clock.now >= 71


def test_post_install_verification_requires_exact_source_and_valve_set():
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
    with pytest.raises(installer.InstallError):
        installer.verify_applied_configuration(
            verified,
            source,
            desired,
            {**desired, "UNEXPECTED_VALVE": "must-not-be-silently-accepted"},
        )
