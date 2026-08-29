"""S3-M1 deterministic core for the artifact-change task class.

Coverage: the path foundation, the explicit write-destination catalogue, the
two contract layers, the contract lifecycle (assignment seed, self lock,
pre-lock default deny, closure), the per-class admission dispatch, and the
adversarial acceptance set required by the design checklist.

Test names stay at the abstraction level of the defect ledger: they name the
property being enforced, not a technique for defeating it.
"""

from __future__ import annotations

import ast
import itertools
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin_runtime import (
    PRELOCK_ENFORCEMENT_ENV,
    ScopeGatePluginRuntime,
    prelock_enforcement_setting,
)
from scope_gate import (
    _GIT_READ_REFUSAL_REASONS,
    _GIT_UNADMITTED_REASONS,
    ARTIFACT_BUDGET_DENY_ACTIONS,
    ARTIFACT_CHANGE_CLASS_BUDGET,
    ARTIFACT_DEVIATION_DENY_ACTIONS,
    ARTIFACT_GIT_DIFF_FAMILY_SUBCOMMANDS,
    ARTIFACT_GIT_PATH_OPTIONS,
    ARTIFACT_GIT_READ_FORM_FLAGS,
    ARTIFACT_GIT_READ_SUBCOMMANDS,
    ARTIFACT_GIT_READ_UNADMITTED,
    ARTIFACT_GIT_WRITE_CAPABLE_SUBCOMMANDS,
    ARTIFACT_GIT_WRITE_FORM_MARKERS,
    ARTIFACT_READ_TOOLS,
    ARTIFACT_RUN_SIGNAL_TOOLS,
    ARTIFACT_WORK_RECORD_TOOLS,
    ARTIFACT_WRITE_TOOL_CATALOG,
    artifact_deny_counter,
    artifact_git_read_refusal_action,
    artifact_git_unadmitted_refusal_action,
    EXECUTION_TEMPLATES,
    GateStore,
    PathRejected,
    classify_task,
    collect_write_targets,
    decision_for,
    locked_admission_for,
    normalize_repo_relative_path,
    normalize_scope_patterns,
    scope_pattern_matches,
    validate_shell_payload,
)

CHANGE_MESSAGE = "ログイン画面のバグを修正して"

# The running tool vocabulary, read from the progress pipe's activity groups
# so the gate's allowlist and the tool names in use cannot drift apart
# silently.
_TOOL_VOCABULARY_SOURCE = (
    ROOT.parents[1]
    / "integrations"
    / "openwebui-hermes-progress"
    / "functions"
    / "hermes_progress_pipe.py"
)


def _hermes_tool_vocabulary() -> frozenset[str]:
    tree = ast.parse(_TOOL_VOCABULARY_SOURCE.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "_PROGRESS_TOOL_ACTIVITY_GROUPS" not in targets:
            continue
        for literal in ast.walk(node.value):
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                names.add(literal.value)
    assert "read_file" in names, "tool vocabulary source did not parse as expected"
    return frozenset(names)


def _init_git_repo(path: Path, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    if (path / ".git").exists():
        return
    subprocess.run(
        ["git", "init", "-q", "-b", branch, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "src" / "deep").mkdir(exist_ok=True)
    (repo / "src" / "deep" / "nested.py").write_text("y = 2\n", encoding="utf-8")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_app.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (repo / "secrets.txt").write_text("keep out\n", encoding="utf-8")
    return repo


def _seeded_store(
    tmp_path: Path,
    *,
    write_paths: list[str] | None = None,
    test_paths: list[str] | None = None,
    execution: list[str] | None = None,
    git_write: list[str] | None = None,
    branch: str = "main",
    repo: Path | None = None,
) -> tuple[GateStore, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    target = repo if repo is not None else _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(target),
        branch=branch,
        write_paths=write_paths if write_paths is not None else ["src/*.py"],
        test_paths=test_paths if test_paths is not None else ["tests/test_app.py"],
        execution=execution or [],
        git_write=git_write,
    )
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )
    return store, target


_CALL_IDS = itertools.count()


def _admit(
    store: GateStore,
    tool_name: str,
    args: dict[str, object],
    *,
    call_id: str | None = None,
    turn_id: str = "turn-change",
):
    # Distinct ids on purpose: a reused id would be answered from the
    # idempotence cache or the argument-drift guard instead of admission.
    return store.admit_tool(
        turn_id=turn_id,
        tool_call_id=call_id or f"{tool_name}-{next(_CALL_IDS)}",
        tool_name=tool_name,
        args=args,
    )


# ---------------------------------------------------------------------------
# Path foundation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "relative", "expected"),
    [
        ("src/*.py", "src/app.py", True),
        # A single-segment wildcard must not reach into a nested directory.
        ("src/*.py", "src/deep/nested.py", False),
        # A prefix wildcard must not spill into a sibling with the same prefix.
        ("src/foo*", "src/foobar/x.py", False),
        ("src/**/*.py", "src/deep/nested.py", True),
        ("src/**", "src/deep/nested.py", True),
        ("src/**", "other/x.py", False),
        ("docs/design/*.md", "docs/design/a.md", True),
        ("docs/design/*.md", "docs/design/sub/a.md", False),
    ],
)
def test_scope_glob_respects_segment_boundaries(
    pattern: str, relative: str, expected: bool
) -> None:
    assert scope_pattern_matches(pattern, relative) is expected


def test_path_normalization_accepts_both_notations_for_the_same_target(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)

    absolute_form, _ = normalize_repo_relative_path(
        str(repo / "src" / "app.py"), root=str(repo)
    )
    relative_form, _ = normalize_repo_relative_path("src/app.py", root=str(repo))
    dotted_form, _ = normalize_repo_relative_path("./src/app.py", root=str(repo))

    assert absolute_form == relative_form == dotted_form == "src/app.py"


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "src/\x01app.py", "src/\tapp.py"],
)
def test_path_normalization_rejects_empty_and_control_characters(
    tmp_path: Path, raw: str
) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(PathRejected):
        normalize_repo_relative_path(raw, root=str(repo))


def test_path_normalization_rejects_targets_outside_the_locked_root(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside" / "x.py"

    with pytest.raises(PathRejected) as first:
        normalize_repo_relative_path(str(outside), root=str(repo))
    with pytest.raises(PathRejected) as second:
        normalize_repo_relative_path("../outside/x.py", root=str(repo))

    assert first.value.code == "target-closed"
    assert second.value.code in {"target-closed", "target-traversal"}


def test_write_target_entity_resolution_stays_inside_the_locked_root(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "linked").symlink_to(outside, target_is_directory=True)

    relative, inside = normalize_repo_relative_path("src/new.py", root=str(repo))

    assert relative == "src/new.py"
    assert inside == repo.resolve() / "src" / "new.py"
    with pytest.raises(PathRejected) as exc:
        normalize_repo_relative_path("linked/new.py", root=str(repo))
    assert exc.value.code == "target-escape"


@pytest.mark.parametrize("depth", [1, 2])
def test_an_upward_reference_after_a_link_element_cannot_relocate_the_target(
    tmp_path: Path, depth: int
) -> None:
    # The check has to run on the raw argument: folding the notation first
    # would erase the upward reference and resolve a different path than the
    # one the tool is handed.
    repo = _repo(tmp_path)
    outside = tmp_path / "outside" / "deep"
    outside.mkdir(parents=True)
    (repo / "src" / "link").symlink_to(outside, target_is_directory=True)
    notation = "src/link/" + "../" * depth + "escaped.py"

    with pytest.raises(PathRejected) as exc:
        normalize_repo_relative_path(notation, root=str(repo))

    assert exc.value.code == "target-traversal"


def test_the_scope_match_uses_the_resolved_destination_not_the_notation(
    tmp_path: Path,
) -> None:
    # An in-scope name that resolves to an out-of-scope location inside the
    # same worktree must be matched at its resolved location.
    repo = _repo(tmp_path)
    (repo / "src" / "alias.py").symlink_to(repo / "secrets.txt")

    relative, resolved = normalize_repo_relative_path("src/alias.py", root=str(repo))

    assert relative == "secrets.txt"
    assert resolved == repo.resolve() / "secrets.txt"


def test_equivalent_spellings_of_the_locked_root_resolve_alike(
    tmp_path: Path,
) -> None:
    # Membership of the locked root is a property of the location, not of the
    # notation: a link component in the argument must not close the gate.
    repo = _repo(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(repo, target_is_directory=True)

    through_alias, _ = normalize_repo_relative_path(
        str(alias / "src" / "app.py"), root=str(repo)
    )
    direct, _ = normalize_repo_relative_path(
        str(repo / "src" / "app.py"), root=str(alias)
    )

    assert through_alias == "src/app.py"
    assert direct == "src/app.py"


@pytest.mark.parametrize(
    "patterns",
    [
        ["/absolute/x"],
        ["../outside/x"],
        ["src/../../x"],
        ["src/\x01x"],
        ["src/x with space"],
        [""],
        [f"pattern{index}" for index in range(33)],
    ],
)
def test_scope_pattern_validation_is_closed(patterns: list[str]) -> None:
    with pytest.raises(PathRejected):
        normalize_scope_patterns(patterns, field="write_paths")


# ---------------------------------------------------------------------------
# Explicit write-destination catalogue
# ---------------------------------------------------------------------------


def test_unlisted_tools_are_treated_as_mutation() -> None:
    with pytest.raises(PathRejected) as exc:
        collect_write_targets("some_unlisted_tool", {"path": "src/app.py"})
    assert exc.value.code == "tool-unlisted"


def test_every_declared_destination_field_is_collected() -> None:
    pair = collect_write_targets(
        "move_file", {"source": "src/a.py", "destination": "src/b.py"}
    )
    nested = collect_write_targets(
        "multi_edit", {"edits": [{"path": "src/a.py"}, {"path": "src/b.py"}]}
    )
    listed = collect_write_targets(
        "write_files", {"files": [{"path": "src/a.py", "content": "x"}, "src/b.py"]}
    )

    assert set(pair) == {"src/a.py", "src/b.py"}
    assert set(nested) == {"src/a.py", "src/b.py"}
    assert set(listed) == {"src/a.py", "src/b.py"}


def test_a_catalogued_tool_without_a_destination_field_is_denied() -> None:
    with pytest.raises(PathRejected) as exc:
        collect_write_targets("write_file", {"content": "x"})
    assert exc.value.code == "target-missing"


def test_the_catalogue_and_the_admission_dispatch_are_wired() -> None:
    assert "write_file" in ARTIFACT_WRITE_TOOL_CATALOG
    assert locked_admission_for("artifact-change") is not None
    assert locked_admission_for("repository-closeout") is not None
    assert locked_admission_for("audit-only") is None


def test_execution_registry_matches_the_contract_schema_enum() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "scope-contract-v1.schema.json").read_text(encoding="utf-8")
    )
    enum = schema["properties"]["execution"]["properties"]["templates"]["items"]["enum"]

    assert sorted(enum) == sorted(EXECUTION_TEMPLATES)


# ---------------------------------------------------------------------------
# Contract lifecycle
# ---------------------------------------------------------------------------


def test_assignment_seed_locks_the_turn_before_its_first_tool_call(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path)

    turn = store.get_turn("turn-change")

    assert turn is not None
    assert turn["state"] == "locked"
    assert turn["contract_origin"] == "assignment"
    contract = json.loads(turn["contract_json"])
    assert contract["origin"] == "assignment"
    assert contract["task_class"] == "artifact-change"
    assert contract["targets"]["write_paths"] == ["src/*.py"]
    assert contract["targets"]["worktrees"] == [str(repo.resolve())]
    assert contract["execution"]["templates"] == []


def test_a_seed_that_fails_verification_keeps_mutation_denied(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, branch="not-the-checked-out-branch")

    turn = store.get_turn("turn-change")
    write = _admit(store, "write_file", {"path": str(repo / "src" / "app.py"), "content": "x"})
    read = _admit(store, "read_file", {"path": str(repo / "src" / "app.py")})

    assert turn is not None
    assert turn["state"] == "mutation-denied"
    assert write.allowed is False
    assert write.action == "seed-verification-failed"
    assert read.allowed is True


def test_a_seed_over_a_non_repository_target_keeps_mutation_denied(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    store, _ = _seeded_store(tmp_path, repo=plain)

    turn = store.get_turn("turn-change")
    decision = _admit(store, "write_file", {"path": str(plain / "src" / "a.py"), "content": "x"})

    assert turn is not None
    assert turn["state"] == "mutation-denied"
    assert decision.allowed is False


def test_pre_lock_allows_reading_and_denies_mutation_and_execution(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )

    turn = store.get_turn("turn-change")
    read = _admit(store, "read_file", {"path": str(repo / "src" / "app.py")})
    write = _admit(store, "write_file", {"path": str(repo / "src" / "app.py"), "content": "x"})
    run = _admit(store, "terminal", {"command": "git status --short", "workdir": str(repo)})
    unknown = _admit(store, "some_unlisted_tool", {"path": "src/app.py"})

    assert turn is not None
    assert turn["state"] == "pre-lock"
    assert read.allowed is True
    for denied in (write, run, unknown):
        assert denied.allowed is False
        assert denied.action == "lock-pending"


def test_self_lock_records_a_weaker_contract_origin(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-self",
        user_message=CHANGE_MESSAGE,
    )

    contract = store.lock_turn(
        turn_id="turn-change",
        repositories=[str(repo)],
        worktrees=[str(repo)],
        branches=["main"],
        write_paths=["src/*.py"],
        test_paths=["tests/test_app.py"],
        execution=["focused-test"],
    )

    assert contract["origin"] == "self"
    assert contract["state"] == "locked"
    turn = store.get_turn("turn-change")
    assert turn is not None
    assert turn["contract_origin"] == "self"


def test_a_self_lock_cannot_exceed_the_assigned_seed(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, write_paths=["src/*.py"], test_paths=[])

    with pytest.raises(ValueError, match="exceeds the assigned contract seed"):
        store.lock_turn(
            turn_id="turn-change",
            repositories=[str(repo)],
            worktrees=[str(repo)],
            branches=["main"],
            write_paths=["src/*.py", "docs/**"],
        )
    with pytest.raises(ValueError, match="exceeds the assigned contract seed"):
        store.lock_turn(
            turn_id="turn-change",
            repositories=[str(repo)],
            worktrees=[str(repo)],
            branches=["main"],
            execution=["focused-test"],
        )


def test_relocking_a_seeded_turn_returns_the_same_contract(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)
    original = json.loads(store.get_turn("turn-change")["contract_json"])

    replayed = store.lock_turn(
        turn_id="turn-change",
        repositories=[str(repo)],
        worktrees=[str(repo)],
        branches=["main"],
        write_paths=["src/*.py"],
    )

    assert replayed == original


def test_targets_and_write_scope_cannot_be_added_after_lock(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)
    other = tmp_path / "other"
    _init_git_repo(other)

    with pytest.raises(ValueError, match="exceeds the assigned contract seed"):
        store.lock_turn(
            turn_id="turn-change",
            repositories=[str(other)],
            worktrees=[str(other)],
            branches=["main"],
            write_paths=["src/*.py"],
        )


def test_a_self_lock_can_only_hold_one_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    other = tmp_path / "other"
    _init_git_repo(other)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-change",
        session_id="s",
        task_id="task-self",
        user_message=CHANGE_MESSAGE,
    )

    with pytest.raises(ValueError, match="exactly one worktree"):
        store.lock_turn(
            turn_id="turn-change",
            repositories=[str(repo), str(other)],
            worktrees=[str(repo), str(other)],
            branches=["main"],
            write_paths=["src/*.py"],
        )


