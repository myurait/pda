from pathlib import Path

import pytest

from pda_wrapper.events import identifiers
from pda_wrapper.registry import Registry


class CapturedEvents:
    def __init__(self) -> None:
        self.records = []
        self.trace_id, self.span_id = identifiers("job", "task")

    def emit(self, kind: str, **attrs: object) -> None:
        self.records.append((kind, attrs))

    def close(self) -> None:
        pass


@pytest.fixture
def events() -> CapturedEvents:
    return CapturedEvents()


@pytest.fixture
def registry() -> Registry:
    return Registry(Path(__file__).resolve().parents[2] / "registry")
