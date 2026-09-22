import asyncio
import hashlib
import os
import signal
import time
from collections.abc import Awaitable
from typing import Any

import httpx
from jsonschema import Draft7Validator, ValidationError

from pda_wrapper.classify import OutputRejected, classify
from pda_wrapper.drivers import RuntimeFailure, RuntimeOutput, acp, jev, tools
from pda_wrapper.events import Events, TaskEvents, configure_logging, json_text, log
from pda_wrapper.registry import Registry


def runtime_deadline(response_timeout: float) -> float:
    remaining = response_timeout - 10
    return remaining if remaining >= 10 else response_timeout / 2


class Worker:
    def __init__(
        self,
        registry: Registry,
        executor_id: str,
        client: httpx.AsyncClient,
        events: Events,
        workdir: str = "/work",
    ) -> None:
        self.registry = registry
        self.declaration = registry.executors[executor_id]
        self.executor_id = executor_id
        self.client = client
        self.events = events
        self.workdir = workdir
        self.stopping = asyncio.Event()
        self.names = [f"{name}.{executor_id}" for name in self.declaration["types"]]

    def stop(self) -> None:
        self.stopping.set()

    async def run(self) -> None:
        while not self.stopping.is_set():
            found = False
            for name in self.names:
                if self.stopping.is_set():
                    break
                try:
                    response = await self.client.get(
                        f"/api/tasks/poll/{name}", params={"workerid": self.executor_id}
                    )
                    response.raise_for_status()
                    task = (
                        response.json()
                        if response.status_code != 204 and response.content
                        else None
                    )
                except httpx.HTTPError as exc:
                    log("poll_failed", error=str(exc), executor_id=self.executor_id)
                    break
                if not task:
                    continue
                found = True
                result = await self.process(task)
                await self.deliver(result)
                break
            if not found and not self.stopping.is_set():
                try:
                    await asyncio.wait_for(self.stopping.wait(), 0.5)
                except TimeoutError:
                    pass

    async def deliver(self, result: dict) -> None:
        for attempt in range(3):
            try:
                response = await self.client.post("/api/tasks", json=result)
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                log("task_result_delivery_failed", task_id=result["taskId"], error=str(exc))
                if attempt < 2:
                    await asyncio.sleep(0.2)

    async def _runtime(self, awaitable: Awaitable[RuntimeOutput], deadline: float) -> RuntimeOutput:
        pending = asyncio.create_task(awaitable)
        stopped = asyncio.create_task(self.stopping.wait())
        try:
            done, _ = await asyncio.wait(
                {pending, stopped}, timeout=max(0, deadline), return_when=asyncio.FIRST_COMPLETED
            )
            if self.stopping.is_set() or pending not in done:
                reason = "interrupted" if self.stopping.is_set() else "runtime_deadline"
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                raise RuntimeFailure(reason)
            return await pending
        finally:
            stopped.cancel()
            await asyncio.gather(stopped, return_exceptions=True)
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

    def driver(
        self, definition: dict, data: dict, prompt: str, events: TaskEvents
    ) -> Awaitable[RuntimeOutput]:
        match definition["driver"]:
            case "acp":
                return acp.run(self.declaration, prompt, events, self.workdir)
            case "jev":
                return jev.run(self.registry, data, self.client, events)
            case "tools":
                return tools.run(definition["command"], data["input"], events, self.workdir)
            case _:
                raise ValueError("unknown_driver")

    async def process(self, task: dict) -> dict:
        started = time.monotonic()
        task_id, job_id = task["taskId"], task["workflowInstanceId"]
        type_name = task.get("taskDefName", task.get("taskType", "")).rpartition(".")[0]
        events = self.events.bind(
            job_id, task_id, task.get("referenceTaskName", ""), self.executor_id, type_name
        )
        span = events.span()
        result: dict[str, Any] = {
            "workflowInstanceId": job_id,
            "taskId": task_id,
            "workerId": self.executor_id,
            "outputData": {},
            "reasonForIncompletion": None,
        }
        attributes = {}
        if self.declaration["agent"] == "codex":
            attributes["pda.agent_mode"] = self.declaration["adapter"]["env"].get(
                "INITIAL_AGENT_MODE", os.environ.get("INITIAL_AGENT_MODE", "")
            )
        events.emit("job.received", **attributes)
        try:
            definition = self.registry.types[type_name]
            data = dict(task.get("inputData") or {})
            if data.get("context") is None:
                data["context"] = {}
            try:
                Draft7Validator(definition["input_schema"]).validate(data)
            except ValidationError:
                raise OutputRejected("input_schema_mismatch") from None
            prompt = (
                self.registry.prompt(data["prompt_ref"])
                + "\n"
                + json_text(
                    {
                        "input": data.get("input", data.get("initial_input")),
                        "context": data["context"],
                    }
                )
            )
            events.emit(
                "input.assembled",
                **{
                    "pda.prompt_id": data["prompt_ref"]["id"],
                    "pda.prompt_version": data["prompt_ref"]["version"],
                    "pda.input_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "pda.context_keys": sorted(data["context"]),
                },
            )
            if self.stopping.is_set():
                raise RuntimeFailure("interrupted")
            timeout = task.get(
                "responseTimeoutSeconds", definition["task_def"]["responseTimeoutSeconds"]
            )
            output = await self._runtime(
                self.driver(definition, data, prompt, events),
                runtime_deadline(timeout) - (time.monotonic() - started),
            )
            classified = classify(output.text, type_name, definition["driver"])
            classified["meta"] = {
                "executor_id": self.executor_id,
                "declaration_version": self.declaration["version"],
                "trace_id": f"{events.trace_id:032x}",
                "stop_reason": output.stop_reason,
            }
            try:
                Draft7Validator(definition["output_schema"]).validate(classified)
            except ValidationError:
                raise OutputRejected("output_schema_mismatch") from None
            events.emit(
                "output.classified",
                **{"pda.kind": classified["kind"], "pda.schema_id": f"{type_name}.output"},
            )
            summary = f"{classified['kind']} {json_text(classified['payload'])[:200]}"
            response = await self.client.post(f"/api/tasks/{task_id}/log", json=summary)
            response.raise_for_status()
            result.update(status="COMPLETED", outputData=classified)
        except OutputRejected as exc:
            events.emit("output.rejected", **{"pda.reason": str(exc)})
            result.update(status="FAILED_WITH_TERMINAL_ERROR", reasonForIncompletion=str(exc))
        except (RuntimeFailure, httpx.HTTPError) as exc:
            reason = str(exc) if isinstance(exc, RuntimeFailure) else "conductor_http_error"
            events.emit("unknown", **{"pda.raw": {"reason": reason, "error": str(exc)}})
            result.update(status="FAILED", reasonForIncompletion=reason)
        except Exception as exc:
            events.emit("unknown", **{"pda.raw": {"reason": "wrapper_error", "error": repr(exc)}})
            result.update(
                status="FAILED_WITH_TERMINAL_ERROR", reasonForIncompletion="wrapper_error"
            )
        finally:
            span.end()
        return result


async def main() -> None:
    configure_logging()
    registry = Registry(os.environ.get("PDA_REGISTRY_DIR", "registry"))
    events = Events(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
    events.start()
    try:
        async with httpx.AsyncClient(
            base_url=os.environ["CONDUCTOR_URL"].rstrip("/"), timeout=2
        ) as client:
            worker = Worker(registry, os.environ["PDA_EXECUTOR_ID"], client, events)
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGTERM, worker.stop)
            loop.add_signal_handler(signal.SIGINT, worker.stop)
            await worker.run()
    finally:
        await events.close()