def test_a_lock_detects_scope_prefixes_that_leave_the_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "linked").symlink_to(outside, target_is_directory=True)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-change",
        session_id="s",
        task_id="task-self",
        user_message=CHANGE_MESSAGE,
    )

    with pytest.raises(PathRejected, match="outside the locked worktree"):
        store.lock_turn(
            turn_id="turn-change",
            repositories=[str(repo)],
            worktrees=[str(repo)],
            branches=["main"],
            write_paths=["linked/**/*.py"],
        )


def test_a_closed_turn_keeps_denying_mutation(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)
    store.complete_turn(turn_id="turn-change", status="success")

    turn = store.get_turn("turn-change")
    decision = _admit(store, "write_file", {"path": str(repo / "src" / "app.py"), "content": "x"})

    assert turn is not None
    assert turn["state"] == "completed"
    assert decision.allowed is False
    assert decision.action == "turn-closed"


def test_an_unbindable_call_on_a_seeded_task_denies_mutation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id="task-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )

    write = store.admit_without_turn(
        task_id="task-change", session_id="s", tool_name="write_file"
    )
    read = store.admit_without_turn(
        task_id="task-change", session_id="s", tool_name="read_file"
    )
    unseeded = store.admit_without_turn(
        task_id="task-other", session_id="s", tool_name="write_file"
    )

    assert write.allowed is False
    assert write.action == "contract-unbound"
    assert read.allowed is True
    assert unseeded.allowed is True


def test_a_seedless_turn_without_a_lock_stays_audit_only(tmp_path: Path) -> None:
    # D-S3-6 is undecided: the pre-lock stage and the seed API ship now, but
    # a lane with no seed wiring is not switched to enforced by default.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.start_turn(
        turn_id="turn-change",
        session_id="s",
        task_id="task-none",
        user_message=CHANGE_MESSAGE,
    )

    decision = _admit(store, "write_file", {"path": str(repo / "src" / "app.py"), "content": "x"})

    assert decision.allowed is True
    assert decision.action == "not-enforced"


@pytest.mark.parametrize(
    ("message", "classified"),
    [
        ("現状を調査してレポートして", "audit-only"),
        ("全面的に見直して", "audit-only"),
        ("この設計はどうなっていますか？", "audit-only"),
        ("gateway サービスを再起動して", "bounded-operation"),
        ("この差分をcommitしてpushしてください", "repository-closeout"),
    ],
)
def test_a_seeded_task_is_enforced_whatever_the_message_classifies_as(
    tmp_path: Path, message: str, classified: str
) -> None:
    # The seed is the authority. A later message of the same task must not be
    # able to move the turn into a class that enforces less, and the closeout
    # class in particular carries permissions the seed does not.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    intent = store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=message,
    )

    turn = store.get_turn("turn-change")
    write = _admit(store, "write_file", {"path": "secrets.txt", "content": "x"})
    push = _admit(
        store, "terminal", {"command": "git push origin main", "workdir": str(repo)}
    )

    assert classify_task(message).task_class == classified
    assert intent.task_class == "artifact-change"
    assert turn is not None
    assert turn["state"] == "locked"
    assert turn["classified_class"] == classified
    assert turn["allow_push"] == 0
    assert write.allowed is False
    assert write.action == "write-scope"
    assert push.allowed is False


def test_every_message_of_a_task_gets_its_own_turn(tmp_path: Path) -> None:
    # A turn key that is only the task id collapses the task into one row:
    # the first message's class, wall clock, and budgets would then stand for
    # the whole task and no later turn would exist to enforce.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    runtime.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    common = {"task_id": "task-change", "session_id": "session-change"}

    runtime.pre_llm_call(**common, user_message="現状を調査して")
    runtime.pre_llm_call(**common, user_message=CHANGE_MESSAGE)
    with runtime.store._connect() as connection:
        rows = connection.execute(
            "SELECT turn_id, state FROM turns WHERE task_id = 'task-change'"
        ).fetchall()
    blocked = runtime.pre_tool_call(
        **common,
        tool_call_id="write-out",
        tool_name="write_file",
        args={"path": str(repo / "secrets.txt"), "content": "x"},
    )

    assert len(rows) == 2
    assert {str(row["state"]) for row in rows} == {"locked"}
    assert blocked is not None
    assert blocked["action"] == "block"
    uses = runtime.store.contract_scope_uses("task-change")
    assert len(uses) == 2


def test_an_open_enforced_turn_is_not_shadowed_by_a_later_unenforced_turn(
    tmp_path: Path,
) -> None:
    # A contract that is still in force must keep binding the calls of its
    # session. Otherwise a following message that classifies as something
    # narrower silently ends enforcement without closing anything.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id="task-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )
    store.start_turn(
        turn_id="turn-later",
        session_id="session-change",
        task_id="task-unrelated",
        user_message="現状を調査して",
    )

    later = store.get_turn("turn-later")
    bound = store.resolve_turn_id(session_id="session-change")
    decision = store.admit_tool(
        turn_id=bound,
        tool_call_id="shadowed-write",
        tool_name="write_file",
        args={"path": str(repo / "secrets.txt"), "content": "x"},
        session_id="session-change",
    )

    assert later is not None
    assert later["task_class"] == "audit-only"
    assert bound == "turn-change"
    assert decision.allowed is False
    assert decision.action == "write-scope"


def test_the_latest_turn_binds_a_call_even_after_it_closed(tmp_path: Path) -> None:
    store, _ = _seeded_store(tmp_path)
    store.start_turn(
        turn_id="turn-earlier",
        session_id="session-change",
        task_id="task-unrelated",
        user_message="現状を調査して",
    )
    store.finalize_turn(turn_id="turn-change", status="success")

    bound = store.resolve_turn_id(task_id="task-change")

    assert bound == "turn-change"


def test_a_closed_turn_keeps_denying_mutation_without_an_explicit_turn_id(
    tmp_path: Path,
) -> None:
    # The refusal of a closed turn only holds if the closed turn stays
    # reachable: falling back to an older open turn, or to no turn at all,
    # turns explicit completion into a way back to unenforced.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-old",
        session_id="session-change",
        task_id="task-change",
        user_message="現状を調査して",
    )
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )
    store.lock_turn(
        turn_id="turn-change",
        repositories=[],
        worktrees=[str(repo)],
        branches=["main"],
        write_paths=["src/*.py"],
    )
    store.finalize_turn(turn_id="turn-change", status="success")

    bound = store.resolve_turn_id(task_id="task-change", session_id="session-change")
    decision = store.admit_tool(
        turn_id=bound,
        tool_call_id="after-close",
        tool_name="write_file",
        args={"path": str(repo / "secrets.txt"), "content": "x"},
        task_id="task-change",
        session_id="session-change",
    )

    assert bound == "turn-change"
    assert decision.allowed is False
    assert decision.action == "turn-closed"


def test_a_self_lock_keeps_enforcing_the_next_turn_of_the_same_task(
    tmp_path: Path,
) -> None:
    # The audit hooks can fire per LLM call rather than per user turn, so a
    # lock that expired with its turn would leave the next call unenforced.
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    common = {"task_id": "task-self", "session_id": "session-self"}
    runtime.pre_llm_call(**common, turn_id="turn-one", user_message=CHANGE_MESSAGE)
    runtime.handle_scope_gate(
        {
            "action": "lock",
            "targets": {"worktrees": [str(repo)], "write_paths": ["src/*.py"]},
        },
        **common,
        turn_id="turn-one",
    )

    runtime.pre_llm_call(**common, turn_id="turn-two", user_message=CHANGE_MESSAGE)
    second = runtime.store.get_turn("turn-two")
    blocked = runtime.pre_tool_call(
        **common,
        turn_id="turn-two",
        tool_call_id="write-out",
        tool_name="write_file",
        args={"path": str(repo / "secrets.txt"), "content": "x"},
    )
    allowed = runtime.pre_tool_call(
        **common,
        turn_id="turn-two",
        tool_call_id="write-in",
        tool_name="write_file",
        args={"path": str(repo / "src" / "app.py"), "content": "x"},
    )

    assert second is not None
    assert second["state"] == "locked"
    assert second["contract_origin"] == "self"
    assert blocked is not None
    assert allowed is None


def test_an_unbindable_call_is_fail_closed_without_a_task_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )

    by_session = store.admit_without_turn(
        task_id="", session_id="session-change", tool_name="write_file"
    )
    unknown_turn = store.admit_tool(
        turn_id="never-registered",
        tool_call_id="ghost",
        tool_name="write_file",
        args={"path": "src/app.py", "content": "x"},
        session_id="session-change",
    )
    unrelated = store.admit_without_turn(
        task_id="", session_id="other-session", tool_name="write_file"
    )

    assert by_session.allowed is False
    assert by_session.action == "contract-unbound"
    assert unknown_turn.allowed is False
    assert unknown_turn.action == "contract-unbound"
    assert unrelated.allowed is True


def test_a_clean_session_end_closes_an_enforced_turn(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    runtime.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    common = {
        "turn_id": "turn-change",
        "task_id": "task-change",
        "session_id": "session-change",
    }
    runtime.pre_llm_call(**common, user_message=CHANGE_MESSAGE)

    runtime.post_llm_call(**common)
    open_turn = runtime.store.get_turn("turn-change")
    runtime.on_session_end(**common, completed=True, failed=False, interrupted=False)
    closed = runtime.store.get_turn("turn-change")
    blocked = runtime.pre_tool_call(
        **common,
        tool_call_id="write-after-end",
        tool_name="write_file",
        args={"path": str(repo / "src" / "app.py"), "content": "x"},
    )

    assert open_turn is not None
    assert open_turn["completion_status"] is None
    assert closed is not None
    assert closed["state"] == "completed"
    assert closed["completion_status"] == "success"
    assert blocked is not None
    assert "turn-closed" in blocked["message"]


def test_the_unlocked_stages_are_bounded_by_the_class_budget(tmp_path: Path) -> None:
    # Replacing unlimited pre-lock access with a default deny is only a
    # bounded stage if the stage carries the class ceilings too.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    for turn_id, message in (("turn-pre", CHANGE_MESSAGE),):
        store.start_turn(
            turn_id=turn_id,
            session_id="s",
            task_id="task-pre",
            user_message=message,
        )
    with store._connect() as connection:
        connection.execute(
            "UPDATE turns SET started_at = 1.0 WHERE turn_id = 'turn-pre'"
        )

    pre_lock = _admit(
        store, "read_file", {"path": str(repo / "src" / "app.py")}, turn_id="turn-pre"
    )

    store_denied, denied_repo = _seeded_store(
        tmp_path / "denied", branch="not-the-checked-out-branch"
    )
    with store_denied._connect() as connection:
        connection.execute(
            "UPDATE turns SET tool_count = 999 WHERE turn_id = 'turn-change'"
        )
    mutation_denied = _admit(
        store_denied, "read_file", {"path": str(denied_repo / "src" / "app.py")}
    )

    assert pre_lock.allowed is False
    assert pre_lock.action == "wall-budget"
    assert mutation_denied.allowed is False
    assert mutation_denied.action == "tool-budget"


def test_a_transient_repository_probe_failure_stays_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A verification that could not run is not a verification that failed:
    # pinning the turn would make one timeout unrecoverable.
    import scope_gate

    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db")
    store.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    calls: list[int] = []
    real = scope_gate._validated_worktree_branches

    def flaky(worktrees: list[str]) -> dict[str, str]:
        calls.append(1)
        if len(calls) == 1:
            raise scope_gate.WorktreeProbeError("probe timed out")
        return real(worktrees)

    monkeypatch.setattr(scope_gate, "_validated_worktree_branches", flaky)

    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )
    unregistered = store.get_turn("turn-change")
    unbound = store.admit_without_turn(
        task_id="task-change", session_id="session-change", tool_name="write_file"
    )
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )
    recovered = store.get_turn("turn-change")

    assert unregistered is None
    assert unbound.allowed is False
    assert recovered is not None
    assert recovered["state"] == "locked"


def test_a_self_lock_is_refused_while_the_task_carries_a_seed(tmp_path: Path) -> None:
    # The ceiling must be checked where the lock happens, not inferred from
    # the turn already being locked: that inference rests on the host wiring
    # an identifier and on the order the records were written.
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-change",
        user_message=CHANGE_MESSAGE,
    )
    store.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/app.py"],
    )

    with pytest.raises(ValueError, match="assigned contract seed"):
        store.lock_turn(
            turn_id="turn-change",
            repositories=[],
            worktrees=[str(repo)],
            branches=["main"],
            write_paths=["**"],
            test_paths=["tests/**"],
            execution=["focused-test"],
        )


def test_the_contract_carries_git_write_permission(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, git_write=[])
    full_store, full_repo = _seeded_store(tmp_path / "full")

    stage = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )
    commit = _admit(
        store, "terminal", {"command": "git commit -m msg", "workdir": str(repo)}
    )
    default_stage = _admit(
        full_store,
        "terminal",
        {"command": "git add src/app.py", "workdir": str(full_repo)},
    )

    assert stage.allowed is False
    assert stage.action == "git-write-forbidden"
    assert commit.allowed is False
    assert commit.action == "git-write-forbidden"
    assert default_stage.allowed is True


def test_a_contract_without_the_git_write_field_denies_git_writes(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path)
    with store._connect() as connection:
        row = connection.execute(
            "SELECT contract_json FROM turns WHERE turn_id = 'turn-change'"
        ).fetchone()
        contract = json.loads(row["contract_json"])
        contract["actions"].pop("git_write")
        connection.execute(
            "UPDATE turns SET contract_json = ? WHERE turn_id = 'turn-change'",
            (json.dumps(contract),),
        )

    decision = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )

    assert decision.allowed is False
    assert decision.action == "git-write-unspecified"


