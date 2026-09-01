from __future__ import annotations

import hashlib
from pathlib import Path

from process_monitor import ProcessMonitorStore
from scope_v2 import ScopeV2Store


NOW = 1_788_240_000.0


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FakeReviewer:
    def __init__(
        self,
        *,
        scope_verdict: str = "pass",
        assurance: bool = False,
        audit_verdict: str = "pass",
    ) -> None:
        self.scope_verdict = scope_verdict
        self.assurance = assurance
        self.audit_verdict = audit_verdict
        self.review_requests: list[dict[str, object]] = []
        self.audit_requests: list[dict[str, object]] = []

    def review(self, request: dict[str, object]) -> dict[str, object]:
        self.review_requests.append(request)
        return {
            "scope_verdict": self.scope_verdict,
            "scope_findings": [],
            "risk": "critical" if self.assurance else "low",
            "risk_basis": ["test"],
            "additional_assurance_required": self.assurance,
            "post_work_audit_must_establish": ["effects stay in scope"],
            "reviewer_note": "test reviewer",
            "review_id": "review-1",
        }

    def audit(self, request: dict[str, object]) -> dict[str, object]:
        self.audit_requests.append(request)
        return {
            "audit_verdict": self.audit_verdict,
            "findings": [],
            "scope_conformant": self.audit_verdict == "pass",
            "audit_id": "audit-1",
        }


def _frame() -> dict[str, object]:
    return {
        "directive_relation": "new",
        "required_outcomes": ["write one file"],
        "targets": ["repository source tree"],
        "allowed_means": ["file edit"],
        "completion_predicates": ["file updated"],
        "non_goals": ["other files"],
        "uncertainties": [],
        "source_refs": ["current_instruction"],
    }


def _containment(root: Path) -> dict[str, object]:
    return {
        "worktrees": [str(root)],
        "write_paths": ["src/**"],
        "test_paths": ["tests/**"],
        "allowed_effects": ["file-write", "git-stage", "git-commit"],
        "command_allowlist": [],
        "services": [],
        "remotes": [],
        "max_tool_calls": 40,
    }


def test_turn_start_never_classifies_natural_language(tmp_path: Path) -> None:
    monitor = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    store = ScopeV2Store(tmp_path / "scope.db", monitor=monitor, clock=lambda: NOW)

    first = store.start_turn(
        turn_id="turn-fix",
        session_id="session",
        task_id="task",
        instruction_sha256=_sha("変更して"),
    )
    second = store.start_turn(
        turn_id="turn-report",
        session_id="session",
        task_id="task",
        instruction_sha256="b" * 64,
    )

    assert first["state"] == "inference-pending"
    assert second["state"] == "inference-pending"
    assert "task_class" not in first
    assert "task_class" not in second


