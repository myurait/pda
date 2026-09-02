from __future__ import annotations

import json
from pathlib import Path

import pytest

import scope_gate
from plugin_runtime_v2 import (
    ScopeGateV2PluginRuntime,
    TerraReviewer,
    validate_shell_payload_v2,
)


class FakeReviewer:
    def __init__(self, *, assurance: bool = False, audit_pass: bool = True) -> None:
        self.assurance = assurance
        self.audit_pass = audit_pass

    def review(self, request):
        return {
            "scope_verdict": "pass",
            "scope_findings": [],
            "risk": "high" if self.assurance else "low",
            "risk_basis": ["test"],
            "additional_assurance_required": self.assurance,
            "post_work_audit_must_establish": ["effects"],
            "reviewer_note": "ok",
            "review_id": "review-id",
        }

    def audit(self, request):
        return {
            "audit_verdict": "pass" if self.audit_pass else "needs_changes",
            "findings": [],
            "scope_conformant": self.audit_pass,
            "audit_id": "audit-id",
        }


def _frame() -> dict[str, object]:
    return {
        "directive_relation": "new",
        "required_outcomes": ["update one file"],
        "targets": ["repo"],
        "allowed_means": ["write"],
        "completion_predicates": ["updated"],
        "non_goals": [],
        "uncertainties": [],
        "source_refs": ["current_instruction"],
    }


def _containment(root: Path) -> dict[str, object]:
    return {
        "worktrees": [str(root)],
        "write_paths": ["src/**"],
        "test_paths": [],
        "allowed_effects": ["file-write"],
        "command_allowlist": [],
        "services": [],
        "remotes": [],
    }


def test_terra_adapter_uses_fresh_safe_mode_session_and_strict_json() -> None:
    calls: list[list[str]] = []

    def runner(command, env, timeout):
        del env, timeout
        calls.append(command)
        return json.dumps(
            {
                "scope_verdict": "pass",
                "scope_findings": [],
                "risk": "low",
                "risk_basis": [],
                "additional_assurance_required": False,
                "post_work_audit_must_establish": [],
                "reviewer_note": "ok",
            }
        )

    reviewer = TerraReviewer(hermes_binary="/usr/bin/hermes", runner=runner)
    result = reviewer.review({"instruction": "test"})

    assert "--safe-mode" in calls[0]
    assert calls[0][calls[0].index("-m") + 1] == "gpt-5.6-terra"
    assert result["reviewer_process"] == "fresh-safe-mode-session"
    assert result["review_id"]

    bad = TerraReviewer(
        hermes_binary="/usr/bin/hermes",
        runner=lambda command, env, timeout: "```json\n{}\n```",
    )
    with pytest.raises(ValueError, match="non-JSON"):
        bad.review({"instruction": "test"})


def test_live_terra_adapter_smoke_only_when_explicitly_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    node_name = "test_live_terra_adapter_smoke_only_when_explicitly_selected"
    if not any(f"::{node_name}" in argument for argument in sys.argv):
        pytest.skip("live Terra smoke runs only by explicit node selection")
    # The explicit node selection is the operator opt-in for using the live
    # Hermes account. Remove pytest's ambient marker only for this subprocess;
    # the normal focused suite continues to skip this test hermetically.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    reviewer = TerraReviewer()
    result = reviewer.review(
        {
            "instruction": "この入力を読み取り専用の評価として扱う",
            "scope_frame": {
                "directive_relation": "new",
                "required_outcomes": ["評価結果を返す"],
                "targets": ["この入力"],
                "allowed_means": ["no-tools review"],
                "completion_predicates": ["JSON verdict"],
                "non_goals": ["外部作用"],
                "uncertainties": [],
                "source_refs": ["current_instruction"],
            },
            "plan": ["入力とframeの過不足を評価する"],
            "containment": {
                "worktrees": [str(Path.cwd())],
                "write_paths": [],
                "allowed_effects": [],
            },
        }
    )

    assert result["scope_verdict"] in {"pass", "revise", "block"}
    assert type(result["additional_assurance_required"]) is bool
    assert result["reviewer_model"] == "gpt-5.6-terra"

    audit = reviewer.audit(
        {
            "instruction": "この入力を読み取り専用の評価として扱う",
            "reviewed_scope_frame": {
                "directive_relation": "new",
                "required_outcomes": ["評価結果を返す"],
                "targets": ["この入力"],
                "allowed_means": ["no-tools review"],
                "completion_predicates": ["JSON verdict"],
                "non_goals": ["外部作用"],
                "uncertainties": [],
                "source_refs": ["current_instruction"],
            },
            "reviewed_plan": ["入力を評価する"],
            "reviewed_containment": {
                "worktrees": [str(Path.cwd())],
                "write_paths": [],
                "allowed_effects": [],
            },
            "observed_effects": [],
            "completion_status": "success",
            "completion_summary": "JSON評価を返した",
            "executor_final_scope_conformant": True,
            "mechanical_findings": [],
        }
    )

    assert audit["audit_verdict"] in {"pass", "needs_changes", "block"}
    assert type(audit["scope_conformant"]) is bool
    assert audit["reviewer_process"] == "fresh-safe-mode-session"


