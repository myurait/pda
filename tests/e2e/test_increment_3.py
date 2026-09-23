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
from tools.generate_defs import generate

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/reports/evidence/increment-4"
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
            "PDA_MAX_ROUNDS": "",
        }
        self.client = httpx.Client(base_url="http://localhost:8080", timeout=10)
        self.definitions = generate(Registry(ROOT / "registry"))
        self.jobs: list[str] = []
        self.first: dict = {}
        self.real_results: dict = {}

    def compose(self, *args: str) -> str:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "deploy/docker-compose.yaml",
                "-f",
                "tests/e2e/compose.yaml",
                *args,
            ],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=240,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def register(self) -> None:
        result = self.compose(
            "run",
            "--rm",
            "--no-deps",
            "exec-tools",
            "python",
            "/app/tools/generate_defs.py",
            "--conductor",
            "http://conductor-server:8080",
            "--registry",
            "/registry",
        )
        assert '"workflowDefs": 1' in result

    def workflow(self, job_id: str) -> dict:
        response = self.client.get(f"/api/workflow/{job_id}", params={"includeTasks": "true"})
        response.raise_for_status()
        return response.json()

    def wait_executor(self, executor: str) -> None:
        import asyncio

        from pda_wrapper.drivers.jev import available_executors

        async def check() -> bool:
            async with httpx.AsyncClient(base_url="http://localhost:8080") as client:
                return executor in await available_executors(client, Registry(ROOT / "registry"))

        wait_for(lambda: asyncio.run(check()))

    def start(self, initial_input: str = "README を要約せよ") -> str:
        if executor := self.env.get("PDA_FIXTURE_EXECUTOR"):
            self.wait_executor(executor)
        response = self.client.post(
            "/api/workflow",
            json={"name": "pda_job", "version": 1, "input": {"initial_input": initial_input}},
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
            key: workflow.get(key)
            for key in ("workflowId", "status", "reasonForIncompletion", "input")
        }
        tasks = [{key: task.get(key) for key in TASK_FIELDS} for task in workflow["tasks"]]
        text = json_text(value)[:-1] + ', "tasks": [\n'
        text += ",\n".join(json_text(task) for task in tasks) + "\n]}"
        json.loads(text)
        save(name, text)

    def events(self, job_id: str) -> list[dict]:
        destination = ROOT / "tmp/e2e-events.jsonl"
        destination.parent.mkdir(exist_ok=True)
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
        h.compose("up", "-d", "--no-build")
        h.register()
        for executor in ["fake-a", "fake-b", "tools", "jev"]:
            h.wait_executor(executor)
        h.register()
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
    workdir = f"/work/jobs/{h.first['workflowId']}"
    assert all(t["inputData"]["workdir"] == workdir for t in cells.values())
    h.compose("exec", "-T", "exec-tools", "test", "-f", f"{workdir}/note.txt")
    records = wait_for(lambda: h.events(h.first["workflowId"]))
    commands = [r for r in records if r["body"] == "command.run"]
    assert commands and commands[0]["attributes"]["pda.workdir"] == workdir
    save("01-workdir.json", {"workdir": workdir, "note_exists": True})


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
    code = (
        "import asyncio,os; from pda_wrapper.events import Events; "
        "e=Events(os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']); "
        f"b=e.bind({job_id!r}, 'shutdown-probe', 'shutdown-probe', 'tools', 'verify.test'); "
        "s=b.span(); b.emit('turn.end', **{'pda.stop_reason':'shutdown_probe'}); "
        "s.end(); asyncio.run(e.close())"
    )
    h.compose("run", "--rm", "--no-deps", "exec-tools", "python", "-c", code)
    wait_for(
        lambda: any(r["attributes"]["pda.cell_id"] == "shutdown-probe" for r in h.events(job_id)),
        20,
    )
    h.save_events("02-events.jsonl", job_id)
    destination = ROOT / "tmp/e2e-traces.jsonl"
    h.compose("cp", "otel-collector:/var/lib/pda/events/traces.jsonl", str(destination))
    spans = []
    for line in destination.read_text().splitlines():
        packet = json.loads(line)
        assert "resourceLogs" not in packet
        for resource in packet.get("resourceSpans", []):
            for scope in resource.get("scopeSpans", []):
                spans.extend(
                    span
                    for span in scope.get("spans", [])
                    if span["traceId"] == hashlib.sha256(job_id.encode()).hexdigest()[:32]
                )
    assert any(span["name"] == "shutdown-probe" for span in spans)
    save("02-traces.jsonl", "\n".join(json_text(span) for span in spans))


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
        code = (
            "import os,json,urllib.request,base64; "
            "auth=base64.b64encode((os.environ['ZO_ROOT_USER_EMAIL']+':'"
            "+os.environ['ZO_ROOT_USER_PASSWORD']).encode()).decode(); "
            "req=urllib.request.Request('http://openobserve:5080/api/default/_search',"
            f"data={json.dumps(body).encode()!r},"
            "headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'}); "
            "print(urllib.request.urlopen(req).read().decode())"
        )
        value = json.loads(
            h.compose("run", "--rm", "--no-deps", "-T", "observe-query", "python", "-c", code)
        )
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
    uid = h.compose("exec", "-T", "exec-fake-a", "id", "-u").strip()
    assert uid == "1000"
    save("08-uid.json", {"uid": int(uid)})
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
    ui_port = h.compose("port", "conductor-ui", "5000").strip().rsplit(":", 1)[1]
    assert httpx.get(f"http://localhost:{ui_port}/").status_code == 200
    assert httpx.get(f"http://localhost:{ui_port}/api/metadata/taskdefs").status_code == 200