def test_review_then_lock_allows_only_reviewed_write_scope(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    monitor = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    reviewer = FakeReviewer()
    store = ScopeV2Store(tmp_path / "scope.db", monitor=monitor, clock=lambda: NOW)
    store.start_turn(
        turn_id="turn",
        session_id="session",
        task_id="task",
        instruction_sha256=_sha("変更して"),
    )

    reviewed = store.review_scope(
        turn_id="turn",
        instruction="変更して",
        scope_frame=_frame(),
        plan=["edit src/one.py"],
        containment=_containment(root),
        reviewer=reviewer,
    )
    locked = store.lock_turn(turn_id="turn")

    assert reviewed["state"] == "reviewed"
    assert locked["state"] == "locked"
    assert store.admit_tool(
        turn_id="turn",
        tool_call_id="inside",
        tool_name="write_file",
        args={"path": str(root / "src" / "one.py"), "content": "ok"},
    ).allowed
    outside = store.admit_tool(
        turn_id="turn",
        tool_call_id="outside",
        tool_name="write_file",
        args={"path": str(root / "other.py"), "content": "bad"},
    )
    assert outside.allowed is False
    assert outside.action == "target-outside-reviewed-scope"
    assert reviewer.review_requests[0]["instruction"] == "変更して"


def test_reviewer_revise_and_adapter_failure_leave_mutation_blocked(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monitor = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    store = ScopeV2Store(tmp_path / "scope.db", monitor=monitor, clock=lambda: NOW)
    store.start_turn(
        turn_id="turn",
        session_id="session",
        task_id="task",
        instruction_sha256=_sha("変更して"),
    )

    result = store.review_scope(
        turn_id="turn",
        instruction="変更して",
        scope_frame=_frame(),
        plan=["edit"],
        containment=_containment(root),
        reviewer=FakeReviewer(scope_verdict="revise"),
    )

    assert result["state"] == "review-blocked"
    blocked = store.admit_tool(
        turn_id="turn",
        tool_call_id="write",
        tool_name="write_file",
        args={"path": str(root / "src" / "one.py"), "content": "x"},
    )
    assert blocked.allowed is False


def test_assignment_seed_can_only_narrow_reviewed_containment(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monitor = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    seed = {
        "worktree": str(root),
        "write_paths": ["src/safe/**"],
        "test_paths": [],
        "execution": [],
        "git_write": ["stage", "commit"],
    }
    store = ScopeV2Store(
        tmp_path / "scope.db",
        monitor=monitor,
        clock=lambda: NOW,
        seed_loader=lambda task_id, session_id="": seed,
    )
    store.start_turn(
        turn_id="turn",
        session_id="session",
        task_id="task",
        instruction_sha256=_sha("変更して"),
    )

    result = store.review_scope(
        turn_id="turn",
        instruction="変更して",
        scope_frame=_frame(),
        plan=["edit"],
        containment=_containment(root),
        reviewer=FakeReviewer(),
    )

    assert result["state"] == "review-blocked"
    assert "assignment seed" in result["reason"]


def test_additional_assurance_failure_refuses_completion_and_further_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    monitor = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    reviewer = FakeReviewer(assurance=True, audit_verdict="needs_changes")
    store = ScopeV2Store(tmp_path / "scope.db", monitor=monitor, clock=lambda: NOW)
    store.start_turn(
        turn_id="turn",
        session_id="session",
        task_id="task",
        instruction_sha256=_sha("変更して"),
    )
    store.review_scope(
        turn_id="turn",
        instruction="変更して",
        scope_frame=_frame(),
        plan=["edit"],
        containment=_containment(root),
        reviewer=reviewer,
    )
    store.lock_turn(turn_id="turn")

    completed = store.complete_turn(
        turn_id="turn",
        status="success",
        observed_effects=[
            {"kind": "file-write", "target": str(root / "src" / "one.py"), "result": "ok"}
        ],
        final_scope_conformant=True,
        completion_summary="updated",
        instruction="変更して",
        reviewer=reviewer,
    )

    assert completed["ok"] is False
    assert completed["state"] == "audit-blocked"
    assert reviewer.audit_requests
    later = store.admit_tool(
        turn_id="turn",
        tool_call_id="later",
        tool_name="write_file",
        args={"path": str(root / "src" / "two.py"), "content": "x"},
    )
    assert later.allowed is False


def test_successful_final_audit_emits_monitored_boolean_and_closes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    monitor = ProcessMonitorStore(tmp_path / "monitor.db", clock=lambda: NOW)
    reviewer = FakeReviewer(assurance=True, audit_verdict="pass")
    store = ScopeV2Store(tmp_path / "scope.db", monitor=monitor, clock=lambda: NOW)
    store.start_turn(
        turn_id="turn",
        session_id="session",
        task_id="task",
        instruction_sha256=_sha("変更して"),
    )
    store.review_scope(
        turn_id="turn",
        instruction="変更して",
        scope_frame=_frame(),
        plan=["edit"],
        containment=_containment(root),
        reviewer=reviewer,
    )
    store.lock_turn(turn_id="turn")

    completed = store.complete_turn(
        turn_id="turn",
        status="success",
        observed_effects=[
            {"kind": "file-write", "target": str(root / "src" / "one.py"), "result": "ok"}
        ],
        final_scope_conformant=True,
        completion_summary="updated",
        instruction="変更して",
        reviewer=reviewer,
    )

    assert completed["ok"] is True
    assert completed["state"] == "completed"
    result = monitor.evaluate("scope.final.final-scope-conformant", cutoff=NOW)
    assert result["N"] == 1
    assert result["trigger"] is False
