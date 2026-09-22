"""The closed PDA event vocabulary and deterministic OpenTelemetry IDs."""
import contextvars
import hashlib
import json
import logging
import os
import sys
import time
from typing import Any

from opentelemetry._logs import LogRecord
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.trace import TraceFlags

KINDS = frozenset('job.received input.assembled message.output reasoning tool.call tool.result '
                  'plan permission.request permission.response usage turn.end output.classified '
                  'output.rejected command.run judge.answer unknown engine.workflow engine.task'.split())
_ids = contextvars.ContextVar('pda_ids', default=(1, 1))
_telemetry: tuple | None = None


def identifiers(job_id: str, task_id: str) -> tuple[int, int]:
    return (int.from_bytes(hashlib.sha256(job_id.encode()).digest()[:16], 'big'),
            int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8], 'big'))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def raw_json(value: Any) -> str:
    return json_text(value).encode()[:10240].decode('utf-8', errors='ignore')


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json_text({'level': record.levelname, 'logger': record.name,
                          'message': record.getMessage()})


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger('httpx').setLevel(logging.WARNING)


class DeterministicIds(IdGenerator):
    def generate_trace_id(self) -> int:
        return _ids.get()[0]

    def generate_span_id(self) -> int:
        return _ids.get()[1]


def telemetry() -> tuple:
    global _telemetry
    if _telemetry is None or _telemetry[0] != os.getpid():
        resource = Resource.create({'service.name': os.getenv('PDA_EXECUTOR_ID', 'conductor-mirror')})
        logs = LoggerProvider(resource=resource)
        traces = TracerProvider(resource=resource, id_generator=DeterministicIds())
        endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '').rstrip('/')
        if endpoint:
            logs.add_log_record_processor(BatchLogRecordProcessor(
                OTLPLogExporter(endpoint=endpoint + '/v1/logs'), schedule_delay_millis=200))
            traces.add_span_processor(BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint + '/v1/traces'), schedule_delay_millis=200))
        _telemetry = (os.getpid(), logs, traces)
    return _telemetry[1:]


class Events:
    def __init__(self, job_id: str, cell_id: str, task_id: str,
                 executor_id: str, type_name: str, *, span: bool = True):
        self.trace_id, self.span_id = identifiers(job_id, task_id)
        self.base = {'pda.job_id': job_id, 'pda.cell_id': cell_id, 'pda.task_id': task_id,
                     'pda.executor_id': executor_id, 'pda.type': type_name}
        self.logs, traces = telemetry()
        self.logger = self.logs.get_logger('pda')
        token = _ids.set((self.trace_id, self.span_id))
        try:
            self.span = traces.get_tracer('pda').start_span(type_name, attributes=self.base) \
                if span else None
        finally:
            _ids.reset(token)

    def emit(self, kind: str, **attributes: Any) -> None:
        if kind not in KINDS:
            attributes = {'pda.raw': raw_json({'kind': kind, **attributes})}
            kind = 'unknown'
        attrs = {**self.base, 'pda.event.kind': kind, **attributes}
        attrs = {k: json_text(v) if isinstance(v, dict) else v
                 for k, v in attrs.items() if v is not None}
        self.logger.emit(LogRecord(timestamp=time.time_ns(), observed_timestamp=time.time_ns(),
                                   trace_id=self.trace_id, span_id=self.span_id,
                                   trace_flags=TraceFlags(1), body=kind, attributes=attrs))
        print(json_text({'trace_id': f'{self.trace_id:032x}', 'span_id': f'{self.span_id:016x}',
                         **attrs}), flush=True)

    def close(self) -> None:
        if self.span:
            self.span.end()
        self.logs.force_flush(timeout_millis=5000)
        telemetry()[1].force_flush(timeout_millis=5000)


def map_update(update: dict) -> tuple[str, dict]:
    kind = update.get('sessionUpdate')
    if kind in ('agent_message_chunk', 'agent_thought_chunk'):
        return ('message.output' if kind == 'agent_message_chunk' else 'reasoning',
                {'pda.chars': len(update.get('content', {}).get('text', ''))})
    if kind == 'tool_call':
        return 'tool.call', {'pda.tool_call_id': update.get('toolCallId', ''),
                             'pda.tool_kind': update.get('kind', 'unknown'),
                             'pda.tool_title': update.get('title', ''),
                             'pda.raw_input': json_text(update.get('rawInput'))}
    if kind == 'tool_call_update':
        return 'tool.result', {'pda.tool_call_id': update.get('toolCallId', ''),
                               'pda.tool_status': update.get('status', 'unknown'),
                               'pda.raw_output': json_text(update.get('rawOutput'))}
    if kind == 'plan':
        return 'plan', {'pda.items': len(update.get('entries', []))}
    if kind == 'usage_update':
        # ACP 0.12's used/size mean context occupancy/capacity, not input/output tokens.
        usage = update.get('usage', update)
        attrs = {}
        for src, dst in [('inputTokens', 'input_tokens'), ('outputTokens', 'output_tokens')]:
            if src in usage:
                attrs['gen_ai.usage.' + dst] = usage[src]
        if attrs:
            return 'usage', attrs
    return 'unknown', {'pda.raw': raw_json(update)}