def test_the_self_lock_target_list_is_derived_not_declared(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = GateStore(tmp_path / "scope.db", enforce_artifact_change_pre_lock=True)
    store.start_turn(
        turn_id="turn-change",
        session_id="s",
        task_id="task-self",
        user_message=CHANGE_MESSAGE,
    )

    contract = store.lock_turn(
        turn_id="turn-change",
        repositories=["/somewhere/else", "/another/place"],
        worktrees=[str(repo)],
        branches=["main"],
        write_paths=["src/*.py"],
    )

    assert contract["targets"]["repositories"] == [str(repo.resolve())]


def test_expansion_review_of_an_already_permitted_action_costs_no_budget(
    tmp_path: Path,
) -> None:
    store, _ = _seeded_store(tmp_path)
    for index in range(3):
        already = store.request_expansion(
            turn_id="turn-change",
            tool_name="write_file",
            args={"path": "src/app.py", "content": str(index)},
            reason="the normalizer did not recognize this write",
        )
        assert already["ok"] is True
        assert already["reviewer"] == "deterministic-allow"

    def approve(payload: dict[str, object]) -> dict[str, object]:
        return {"allow": True, "reason": "indispensable"}

    outside = store.request_expansion(
        turn_id="turn-change",
        tool_name="write_file",
        args={"path": "docs/other.md", "content": "x"},
        reason="a genuine expansion",
        judge=approve,
    )

    assert outside["ok"] is True
    assert outside["reviewer"] == "judge"


def test_expired_contract_records_and_permits_are_purged(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)
    store.request_expansion(
        turn_id="turn-change",
        tool_name="write_file",
        args={"path": "docs/other.md", "content": "x"},
        reason="r",
    )
    with store._connect() as connection:
        connection.execute("UPDATE turns SET started_at = 1.0")
        connection.execute("UPDATE contract_seeds SET created_at = 1.0")

    store.purge_expired(now=31 * 24 * 60 * 60 + 1, retention_days=30)

    with store._connect() as connection:
        remaining = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("turns", "contract_seeds", "expansion_permits")
        }

    assert remaining == {"turns": 0, "contract_seeds": 0, "expansion_permits": 0}


def test_a_declared_nested_container_is_never_skipped(tmp_path: Path) -> None:
    listed = collect_write_targets(
        "multi_edit", {"path": "src/a.py", "edits": [{"path": "src/b.py"}]}
    )

    assert set(listed) == {"src/a.py", "src/b.py"}
    for args in (
        {"path": "src/a.py", "edits": {"0": {"path": "secrets.txt"}}},
        {"path": "src/a.py", "edits": ["secrets.txt"]},
        {"path": "src/a.py", "edits": [{"content": "x"}]},
    ):
        with pytest.raises(PathRejected) as exc:
            collect_write_targets("multi_edit", args)
        assert exc.value.code in {"target-shape", "target-missing"}


def test_the_read_tool_allowlist_matches_the_running_tool_vocabulary() -> None:
    # A name that no tool answers to is not a widening, but it reads as
    # coverage that does not exist; a real read tool that is missing is a
    # false deny in a class that must have none.
    vocabulary = _hermes_tool_vocabulary()

    assert ARTIFACT_READ_TOOLS <= vocabulary
    assert {
        "read_file",
        "search_files",
        "session_search",
        "skill_view",
        "tool_describe",
    } <= ARTIFACT_READ_TOOLS


def test_reads_of_the_agents_own_configuration_plane_touch_no_write_boundary(
    tmp_path: Path,
) -> None:
    # skill_view (a skill definition) and tool_describe (a tool schema) read
    # the agent's own configuration and metadata plane. Neither names a
    # repository path nor an execution boundary, so the first layer has no
    # destination to bound and the rationale holds in every stage - which is
    # also the full reach of this allow-direction change (isolated live-run
    # finding, 2026-08-24).
    locked, _ = _seeded_store(tmp_path / "locked")
    pre_lock = GateStore(
        tmp_path / "pre.db", enforce_artifact_change_pre_lock=True
    )
    pre_lock.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-pre",
        user_message=CHANGE_MESSAGE,
    )
    unbound, _ = _seeded_store(tmp_path / "unbound")

    for tool_name in ("skill_view", "tool_describe"):
        in_locked = _admit(locked, tool_name, {})
        before_lock = _admit(pre_lock, tool_name, {})
        without_turn = unbound.admit_without_turn(
            task_id="task-change", session_id="session-change", tool_name=tool_name
        )

        assert in_locked.allowed is True, tool_name
        assert in_locked.action == "inspect-locked-target", tool_name
        assert before_lock.allowed is True, tool_name
        assert before_lock.action == "inspect-before-lock", tool_name
        assert without_turn.allowed is True, tool_name
        assert without_turn.action == "inspect-unbound", tool_name

    assert pre_lock.get_turn("turn-change")["state"] == "pre-lock"
    # The writing neighbour in the same vocabulary group stays out: it can
    # write skill definitions, which are repository files. tool_call carries
    # another tool's invocation, which the first layer does not bound either.
    for excluded in ("skill_manage", "tool_call"):
        assert excluded in _hermes_tool_vocabulary(), excluded
        assert excluded not in ARTIFACT_READ_TOOLS, excluded


def test_the_admission_dispatch_is_the_only_class_branch() -> None:
    assert decision_for("artifact-change") is not None
    assert decision_for("repository-closeout") is not None
    assert decision_for("audit-only") is None
    assert locked_admission_for("artifact-change") is not None


def test_the_prelock_stage_has_a_configuration_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(PRELOCK_ENFORCEMENT_ENV, "1")
    enabled = ScopeGatePluginRuntime(tmp_path / "on.db")
    monkeypatch.setenv(PRELOCK_ENFORCEMENT_ENV, "0")
    disabled = ScopeGatePluginRuntime(tmp_path / "off.db")
    monkeypatch.delenv(PRELOCK_ENFORCEMENT_ENV)
    default = ScopeGatePluginRuntime(tmp_path / "default.db")

    assert prelock_enforcement_setting() is None
    assert enabled.store.enforce_artifact_change_pre_lock is True
    assert disabled.store.enforce_artifact_change_pre_lock is False
    assert default.store.enforce_artifact_change_pre_lock is False


def test_admission_under_write_contention_returns_a_decision(tmp_path: Path) -> None:
    # Admission holds the write lock across the repository probe, so a
    # concurrent call has to wait rather than surface a store error: an
    # exception here is not a verdict, and only one of the two hook paths
    # has a fail-closed boundary of its own.
    import threading

    store, repo = _seeded_store(tmp_path)
    holder_ready = threading.Event()
    release = threading.Event()

    def hold_write_lock() -> None:
        with store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE turns SET tool_count = tool_count WHERE turn_id = 'turn-change'"
            )
            holder_ready.set()
            release.wait(5)
            connection.commit()

    holder = threading.Thread(target=hold_write_lock)
    holder.start()
    try:
        holder_ready.wait(5)
        release.set()
        decision = _admit(
            store,
            "terminal",
            {"command": "git commit -m msg", "workdir": str(repo)},
        )
    finally:
        release.set()
        holder.join(10)

    assert decision.allowed is True, decision


def test_the_admission_boundary_blocks_when_the_gate_itself_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")

    def broken(**kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(runtime.store, "resolve_turn_id", broken)
    blocked = runtime.pre_tool_call(
        turn_id="turn-change",
        task_id="task-change",
        session_id="session-change",
        tool_call_id="write",
        tool_name="write_file",
        args={"path": str(repo / "src" / "app.py"), "content": "x"},
    )
    control = runtime.handle_scope_gate(
        {"action": "lock", "targets": {"worktrees": [str(repo)]}},
        task_id="task-change",
        session_id="session-change",
    )

    assert blocked is not None
    assert blocked["action"] == "block"
    assert "admission-validator-error" in blocked["message"]
    assert control["ok"] is False


def test_a_locked_turn_survives_an_intermediate_audit_hook(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    runtime.record_contract_seed(
        task_id="task-change",
        session_id="session-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )
    context = runtime.pre_llm_call(
        turn_id="turn-change",
        task_id="task-change",
        session_id="session-change",
        user_message=CHANGE_MESSAGE,
    )

    runtime.post_llm_call(
        turn_id="turn-change", task_id="task-change", session_id="session-change"
    )
    blocked = runtime.pre_tool_call(
        turn_id="turn-change",
        task_id="task-change",
        session_id="session-change",
        tool_call_id="write-1",
        tool_name="write_file",
        args={"path": str(repo / "src" / "app.py"), "content": "x"},
    )
    turn = runtime.store.get_turn("turn-change")

    assert context is not None
    assert "artifact-change" in context["context"]
    assert turn is not None
    assert turn["state"] == "locked"
    assert turn["completion_status"] is None
    assert blocked is None


def test_the_seed_api_is_not_part_of_the_agent_facing_control_tool(
    tmp_path: Path,
) -> None:
    # The executing agent must not be able to create or widen its own seed,
    # so seeding is a store/runtime API and never a control-tool action.
    runtime = ScopeGatePluginRuntime(tmp_path / "scope.db")
    module = sys.modules[ScopeGatePluginRuntime.__module__]
    schema = getattr(module, "_SCOPE_GATE_SCHEMA", None)
    if schema is None:  # the tool schema lives in the plugin package entry
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "scope_gate_plugin_entry", ROOT / "__init__.py"
        )
        assert spec is not None and spec.loader is not None
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        schema = entry._SCOPE_GATE_SCHEMA
    actions = schema["parameters"]["properties"]["action"]["enum"]

    refused = runtime.handle_scope_gate(
        {"action": "seed", "targets": {"worktrees": [str(tmp_path)]}},
        task_id="task-change",
        session_id="session-change",
    )

    assert sorted(actions) == ["complete", "lock", "review"]
    assert refused["ok"] is False


def test_the_shell_hook_path_is_fail_closed_for_a_seeded_task(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    state = tmp_path / "scope.db"
    store = GateStore(state)
    store.record_contract_seed(
        task_id="task-change",
        worktree=str(repo),
        branch="main",
        write_paths=["src/*.py"],
    )

    directive = validate_shell_payload(
        {
            "hook_event_name": "pre_tool_call",
            "session_id": "session-change",
            "tool_name": "write_file",
            "tool_input": {"path": str(repo / "secrets.txt"), "content": "x"},
            "extra": {"task_id": "task-change"},
        },
        state_path=state,
    )

    assert directive.get("action") == "block"


# ---------------------------------------------------------------------------
# First layer: write boundary
# ---------------------------------------------------------------------------


def test_writes_inside_the_locked_scope_are_admitted(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)

    absolute = _admit(store, "write_file", {"path": str(repo / "src" / "app.py"), "content": "x"})
    relative = _admit(store, "patch", {"path": "src/app.py", "old_string": "a", "new_string": "b"})
    test_asset = _admit(store, "write_file", {"path": "tests/test_app.py", "content": "x"})

    for decision in (absolute, relative, test_asset):
        assert decision.allowed is True, decision
        assert decision.action == "write-in-scope-change"


@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        ("write_file", {"path": "secrets.txt", "content": "x"}),
        ("write_file", {"path": "src/deep/nested.py", "content": "x"}),
        ("patch", {"path": "docs/other.md", "old_string": "a", "new_string": "b"}),
        ("move_file", {"source": "src/app.py", "destination": "secrets.txt"}),
        ("multi_edit", {"edits": [{"path": "src/app.py"}, {"path": "secrets.txt"}]}),
        ("delete_file", {"path": "tests/other_test.py"}),
    ],
)
def test_writes_outside_the_locked_scope_are_denied(
    tmp_path: Path, tool_name: str, args: dict[str, object]
) -> None:
    store, _ = _seeded_store(tmp_path)

    decision = _admit(store, tool_name, args)

    assert decision.allowed is False
    assert decision.action in {"write-scope", "target-closed", "target-escape"}


@pytest.mark.parametrize(
    ("tool_name", "args_template"),
    [
        ("write_file", {"path": "src/alias.py", "content": "x"}),
        ("terminal", {"command": "git add src/alias.py"}),
        ("terminal", {"command": "pytest src/alias.py"}),
    ],
)
def test_an_in_scope_name_resolving_out_of_scope_is_denied_on_every_layer(
    tmp_path: Path, tool_name: str, args_template: dict[str, object]
) -> None:
    # The first-layer write catalogue, the staging range, and the
    # second-layer verification target all have to match on the resolved
    # destination, not on the notation that was written.
    store, repo = _seeded_store(tmp_path, execution=["focused-test"])
    (repo / "src" / "alias.py").symlink_to(repo / "secrets.txt")
    args = dict(args_template)
    if tool_name == "terminal":
        args["workdir"] = str(repo)

    decision = _admit(store, tool_name, args)

    assert decision.allowed is False, (tool_name, args, decision)
    assert decision.action in {"write-scope", "stage-scope", "execution-target"}


def test_a_name_resolving_outside_the_worktree_is_denied_on_every_layer(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path, execution=["focused-test"])
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escaped.py").write_text("x\n", encoding="utf-8")
    (repo / "src" / "away.py").symlink_to(outside / "escaped.py")

    write = _admit(store, "write_file", {"path": "src/away.py", "content": "x"})
    stage = _admit(
        store, "terminal", {"command": "git add src/away.py", "workdir": str(repo)}
    )
    verify = _admit(
        store, "terminal", {"command": "pytest src/away.py", "workdir": str(repo)}
    )

    for decision in (write, stage, verify):
        assert decision.allowed is False, decision
        assert decision.action == "target-escape"


def test_an_equivalent_spelling_of_the_locked_worktree_is_not_falsely_denied(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(repo, target_is_directory=True)

    write = _admit(store, "write_file", {"path": str(alias / "src" / "app.py"), "content": "x"})
    stage = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(alias)}
    )

    assert write.allowed is True, write
    assert write.action == "write-in-scope-change"
    assert stage.allowed is True, stage


def test_staging_a_directory_is_denied_even_when_a_pattern_matches_its_name(
    tmp_path: Path,
) -> None:
    # A pattern can match a directory name while rejecting the files beneath
    # it, so a directory pathspec would stage what the write layer denies.
    store, repo = _seeded_store(
        tmp_path, write_paths=["**/tests", "src/*.py"], test_paths=[]
    )

    directory = _admit(
        store, "terminal", {"command": "git add tests", "workdir": str(repo)}
    )
    contained = _admit(
        store,
        "terminal",
        {"command": "git add tests/test_app.py", "workdir": str(repo)},
    )
    subtree = _admit(
        store, "terminal", {"command": "git add src", "workdir": str(repo)}
    )

    assert directory.allowed is False
    assert directory.action == "stage-directory"
    assert contained.allowed is False
    assert subtree.allowed is False
    assert subtree.action == "stage-directory"


def test_staging_a_deletion_of_an_in_scope_file_is_not_falsely_denied(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path)
    (repo / "src" / "app.py").unlink()

    decision = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )

    assert decision.allowed is True, decision
    assert decision.action == "stage-in-scope-change"


