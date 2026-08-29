"""Assignment-time scope seed derivation for the PDA improvement lane.

The scope gate treats the presence of a contract seed as the switch that puts
an ``artifact-change`` turn under hard enforcement, and the seed is a standing
ceiling the executing agent cannot widen.  Recording it therefore belongs on
the orchestrator side of the boundary (INV-S8), which is this module: the
router calls it at assignment time, before the worker exists.

This module deliberately carries no ``hermes_cli`` dependency so the
derivation and the store interaction stay testable without a Hermes runtime.
The Kanban-side wiring lives in ``pda_improvement_cycle``.

The write scope is read from a machine-readable declaration on the card.  No
tenant-wide default is supplied: the point of a seed is a narrow ceiling, and
a broad default would make the seed path meaningless.  A card without a
declaration is not assigned.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# The fenced block that carries the machine-readable declaration. The info
# string is matched exactly so an ordinary JSON example in a card body cannot
# be mistaken for a scope declaration.
SCOPE_BLOCK_INFO = "pda-scope"

# A code fence opens at column 0 through column 3; a run of backticks indented
# four or more columns is literal text inside an indented code block, not a
# fence. Both fence characters CommonMark defines are recognised so a
# declaration shown inside a tilde-fenced example stays inert.
_FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")

# Declared scope patterns must name the top level rather than stand in for all
# of it. A leading wildcard segment is the one form whose breadth is unbounded
# by anything a reader of the card can see, and it reaches the same state
# design §3.2 refused when it declined to ship a tenant-wide default: a
# ceiling that covers the whole tree makes the seed path meaningless. Every
# other glob is bounded by the literal text around it: a single-segment
# pattern cannot match a nested path at all, and a prefixed segment is
# bounded by its prefix.
_UNANCHORED_FIRST_SEGMENTS = frozenset({"*", "**"})

# How many top-level entries of the real tree one card's declaration may reach.
# This is the mechanical limit on the limit. The spelling rule above is a
# tree-independent floor and no more than that: an open argument space cannot
# be closed by enumerating spellings, and a pattern language with in-segment
# wildcards and character classes can express the same breadth many ways. So
# the breadth a declaration actually buys is measured instead of parsed --
# matched against the tree the worktree is made from -- and the count of
# distinct top-level entries it covers is what the limit is stated on. That
# quantity is what design §3.2 was protecting when it declined a tenant-wide
# default, and it is invariant under how the patterns are written.
#
# The default is conservative rather than fitted: the cards this lane routes
# name one area plus its tests, and a card that genuinely needs more is a card
# that should be split. ``max_top_level_entries`` in the ``scope_seed`` policy
# block raises it for a lane that needs to.
MAX_DECLARED_TOP_LEVEL_ENTRIES = 3

# Directory entries the walk never descends into. Git's own metadata is not a
# declarable destination in any case (the gate refuses it whatever the
# declaration says), and walking it would make the measured count depend on
# repository internals rather than on the working tree.
_UNWALKED_DIRECTORY_NAMES = frozenset({".git"})

# Governance surfaces (ADR D3), duplicated from ``install.py`` on purpose: a
# worker finalization may never change the rules that judge workers, and the
# activation path refuses an approval contract whose diff touches these paths
# outright. A declaration that covers them therefore buys work that can never
# be finalized, so the refusal belongs at declaration time where the card can
# still be fixed. The duplication is pinned by a cross-implementation equality
# test, which is the discipline this repository already applies to the
# approval-side copy.
GOVERNANCE_PATHS = (
    "pda_charter.md",
    "conftest.py",
    "continuity/autonomous-improvement.json",
    "continuity/local-backup.json",
    "profiles/pda/managed-habits.json",
    "profiles/pda/skills/pda-autonomous-improvement/",
    "schemas/",
    "docs/design/self-improvement-governance-adr.md",
    "docs/design/task-scope-admission-gate.md",
    "docs/design/auto-integration-gate.md",
    "docs/design/improvement-orchestrator.md",
    "docs/design/staged-verification.md",
    "docs/roadmap/autonomous-improvement-goal.md",
    "docs/roadmap/autonomous-improvement-operating-rules.md",
    "docs/roadmap/current-priority.md",
    "docs/operations/adversarial-suite.md",
    "docs/operations/pda-improvement-cycle.md",
    "docs/operations/worktree-lifecycle.md",
    "docs/status/",
    "integrations/hermes-kanban-governance/",
    "integrations/hermes-scope-gate/",
    "integrations/hermes-pda-approvals/",
    "operations/improvement/",
    "operations/backup/",
    "src/pda/backup/",
    "infra/systemd/",
)

# D-S3-3 class default. A card may narrow this set, never widen it.
CLASS_DEFAULT_GIT_WRITE = ("stage", "commit")

_DECLARATION_KEYS = frozenset(
    {"write_paths", "test_paths", "execution", "git_write"}
)


class ScopeSeedError(RuntimeError):
    """A card's scope declaration is missing, malformed, or too wide."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def _string_list(raw: Any, field: str) -> list[str]:
    if not isinstance(raw, list) or not all(
        isinstance(item, str) and item.strip() for item in raw
    ):
        raise ScopeSeedError(
            "invalid-scope-declaration",
            f"{field} must be a list of non-empty strings",
        )
    return [item for item in raw]


