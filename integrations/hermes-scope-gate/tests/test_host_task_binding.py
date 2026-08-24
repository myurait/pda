"""Resolution of the task identifier a hook call is bound by.

A seed is keyed by the board card the work was assigned as. The identifiers
that reach the hooks of a dispatcher-started worker were measured to carry
the conversation id in both the task and the session field, so a contract
recorded against the card could not be joined to the turn executing it and
the turn came up unseeded. The dispatcher does export the card id into the
worker's process environment, and that anchor is what these tests pin: it
outranks the payload identifiers, the payload identifiers still bind every
surface the dispatcher does not start, and both the in-process and the
out-of-process admission surfaces resolve the same way.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin_runtime import ScopeGatePluginRuntime
from scope_gate import (
    HOST_TASK_BINDING_ENV,
    GateStore,
    host_task_binding,
    resolve_task_binding,
    validate_shell_payload,
)

CHANGE_MESSAGE = "ログイン画面のバグを修正して"

# The measured shape of a dispatcher-started worker: the card id arrives only
# through the process environment, while both payload identifiers carry the
# conversation id.
CARD_ID = "t_dec48aee"
SESSION_ID = "20260824_122848_9e31b9"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "secrets.txt").write_text("keep out\n", encoding="utf-8")
    return repo


def _seed(runtime: ScopeGatePluginRuntime, repo: Path, task_id: str) -> None:
    runtime.record_contract_seed(
        task_id=task_id,
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )


# ---------------------------------------------------------------------------
# The resolution itself
# ---------------------------------------------------------------------------


def test_the_host_anchor_is_read_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Freezing the anchor at import or construction time would bind every
    # later call of the process to whichever value existed first.
    assert host_task_binding() == ""
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)
    assert host_task_binding() == CARD_ID


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_host_anchor_is_absent_rather_than_a_task_id(
    monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    # An exported-but-empty variable is the shape a shell leaves behind. Read
    # as a task id it would key every contract lookup on the empty string.
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, blank)
    assert host_task_binding() == ""
    assert resolve_task_binding(SESSION_ID) == SESSION_ID


def test_the_host_anchor_outranks_the_payload_task_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)
    assert resolve_task_binding(SESSION_ID) == CARD_ID
    assert resolve_task_binding("") == CARD_ID


def test_without_the_host_anchor_the_payload_task_id_is_the_binding() -> None:
    assert resolve_task_binding(SESSION_ID) == SESSION_ID
    assert resolve_task_binding("  padded  ") == "padded"
    assert resolve_task_binding("") == ""


# ---------------------------------------------------------------------------
# In-process hook surface
# ---------------------------------------------------------------------------


def test_the_host_anchor_joins_a_card_seed_to_the_first_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The defect this closes: with the card id reachable only through the
    # environment, the seed recorded against the card was never found and the
    # turn opened unseeded.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, CARD_ID)
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)

    context = runtime.pre_llm_call(
        task_id=SESSION_ID,
        session_id=SESSION_ID,
        user_message=CHANGE_MESSAGE,
    )

    assert context is not None
    assert "artifact-change" in context["context"]
    with runtime.store._connect() as connection:
        rows = connection.execute("SELECT * FROM turns").fetchall()
    assert len(rows) == 1
    assert str(rows[0]["task_id"]) == CARD_ID
    assert str(rows[0]["session_id"]) == SESSION_ID
    assert str(rows[0]["state"]) == "locked"
    assert str(rows[0]["contract_origin"]) == "assignment"
    seed = runtime.store.get_contract_seed(CARD_ID)
    assert seed is not None
    assert seed["consumed_turn_id"] == str(rows[0]["turn_id"])


def test_the_bound_contract_governs_the_tool_calls_of_the_same_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Binding the turn under one identifier and admitting under another would
    # leave the contract in force on paper and absent at the tool boundary.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, CARD_ID)
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)
    payload = {"task_id": SESSION_ID, "session_id": SESSION_ID}
    runtime.pre_llm_call(**payload, user_message=CHANGE_MESSAGE)

    in_scope = runtime.pre_tool_call(
        **payload,
        tool_call_id="write-in",
        tool_name="write_file",
        args={"path": str(repo / "src" / "app.py"), "content": "x"},
    )
    out_of_scope = runtime.pre_tool_call(
        **payload,
        tool_call_id="write-out",
        tool_name="write_file",
        args={"path": str(repo / "secrets.txt"), "content": "x"},
    )

    assert in_scope is None
    assert out_of_scope is not None
    assert out_of_scope["action"] == "block"


def test_an_unbindable_call_is_enforced_against_the_card_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No turn was ever registered, so admission takes the unbound path. It
    # has to look the contract up under the same anchor, or a seeded card
    # would read as an unenforced task.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, CARD_ID)
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)

    blocked = runtime.pre_tool_call(
        task_id=SESSION_ID,
        session_id=SESSION_ID,
        tool_call_id="unbound-write",
        tool_name="write_file",
        args={"path": str(repo / "src" / "app.py"), "content": "x"},
    )

    assert blocked is not None
    assert blocked["action"] == "block"
    assert "contract-unbound" in blocked["message"]


def test_the_execution_middleware_resolves_the_same_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The middleware is the second half of the doubled admission. If only the
    # pre hook resolved the anchor, the recheck would run against a different
    # turn than the one that was admitted.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, CARD_ID)
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)
    payload = {"task_id": SESSION_ID, "session_id": SESSION_ID}
    runtime.pre_llm_call(**payload, user_message=CHANGE_MESSAGE)
    executed: list[dict[str, object]] = []

    result = runtime.tool_execution_middleware(
        **payload,
        tool_call_id="drifted",
        tool_name="write_file",
        args={"path": str(repo / "secrets.txt"), "content": "x"},
        next_call=lambda args: executed.append(args) or {"ok": True},
    )

    assert executed == []
    assert "PDA scope gate" in str(result["error"])


def test_the_control_tool_locks_the_turn_the_anchor_binds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `complete` has to reach the same turn the seed locked; resolving it from
    # the payload alone would refuse the closure of a live contract.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, CARD_ID)
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)
    payload = {"task_id": SESSION_ID, "session_id": SESSION_ID}
    runtime.pre_llm_call(**payload, user_message=CHANGE_MESSAGE)

    completed = runtime.handle_scope_gate({"action": "complete"}, **payload)

    assert completed["ok"] is True
    assert completed["completion_status"] == "success"


def test_the_payload_identifiers_still_bind_without_the_host_anchor(
    tmp_path: Path,
) -> None:
    # Interactive sessions are not dispatcher-started and carry no anchor.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, "task-change")

    context = runtime.pre_llm_call(
        task_id="task-change",
        session_id="session-change",
        user_message=CHANGE_MESSAGE,
    )

    assert context is not None
    assert "artifact-change" in context["context"]
    with runtime.store._connect() as connection:
        row = connection.execute("SELECT * FROM turns").fetchone()
    assert str(row["task_id"]) == "task-change"
    assert str(row["state"]) == "locked"


def test_the_anchor_wins_over_a_payload_task_that_carries_its_own_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both identifiers resolve to a real contract, so the precedence is
    # observable rather than inferred from one lookup failing.
    repo = _repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(other)],
        check=True,
        capture_output=True,
        text=True,
    )
    (other / "src").mkdir()
    (other / "src" / "other.py").write_text("z = 3\n", encoding="utf-8")
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    _seed(runtime, repo, CARD_ID)
    runtime.record_contract_seed(
        task_id="task-payload",
        worktree=str(other),
        branch="main",
        write_paths=["src/other.py"],
    )
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)

    runtime.pre_llm_call(
        task_id="task-payload",
        session_id=SESSION_ID,
        user_message=CHANGE_MESSAGE,
    )

    with runtime.store._connect() as connection:
        row = connection.execute("SELECT * FROM turns").fetchone()
    assert str(row["task_id"]) == CARD_ID
    assert str(repo) in str(row["contract_json"])
    assert str(other) not in str(row["contract_json"])
    assert runtime.store.get_contract_seed("task-payload")["consumed_turn_id"] is None


# ---------------------------------------------------------------------------
# Out-of-process shell-hook surface
# ---------------------------------------------------------------------------


def test_the_shell_hook_resolves_the_host_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The shell validator is spawned by the worker and so inherits the same
    # environment. It is an independent resolution point, and the one place
    # the session field may be absent from the payload altogether: with the
    # task field carrying the conversation id, the anchor is then the only
    # identifier that reaches the contract at all.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id=CARD_ID,
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    store.start_turn(
        turn_id="turn-card",
        session_id=SESSION_ID,
        task_id=CARD_ID,
        user_message=CHANGE_MESSAGE,
    )
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)
    common = {
        "hook_event_name": "pre_tool_call",
        "extra": {"task_id": SESSION_ID},
    }

    blocked = validate_shell_payload(
        {
            **common,
            "tool_name": "write_file",
            "tool_input": {"path": str(repo / "secrets.txt"), "content": "x"},
        },
        state_path=store.path,
    )
    admitted = validate_shell_payload(
        {
            **common,
            "tool_name": "write_file",
            "tool_input": {"path": str(repo / "src" / "app.py"), "content": "x"},
        },
        state_path=store.path,
    )

    assert blocked.get("action") == "block"
    assert admitted == {}


def test_the_shell_hook_enforces_an_unbindable_call_under_the_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id=CARD_ID,
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, CARD_ID)

    directive = validate_shell_payload(
        {
            "hook_event_name": "pre_tool_call",
            "session_id": SESSION_ID,
            "tool_name": "write_file",
            "tool_input": {"path": str(repo / "src" / "app.py"), "content": "x"},
            "extra": {"task_id": SESSION_ID},
        },
        state_path=store.path,
    )

    assert directive.get("action") == "block"
    assert "contract-unbound" in directive["message"]


# ---------------------------------------------------------------------------
# The assignment side keeps its explicit key
# ---------------------------------------------------------------------------


def test_seed_recording_is_not_rebound_by_the_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The orchestrator records a seed for the card it is handing out, which
    # is not the card its own process may be executing. Applying the worker
    # anchor here would file the seed under the wrong task.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    monkeypatch.setenv(HOST_TASK_BINDING_ENV, "t_executing_card")

    runtime.record_contract_seed(
        task_id="t_assigned_card",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )

    assert runtime.store.get_contract_seed("t_assigned_card") is not None
    assert runtime.store.get_contract_seed("t_executing_card") is None
