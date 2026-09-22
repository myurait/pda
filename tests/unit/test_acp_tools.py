import asyncio
import json
import os
import sys
import time

import acp as sdk
import pytest
from acp.connection import StreamDirection, StreamEvent
from acp.schema import PermissionOption, ToolCallUpdate

from pda_wrapper.drivers import RuntimeFailure, acp, tools


def test_fake_slow_returns_cancelled_on_protocol_cancel(
    registry, events, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_MODE", "slow")
    declaration = registry.executors["fake-a"]

    async def scenario() -> None:
        client = acp.AcpClient(declaration, events.bind("j", "t", "c1", "fake-a", "implement"))
        async with sdk.spawn_agent_process(
            client, *declaration["adapter"]["command"], env=dict(os.environ), cwd=str(tmp_path)
        ) as (connection, process):
            await connection.initialize(protocol_version=sdk.PROTOCOL_VERSION)
            session = await connection.new_session(cwd=str(tmp_path), mcp_servers=[])
            pending = asyncio.create_task(
                connection.prompt(session_id=session.session_id, prompt=[sdk.text_block("slow")])
            )
            await asyncio.sleep(0.3)
            await connection.cancel(session_id=session.session_id)
            response = await asyncio.wait_for(pending, 2)
            assert response.stop_reason == "cancelled"
            assert process.returncode is None

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["echo", "invalid", "permission", "slow"])
def test_real_acp_roundtrip(registry, events, tmp_path, monkeypatch, capsys, mode) -> None:
    monkeypatch.setenv("FAKE_MODE", mode)
    monkeypatch.setenv("FAKE_SLEEP_SECONDS", "700")

    async def scenario() -> None:
        bound = events.bind("job", "task", "c1", "fake-a", "implement")
        pending = asyncio.create_task(
            acp.run(registry.executors["fake-a"], "hello", bound, str(tmp_path))
        )
        if mode == "slow":
            await asyncio.sleep(0.8)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(pending, 5)
        else:
            output = await asyncio.wait_for(pending, 5)
            assert json.loads(output.text)["kind"] == ("bogus" if mode == "invalid" else "input")
        await events.close()

    asyncio.run(scenario())
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    kinds = {line["body"] for line in records}
    assert {"reasoning", "tool.call", "tool.result", "turn.end"} <= kinds
    if mode == "slow":
        assert records[-1]["attributes"]["pda.stop_reason"] == "cancelled"
    if mode == "permission":
        assert {"permission.request", "permission.response"} <= kinds


@pytest.mark.parametrize(
    ("deny", "options", "expected"),
    [
        ([], ["allow_once", "reject_once"], "allow_once"),
        (["read"], ["allow_once", "reject_once"], "reject_once"),
        (["read"], ["allow_once"], None),
    ],
)
def test_permissions(registry, events, deny, options, expected) -> None:
    declaration = registry.executors["fake-a"]
    declaration["permissions"]["deny_kinds"] = deny
    client = acp.AcpClient(declaration, events.bind("j", "t", "c", "fake-a", "implement"))
    response = asyncio.run(
        client.request_permission(
            "s",
            ToolCallUpdate(tool_call_id="t", kind="read"),
            [PermissionOption(option_id=kind, kind=kind, name=kind) for kind in options],
        )
    )
    assert response.outcome.outcome == ("selected" if expected else "cancelled")
    if expected:
        assert response.outcome.option_id == expected


def test_raw_observer_and_usage(registry, events, capsys) -> None:
    client = acp.AcpClient(
        registry.executors["fake-a"], events.bind("j", "t", "c", "a", "implement")
    )
    for update in [
        {"sessionUpdate": "future_variant", "value": 1},
        {"sessionUpdate": "plan", "entries": [1, 2]},
        {"sessionUpdate": "usage_update", "used": 12, "size": 100},
    ]:
        client.observe(
            StreamEvent(
                StreamDirection.INCOMING, {"method": "session/update", "params": {"update": update}}
            )
        )
    client.usage({"inputTokens": 5, "outputTokens": 8})
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert records[0]["body"] == "unknown"
    assert "future_variant" in records[0]["attributes"]["pda.raw"]
    assert records[1]["attributes"]["pda.items"] == 2
    assert "gen_ai.usage.input_tokens" not in records[2]["attributes"]
    assert records[3]["attributes"]["gen_ai.usage.output_tokens"] == 8


def test_stderr_is_log_not_event(registry, events, tmp_path, capsys) -> None:
    declaration = registry.executors["fake-a"]
    declaration["adapter"]["command"] = [
        sys.executable,
        "-c",
        "import sys,asyncio; print('stderr sentinel', file=sys.stderr); "
        "import acp; from pda_fake_agent.__main__ import FakeAgent; "
        "asyncio.run(acp.run_agent(FakeAgent()))",
    ]
    asyncio.run(
        acp.run(declaration, "hello", events.bind("j", "t", "c", "a", "implement"), str(tmp_path))
    )
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(record.get("message") == "runtime.stderr" for record in records)
    assert not any(
        "stderr sentinel" in json.dumps(record) for record in records if "body" in record
    )


def test_failed_runtime_contains_stderr_tail(registry, events, tmp_path, capsys) -> None:
    declaration = registry.executors["fake-a"]
    declaration["adapter"]["command"] = [
        sys.executable,
        "-c",
        "import sys; [print('line'+str(n), file=sys.stderr) for n in range(30)]; sys.exit(2)",
    ]
    with pytest.raises(RuntimeFailure):
        asyncio.run(
            acp.run(
                declaration, "hello", events.bind("j", "t", "c", "a", "implement"), str(tmp_path)
            )
        )
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    failure = json.loads(records[-1]["attributes"]["pda.raw"])
    assert failure["stderr_tail"] == [f"line{n}" for n in range(10, 30)]


@pytest.mark.parametrize("exit_code", [0, 7])
def test_tools_exit_and_workdir(events, tmp_path, exit_code) -> None:
    command = [
        sys.executable,
        "-c",
        f"import os,sys;print(os.getcwd());print('error',file=sys.stderr);sys.exit({exit_code})",
    ]
    result = asyncio.run(
        tools.run(
            command,
            json.dumps({"workdir": str(tmp_path)}),
            events.bind("j", "t", "c", "tools", "verify.test"),
        )
    )
    payload = json.loads(result.text)["payload"]
    assert payload["passed"] is (exit_code == 0)
    assert payload["exit_code"] == exit_code
    assert payload["stdout_tail"].strip() == str(tmp_path)
    assert payload["stderr_tail"].strip() == "error"


def test_tools_deadline_kills_process(events, tmp_path) -> None:
    pidfile = tmp_path / "pid"
    command = [
        sys.executable,
        "-c",
        "import os,time,pathlib;"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(100)",
    ]

    async def scenario() -> None:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(
                tools.run(
                    command, "{}", events.bind("j", "t", "c", "tools", "verify.test"), str(tmp_path)
                ),
                0.5,
            )

    started = time.monotonic()
    asyncio.run(scenario())
    assert time.monotonic() - started < 4
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)
