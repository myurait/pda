"""Reproduce a control-path closure in unchanged scope-v2 source, offline.

Explicit writes use temporary SQLite stores and a containment directory.
Repository-loader bytecode writes are disabled and tested on a fresh source
copy; source hashes alone do not constitute host-wide filesystem auditing.
The real plugin is never registered, configured, patched or enabled. A scripted
review verdict arranges the locked-state precondition; it is not evidence about
production reviewer availability or the owner's original incident trigger.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "integrations/hermes-scope-gate"


class FixtureReviewer:
    """Arrange a reviewed turn without any model call or genuine approval."""

    def review(self, request: dict[str, object]) -> dict[str, object]:
        return {
            "scope_verdict": "pass",
            "scope_findings": [],
            "risk": "low",
            "risk_basis": ["offline fixture arranging a locked turn"],
            "additional_assurance_required": False,
            "post_work_audit_must_establish": ["no external effects"],
            "reviewer_note": "synthetic arrangement, not owner authorization",
            "review_id": "offline-review-fixture",
        }


def run_probe(budget: int = 1, scenario: str = "exhaust") -> dict[str, object]:
    if scenario == "shrink":
        budget = 8
    if not 1 <= budget <= 500:
        raise ValueError("budget must be within the real gate's supported range 1..500")
    source_paths = [SOURCE_DIR / "scope_v2.py", SOURCE_DIR / "process_monitor.py"]
    before_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    # Import the source module, not the plugin entry point or the live runtime.
    # Suppress loader bytecode writes even when the caller omitted Python -B.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SOURCE_DIR))
    spec = importlib.util.spec_from_file_location("m1_unchanged_scope_v2", source_paths[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="pda-v2-m1-offline-") as temporary:
        sandbox = Path(temporary)
        containment_root = sandbox / "containment"
        containment_root.mkdir()
        store = module.ScopeV2Store(sandbox / "scope.db", clock=lambda: 1_788_240_000.0)
        instruction = "Inspect the fixture and preserve the ability to report a stop."
        store.start_turn(
            turn_id="offline-turn", session_id="offline-session", task_id="offline-task",
            instruction_sha256=hashlib.sha256(instruction.encode()).hexdigest(),
        )
        frame = {
            "directive_relation": "new",
            "required_outcomes": ["inspect an offline fixture"],
            "targets": ["temporary containment"],
            "allowed_means": ["read"],
            "completion_predicates": ["inspection recorded"],
            "non_goals": ["production changes"],
            "uncertainties": [],
            "source_refs": ["current_instruction"],
        }
        containment = {
                "worktrees": [str(containment_root)],
                "write_paths": [], "test_paths": [], "allowed_effects": [],
                "command_allowlist": [], "services": [], "remotes": [],
                "max_tool_calls": budget,
        }
        store.review_scope(
            turn_id="offline-turn", instruction=instruction,
            scope_frame=frame, plan=["inspect the fixture"],
            containment=containment,
            reviewer=FixtureReviewer(),
        )
        store.lock_turn(turn_id="offline-turn")
        def admit(name: str, call_id: str) -> dict[str, object]:
            return asdict(store.admit_tool(
                turn_id="offline-turn", tool_call_id=call_id, tool_name=name, args={}
            ))
        spend = 2 if scenario == "shrink" else budget
        budgeted = [admit("read_file", f"spend-{index}") for index in range(spend)]
        before = budgeted[-1]
        rereview_evidence = {}
        if scenario == "shrink":
            spent_before = store.get_turn("offline-turn")["tool_calls"]
            rereview = store.review_scope(
                turn_id="offline-turn", instruction=instruction,
                scope_frame=frame, plan=["inspect the fixture"],
                containment={**containment, "max_tool_calls": 1},
                reviewer=FixtureReviewer(),
            )
            relock = store.lock_turn(turn_id="offline-turn")
            rereview_evidence = {
                "cap_before": budget, "cap_after": 1,
                "spent_before_rereview": spent_before,
                "spent_after_rereview": store.get_turn("offline-turn")["tool_calls"],
                "rereview_accepted": rereview["state"] == "reviewed",
                "relock_accepted": relock["state"] == "locked",
            }
        turn = store.get_turn("offline-turn")
        assert turn is not None
        after = {name: admit(name, "after-" + name) for name in (
            "read_file", "kanban_heartbeat", "kanban_block", "scope_gate", "delegate_task"
        )}
        completion = admit("kanban_request_review", "finish-after-exhaustion")
        reopened = module.ScopeV2Store(sandbox / "scope.db", clock=lambda: 1_788_240_000.0)
        reopened_decision = asdict(reopened.admit_tool(
            turn_id="offline-turn", tool_call_id="after-reopen",
            tool_name="scope_gate", args={},
        ))
        report = {
            "schema_version": 1,
            "scenario": scenario,
            "scope": "offline-unchanged-gate-witness-not-production-repair",
            "source_files": before_hashes,
            "fixture_reviewer": "synthetic locked-state arrangement only",
            "configured_budget": budget,
            "spent_calls": int(turn["tool_calls"]),
            "all_budgeted_calls_allowed": all(item["allowed"] for item in budgeted),
            "recorded_external_effects": len(store.observed_effects("offline-turn")),
            "before_exhaustion": before,
            "remaining_before": int(turn["containment"]["max_tool_calls"]) - int(turn["tool_calls"]),
            "after_exhaustion": after,
            "completion_signal": completion,
            "after_reopen": reopened_decision,
            "observed_self_blocking": before["allowed"] and all(
                not row["allowed"] and row["action"] == "tool-budget-exhausted"
                for row in after.values()
            ),
            "live_gate_enabled_by_probe": False,
            "original_incident_trigger": "not established by this offline witness",
            **rereview_evidence,
        }
    report["source_unchanged"] = before_hashes == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=1)
    parser.add_argument("--scenario", choices=["exhaust", "shrink"], default="exhaust")
    options = parser.parse_args()
    print(json.dumps(run_probe(options.budget, options.scenario), ensure_ascii=False, sort_keys=True))
