import contextlib
import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from pda_wrapper.events import json_text
from pda_wrapper.registry import Registry
from tools.generate_defs import generate, register

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/reports/evidence/increment-2"
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("PDA_E2E") != "1", reason="set PDA_E2E=1 for Docker Compose tests"
    ),
]
TASK_FIELDS = [
    "referenceTaskName",
    "taskDefName",
    "taskType",
    "status",
    "retryCount",
    "reasonForIncompletion",
    "responseTimeoutSeconds",
    "workerId",
    "iteration",
    "inputData",
    "outputData",
]


def save(name: str, value: Any) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / name
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    assert len(text.splitlines()) <= 300
    path.write_text(text.rstrip() + "\n")


def wait_for(check: Callable, timeout: float = 120) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(1)
    raise AssertionError(f"condition not met after {timeout}s")


class Harness:
    def __init__(self) -> None:
        self.env = {
            **os.environ,
            "JEV_MODE": "fixture",
            "PDA_FIXTURE_EXECUTOR": "",
            "PDA_FIXTURE_TYPE": "",
            "FAKE_B_MODE": "echo",
        }
        self.client = httpx.Client(base_url="http://localhost:8080", timeout=10)
        self.definitions = generate(Registry(ROOT / "registry"))
        self.jobs: list[str] = []
        self.first: dict = {}
        self.credentials = {}
        for line in (ROOT / "deploy/.env").read_text().splitlines():
            key, _, value = line.partition("=")
            self.credentials[key] = value.strip().strip("\"'")

    def compose(self, *args: str) -> str:
        result = subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yaml", *args],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=240,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def workflow(self, job_id: str) -> dict:
        response = self.client.get(f"/api/workflow/{job_id}", params={"includeTasks": "true"})
        response.raise_for_status()
        return response.json()

    def start(self) -> str:
        response = self.client.post(
            "/api/workflow",
            json={"name": "pda_job", "version": 1, "input": {"initial_input": "README を要約せよ"}},
        )
        response.raise_for_status()
        job_id = response.text.strip('"')
        self.jobs.append(job_id)
        return job_id

    def complete(self, job_id: str, status: str = "COMPLETED") -> dict:
        def check() -> dict | None:
            workflow = self.workflow(job_id)
            if workflow["status"] == status:
                return workflow
            assert workflow["status"] not in {"FAILED", "TIMED_OUT", "TERMINATED"}, workflow
            return None

        return wait_for(check)

    def task(self, job_id: str, predicate: Callable, timeout: float = 120) -> dict:
        return wait_for(
            lambda: next((t for t in self.workflow(job_id)["tasks"] if predicate(t)), None), timeout
        )

    def excerpt(self, name: str, workflow: dict) -> None:
        value = {
            key: workflow.get(key) for key in ("workflowId", "status", "reasonForIncompletion")
        }
        tasks = [{key: task.get(key) for key in TASK_FIELDS} for task in workflow["tasks"]]
        text = json_text(value)[:-1] + ', "tasks": [\n'
        text += ",\n".join(json_text(task) for task in tasks) + "\n]}"
        json.loads(text)
        save(name, text)

    def events(self, job_id: str) -> list[dict]:
        destination = ROOT / "tmp/e2e-events.jsonl"
        self.compose("cp", "otel-collector:/var/lib/pda/events/events.jsonl", str(destination))
        events = []
        for line in destination.read_text().splitlines():
            packet = json.loads(line)
            for resource in packet.get("resourceLogs", []):
                for scope in resource.get("scopeLogs", []):
                    for record in scope.get("logRecords", []):
                        attributes = {
                            item["key"]: next(iter(item["value"].values()), None)
                            for item in record.get("attributes", [])
                        }
                        if attributes.get("pda.job_id") == job_id:
                            events.append(
                                {
                                    "trace_id": record.get("traceId"),
                                    "span_id": record.get("spanId"),
                                    "timestamp": record.get("timeUnixNano"),
                                    "body": record.get("body", {}).get("stringValue"),
                                    "attributes": attributes,
                                }
                            )
        return events

    def save_events(self, filename: str, job_id: str) -> list[dict]:
        records = self.events(job_id)
        save(filename, "\n".join(json_text(record) for record in records[:300]))
        return records

    def select_fake_b(self, mode: str) -> None:
        self.env.update(
            PDA_FIXTURE_EXECUTOR="fake-b", PDA_FIXTURE_TYPE="implement", FAKE_B_MODE=mode
        )
        self.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev", "exec-fake-b")

    def timeout_definition(self, seconds: int = 60) -> None:
        definition = next(
            t for t in self.definitions["taskDefs"] if t["name"] == "implement.fake-b"
        )
        self.client.put(
            "/api/metadata/taskdefs",
            json={
                **definition,
                "responseTimeoutSeconds": seconds,
                "retryCount": 1,
                "retryDelaySeconds": 1,
            },
        ).raise_for_status()
        time.sleep(2)

    def restore_definition(self) -> None:
        definition = next(
            t for t in self.definitions["taskDefs"] if t["name"] == "implement.fake-b"
        )
        self.client.put("/api/metadata/taskdefs", json=definition).raise_for_status()