def test_unlisted_terminal_argument_fields_are_denied(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)

    decision = _admit(
        store,
        "terminal",
        {
            "command": "git commit -m msg",
            "workdir": str(repo),
            "environment": {"PATH": "/elsewhere"},
        },
    )

    assert decision.allowed is False
    assert decision.action == "terminal-argument-unlisted"


def test_the_ordinary_change_then_verify_then_commit_flow_is_not_blocked(
    tmp_path: Path,
) -> None:
    # The flow the improvement cycle expects of a worker: create a source
    # file and its test, run the focused verification, stage both, commit.
    store, repo = _seeded_store(
        tmp_path,
        write_paths=["src/*.py"],
        test_paths=["tests/test_*.py"],
        execution=["focused-test"],
    )
    steps = [
        ("write_file", {"path": "src/feature.py", "content": "x"}),
        ("write_file", {"path": "tests/test_feature.py", "content": "y"}),
        ("read_file", {"path": str(repo / "src" / "feature.py")}),
        ("terminal", {"command": "pytest -q tests/test_feature.py", "workdir": str(repo)}),
        ("terminal", {"command": "git add src/feature.py tests/test_feature.py", "workdir": str(repo)}),
        ("terminal", {"command": "git commit -m 'add feature'", "workdir": str(repo)}),
    ]

    for tool_name, args in steps:
        decision = _admit(store, tool_name, args)
        assert decision.allowed is True, (tool_name, args, decision)


def test_test_assets_need_their_own_declared_scope(tmp_path: Path) -> None:
    store, _ = _seeded_store(tmp_path, test_paths=[])

    decision = _admit(store, "write_file", {"path": "tests/test_app.py", "content": "x"})

    assert decision.allowed is False
    assert decision.action == "write-scope"


def test_unknown_mutation_tools_fall_through_to_expansion_review(tmp_path: Path) -> None:
    store, _ = _seeded_store(tmp_path)

    for tool_name in ("delegate_task", "execute_code", "some_unlisted_tool"):
        decision = _admit(store, tool_name, {"path": "src/app.py"}, call_id=tool_name)
        assert decision.allowed is False, tool_name
        assert decision.action == "expansion-required", tool_name


def test_staging_is_limited_to_named_in_scope_paths(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)

    allowed = _admit(
        store,
        "terminal",
        {"command": "git add src/app.py tests/test_app.py", "workdir": str(repo)},
    )

    assert allowed.allowed is True
    assert allowed.action == "stage-in-scope-change"


@pytest.mark.parametrize(
    "command",
    [
        "git add .",
        "git add -A",
        "git add --all",
        "git add",
        "git add src/*.py",
        "git add secrets.txt",
        "git add src/deep/nested.py",
        "git add --pathspec-from-file=list.txt",
        "git add :/",
    ],
)
def test_bulk_or_out_of_scope_staging_is_denied(tmp_path: Path, command: str) -> None:
    store, repo = _seeded_store(tmp_path)

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})

    assert decision.allowed is False, command
    assert decision.action.startswith("stage-") or decision.action in {
        "write-scope",
        "target-closed",
    }


def test_a_local_commit_with_an_explicit_message_is_admitted(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)

    short_form = _admit(
        store, "terminal", {"command": "git commit -m 'fix login'", "workdir": str(repo)}
    )
    long_form = _admit(
        store, "terminal", {"command": "git commit --message=fix -q", "workdir": str(repo)}
    )

    assert short_form.allowed is True
    assert short_form.action == "commit-in-scope-change"
    assert long_form.allowed is True


@pytest.mark.parametrize(
    "command",
    [
        "git commit",
        "git commit -m",
        "git commit -a -m msg",
        "git commit --amend -m msg",
        "git commit --no-verify -m msg",
        "git commit -n -m msg",
        "git commit --fixup=HEAD",
        "git commit -am msg",
        "git push origin main",
        "git reset --hard HEAD",
        "git checkout other",
        # `git status --short` used to be denied here. D-S3-7 admits the
        # read-only Git subset, so the read cases moved to the read-set
        # tests below and this list keeps only the write forms.
    ],
)
def test_commit_arguments_and_other_git_writes_are_bounded(
    tmp_path: Path, command: str
) -> None:
    store, repo = _seeded_store(tmp_path)

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})

    assert decision.allowed is False, command


def test_git_writes_are_denied_when_the_branch_binding_drifts(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)
    subprocess.run(
        ["git", "-C", str(repo), "checkout", "-q", "-b", "moved"],
        check=True,
        capture_output=True,
        text=True,
    )

    decision = _admit(
        store, "terminal", {"command": "git commit -m msg", "workdir": str(repo)}
    )

    assert decision.allowed is False
    assert decision.action == "target-drift"


def test_terminal_work_outside_the_locked_worktree_is_denied(tmp_path: Path) -> None:
    store, _ = _seeded_store(tmp_path)
    other = tmp_path / "other"
    _init_git_repo(other)

    decision = _admit(
        store, "terminal", {"command": "git commit -m msg", "workdir": str(other)}
    )

    assert decision.allowed is False
    # Refused on the workdir, before the command is tokenized -- so this is
    # the workdir code and not the write-target code, even though the command
    # itself would have been a commit.
    assert decision.action == "workdir-outside"


def test_composed_and_backgrounded_terminal_calls_are_denied(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, execution=["focused-test"])

    composed = _admit(
        store,
        "terminal",
        {"command": "git add src/app.py; git commit -m msg", "workdir": str(repo)},
        call_id="composed",
    )
    backgrounded = _admit(
        store,
        "terminal",
        {"command": "git commit -m msg", "workdir": str(repo), "background": True},
        call_id="backgrounded",
    )

    assert composed.allowed is False
    assert composed.action == "compound-command"
    assert backgrounded.allowed is False
    assert backgrounded.action == "background-forbidden"


# ---------------------------------------------------------------------------
# Second layer: opted-in verification
# ---------------------------------------------------------------------------


def test_execution_is_denied_entirely_without_an_opt_in(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, execution=[])

    for command in ("pytest tests/test_app.py", "python -m py_compile src/app.py"):
        decision = _admit(
            store, "terminal", {"command": command, "workdir": str(repo)}, call_id=command
        )
        assert decision.allowed is False, command
        assert decision.action == "execution-not-opted-in", command


def test_an_opted_in_template_admits_named_file_targets(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, execution=["focused-test", "syntax-check"])

    focused = _admit(
        store, "terminal", {"command": "pytest tests/test_app.py", "workdir": str(repo)}
    )
    module_form = _admit(
        store,
        "terminal",
        {"command": "python -m pytest tests/test_app.py", "workdir": str(repo)},
    )
    syntax = _admit(
        store,
        "terminal",
        {"command": "python -m py_compile src/app.py", "workdir": str(repo)},
    )

    assert focused.allowed is True
    assert focused.action == "run-focused-test"
    assert module_form.allowed is True
    assert syntax.allowed is True
    assert syntax.action == "check-target-syntax"


@pytest.mark.parametrize(
    "command",
    [
        # options outside the allowlist, in both joined and separated form
        "pytest --rootdir=/elsewhere tests/test_app.py",
        "pytest --rootdir /elsewhere tests/test_app.py",
        "pytest -c other.ini tests/test_app.py",
        "pytest -p someplugin tests/test_app.py",
        "pytest --basetemp=/elsewhere tests/test_app.py",
        "pytest --override-ini=x=y tests/test_app.py",
        "pytest --confcutdir=/ tests/test_app.py",
        "pytest --import-mode=importlib tests/test_app.py",
        "pytest -xk something tests/test_app.py",
        # no explicit target, directory-wide target, or target outside scope
        "pytest",
        "pytest tests",
        "pytest tests/",
        "pytest src/deep/nested.py",
        "pytest ../outside/test_x.py",
        "pytest tests/*.py",
        # target taken from somewhere other than the argument list
        "pytest -",
        "python -m py_compile -",
        # a template that was not opted in
        "python -m unittest tests/test_app.py",
    ],
)
def test_verification_arguments_are_scanned_in_full_and_default_to_deny(
    tmp_path: Path, command: str
) -> None:
    store, repo = _seeded_store(tmp_path, execution=["focused-test", "syntax-check"])

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})

    assert decision.allowed is False, command
    assert decision.action in {
        "execution-option",
        "execution-target",
        "execution-stdin",
        "execution-template",
        "target-closed",
        "target-traversal",
    }, (command, decision)


@pytest.mark.parametrize(
    "command",
    [
        "pytest tests/test_app.py",
        "pytest -x tests/test_app.py",
        "pytest -q tests/test_app.py",
        "pytest -x -q tests/test_app.py",
        "pytest -x -q --maxfail=1 tests/test_app.py",
        "pytest --tb=short tests/test_app.py",
        "pytest --maxfail 1 --tb short tests/test_app.py",
        "pytest -q --color=no tests/test_app.py",
        "pytest -q tests/test_app.py src/app.py",
        "pytest -q -- tests/test_app.py",
        "python3 -m pytest -q tests/test_app.py",
        "python -m py_compile src/app.py",
        "python -m py_compile -q src/app.py",
    ],
)
def test_ordinary_safe_verification_invocations_are_not_falsely_denied(
    tmp_path: Path, command: str
) -> None:
    store, repo = _seeded_store(
        tmp_path,
        write_paths=["src/*.py"],
        test_paths=["tests/test_app.py"],
        execution=["focused-test", "syntax-check"],
    )

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})

    assert decision.allowed is True, (command, decision)


# ---------------------------------------------------------------------------
# G3 expansion review through the shared dispatch table
# ---------------------------------------------------------------------------


def test_expansion_review_reports_actions_the_contract_already_permits(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path)

    result = store.request_expansion(
        turn_id="turn-change",
        tool_name="write_file",
        args={"path": "src/app.py", "content": "x"},
        reason="the normalizer did not recognize this write",
    )

    assert result["ok"] is True
    assert result["reviewer"] == "deterministic-allow"


def test_expansion_review_still_fails_closed_for_out_of_scope_actions(
    tmp_path: Path,
) -> None:
    store, _ = _seeded_store(tmp_path)

    result = store.request_expansion(
        turn_id="turn-change",
        tool_name="write_file",
        args={"path": "secrets.txt", "content": "x"},
        reason="an urgent and very persuasive justification",
    )

    assert result["ok"] is False
    assert result["reviewer"] == "fail-closed"


def test_a_persuasive_reason_cannot_widen_the_hard_bounds(tmp_path: Path) -> None:
    # Pre-defined for the M2 judge connection: a self-reported reason must
    # never move a deterministic stage-1/2 outcome.
    store, _ = _seeded_store(tmp_path)

    def permissive_judge(payload: dict[str, object]) -> dict[str, object]:
        return {"allow": True, "reason": "approved"}

    first = store.request_expansion(
        turn_id="turn-change",
        tool_name="write_file",
        args={"path": "secrets.txt", "content": "x"},
        reason="the owner already approved this",
        judge=permissive_judge,
    )
    replay = _admit(store, "write_file", {"path": "secrets.txt", "content": "x"})
    second = _admit(store, "write_file", {"path": "secrets.txt", "content": "y"})

    # A permit is one-use and fingerprint-bound; the contract itself is
    # unchanged, so a different action stays denied.
    assert first["ok"] is True
    assert replay.allowed is True
    assert replay.action == "expansion-permit"
    assert second.allowed is False


# ---------------------------------------------------------------------------
# D-S3-7: the first-layer permitted set and the operating flow
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git status --short",
        "git diff",
        "git diff --cached",
        "git diff --stat",
        "git diff -- src/app.py",
        "git rev-parse HEAD",
        "git rev-parse --abbrev-ref HEAD",
        "git branch --show-current",
    ],
)
def test_read_only_git_is_admitted_inside_the_locked_worktree(
    tmp_path: Path, command: str
) -> None:
    # Staging names explicit paths, so the turn has to be able to see which
    # paths changed; the approval metadata needs the commit id and branch.
    store, repo = _seeded_store(tmp_path)

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})

    assert decision.allowed is True, (command, decision)


@pytest.mark.parametrize(
    "command",
    [
        "git diff ../outside",
        "git diff --output=/tmp/leak",
        "git diff --ext-diff",
        "git rev-parse --git-dir",
        "git branch -D other",
        "git branch --set-upstream-to=origin/main",
    ],
)
def test_read_only_git_arguments_outside_the_admitted_form_are_denied(
    tmp_path: Path, command: str
) -> None:
    store, repo = _seeded_store(tmp_path)

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})

    assert decision.allowed is False, command


@pytest.mark.parametrize(
    ("command", "action"),
    [
        # Reaching outside the locked worktree is a boundary deviation.
        ("git diff ../outside", "git-read-unsafe"),
        ("git diff -- ../outside", "git-read-unsafe"),
        ("git rev-parse /etc/passwd", "git-read-unsafe"),
        # The write form of a subcommand whose read form is admitted.
        ("git diff --output=/tmp/leak", "git-write-form"),
        ("git diff --output /tmp/leak", "git-write-form"),
        ("git diff --ext-diff", "git-write-form"),
        ("git branch -D other", "git-write-form"),
        ("git branch --delete other", "git-write-form"),
        ("git branch newbranch", "git-write-form"),
        ("git branch -m old new", "git-write-form"),
        ("git branch --set-upstream-to=origin/main", "git-write-form"),
        # A pure read inside the locked worktree whose argument form is not
        # on the allowlist: refused, but not an attempt on any boundary.
        ("git rev-parse --git-dir", "git-read-unbounded"),
        ("git rev-parse --git-common-dir", "git-read-unbounded"),
        ("git rev-parse --show-toplevel", "git-read-unbounded"),
        ("git rev-parse --short HEAD", "git-read-unbounded"),
        ("git rev-parse HEAD~1", "git-read-unbounded"),
        ("git branch", "git-read-unbounded"),
        ("git branch --list", "git-read-unbounded"),
        ("git branch -a", "git-read-unbounded"),
        ("git diff --name-only HEAD~1", "git-read-unbounded"),
        # A revision range carries `..` as an operator between revisions, so
        # it must not be read as a parent-directory reference.
        ("git diff HEAD~1..HEAD", "git-read-unbounded"),
    ],
)
def test_a_refused_read_is_classified_by_the_whole_invocation(
    tmp_path: Path, command: str, action: str
) -> None:
    # The invocation still decides the audit label. What it no longer decides
    # is the budget: every refusal in the Git read lane spends the tool budget
    # and leaves the deny ceiling untouched (D-S3-7 補則).
    store, repo = _seeded_store(tmp_path)

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})
    turn = store.get_turn("turn-change")

    assert decision.allowed is False, command
    assert decision.action == action, command
    assert turn is not None
    assert turn["denied_count"] == 0, command
    assert turn["tool_count"] == 1, command


