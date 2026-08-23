"""Assignment-side wiring of the scope gate's contract seed.

These tests cover the orchestrator half of the seeded ``artifact-change`` lane:
the derivation of a seed payload from a card's machine-readable declaration,
the order in which the router records the seed relative to claiming the task,
and the switch that keeps the whole path inert by default.

They live beside the gate's own tests because the gate's seed semantics are
what the router has to satisfy, and because this directory is the suite that
runs without a Hermes runtime.  ``operations.improvement.scope_seed`` carries
no ``hermes_cli`` dependency for that reason; the router module does, so the
ordering test installs a minimal stub for it.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCOPE_SEED_SOURCE = REPO_ROOT / "operations" / "improvement" / "scope_seed.py"
CYCLE_SOURCE = REPO_ROOT / "operations" / "improvement" / "pda_improvement_cycle.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scope_seed = _load("scope_seed_under_test", SCOPE_SEED_SOURCE)


def _card_body(**declaration) -> str:
    return (
        "目的: 何かを直す\n\n"
        f"```{scope_seed.SCOPE_BLOCK_INFO}\n"
        + json.dumps(declaration, ensure_ascii=False, indent=2)
        + "\n```\n\n受入条件: テストが通る\n"
    )


def _repo_with_worktree(tmp_path: Path) -> tuple[Path, Path, str]:
    """Build a primary repository plus one linked worktree.

    The seed requires a real Git worktree root because the gate canonicalises
    the target, so this mirrors what ``_ensure_worktree`` produces.
    """

    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
    }
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, env=env
    )
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True, env=env
    )
    branch = "pda-auto/t_seed"
    worktree = tmp_path / "wt" / "t_seed"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", branch, str(worktree), "main"],
        check=True,
        env=env,
    )
    # The router loads the helper from the repository root at runtime, so the
    # temporary repository has to carry a copy of it.
    target = repo / "operations" / "improvement"
    target.mkdir(parents=True)
    shutil.copy2(SCOPE_SEED_SOURCE, target / "scope_seed.py")
    # The gate resolves its contract JSON schema relative to its own module
    # file, so the copy needs the schema directory beside it.
    gate_source = REPO_ROOT / "integrations" / "hermes-scope-gate"
    gate_target = repo / "integrations" / "hermes-scope-gate"
    gate_target.mkdir(parents=True)
    shutil.copy2(gate_source / "scope_gate.py", gate_target / "scope_gate.py")
    shutil.copytree(gate_source / "schemas", gate_target / "schemas")
    return repo, worktree, branch


# --------------------------------------------------------------------------
# Declaration parsing and payload derivation
# --------------------------------------------------------------------------

def _measure_tree(root: Path) -> Path:
    """A small working tree for the breadth measurement to be taken against.

    More top-level entries than one card's declared scope may cover, so the
    limit is exercised rather than being unreachable, and enough depth that a
    recursive pattern and a single-segment pattern reach different amounts.
    """

    for relative in (
        "src/app.py",
        "src/sub/deep.py",
        "tests/test_app.py",
        "docs/note.md",
        "docs/design/spec.md",
        "schemas/thing.json",
        "README.md",
        "Makefile",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
    return root


@pytest.fixture(scope="session")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _measure_tree(tmp_path_factory.mktemp("measure-tree"))


def _derive(body: object, tree_root: Path, *, task_id: str = "t_1", **kwargs):
    """Derive against a real tree, with the matcher read from this checkout.

    ``tree_root`` is required by the derivation, so the tests pass one too:
    a helper that defaulted it would hide the argument the fence depends on.
    """

    return scope_seed.derive_seed_payload(
        task_id=task_id,
        body=body,
        tree_root=tree_root,
        gate_root=REPO_ROOT,
        **kwargs,
    )


def test_a_card_without_a_declaration_is_not_routable(tree: Path) -> None:
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive("目的: 何か\n受入条件: X\n", tree)
    assert excinfo.value.kind == "missing-scope-declaration"


@pytest.mark.parametrize("body", [None, "", 17, []])
def test_a_non_string_body_is_treated_as_undeclared(body: object, tree: Path) -> None:
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(body, tree)
    assert excinfo.value.kind == "missing-scope-declaration"


def test_two_declarations_are_refused_rather_than_resolved(tree: Path) -> None:
    body = _card_body(write_paths=["src/*.py"]) + _card_body(write_paths=["docs/*.md"])
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(body, tree)
    assert excinfo.value.kind == "invalid-scope-declaration"


def test_an_ordinary_json_block_is_not_mistaken_for_a_declaration(tree: Path) -> None:
    body = '目的: X\n\n```json\n{"write_paths": ["src/*.py"]}\n```\n'
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(body, tree)
    assert excinfo.value.kind == "missing-scope-declaration"


@pytest.mark.parametrize(
    "declaration",
    [
        {},
        {"write_paths": []},
        {"write_paths": "src/*.py"},
        {"write_paths": ["src/*.py", ""]},
        {"write_paths": ["src/*.py"], "test_paths": "tests/x.py"},
        {"write_paths": ["src/*.py"], "execution": [1]},
        {"write_paths": ["src/*.py"], "unexpected": True},
    ],
)
def test_malformed_declarations_are_refused(declaration: dict, tree: Path) -> None:
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(**declaration), tree)
    assert excinfo.value.kind == "invalid-scope-declaration"


def test_the_defaults_grant_no_test_writes_and_no_execution(tree: Path) -> None:
    payload = _derive(_card_body(write_paths=["src/*.py"]), tree)
    assert payload["test_paths"] == []
    assert payload["execution"] == []
    # Omitted git_write means the class default, applied by the gate.
    assert payload["git_write"] is None


def test_git_write_may_narrow_the_class_default(tree: Path) -> None:
    payload = _derive(
        _card_body(write_paths=["src/*.py"], git_write=["stage"]), tree
    )
    assert payload["git_write"] == ["stage"]


@pytest.mark.parametrize("git_write", [["push"], ["stage", "push"], ["merge"]])
def test_git_write_cannot_widen_the_class_default(
    git_write: list[str], tree: Path
) -> None:
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(write_paths=["src/*.py"], git_write=git_write), tree)
    assert excinfo.value.kind == "invalid-scope-declaration"


def test_derivation_is_deterministic_for_an_unchanged_card(tree: Path) -> None:
    """The gate refuses a second seed with a different payload, so re-deriving
    from the same card must not reorder or rewrite anything."""

    body = _card_body(
        write_paths=["src/b.py", "src/a.py"], test_paths=["tests/t_b.py", "tests/t_a.py"]
    )
    first = _derive(body, tree)
    second = _derive(body, tree)
    assert first == second
    # Ordering is left to the gate's normaliser, not re-sorted here.
    assert first["write_paths"] == ["src/b.py", "src/a.py"]


# --------------------------------------------------------------------------
# Seed recording against a real gate store
# --------------------------------------------------------------------------


def test_recording_the_same_declaration_twice_is_idempotent(tmp_path: Path) -> None:
    repo, worktree, branch = _repo_with_worktree(tmp_path)
    state = tmp_path / "scope.db"
    body = _card_body(write_paths=["src/*.py"])
    first = scope_seed.record_seed(
        repo_root=repo,
        task_id="t_seed",
        body=body,
        worktree=worktree,
        branch=branch,
        state_path=state,
    )
    second = scope_seed.record_seed(
        repo_root=repo,
        task_id="t_seed",
        body=body,
        worktree=worktree,
        branch=branch,
        state_path=state,
    )
    assert first == second
    assert first["write_paths"] == ["src/*.py"]
    assert first["git_write"] == ["stage", "commit"]


def test_a_changed_declaration_is_refused_rather_than_replacing_the_ceiling(
    tmp_path: Path,
) -> None:
    repo, worktree, branch = _repo_with_worktree(tmp_path)
    state = tmp_path / "scope.db"
    scope_seed.record_seed(
        repo_root=repo,
        task_id="t_seed",
        body=_card_body(write_paths=["src/*.py"]),
        worktree=worktree,
        branch=branch,
        state_path=state,
    )
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        scope_seed.record_seed(
            repo_root=repo,
            task_id="t_seed",
            body=_card_body(write_paths=["src/*.py", "docs/*.md"]),
            worktree=worktree,
            branch=branch,
            state_path=state,
        )
    assert excinfo.value.kind == "scope-seed-rejected"
    # The original ceiling still stands.
    gate = scope_seed.load_scope_gate(repo)
    store = gate.GateStore(state)
    again = store.record_contract_seed(
        task_id="t_seed",
        worktree=str(worktree),
        branch=branch,
        write_paths=["src/*.py"],
    )
    assert again["write_paths"] == ["src/*.py"]


def test_the_recorded_seed_locks_the_first_turn_of_the_task(tmp_path: Path) -> None:
    """The router's seed is what the gate reads to start a turn enforced.

    This is the assignment-side half of the gate's own seed tests: it proves the
    payload this module writes is the shape the gate consumes.
    """

    repo, worktree, branch = _repo_with_worktree(tmp_path)
    state = tmp_path / "scope.db"
    scope_seed.record_seed(
        repo_root=repo,
        task_id="t_seed",
        body=_card_body(write_paths=["src/*.py"]),
        worktree=worktree,
        branch=branch,
        state_path=state,
    )
    gate = scope_seed.load_scope_gate(repo)
    store = gate.GateStore(state)
    store.start_turn(
        turn_id="turn-1",
        session_id="session-1",
        task_id="t_seed",
        user_message="カードの実装を進めてください",
    )
    turn = store.get_turn("turn-1")
    assert turn is not None
    assert turn["state"] == "locked"
    assert turn["contract_origin"] == "assignment"
    contract = json.loads(turn["contract_json"])
    assert contract["task_class"] == "artifact-change"
    assert contract["targets"]["write_paths"] == ["src/*.py"]
    assert contract["targets"]["worktrees"] == [str(worktree.resolve())]
    # The card declared no execution templates, so the second layer stays shut.
    assert contract["execution"]["templates"] == []


# --------------------------------------------------------------------------
# Router ordering and the activation switch
# --------------------------------------------------------------------------


class _FakeTask:
    def __init__(self, task_id: str, body: str) -> None:
        self.id = task_id
        self.body = body
        self.status = "ready"
        self.assignee = None
        self.skills: list[str] = []
        self.title = "改善カード"


class _FakeKanban(types.ModuleType):
    """Minimal stand-in for ``hermes_cli.kanban_db``.

    Only the surface the router touches is provided.  Every mutation appends to
    ``log`` so the test can assert the order the router performs them in.
    """

    def __init__(self, task: _FakeTask) -> None:
        super().__init__("kanban_db")
        self.task = task
        self.log: list[str] = []

    def get_task(self, conn, task_id):  # noqa: ARG002
        return self.task if task_id == self.task.id else None

    @contextmanager
    def write_txn(self, conn):  # noqa: ARG002
        yield

    def add_comment(self, conn, task_id, author, body):
        conn.execute(
            "INSERT INTO task_comments (task_id, author, body) VALUES (?, ?, ?)",
            (task_id, author, body),
        )
        self.log.append("comment")

    def _append_event(self, conn, task_id, kind, payload):  # noqa: ARG002
        self.log.append(f"event:{kind}")

    def notify_task_updated(self, conn, task_id, fields):  # noqa: ARG002
        self.log.append("notify")


def _cycle_module(kanban: _FakeKanban):
    hermes_cli = types.ModuleType("hermes_cli")
    hermes_cli.kanban_db = kanban  # type: ignore[attr-defined]
    saved = {
        name: sys.modules.get(name)
        for name in ("hermes_cli", "hermes_cli.kanban_db")
    }
    sys.modules["hermes_cli"] = hermes_cli
    sys.modules["hermes_cli.kanban_db"] = kanban
    try:
        return _load("cycle_under_test", CYCLE_SOURCE)
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "kanban.db")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT, assignee TEXT, "
        "workspace_path TEXT, branch_name TEXT, skills TEXT, "
        "consecutive_failures INTEGER DEFAULT 0, last_failure_error TEXT)"
    )
    conn.execute(
        "CREATE TABLE task_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "task_id TEXT, author TEXT, body TEXT)"
    )
    return conn


def _seeded_router(tmp_path: Path, body: str):
    repo, worktree, branch = _repo_with_worktree(tmp_path)
    task = _FakeTask("t_seed", body)
    kanban = _FakeKanban(task)
    cycle = _cycle_module(kanban)
    conn = _conn(tmp_path)
    conn.execute(
        "INSERT INTO tasks (id, status, assignee) VALUES (?, 'ready', NULL)", (task.id,)
    )
    conn.commit()
    return cycle, kanban, conn, repo, worktree, branch


def test_the_router_records_the_seed_before_claiming_and_notifies_last(
    tmp_path: Path,
) -> None:
    """Seed -> assignment CAS -> notification.

    The two stores cannot share a transaction, so the ordering is the failure
    handling: the notification that wakes the dispatcher must never fire for a
    task whose ceiling is not already recorded.
    """

    cycle, kanban, conn, repo, worktree, branch = _seeded_router(
        tmp_path, _card_body(write_paths=["src/*.py"])
    )
    state = tmp_path / "scope.db"
    gate = scope_seed.load_scope_gate(repo)

    seen_at_cas: list[bool] = []
    original_append = kanban._append_event

    def spy_append(conn_, task_id, kind, payload):
        if kind == "assigned":
            store = gate.GateStore(state)
            seen_at_cas.append(store.get_contract_seed(task_id) is not None)
        return original_append(conn_, task_id, kind, payload)

    kanban._append_event = spy_append  # type: ignore[assignment]

    cycle._route_task(
        conn,
        kanban.task,
        worktree,
        branch,
        "default",
        repo=repo,
        scope_seed_enabled=True,
        scope_seed_state_path=state,
    )

    assert seen_at_cas == [True], "the seed must exist by the time the task is claimed"
    assert kanban.log[-1] == "notify", "the dispatcher notification is last"
    assert kanban.log.index("event:assigned") < kanban.log.index("notify")
    row = conn.execute("SELECT assignee, branch_name FROM tasks").fetchone()
    assert row["assignee"] == "default"
    assert row["branch_name"] == branch


def test_the_router_leaves_the_card_unassigned_when_the_scope_is_undeclared(
    tmp_path: Path,
) -> None:
    cycle, kanban, conn, repo, worktree, branch = _seeded_router(
        tmp_path, "目的: 何か\n受入条件: X\n"
    )
    state = tmp_path / "scope.db"
    with pytest.raises(cycle.CycleError) as excinfo:
        cycle._route_task(
            conn,
            kanban.task,
            worktree,
            branch,
            "default",
            repo=repo,
            scope_seed_enabled=True,
            scope_seed_state_path=state,
        )
    assert excinfo.value.kind == "missing-scope-declaration"
    row = conn.execute("SELECT assignee FROM tasks").fetchone()
    assert row["assignee"] is None
    assert "notify" not in kanban.log
    assert "event:assigned" not in kanban.log
    comments = conn.execute("SELECT body FROM task_comments").fetchall()
    assert len(comments) == 1
    assert scope_seed.SCOPE_BLOCK_INFO in comments[0]["body"]


def test_a_repeatedly_unroutable_card_collects_one_comment(tmp_path: Path) -> None:
    """The router runs on a timer; a stuck card must not accrue one comment per
    tick."""

    cycle, kanban, conn, repo, worktree, branch = _seeded_router(
        tmp_path, "目的: 何か\n受入条件: X\n"
    )
    state = tmp_path / "scope.db"
    for _ in range(3):
        with pytest.raises(cycle.CycleError):
            cycle._route_task(
                conn,
                kanban.task,
                worktree,
                branch,
                "default",
                repo=repo,
                scope_seed_enabled=True,
                scope_seed_state_path=state,
            )
    count = conn.execute("SELECT COUNT(*) FROM task_comments").fetchone()[0]
    assert count == 1


def test_a_changed_declaration_mid_flight_surfaces_instead_of_replacing_the_seed(
    tmp_path: Path,
) -> None:
    cycle, kanban, conn, repo, worktree, branch = _seeded_router(
        tmp_path, _card_body(write_paths=["src/*.py"])
    )
    state = tmp_path / "scope.db"
    cycle._route_task(
        conn,
        kanban.task,
        worktree,
        branch,
        "default",
        repo=repo,
        scope_seed_enabled=True,
        scope_seed_state_path=state,
    )
    # Re-routing after the card's declaration was edited must not quietly
    # install a wider ceiling.
    kanban.task.status = "ready"
    kanban.task.assignee = None
    conn.execute("UPDATE tasks SET assignee = NULL, status = 'ready'")
    conn.commit()
    kanban.task.body = _card_body(write_paths=["src/*.py", "docs/*.md"])
    with pytest.raises(cycle.CycleError) as excinfo:
        cycle._route_task(
            conn,
            kanban.task,
            worktree,
            branch,
            "default",
            repo=repo,
            scope_seed_enabled=True,
            scope_seed_state_path=state,
        )
    assert excinfo.value.kind == "scope-seed-rejected"
    gate = scope_seed.load_scope_gate(repo)
    seed = gate.GateStore(state).get_contract_seed("t_seed")
    assert seed is not None and seed["write_paths"] == ["src/*.py"]


def test_the_flag_defaults_off_and_records_nothing(tmp_path: Path) -> None:
    """With the switch off the lane behaves exactly as before: no seed, and no
    declaration requirement either."""

    cycle, kanban, conn, repo, worktree, branch = _seeded_router(
        tmp_path, "目的: 宣言のないカード\n受入条件: X\n"
    )
    state = tmp_path / "scope.db"
    cycle._route_task(
        conn,
        kanban.task,
        worktree,
        branch,
        "default",
        repo=repo,
        scope_seed_enabled=False,
    )
    row = conn.execute("SELECT assignee FROM tasks").fetchone()
    assert row["assignee"] == "default"
    assert kanban.log[-1] == "notify"
    assert not state.exists(), "no seed store is created while the switch is off"


def test_the_committed_policy_default_keeps_the_seed_path_off() -> None:
    policy = json.loads(
        (REPO_ROOT / "continuity" / "autonomous-improvement.json").read_text(
            encoding="utf-8"
        )
    )
    assert policy["scope_seed"]["enabled"] is False


# --------------------------------------------------------------------------
# The ceiling on the ceiling, and which Markdown regions are live
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    ["**", "**/*", "*", "*/**", "*/src/*.py", " ** ", "**/*.py"],
)
def test_a_declaration_cannot_stand_in_for_the_whole_tree(
    pattern: str, tree: Path
) -> None:
    """The declared ceiling must name what it covers.

    Design §3.2 declined a tenant-wide default because a broad ceiling makes
    the seed path meaningless. A card body is written by a model, so without a
    mechanical limit the same breadth is reachable through the declaration and
    the only thing standing against it is prose in the reconciler prompt.
    """

    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(write_paths=[pattern]), tree, task_id="t1")

    assert excinfo.value.kind == "invalid-scope-declaration"


def test_the_same_limit_applies_to_declared_test_assets(tree: Path) -> None:
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(
            _card_body(write_paths=["src/*.py"], test_paths=["**"]),
            tree,
            task_id="t1",
        )

    assert excinfo.value.kind == "invalid-scope-declaration"


@pytest.mark.parametrize(
    "pattern",
    [
        "src/**",
        "src/*.py",
        "src/sub/*.py",
        "README.md",
        "src*/**",
        "*.py",
    ],
)
def test_an_anchored_pattern_of_any_depth_is_still_accepted(
    pattern: str, tree: Path
) -> None:
    # The companion to the refusal above: the limit rejects breadth, not
    # recursion, prefixes, or single-segment globs. A class that requires no
    # false denial cannot afford a limit that narrows the ordinary forms.
    payload = _derive(_card_body(write_paths=[pattern]), tree, task_id="t1")

    assert payload["write_paths"] == [pattern]


# --------------------------------------------------------------------------
# The breadth the declaration actually buys, measured against the tree
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    [
        "?*",
        "?*/**",
        "?**",
        "*?",
        "*?/**",
        "??*/**",
        "[a-zA-Z0-9._-]*/**",
    ],
)
def test_a_spelling_that_evades_the_floor_is_still_measured(
    pattern: str, tree: Path
) -> None:
    """The property the spelling rule was standing in for.

    Two literal spellings are what the floor compares, and the pattern
    language writes the same breadth many other ways. What has to hold is a
    bound on the breadth itself, so it is measured against the tree the
    worktree is a checkout of and stated on a quantity no spelling changes.
    """

    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(write_paths=[pattern]), tree, task_id="t1")

    assert excinfo.value.kind == "invalid-scope-declaration"


def test_the_measured_breadth_is_the_union_of_both_declared_fields(
    tree: Path,
) -> None:
    """The gate matches a write against write_paths and test_paths together.

    Measuring the fields separately would let two halves that each pass the
    limit add up to a ceiling that does not.
    """

    within = _derive(
        _card_body(write_paths=["src/**"], test_paths=["tests/**"]), tree, task_id="t1"
    )
    assert within["write_paths"] == ["src/**"]

    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(
            _card_body(
                write_paths=["src/**", "docs/**"],
                test_paths=["tests/**", "schemas/**"],
            ),
            tree,
            task_id="t1",
        )
    assert excinfo.value.kind == "invalid-scope-declaration"


def test_the_limit_is_configurable_without_changing_the_measurement(
    tree: Path,
) -> None:
    # A lane that needs a wider ceiling raises the limit in the committed
    # policy; the measurement itself does not move.
    declaration = _card_body(
        write_paths=["src/**", "docs/**"], test_paths=["tests/**", "schemas/**"]
    )

    with pytest.raises(scope_seed.ScopeSeedError):
        _derive(declaration, tree, task_id="t1", max_top_level_entries=3)

    payload = _derive(declaration, tree, task_id="t1", max_top_level_entries=4)

    assert payload["test_paths"] == ["tests/**", "schemas/**"]


@pytest.mark.parametrize(
    "pattern",
    [
        # A pattern whose text places it on a governance surface, including a
        # destination that does not exist yet and so matches nothing.
        "operations/improvement/*.py",
        "operations/improvement/brand_new_module.py",
        "integrations/hermes-scope-gate/**",
        "docs/design/task-scope-admission-gate.md",
        "conftest.py",
        "src/**/conftest.py",
        "infra/systemd/*.service",
    ],
)
def test_a_declaration_covering_a_governance_surface_is_refused(
    pattern: str, tree: Path
) -> None:
    """The refusal that finalization would make anyway, moved to the front.

    ``install.py`` refuses an approval contract whose diff touches a
    governance path outright, so a card that declares one buys work that can
    never be finalized. Refusing at declaration time is the same rule applied
    where the card can still be corrected.
    """

    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(write_paths=[pattern]), tree, task_id="t1")

    assert excinfo.value.kind == "invalid-scope-declaration"


def test_a_governance_file_reached_by_a_wide_pattern_is_refused(
    tmp_path: Path,
) -> None:
    # The measurement side of the same rule: the pattern's own text names no
    # governance path, but what it covers in the tree does.
    root = tmp_path / "governed"
    for relative in ("docs/note.md", "docs/roadmap/current-priority.md"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")

    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(write_paths=["docs/**"]), root, task_id="t1")

    assert excinfo.value.kind == "invalid-scope-declaration"


def test_the_governance_surfaces_match_the_activation_gate() -> None:
    """Two implementations of one rule, pinned by comparison.

    The declaration-time refusal and the activation-time refusal have to name
    the same surfaces, or a card is accepted for work the activation path will
    reject.
    """

    # Read rather than imported: ``install.py`` carries the Hermes runtime
    # dependency this suite runs without, and the value being compared is a
    # tuple of string literals, so reading the assignment is a faithful
    # reading of it here.
    source = (REPO_ROOT / "operations" / "improvement" / "install.py").read_text(
        encoding="utf-8"
    )
    declared: tuple[str, ...] | None = None
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "GOVERNANCE_PATHS"
            for target in node.targets
        ):
            continue
        assert isinstance(node.value, ast.Tuple)
        entries = []
        for element in node.value.elts:
            assert isinstance(element, ast.Constant) and isinstance(element.value, str)
            entries.append(element.value)
        declared = tuple(entries)
    assert declared is not None, "install.py no longer declares GOVERNANCE_PATHS"

    assert scope_seed.GOVERNANCE_PATHS == declared


def test_an_unmeasurable_tree_refuses_rather_than_assuming_narrowness(
    tmp_path: Path,
) -> None:
    # Fail closed: without a tree there is no measured breadth, and an
    # unmeasured ceiling is not evidence of a narrow one.
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(_card_body(write_paths=["src/**"]), tmp_path / "absent", task_id="t1")

    assert excinfo.value.kind == "scope-breadth-unmeasured"


def _wrapped(inner: str) -> str:
    return "目的: 直す\n\n" + inner + "\n受入条件: X\n"


def test_an_indented_example_is_not_a_live_declaration(tree: Path) -> None:
    """Four columns of indentation is literal text in Markdown.

    Reading it as a declaration lets prose written for a human reader decide
    the ceiling, which inverts the direction the field is supposed to work in.
    """

    body = _wrapped(
        "    ```pda-scope\n"
        '    {"write_paths": ["**"]}\n'
        "    ```\n"
    )

    assert scope_seed.scope_declaration_blocks(body) == []
    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(body, tree, task_id="t1")
    assert excinfo.value.kind == "missing-scope-declaration"


@pytest.mark.parametrize("outer", ["````", "~~~~"])
def test_a_declaration_shown_inside_an_example_block_is_inert(outer: str) -> None:
    body = _wrapped(
        f"{outer}\n"
        "```pda-scope\n"
        '{"write_paths": ["**"]}\n'
        "```\n"
        f"{outer}\n"
    )

    assert scope_seed.scope_declaration_blocks(body) == []


def test_a_real_declaration_beside_a_worked_example_is_not_ambiguous(
    tree: Path,
) -> None:
    """The other direction of the same defect.

    Documenting the form next to the real declaration used to make the card
    look like it carried two ceilings, so the card was refused. Refusing a
    correctly written card is the failure this field cannot have.
    """

    body = _wrapped(
        "````\n"
        "```pda-scope\n"
        '{"write_paths": ["docs/**"]}\n'
        "```\n"
        "````\n\n"
        "```pda-scope\n"
        '{"write_paths": ["src/*.py"]}\n'
        "```\n"
    )

    payload = _derive(body, tree, task_id="t1")

    assert payload["write_paths"] == ["src/*.py"]


def test_two_live_declarations_are_still_refused(tree: Path) -> None:
    # The ambiguity refusal has to survive the inert-region handling.
    body = _wrapped(
        "```pda-scope\n"
        '{"write_paths": ["docs/**"]}\n'
        "```\n\n"
        "```pda-scope\n"
        '{"write_paths": ["src/*.py"]}\n'
        "```\n"
    )

    with pytest.raises(scope_seed.ScopeSeedError) as excinfo:
        _derive(body, tree, task_id="t1")

    assert excinfo.value.kind == "invalid-scope-declaration"


def test_the_documented_declaration_example_is_the_accepted_form(tree: Path) -> None:
    """The operations runbook is the form a specifier copies.

    An example that the parser does not recognise makes the runbook a source
    of unroutable cards, which is the same outage as an undeclared card.
    """

    runbook = (REPO_ROOT / "docs" / "operations" / "pda-improvement-cycle.md").read_text(
        encoding="utf-8"
    )
    marker = "````\n```" + scope_seed.SCOPE_BLOCK_INFO + "\n"
    start = runbook.index(marker) + len("````\n")
    end = runbook.index("````", start)
    shown = runbook[start:end]

    payload = _derive(shown, tree, task_id="t1")

    assert payload["write_paths"]


# --------------------------------------------------------------------------
# Cross-implementation agreement
# --------------------------------------------------------------------------


def test_the_class_default_matches_the_gate_that_enforces_it(tmp_path: Path) -> None:
    """Two independent literals, pinned equal.

    The router decides "narrowing only" from its own copy of the class
    default, and the gate decides what it will accept from its own. A drift
    between them is either a card that cannot declare an action the gate
    admits, or a declaration the router passes and the gate refuses at
    assignment time.
    """

    repo, _, _ = _repo_with_worktree(tmp_path)
    gate = scope_seed.load_scope_gate(repo)

    assert tuple(scope_seed.CLASS_DEFAULT_GIT_WRITE) == tuple(
        gate.ARTIFACT_GIT_WRITE_ACTIONS
    )


def test_the_router_reads_the_gate_the_installer_deploys() -> None:
    """The seed writer and the enforcer must be the same implementation.

    The installer publishes the gate as a symlink to this directory, so the
    enforcing copy is this file. The router resolves its copy from the
    repository root it was configured with. Pinning the two paths equal is
    what makes the normalisation semantics behind a recorded ceiling and an
    enforced ceiling the same semantics.
    """

    install = _load(
        "scope_gate_install_under_test",
        REPO_ROOT / "integrations" / "hermes-scope-gate" / "install.py",
    )
    installer_source = Path(install.__file__).resolve().parent
    router_source = (
        REPO_ROOT / "integrations" / "hermes-scope-gate" / "scope_gate.py"
    ).resolve()

    assert (installer_source / "scope_gate.py").resolve() == router_source