@pytest.fixture(scope="module")
def harness():
    h = Harness()
    try:
        h.compose("up", "-d", "--build")
        register(h.client, h.definitions)
        register(h.client, h.definitions)
        save(
            "registration.json",
            {
                "task_definitions": 19,
                "workflow_definitions": 1,
                "consecutive_successful_registrations": 2,
            },
        )
        yield h
    finally:
        for job_id in h.jobs:
            with contextlib.suppress(httpx.HTTPError):
                if h.workflow(job_id)["status"] == "RUNNING":
                    h.client.delete(f"/api/workflow/{job_id}").raise_for_status()
        h.restore_definition()
        h.env.update(PDA_FIXTURE_EXECUTOR="", PDA_FIXTURE_TYPE="", FAKE_B_MODE="echo")
        h.compose("up", "-d", "--no-build", "exec-jev", "exec-fake-b")
        h.client.close()


def test_01_fixture_loop_and_input(harness) -> None:
    h = harness
    h.first = h.complete(h.start())
    h.excerpt("01-workflow.json", h.first)
    tasks = h.first["tasks"]
    judges = [t for t in tasks if t["taskDefName"] == "judge.jev"]
    assert [t["referenceTaskName"] for t in judges] == ["judge__1", "judge__2", "judge__3"]
    cells = {t["referenceTaskName"]: t for t in tasks if t["referenceTaskName"].startswith("c")}
    assert cells["c1__1"]["taskDefName"] == "break-down.fake-a"
    assert cells["c2__1"]["taskDefName"] == "verify.test.tools"
    assert cells["c1__2"]["taskDefName"] == "summarize.fake-a"
    expected = "\n".join(
        json_text(cells[ref]["outputData"]["payload"]) for ref in ["c1__1", "c2__1"]
    )
    assert cells["c1__2"]["inputData"]["input"] == expected


def test_02_event_stream_and_origin(harness) -> None:
    h = harness
    job_id = h.first["workflowId"]
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
        "engine.workflow",
    }

    def check() -> list[dict] | None:
        records = h.events(job_id)
        observed_cells = {
            record["attributes"]["pda.cell_id"]
            for record in records
            if record["body"] == "engine.task"
        }
        completed = any(
            record["body"] == "engine.workflow"
            and record["attributes"]["pda.status"] == "COMPLETED"
            for record in records
        )
        ready = (
            required <= {r["body"] for r in records}
            and {"c1__1", "c2__1", "c1__2"} <= observed_cells
            and completed
        )
        return records if ready else None

    records = wait_for(check, 20)
    h.save_events("02-events.jsonl", job_id)
    assert {r["trace_id"] for r in records} == {hashlib.sha256(job_id.encode()).hexdigest()[:32]}
    cells = [
        r
        for r in records
        if r["body"] == "engine.task" and r["attributes"]["pda.cell_id"].startswith("c")
    ]
    assert cells and all(r["attributes"]["pda.origin_cell"].startswith("judge__") for r in cells)


def test_03_openobserve_sql(harness) -> None:
    h = harness
    job_id = h.first["workflowId"]
    sql = f"SELECT * FROM pda_events WHERE pda_job_id = '{job_id}' ORDER BY _timestamp LIMIT 3"
    body = {
        "query": {
            "sql": sql,
            "start_time": int((time.time() - 3600) * 1e6),
            "end_time": int((time.time() + 60) * 1e6),
            "from": 0,
            "size": 3,
        }
    }

    def check() -> dict | None:
        response = httpx.post(
            "http://localhost:5080/api/default/_search",
            json=body,
            auth=(h.credentials["ZO_ROOT_USER_EMAIL"], h.credentials["ZO_ROOT_USER_PASSWORD"]),
            timeout=15,
        )
        if response.status_code != 200:
            save("03-search-error.json", {"status": response.status_code, "body": response.text})
            return None
        value = response.json()
        return value if value.get("hits") else None

    value = wait_for(check, 60)
    save("03-openobserve.json", {"sql": sql, "hits": value["hits"]})