def test_runtime_never_calls_legacy_natural_language_classifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        scope_gate,
        "classify_task",
        lambda message: (_ for _ in ()).throw(AssertionError(message)),
    )
    runtime = ScopeGateV2PluginRuntime(tmp_path / "scope.db", reviewer=FakeReviewer())

    context = runtime.pre_llm_call(
        turn_id="turn",
        task_id="task",
        session_id="session",
        user_message="直せ",
    )

    assert context is not None
    assert "task classifier" in context["context"]
    turn = runtime.store.get_turn("turn")
    assert turn is not None
    assert "task_class" not in turn


def test_runtime_review_lock_effect_observation_and_complete(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    runtime = ScopeGateV2PluginRuntime(
        tmp_path / "scope.db", reviewer=FakeReviewer(assurance=True)
    )
    common = {"turn_id": "turn", "task_id": "task", "session_id": "session"}
    runtime.pre_llm_call(**common, user_message="変更して")

    reviewed = runtime.handle_scope_gate(
        {
            "action": "review",
            "scope_frame": _frame(),
            "plan": ["write src/one.py"],
            "containment": _containment(root),
        },
        **common,
    )
    locked = runtime.handle_scope_gate({"action": "lock"}, **common)
    args = {"path": str(root / "src" / "one.py"), "content": "ok"}
    assert runtime.pre_tool_call(
        **common,
        tool_call_id="write",
        tool_name="write_file",
        args=args,
    ) is None
    runtime.post_tool_call(
        **common,
        tool_call_id="write",
        tool_name="write_file",
        args=args,
        status="ok",
        result={"verified": True},
    )
    completed = runtime.handle_scope_gate(
        {
            "action": "complete",
            "status": "success",
            "observed_effects": [],
            "final_scope_conformant": True,
            "completion_summary": "updated",
        },
        **common,
    )

    assert reviewed["ok"] is True
    assert locked["ok"] is True
    assert completed["ok"] is True
    assert completed["audit"]["observed_effects"][0]["kind"] == "file-write"


def test_post_llm_auto_closes_no_effect_turn_but_marks_missing_explicit_audit(
    tmp_path: Path,
) -> None:
    runtime = ScopeGateV2PluginRuntime(tmp_path / "scope.db", reviewer=FakeReviewer())
    runtime.pre_llm_call(
        turn_id="read",
        task_id="task-read",
        session_id="session-read",
        user_message="状態は？",
    )
    runtime.post_llm_call(
        turn_id="read", task_id="task-read", session_id="session-read"
    )
    read_turn = runtime.store.get_turn("read")
    assert read_turn is not None
    assert read_turn["state"] == "completed"

    root = tmp_path / "repo"
    root.mkdir()
    common = {"turn_id": "write", "task_id": "task-write", "session_id": "session-write"}
    runtime.pre_llm_call(**common, user_message="変更して")
    runtime.handle_scope_gate(
        {
            "action": "review",
            "scope_frame": _frame(),
            "plan": ["write"],
            "containment": _containment(root),
        },
        **common,
    )
    runtime.handle_scope_gate({"action": "lock"}, **common)
    runtime.post_llm_call(**common)
    runtime.monitor.evaluate("scope.final.final-scope-conformant")

    failures = runtime.monitor.list_failures()
    assert any(item["failure_type"] == "missing-decision" for item in failures)


def test_shell_validator_rechecks_v2_contract(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    state = tmp_path / "scope.db"
    runtime = ScopeGateV2PluginRuntime(state, reviewer=FakeReviewer())
    common = {"turn_id": "turn", "task_id": "task", "session_id": "session"}
    runtime.pre_llm_call(**common, user_message="変更して")
    runtime.handle_scope_gate(
        {
            "action": "review",
            "scope_frame": _frame(),
            "plan": ["write"],
            "containment": _containment(root),
        },
        **common,
    )
    runtime.handle_scope_gate({"action": "lock"}, **common)
    payload = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "write_file",
        "tool_input": {"path": str(root / "outside.py"), "content": "bad"},
        "session_id": "session",
        "extra": {
            "turn_id": "turn",
            "task_id": "task",
            "tool_call_id": "outside",
        },
    }

    result = validate_shell_payload_v2(payload, state_path=state)

    assert result["action"] == "block"
    assert "target-outside-reviewed-scope" in result["message"]


def test_shell_validator_blocks_unbound_mutation_but_keeps_read_diagnostics(
    tmp_path: Path,
) -> None:
    state = tmp_path / "scope.db"
    base = {
        "hook_event_name": "pre_tool_call",
        "session_id": "new-session",
        "extra": {"turn_id": "new-turn", "task_id": "", "tool_call_id": "call"},
    }
    write_payload = {
        **base,
        "tool_name": "write_file",
        "tool_input": {"path": str(tmp_path / "file"), "content": "x"},
    }
    read_payload = {
        **base,
        "tool_name": "read_file",
        "tool_input": {"path": str(tmp_path / "file")},
    }

    blocked = validate_shell_payload_v2(write_payload, state_path=state)
    allowed = validate_shell_payload_v2(read_payload, state_path=state)

    assert blocked["action"] == "block"
    assert "v2-turn-required" in blocked["message"]
    assert allowed == {}


def test_pre_llm_call_binds_delegated_child_session_to_parent_turn(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    runtime = ScopeGateV2PluginRuntime(tmp_path / "scope.db", reviewer=FakeReviewer())
    parent = {"turn_id": "parent-turn", "task_id": "", "session_id": "parent"}
    runtime.pre_llm_call(**parent, user_message="直して")
    runtime.handle_scope_gate(
        {
            "action": "review",
            "scope_frame": _frame(),
            "plan": ["write"],
            "containment": _containment(root),
        },
        **parent,
    )
    assert runtime.handle_scope_gate({"action": "lock"}, **parent)["ok"] is True

    child = {"turn_id": "child-turn", "task_id": "", "session_id": "child"}
    context = runtime.pre_llm_call(
        **child,
        parent_session_id="parent",
        user_message="親モデルが書いた委譲文: src/one.py を書け",
    )
    assert context is not None
    assert runtime.store.get_turn("child-turn") is None, "child must not open its own turn"
    assert runtime.pre_tool_call(
        **child,
        tool_call_id="cw",
        tool_name="write_file",
        args={"path": str(root / "src" / "one.py"), "content": "x"},
    ) is None
    outside = runtime.pre_tool_call(
        **child,
        tool_call_id="cw2",
        tool_name="write_file",
        args={"path": str(root / "other.py"), "content": "x"},
    )
    assert outside is not None and "target-outside-reviewed-scope" in outside["message"]

    orphan = {"turn_id": "orphan-turn", "task_id": "", "session_id": "orphan"}
    runtime.pre_llm_call(**orphan, parent_session_id="unknown-parent", user_message="書け")
    blocked = runtime.pre_tool_call(
        **orphan,
        tool_call_id="ow",
        tool_name="write_file",
        args={"path": str(root / "src" / "one.py"), "content": "x"},
    )
    assert blocked is not None and "v2-turn-required" in blocked["message"]


def test_shell_validator_never_routes_into_legacy_classifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import plugin_runtime_v2

    assert not hasattr(plugin_runtime_v2, "validate_legacy_shell_payload")
    for name in ("validate_shell_payload", "classify_task"):
        monkeypatch.setattr(
            scope_gate,
            name,
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError(name)),
        )
    state = tmp_path / "scope.db"
    root = tmp_path / "repo"
    root.mkdir()
    # A legacy assignment seed exists for the task, exactly the situation that
    # used to route seeded workers into the v1 validator.
    scope_gate.GateStore(state).record_contract_seed(
        task_id="task",
        worktree=str(root),
        branch="main",
        write_paths=["src/**"],
        base_commit="a" * 40,
    )
    payload = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "write_file",
        "tool_input": {"path": str(root / "src" / "one.py"), "content": "x"},
        "session_id": "worker",
        "extra": {"turn_id": "", "task_id": "task", "tool_call_id": "call"},
    }

    blocked = validate_shell_payload_v2(payload, state_path=state)

    assert blocked["action"] == "block"
    assert "v2-turn-required" in blocked["message"]