def test_09_add_executor_declaration(harness) -> None:
    h = harness
    path = ROOT / "registry/executors/fake-c.yaml"
    assert not path.exists()
    container = None
    before = {t["name"]: t for t in h.client.get("/api/metadata/taskdefs").json()}
    try:
        path.write_text(
            (ROOT / "registry/executors/fake-a.yaml")
            .read_text()
            .replace("executor_id: fake-a", "executor_id: fake-c")
            .replace("name: 試験用エージェント A", "name: 試験用エージェント C")
        )
        h.register()
        after = {t["name"]: t for t in h.client.get("/api/metadata/taskdefs").json()}
        added = set(after) - set(before)
        assert added == {
            f"{name}.fake-c" for name in ["break-down", "implement", "review", "summarize"]
        }
        # Conductor updates registration timestamps even when the definition is identical.
        metadata = {"createTime", "updateTime", "createdBy", "updatedBy"}
        assert {
            k: {a: b for a, b in v.items() if a not in metadata} for k, v in before.items()
        } == {k: {a: b for a, b in after[k].items() if a not in metadata} for k in before}
        h.env.update(PDA_FIXTURE_EXECUTOR="fake-c", PDA_FIXTURE_TYPE="implement")
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev")
        container = h.compose(
            "run", "--rm", "-d", "-e", "PDA_EXECUTOR_ID=fake-c", "exec-fake-a"
        ).strip()
        job_id = h.start()
        workflow = h.complete(job_id)
        assert any(
            t["taskDefName"] == "implement.fake-c" and t["status"] == "COMPLETED"
            for t in workflow["tasks"]
        )
        h.excerpt("09-workflow.json", workflow)
        h.save_events("09-events.jsonl", job_id)
        save(
            "09-definitions.json",
            {
                "added": sorted(added),
                "existing_definitions_equal": True,
                "excluded_metadata_fields": sorted(metadata),
            },
        )
    finally:
        if container:
            subprocess.run(["docker", "stop", container], check=True, capture_output=True)
        path.unlink(missing_ok=True)
        for name in ["break-down", "implement", "review", "summarize"]:
            response = h.client.delete(f"/api/metadata/taskdefs/{name}.fake-c")
            assert response.status_code in (200, 204, 404)
        h.env.update(PDA_FIXTURE_EXECUTOR="", PDA_FIXTURE_TYPE="")
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev")


REAL_INPUT = (
    "作業ディレクトリに hello.py を作り、実行すると hello と表示するようにせよ。"
    "作ったファイル名を報告せよ"
)