@pytest.mark.parametrize(
    "command",
    [
        "git remote add other https://example.invalid/x",
        "git remote set-url origin https://example.invalid/x",
        "git remote prune origin",
        "git reflog expire --expire=now --all",
        "git reflog delete HEAD@{0}",
    ],
)
def test_git_families_with_a_write_form_are_not_recognized_as_reads(
    tmp_path: Path, command: str
) -> None:
    # A family whose read form and state-changing form share one subcommand
    # name is not recognized as a read at all, so admission denies it under
    # the unrecognized-subcommand code. That code does not charge the ceiling:
    # an unrecognized subcommand can equally well be a pure read, so the lane
    # is undetermined and the tool budget bounds it (D-S3-7 補則).
    store, repo = _seeded_store(tmp_path)

    decision = _admit(store, "terminal", {"command": command, "workdir": str(repo)})
    turn = store.get_turn("turn-change")

    assert decision.allowed is False, command
    assert decision.action == "git-subcommand", command
    assert turn is not None
    assert turn["denied_count"] == 0, command
    assert turn["tool_count"] == 1, command


def test_read_only_git_reads_outside_the_locked_worktree_are_denied(
    tmp_path: Path,
) -> None:
    store, _ = _seeded_store(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    _init_git_repo(elsewhere)

    decision = _admit(
        store, "terminal", {"command": "git status", "workdir": str(elsewhere)}
    )

    assert decision.allowed is False
    # The workdir refusal carries its own code: it is decided before the
    # command is tokenized, so it cannot mean the write lane the way the
    # write-target codes do (D-S3-7 補則).
    assert decision.action == "workdir-outside"


def test_read_only_git_needs_no_git_write_permission(tmp_path: Path) -> None:
    # Reading the state one is working on is not a write permission, so a
    # contract that hands out none still has to be able to look.
    store, repo = _seeded_store(tmp_path, git_write=[])

    read = _admit(store, "terminal", {"command": "git status", "workdir": str(repo)})
    stage = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )

    assert read.allowed is True
    assert stage.allowed is False
    assert stage.action == "git-write-forbidden"


def test_push_stays_outside_the_first_layer(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path)

    decision = _admit(
        store, "terminal", {"command": "git push origin main", "workdir": str(repo)}
    )

    assert decision.allowed is False
    assert decision.action == "git-subcommand"


@pytest.mark.parametrize("subcommand", sorted(ARTIFACT_GIT_READ_UNADMITTED))
def test_recognized_read_only_git_subcommands_are_refused_without_counting(
    tmp_path: Path, subcommand: str
) -> None:
    # A read-only subcommand this class does not admit is a read refusal, not
    # an attempt on the write boundary, so it must not spend the ceiling that
    # exists to stop boundary probing.
    store, repo = _seeded_store(tmp_path)

    decision = _admit(
        store, "terminal", {"command": f"git {subcommand}", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert decision.allowed is False
    assert decision.action == "git-read-unadmitted"
    assert turn is not None
    assert turn["denied_count"] == 0
    assert turn["tool_count"] == 1


def test_unrecognized_git_subcommands_are_denied_and_bounded_by_tool_budget(
    tmp_path: Path,
) -> None:
    # Admission is unchanged: a history-rewriting subcommand is denied. Only
    # the attribution moved, because the same code answers `git ls-tree`, a
    # pure read, and the lane cannot be told apart from the code alone.
    store, repo = _seeded_store(tmp_path)

    decision = _admit(
        store, "terminal", {"command": "git rebase -i main", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert decision.allowed is False
    assert decision.action == "git-subcommand"
    assert turn is not None
    assert turn["denied_count"] == 0
    assert turn["tool_count"] == 1


@pytest.mark.parametrize("tool_name", sorted(ARTIFACT_WORK_RECORD_TOOLS))
def test_work_record_tools_are_admitted_in_a_locked_turn(
    tmp_path: Path, tool_name: str
) -> None:
    store, _ = _seeded_store(tmp_path)

    decision = _admit(store, tool_name, {"card": "CARD-1", "body": "progress"})

    assert decision.allowed is True
    assert decision.action == "record-work-state"


@pytest.mark.parametrize("tool_name", sorted(ARTIFACT_RUN_SIGNAL_TOOLS))
def test_run_signal_tools_are_admitted_in_a_locked_turn(
    tmp_path: Path, tool_name: str
) -> None:
    store, _ = _seeded_store(tmp_path)

    decision = _admit(store, tool_name, {"card": "CARD-1", "summary": "done"})

    assert decision.allowed is True
    assert decision.action == "signal-run-outcome"


@pytest.mark.parametrize("tool_name", sorted(ARTIFACT_RUN_SIGNAL_TOOLS))
def test_run_signal_tools_are_denied_outside_a_locked_turn(
    tmp_path: Path, tool_name: str
) -> None:
    # A turn whose contract could not be verified has established nothing
    # that a completion or a review request could be about, and those
    # transitions are what the orchestrator dispatches the next run on. The
    # escape valve INV-S6 asks such a turn for is the blocked record, which
    # is in the annotation catalogue and stays admitted.
    pre_lock = GateStore(tmp_path / "pre.db", enforce_artifact_change_pre_lock=True)
    pre_lock.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-pre",
        user_message=CHANGE_MESSAGE,
    )
    denied_store, _ = _seeded_store(
        tmp_path / "denied", branch="not-the-checked-out-branch"
    )

    before_lock = _admit(pre_lock, tool_name, {"card": "CARD-1"})
    after_failure = _admit(denied_store, tool_name, {"card": "CARD-1"})
    escape_valve = _admit(denied_store, "kanban_block", {"card": "CARD-1"})

    assert pre_lock.get_turn("turn-change")["state"] == "pre-lock"
    assert denied_store.get_turn("turn-change")["state"] == "mutation-denied"
    assert before_lock.allowed is False
    assert before_lock.action == "lock-pending"
    assert after_failure.allowed is False
    assert after_failure.action == "seed-verification-failed"
    assert escape_valve.allowed is True


def test_work_record_tools_are_admitted_before_lock_and_after_a_failed_seed(
    tmp_path: Path,
) -> None:
    # Nothing about the work-management plane depends on the scope being
    # fixed, and recording a blocked state is what INV-S6 asks a stalled
    # turn to do instead of starting repair work.
    pre_lock = GateStore(tmp_path / "pre.db", enforce_artifact_change_pre_lock=True)
    pre_lock.start_turn(
        turn_id="turn-change",
        session_id="session-change",
        task_id="task-pre",
        user_message=CHANGE_MESSAGE,
    )
    denied_store, _ = _seeded_store(
        tmp_path / "denied", branch="not-the-checked-out-branch"
    )

    before_lock = _admit(pre_lock, "kanban_heartbeat", {"card": "CARD-1"})
    after_failure = _admit(denied_store, "kanban_block", {"card": "CARD-1"})

    assert pre_lock.get_turn("turn-change")["state"] == "pre-lock"
    assert denied_store.get_turn("turn-change")["state"] == "mutation-denied"
    assert before_lock.allowed is True
    assert after_failure.allowed is True


def test_the_work_record_catalogue_is_a_closed_explicit_set(tmp_path: Path) -> None:
    vocabulary = _hermes_tool_vocabulary()
    both = ARTIFACT_WORK_RECORD_TOOLS | ARTIFACT_RUN_SIGNAL_TOOLS

    # Every listed name is a tool that actually exists, and the categories do
    # not overlap: membership is by name, never inferred from capability or
    # from the shape of the arguments.
    assert both <= vocabulary
    assert not (ARTIFACT_WORK_RECORD_TOOLS & ARTIFACT_RUN_SIGNAL_TOOLS)
    assert not (both & ARTIFACT_READ_TOOLS)
    assert not (both & set(ARTIFACT_WRITE_TOOL_CATALOG))
    assert "terminal" not in both
    # Excluded on purpose: another agent, outside material, skill files, and
    # durable state outside the turn are not records of the work in hand.
    for excluded in ("delegate_task", "web_search", "skill_manage", "memory", "cronjob"):
        assert excluded not in both, excluded
    # Also excluded: creating a card is how a blocker becomes a new task
    # (INV-S6), recording the reviewer's verdict is the other authority's
    # act (INV-S7), and the link/attach forms each carry a destination the
    # first layer does not bound.
    for excluded in (
        "kanban_create",
        "kanban_request_changes",
        "kanban_link",
        "kanban_attach",
        "kanban_attach_url",
    ):
        assert excluded in vocabulary, excluded
        assert excluded not in both, excluded
    # The escape valve INV-S6 asks a stalled turn for is in the catalogue
    # that every stage admits, not in the locked-only one.
    assert "kanban_block" in ARTIFACT_WORK_RECORD_TOOLS


@pytest.mark.parametrize(
    "tool_name",
    [
        "kanban_create",
        "kanban_request_changes",
        "kanban_link",
        "kanban_attach",
        "kanban_attach_url",
        "delegate_task",
    ],
)
def test_tools_outside_the_work_record_catalogue_stay_denied(
    tmp_path: Path, tool_name: str
) -> None:
    # Real neighbouring names from the running vocabulary: a fictional name
    # would assert coverage the closed set does not actually have.
    store, _ = _seeded_store(tmp_path)

    decision = _admit(store, tool_name, {"card": "CARD-1"})

    assert decision.allowed is False, tool_name
    assert decision.action == "expansion-required", tool_name


def test_an_unbindable_call_cannot_record_work_state(tmp_path: Path) -> None:
    # The work-record catalogues are admitted in the unlocked stages because
    # INV-S6 needs a stalled turn to record a blocked state. A call that
    # cannot be bound to a turn has no turn state to record, so the same
    # rationale does not reach this path and it stays fail-closed.
    store, _ = _seeded_store(tmp_path)

    read = store.admit_without_turn(
        task_id="task-change", session_id="session-change", tool_name="read_file"
    )
    record = store.admit_without_turn(
        task_id="task-change", session_id="session-change", tool_name="kanban_block"
    )
    signal = store.admit_without_turn(
        task_id="task-change", session_id="session-change", tool_name="kanban_complete"
    )

    assert read.allowed is True
    assert read.action == "inspect-unbound"
    assert record.allowed is False
    assert record.action == "contract-unbound"
    assert signal.allowed is False
    assert signal.action == "contract-unbound"


# The canonical counting set. Written out here rather than derived from the
# implementation so that adding or removing a reason code has to be a
# deliberate edit in two places (D-S3-7 補則).
_EXPECTED_DEVIATION_DENY_ACTIONS = frozenset(
    {
        # Structured write lane.
        "write-scope",
        "target-shape",
        "target-missing",
        "target-control",
        "target-base",
        "target-traversal",
        "target-escape",
        "target-closed",
        "target-root",
        "write-git-metadata",
        # Git write lane.
        "git-write-unspecified",
        "git-write-forbidden",
        "target-drift",
        "git-discovery-redirected",
        "git-discovery-unverified",
        "stage-git-metadata",
        "stage-unbounded",
        "stage-option",
        "stage-magic",
        "stage-directory",
        "stage-scope",
        "commit-unsafe",
        "commit-rewrite",
        # Execution lane: only codes issued after a template head matched.
        "execution-option",
        "execution-stdin",
        "execution-target",
    }
)


def test_the_counting_set_is_exactly_the_ratified_enumeration() -> None:
    assert ARTIFACT_DEVIATION_DENY_ACTIONS == _EXPECTED_DEVIATION_DENY_ACTIONS


# Audit labels the Git argument classification can produce. Since D-S3-7 補則
# these are attribution only: the tests below pin which label an operator sees
# in the audit trail, and pin that none of them charges the deny ceiling. They
# are no longer a safety property, so the label coverage is not required to be
# exhaustive over the argument space.
_CLASSIFIER_BOUNDARY_LABELS = frozenset({"git-write-form", "git-read-unsafe"})
_CLASSIFIER_READ_LABELS = frozenset({"git-read-unbounded", "git-read-unadmitted"})


@pytest.mark.parametrize("action", sorted(_EXPECTED_DEVIATION_DENY_ACTIONS))
def test_every_definitive_determination_charges_the_deny_ceiling(action: str) -> None:
    assert artifact_deny_counter(action) == "denied_count"


@pytest.mark.parametrize("action", sorted(ARTIFACT_BUDGET_DENY_ACTIONS))
def test_a_budget_denial_consumes_no_counter(action: str) -> None:
    assert artifact_deny_counter(action) is None


@pytest.mark.parametrize(
    "action",
    [
        # Argument-classification labels: the codomain of the heuristic stage.
        "git-read-unsafe",
        "git-write-form",
        "git-read-unbounded",
        "git-read-unadmitted",
        # Lanes an actual pure read reaches.
        "git-subcommand",
        "expansion-required",
        # No template head matched, so the lane is undetermined: a command
        # issued to read a file lands on these too.
        "execution-not-opted-in",
        "execution-template",
        "lock-pending",
        "seed-verification-failed",
        "contract-invalid",
        "turn-closed",
        "scope-control-invalid",
        "terminal-argument-unlisted",
        "background-forbidden",
        "compound-command",
        "command-parse",
        "workdir-missing",
        "workdir-traversal",
        "workdir-outside",
    ],
)
def test_a_denial_that_is_not_a_definitive_determination_spends_tool_budget(
    action: str,
) -> None:
    assert action not in ARTIFACT_DEVIATION_DENY_ACTIONS
    assert artifact_deny_counter(action) == "tool_count"


def test_an_unclassified_denial_does_not_charge_the_deny_ceiling() -> None:
    # Inverted polarity: a reason code has to be admitted to the ceiling
    # deliberately. The uncounted default is bounded by the tool budget.
    assert artifact_deny_counter("some-future-reason") == "tool_count"


def test_the_idempotence_guard_charges_the_ceiling_outside_the_mapping(
    tmp_path: Path,
) -> None:
    # The one counting site that does not go through the reason-code mapping:
    # replaying a tool-call id with different arguments is refused by the
    # idempotence guard, which charges the ceiling directly. Class-agnostic and
    # older than D-S3-7 補則. Pinned here so the exception cannot drift
    # unnoticed in either direction.
    store, _ = _seeded_store(tmp_path)

    first = _admit(
        store, "write_file", {"path": "src/app.py", "content": "a"}, call_id="same-id"
    )
    drifted = _admit(
        store, "write_file", {"path": "src/app.py", "content": "b"}, call_id="same-id"
    )
    turn = store.get_turn("turn-change")

    assert first.allowed is True
    assert drifted.allowed is False
    assert drifted.action == "hook-argument-drift"
    assert drifted.action not in ARTIFACT_DEVIATION_DENY_ACTIONS
    assert turn is not None
    assert turn["denied_count"] == 1


def test_the_counting_rule_does_not_consume_the_argument_classification() -> None:
    consumed = set(artifact_deny_counter.__code__.co_names)
    forbidden = {
        "ARTIFACT_GIT_WRITE_FORM_MARKERS",
        "ARTIFACT_GIT_PATH_OPTIONS",
        "ARTIFACT_GIT_READ_FORM_FLAGS",
        "ARTIFACT_GIT_READ_UNADMITTED",
        "ARTIFACT_GIT_READ_SUBCOMMANDS",
        "ARTIFACT_GIT_DIFF_FAMILY_SUBCOMMANDS",
        "_artifact_git_deviation_action",
        "artifact_git_read_refusal_action",
        "artifact_git_unadmitted_refusal_action",
        "_git_token_matches_marker",
        "_git_token_reaches_outside",
        "_git_token_path_candidates",
    }
    assert not (consumed & forbidden), sorted(consumed & forbidden)


def test_no_classification_label_can_reach_the_deny_ceiling() -> None:
    # Layer two of the independence check: the counting set could have been
    # built *from* the tables without naming them. Derive the classifier's
    # codomain from the reason tables so a new label is caught here.
    codomain = set(_GIT_READ_REFUSAL_REASONS) | set(_GIT_UNADMITTED_REASONS)
    assert codomain
    assert not (codomain & ARTIFACT_DEVIATION_DENY_ACTIONS), sorted(
        codomain & ARTIFACT_DEVIATION_DENY_ACTIONS
    )
    for label in sorted(codomain):
        assert artifact_deny_counter(label) == "tool_count", label


def test_read_refusals_do_not_strand_a_turn_that_keeps_working(
    tmp_path: Path,
) -> None:
    store, repo = _seeded_store(tmp_path)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])

    for index in range(ceiling + 2):
        refused = _admit(
            store,
            "terminal",
            {"command": "git log --oneline -1", "workdir": str(repo)},
            call_id=f"log-{index}",
        )
        assert refused.allowed is False, index

    still_working = _admit(
        store, "write_file", {"path": "src/app.py", "content": "fixed"}
    )
    turn = store.get_turn("turn-change")

    assert still_working.allowed is True
    assert still_working.action == "write-in-scope-change"
    assert turn is not None
    assert turn["denied_count"] == 0


@pytest.mark.parametrize(
    "execution",
    [
        # No opt-in at all, and an opt-in the command does not match: both
        # produce a template mismatch, so neither fixes the lane.
        [],
        ["focused-test", "syntax-check"],
    ],
)
def test_a_terminal_read_that_matches_no_template_does_not_strand_the_turn(
    tmp_path: Path, execution: list[str]
) -> None:
    # A command issued to read a file inside the locked scope is denied -- the
    # execution boundary holds -- but the denial does not fix the lane, so it
    # must not spend the ceiling. Counting it stranded the turn: past the
    # ceiling even an unconditionally admitted read tool came back
    # `deny-budget`.
    store, repo = _seeded_store(tmp_path, execution=execution)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])

    for index in range(ceiling + 2):
        refused = _admit(
            store,
            "terminal",
            {"command": "cat src/app.py", "workdir": str(repo)},
            call_id=f"read-{index}",
        )
        assert refused.allowed is False, index
        assert refused.action in {
            "execution-not-opted-in",
            "execution-template",
        }, (index, refused)

    read_tool = _admit(store, "read_file", {"path": "src/app.py"})
    admitted_git = _admit(
        store, "terminal", {"command": "git status --porcelain", "workdir": str(repo)}
    )
    write = _admit(store, "write_file", {"path": "src/app.py", "content": "fixed"})
    stage = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert read_tool.allowed is True
    assert admitted_git.allowed is True
    assert write.allowed is True
    assert stage.allowed is True
    assert turn is not None
    assert turn["denied_count"] == 0


