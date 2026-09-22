import copy
import sys
from pathlib import Path

import pytest

from pda_wrapper.events import Events
from pda_wrapper.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def registry() -> Registry:
    result = Registry(ROOT / "registry")
    for name in ("fake-a", "fake-b"):
        result.executors[name]["adapter"]["command"][0] = sys.executable
    return result


@pytest.fixture
def events() -> Events:
    return Events()


@pytest.fixture
def task() -> dict:
    return copy.deepcopy(
        {
            "workflowInstanceId": "job-unit",
            "taskId": "task-unit",
            "taskDefName": "implement.fake-a",
            "referenceTaskName": "c1__1",
            "responseTimeoutSeconds": 600,
            "inputData": {
                "job_id": "job-unit",
                "cell_id": "c1",
                "type": "implement",
                "prompt_ref": {"id": "implement", "version": 1},
                "input": "テスト入力",
                "context": None,
            },
        }
    )
