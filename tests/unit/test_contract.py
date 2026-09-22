import asyncio
import copy
import hashlib
import json

import pytest
from conductor.client.worker.exception import NonRetryableException

from pda_wrapper.classify import OutputRejected, classify, validate_output
from pda_wrapper.drivers import RuntimeFailure
from pda_wrapper.events import identifiers, map_update, raw_json
from pda_wrapper.worker import execute
from tools.generate_defs import generate, register


@pytest.mark.parametrize(
    ("raw", "kind", "payload"),
    [
        ("plain text", "result", {"text": "plain text"}),
        ('{"a":1}', "result", {"a": 1}),
        ("[1,2]", "result", [1, 2]),
        ("null", "result", None),
        ("42", "result", 42),
        ('{"kind":"input","payload":{"a":1}}', "input", {"a": 1}),
        ('{"kind":"result","payload":"abc"}', "result", "abc"),
    ],
)
def test_classification(raw, kind, payload):
    assert classify(raw, "implement") == {"kind": kind, "payload": payload}


@pytest.mark.parametrize(
    "raw", ['{"kind":"bogus","payload":{}}', '{"kind":"result"}', '{"kind":"flow","payload":{}}']
)
def test_rejection(raw):
    with pytest.raises(OutputRejected):
        classify(raw, "implement")


@pytest.mark.parametrize("raw", ["plain", "{}", "null"])
def test_structured_drivers_do_not_silently_wrap(raw):
    with pytest.raises(OutputRejected):
        classify(raw, "judge", structured=True)


def test_invalid_flow_schema(registry):
    output = {
        "kind": "flow",
        "payload": {"then": "continue", "cells": [], "dynamicTasks": [], "dynamicTasksInput": {}},
        "meta": {
            "executor_id": "jev",
            "declaration_version": 1,
            "trace_id": "a" * 32,
            "stop_reason": "end_turn",
        },
    }
    with pytest.raises(OutputRejected):
        validate_output(output, registry.types["judge"]["output_schema"])


def test_prompt_version(registry):
    with pytest.raises(ValueError):
        registry.prompt({"id": "../secrets", "version": 1}, "implement")


def test_deterministic_ids():
    trace, span = identifiers("job", "task")
    assert f"{trace:032x}" == hashlib.sha256(b"job").hexdigest()[:32]
    assert f"{span:016x}" == hashlib.sha256(b"task").hexdigest()[:16]


@pytest.mark.parametrize(
    ("update", "kind"),
    [
        ({"sessionUpdate": "agent_message_chunk", "content": {"text": "日本語"}}, "message.output"),
        ({"sessionUpdate": "agent_thought_chunk"}, "reasoning"),
        ({"sessionUpdate": "tool_call", "toolCallId": "x"}, "tool.call"),
        ({"sessionUpdate": "tool_call_update", "toolCallId": "x"}, "tool.result"),
        ({"sessionUpdate": "plan", "entries": [{}, {}]}, "plan"),
        ({"sessionUpdate": "usage_update", "inputTokens": 9, "outputTokens": 2}, "usage"),
        ({"sessionUpdate": "usage_update", "used": 10, "size": 100}, "unknown"),
        ({"sessionUpdate": "future_kind"}, "unknown"),
    ],
)
def test_event_mapping(update, kind):
    actual, attrs = map_update(update)
    assert actual == kind
    if kind == "message.output":
        assert attrs["pda.chars"] == 3


def test_unknown_is_bounded_bytes():
    assert len(raw_json({"x": "日" * 15000}).encode()) <= 10240


def test_definitions(registry):
    tasks, wf = generate(registry.root)
    assert len(tasks) == 19
    assert all(t["enforceSchema"] and t["inputSchema"]["type"] == "JSON" for t in tasks)
    judge = wf["tasks"][0]["loopOver"][0]
    assert "input" not in judge["inputParameters"]
    assert judge["inputParameters"]["job_id"] == "${workflow.workflowId}"
    assert "initial_input" in wf["inputSchema"]["data"]["required"]


def test_idempotent_registration(registry):
    import httpx

    saved = {}
    writes = []

    def handler(request):
        path = request.url.path
        if request.method == "GET":
            return httpx.Response(200 if path in saved else 404, json={})
        value = json.loads(request.content)
        for item in value if isinstance(value, list) else [value]:
            saved[path + "/" + item["name"]] = item
        writes.append(request.method)
        return httpx.Response(200, json={})

    with httpx.Client(base_url="http://engine/api", transport=httpx.MockTransport(handler)) as c:
        tasks, wf = generate(registry.root)
        register(c, tasks, wf)
        register(c, tasks, wf)
    assert writes[:20] == ["POST"] * 20
    assert writes[20:] == ["PUT"] * 20


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (RuntimeFailure("adapter unavailable"), RuntimeFailure),
        (TypeError("bug"), NonRetryableException),
    ],
)
def test_failure_boundary(monkeypatch, registry, events, failure, expected):
    from pda_wrapper.drivers import acp

    async def fail(*args):
        raise failure

    monkeypatch.setattr(acp, "run", fail)
    inp = {
        "job_id": "j",
        "cell_id": "c1",
        "type": "implement",
        "prompt_ref": {"id": "implement", "version": 1},
        "input": "x",
        "context": {},
    }
    with pytest.raises(expected):
        asyncio.run(execute(inp, {}, registry, registry.executors["fake-a"], events))
    assert events.records[-1][0] == "unknown"


def test_invalid_output_terminal(monkeypatch, registry, events):
    from pda_wrapper.drivers import acp

    async def invalid(*args):
        return '{"kind":"bogus","payload":{}}', "end_turn"

    monkeypatch.setattr(acp, "run", invalid)
    inp = {
        "job_id": "j",
        "cell_id": "c1",
        "type": "implement",
        "prompt_ref": {"id": "implement", "version": 1},
        "input": "x",
        "context": {},
    }
    with pytest.raises(NonRetryableException):
        asyncio.run(execute(inp, {}, registry, registry.executors["fake-a"], events))
    assert events.records[-1][0] == "output.rejected"
    assembled = dict(events.records)["input.assembled"]
    assert "x" not in assembled.values()
    assert len(assembled["pda.input_sha256"]) == 64


def test_registry_schemas_are_valid(registry):
    from jsonschema import Draft7Validator

    for type_def in registry.types.values():
        Draft7Validator.check_schema(type_def["input_schema"])
        Draft7Validator.check_schema(type_def["output_schema"])
    a, b = copy.deepcopy(registry.executors["fake-a"]), copy.deepcopy(registry.executors["fake-b"])
    for declaration in (a, b):
        declaration.pop("executor_id")
        declaration.pop("name")
    assert a == b