def scope_declaration_blocks(body: Any) -> list[str]:
    """Every live ``pda-scope`` fenced block in a card body.

    Recognition follows the two Markdown facts a single regular expression
    could not carry: a fence opened while another fence is already open is
    content of the outer block rather than a fence of its own, and a run of
    backticks indented four or more columns is literal text. Both directions
    matter for this field. A worked example written for a human reader must
    not become the effective ceiling, and a card that shows an example
    alongside its real declaration must not be refused as ambiguous -- the
    ceiling is a Ready condition on a class that requires no false denial.
    """

    text = body if isinstance(body, str) else ""
    blocks: list[str] = []
    open_fence: str | None = None
    collecting: list[str] | None = None
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if match is None:
            if collecting is not None:
                collecting.append(line)
            continue
        marker = match.group("fence")
        info = match.group("info").strip()
        if open_fence is None:
            open_fence = marker
            # An info string is only meaningful on the opening fence, and the
            # declaration's is matched exactly: a block labelled anything else
            # is an ordinary example whose contents are skipped.
            collecting = [] if info == SCOPE_BLOCK_INFO else None
            continue
        closes = (
            marker[0] == open_fence[0]
            and len(marker) >= len(open_fence)
            and not info
        )
        if not closes:
            # A fence line that does not close the open block is part of it.
            if collecting is not None:
                collecting.append(line)
            continue
        if collecting is not None:
            blocks.append("\n".join(collecting))
        open_fence = None
        collecting = None
    return blocks


def parse_scope_declaration(body: Any) -> dict[str, Any]:
    """Extract the scope declaration from a card body.

    Exactly one ``pda-scope`` block must be present. Zero blocks means the
    card is not Ready for the seeded lane; more than one is ambiguous and is
    refused rather than resolved by picking one.
    """

    blocks = scope_declaration_blocks(body)
    if not blocks:
        raise ScopeSeedError(
            "missing-scope-declaration",
            "card has no machine-readable ```"
            + SCOPE_BLOCK_INFO
            + "``` write scope declaration",
        )
    if len(blocks) > 1:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            f"card declares {len(blocks)} {SCOPE_BLOCK_INFO} blocks; exactly one is required",
        )
    try:
        declaration = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            f"{SCOPE_BLOCK_INFO} block is not valid JSON: {exc}",
        ) from exc
    if not isinstance(declaration, dict):
        raise ScopeSeedError(
            "invalid-scope-declaration",
            f"{SCOPE_BLOCK_INFO} block must contain a JSON object",
        )
    unknown = sorted(set(declaration) - _DECLARATION_KEYS)
    if unknown:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            "unknown scope declaration keys: " + ", ".join(unknown),
        )
    return declaration


def _reject_unanchored_patterns(patterns: list[str], field: str) -> None:
    """Refuse the spellings that state whole-tree breadth outright.

    A floor, not the guarantee. This rule compares two spellings, and a
    pattern language with in-segment wildcards and character classes can write
    the same breadth other ways, so what bounds the ceiling is the measured
    breadth in ``_reject_overbroad_scope`` -- a quantity that does not depend
    on the spelling. The floor is kept because it holds without a tree to
    measure against, which keeps the plainest form of the defect refused
    independently of how small a tree the measurement happens to see.

    The check lives here, on the router side, so the gate's shared pattern
    normalisation stays free of rules that belong to one task class
    (D-S3-7 決定 1).
    """

    offenders = sorted(
        {
            pattern
            for pattern in patterns
            if pattern.strip().split("/", 1)[0].strip() in _UNANCHORED_FIRST_SEGMENTS
        }
    )
    if offenders:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            f"{field} must name the paths it covers rather than begin with a "
            "wildcard segment; refused: " + ", ".join(offenders),
        )


