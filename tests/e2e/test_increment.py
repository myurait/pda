"""Run only against the explicitly started local fixture Compose project."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import pytest

from tools.generate_defs import generate, register

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/reports/evidence/increment-1"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "deploy/docker-compose.yaml")]
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.getenv("PDA_E2E") != "1", reason="PDA_E2E=1 only"),
]


def compose(*args: str, env: dict | None = None, stdin: str | None = None) -> str:
    result = subprocess.run(
        COMPOSE + list(args),
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        input=stdin,
        text=True,
        capture_output=True,
        timeout=360,
    )
    assert result.returncode == 0, result.stderr[-8000:]
    return result.stdout


def save(name: str, value: object) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def until(check, timeout: float = 180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(1)
    raise AssertionError("condition did not become true before timeout")


@pytest.fixture(scope="module")
def engine():
    compose(
        "up",
        "-d",
        "--build",
        env={"PDA_FIXTURE_EXECUTOR": "", "FAKE_B_MODE": "echo", "FAKE_B_LEASE_EXTEND": "true"},
    )
    client = httpx.Client(base_url="http://localhost:8080/api", timeout=30)

    def ready():
        try:
            return client.get("/metadata/taskdefs").status_code == 200
        except httpx.HTTPError:
            return False

    until(ready)
    tasks, workflow = generate(ROOT / "registry")
    save(
        "registration.json",
        {"first": register(client, tasks, workflow), "second": register(client, tasks, workflow)},
    )
    # The sample test occupies at least one 3-second mirror interval.
    compose(
        "exec",
        "-T",
        "exec-tools",
        "python",
        "-c",
        "from pathlib import Path; p=Path('/work/pda_e2e_fixture'); p.mkdir(exist_ok=True); "
        "(p/'README').write_text('PDA integration fixture'); "
        "(p/'test_readme.py').write_text('import time\\nfrom pathlib import Path\\n"
        "def test_readme():\\n    time.sleep(4)\\n"
        '    assert Path(__file__).with_name("README").read_text()\\n\')',
    )
    try:
        yield client
    finally:
        register(client, tasks, workflow)
        compose(
            "up",
            "-d",
            "--no-deps",
            "exec-fake-b",
            "exec-jev",
            env={"PDA_FIXTURE_EXECUTOR": "", "FAKE_B_MODE": "echo", "FAKE_B_LEASE_EXTEND": "true"},
        )
        client.close()


def start(engine: httpx.Client) -> str:
    response = engine.post(
        "/workflow",
        json={
            "name": "pda_job",
            "version": 1,
            "input": {"initial_input": "README を要約せよ", "context": {}},
        },
    )
    assert response.is_success, response.text
    return response.text.strip('"')


def snapshot(engine: httpx.Client, wid: str) -> dict:
    response = engine.get("/workflow/" + wid, params={"includeTasks": "true"})
    response.raise_for_status()
    return response.json()


def completed(engine: httpx.Client, wid: str) -> dict | None:
    data = snapshot(engine, wid)
    if data["status"] in ("COMPLETED", "FAILED", "TIMED_OUT", "TERMINATED"):
        return data
    return None


def event_rows(wid: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "events.jsonl"
        compose("cp", "otel-collector:/var/lib/pda/events/events.jsonl", str(path))
        rows = []
        for line in path.read_text().splitlines():
            try:
                packet = json.loads(line)
            except json.JSONDecodeError:
                continue  # A live writer may have an incomplete final line.
            for resource in packet.get("resourceLogs", []):
                for scope in resource.get("scopeLogs", []):
                    for record in scope.get("logRecords", []):
                        attrs = {
                            a["key"]: next(iter(a["value"].values()), None)
                            for a in record.get("attributes", [])
                        }
                        if attrs.get("pda.job_id") == wid:
                            rows.append(
                                {
                                    **attrs,
                                    "traceId": record.get("traceId"),
                                    "spanId": record.get("spanId"),
                                }
                            )
        return rows


@pytest.fixture(scope="module")
def normal(engine):
    wid = start(engine)
    data = until(lambda: completed(engine, wid))
    save("normal-workflow.json", data)
    return wid, data


def test_01_two_iterations(engine, normal):
    wid, data = normal
    assert data["status"] == "COMPLETED", data.get("reasonForIncompletion")
    assert [t["referenceTaskName"] for t in data["tasks"] if t["taskDefName"] == "judge.jev"] == [
        "judge__1",
        "judge__2",
    ]
    cells = [t for t in data["tasks"] if t["referenceTaskName"].startswith("c")]
    assert {t["taskDefName"] for t in cells} == {"break-down.fake-a", "verify.test.tools"}
    assert all(t["status"] == "COMPLETED" for t in cells)
    assert next(t for t in cells if t["taskDefName"] == "verify.test.tools")["outputData"][
        "payload"
    ]["passed"]
    for task in cells:
        log = engine.get(f"/tasks/{task['taskId']}/log")
        assert log.is_success and log.json()


def test_02_file_events(normal):
    wid, _ = normal
    required = {
        "job.received",
        "input.assembled",
        "tool.call",
        "tool.result",
        "turn.end",
        "output.classified",
        "command.run",
        "judge.answer",
        "engine.task",
    }
    rows = until(
        lambda: (
            (r if required <= {x["pda.event.kind"] for x in r} else None)
            if (r := event_rows(wid))
            else None
        ),
        timeout=45,
    )
    save("normal-events.json", rows)
    assert all(
        row.get("pda.origin_cell") == "judge__1"
        for row in rows
        if row["pda.event.kind"] == "engine.task" and row["pda.cell_id"].startswith("c")
    )


def test_03_openobserve_sql(normal):
    wid, _ = normal
    env = dict(
        line.split("=", 1)
        for line in (ROOT / "deploy/.env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    sql = f"SELECT * FROM \"pda\" WHERE pda_job_id = '{wid}' LIMIT 100"

    def search():
        reply = httpx.post(
            "http://localhost:5080/api/default/_search",
            auth=(env["ZO_ROOT_USER_EMAIL"], env["ZO_ROOT_USER_PASSWORD"]),
            timeout=30,
            json={
                "query": {
                    "sql": sql,
                    "start_time": int((time.time() - 3600) * 1e6),
                    "end_time": int((time.time() + 60) * 1e6),
                    "from": 0,
                    "size": 100,
                }
            },
        )
        save(
            "openobserve-search.json",
            {"status": reply.status_code, "sql": sql, "response": reply.json()},
        )
        assert reply.is_success, reply.text
        return reply.json() if reply.json().get("hits") else None

    assert until(search, timeout=60)["hits"]


def test_04_invalid_output(engine):
    compose(
        "up",
        "-d",
        "--no-deps",
        "exec-fake-b",
        "exec-jev",
        env={"PDA_FIXTURE_EXECUTOR": "fake-b", "FAKE_B_MODE": "invalid"},
    )
    wid = start(engine)
    data = until(lambda: completed(engine, wid))
    save("invalid-workflow.json", data)
    cells = [t for t in data["tasks"] if t["taskDefName"] == "implement.fake-b"]
    assert len(cells) == 1 and cells[0]["status"] == "FAILED_WITH_TERMINAL_ERROR"
    rows = until(
        lambda: (
            (r if any(x["pda.event.kind"] == "output.rejected" for x in r) else None)
            if (r := event_rows(wid))
            else None
        ),
        timeout=30,
    )
    save("invalid-events.json", rows)


def test_05_response_timeout_retry(engine):
    original = engine.get("/metadata/taskdefs/implement.fake-b").json()
    timed = {**original, "responseTimeoutSeconds": 30, "retryCount": 1, "retryDelaySeconds": 1}
    reply = engine.put("/metadata/taskdefs", json=timed)
    assert reply.is_success, reply.text
    compose(
        "up",
        "-d",
        "--no-deps",
        "exec-fake-b",
        "exec-jev",
        env={
            "PDA_FIXTURE_EXECUTOR": "fake-b",
            "FAKE_B_MODE": "slow",
            "FAKE_SLEEP_SECONDS": "700",
            "FAKE_B_LEASE_EXTEND": "false",
        },
    )
    wid = start(engine)
    try:

        def retried():
            data = snapshot(engine, wid)
            cells = [t for t in data["tasks"] if t["taskDefName"] == "implement.fake-b"]
            return data if any(t["retryCount"] > 0 for t in cells) else None

        data = until(retried, timeout=180)
        save("timeout-scheduled-workflow.json", data)
        # A response timeout requeues work but does not stop a live runtime. Simulate recovery:
        # SIGTERM cancels the slow ACP session; the new worker receives the queued retry.
        compose(
            "up",
            "-d",
            "--no-deps",
            "exec-fake-b",
            env={"FAKE_B_MODE": "echo", "FAKE_B_LEASE_EXTEND": "true"},
        )
        data = until(lambda: completed(engine, wid), timeout=120)
        assert data["status"] == "COMPLETED", data.get("reasonForIncompletion")
        save("timeout-workflow.json", data)
        cells = [t for t in data["tasks"] if t["taskDefName"] == "implement.fake-b"]
        assert cells[0]["status"] == "TIMED_OUT"
        assert cells[0]["inputData"] == cells[1]["inputData"]
        assert cells[0]["reasonForIncompletion"]
        assert cells[1]["status"] == "COMPLETED" and cells[1]["retryCount"] == 1
        assert cells[1]["workerId"] == "fake-b" and cells[1]["startTime"] > 0

        def mirrored():
            rows = event_rows(wid)
            retries = any(int(r.get("pda.retry_count", 0)) > 0 for r in rows)
            reasons = any(r.get("pda.status") == "TIMED_OUT" and r.get("pda.reason") for r in rows)
            return rows if retries and reasons else None

        save("timeout-events.json", until(mirrored, timeout=30))
    finally:
        if snapshot(engine, wid)["status"] == "RUNNING":
            engine.delete("/workflow/" + wid, params={"reason": "e2e timeout evidence collected"})
        engine.put("/metadata/taskdefs", json=original).raise_for_status()


def test_06_docker_stats(engine):
    ids = compose("ps", "-q").split()
    result = subprocess.run(
        ["docker", "stats", "--no-stream", *ids],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    (EVIDENCE / "docker-stats.txt").write_text(result.stdout)
    assert "pda-increment-1" in result.stdout
