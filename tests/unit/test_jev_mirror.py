import asyncio
import copy
import json
import time

import httpx
import pytest

from pda_mirror.__main__ import Mirror
from pda_wrapper.drivers import RuntimeFailure, jev
from pda_wrapper.history import origin_cell, previous_outputs


def history(rounds: int = 1) -> dict:
    tasks = []
    for iteration in range(1, rounds + 1):
        dynamic = [{"name": "implement.fake-a", "taskReferenceName": "c1", "type": "SIMPLE"}]
        tasks.extend(
            [
                {
                    "taskId": f"j-{iteration}",
                    "referenceTaskName": f"judge__{iteration}",
                    "taskDefName": "judge.jev",
                    "status": "COMPLETED",
                    "outputData": {"payload": {"dynamicTasks": dynamic}},
                },
                {
                    "taskId": f"f-{iteration}",
                    "referenceTaskName": f"fork__{iteration}",
                    "taskType": "FORK",
                    "workflowTask": {"type": "FORK_JOIN_DYNAMIC"},
                    "status": "COMPLETED",
                    "inputData": {"dynamicTasks": dynamic},
                },
                {
                    "taskId": f"c-{iteration}",
                    "referenceTaskName": f"c1__{iteration}",
                    "taskDefName": "implement.fake-a",
                    "status": "COMPLETED",
                    "retryCount": 0,
                    "outputData": {"kind": "input", "payload": {"iteration": iteration}},
                },
            ]
        )
    return {"workflowId": "j", "status": "RUNNING", "tasks": tasks}


@pytest.mark.parametrize("rounds", [0, 1, 2, 3])
def test_fixture_rounds(registry, events, monkeypatch, rounds) -> None:
    monkeypatch.setenv("JEV_MODE", "fixture")
    monkeypatch.delenv("PDA_FIXTURE_EXECUTOR", raising=False)
    monkeypatch.delenv("PDA_FIXTURE_TYPE", raising=False)

    async def scenario() -> dict:
        async with httpx.AsyncClient(
            base_url="http://conductor",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200, json=polls(registry) if "polldata" in req.url.path else history(rounds)
                )
            ),
        ) as client:
            result = await jev.run(
                registry,
                {"job_id": "j", "initial_input": "初期入力"},
                client,
                events.bind("j", "t", "judge", "jev", "judge"),
            )
            return json.loads(result.text)["payload"]

    payload = asyncio.run(scenario())
    assert payload["then"] == ("finish" if rounds >= 2 else "continue")
    assert len(payload["cells"]) == (2 if rounds == 0 else 1 if rounds == 1 else 0)
    if rounds == 1:
        assert payload["dynamicTasksInput"]["c1"]["input"] == '{"iteration": 1}'


def test_override(registry, monkeypatch) -> None:
    monkeypatch.setenv("PDA_FIXTURE_EXECUTOR", "fake-b")
    monkeypatch.setenv("PDA_FIXTURE_TYPE", "implement")
    assert jev.fixture(registry, 0)["cells"] == [
        {"type": "implement", "executor": "fake-b", "input_from": "initial"}
    ]
    assert jev.fixture(registry, 1)["then"] == "finish"


def test_history_latest_retry_before_completed_and_numeric_order() -> None:
    workflow = history(2)
    failed = copy.deepcopy(workflow["tasks"][-1])
    failed.update(taskId="retry", retryCount=1, status="FAILED")
    workflow["tasks"].append(failed)
    assert previous_outputs(workflow) == (2, [])
    failed["status"] = "COMPLETED"
    for number in [10, 2]:
        task = copy.deepcopy(failed)
        task["referenceTaskName"] = f"c{number}__2"
        workflow["tasks"].append(task)
    rounds, outputs = previous_outputs(workflow)
    assert rounds == 2
    assert [out["cell_id"] for out in outputs] == ["c1__2", "c2__2", "c10__2"]