def _is_governance_path(path: str) -> bool:
    """Mirror of ``install.py::_is_governance_path`` (pinned by an equality test)."""

    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    # Any conftest.py anywhere is part of the test-isolation guard (C7).
    if Path(normalized).name == "conftest.py":
        return True
    for entry in GOVERNANCE_PATHS:
        if entry.endswith("/"):
            if normalized.startswith(entry):
                return True
        elif normalized == entry:
            return True
    return False


def _pattern_reaches_below(pattern_segments: tuple[str, ...], entry_segments: tuple[str, ...]) -> bool:
    """Whether the pattern can match some path *below* a governance directory.

    Compared segment by segment rather than as literal text, because a
    wildcard placed on a governance directory's own name (``docs/*/new.md``,
    ``docs/sta*/new.md``) covers the surface without spelling it. ``**``
    crosses separators, so it may consume any number of the directory's
    segments; every other segment consumes exactly one, matched with
    ``fnmatch`` so the pattern's own wildcards decide.

    The pattern has to reach past the directory: covering the directory entry
    itself is not covering its contents, which is the same line
    ``_is_governance_path`` draws.
    """

    if not entry_segments:
        return bool(pattern_segments)
    if not pattern_segments:
        return False
    head, rest = pattern_segments[0], pattern_segments[1:]
    if head == "**":
        if not rest:
            return True
        return _pattern_reaches_below(rest, entry_segments) or _pattern_reaches_below(
            pattern_segments, entry_segments[1:]
        )
    if fnmatch.fnmatchcase(entry_segments[0], head):
        return _pattern_reaches_below(rest, entry_segments[1:])
    return False


def _pattern_names_governance(pattern: str) -> bool:
    """True when a pattern can place a not-yet-existing file on a governance surface.

    The tree walk below catches a pattern that covers a governance file which
    exists. This catches the same pattern aimed at a name that does not exist
    yet: a new file under a governance directory matches nothing in the tree,
    so measurement alone would let the declaration through and the refusal
    would only arrive at finalization, after the work was done.

    Directory surfaces are tested as patterns against the directory's
    segments, not as a prefix of the pattern's text: a spelling that puts a
    wildcard on the directory's own name reaches the same files while sharing
    no literal prefix with it. The single-file entries stay a text comparison
    -- each of them is a file that exists, so a wildcard spelling aimed at one
    is already caught by the measurement against the tree.
    """

    text = pattern.strip()
    while text.startswith("./"):
        text = text[2:]
    if Path(text).name == "conftest.py":
        return True
    segments = tuple(part for part in text.split("/") if part)
    for entry in GOVERNANCE_PATHS:
        if entry.endswith("/"):
            if text.startswith(entry) or _pattern_reaches_below(
                segments, tuple(part for part in entry.split("/") if part)
            ):
                return True
        elif text == entry:
            return True
    return False


# The tree walk is bounded so a pathological worktree cannot make one routing
# tick unbounded. Exhausting the budget means the breadth was not measured, and
# an unmeasured ceiling is refused rather than assumed narrow.
_MAX_TREE_ENTRIES_SCANNED = 200_000


def _measure_declared_breadth(
    patterns: list[str], *, tree_root: Path, matches
) -> tuple[set[str], list[str]]:
    """Match the declared patterns against the real tree.

    Returns the set of top-level entries the declaration reaches and the
    governance paths among the matches. Directories are matched as well as
    files: a pattern that names only top-level files would otherwise reach the
    floor of the tree without being counted.
    """

    covered: set[str] = set()
    governance: list[str] = []
    scanned = 0

    def _consider(relative: str) -> None:
        nonlocal governance
        if not any(matches(pattern, relative) for pattern in patterns):
            return
        covered.add(relative.split("/", 1)[0])
        if len(governance) < 3 and _is_governance_path(relative):
            governance.append(relative)

    for current, directory_names, file_names in os.walk(
        str(tree_root), followlinks=False
    ):
        directory_names[:] = [
            name for name in directory_names if name not in _UNWALKED_DIRECTORY_NAMES
        ]
        base = Path(current).relative_to(tree_root)
        for name in list(directory_names) + file_names:
            scanned += 1
            if scanned > _MAX_TREE_ENTRIES_SCANNED:
                raise ScopeSeedError(
                    "scope-breadth-unmeasured",
                    "the worktree is too large to measure the declared scope "
                    f"against ({_MAX_TREE_ENTRIES_SCANNED} entries scanned)",
                )
            _consider((base / name).as_posix())
    return covered, governance


