"""S3-M1 deterministic core for the artifact-change task class.

Coverage: the path foundation, the explicit write-destination catalogue, the
two contract layers, the contract lifecycle (assignment seed, self lock,
pre-lock default deny, closure), the per-class admission dispatch, and the
adversarial acceptance set required by the design checklist.

Test names stay at the abstraction level of the defect ledger: they name the
property being enforced, not a technique for defeating it.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin_runtime import ScopeGatePluginRuntime
from scope_gate import (
    ARTIFACT_WRITE_TOOL_CATALOG,
    EXECUTION_TEMPLATES,
    GateStore,
    PathRejected,
    collect_write_targets,
    locked_admission_for,
    normalize_repo_relative_path,
    normalize_scope_patterns,
    resolve_existing_ancestor,
    scope_pattern_matches,
    validate_shell_payload,
)

CHANGE_MESSAGE = "ログイン画面のバグを修正して"


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
    branch: str = "main",
    repo: Path | None = None,
) -> tuple[GateStore, Path]:
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

    _, inside = normalize_repo_relative_path("src/new.py", root=str(repo))
    _, escaping = normalize_repo_relative_path("linked/new.py", root=str(repo))

    assert resolve_existing_ancestor(inside, root=str(repo))
    with pytest.raises(PathRejected) as exc:
        resolve_existing_ancestor(escaping, root=str(repo))
    assert exc.value.code == "target-escape"


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
        "git status --short",
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
    assert decision.action == "target-closed"


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
