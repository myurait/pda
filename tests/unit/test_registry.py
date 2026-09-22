import json
import re
import subprocess
import sys
from pathlib import Path

import httpx
import yaml
from jsonschema import Draft7Validator

from tools.generate_defs import generate, register

ROOT = Path(__file__).resolve().parents[2]


def test_registry_contract(registry) -> None:
    assert len(registry.types) == 7
    assert len(registry.executors) == 6
    assert len(registry.questions["questions"]) == 4
    assert len(registry.fixture) == 3
    for definition in registry.types.values():
        Draft7Validator.check_schema(definition["input_schema"])
        Draft7Validator.check_schema(definition["output_schema"])
        assert (registry.directory / definition["prompt"]).is_file()
    instruction = (ROOT / "docs/codex-runs/2026-09-22-increment-2.md").read_text()
    section = instruction.split("## 5. 雛形ワークフロー")[1]
    assert registry.workflow == json.loads(re.search(r"```json\n(.*?)\n```", section, re.S)[1])
    assert all(
        json.dumps(question, ensure_ascii=False).isascii()
        for question in registry.questions["questions"].values()
    )


def test_generated_schema_and_idempotent_registration(registry) -> None:
    definitions = generate(registry)
    assert len(definitions["taskDefs"]) == 19
    assert len(definitions["workflowDefs"]) == 1
    for task in definitions["taskDefs"]:
        assert task["enforceSchema"] is True
        assert task["inputSchema"]["type"] == "JSON"
        assert task["outputSchema"]["version"] == 1
    stored_tasks, stored_workflows = {}, {}

    def request(req: httpx.Request) -> httpx.Response:
        workflows = req.url.path.endswith("workflow")
        store = stored_workflows if workflows else stored_tasks
        if req.method == "GET":
            return httpx.Response(200, json=list(store.values()))
        body = json.loads(req.content)
        items = body if isinstance(body, list) else [body]
        for item in items:
            if req.method == "POST":
                assert item["name"] not in store
            else:
                assert item["name"] in store
            store[item["name"]] = item
        return httpx.Response(200)

    with httpx.Client(
        base_url="http://conductor", transport=httpx.MockTransport(request)
    ) as client:
        register(client, definitions)
        register(client, definitions)
    assert len(stored_tasks) == 19 and len(stored_workflows) == 1


def test_dry_run_without_server() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/generate_defs.py",
            "--dry-run",
            "--conductor",
            "http://127.0.0.1:1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert len(json.loads(result.stdout)["taskDefs"]) == 19


def test_compose_networks_and_ports() -> None:
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    assert compose["name"] == "pda-increment-2"
    published = {name for name, service in compose["services"].items() if service.get("ports")}
    assert published == {"conductor-server", "conductor-ui", "openobserve"}
    for name, service in compose["services"].items():
        if not name.startswith("exec-"):
            continue
        executor = name.removeprefix("exec-")
        assert service["init"] is True and service["stop_grace_period"] == "20s"
        assert compose["networks"][executor]["internal"] is True
        members = {n for n, s in compose["services"].items() if executor in s["networks"]}
        assert members == {name, "conductor-server", "otel-collector"}
        assert all("." not in key for key in service["environment"])
    for name in ("codex-personal", "claude-company"):
        assert compose["services"][f"exec-{name}"]["profiles"] == ["real"]