def test_terra_adapter_pins_minimal_toolset_and_reports_audit_path(tmp_path: Path) -> None:
    import sys

    calls: list[list[str]] = []

    def runner(command, env, timeout):
        del env, timeout
        calls.append(command)
        return json.dumps({"audit_verdict": "pass", "findings": [], "scope_conformant": True})

    reviewer = TerraReviewer(hermes_binary=sys.executable, runner=runner)
    reviewer.audit({"instruction": "x"})

    assert calls[0][calls[0].index("-t") + 1] == "todo"
    assert reviewer.audit_available() is True
    missing = TerraReviewer(hermes_binary=str(tmp_path / "no-such-hermes"), runner=runner)
    assert missing.audit_available() is False


def test_child_final_response_never_finalizes_parent_turn(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    runtime = ScopeGateV2PluginRuntime(tmp_path / "scope.db", reviewer=FakeReviewer())
    parent = {"turn_id": "parent-turn", "task_id": "", "session_id": "parent"}
    runtime.pre_llm_call(**parent, user_message="直して")

    # Child finishes read-only research before the parent has even reviewed.
    early = {"turn_id": "child-a", "task_id": "", "session_id": "child-a"}
    runtime.pre_llm_call(**early, parent_session_id="parent", user_message="調べて")
    runtime.post_llm_call(**early)
    assert runtime.store.get_turn("parent-turn")["state"] == "inference-pending"

    runtime.handle_scope_gate(
        {
            "action": "review",
            "scope_frame": _frame(),
            "plan": ["write"],
            "containment": _containment(root),
        },
        **parent,
    )
    assert runtime.handle_scope_gate({"action": "lock"}, **parent)["ok"] is True

    # Child finishes after the parent locked.
    late = {"turn_id": "child-b", "task_id": "", "session_id": "child-b"}
    runtime.pre_llm_call(**late, parent_session_id="parent", user_message="書いて")
    runtime.post_llm_call(**late)
    runtime.on_session_end(**late)
    assert runtime.store.get_turn("parent-turn")["state"] == "locked"

    completed = runtime.handle_scope_gate(
        {
            "action": "complete",
            "status": "success",
            "observed_effects": [],
            "final_scope_conformant": True,
            "completion_summary": "done",
        },
        **parent,
    )
    assert completed["ok"] is True


def test_reviewer_session_never_opens_a_turn_or_feeds_the_monitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plugin_runtime_v2 import REVIEWER_SESSION_ENV

    calls: list[list[str]] = []

    def runner(command, env, timeout):
        del timeout
        calls.append(command)
        assert env[REVIEWER_SESSION_ENV] == "1"
        return json.dumps({"audit_verdict": "pass", "findings": [], "scope_conformant": True})

    TerraReviewer(hermes_binary="/usr/bin/hermes", runner=runner).audit({"instruction": "x"})
    assert calls

    monkeypatch.setenv(REVIEWER_SESSION_ENV, "1")
    runtime = ScopeGateV2PluginRuntime(tmp_path / "scope.db", reviewer=FakeReviewer())
    common = {"turn_id": "terra-turn", "task_id": "", "session_id": "terra-session"}
    assert runtime.pre_llm_call(**common, user_message="監査依頼") is None
    assert runtime.store.get_turn("terra-turn") is None
    assert runtime.pre_tool_call(**common, tool_call_id="r", tool_name="read_file", args={"path": "/x"}) is None
    blocked = runtime.pre_tool_call(
        **common, tool_call_id="w", tool_name="write_file", args={"path": "/x", "content": "y"}
    )
    assert blocked is not None and "v2-turn-required" in blocked["message"]
    runtime.post_llm_call(**common)
    assert runtime.monitor.evaluate("scope.final.final-scope-conformant")["N"] == 0
