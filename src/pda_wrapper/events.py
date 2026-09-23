import asyncio
import hashlib
import json
import logging
import threading
import time
from contextvars import ContextVar
from typing import Any

from opentelemetry._logs import LogRecord
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.trace import Span, TraceFlags

KINDS = frozenset(
    {
        "job.received",
        "input.assembled",
        "message.output",
        "reasoning",
        "tool.call",
        "tool.result",
        "plan",
        "permission.request",
        "permission.response",
        "usage",
        "turn.end",
        "output.classified",
        "output.rejected",
        "command.run",
        "judge.answer",
        "engine.workflow",
        "engine.task",
        "unknown",
    }
)
_ids: ContextVar[tuple[int, int]] = ContextVar("pda_ids")


def identifiers(job_id: str, task_id: str) -> tuple[int, int]:
    return (
        int.from_bytes(hashlib.sha256(job_id.encode()).digest()[:16]),
        int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8]),
    )


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def raw_text(value: Any) -> str:
    return json_text(value).encode()[:10240].decode(errors="ignore")


def log(message: str, **fields: Any) -> None:
    print(json_text({"message": message, **fields}), flush=True)


class JsonLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        log(record.getMessage(), logger=record.name, level=record.levelname)


def configure_logging() -> None:
    logging.basicConfig(handlers=[JsonLogHandler()], level=logging.WARNING, force=True)


class DeterministicIds(IdGenerator):
    def generate_trace_id(self) -> int:
        return _ids.get()[0]

    def generate_span_id(self) -> int:
        return _ids.get()[1]


class Events:
    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint
        resource = Resource.create({"service.name": "pda"})
        self.provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
        self.traces = TracerProvider(
            resource=resource, id_generator=DeterministicIds(), shutdown_on_exit=False
        )
        if endpoint:
            self.provider.add_log_record_processor(
                BatchLogRecordProcessor(
                    OTLPLogExporter(endpoint=f"{endpoint.rstrip('/')}/v1/logs", timeout=2)
                )
            )
            self.traces.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces", timeout=2)
                )
            )
        self.logger = self.provider.get_logger("pda")
        self.tracer = self.traces.get_tracer("pda")

    def _flush(self) -> None:
        deadline = time.monotonic() + 4
        logs = self.provider.force_flush(timeout_millis=4000)
        traces = self.traces.force_flush(
            timeout_millis=max(1, int((deadline - time.monotonic()) * 1000))
        )
        if not logs or not traces:
            log("otlp_flush_timeout")

    async def force_flush(self) -> None:
        await asyncio.to_thread(self._flush)

    def bind(
        self, job_id: str, task_id: str, cell_id: str, executor_id: str, type_name: str
    ) -> "TaskEvents":
        return TaskEvents(self, job_id, task_id, cell_id, executor_id, type_name)

    async def close(self) -> None:
        done = threading.Event()

        def shutdown() -> None:
            try:
                self._flush()
                self.provider.shutdown()
                self.traces.shutdown()
            finally:
                done.set()

        threading.Thread(target=shutdown, daemon=True).start()
        if not await asyncio.to_thread(done.wait, 5):
            log("otlp_shutdown_timeout")


class TaskEvents:
    def __init__(
        self,
        events: Events,
        job_id: str,
        task_id: str,
        cell_id: str,
        executor_id: str,
        type_name: str,
    ) -> None:
        self.events = events
        self.trace_id, self.span_id = identifiers(job_id, task_id)
        self.attributes = {
            "pda.job_id": job_id,
            "pda.cell_id": cell_id,
            "pda.task_id": task_id,
            "pda.executor_id": executor_id,
            "pda.type": type_name,
        }

    def span(self) -> Span:
        token = _ids.set((self.trace_id, self.span_id))
        try:
            return self.events.tracer.start_span(
                self.attributes["pda.cell_id"], context=Context(), attributes=self.attributes
            )
        finally:
            _ids.reset(token)

    def emit(self, kind: str, **attributes: Any) -> None:
        if kind not in KINDS:
            attributes = {"pda.raw": {"kind": kind, "attributes": attributes}}
            kind = "unknown"
        if kind == "unknown":
            attributes = {"pda.raw": raw_text(attributes.get("pda.raw", attributes))}
        attrs = {**self.attributes, "pda.event.kind": kind, **attributes}
        attrs = {
            key: json_text(value) if isinstance(value, dict) else value
            for key, value in attrs.items()
            if value is not None
        }
        timestamp = time.time_ns()
        print(
            json_text(
                {
                    "timestamp": timestamp,
                    "trace_id": f"{self.trace_id:032x}",
                    "span_id": f"{self.span_id:016x}",
                    "body": kind,
                    "attributes": attrs,
                }
            ),
            flush=True,
        )
        self.events.logger.emit(
            LogRecord(
                timestamp=timestamp,
                trace_id=self.trace_id,
                span_id=self.span_id,
                trace_flags=TraceFlags(1),
                body=kind,
                attributes=attrs,
            )
        )
