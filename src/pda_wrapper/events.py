import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Sequence
from contextvars import ContextVar
from typing import Any

import httpx
from opentelemetry._logs import LogRecord
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.common._internal._log_encoder import encode_logs
from opentelemetry.exporter.otlp.proto.common._internal.trace_encoder import encode_spans
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    LogRecordExporter,
    LogRecordExportResult,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
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


class LogQueueExporter(LogRecordExporter):
    def __init__(self, queue: asyncio.Queue) -> None:
        self.queue = queue

    def export(self, batch: Sequence) -> LogRecordExportResult:
        self.queue.put_nowait(("logs", encode_logs(batch).SerializeToString()))
        return LogRecordExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


class SpanQueueExporter(SpanExporter):
    def __init__(self, queue: asyncio.Queue) -> None:
        self.queue = queue

    def export(self, spans: Sequence) -> SpanExportResult:
        self.queue.put_nowait(("traces", encode_spans(spans).SerializeToString()))
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


class Events:
    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint
        self.queue: asyncio.Queue = asyncio.Queue()
        resource = Resource.create({"service.name": "pda"})
        self.provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
        self.traces = TracerProvider(
            resource=resource, id_generator=DeterministicIds(), shutdown_on_exit=False
        )
        if endpoint:
            self.provider.add_log_record_processor(
                SimpleLogRecordProcessor(LogQueueExporter(self.queue))
            )
            self.traces.add_span_processor(SimpleSpanProcessor(SpanQueueExporter(self.queue)))
        self.logger = self.provider.get_logger("pda")
        self.tracer = self.traces.get_tracer("pda")
        self.sender: asyncio.Task | None = None

    def start(self) -> None:
        if self.endpoint:
            self.sender = asyncio.create_task(self._send())

    async def _send(self) -> None:
        async with httpx.AsyncClient(timeout=2) as client:
            while True:
                signal, data = await self.queue.get()
                while True:
                    try:
                        response = await client.post(
                            f"{self.endpoint.rstrip('/')}/v1/{signal}",
                            content=data,
                            headers={"Content-Type": "application/x-protobuf"},
                        )
                        response.raise_for_status()
                        break
                    except httpx.HTTPError as exc:
                        log("otlp_export_failed", error=str(exc))
                        await asyncio.sleep(0.5)
                self.queue.task_done()

    def bind(
        self, job_id: str, task_id: str, cell_id: str, executor_id: str, type_name: str
    ) -> "TaskEvents":
        return TaskEvents(self, job_id, task_id, cell_id, executor_id, type_name)

    async def close(self) -> None:
        self.provider.force_flush()
        self.traces.force_flush()
        if self.sender:
            try:
                await asyncio.wait_for(self.queue.join(), timeout=5)
            except TimeoutError:
                log("otlp_flush_timeout", pending=self.queue.qsize())
            self.sender.cancel()
            await asyncio.gather(self.sender, return_exceptions=True)
        self.provider.shutdown()
        self.traces.shutdown()


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