def _reject_overbroad_scope(
    patterns: list[str], *, tree_root: Path, matches, limit: int
) -> None:
    """Refuse a declaration whose measured breadth exceeds the class ceiling.

    Measured, not parsed. The spelling rule is a floor that holds without a
    tree; this is the property the floor was standing in for, taken on the
    tree the worktree is a checkout of, so it does not depend on how the
    patterns are written.
    """

    for pattern in patterns:
        if _pattern_names_governance(pattern):
            raise ScopeSeedError(
                "invalid-scope-declaration",
                "the declared scope covers a governance surface, which only the "
                f"owner commits: {pattern}",
            )
    covered, governance = _measure_declared_breadth(
        patterns, tree_root=tree_root, matches=matches
    )
    if governance:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            "the declared scope covers governance surfaces, which only the "
            "owner commits: " + ", ".join(governance),
        )
    if len(covered) > limit:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            f"the declared scope reaches {len(covered)} top-level entries of the "
            f"repository ({', '.join(sorted(covered)[:6])}); at most {limit} are "
            "allowed, so split the card or name the paths the work needs",
        )


_BASE_COMMIT_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _normalized_base_commit(raw: Any) -> str:
    """The assignment-time base commit, or "" when the caller states none.

    The value never comes from the card and never from the worker: it is the
    commit the assigning side resolved when it created the worktree. A card
    cannot smuggle one in either, because the declaration's key set is closed
    and ``base_commit`` is not in it.
    """

    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ScopeSeedError(
            "invalid-base-commit", "the assignment-time base commit must be a string"
        )
    value = raw.strip()
    if not value:
        return ""
    if not _BASE_COMMIT_RE.match(value):
        raise ScopeSeedError(
            "invalid-base-commit",
            "the assignment-time base commit must be a full lowercase "
            f"hexadecimal Git object name; got {value!r}",
        )
    return value


def derive_seed_payload(
    *,
    task_id: str,
    body: Any,
    tree_root: Path | str,
    gate_root: Path | str | None = None,
    max_top_level_entries: int | None = None,
    base_commit: str | None = None,
) -> dict[str, Any]:
    """Turn a card body into the keyword arguments for a contract seed.

    The derivation is deterministic and performs no ordering or de-duplication
    of its own: pattern normalisation is the gate's single responsibility
    (``normalize_scope_patterns``).  Re-deriving from an unchanged card must
    produce a byte-identical payload, because the gate refuses a second seed
    whose payload differs from the first.  The breadth measurement decides
    acceptance only; it never changes the payload, so the gate's idempotent
    path is unaffected.

    ``tree_root`` has no default. The declared ceiling is measured against a
    real tree, and a caller that omits the tree would get the spelling floor
    alone -- the state this argument exists to end. ``gate_root`` names the
    checkout the pattern matcher is read from and defaults to ``tree_root``;
    the router passes the primary repository so the matcher never comes from a
    tree a worker can write to.

    ``base_commit`` is the commit the assigned worktree starts from. It is an
    argument rather than something read out of the card because the card is
    worker-writable and the value has to be the assigning side's own
    resolution. It is optional here so the pre-worktree admission check can
    reuse this derivation before a base exists; ``record_seed`` is where the
    value becomes mandatory, because that is the payload that gets stored.
    """

    declaration = parse_scope_declaration(body)
    write_paths = _string_list(declaration.get("write_paths"), "write_paths")
    if not write_paths:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            "write_paths must declare at least one pattern",
        )
    _reject_unanchored_patterns(write_paths, "write_paths")
    # Defaults: test asset writes are not granted unless declared, and the
    # second contract layer stays closed unless the card opts in.
    test_paths = _string_list(declaration.get("test_paths", []), "test_paths")
    _reject_unanchored_patterns(test_paths, "test_paths")
    execution = _string_list(declaration.get("execution", []), "execution")

    # The union, because the gate matches a write against both fields at once:
    # the effective ceiling is what the two together reach, not either alone.
    resolved_tree = Path(tree_root)
    if not resolved_tree.is_dir():
        raise ScopeSeedError(
            "scope-breadth-unmeasured",
            f"the tree to measure the declared scope against is missing: {resolved_tree}",
        )
    gate = load_scope_gate(Path(gate_root) if gate_root is not None else resolved_tree)
    _reject_overbroad_scope(
        write_paths + test_paths,
        tree_root=resolved_tree,
        matches=gate.scope_pattern_matches,
        limit=(
            MAX_DECLARED_TOP_LEVEL_ENTRIES
            if max_top_level_entries is None
            else int(max_top_level_entries)
        ),
    )

    if "git_write" in declaration:
        git_write: list[str] | None = _string_list(
            declaration.get("git_write"), "git_write"
        )
        widened = sorted(set(git_write or ()) - set(CLASS_DEFAULT_GIT_WRITE))
        if widened:
            raise ScopeSeedError(
                "invalid-scope-declaration",
                "git_write may only narrow the class default; unknown actions: "
                + ", ".join(widened),
            )
    else:
        # Omitted means the class default; the gate applies it.
        git_write = None

    return {
        "task_id": task_id,
        "write_paths": write_paths,
        "test_paths": test_paths,
        "execution": execution,
        "git_write": git_write,
        "base_commit": _normalized_base_commit(base_commit),
    }