def test_04_invalid_output(harness) -> None:
    h = harness
    h.select_fake_b("invalid")
    job_id = h.start()
    task = h.task(job_id, lambda t: t["status"] == "FAILED_WITH_TERMINAL_ERROR")
    assert task["reasonForIncompletion"] == "invalid_kind_or_missing_payload"
    h.excerpt("04-invalid-workflow.json", h.workflow(job_id))
    wait_for(lambda: any(r["body"] == "output.rejected" for r in h.events(job_id)), 20)
    h.save_events("04-invalid-events.jsonl", job_id)


def test_05_worker_disappears_and_retry(harness) -> None:
    h = harness
    h.timeout_definition()
    try:
        h.select_fake_b("slow")
        job_id = h.start()
        first = h.task(
            job_id,
            lambda t: t["taskDefName"] == "implement.fake-b" and t["status"] == "IN_PROGRESS",
        )
        h.compose("kill", "exec-fake-b")
        timed_out = h.task(
            job_id, lambda t: t["taskId"] == first["taskId"] and t["status"] == "TIMED_OUT", 180
        )
        assert "responseTimeout: 60" in timed_out["reasonForIncompletion"]
        h.env["FAKE_B_MODE"] = "echo"
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-fake-b")
        workflow = h.complete(job_id)
        attempts = [t for t in workflow["tasks"] if t["taskDefName"] == "implement.fake-b"]
        assert len(attempts) == 2
        assert attempts[0]["inputData"] == attempts[1]["inputData"]
        assert attempts[1]["retryCount"] == 1 and attempts[1]["status"] == "COMPLETED"
        h.excerpt("05-retry-workflow.json", workflow)

        def check() -> bool:
            records = h.events(job_id)
            engine = [r["attributes"] for r in records if r["body"] == "engine.task"]
            return any(int(r["pda.retry_count"]) == 1 for r in engine) and any(
                "responseTimeout: 60" in r["pda.reason"] for r in engine
            )

        wait_for(check, 20)
        h.save_events("05-retry-events.jsonl", job_id)
    finally:
        h.restore_definition()


def test_06_runtime_deadline(harness) -> None:
    h = harness
    h.timeout_definition()
    job_id = None
    try:
        h.select_fake_b("slow")
        job_id = h.start()
        first = h.task(
            job_id,
            lambda t: t["taskDefName"] == "implement.fake-b" and t["status"] == "IN_PROGRESS",
        )
        failed = h.task(
            job_id, lambda t: t["taskId"] == first["taskId"] and t["status"] == "FAILED", 80
        )
        assert failed["reasonForIncompletion"] == "runtime_deadline"
        elapsed = (failed["endTime"] - failed["startTime"]) / 1000
        assert 49 <= elapsed < 56
        h.excerpt("06-deadline-workflow.json", h.workflow(job_id))
        save(
            "06-deadline-timing.json", {"elapsed_seconds": elapsed, "response_timeout_seconds": 60}
        )
        wait_for(
            lambda: any(
                r["attributes"].get("pda.stop_reason") == "cancelled" for r in h.events(job_id)
            ),
            20,
        )
        h.save_events("06-deadline-events.jsonl", job_id)
    finally:
        if job_id:
            h.client.delete(f"/api/workflow/{job_id}").raise_for_status()
        h.restore_definition()


def test_07_workflow_schema(harness) -> None:
    h = harness
    response = h.client.post("/api/workflow", json={"name": "pda_job", "version": 1, "input": {}})
    save("07-schema-response.json", {"status": response.status_code, "body": response.text})
    if response.is_success:
        job_id = response.text.strip('"')
        h.jobs.append(job_id)
        workflow = wait_for(lambda: w if (w := h.workflow(job_id))["status"] != "RUNNING" else None)
        assert workflow["status"] != "COMPLETED"
        h.excerpt("07-schema-workflow.json", workflow)


def test_08_stats_and_network_isolation(harness) -> None:
    h = harness
    ids = h.compose("ps", "-q").split()
    result = subprocess.run(
        ["docker", "stats", "--no-stream", *ids], text=True, capture_output=True, check=True
    )
    save("08-docker-stats.txt", result.stdout)
    response = h.compose(
        "exec",
        "-T",
        "exec-fake-a",
        "python",
        "-c",
        "import socket,json; "
        "\ntry:\n socket.create_connection(('openobserve',5080),timeout=2); reachable=True"
        "\nexcept OSError:\n reachable=False"
        "\nprint(json.dumps({'openobserve_reachable':reachable})); assert not reachable",
    )
    save("08-isolation.json", response)
    ui_port = h.credentials.get("CONDUCTOR_UI_PORT", "5000")
    assert httpx.get(f"http://localhost:{ui_port}/").status_code == 200
    assert httpx.get(f"http://localhost:{ui_port}/api/metadata/taskdefs").status_code == 200