def test_boundary_deviations_still_exhaust_the_deny_ceiling(tmp_path: Path) -> None:
    store, _ = _seeded_store(tmp_path)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])

    for index in range(ceiling):
        deviation = _admit(
            store,
            "write_file",
            {"path": "secrets.txt", "content": str(index)},
            call_id=f"deviation-{index}",
        )
        assert deviation.allowed is False, index

    exhausted = _admit(store, "write_file", {"path": "src/app.py", "content": "x"})

    assert exhausted.allowed is False
    assert exhausted.action == "deny-budget"


@pytest.mark.parametrize(
    ("last_command", "beyond_command", "action", "execution"),
    [
        ("git show HEAD", "git show HEAD~1", "git-read-unadmitted", []),
        ("git rev-parse --git-dir", "git branch --list", "git-read-unbounded", []),
        # Template mismatch: no head matched, so the lane is undetermined and
        # the denial is uncounted. Both variants -- no opt-in at all, and an
        # opt-in the command does not match.
        ("cat src/app.py", "cat README.md", "execution-not-opted-in", []),
        (
            "cat src/app.py",
            "cat README.md",
            "execution-template",
            ["focused-test", "syntax-check"],
        ),
    ],
)
def test_uncounted_denials_stay_bounded_by_the_class_budget(
    tmp_path: Path,
    last_command: str,
    beyond_command: str,
    action: str,
    execution: list[str],
) -> None:
    # The uncounted path is not an unbounded path: it spends the tool budget,
    # so the class ceilings still terminate it. Every exempt reason code has
    # to be shown bounded, not just the first one that was exempted.
    store, repo = _seeded_store(tmp_path, execution=execution)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_tool_calls"])
    with store._connect() as connection:
        connection.execute(
            "UPDATE turns SET tool_count = ? WHERE turn_id = 'turn-change'",
            (ceiling - 1,),
        )

    last = _admit(store, "terminal", {"command": last_command, "workdir": str(repo)})
    beyond = _admit(
        store, "terminal", {"command": beyond_command, "workdir": str(repo)}
    )

    assert last.action == action
    assert beyond.allowed is False
    assert beyond.action == "tool-budget"


def test_closeout_deny_counting_is_unchanged(tmp_path: Path) -> None:
    # The counting rule is scoped to artifact-change; the enforced class that
    # shipped in S1 keeps counting every denial.
    store = GateStore(tmp_path / "closeout.db")
    store.start_turn(
        turn_id="turn-closeout",
        session_id="s",
        user_message="commit, pushしていない資源があればcommit, pushして",
    )

    denied = store.admit_tool(
        turn_id="turn-closeout",
        tool_call_id="c1",
        tool_name="delegate_task",
        args={"goal": "review everything"},
    )
    turn = store.get_turn("turn-closeout")

    assert denied.allowed is False
    assert turn is not None
    assert turn["task_class"] == "repository-closeout"
    assert turn["denied_count"] == 1


# ---------------------------------------------------------------------------
# Section 10 acceptance: artifact-change replay in the enforced state
# ---------------------------------------------------------------------------


def test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling(
    tmp_path: Path,
) -> None:
    """Section 10 item 15: the normal autonomous-worker flow, enforced.

    Inspect the diff, edit, verify, stage, commit, collect the approval
    metadata the operating procedure requires, update the card. The existing
    artifact-change fixtures pin the unenforced state only, so this is the
    first replay that runs the flow through a locked contract.

    The metadata step is part of the flow on purpose. Writing the acceptance
    item to the allow set instead of to the required procedure is what let the
    first version of this replay pass while the procedure still stranded.
    """

    store, repo = _seeded_store(
        tmp_path,
        write_paths=["src/*.py"],
        test_paths=["tests/test_app.py"],
        execution=["focused-test"],
    )
    flow: list[tuple[str, dict[str, object]]] = [
        ("kanban_show", {"card": "CARD-1"}),
        ("todo", {"items": ["inspect", "edit", "verify", "commit"]}),
        ("terminal", {"command": "git status --short", "workdir": str(repo)}),
        ("terminal", {"command": "git diff", "workdir": str(repo)}),
        # Base commit id, before anything is committed.
        ("terminal", {"command": "git rev-parse HEAD", "workdir": str(repo)}),
        ("read_file", {"path": str(repo / "src" / "app.py")}),
        ("write_file", {"path": "src/app.py", "content": "x = 2\n"}),
        ("write_file", {"path": "tests/test_app.py", "content": "def test_x():\n    pass\n"}),
        ("terminal", {"command": "pytest -q tests/test_app.py", "workdir": str(repo)}),
        # Changed-files list for the metadata, then stage exactly those.
        ("terminal", {"command": "git diff --name-only", "workdir": str(repo)}),
        ("terminal", {"command": "git add src/app.py tests/test_app.py", "workdir": str(repo)}),
        ("terminal", {"command": "git diff --cached --name-only", "workdir": str(repo)}),
        ("terminal", {"command": "git commit -m 'fix: login'", "workdir": str(repo)}),
        # Head commit id and branch identity for the metadata.
        ("terminal", {"command": "git rev-parse HEAD", "workdir": str(repo)}),
        ("terminal", {"command": "git rev-parse --verify HEAD", "workdir": str(repo)}),
        ("terminal", {"command": "git branch --show-current", "workdir": str(repo)}),
        ("terminal", {"command": "git rev-parse --abbrev-ref HEAD", "workdir": str(repo)}),
        ("kanban_comment", {"card": "CARD-1", "body": "done"}),
        ("kanban_request_review", {"card": "CARD-1"}),
    ]

    for index, (tool_name, args) in enumerate(flow):
        decision = _admit(store, tool_name, args, call_id=f"flow-{index}")
        assert decision.allowed is True, (tool_name, args, decision)

    turn = store.get_turn("turn-change")

    assert turn is not None
    assert turn["denied_count"] == 0
    assert turn["state"] == "locked"


