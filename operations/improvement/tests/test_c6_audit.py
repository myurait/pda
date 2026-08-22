"""Tests for the C6 audit-event contract (ADR D4, owner decision 2026-08-22)."""
from __future__ import annotations

import json
from pathlib import Path

from operations.improvement.c6_audit import REQUIRED_KEYS, validate_ai_invocation

REPO = Path(__file__).parents[3]


def _valid_record() -> dict:
    return {
        "actor": "verifier",
        "purpose": "受入条件と回帰の独立検証",
        "consumer": "review-handoff",
        "task_id": "t_abc12345",
        "started_at": 1787380000,
    }


def test_consumed_invocation_is_valid():
    assert validate_ai_invocation(_valid_record()) == []


def test_unconsumed_invocation_is_a_c6_violation():
    record = _valid_record()
    record["consumer"] = "none"
    errors = validate_ai_invocation(record)
    assert any("violate C6" in error for error in errors)

    record["consumer"] = "   "
    errors = validate_ai_invocation(record)
    assert any("consumer is required" in error for error in errors)


def test_missing_fields_are_rejected():
    errors = validate_ai_invocation({})
    for key in ("actor", "purpose", "consumer"):
        assert f"{key} is required" in errors
    assert "started_at must be a unix timestamp" in errors

    assert validate_ai_invocation("not-a-dict") == ["audit record must be an object"]


def test_schema_file_matches_validator_contract():
    schema = json.loads(
        (REPO / "schemas" / "ai-invocation-audit-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(schema["required"]) == REQUIRED_KEYS

    verification = json.loads(
        (REPO / "schemas" / "verification-report-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(verification["required"]) == {
        "verifier",
        "implementer",
        "verified_head_sha",
        "verdict",
        "summary",
        "checks",
    }
