import argparse
import copy
import json
from pathlib import Path

import httpx

from pda_wrapper.registry import Registry


def schema_def(name: str, data: dict) -> dict:
    return {"name": name, "version": 1, "type": "JSON", "data": data}


def generate(registry: Registry) -> dict:
    tasks = []
    for executor in registry.executors.values():
        for name in executor["types"]:
            definition = registry.types[name]
            tasks.append(
                {
                    "name": f"{name}.{executor['executor_id']}",
                    **definition["task_def"],
                    "inputSchema": schema_def(f"{name}.input", definition["input_schema"]),
                    "outputSchema": schema_def(f"{name}.output", definition["output_schema"]),
                    "enforceSchema": True,
                }
            )
    workflow = copy.deepcopy(registry.workflow)
    workflow["inputSchema"] = schema_def(
        "pda_job.input",
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["initial_input"],
            "properties": {"initial_input": {"type": "string"}, "context": {"type": "object"}},
            "additionalProperties": False,
        },
    )
    workflow["enforceSchema"] = True
    return {"taskDefs": tasks, "workflowDefs": [workflow]}


def register(client: httpx.Client, definitions: dict) -> None:
    response = client.get("/api/metadata/taskdefs")
    response.raise_for_status()
    existing = {task["name"] for task in response.json()}
    new = []
    for task in definitions["taskDefs"]:
        if task["name"] in existing:
            client.put("/api/metadata/taskdefs", json=task).raise_for_status()
        else:
            new.append(task)
    if new:
        client.post("/api/metadata/taskdefs", json=new).raise_for_status()
    response = client.get("/api/metadata/workflow")
    response.raise_for_status()
    existing_workflows = {(item["name"], item["version"]) for item in response.json()}
    for workflow in definitions["workflowDefs"]:
        if (workflow["name"], workflow["version"]) in existing_workflows:
            client.put("/api/metadata/workflow", json=[workflow]).raise_for_status()
        else:
            client.post("/api/metadata/workflow", json=workflow).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conductor", default="http://localhost:8080")
    parser.add_argument("--registry", type=Path, default=Path("registry"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    definitions = generate(Registry(args.registry))
    if args.dry_run:
        print(json.dumps(definitions, ensure_ascii=False, indent=2))
    else:
        with httpx.Client(base_url=args.conductor.rstrip("/"), timeout=30) as client:
            register(client, definitions)
        print(json.dumps({"taskDefs": len(definitions["taskDefs"]), "workflowDefs": 1}))


if __name__ == "__main__":
    main()
