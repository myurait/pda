"""TypeSafe System One and deterministic conversion of its four answers."""

import json
import os
import re
from pathlib import Path

import httpx

from pda_wrapper.drivers import RuntimeFailure
from pda_wrapper.events import Events, json_text
from pda_wrapper.registry import Registry


def iteration(task: dict) -> int:
    suffix = re.search(r"__(\d+)$", task.get("referenceTaskName", ""))
    return int(suffix[1]) if suffix else int(task.get("iteration", 0) or 0)


def previous_outputs(workflow: dict) -> list[dict]:
    tasks = [
        t
        for t in workflow.get("tasks", [])
        if re.fullmatch(r"c\d+(?:__\d+)?", t.get("referenceTaskName", ""))
    ]
    if not tasks:
        return []
    latest = max(iteration(t) for t in tasks)
    # Each cell can have several retry task IDs; use the newest attempt of each cell.
    by_ref = {}
    for task in sorted(tasks, key=lambda t: (t.get("retryCount", 0), t.get("scheduledTime", 0))):
        if iteration(task) == latest:
            by_ref[task["referenceTaskName"]] = task
    outputs = []
    for ref, task in sorted(by_ref.items()):
        out = task.get("outputData", {})
        if task.get("status") != "COMPLETED" or "kind" not in out:
            continue
        inp = task.get("inputData", {})
        outputs.append(
            {
                "cell_id": ref,
                "type": inp.get("type"),
                "executor": out.get("meta", {}).get("executor_id"),
                "kind": out["kind"],
                "payload": out.get("payload"),
            }
        )
    return outputs


def api_key(path: Path = Path("/secrets/typesafe_credentials")) -> str:
    if key := os.getenv("TYPESAFE_API_KEY", "").strip():
        return key
    if path.is_file():
        for line in path.read_text().splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip() == "API_KEY":
                return value.strip().strip("'\"")
    raise RuntimeFailure("typesafe_api_key_missing")


def flow_payload(cells: list[dict], state: dict, registry: Registry, job_id: str) -> dict:
    tasks, inputs = [], {}
    for index, cell in enumerate(cells, 1):
        type_name, executor = cell["type"], cell["executor"]
        if (
            type_name == "judge"
            or type_name not in registry.types
            or executor not in registry.executors
            or type_name not in registry.executors[executor]["types"]
        ):
            raise RuntimeFailure("judge_selected_unsupported_type_executor")
        if cell["input_from"] not in ("initial", "previous"):
            raise RuntimeFailure("judge_invalid_input_from")
        ref = f"c{index}"
        tasks.append(
            {"name": f"{type_name}.{executor}", "taskReferenceName": ref, "type": "SIMPLE"}
        )
        value = (
            "\n".join(json_text(out["payload"]) for out in state["previous_outputs"])
            if cell["input_from"] == "previous"
            else state["initial_input"]
        )
        inputs[ref] = {
            "job_id": job_id,
            "cell_id": ref,
            "type": type_name,
            "prompt_ref": {"id": type_name, "version": 1},
            "input": value,
            "context": state["context"],
        }
    return {
        "then": "continue" if cells else "finish",
        "cells": cells,
        "dynamicTasks": tasks,
        "dynamicTasksInput": inputs,
    }


def cells_from_answers(answers: dict, threshold: float, previous: list[dict]) -> list[dict]:
    try:
        if (
            float(answers["is_complete"]["noul"]) >= threshold
            or answers["next_type"]["choice"] == "none"
        ):
            return []
        count = int(answers["cell_count"]["choice"])
        if count not in (1, 2, 3):
            raise ValueError("invalid cell_count")
        return [
            {
                "type": answers["next_type"]["choice"],
                "executor": answers["executor"]["choice"],
                "input_from": "previous" if previous else "initial",
            }
            for _ in range(count)
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeFailure("judge_invalid_answers") from exc


async def run(
    registry: Registry, task_input: dict, events: Events, client: httpx.AsyncClient
) -> tuple[str, str]:
    try:
        response = await client.get(
            "/workflow/" + task_input["job_id"], params={"includeTasks": "true"}
        )
        response.raise_for_status()
        state = {
            "initial_input": task_input["initial_input"],
            "context": task_input.get("context") or {},
            "previous_outputs": previous_outputs(response.json()),
            "executors": list(registry.executors.values()),
            "types": list(registry.types),
        }
        questions = json.loads((registry.root / "judge/questions.json").read_text())
        if os.getenv("JEV_MODE", "fixture") == "fixture":
            fixture = json.loads((registry.root / "judge/fixture.json").read_text())
            entry = fixture["subsequent" if state["previous_outputs"] else "initial"]
            answers = entry["answers"]
            cells = entry.get("cells")
            override = os.getenv("PDA_FIXTURE_EXECUTOR")
            if override and not state["previous_outputs"]:
                name = os.getenv("PDA_FIXTURE_TYPE", "implement")
                cells = [{"type": name, "executor": override, "input_from": "initial"}]
                answers = {
                    **answers,
                    "next_type": {"choice": name, "confidence": 1.0},
                    "executor": {"choice": override, "confidence": 1.0},
                    "cell_count": {"choice": "1", "confidence": 1.0},
                }
        else:
            # Ported from jev/lib/jev_api.py: endpoint, Bearer auth and exact request keys.
            async with httpx.AsyncClient(timeout=120) as api:
                reply = await api.post(
                    "https://api.typesafe.ai/v1/systemone",
                    headers={"Authorization": f"Bearer {api_key()}"},
                    json={
                        "state": state,
                        "model": questions["model"],
                        "questions": questions["questions"],
                    },
                )
                reply.raise_for_status()
                answers = reply.json()["answers"]
            cells = None
        for qid in questions["questions"]:
            answer = answers[qid]
            events.emit(
                "judge.answer",
                **{
                    "pda.question_id": qid,
                    "pda.choice": str(answer.get("choice", answer.get("noul"))),
                    "pda.confidence": float(answer.get("confidence", answer.get("noul", 0))),
                },
            )
        decided = cells_from_answers(
            answers, questions["thresholds"]["is_complete"], state["previous_outputs"]
        )
        if cells is None:
            cells = decided
        elif not cells and decided:
            events.emit(
                "judge.answer",
                **{
                    "pda.question_id": "next_type",
                    "pda.choice": "finish:empty_cells",
                    "pda.confidence": 1.0,
                },
            )
        # Even fixture overrides cannot continue after the explicit completion decision.
        if not decided:
            cells = []
        return json_text(
            {"kind": "flow", "payload": flow_payload(cells, state, registry, task_input["job_id"])}
        ), "end_turn"
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise RuntimeFailure(f"judge_runtime:{type(exc).__name__}") from exc
