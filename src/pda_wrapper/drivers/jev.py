import copy
import json
import os
import time
from pathlib import Path

import httpx

from pda_wrapper.drivers import RuntimeFailure, RuntimeOutput
from pda_wrapper.events import TaskEvents, json_text
from pda_wrapper.history import previous_outputs
from pda_wrapper.registry import Registry

ENDPOINT = "https://api.typesafe.ai/v1/systemone"


def api_key(path: Path = Path("/secrets/typesafe_credentials")) -> str:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    if path.is_file():
        for line in path.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "API_KEY":
                return value.strip().strip("\"'")
    raise RuntimeFailure("jev_missing_api_key")


def build_state(workflow: dict, registry: Registry, initial_input: str | None = None) -> dict:
    _, outputs = previous_outputs(workflow)
    data = workflow.get("input", {})
    return {
        "initial_input": data.get("initial_input", "") if initial_input is None else initial_input,
        "context": data.get("context") or {},
        "previous_outputs": outputs,
        "executors": list(registry.executors.values()),
        "types": list(registry.types),
    }


def valid_polldata(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(row, dict)
        and isinstance(row.get("queueName"), str)
        and isinstance(row.get("workerId"), str)
        and isinstance(row.get("lastPollTime"), (int, float))
        for row in value
    )


async def available_executors(client: httpx.AsyncClient, registry: Registry) -> list[str]:
    response = await client.get("/api/tasks/queue/polldata/all")
    rows = None
    if response.status_code != 404:
        response.raise_for_status()
        try:
            rows = response.json()
        except ValueError:
            pass
    if not valid_polldata(rows):
        rows = []
        for executor, declaration in registry.executors.items():
            for type_name in declaration["types"]:
                result = await client.get(
                    "/api/tasks/queue/polldata", params={"taskType": f"{type_name}.{executor}"}
                )
                result.raise_for_status()
                records = result.json()
                if not valid_polldata(records):
                    raise RuntimeFailure("invalid_polldata")
                rows.extend(records)
    now = time.time() * 1000
    queues = {
        row["queueName"]
        for row in rows
        if row["workerId"] and 0 <= now - row["lastPollTime"] <= 60000
    }
    return [
        executor
        for executor, declaration in registry.executors.items()
        if any(f"{name}.{executor}" in queues for name in declaration["types"])
    ]