def run_real(h: Harness, executor: str, number: int) -> None:
    service = f"exec-{executor}"
    definition = next(t for t in h.definitions["taskDefs"] if t["name"] == f"implement.{executor}")
    job_id = None
    try:
        # A failed authentication must not start additional paid attempts.
        h.client.put(
            "/api/metadata/taskdefs", json={**definition, "retryCount": 0}
        ).raise_for_status()
        h.env.update(PDA_FIXTURE_EXECUTOR=executor, PDA_FIXTURE_TYPE="implement")
        h.compose("--profile", "real", "up", "-d", "--no-build", service)
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev")
        job_id = h.start(REAL_INPUT)
        workflow = wait_for(
            lambda: w if (w := h.workflow(job_id))["status"] != "RUNNING" else None, 660
        )
        h.excerpt(f"{number:02}-workflow.json", workflow)
        wait_for(
            lambda: any(
                r["body"] in {"output.classified", "unknown"}
                and r["attributes"]["pda.executor_id"] == executor
                for r in h.events(job_id)
            ),
            20,
        )
        records = h.save_events(f"{number:02}-events.jsonl", job_id)
        records = [r for r in records if r["attributes"]["pda.executor_id"] == executor]
        task = next(t for t in workflow["tasks"] if t["taskDefName"] == f"implement.{executor}")
        workdir = f"/work/jobs/{job_id}"
        check = json.loads(
            h.compose(
                "exec",
                "-T",
                "exec-tools",
                "python",
                "-c",
                f"import pathlib,json,subprocess; p=pathlib.Path({workdir!r})/'hello.py'; "
                "print(json.dumps({'exists':p.is_file(), 'output':"
                "subprocess.check_output(['python',str(p)],text=True).strip() "
                "if p.is_file() else None}))",
            )
        )
        result = {
            "executor": executor,
            "job_id": job_id,
            "status": workflow["status"],
            "task_status": task["status"],
            "workdir": workdir,
            "file": check,
            "agent_mode": [
                r["attributes"].get("pda.agent_mode")
                for r in records
                if r["body"] == "job.received"
            ],
            "permission_requests": sum(r["body"] == "permission.request" for r in records),
            "stop_reasons": [
                r["attributes"].get("pda.stop_reason") for r in records if r["body"] == "turn.end"
            ],
            "event_kinds": sorted({r["body"] for r in records}),
            "task_fields": sorted(task),
            "input_fields": sorted(task["inputData"]),
            "output_fields": sorted(task["outputData"]),
            "meta_fields": sorted(task["outputData"].get("meta", {})),
        }
        save(f"{number:02}-result.json", result)
        h.real_results[executor] = result
        assert workflow["status"] == "COMPLETED", result
        assert check == {"exists": True, "output": "hello"}
    finally:
        if job_id and h.workflow(job_id)["status"] == "RUNNING":
            h.client.delete(f"/api/workflow/{job_id}").raise_for_status()
        h.client.put("/api/metadata/taskdefs", json=definition).raise_for_status()
        h.compose("stop", service)
        h.env.update(PDA_FIXTURE_EXECUTOR="", PDA_FIXTURE_TYPE="")
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev")


def test_10_real_codex(harness) -> None:
    run_real(harness, "codex-personal", 10)


def test_11_real_claude(harness) -> None:
    run_real(harness, "claude-personal", 11)


def test_12_compare_executors(harness) -> None:
    results = harness.real_results
    assert set(results) == {"codex-personal", "claude-personal"}
    codex, claude = results["codex-personal"], results["claude-personal"]
    comparison = {}
    for field in ["event_kinds", "task_fields", "input_fields", "output_fields", "meta_fields"]:
        comparison[field] = {
            "codex_only": sorted(set(codex[field]) - set(claude[field])),
            "claude_only": sorted(set(claude[field]) - set(codex[field])),
        }
    save("12-comparison.json", comparison)
    assert codex["status"] == claude["status"] == "COMPLETED"
    assert all(
        not comparison[field][side]
        for field in ["task_fields", "input_fields", "output_fields", "meta_fields"]
        for side in ["codex_only", "claude_only"]
    )