def load_scope_gate(repo_root: Path):
    """Import the scope gate module from its canonical location in the repo.

    The gate is a Hermes plugin file rather than an installed package, so it is
    loaded from an explicit path anchored at the repository root instead of
    relying on ``sys.path`` ordering.
    """

    module_path = (
        Path(repo_root)
        / "integrations"
        / "hermes-scope-gate"
        / "scope_gate.py"
    )
    if not module_path.is_file():
        raise ScopeSeedError(
            "scope-gate-missing", f"scope gate module not found: {module_path}"
        )
    # Keyed by the resolved path so two different repository roots in one
    # process cannot silently share the first one's module object.
    name = "pda_scope_gate_" + hashlib.sha256(
        str(module_path.resolve()).encode("utf-8")
    ).hexdigest()[:16]
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ScopeSeedError(
            "scope-gate-missing", f"scope gate module is not importable: {module_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def record_seed(
    *,
    repo_root: Path,
    task_id: str,
    body: Any,
    worktree: Path | str,
    branch: str,
    base_commit: str,
    state_path: Path | str | None = None,
    max_top_level_entries: int | None = None,
) -> dict[str, Any]:
    """Record the assignment-time contract seed for one task.

    Raises ``ScopeSeedError`` for every failure, including a second seed whose
    payload differs from the one already recorded.  A differing payload means
    the card's declaration changed while the task was in flight; the gate
    refuses it, and surfacing that as an error keeps the ceiling meaningful
    instead of silently accepting a new one.

    The breadth is measured against the worktree this seed is being recorded
    for -- the tree the ceiling will actually govern -- while the matcher is
    read from the primary repository, which is outside every worker's ceiling.

    ``base_commit`` has no default on purpose. It is the record of which
    commit the assigned worktree started from, and a caller that may omit it
    would record a seed that states nothing about its own base while still
    reporting success. Without a default the omission is a loud failure at
    the call site instead of a silently baseless seed.
    """

    payload = derive_seed_payload(
        task_id=task_id,
        body=body,
        tree_root=Path(worktree),
        gate_root=repo_root,
        max_top_level_entries=max_top_level_entries,
        base_commit=base_commit,
    )
    gate = load_scope_gate(repo_root)
    resolved_state = (
        Path(state_path) if state_path is not None else gate.default_state_path()
    )
    store = gate.GateStore(resolved_state)
    try:
        return store.record_contract_seed(
            worktree=str(worktree),
            branch=branch,
            **payload,
        )
    except gate.ContractSeedBaseConflict as exc:
        # Separated from the declaration refusal below because the card is not
        # what is wrong and editing it changes nothing: the standing row was
        # written for a workspace that started at another commit, or before
        # the base was recorded at all. Only retiring that row clears it.
        raise ScopeSeedError("scope-seed-base-mismatch", str(exc)) from exc
    except ValueError as exc:
        raise ScopeSeedError("scope-seed-rejected", str(exc)) from exc
    except OSError as exc:
        raise ScopeSeedError("scope-seed-unavailable", str(exc)) from exc
