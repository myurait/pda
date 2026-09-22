"""Classification is structural, never a judgment about the payload."""

import json

from jsonschema import Draft7Validator


class OutputRejected(ValueError):
    pass


def classify(raw: str, type_name: str, *, structured: bool = False) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        if structured:
            raise OutputRejected("structured_output_not_json") from None
        return {"kind": "result", "payload": {"text": raw}}
    if isinstance(value, dict) and "kind" in value:
        if value["kind"] == "flow" and type_name != "judge":
            raise OutputRejected("flow_from_non_judge")
        if value["kind"] not in ("flow", "input", "result") or "payload" not in value:
            raise OutputRejected("invalid_kind_or_missing_payload")
        return value
    if structured:
        raise OutputRejected("structured_output_missing_kind")
    return {"kind": "result", "payload": value}


def validate_output(value: dict, schema: dict) -> None:
    error = next(Draft7Validator(schema).iter_errors(value), None)
    if error:
        path = ".".join(str(item) for item in error.absolute_path)
        # Do not copy an arbitrarily large/sensitive payload into the failure reason.
        raise OutputRejected(f"schema_mismatch:{path}:{error.validator}")
