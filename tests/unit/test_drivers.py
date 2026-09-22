import asyncio
import copy
import json
import sys

import httpx
import pytest

from pda_wrapper.drivers import RuntimeFailure, acp, jev, tools


@pytest.mark.parametrize(
    ("mode", "kind"), [("echo", "input"), ("invalid", "bogus"), ("permission", "input")]
)
def test_real_acp_sdk_roundtrip(registry, events, tmp_path, mode, kind):
    declaration = copy.deepcopy(registry.executors["fake-a"])
    declaration["adapter"] = {
        "command": [sys.executable, "-m", "pda_fake_agent"],
        "env": {"FAKE_MODE": mode},
    }
    raw, stop = asyncio.run(acp.run(declaration, "hello", events, str(tmp_path)))
    assert json.loads(raw)["kind"] == kind
    assert stop == "end_turn"
    kinds = [k for k, _ in events.records]
    assert "tool.call" in kinds and "tool.result" in kinds and "reasoning" in kinds
    if mode == "permission":
        assert dict(events.records)["permission.response"]["pda.option_id"] == "yes"


def test_permission_deny_and_missing_option():
    choices = [{"optionId": "yes", "kind": "allow_once"}, {"optionId": "no", "kind": "reject_once"}]
    assert acp.permission_option(
        {"kind": "delete"}, choices, {"deny_kinds": ["delete"], "default": "allow_once"}
    ) == ("no", "reject_once")
    assert acp.permission_option({}, [], {"default": "allow_once"})[0] is None


def test_acp_cancellation(registry, events, tmp_path):
    decl = copy.deepcopy(registry.executors["fake-a"])
    decl["adapter"] = {
        "command": [sys.executable, "-m", "pda_fake_agent"],
        "env": {"FAKE_MODE": "slow", "FAKE_SLEEP_SECONDS": "60"},
    }

    async def check():
        task = asyncio.create_task(acp.run(decl, "x", events, str(tmp_path)))
        for _ in range(100):
            if any(k == "tool.result" for k, _ in events.records):
                break
            await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(check())
    assert dict(events.records)["turn.end"]["pda.stop_reason"] == "cancelled"


def test_tools_result_and_workdir(events, tmp_path):
    cmd = [sys.executable, "-c", "import os; print(os.getcwd()); raise SystemExit(2)"]
    raw, _ = asyncio.run(
        tools.run({"command": cmd}, {"input": json.dumps({"workdir": str(tmp_path)})}, events)
    )
    result = json.loads(raw)["payload"]
    assert not result["passed"] and result["exit_code"] == 2
    assert str(tmp_path) in result["stdout_tail"]
    assert dict(events.records)["command.run"]["pda.exit_code"] == 2


def test_tools_timeout(events, tmp_path):
    with pytest.raises(RuntimeFailure):
        asyncio.run(
            tools.run(
                {"command": [sys.executable, "-c", "import time; time.sleep(60)"]},
                {"input": "x"},
                events,
                str(tmp_path),
                timeout=0.1,
            )
        )
    assert dict(events.records)["command.run"]["pda.exit_code"] == -9


def test_previous_round_not_lexicographic_or_first_retry():
    def cell(ref, value, retry=0, status="COMPLETED"):
        return {
            "referenceTaskName": ref,
            "retryCount": retry,
            "status": status,
            "inputData": {"type": "implement"},
            "outputData": {"kind": "input", "payload": value, "meta": {"executor_id": "fake-a"}},
        }

    tasks = [
        cell("c1__2", "old"),
        cell("c1__10", "failed", status="TIMED_OUT"),
        cell("c1__10", "new", retry=1),
        cell("c2__10", "second"),
    ]
    assert [x["payload"] for x in jev.previous_outputs({"tasks": tasks})] == ["new", "second"]


def test_flow_conversion_preserves_payload(registry):
    state = {
        "initial_input": "初期",
        "context": {"a": 1},
        "previous_outputs": [{"payload": {"text": "結果"}}],
    }
    cell = {"type": "implement", "executor": "fake-a", "input_from": "previous"}
    flow = jev.flow_payload([cell], state, registry, "j")
    assert flow["dynamicTasks"][0]["name"] == "implement.fake-a"
    assert json.loads(flow["dynamicTasksInput"]["c1"]["input"]) == {"text": "結果"}
    assert flow["dynamicTasksInput"]["c1"]["context"] == state["context"]
    assert jev.flow_payload([], state, registry, "j")["then"] == "finish"
    with pytest.raises(RuntimeFailure):
        jev.flow_payload([{**cell, "executor": "tools"}], state, registry, "j")


@pytest.mark.parametrize("has_previous", [False, True])
def test_fixture_without_api(registry, events, monkeypatch, has_previous):
    monkeypatch.setenv("JEV_MODE", "fixture")
    monkeypatch.delenv("PDA_FIXTURE_EXECUTOR", raising=False)
    task = {
        "referenceTaskName": "c1__1",
        "status": "COMPLETED",
        "inputData": {"type": "implement"},
        "outputData": {"kind": "input", "payload": {}},
    }

    def handler(request):
        assert request.url.host == "engine"
        assert request.url.params["includeTasks"] == "true"
        return httpx.Response(200, json={"tasks": [task] if has_previous else []})

    async def check():
        async with httpx.AsyncClient(
            base_url="http://engine/api", transport=httpx.MockTransport(handler)
        ) as client:
            return await jev.run(registry, {"job_id": "j", "initial_input": "仕事"}, events, client)

    result = json.loads(asyncio.run(check())[0])
    assert result["payload"]["then"] == ("finish" if has_previous else "continue")
    assert len([k for k, _ in events.records if k == "judge.answer"]) == 4


def test_api_key_precedence(tmp_path, monkeypatch):
    path = tmp_path / "credentials"
    path.write_text('API_KEY="file-example"\n')
    monkeypatch.setenv("TYPESAFE_API_KEY", "env-example")
    assert jev.api_key(path) == "env-example"
    monkeypatch.delenv("TYPESAFE_API_KEY")
    assert jev.api_key(path) == "file-example"
