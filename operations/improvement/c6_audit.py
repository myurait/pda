"""C6 (credit discipline) audit-event validation.

Contract: schemas/ai-invocation-audit-v1.schema.json. Every AI invocation the
improvement cycle starts must be recorded as an audit event whose ``consumer``
names the step or artifact that consumes the output. An invocation without a
real consumer — evidence, logs, or owner-styled documents that never reach the
owner — is the C6 violation class this validator detects.

Verification/review invocations are consumed (their reports gate approval)
and are therefore never restricted by C6 (owner clarification, 2026-08-22).

Kept dependency-free on purpose: the hermes venv used for cycle tests does not
ship jsonschema, and the emitting orchestrator (M2) must be able to validate
before writing the event.
"""
from __future__ import annotations

from typing import Any

REQUIRED_KEYS = ("actor", "purpose", "consumer", "started_at")
_FORBIDDEN_CONSUMERS = {"", "none"}


def validate_ai_invocation(record: Any) -> list[str]:
    """Return contract violations for one audit record (empty list = valid)."""
    if not isinstance(record, dict):
        return ["audit record must be an object"]
    errors: list[str] = []
    for key in ("actor", "purpose", "consumer"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} is required")
    consumer = record.get("consumer")
    if (
        isinstance(consumer, str)
        and consumer.strip().lower() in _FORBIDDEN_CONSUMERS
    ):
        errors.append(
            "consumer must name the step or artifact that consumes the "
            "output; unconsumed AI invocations violate C6"
        )
    started_at = record.get("started_at")
    if not isinstance(started_at, (int, float)) or isinstance(started_at, bool):
        errors.append("started_at must be a unix timestamp")
    task_id = record.get("task_id")
    if task_id is not None and (
        not isinstance(task_id, str) or not task_id.strip()
    ):
        errors.append("task_id must be a non-empty string when present")
    return errors