@pytest.mark.parametrize(
    "refused_command",
    [
        # Outside the admitted read subset entirely.
        "git log --oneline -1",
        "git merge-base main HEAD",
        # Inside it, but in an argument form the allowlist does not carry.
        # This is the shape the operating procedure actually reaches for, so
        # an acceptance item that only covered the first group left the
        # stranding it was written to prevent in place.
        "git rev-parse --show-toplevel",
        "git rev-parse --git-dir",
        "git rev-parse --git-common-dir",
        "git rev-parse --short HEAD",
        "git branch --list",
        "git diff HEAD~1",
    ],
)
def test_replay_the_worker_flow_survives_one_refused_read(
    tmp_path: Path, refused_command: str
) -> None:
    """Section 10 item 16: a refused read does not stall the enforced flow."""

    store, repo = _seeded_store(tmp_path, execution=["focused-test"])

    refused = _admit(
        store, "terminal", {"command": refused_command, "workdir": str(repo)}
    )
    substitute = _admit(
        store, "terminal", {"command": "git rev-parse HEAD", "workdir": str(repo)}
    )
    staged = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )
    committed = _admit(
        store, "terminal", {"command": "git commit -m 'fix'", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert refused.allowed is False, refused_command
    for allowed in (substitute, staged, committed):
        assert allowed.allowed is True, (refused_command, allowed)
    assert turn is not None
    assert turn["denied_count"] == 0, refused_command


def test_repeated_refused_reads_do_not_strand_the_required_flow(
    tmp_path: Path,
) -> None:
    """Section 10 item 16: the refusals the required flow reaches are exempt.

    The identity reads the approval metadata asks for have no admitted form,
    so a turn that follows the procedure produces more refusals than the deny
    ceiling allows. Every one of them has to stay off the ceiling, or the
    in-scope write that follows becomes a budget denial.
    """

    store, repo = _seeded_store(tmp_path)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])
    identity_reads = [
        "git rev-parse --show-toplevel",
        "git rev-parse --git-dir",
        "git rev-parse --git-common-dir",
        "git rev-parse --is-inside-work-tree",
        "git rev-parse HEAD~1",
        "git rev-parse --verify HEAD~1",
        "git merge-base main HEAD",
        "git diff --name-only HEAD~1",
    ]
    assert len(identity_reads) > ceiling

    for index, command in enumerate(identity_reads):
        refused = _admit(
            store,
            "terminal",
            {"command": command, "workdir": str(repo)},
            call_id=f"identity-{index}",
        )
        assert refused.allowed is False, command
        assert artifact_deny_counter(refused.action) == "tool_count", command

    admitted_read = _admit(
        store, "terminal", {"command": "git branch --show-current", "workdir": str(repo)}
    )
    written = _admit(store, "write_file", {"path": "src/app.py", "content": "fixed"})
    staged = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )
    committed = _admit(
        store, "terminal", {"command": "git commit -m 'fix'", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert admitted_read.allowed is True
    assert written.allowed is True
    assert staged.allowed is True
    assert committed.allowed is True
    assert turn is not None
    assert turn["denied_count"] == 0


def test_replay_the_enforced_flow_still_refuses_the_incident_expansions(
    tmp_path: Path,
) -> None:
    """Section 10 item 17: the original incident's expansions stay denied.

    The same replay set as item 5, run in the enforced state instead of the
    unenforced one: a whole-suite run, another worktree, a subagent, and
    push are all outside the first layer. `push` is not part of S3's first
    layer at all and stays with the separate finalization contract.
    """

    store, repo = _seeded_store(tmp_path, execution=["focused-test"])
    other = tmp_path / "other-worktree"
    _init_git_repo(other)

    denials = {
        "whole-suite": _admit(
            store, "terminal", {"command": "pytest", "workdir": str(repo)}
        ),
        "other-worktree": _admit(
            store, "write_file", {"path": str(other / "src" / "a.py"), "content": "x"}
        ),
        "subagent": _admit(store, "delegate_task", {"goal": "review all worktrees"}),
        "push": _admit(
            store, "terminal", {"command": "git push origin main", "workdir": str(repo)}
        ),
        "out-of-scope-write": _admit(
            store, "write_file", {"path": "secrets.txt", "content": "x"}
        ),
    }

    for name, decision in denials.items():
        assert decision.allowed is False, name
        assert decision.action != "git-read-unadmitted", name


def test_the_read_only_git_subset_is_a_closed_set() -> None:
    # Network reads serve push, which this class does not have, and `log` has
    # no bounded-argument implementation to reuse.
    assert ARTIFACT_GIT_READ_SUBCOMMANDS == {"status", "diff", "rev-parse", "branch"}
    assert not (ARTIFACT_GIT_READ_SUBCOMMANDS & ARTIFACT_GIT_READ_UNADMITTED)
    for excluded in ("ls-remote", "remote", "log"):
        assert excluded not in ARTIFACT_GIT_READ_SUBCOMMANDS, excluded
    # No subcommand whose own purpose is changing state may be recognized as a
    # read, so its refusals stay on the counted side.
    assert not (
        ARTIFACT_GIT_READ_UNADMITTED & ARTIFACT_GIT_WRITE_CAPABLE_SUBCOMMANDS
    )
    for write_form in sorted(ARTIFACT_GIT_WRITE_CAPABLE_SUBCOMMANDS):
        assert write_form not in ARTIFACT_GIT_READ_UNADMITTED, write_form
    # An admitted subcommand that also carries a write form has to carry a
    # read-form allowlist, so anything else about it counts. Widening the
    # admitted set with such a subcommand and no allowlist fails here.
    assert set(ARTIFACT_GIT_READ_FORM_FLAGS) <= ARTIFACT_GIT_READ_SUBCOMMANDS
    guarded = ARTIFACT_GIT_READ_SUBCOMMANDS & ARTIFACT_GIT_WRITE_CAPABLE_SUBCOMMANDS
    assert guarded, "the invariant is vacuous if no admitted subcommand can write"
    for subcommand in sorted(guarded):
        assert subcommand in ARTIFACT_GIT_READ_FORM_FLAGS, subcommand
    # Write-form markers are declared per subcommand, so they only bite where
    # the refusal is classified at all: the admitted subset or the recognized
    # unadmitted set. A marker declared for anything else is dead.
    recognized = ARTIFACT_GIT_READ_SUBCOMMANDS | ARTIFACT_GIT_READ_UNADMITTED
    # Both declaration tables are TOTAL over the recognized set, not merely
    # contained in it. A member with no entry at all is the silence that let a
    # member naming an external program to run stay in the exempt lane while
    # this invariant was green: the obligation was written as a list of the one
    # family that had been audited, so a family nobody had looked at could not
    # fail it. Totality moves the obligation from "the families we listed" to
    # "every family", and an empty entry is the explicit statement that the
    # member was audited and has nothing to declare.
    assert set(ARTIFACT_GIT_WRITE_FORM_MARKERS) == recognized
    assert set(ARTIFACT_GIT_PATH_OPTIONS) == recognized
    # Membership in the unadmitted set is not the exemption. Every member that
    # takes the diff family's options can be told to write a file, so it has
    # to carry markers -- otherwise naming it here would exempt its write form
    # from the ceiling, which is the error this classification removed once at
    # the subcommand level and would otherwise re-open at the argument level.
    for subcommand in sorted(ARTIFACT_GIT_DIFF_FAMILY_SUBCOMMANDS):
        assert ARTIFACT_GIT_WRITE_FORM_MARKERS[subcommand], subcommand
        assert ARTIFACT_GIT_PATH_OPTIONS[subcommand], subcommand
    assert ARTIFACT_GIT_DIFF_FAMILY_SUBCOMMANDS & ARTIFACT_GIT_READ_UNADMITTED
    # The write boundary is not the only one an argument can name. A network
    # read that takes the far-side program as an argument reaches the execution
    # boundary, so its declaration is what keeps that probe on the ceiling.
    for subcommand in sorted(recognized):
        if subcommand.startswith("ls-remote"):
            assert ARTIFACT_GIT_WRITE_FORM_MARKERS[subcommand], subcommand
    # Non-vacuity for the totality asserts above: a table of nothing but empty
    # entries would satisfy them while declaring nothing.
    assert any(ARTIFACT_GIT_WRITE_FORM_MARKERS.values())
    assert any(ARTIFACT_GIT_PATH_OPTIONS.values())


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        ("diff", ["--output=/tmp/x"]),
        ("diff", ["--output", "/tmp/x"]),
        ("diff", ["--ext-diff"]),
        ("branch", ["-d", "gone"]),
        ("branch", ["-D", "gone"]),
        ("branch", ["--delete", "gone"]),
        ("branch", ["-m", "old", "new"]),
        ("branch", ["-M", "old", "new"]),
        ("branch", ["-c", "old", "new"]),
        ("branch", ["--copy", "old", "new"]),
        ("branch", ["--force", "existing"]),
        ("branch", ["-u", "origin/main"]),
        ("branch", ["--set-upstream-to=origin/main"]),
        ("branch", ["--unset-upstream"]),
        ("branch", ["--edit-description"]),
        ("branch", ["created"]),
        # Bundled short options and joined values must not slip past a
        # marker or allowlist that only matches the plain spelling.
        ("branch", ["-av"]),
        ("branch", ["-rd", "gone"]),
        ("branch", ["--list=pattern"]),
        ("diff", ["--output=relative-path"]),
        ("diff", ["--ext-diff", "driver"]),
        # Reaching outside the locked root, in either notation.
        ("diff", ["--", "../outside"]),
        ("diff", ["/etc/passwd"]),
        ("rev-parse", ["/etc/passwd"]),
        ("rev-parse", ["--show-toplevel", "../elsewhere"]),
    ],
)
def test_a_write_form_of_an_admitted_read_is_labelled_as_a_boundary_form(
    subcommand: str, tail: list[str]
) -> None:
    # Audit attribution: the operator should see that a state-changing form
    # was refused, not just that a read was. The label carries no budget
    # consequence -- the Git read lane spends the tool budget either way.
    action = artifact_git_read_refusal_action(subcommand, tail)

    assert action in _CLASSIFIER_BOUNDARY_LABELS, (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        ("branch", []),
        ("branch", ["--list"]),
        ("branch", ["-a"]),
        ("branch", ["-r"]),
        ("branch", ["-v"]),
        ("branch", ["--all"]),
        ("rev-parse", ["--git-dir"]),
        ("rev-parse", ["--git-common-dir"]),
        ("rev-parse", ["--show-toplevel"]),
        ("rev-parse", ["--is-inside-work-tree"]),
        ("rev-parse", ["--short", "HEAD"]),
        ("rev-parse", ["HEAD~1"]),
        ("diff", ["HEAD~1"]),
        ("diff", ["--stat", "HEAD~1"]),
        # Revision ranges: `..` and `...` are operators between revisions.
        ("diff", ["HEAD~1..HEAD"]),
        ("diff", ["main...HEAD"]),
        # Safe look-alikes of the two write markers.
        ("diff", ["--no-ext-diff"]),
        ("diff", ["--output-indicator-new=x"]),
    ],
)
def test_a_pure_read_inside_the_locked_root_stays_off_the_ceiling(
    subcommand: str, tail: list[str]
) -> None:
    # Marker matching stays narrow enough that a longer unrelated option is
    # not swept in. Under D-S3-7 補則 a miss here would cost audit precision
    # rather than stranding the turn, but the label is still worth pinning.
    action = artifact_git_read_refusal_action(subcommand, tail)

    assert action in _CLASSIFIER_READ_LABELS, (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        # The output form of each diff-family member actually creates the
        # named file, so naming the subcommand as a recognized read must not
        # carry its write form into the exempt lane with it.
        ("log", ["--output=out.txt"]),
        ("log", ["--output", "out.txt"]),
        ("show", ["--output=out.txt"]),
        ("blame", ["--output=out.txt", "src/app.py"]),
        ("shortlog", ["--output=out.txt"]),
        # Handing the comparison to an external program is an execution
        # boundary, not a read.
        ("log", ["--ext-diff"]),
        ("show", ["--ext-diff"]),
        # Reaching outside the locked root under a recognized read name.
        ("log", ["../outside"]),
        ("show", ["/etc/passwd"]),
        ("blame", ["--", "../outside"]),
    ],
)
def test_a_write_form_under_a_recognized_read_name_is_labelled_as_one(
    subcommand: str, tail: list[str]
) -> None:
    # Several members of the unadmitted set take the diff family's options, so
    # the audit label distinguishes their write form from their read form. All
    # of them are denied, and all of them spend the tool budget.
    action = artifact_git_unadmitted_refusal_action(subcommand, tail)

    assert action in _CLASSIFIER_BOUNDARY_LABELS, (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        ("log", []),
        ("log", ["--oneline", "-1"]),
        ("log", ["--no-ext-diff"]),
        ("show", ["--name-only", "HEAD"]),
        ("blame", ["src/app.py"]),
        ("shortlog", ["-s", "-n"]),
        ("merge-base", ["main", "HEAD"]),
        ("ls-files", ["--cached"]),
        ("describe", ["--tags"]),
        # A revision range under a recognized name is still a pure read.
        ("log", ["HEAD~1..HEAD"]),
        ("show", ["main...HEAD"]),
    ],
)
def test_a_pure_read_of_a_recognized_read_name_stays_exempt(
    subcommand: str, tail: list[str]
) -> None:
    # The other half of the same closure. The required approval-metadata flow
    # reaches several of these, so counting them strands the turn.
    action = artifact_git_unadmitted_refusal_action(subcommand, tail)

    assert action == "git-read-unadmitted", (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        # A path does not have to be the whole token: an option can pack it
        # onto a single-dash flag or carry it as a joined value, and an option
        # that reads a file from an absolute path is reaching outside the root
        # whatever the option is called.
        ("diff", ["-O/etc/passwd"]),
        ("diff", ["--relative=../outside"]),
        ("log", ["-O/etc/passwd"]),
        ("rev-parse", ["--git-path=/etc/passwd"]),
        ("show", ["--relative=../../elsewhere"]),
    ],
)
def test_a_path_inside_a_joined_option_value_is_labelled_unsafe(
    subcommand: str, tail: list[str]
) -> None:
    admitted = artifact_git_read_refusal_action(subcommand, tail)
    recognized = artifact_git_unadmitted_refusal_action(subcommand, tail)

    for action in (admitted, recognized):
        assert action == "git-read-unsafe", (subcommand, tail, action)
        assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        # Short flags and joined values that carry no path at all: bundling or
        # an `=` must not by itself move a pure read onto the ceiling.
        ("branch", ["-a"]),
        ("branch", ["--color=never"]),
        ("diff", ["--output-indicator-new=x"]),
        ("log", ["-1"]),
        ("log", ["--format=%H"]),
        ("shortlog", ["-sn"]),
    ],
)
def test_a_joined_value_without_a_path_is_labelled_a_read(
    subcommand: str, tail: list[str]
) -> None:
    # Looking inside a token for a path must not label every bundled flag or
    # `key=value` option a boundary attempt.
    if subcommand in ARTIFACT_GIT_READ_SUBCOMMANDS:
        action = artifact_git_read_refusal_action(subcommand, tail)
    else:
        action = artifact_git_unadmitted_refusal_action(subcommand, tail)

    assert action in _CLASSIFIER_READ_LABELS, (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    "tail",
    [
        # The program to run on the far side is named by an argument, so an
        # absolute program path is not the only spelling that reaches the
        # execution boundary. A bare program name left to PATH resolution
        # carries no path for the boundary check to see, which is how this
        # family stayed exempt while the diff family's output form did not.
        ["--upload-pack=/bin/echo", "origin"],
        ["--upload-pack=echo", "origin"],
        ["--upload-pack", "echo", "origin"],
        ["--exec=echo", "origin"],
        ["-uecho", "origin"],
        ["-u", "echo", "origin"],
        ["-quecho", "origin"],
    ],
)
def test_an_execution_form_under_a_recognized_read_name_is_labelled_as_one(
    tail: list[str],
) -> None:
    # Same structure as the write-form label, one boundary over: a member that
    # can name a program to run gets the boundary label rather than the read
    # label. Admission denies every spelling here regardless.
    action = artifact_git_unadmitted_refusal_action("ls-remote", tail)

    assert action in _CLASSIFIER_BOUNDARY_LABELS, (tail, action)
    assert artifact_deny_counter(action) == "tool_count", tail


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        # A value-taking short option may sit at the end of a bundle of
        # valueless flags, so the value does not have to start at the third
        # character. Reading only the third character onward left every
        # bundled spelling unclassified.
        ("diff", ["-pO/etc/passwd"]),
        ("log", ["-pO/etc/passwd"]),
        ("log", ["-pO../outside"]),
        ("show", ["-pO/etc/passwd"]),
        ("blame", ["-pO/etc/passwd", "src/app.py"]),
        ("blame", ["-lS/etc/passwd", "src/app.py"]),
        ("ls-files", ["-cX/etc/passwd"]),
    ],
)
def test_a_path_packed_onto_a_flag_bundle_is_labelled_unsafe(
    subcommand: str, tail: list[str]
) -> None:
    if subcommand in ARTIFACT_GIT_READ_SUBCOMMANDS:
        action = artifact_git_read_refusal_action(subcommand, tail)
    else:
        action = artifact_git_unadmitted_refusal_action(subcommand, tail)

    assert action == "git-read-unsafe", (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


@pytest.mark.parametrize(
    ("subcommand", "tail"),
    [
        # Values that DO carry path separators and are nevertheless not paths.
        # Reading the value without reading the option name used to put each of
        # these on the deny ceiling, where six of them stranded the turn; since
        # D-S3-7 補則 the same mistake would only mislabel the audit record.
        ("log", ["--grep=/etc/passwd"]),
        ("log", ["--grep=../old-api"]),
        ("log", ["--author=../x"]),
        ("log", ["--committer=/root"]),
        ("log", ["--format=/%H"]),
        ("log", ["--pretty=format:/%h %s"]),
        ("diff", ["--src-prefix=/a/"]),
        ("diff", ["--dst-prefix=../b/"]),
        ("diff", ["--line-prefix=/x"]),
        # Pickaxe: a search for a path-shaped string in the history is a read
        # of the history, not a read of that path.
        ("log", ["-S/usr/bin/env"]),
        ("log", ["-G/api/v1"]),
        ("log", ["-S../old/path"]),
        # Line attribution given its range as a regular expression. The
        # separators belong to the regex delimiters, and this is a common form
        # of both members that accept it.
        ("blame", ["-L/^def main/,+20", "src/app.py"]),
        ("log", ["-L/^def main/,+20:src/app.py"]),
    ],
)
def test_a_value_that_only_looks_like_a_path_is_labelled_a_read(
    subcommand: str, tail: list[str]
) -> None:
    if subcommand in ARTIFACT_GIT_READ_SUBCOMMANDS:
        action = artifact_git_read_refusal_action(subcommand, tail)
    else:
        action = artifact_git_unadmitted_refusal_action(subcommand, tail)

    assert action in _CLASSIFIER_READ_LABELS, (subcommand, tail, action)
    assert artifact_deny_counter(action) == "tool_count", (subcommand, tail)


def test_a_path_option_is_declared_per_subcommand_not_by_spelling() -> None:
    # The same short spelling is a revision *file* for line attribution and a
    # pickaxe *string* for the history family. A single table keyed by
    # spelling alone has to be wrong in one direction or the other: either the
    # file read stays exempt, or an ordinary history search lands on the
    # ceiling and strands the turn.
    packed = "-S/etc/passwd"

    assert artifact_git_unadmitted_refusal_action("blame", [packed]) == (
        "git-read-unsafe"
    )
    assert artifact_git_unadmitted_refusal_action("log", [packed]) == (
        "git-read-unadmitted"
    )
    assert "-S" in ARTIFACT_GIT_PATH_OPTIONS["blame"]
    assert "-S" not in ARTIFACT_GIT_PATH_OPTIONS["log"]


def test_a_read_whose_value_looks_like_a_path_does_not_strand_the_turn(
    tmp_path: Path,
) -> None:
    # End to end, the false-deny side. The stranding this reverses is the same
    # failure mode the ceiling rule was rewritten to remove: repeating a pure
    # read past the ceiling must leave the deny count at zero and the turn
    # able to keep working.
    store, repo = _seeded_store(tmp_path)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])

    for index in range(ceiling + 2):
        refused = _admit(
            store,
            "terminal",
            {"command": "git log --grep=../old-api -1", "workdir": str(repo)},
            call_id=f"looks-like-path-{index}",
        )
        assert refused.allowed is False, index
        assert refused.action == "git-read-unadmitted", index

    still_working = _admit(
        store, "write_file", {"path": "src/app.py", "content": "fixed"}
    )
    reading = _admit(
        store, "terminal", {"command": "git status --short", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert still_working.allowed is True
    assert still_working.action == "write-in-scope-change"
    assert reading.allowed is True
    assert turn is not None
    assert turn["denied_count"] == 0


@pytest.mark.parametrize(
    ("command", "action"),
    [
        # One command per uncounted lane, covering both classification labels
        # and the two lanes whose code cannot determine the lane at all.
        ("git ls-remote --upload-pack=echo origin", "git-write-form"),
        ("git log -pO/etc/passwd", "git-read-unsafe"),
        ("git log --oneline", "git-read-unadmitted"),
        ("git rev-parse --git-dir", "git-read-unbounded"),
        ("git rebase -i main", "git-subcommand"),
    ],
)
def test_an_uncounted_denial_lane_is_closed_by_the_tool_budget(
    tmp_path: Path, command: str, action: str
) -> None:
    # D-S3-7 補則 moved these lanes off the deny ceiling. What has to hold in
    # their place: repeating one never strands the turn on the ceiling, and it
    # does not run forever either -- the class tool budget closes the turn, and
    # the closure is a denial rather than a fail-open.
    store, repo = _seeded_store(tmp_path)
    tool_budget = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_tool_calls"])

    for index in range(tool_budget):
        refused = _admit(
            store,
            "terminal",
            {"command": command, "workdir": str(repo)},
            call_id=f"uncounted-{index}",
        )
        assert refused.allowed is False, index
        assert refused.action == action, index

    turn = store.get_turn("turn-change")
    assert turn is not None
    assert turn["denied_count"] == 0
    assert turn["tool_count"] == tool_budget

    exhausted = _admit(
        store, "terminal", {"command": command, "workdir": str(repo)}
    )

    assert exhausted.allowed is False
    assert exhausted.action == "tool-budget"


@pytest.mark.parametrize(
    ("command", "action"),
    [
        # One command per classification label, including the two labels the
        # classifier reserves for boundary forms. Whichever label the argument
        # inspection picks -- and whether it picks it correctly -- the required
        # flow has to survive past the ceiling. This is the property that the
        # spelling coverage of the marker and path tables no longer has to
        # carry: a misclassification here cannot strand the turn.
        ("git log --oneline -1", "git-read-unadmitted"),
        ("git rev-parse --git-dir", "git-read-unbounded"),
        ("git log --output=leak.txt", "git-write-form"),
        ("git log -pO/etc/passwd", "git-read-unsafe"),
    ],
)
def test_no_classification_label_can_strand_the_required_flow(
    tmp_path: Path, command: str, action: str
) -> None:
    store, repo = _seeded_store(tmp_path)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])

    for index in range(ceiling + 2):
        refused = _admit(
            store,
            "terminal",
            {"command": command, "workdir": str(repo)},
            call_id=f"label-{index}",
        )
        assert refused.allowed is False, index
        assert refused.action == action, index

    writing = _admit(store, "write_file", {"path": "src/app.py", "content": "fixed"})
    staging = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(repo)}
    )
    turn = store.get_turn("turn-change")

    assert writing.allowed is True, action
    assert writing.action == "write-in-scope-change"
    assert staging.allowed is True, action
    assert staging.action == "stage-in-scope-change"
    assert turn is not None
    assert turn["denied_count"] == 0, action


