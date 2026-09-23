import asyncio
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
import yaml

from pda_view.__main__ import Handler, View
from pda_wrapper.drivers import jev
from pda_wrapper.drivers.acp import AcpClient

ROOT = Path(__file__).resolve().parents[2]


def test_notifications(events, capsys) -> None:
    client = AcpClient({}, events.bind("j", "t", "c", "fake-a", "implement"))
    for kind in ["available_commands_update", "session_info_update"]:
        client.update({"sessionUpdate": kind})
    assert capsys.readouterr().out == ""
    client.update({"sessionUpdate": "future"})
    assert "unknown" in capsys.readouterr().out


def test_prompts_compose() -> None:
    prompts = [p for p in (ROOT / "registry/prompts").glob("*.md") if p.stem != "judge"]
    assert len(prompts) == 6
    assert all("出力は JSON だけを返す。" in p.read_text() for p in prompts)
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    assert compose["name"] == "pda"
    services = compose["services"]
    assert all(
        s["image"].endswith(":local")
        for s in services.values()
        if s["image"].startswith("pda-executor")
    )
    assert services["exec-jev"]["environment"]["PDA_MAX_ROUNDS"] == "${PDA_MAX_ROUNDS:-}"
    assert services["pda-view"]["networks"] == ["public", "telemetry", "mirror"]


@pytest.mark.parametrize("fallback", [None, 404, "shape"])
def test_availability(registry, monkeypatch, fallback) -> None:
    monkeypatch.setattr(jev.time, "time", lambda: 100)
    requested = []
    rows = [
        {"queueName": f"implement.{name}", "workerId": name, "lastPollTime": stamp}
        for name, stamp in [
            ("fake-b", 40000),
            ("fake-a", 39999),
            ("codex-personal", 100001),
            ("claude-personal", 100000),
        ]
    ]

    def request(req) -> httpx.Response:
        requested.append(req)
        if req.url.path.endswith("/all"):
            if fallback == 404:
                return httpx.Response(404)
            return httpx.Response(200, json={} if fallback else rows)
        return httpx.Response(
            200, json=[r for r in rows if r["queueName"] == req.url.params["taskType"]]
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(request)
        ) as client:
            assert await jev.available_executors(client, registry) == ["claude-personal", "fake-b"]

    asyncio.run(scenario())
    assert len(requested) == (20 if fallback else 1)


@pytest.mark.parametrize(
    ("original", "type_name", "available", "expected"),
    [
        ("codex-personal", "implement", ["fake-b", "fake-a"], "fake-a"),
        ("tools", "implement", ["tools", "fake-b"], "fake-b"),
        ("fake-a", "implement", [], None),
    ],
)
def test_substitution(registry, events, capsys, original, type_name, available, expected) -> None:
    cells, finished = jev.substitute(
        [{"type": type_name, "executor": original, "input_from": "initial"}],
        available,
        registry,
        events.bind("j", "t", "judge", "jev", "judge"),
    )
    assert finished == (expected is None)
    if expected:
        assert cells[0]["executor"] == expected
        assert f"substituted:{original}->{expected}" in capsys.readouterr().out
    else:
        assert cells == []
        assert "finish:no_available_executor" in capsys.readouterr().out


def test_max_rounds(registry, events, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PDA_MAX_ROUNDS", "1")

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"tasks": [{"referenceTaskName": "c1__1"}]})
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
    assert "finish:round_limit" in capsys.readouterr().out


@pytest.fixture
def view_server():
    calls = []
    workflow = {
        "status": "COMPLETED",
        "startTime": 100,
        "endTime": 200,
        "input": {"initial_input": "x" * 100},
        "tasks": [
            {
                "referenceTaskName": "c1__1",
                "seq": 2,
                "taskDefName": "implement.fake-a",
                "status": "COMPLETED",
                "startTime": 100,
                "endTime": 150,
                "outputData": {"kind": "result", "payload": {"text": "ok"}},
            },
            {
                "referenceTaskName": "judge__1",
                "seq": 1,
                "taskDefName": "judge.jev",
                "status": "COMPLETED",
            },
        ],
    }
    broken = set()

    def request(req) -> httpx.Response:
        calls.append(req)
        if req.url.host in broken:
            raise httpx.ConnectError("offline", request=req)
        if req.url.path.endswith("/running/pda_job"):
            return httpx.Response(200, json=["j"])
        if req.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"workflowId": "j"}]})
        if req.url.path.endswith("/_search"):
            return httpx.Response(
                200,
                json={
                    "hits": [
                        {
                            "_timestamp": 1,
                            "body": "judge.answer",
                            "pda_cell_id": "judge__1",
                            "pda_executor_id": "jev",
                            "pda_question_id": "executor",
                            "pda_answer": "fake-a",
                        }
                    ]
                },
            )
        return httpx.Response(200, json=workflow)

    with (
        httpx.Client(base_url="http://c", transport=httpx.MockTransport(request)) as c,
        httpx.Client(base_url="http://o", transport=httpx.MockTransport(request)) as o,
    ):

        class TestHandler(Handler):
            view = View(c, o, "pda_events")

        server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}") as client:
                yield client, calls, broken
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


