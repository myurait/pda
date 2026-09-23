import asyncio
import copy
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml
from jsonschema import Draft7Validator, ValidationError

from pda_wrapper.drivers import jev
from pda_wrapper.events import Events
from pda_wrapper.worker import Worker

ROOT = Path(__file__).resolve().parents[2]


def test_no_internal_imports() -> None:
    for path in (ROOT / "src").rglob("*.py"):
        assert "_internal" not in path.read_text(), path


def test_empty_endpoint_has_no_exporters(monkeypatch) -> None:
    def forbidden(*args, **kwargs) -> None:
        raise AssertionError("exporter created")

    monkeypatch.setattr("pda_wrapper.events.OTLPLogExporter", forbidden)
    monkeypatch.setattr("pda_wrapper.events.OTLPSpanExporter", forbidden)
    asyncio.run(Events("").close())


def test_registry_and_deployment(registry) -> None:
    assert "claude-company" not in registry.executors
    claude = registry.executors["claude-personal"]
    assert claude["account"] == "personal"
    assert claude["adapter"]["env"]["CLAUDE_CONFIG_DIR"] == "/claude-config"
    assert registry.executors["codex-personal"]["adapter"]["env"] == {
        "INITIAL_AGENT_MODE": "agent-full-access"
    }
    for name, definition in registry.types.items():
        schema = definition["input_schema"]
        assert schema["properties"]["workdir"] == {"type": "string"}
        assert ("workdir" in schema["required"]) is (name != "judge")
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    codex = compose["services"]["exec-codex-personal"]
    assert codex["environment"]["CODEX_HOME"] == "/codex-home"
    assert "${CODEX_AUTH_DIR:-../secrets/codex}:/codex-home" in codex["volumes"]
    settings = json.loads((ROOT / "deploy/executors/claude-settings.json").read_text())
    assert settings == {"permissions": {"defaultMode": "bypassPermissions"}}
    collector = yaml.safe_load((ROOT / "deploy/otel-collector.yaml").read_text())
    for signal, filename in [("logs", "events"), ("traces", "traces")]:
        exporter = collector["exporters"][f"file/{signal}"]
        assert exporter["path"] == f"/var/lib/pda/events/{filename}.jsonl"
        assert exporter["rotation"] == {"max_megabytes": 100, "max_backups": 5}
        assert f"file/{signal}" in collector["service"]["pipelines"][signal]["exporters"]


def test_workdir_required(registry, task) -> None:
    del task["inputData"]["workdir"]
    with pytest.raises(ValidationError):
        Draft7Validator(registry.types["implement"]["input_schema"]).validate(task["inputData"])


def test_workdir_created_prompt_and_flush(registry, task, events, monkeypatch, capsys) -> None:
    monkeypatch.setenv("FAKE_MODE", "echo")
    flush = AsyncMock()
    monkeypatch.setattr(events, "force_flush", flush)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(lambda req: httpx.Response(200))
        ) as client:
            worker = Worker(registry, "fake-a", client, events)
            assert (await worker.process(task))["status"] == "COMPLETED"
            assert (await worker.process(task))["status"] == "COMPLETED"

    asyncio.run(scenario())
    note = (Path(task["inputData"]["workdir"]) / "note.txt").read_text()
    assert task["inputData"]["workdir"] in note
    assert flush.await_count == 2
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert all(
        r["attributes"]["pda.workdir"] == task["inputData"]["workdir"]
        for r in records
        if r["body"] == "job.received"
    )


@pytest.mark.parametrize("succeed", [True, False])
def test_result_delivery_deadline(registry, task, events, monkeypatch, capsys, succeed) -> None:
    clock = [100.0]
    attempts = []
    monkeypatch.setattr("pda_wrapper.worker.time.monotonic", lambda: clock[0])

    async def sleep(delay: float) -> None:
        assert delay == 1
        clock[0] += delay

    monkeypatch.setattr("pda_wrapper.worker.asyncio.sleep", sleep)
    task["responseTimeoutSeconds"] = 5
    clock[0] = 102.0

    def request(req: httpx.Request) -> httpx.Response:
        attempts.append(clock[0])
        return httpx.Response(200 if succeed and len(attempts) == 3 else 503)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(request)
        ) as c:
            await Worker(registry, "fake-a", c, events).deliver(
                {"workflowInstanceId": "job-unit", "taskId": "task-unit"}, task, 100.0
            )

    asyncio.run(scenario())
    assert attempts == [102.0, 103.0, 104.0]
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(r.get("body") == "unknown" for r in records) is (not succeed)


def test_round_limit_fixture(registry, events, monkeypatch, capsys) -> None:
    monkeypatch.setenv("JEV_MODE", "fixture")
    monkeypatch.delenv("PDA_FIXTURE_EXECUTOR", raising=False)
    registry.fixture = [copy.deepcopy(registry.fixture[0]) for _ in range(11)]
    tasks = []

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200, json=polls(registry) if "polldata" in req.url.path else {"tasks": tasks}
                )
            ),
        ) as client:
            for rounds in range(11):
                output = await jev.run(
                    registry,
                    {"job_id": "j", "initial_input": "x"},
                    client,
                    events.bind("j", "t", "judge", "jev", "judge"),
                )
                payload = json.loads(output.text)["payload"]
                assert payload["then"] == ("finish" if rounds == 10 else "continue")
                if rounds < 10:
                    assert payload["dynamicTasksInput"]["c1"]["workdir"] == "/work/jobs/j"
                else:
                    assert payload["cells"] == [] and payload["dynamicTasksInput"] == {}
                tasks.append({"referenceTaskName": f"c1__{rounds + 1}", "status": "COMPLETED"})

    asyncio.run(scenario())
    assert "finish:round_limit" in capsys.readouterr().out


def test_shutdown_wait_is_bounded(monkeypatch) -> None:
    events = Events()
    monkeypatch.setattr(events, "_flush", lambda: time.sleep(6))
    started = time.monotonic()
    asyncio.run(events.close())
    assert 4.9 < time.monotonic() - started < 5.5


def test_flush_before_result_delivery(registry, task, events, monkeypatch) -> None:
    order = []
    monkeypatch.setenv("FAKE_MODE", "echo")

    async def flush() -> None:
        order.append("flush")

    monkeypatch.setattr(events, "force_flush", flush)

    async def scenario() -> None:
        def request(req: httpx.Request) -> httpx.Response:
            if "/poll/" in req.url.path:
                return httpx.Response(200, json=task)
            if req.url.path == "/api/tasks":
                order.append("deliver")
                worker.stop()
            return httpx.Response(200)

        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(request)
        ) as client:
            worker = Worker(registry, "fake-a", client, events)
            await worker.run()

    asyncio.run(scenario())
    assert order == ["flush", "deliver"]


def polls(registry) -> list[dict]:
    return [
        {
            "queueName": f"{name}.{executor}",
            "workerId": executor,
            "lastPollTime": time.time() * 1000,
        }
        for executor, declaration in registry.executors.items()
        for name in declaration["types"]
    ]