async def live_answers(
    state: dict,
    registry: Registry,
    client: httpx.AsyncClient,
    credentials: Path = Path("/secrets/typesafe_credentials"),
) -> dict:
    response = await client.post(
        ENDPOINT,
        json={
            "state": state,
            "model": registry.questions["model"],
            "questions": registry.questions["questions"],
        },
        headers={
            "Authorization": f"Bearer {api_key(credentials)}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    return response.json()["answers"]


def substitute(
    cells: list[dict],
    available: list[str],
    registry: Registry,
    events: TaskEvents,
) -> tuple[list[dict], bool]:
    cells = copy.deepcopy(cells)
    for cell in cells:
        original = cell["executor"]
        candidates = [
            executor
            for executor, declaration in registry.executors.items()
            if executor in available and cell["type"] in declaration["types"]
        ]
        if original in candidates:
            continue
        if not candidates:
            events.emit(
                "judge.answer",
                **{"pda.question_id": "next_type", "pda.answer": "finish:no_available_executor"},
            )
            return [], True
        cell["executor"] = candidates[0]
        events.emit(
            "judge.answer",
            **{
                "pda.question_id": "executor",
                "pda.answer": f"substituted:{original}->{candidates[0]}",
            },
        )
    return cells, False


def fixture(registry: Registry, rounds: int) -> dict:
    item = copy.deepcopy(registry.fixture[min(rounds, len(registry.fixture) - 1)])
    executor = os.environ.get("PDA_FIXTURE_EXECUTOR")
    type_name = os.environ.get("PDA_FIXTURE_TYPE")
    if executor and type_name:
        item = copy.deepcopy(registry.fixture[0 if rounds == 0 else 2])
        if rounds == 0:
            item["cells"] = [{"type": type_name, "executor": executor, "input_from": "initial"}]
            item["answers"]["next_type"]["choice"] = type_name
            item["answers"]["executor"]["choice"] = executor
            item["answers"]["cell_count"]["choice"] = "1"
    return item


def flow_payload(
    cells: list[dict], then: str, data: dict, outputs: list[dict], registry: Registry
) -> dict:
    tasks, inputs = [], {}
    previous = "\n".join(json_text(output["payload"]) for output in outputs)
    for number, cell in enumerate(cells, start=1):
        type_name, executor = cell["type"], cell["executor"]
        if (
            type_name not in registry.types
            or executor not in registry.executors
            or type_name not in registry.executors[executor]["types"]
        ):
            raise RuntimeFailure("judge_selected_unsupported_pair")
        reference = f"c{number}"
        tasks.append(
            {"name": f"{type_name}.{executor}", "taskReferenceName": reference, "type": "SIMPLE"}
        )
        inputs[reference] = {
            "job_id": data["job_id"],
            "workdir": f"/work/jobs/{data['job_id']}",
            "cell_id": reference,
            "type": type_name,
            "prompt_ref": {"id": type_name, "version": 1},
            "input": previous if cell["input_from"] == "previous" else data["initial_input"],
            "context": data.get("context") or {},
        }
    return {"then": then, "cells": cells, "dynamicTasks": tasks, "dynamicTasksInput": inputs}


async def run(
    registry: Registry,
    data: dict,
    conductor: httpx.AsyncClient,
    events: TaskEvents,
    api_client: httpx.AsyncClient | None = None,
) -> RuntimeOutput:
    response = await conductor.get(
        f"/api/workflow/{data['job_id']}", params={"includeTasks": "true"}
    )
    response.raise_for_status()
    rounds, outputs = previous_outputs(response.json())
    if rounds >= int(
        os.environ.get("PDA_MAX_ROUNDS") or registry.questions["limits"]["max_rounds"]
    ):
        events.emit(
            "judge.answer",
            **{"pda.question_id": "next_type", "pda.answer": "finish:round_limit"},
        )
        return RuntimeOutput(
            json_text(
                {"kind": "flow", "payload": flow_payload([], "finish", data, outputs, registry)}
            )
        )
    state = build_state(response.json(), registry, data["initial_input"])
    state["context"] = data.get("context") or {}
    state["available_executors"] = await available_executors(conductor, registry)
    events.emit(
        "input.assembled",
        **{
            "pda.input_kind": "judge_state",
            "pda.rounds": rounds,
            "pda.previous_outputs": len(outputs),
            "pda.available_executors": state["available_executors"],
        },
    )
    if os.environ.get("JEV_MODE", "fixture") == "fixture":
        item = fixture(registry, rounds)
        answers, cells, then = item["answers"], item["cells"], item["then"]
    else:
        try:
            if api_client:
                answers = await live_answers(state, registry, api_client)
            else:
                async with httpx.AsyncClient(timeout=120) as client:
                    answers = await live_answers(state, registry, client)
            finished = (
                answers["is_complete"]["noul"] >= registry.questions["thresholds"]["is_complete"]
                or answers["next_type"]["choice"] == "none"
            )
            then = "finish" if finished else "continue"
            count = int(answers["cell_count"]["choice"])
            if count not in {1, 2, 3}:
                raise ValueError("invalid_cell_count")
            cells = (
                []
                if finished
                else [
                    {
                        "type": answers["next_type"]["choice"],
                        "executor": answers["executor"]["choice"],
                        "input_from": "previous" if rounds else "initial",
                    }
                    for _ in range(count)
                ]
            )
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise RuntimeFailure("jev_invalid_response") from exc
    for question_id, answer in answers.items():
        attributes = {
            "pda.question_id": question_id,
            "pda.answer": str(answer.get("choice", answer.get("noul"))),
        }
        if "choice" in answer:
            attributes["pda.confidence"] = answer.get("confidence", 0.0)
        events.emit("judge.answer", **attributes)
    cells, no_candidates = substitute(cells, state["available_executors"], registry, events)
    if no_candidates:
        then = "finish"
    if then == "continue" and not cells:
        then = "finish"
        events.emit(
            "judge.answer", **{"pda.question_id": "next_type", "pda.answer": "finish:empty_cells"}
        )
    return RuntimeOutput(
        json.dumps(
            {"kind": "flow", "payload": flow_payload(cells, then, data, outputs, registry)},
            ensure_ascii=False,
        )
    )