def test_view_apis_and_assets(view_server) -> None:
    client, calls, _ = view_server
    jobs = client.get("/api/jobs").json()
    assert jobs == [
        {
            "job_id": "j",
            "status": "COMPLETED",
            "start_time": 100,
            "end_time": 200,
            "executors": ["jev", "fake-a"],
            "initial_input": "x" * 80,
        }
    ]
    detail = client.get("/api/jobs/j").json()
    assert set(detail) == {"job_id", "status", "reason", "initial_input", "cells"}
    assert [c["ref"] for c in detail["cells"]] == ["judge__1", "c1__1"]
    assert detail["cells"][1]["duration_ms"] == 50
    assert set(detail["cells"][1]) == {
        "ref",
        "type",
        "executor",
        "status",
        "retry_count",
        "start_time",
        "end_time",
        "duration_ms",
        "reason",
        "output_kind",
        "output_excerpt",
    }
    assert client.get("/api/jobs/j/events?cell=judge__1").json() == [
        {
            "time": 1,
            "kind": "judge.answer",
            "executor": "jev",
            "cell": "judge__1",
            "summary": "executor / fake-a",
        }
    ]
    sql = json.loads(calls[-1].content)["query"]["sql"]
    assert "pda_job_id = 'j' AND pda_cell_id = 'judge__1'" in sql
    html = client.get("/").text
    assert all(f'id="{name}"' in html for name in ["jobs", "detail", "events"])
    for path in ["/static/app.js", "/static/app.css"]:
        assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    ("host", "path"), [("c", "/api/jobs"), ("c", "/api/jobs/j"), ("o", "/api/jobs/j/events")]
)
def test_upstream_failure_recovers(view_server, host, path) -> None:
    client, _, broken = view_server
    broken.add(host)
    response = client.get(path)
    assert response.status_code == 502 and "reason" in response.json()
    broken.clear()
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("from_file", [True, False])
def test_probe_sources(registry, tmp_path, monkeypatch, from_file) -> None:
    import argparse

    from tools.judge_probe import probe

    workflow = {"input": {"initial_input": "saved"}, "tasks": []}
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(workflow))
    original = httpx.AsyncClient
    requests = []

    def request(req) -> httpx.Response:
        requests.append(req)
        if req.url.host == "api.typesafe.ai":
            assert json.loads(req.content)["state"]["initial_input"] == "saved"
            return httpx.Response(200, json={"answers": registry.fixture[0]["answers"]})
        return httpx.Response(200, json=[] if "polldata" in req.url.path else workflow)

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(request))
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "unit-test")
    args = argparse.Namespace(
        registry=ROOT / "registry",
        conductor="http://c",
        workflow_file=path if from_file else None,
        job_id=None if from_file else "j",
        initial_input=None,
    )
    result = asyncio.run(probe(args))
    assert result["state_summary"] == {
        "rounds": 0,
        "previous_outputs": 0,
        "available_executors": [],
    }
    assert result["answers"] == registry.fixture[0]["answers"]
    assert result["elapsed_ms"] >= 0
    assert sum(req.url.host == "api.typesafe.ai" for req in requests) == 1


def test_search_query_fallback() -> None:
    queries = []

    def request(req) -> httpx.Response:
        if req.url.path.endswith("/search"):
            queries.append(req.url.params["query"])
            if len(queries) == 1:
                return httpx.Response(400)
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json=[])

    with httpx.Client(base_url="http://c", transport=httpx.MockTransport(request)) as client:
        assert View(client, client, "pda_events").jobs() == []
    assert queries == ["workflowType='pda_job'", "workflowType IN (pda_job)"]


def test_fixture_state_is_observable(registry, events, monkeypatch, capsys) -> None:
    monkeypatch.setenv("JEV_MODE", "fixture")
    monkeypatch.delenv("PDA_FIXTURE_EXECUTOR", raising=False)
    monkeypatch.delenv("PDA_MAX_ROUNDS", raising=False)
    monkeypatch.setattr(jev.time, "time", lambda: 100)
    rows = [
        {
            "queueName": f"{declaration['types'][0]}.{executor}",
            "workerId": executor,
            "lastPollTime": 100000,
        }
        for executor, declaration in registry.executors.items()
        if executor in ["fake-a", "fake-b", "jev", "tools"]
    ]

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json=rows if "polldata" in req.url.path else {})
            ),
        ) as client:
            await jev.run(
                registry,
                {"job_id": "j", "initial_input": "x"},
                client,
                events.bind("j", "t", "judge", "jev", "judge"),
            )

    asyncio.run(scenario())
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    state = next(r for r in records if r["attributes"].get("pda.input_kind") == "judge_state")
    assert state["body"] == "input.assembled"
    assert state["attributes"]["pda.available_executors"] == ["fake-a", "fake-b", "jev", "tools"]
    assert state["attributes"]["pda.previous_outputs"] == 0
    assert not any(r["body"] == "unknown" for r in records)
