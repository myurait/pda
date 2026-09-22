from dataclasses import dataclass


class RuntimeFailure(Exception):
    pass


@dataclass
class RuntimeOutput:
    text: str
    stop_reason: str = "end_turn"
