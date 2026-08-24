"""Shared fixtures for the scope-gate suite.

The gate reads a host-supplied task anchor out of the process environment,
and this suite also runs on the machine whose dispatcher sets that variable
for the processes it spawns. An ambient value would take over the binding in
every test that passes explicit identifiers.

The repository-root conftest scrubs the variable for any run whose rootdir is
the repository. This fixture is the second line of defence, for a run started
from inside this directory, where that conftest is out of scope. A test that
wants the anchor monkeypatches it back in, which happens after this fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scope_gate import HOST_TASK_BINDING_ENV


@pytest.fixture(autouse=True)
def _clear_host_task_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HOST_TASK_BINDING_ENV, raising=False)