def test_13_live_jev(harness) -> None:
    from jsonschema import Draft7Validator

    h = harness
    job_id = None
    try:
        for definition in h.definitions["taskDefs"]:
            h.client.put(
                "/api/metadata/taskdefs", json={**definition, "retryCount": 0}
            ).raise_for_status()
        h.env.update(
            JEV_MODE="live", PDA_MAX_ROUNDS="2", PDA_FIXTURE_EXECUTOR="", PDA_FIXTURE_TYPE=""
        )
        h.compose(
            "--profile",
            "real",
            "up",
            "-d",
            "--no-build",
            "exec-codex-personal",
            "exec-claude-personal",
        )
        for executor in ["codex-personal", "claude-personal"]:
            h.wait_executor(executor)
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev")
        job_id = h.start(REAL_INPUT)
        workflow = wait_for(
            lambda: w if (w := h.workflow(job_id))["status"] != "RUNNING" else None, 1500
        )
        h.excerpt("13-workflow.json", workflow)
        records = h.save_events("13-events.jsonl", job_id)
        judges = [t for t in workflow["tasks"] if t["taskDefName"] == "judge.jev"]
        cells = [t for t in workflow["tasks"] if t["referenceTaskName"].startswith("c")]
        save(
            "13-summary.json",
            {
                "job_id": job_id,
                "status": workflow["status"],
                "states": [r["attributes"] for r in records if r["body"] == "judge.state"],
                "answers": [r["attributes"] for r in records if r["body"] == "judge.answer"],
                "cells": [
                    {
                        "ref": t["referenceTaskName"],
                        "name": t["taskDefName"],
                        "status": t["status"],
                        "kind": t["outputData"].get("kind"),
                        "json_output": not (
                            isinstance(t["outputData"].get("payload"), dict)
                            and set(t["outputData"]["payload"]) == {"text"}
                        ),
                    }
                    for t in cells
                ],
            },
        )
        result = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "tools/judge_probe.py",
                "--job-id",
                job_id,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=150,
        )
        assert result.returncode == 0, result.stderr
        save("13-probe.json", json.loads(result.stdout))
        assert workflow["status"] in {"COMPLETED", "FAILED"}
        assert len(cells) <= 6 and all(t["retryCount"] == 0 for t in cells + judges)
        assert len({t["referenceTaskName"].rsplit("__", 1)[-1] for t in cells}) <= 2
        for judge in judges:
            assert judge["status"] == "COMPLETED"
            Draft7Validator(Registry(ROOT / "registry").types["judge"]["output_schema"]).validate(
                judge["outputData"]
            )
        actual = [
            r
            for r in records
            if r["body"] == "judge.answer"
            and r["attributes"].get("pda.question_id") == "is_complete"
        ]
        assert 1 <= len(actual) <= 2
        for record in actual:
            cell = record["attributes"]["pda.cell_id"]
            answers = [
                r["attributes"]
                for r in records
                if r["body"] == "judge.answer" and r["attributes"]["pda.cell_id"] == cell
            ]
            assert {"is_complete", "next_type", "executor", "cell_count"} <= {
                a["pda.question_id"] for a in answers
            }
    finally:
        if job_id and h.workflow(job_id)["status"] == "RUNNING":
            h.client.delete(f"/api/workflow/{job_id}").raise_for_status()
        for definition in h.definitions["taskDefs"]:
            h.client.put("/api/metadata/taskdefs", json=definition).raise_for_status()
        h.env.update(JEV_MODE="fixture", PDA_MAX_ROUNDS="")
        h.compose("up", "-d", "--no-build", "--force-recreate", "exec-jev")
        h.compose("--profile", "real", "stop", "exec-codex-personal", "exec-claude-personal")


def test_14_view(harness) -> None:
    h = harness
    job_id = h.first["workflowId"]
    with httpx.Client(base_url="http://localhost:5081", timeout=30) as client:

        def jobs_ready() -> list[dict] | None:
            response = client.get("/api/jobs")
            response.raise_for_status()
            jobs = response.json()
            return jobs if any(j["job_id"] == job_id for j in jobs) else None

        jobs = wait_for(jobs_ready)
        detail = client.get(f"/api/jobs/{job_id}").json()
        expected = sorted(
            [
                t
                for t in h.workflow(job_id)["tasks"]
                if t["referenceTaskName"].startswith(("c", "judge"))
            ],
            key=lambda t: t["seq"],
        )
        assert [(t["ref"], t["status"]) for t in detail["cells"]] == [
            (t["referenceTaskName"], t["status"]) for t in expected
        ]
        count = len((EVIDENCE / "02-events.jsonl").read_text().splitlines())
        events = wait_for(
            lambda: (
                rows
                if len(rows := client.get(f"/api/jobs/{job_id}/events").json()) >= count
                else None
            )
        )
        filtered = client.get(f"/api/jobs/{job_id}/events?cell=judge__1").json()
        assert filtered and all(row["cell"] == "judge__1" for row in filtered)
        for name, value in [("jobs", jobs), ("detail", detail), ("events", events)]:
            save(
                f"14-{name}.json",
                "\n".join(json.dumps(value, ensure_ascii=False, indent=2).splitlines()[:50]),
            )
        save(
            "14-checks.json",
            {
                "job_id": job_id,
                "events": len(events),
                "e2e_02_events": count,
                "judge_events": len(filtered),
                "cells_match": True,
            },
        )
        assert "<html" in client.get("/").text
        for path in ["/", "/static/app.js", "/static/app.css"]:
            assert client.get(path).status_code == 200
