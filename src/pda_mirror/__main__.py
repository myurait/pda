import asyncio
import os
import signal

import httpx

from pda_wrapper.events import Events, configure_logging, log
from pda_wrapper.history import CELL, origin_cell


class Mirror:
    def __init__(self, client: httpx.AsyncClient, events: Events) -> None:
        self.client = client
        self.events = events
        self.pending: set[str] = set()
        self.states: dict[str, dict] = {}

    async def poll(self) -> None:
        response = await self.client.get("/api/workflow/running/pda_job")
        response.raise_for_status()
        running = set(response.json())
        ids = running | self.pending
        self.pending |= running
        for job_id in sorted(ids):
            try:
                response = await self.client.get(
                    f"/api/workflow/{job_id}", params={"includeTasks": "true"}
                )
                response.raise_for_status()
                self.observe(job_id, response.json())
            except httpx.HTTPError as exc:
                log("mirror_read_failed", job_id=job_id, error=str(exc))
                continue
            if job_id not in running:
                self.pending.discard(job_id)
                self.states.pop(job_id, None)

    def observe(self, job_id: str, workflow: dict) -> None:
        state = self.states.setdefault(job_id, {"status": None, "tasks": {}})
        if state["status"] != workflow.get("status"):
            self.events.bind(job_id, job_id, "", "engine", "pda_job").emit(
                "engine.workflow",
                **{
                    "pda.status": workflow.get("status", ""),
                    "pda.reason": workflow.get("reasonForIncompletion") or "",
                },
            )
            state["status"] = workflow.get("status")
        for task in workflow.get("tasks", []):
            task_id = task["taskId"]
            current = (task.get("status"), task.get("retryCount", 0))
            if state["tasks"].get(task_id) == current:
                continue
            reference = task.get("referenceTaskName", "")
            name = task.get("taskDefName", "")
            type_name, separator, executor = name.rpartition(".")
            events = self.events.bind(
                job_id,
                task_id,
                reference,
                executor if separator else "engine",
                type_name if separator else task.get("taskType", ""),
            )
            attributes = {
                "pda.status": current[0],
                "pda.retry_count": current[1],
                "pda.reason": task.get("reasonForIncompletion") or "",
                "pda.worker_id": task.get("workerId") or "",
                "pda.task_def_name": name,
            }
            if CELL.fullmatch(reference):
                origin = origin_cell(task, workflow)
                attributes["pda.origin_cell"] = origin or "unknown"
                if origin is None:
                    events.emit("unknown", **{"pda.raw": task})
            events.emit("engine.task", **attributes)
            state["tasks"][task_id] = current


async def main() -> None:
    configure_logging()
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stopped.set)
    loop.add_signal_handler(signal.SIGINT, stopped.set)
    events = Events(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
    try:
        async with httpx.AsyncClient(base_url=os.environ["CONDUCTOR_URL"], timeout=5) as client:
            mirror = Mirror(client, events)
            while not stopped.is_set():
                try:
                    await mirror.poll()
                except httpx.HTTPError as exc:
                    log("mirror_poll_failed", error=str(exc))
                try:
                    await asyncio.wait_for(stopped.wait(), 3)
                except TimeoutError:
                    pass
    finally:
        await events.close()


if __name__ == "__main__":
    asyncio.run(main())