def test_a_recognized_read_still_does_not_strand_the_required_flow(
    tmp_path: Path,
) -> None:
    # The same subcommand in its read form stays exempt past the ceiling, so
    # the in-scope write that follows is still admitted.
    store, repo = _seeded_store(tmp_path)
    ceiling = int(ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"])

    for _ in range(ceiling + 2):
        refused = _admit(
            store, "terminal", {"command": "git show --name-only HEAD", "workdir": str(repo)}
        )
        assert refused.allowed is False
        assert refused.action == "git-read-unadmitted"

    written = _admit(store, "write_file", {"path": "src/app.py", "content": "fixed"})
    turn = store.get_turn("turn-change")

    assert written.allowed is True, written
    assert turn is not None
    assert turn["denied_count"] == 0


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git status --short",
        "git diff",
        "git diff --name-only",
        "git rev-parse HEAD",
        "git rev-parse --verify HEAD",
        "git rev-parse --abbrev-ref HEAD",
        "git branch --show-current",
        "git branch -d gone",
        "git diff --output=/tmp/x",
        "git rev-parse --git-dir",
        "git diff HEAD~1..HEAD",
    ],
)
def test_read_admission_does_not_consult_the_branch_binding(
    tmp_path: Path, command: str
) -> None:
    # The only subcommand whose verdict depends on a branch set is the
    # network read this class does not admit, so the verdict must be the same
    # whatever branch the contract binds.
    bound, bound_repo = _seeded_store(tmp_path / "bound")
    renamed_repo = tmp_path / "renamed" / "repo"
    _init_git_repo(renamed_repo, branch="other-branch")
    renamed, _ = _seeded_store(
        tmp_path / "renamed", branch="other-branch", repo=renamed_repo
    )

    first = _admit(bound, "terminal", {"command": command, "workdir": str(bound_repo)})
    second = _admit(
        renamed, "terminal", {"command": command, "workdir": str(renamed_repo)}
    )

    assert first.allowed is second.allowed, command
    assert first.action == second.action, command


# ---------------------------------------------------------------------------
# Git metadata is outside every contract (W-B-01 breadth, W-B-02 blocker)
# ---------------------------------------------------------------------------


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path, str]:
    """A primary repository plus one linked worktree on its own branch."""

    primary = tmp_path / "primary"
    _init_git_repo(primary)
    (primary / "src").mkdir()
    (primary / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    for command in (
        ["git", "-C", str(primary), "config", "user.email", "t@example.invalid"],
        ["git", "-C", str(primary), "config", "user.name", "T"],
        ["git", "-C", str(primary), "add", "-A"],
        ["git", "-C", str(primary), "commit", "-q", "-m", "base"],
    ):
        subprocess.run(command, check=True, capture_output=True, text=True)
    worktree = tmp_path / "wt"
    branch = "pda-auto/t1"
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", "-q", "-b", branch, str(worktree), "main"],
        check=True,
        capture_output=True,
        text=True,
    )
    return primary, worktree, branch


@pytest.mark.parametrize(
    "target",
    [".git", ".git/config", ".git/hooks/pre-commit", "vendor/.git/config"],
)
def test_the_widest_write_scope_still_refuses_gits_own_metadata(
    tmp_path: Path, target: str
) -> None:
    # The declared ceiling here matches everything, which is exactly the
    # premise the refusal must not depend on: the contract's guarantees are
    # stated through Git's discovery from the locked root, so the storage
    # backing that discovery is never a write destination.
    store, _ = _seeded_store(tmp_path, write_paths=["**"], test_paths=[])

    decision = _admit(store, "write_file", {"path": target, "content": "x"})

    assert decision.allowed is False, target
    assert decision.action == "write-git-metadata"
    assert artifact_deny_counter(decision.action) == "denied_count"


def test_the_widest_write_scope_still_admits_ordinary_files(tmp_path: Path) -> None:
    # The companion to the refusal above: the carve-out is a named exception,
    # not a narrowing of what a broad declaration otherwise reaches.
    store, _ = _seeded_store(tmp_path, write_paths=["**"], test_paths=[])

    decision = _admit(store, "write_file", {"path": "src/app.py", "content": "x"})

    assert decision.allowed is True


@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        ("delete_file", {"path": ".git/config"}),
        ("append_file", {"path": ".git/config", "content": "x"}),
        ("edit_file", {"file_path": ".git/hooks/pre-commit"}),
        ("write_files", {"paths": ["src/app.py", ".git/config"]}),
        ("multi_edit", {"edits": [{"path": "src/app.py"}, {"path": ".git/config"}]}),
        # Only the destination names metadata: a pair-field tool must be
        # refused on either end, not just the one that happens to be first.
        ("move_file", {"source_path": "src/app.py", "destination_path": ".git/config"}),
        ("copy_file", {"source_path": ".git/config", "destination_path": "src/app.py"}),
    ],
)
def test_no_write_catalogue_tool_reaches_git_metadata(
    tmp_path: Path, tool_name: str, args: dict[str, object]
) -> None:
    store, _ = _seeded_store(tmp_path, write_paths=["**"], test_paths=[])

    decision = _admit(store, tool_name, dict(args))

    assert decision.allowed is False, tool_name
    assert decision.action == "write-git-metadata", tool_name


def _filesystem_folds_case(root: Path) -> bool:
    probe = root / "case-probe-directory"
    probe.mkdir()
    try:
        return (root / "CASE-PROBE-DIRECTORY").is_dir()
    finally:
        probe.rmdir()


def test_a_metadata_name_the_filesystem_folds_is_still_refused(tmp_path: Path) -> None:
    """The identity of the destination decides, not the spelling of the name.

    On a filesystem that folds case, a differently cased spelling of the
    metadata directory opens the same storage: the segment differs, the entity
    does not. Where case is significant it is a genuinely different directory
    and writing to it has to stay admitted, so both directions are asserted
    against what the filesystem under the fixture actually does.
    """

    store, repo = _seeded_store(tmp_path, write_paths=["**"], test_paths=[])
    folds = _filesystem_folds_case(repo)

    decision = _admit(store, "write_file", {"path": ".Git/config", "content": "x"})

    if folds:
        assert decision.allowed is False
        assert decision.action == "write-git-metadata"
        assert artifact_deny_counter(decision.action) == "denied_count"
    else:
        # The false-denial side: a distinct directory that merely resembles the
        # metadata name is an ordinary destination.
        assert decision.allowed is True
        assert decision.action == "write-in-scope-change"


def test_an_alias_of_the_metadata_pointer_is_refused(tmp_path: Path) -> None:
    """A second name for the same entity, on every filesystem.

    A linked worktree's ``.git`` is a pointer file, so a hard link to it is
    the same inode under a different name and path resolution does not fold
    it away. Writing through that name rewrites where discovery from the
    locked root goes, which is the premise the contract's own guarantees rest
    on -- and it carries no ``.git`` segment, so only the identity comparison
    reaches it.
    """

    _, worktree, branch = _linked_worktree(tmp_path)
    pointer = worktree / ".git"
    assert pointer.is_file(), "a linked worktree carries a pointer file"
    alias = worktree / "repo-pointer"
    os.link(pointer, alias)
    store, _ = _seeded_store(
        tmp_path / "state",
        write_paths=["**"],
        test_paths=[],
        branch=branch,
        repo=worktree,
    )

    decision = _admit(store, "write_file", {"path": "repo-pointer", "content": "x"})

    assert decision.allowed is False
    assert decision.action == "write-git-metadata"
    assert artifact_deny_counter(decision.action) == "denied_count"

    # The same identity comparison on the staging path.
    staged = _admit(
        store,
        "terminal",
        {"command": "git add repo-pointer", "workdir": str(worktree)},
    )
    assert staged.allowed is False
    assert staged.action == "stage-git-metadata"


def test_an_ordinary_file_beside_the_metadata_pointer_is_not_refused(
    tmp_path: Path,
) -> None:
    # The companion to the alias refusal: the comparison must not deny a file
    # that merely lives beside the pointer.
    _, worktree, branch = _linked_worktree(tmp_path)
    store, _ = _seeded_store(
        tmp_path / "state",
        write_paths=["**"],
        test_paths=[],
        branch=branch,
        repo=worktree,
    )

    decision = _admit(store, "write_file", {"path": "notes.md", "content": "x"})

    assert decision.allowed is True
    assert decision.action == "write-in-scope-change"


def test_staging_refuses_gits_own_metadata(tmp_path: Path) -> None:
    store, repo = _seeded_store(tmp_path, write_paths=["**"], test_paths=[])

    decision = _admit(
        store, "terminal", {"command": "git add .git/config", "workdir": str(repo)}
    )

    assert decision.allowed is False
    assert decision.action == "stage-git-metadata"
    assert artifact_deny_counter(decision.action) == "denied_count"


def test_a_linked_worktree_is_admitted_by_the_discovery_check(tmp_path: Path) -> None:
    # The production shape. Both resolved directories live in the primary
    # repository, which is outside every worker ceiling, so the check adds no
    # refusal here. Without this case the containment rule below could be
    # satisfied by refusing everything.
    _, worktree, branch = _linked_worktree(tmp_path)
    store, _ = _seeded_store(
        tmp_path / "state", write_paths=["src/*.py"], test_paths=[], branch=branch, repo=worktree
    )

    staged = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(worktree)}
    )

    assert staged.allowed is True
    assert staged.action == "stage-in-scope-change"


def test_a_git_write_is_refused_when_discovery_resolves_inside_the_locked_root(
    tmp_path: Path,
) -> None:
    # Independent of the write-form refusal above: however the redirection was
    # reached, a repository that lives inside the locked root is agent-writable
    # storage standing in for the real one, and a Git write through it is what
    # turns a file write into execution the contract never declared.
    primary, worktree, branch = _linked_worktree(tmp_path)
    store, _ = _seeded_store(
        tmp_path / "state", write_paths=["**"], test_paths=[], branch=branch, repo=worktree
    )
    before = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(worktree)}
    )
    assert before.allowed is True

    substitute = worktree / "vendor" / "substitute.git"
    substitute.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(primary / ".git", substitute, ignore=shutil.ignore_patterns("worktrees"))
    linked = substitute / "worktrees" / "w1"
    linked.mkdir(parents=True)
    for name in ("HEAD", "index"):
        source = primary / ".git" / "worktrees" / worktree.name / name
        if source.exists():
            shutil.copy2(source, linked / name)
    (linked / "commondir").write_text("../..\n", encoding="utf-8")
    (linked / "gitdir").write_text(str(worktree / ".git") + "\n", encoding="utf-8")
    (worktree / ".git").write_text(f"gitdir: {linked}\n", encoding="utf-8")

    staged = _admit(
        store, "terminal", {"command": "git add src/app.py", "workdir": str(worktree)}
    )
    committed = _admit(
        store, "terminal", {"command": "git commit -m msg", "workdir": str(worktree)}
    )

    assert staged.allowed is False
    assert staged.action == "git-discovery-redirected"
    assert committed.allowed is False
    assert committed.action == "git-discovery-redirected"
    assert artifact_deny_counter(staged.action) == "denied_count"
