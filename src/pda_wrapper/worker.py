"""Conductor SDK workers and the common executor contract."""

import asyncio
import hashlib
import os
import signal
import threading
from typing import Any

import httpx
from conductor.client.automator.task_handler import TaskHandler
from conductor.client.configuration.configuration import Configuration
from conductor.client.context import get_task_context
from conductor.client.worker.exception import NonRetryableException
from conductor.client.worker.worker_task import worker_task
from jsonschema import Draft7Validator

from pda_wrapper.classify import OutputRejected, classify, validate_output
from pda_wrapper.drivers import RuntimeFailure, acp, jev, tools
from pda_wrapper.events import Events, configure_logging, json_text, raw_json
from pda_wrapper.registry import Registry

_active: set[tuple] = set()
_active_lock = threading.Lock()


def cancel_active(signum: int, frame: Any) -> None:
    with _active_lock:
        for loop, task in _active:
            loop.call_soon_threadsafe(task.cancel)
    # SDK workers run forever. Give ACP cancellation/telemetry bounded time before exiting.
    threading.Timer(5, lambda: os._exit(128 + signum)).start()


# TaskHandler uses spawned workers; importing this module installs cancellation in each one.
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGTERM, cancel_active)
    configure_logging()


async def execute(
    task_input: dict, task: dict, registry: Registry, declaration: dict, events: Events
) -> dict:
    events.emit(
        "job.received",
        **(
            {"pda.agent_mode": declaration["adapter"]["env"].get("INITIAL_AGENT_MODE", "")}
            if declaration["agent"] == "codex"
            else {}
        ),
    )
    try:
        type_name = task_input["type"]
        type_def = registry.types[type_name]
        if type_name not in declaration["types"]:
            raise OutputRejected("type_not_declared")
        if next(Draft7Validator(type_def["input_schema"]).iter_errors(task_input), None):
            raise OutputRejected("input_schema_mismatch")
        prompt = registry.prompt(task_input["prompt_ref"], type_name)
        assembled = (
            prompt
            + "\n"
            + json_text(
                {
                    "input": task_input.get("input", task_input.get("initial_input")),
                    "context": task_input.get("context") or {},
                }
            )
        )
        events.emit(
            "input.assembled",
            **{
                "pda.prompt_id": task_input["prompt_ref"]["id"],
                "pda.prompt_version": task_input["prompt_ref"]["version"],
                "pda.input_sha256": hashlib.sha256(assembled.encode()).hexdigest(),
                "pda.context_keys": sorted((task_input.get("context") or {}).keys()),
            },
        )
        driver = type_def["driver"]
        if driver != declaration["runtime"]:
            raise OutputRejected("driver_runtime_mismatch")
        if driver == "acp":
            raw, stop = await acp.run(declaration, assembled, events)
        elif driver == "tools":
            raw, stop = await tools.run(type_def, task_input, events)
        else:
            url = os.getenv("CONDUCTOR_URL", "http://conductor-server:8080").rstrip("/")
            async with httpx.AsyncClient(base_url=url + "/api", timeout=30) as client:
                raw, stop = await jev.run(registry, task_input, events, client)
        output = classify(raw, type_name, structured=driver != "acp")
        output["meta"] = {
            "executor_id": declaration["executor_id"],
            "declaration_version": declaration["version"],
            "trace_id": f"{events.trace_id:032x}",
            "stop_reason": stop,
        }
        validate_output(output, type_def["output_schema"])
        events.emit(
            "output.classified",
            **{"pda.kind": output["kind"], "pda.schema_id": type_name + ".output"},
        )
        return output
    except OutputRejected as exc:
        events.emit("output.rejected", **{"pda.reason": str(exc)})
        raise NonRetryableException(str(exc)) from exc
    except (RuntimeFailure, TimeoutError, httpx.HTTPError) as exc:
        events.emit("unknown", **{"pda.raw": raw_json({"failure": "runtime", "reason": str(exc)})})
        raise RuntimeFailure(str(exc)) from exc
    except asyncio.CancelledError:
        events.emit("unknown", **{"pda.raw": raw_json({"failure": "cancelled"})})
        raise RuntimeFailure("task_cancelled") from None
    except Exception as exc:
        events.emit("unknown", **{"pda.raw": raw_json({"failure": "wrapper", "reason": repr(exc)})})
        raise NonRetryableException(f"wrapper_bug:{type(exc).__name__}:{exc}") from exc
    finally:
        events.close()


def execute_current() -> dict:
    context = get_task_context()
    registry = Registry(os.getenv("PDA_REGISTRY_DIR", "/registry"))
    declaration = registry.executors[os.environ["PDA_EXECUTOR_ID"]]
    inp = context.get_input()
    events = Events(
        inp.get("job_id", context.get_workflow_instance_id()),
        context.task.reference_task_name,
        context.get_task_id(),
        declaration["executor_id"],
        inp.get("type", "unknown"),
    )

    async def invoke() -> dict:
        active = (asyncio.get_running_loop(), asyncio.current_task())
        with _active_lock:
            _active.add(active)
        try:
            return await execute(inp, {}, registry, declaration, events)
        finally:
            with _active_lock:
                _active.remove(active)

    output = asyncio.run(invoke())
    context.add_log(output["kind"] + " " + json_text(output["payload"])[:200])
    return output


def main() -> None:
    registry = Registry(os.getenv("PDA_REGISTRY_DIR", "/registry"))
    eid = os.environ["PDA_EXECUTOR_ID"]
    for type_name in registry.executors[eid]["types"]:
        worker_task(
            f"{type_name}.{eid}", worker_id=eid, lease_extend_enabled=True, poll_interval_millis=500
        )(execute_current)
    config = Configuration(
        server_api_url=os.getenv("CONDUCTOR_URL", "http://conductor-server:8080").rstrip("/")
        + "/api"
    )
    handler = TaskHandler(configuration=config)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    handler.start_processes()
    try:
        stopped.wait()
    finally:
        handler.stop_processes()