@pytest.mark.parametrize(
    ("type_name", "executor"),
    [
        ("missing", "fake-a"),
        ("implement", "missing"),
        ("judge", "fake-a"),
    ],
)
def test_unsupported_pair(registry, type_name, executor) -> None:
    with pytest.raises(RuntimeFailure, match="judge_selected_unsupported_pair"):
        jev.flow_payload(
            [{"type": type_name, "executor": executor, "input_from": "initial"}],
            "continue",
            {"job_id": "j", "initial_input": "x"},
            [],
            registry,
        )


def test_jev_request_contract(registry, events, monkeypatch) -> None:
    monkeypatch.setenv("JEV_MODE", "live")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-key")

    def request(req: httpx.Request) -> httpx.Response:
        assert str(req.url) == "https://api.typesafe.ai/v1/systemone"
        assert req.method == "POST"
        assert req.headers["authorization"] == "Bearer test-only-key"
        assert req.headers["content-type"] == "application/json"
        body = json.loads(req.content)
        assert set(body) == {"state", "model", "questions"}
        assert body["model"] == "jev-latest"
        assert body["questions"] == registry.questions["questions"]
        assert body["state"]["context"] == {}
        assert len(body["state"]["executors"]) == 6
        return httpx.Response(200, json={"answers": registry.fixture[0]["answers"]})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(request)) as api:
            async with httpx.AsyncClient(
                base_url="http://conductor",
                transport=httpx.MockTransport(
                    lambda req: httpx.Response(
                        200, json=polls(registry) if "polldata" in req.url.path else history(0)
                    )
                ),
            ) as conductor:
                result = await jev.run(
                    registry,
                    {"job_id": "j", "initial_input": "x"},
                    conductor,
                    events.bind("j", "t", "judge", "jev", "judge"),
                    api,
                )
                assert len(json.loads(result.text)["payload"]["cells"]) == 2

    asyncio.run(scenario())


def test_empty_cells_finish(registry, events, monkeypatch, capsys) -> None:
    monkeypatch.setenv("JEV_MODE", "fixture")
    registry.fixture[0]["cells"] = []

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200, json=polls(registry) if "polldata" in req.url.path else history(0)
                )
            ),
        ) as client:
            result = await jev.run(
                registry,
                {"job_id": "j", "initial_input": "x"},
                client,
                events.bind("j", "t", "judge", "jev", "judge"),
            )
            assert json.loads(result.text)["payload"]["then"] == "finish"

    asyncio.run(scenario())
    assert "finish:empty_cells" in capsys.readouterr().out


def test_credentials_file_and_env(tmp_path, monkeypatch) -> None:
    path = tmp_path / "key"
    path.write_text('# comment\nAPI_KEY="file-test"\n')
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert jev.api_key(path) == "file-test"
    monkeypatch.setenv("TYPESAFE_API_KEY", "environment-test")
    assert jev.api_key(path) == "environment-test"


def test_mirror_final_fetch_retry_and_evict(events, capsys) -> None:
    workflow = history()
    running = ["j"]
    failed = False
    fetches = 0

    def request(req: httpx.Request) -> httpx.Response:
        nonlocal fetches
        if "running" in req.url.path:
            return httpx.Response(200, json=running)
        fetches += 1
        return httpx.Response(503) if failed else httpx.Response(200, json=workflow)

    async def scenario() -> None:
        nonlocal failed
        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(request)
        ) as c:
            mirror = Mirror(c, events)
            await mirror.poll()
            first = capsys.readouterr().out
            assert '"pda.origin_cell": "judge__1"' in first
            await mirror.poll()
            assert capsys.readouterr().out == ""
            running.clear()
            failed = True
            await mirror.poll()
            assert "j" in mirror.pending
            failed = False
            workflow["status"] = "COMPLETED"
            await mirror.poll()
            assert mirror.pending == set() and mirror.states == {}
            await mirror.poll()
            assert fetches == 4

    asyncio.run(scenario())


def test_origin_requires_matching_fork_and_judge() -> None:
    workflow = history()
    task = workflow["tasks"][-1]
    assert origin_cell(task, workflow) == "judge__1"
    workflow["tasks"][0]["outputData"]["payload"]["dynamicTasks"] = []
    assert origin_cell(task, workflow) is None


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
