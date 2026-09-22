import asyncio
import hashlib
import json

import pytest
from jsonschema import Draft7Validator, ValidationError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from pda_wrapper.classify import OutputRejected, classify
from pda_wrapper.events import KINDS, Events, identifiers


@pytest.mark.parametrize(
    ("raw", "kind", "payload"),
    [
        ('{"kind":"input","payload":{"a":1}}', "input", {"a": 1}),
        ('{"kind":"result","payload":null}', "result", None),
        ('{"a":1}', "result", {"a": 1}),
        ("[1,2]", "result", [1, 2]),
        ("42", "result", 42),
        ("true", "result", True),
        ("null", "result", None),
        ("plain text", "result", {"text": "plain text"}),
    ],
)
def test_classification(raw, kind, payload) -> None:
    assert classify(raw, "implement", "acp") == {"kind": kind, "payload": payload}


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ('{"kind":"flow","payload":{}}', "flow_from_non_judge"),
        ('{"kind":"bogus","payload":{}}', "invalid_kind_or_missing_payload"),
        ('{"kind":"input"}', "invalid_kind_or_missing_payload"),
    ],
)
def test_rejection(raw, reason) -> None:
    with pytest.raises(OutputRejected, match=reason):
        classify(raw, "implement", "acp")


@pytest.mark.parametrize("driver", ["jev", "tools"])
@pytest.mark.parametrize("raw", ['{"anything":1}', "not json", "[]"])
def test_strict_drivers(driver, raw) -> None:
    with pytest.raises(OutputRejected, match="invalid_kind_or_missing_payload"):
        classify(raw, "judge", driver)


def test_flow_schema(registry) -> None:
    value = classify(
        '{"kind":"flow","payload":{"then":"finish","cells":[], '
        '"dynamicTasks":[],"dynamicTasksInput":{}}}',
        "judge",
        "jev",
    )
    value["meta"] = {
        "executor_id": "jev",
        "declaration_version": 1,
        "trace_id": "0" * 32,
        "stop_reason": "end_turn",
    }
    validator = Draft7Validator(registry.types["judge"]["output_schema"])
    validator.validate(value)
    value["payload"]["then"] = "continue"
    with pytest.raises(ValidationError):
        validator.validate(value)
    value["payload"]["cells"] = [
        {"type": "implement", "executor": "fake-a", "input_from": "initial"}
    ]
    with pytest.raises(ValidationError):
        validator.validate(value)


def test_all_events_and_deterministic_ids(capsys) -> None:
    async def scenario() -> None:
        events = Events("http://unused")
        bound = events.bind("job", "task", "c1__1", "fake-a", "implement")
        span = bound.span()
        for kind in sorted(KINDS):
            bound.emit(kind)
        bound.emit("new.event", value="x")
        bound.emit("unknown", **{"pda.raw": "日" * 20000})
        span.end()
        packets = []
        while not events.queue.empty():
            kind, data = events.queue.get_nowait()
            packet = ExportLogsServiceRequest() if kind == "logs" else ExportTraceServiceRequest()
            packet.ParseFromString(data)
            packets.append((kind, packet))
        logs = [
            packet.resource_logs[0].scope_logs[0].log_records[0]
            for kind, packet in packets
            if kind == "logs"
        ]
        assert len(logs) == len(KINDS) + 2
        trace = [packet for kind, packet in packets if kind == "traces"][0]
        actual_span = trace.resource_spans[0].scope_spans[0].spans[0]
        assert actual_span.trace_id == logs[0].trace_id == hashlib.sha256(b"job").digest()[:16]
        assert actual_span.span_id == logs[0].span_id == hashlib.sha256(b"task").digest()[:8]
        events.provider.shutdown()
        events.traces.shutdown()

    asyncio.run(scenario())
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {line["body"] for line in lines} == KINDS
    assert lines[-2]["body"] == "unknown"
    assert len(lines[-1]["attributes"]["pda.raw"].encode()) <= 10240
    assert identifiers("job", "task") == identifiers("job", "task")
    assert all(len(line["attributes"]) >= 6 for line in lines)
