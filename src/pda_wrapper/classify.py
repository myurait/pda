import json


class OutputRejected(ValueError):
    pass


def classify(raw: str, type_name: str, driver: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        if driver != "acp":
            raise OutputRejected("invalid_kind_or_missing_payload") from None
        return {"kind": "result", "payload": {"text": raw}}
    if isinstance(value, dict) and "kind" in value:
        if value["kind"] == "flow" and type_name != "judge":
            raise OutputRejected("flow_from_non_judge")
        if value["kind"] not in {"flow", "input", "result"} or "payload" not in value:
            raise OutputRejected("invalid_kind_or_missing_payload")
        return value
    if driver != "acp":
        raise OutputRejected("invalid_kind_or_missing_payload")
    return {"kind": "result", "payload": value}
