"""Poll running workflows and record changes, including one final snapshot."""

import os
import signal
import threading
from typing import Any

import httpx

from pda_wrapper.drivers.jev import iteration
from pda_wrapper.events import Events, configure_logging, raw_json


def origins(tasks: list[dict]) -> dict[str, str]:
    result = {}
    for fork in tasks:
        if (
            fork.get("taskType") != "FORK_JOIN_DYNAMIC"
            and fork.get("workflowTask", {}).get("type") != "FORK_JOIN_DYNAMIC"
        ):
            continue
        dynamic = fork.get("inputData", {}).get("dynamicTasks", [])
        judges = [
            t
            for t in tasks
            if t.get("inputData", {}).get("type") == "judge"
            and iteration(t) == iteration(fork)
            and t.get("outputData", {}).get("payload", {}).get("dynamicTasks") == dynamic
            and t.get("seq", 0) < fork.get("seq", 0)
        ]
        origin = (
            max(judges, key=lambda t: t.get("seq", 0))["referenceTaskName"] if judges else "unknown"
        )
        for definition in dynamic:
            ref = definition["taskReferenceName"]
            for child in tasks:
                if child.get("referenceTaskName", "").split("__")[0] == ref.split("__")[
                    0
                ] and iteration(child) == iteration(fork):
                    result[child["taskId"]] = origin
    return result


class Mirror:
    def __init__(self) -> None:
        self.running: set[str] = set()
        self.workflows: dict[str, str] = {}
        self.tasks: dict[str, tuple] = {}

    def changes(self, workflow: dict) -> list[tuple[str, dict, dict]]:
        wid = workflow["workflowId"]
        job = workflow.get("correlationId") or wid
        changes = []
        if self.workflows.get(wid) != workflow["status"]:
            self.workflows[wid] = workflow["status"]
            changes.append(
                (
                    "engine.workflow",
                    {
                        "job_id": job,
                        "cell_id": "",
                        "task_id": wid,
                        "executor_id": "engine",
                        "type_name": "pda_job",
                    },
                    {
                        "pda.status": workflow["status"],
                        "pda.reason": workflow.get("reasonForIncompletion") or "",
                    },
                )
            )
        tasks = workflow.get("tasks", [])
        source = origins(tasks)
        for task in tasks:
            tid = task["taskId"]
            state = (task["status"], task.get("retryCount", 0))
            if self.tasks.get(tid) == state:
                continue
            self.tasks[tid] = state
            name = task.get("taskDefName", task.get("taskType", ""))
            attrs = {
                "pda.cell_id": task.get("referenceTaskName", ""),
                "pda.task_id": tid,
                "pda.status": state[0],
                "pda.retry_count": state[1],
                "pda.reason": task.get("reasonForIncompletion") or "",
                "pda.worker_id": task.get("workerId") or "",
                "pda.task_def_name": name,
            }
            if task.get("referenceTaskName", "").startswith("c"):
                attrs["pda.origin_cell"] = source.get(tid, "unknown")
            changes.append(
                (
                    "engine.task",
                    {
                        "job_id": job,
                        "cell_id": task.get("referenceTaskName", ""),
                        "task_id": tid,
                        "executor_id": name.rsplit(".", 1)[-1] if "." in name else "engine",
                        "type_name": task.get("inputData", {}).get(
                            "type", task.get("taskType", "")
                        ),
                    },
                    attrs,
                )
            )
        return changes

    def poll(self, client: httpx.Client) -> None:
        response = client.get("/workflow/running/pda_job")
        response.raise_for_status()
        running = set(response.json())
        read = running | self.running
        unresolved = set()
        for wid in sorted(read):
            try:
                response = client.get("/workflow/" + wid, params={"includeTasks": "true"})
                response.raise_for_status()
                for kind, base, attrs in self.changes(response.json()):
                    event = Events(**base, span=False)
                    event.emit(kind, **attrs)
                    event.close()
            except httpx.HTTPError:
                unresolved.add(wid)  # Preserve the final-read obligation until a successful read.
        self.running = running | unresolved


def main() -> None:
    configure_logging()
    mirror = Mirror()
    stop = threading.Event()

    def terminate(*args: Any) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    url = os.getenv("CONDUCTOR_URL", "http://conductor-server:8080").rstrip("/")
    with httpx.Client(base_url=url + "/api", timeout=10) as client:
        while not stop.is_set():
            try:
                mirror.poll(client)
            except httpx.HTTPError as exc:
                event = Events("", "", "", "engine", "", span=False)
                event.emit("unknown", **{"pda.raw": raw_json({"mirror_error": str(exc)})})
                event.close()
            stop.wait(3)


if __name__ == "__main__":
    main()
