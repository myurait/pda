"""Deterministic PDA task-scope admission policy.

The module intentionally uses only the Python standard library so the same
validator can run in-process as a Hermes plugin and out-of-process as a
fail-closed shell hook.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import sqlite3
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

_STATE_MENTION_RE = re.compile(
    r"(?:"
    r"(?:commit|コミット)\s*[,、/]\s*(?:push|プッシュ)していない|"
    r"(?:commit|push)していない|(?:コミット|プッシュ)(?:して|されて)いない|"
    r"未(?:commit|push|コミット|プッシュ)|uncommitted|unpushed"
    r")",
    re.IGNORECASE,
)

HOST_TASK_BINDING_ENV = "HERMES_KANBAN_TASK"


def host_task_binding() -> str:
    """The task identifier the host set on this worker process, if any.

    The dispatcher that spawns a worker exports the board card id in the
    worker's process environment. That is the only identifier that names the
    unit of work a contract seed is keyed by: the identifiers carried in the
    hook payload name the conversation, and were measured to be the session
    id in both the task and the session field, which a seed cannot be joined
    on.
    """

    return os.environ.get(HOST_TASK_BINDING_ENV, "").strip()


def resolve_task_binding(
    payload_task_id: str = "",
    *,
    has_contract: Callable[[str], bool] | None = None,
) -> str:
    """The task identifier to bind a hook call by.

    The host-supplied value wins because it is the assigner's own key for the
    work, not the executor's view of it; the payload value remains the
    fallback for every surface the dispatcher does not start (interactive
    sessions above all). ``session_id`` is never overridden: it identifies
    the conversation, and the contract lookup still needs it as its own
    fallback when neither task identifier is present.

    Precedence may not retire a contract. ``has_contract`` answers "does
    binding by this identifier reach a contract record", and when the two
    identifiers disagree, an anchor that reaches none does not displace a
    payload identifier that does: a lookup that finds nothing is not the
    safe side of this choice, it is the unenforced side, which is strictly
    wider than the contract the payload identifier was already carrying.
    Losing the host's supply and being handed a wrong value are different
    conditions, and only the former was fail-closed by absence alone.

    The correction can only add enforcement, never remove it, so anchor
    precedence stands wherever the anchor reaches a contract of its own --
    including one reached through the session fallback -- and wherever
    neither identifier reaches one.
    """

    anchor = host_task_binding()
    payload = str(payload_task_id or "").strip()
    if not anchor:
        return payload
    if has_contract is None or not payload or payload == anchor:
        return anchor
    if has_contract(anchor) or not has_contract(payload):
        return anchor
    return payload


@dataclass(frozen=True)
class TaskIntent:
    task_class: str
    allow_commit: bool = False
    allow_push: bool = False
    explicit_global: bool = False


# A full Git object name: 40 hex characters for SHA-1, 64 for SHA-256.
_BASE_COMMIT_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

_CLOSEOUT_RE = re.compile(
    r"(?:(?<!未)(?<![A-Za-z0-9_])commit(?![A-Za-z0-9_])|(?<!未)(?<![A-Za-z0-9_])push(?![A-Za-z0-9_])|(?<!未)コミット|(?<!未)プッシュ|保存して|保存せよ|close[ -]?out)",
    re.IGNORECASE,
)
_CHANGE_RE = re.compile(
    r"(?:実装|修正|変更|解消|作成|追加|削除|導入|反映|直して|調査|設計|分析|"
    r"(?<![A-Za-z0-9_])fix(?:ed|es|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])implement(?:ation|ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])resolve(?:d|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])edit(?:ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])refactor(?:ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])test(?:s|ed|ing)?(?![A-Za-z0-9_])|テスト)",
    re.IGNORECASE,
)
_GLOBAL_RE = re.compile(
    r"(?:全(?:て|部)?(?:の)?(?:branch(?:es)?|ブランチ|worktree|作業ツリー|repository|repo|リポジトリ)|"
    r"all\s+(?:branches|worktrees|repositories|repos)|"
    r"every\s+(?:branch|worktree|repository|repo))",
    re.IGNORECASE,
)
# --- S2/S3 rollout, stage G0: deterministic classification only. ---
# The classes below are recorded on the turn contract for audit and gold-set
# calibration; admission keeps treating every non-closeout class as
# not-enforced until their admission functions are activated in a later
# rollout stage.
_BROAD_MISSION_RE = re.compile(
    r"(?:全面|全体|大規模|包括|徹底|作り直|再設計|"
    r"(?<![A-Za-z0-9_])redesign(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])migrat(?:e|ion|ing)(?![A-Za-z0-9_])|移行|"
    r"(?<![A-Za-z0-9_])audit(?![A-Za-z0-9_])|監査)",
    re.IGNORECASE,
)
_BOUNDED_OP_RE = re.compile(
    r"(?:再起動|リスタート|再読込|有効化|無効化|切り?替え|"
    r"(?<![A-Za-z0-9_])restart(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])reload(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])enable(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])disable(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])cutover(?![A-Za-z0-9_]))",
    re.IGNORECASE,
)
_BOUNDED_TARGET_RE = re.compile(
    r"(?:[\w.-]+\.(?:service|timer)|gateway|dashboard|daemon|デーモン|"
    r"サービス|systemd|(?<![A-Za-z0-9_])timer(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])cron(?![A-Za-z0-9_])|valve|pipe|plugin|プラグイン|"
    r"container|コンテナ|docker)",
    re.IGNORECASE,
)
_ARTIFACT_CHANGE_RE = re.compile(
    r"(?:実装|修正|変更|解消|作成|追加|削除|導入|反映|直して|"
    r"(?<![A-Za-z0-9_])fix(?:ed|es|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])implement(?:ation|ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])resolve(?:d|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])edit(?:ed|s|ing)?(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])refactor(?:ed|s|ing)?(?![A-Za-z0-9_]))",
    re.IGNORECASE,
)


def _classify_non_closeout(text: str) -> TaskIntent:
    """Deterministic class for requests that are not repository closeouts.

    Conservative by design: any broad-mission marker keeps the wider
    ``audit-only`` class so a large piece of work is never misfiled into a
    narrow, budget-capped class (design gold-set requirement). Investigation,
    analysis, and design requests also stay ``audit-only``.
    """
    if _BROAD_MISSION_RE.search(text):
        return TaskIntent(task_class="audit-only")
    if (
        _BOUNDED_OP_RE.search(text)
        and _BOUNDED_TARGET_RE.search(text)
        and not _ARTIFACT_CHANGE_RE.search(text)
    ):
        return TaskIntent(task_class="bounded-operation")
    if _ARTIFACT_CHANGE_RE.search(text):
        return TaskIntent(task_class="artifact-change")
    return TaskIntent(task_class="audit-only")


_REPOSITORY_CONTEXT_RE = re.compile(
    r"(?:\bgit\b|repo(?:sitory)?|worktree|branch|origin|remote|changes?|results?|"
    r"リポジトリ|作業ツリー|ブランチ|差分|成果|資源|"
    r"未(?:commit|push|コミット|プッシュ)|uncommitted|unpushed)",
    re.IGNORECASE,
)
_EXPLICIT_ACTION_RE = re.compile(
    r"(?:"
    r"(?:commit|push|コミット|プッシュ).{0,30}(?:してくれ|してください|せよ|しろ|すること|して)|"
    r"(?:please|can\s+you)\s+(?:commit|push)|"
    r"(?:commit|push)\s+(?:this|these|the|current|my)\b|"
    r"^\s*(?:commit|push)(?:\s*(?:and|,|/|&)\s*(?:commit|push))*\s*[.!。]?\s*$"
    r")",
    re.IGNORECASE,
)


def classify_task(user_message: str) -> TaskIntent:
    """Classify the request into a deterministic task class.

    Any explicit content-changing verb wins over commit/push wording, so a
    change request never becomes a closeout. Non-closeout requests are
    classified by :func:`_classify_non_closeout` for audit and gold-set
    calibration; only ``repository-closeout`` is enforced in the current
    rollout stage (every other class stays not-enforced at admission).
    """

    text = user_message or ""
    action_text = _STATE_MENTION_RE.sub("", text)
    if _CHANGE_RE.search(text) or not _CLOSEOUT_RE.search(action_text):
        return _classify_non_closeout(text)

    commit_requested = bool(
        re.search(
            r"(?:(?<!未)(?<![A-Za-z0-9_])commit(?![A-Za-z0-9_])|(?<!未)コミット)",
            action_text,
            re.IGNORECASE,
        )
    )
    push_requested = bool(
        re.search(
            r"(?:(?<!未)(?<![A-Za-z0-9_])push(?![A-Za-z0-9_])|(?<!未)プッシュ)",
            action_text,
            re.IGNORECASE,
        )
    )
    save_requested = bool(
        re.search(r"保存して|保存せよ|close[ -]?out", action_text, re.IGNORECASE)
    )
    repository_context = bool(_REPOSITORY_CONTEXT_RE.search(text))
    explicit_action = bool(_EXPLICIT_ACTION_RE.search(action_text))
    if ("?" in text or "？" in text) and not explicit_action:
        return _classify_non_closeout(text)

    commit_requested = commit_requested and (explicit_action or repository_context)
    push_requested = push_requested and (
        explicit_action or repository_context or commit_requested
    )
    save_requested = save_requested and (
        repository_context
        or bool(re.search(r"close[ -]?out", action_text, re.IGNORECASE))
    )
    if not (commit_requested or push_requested or save_requested):
        return _classify_non_closeout(text)
    return TaskIntent(
        task_class="repository-closeout",
        allow_commit=commit_requested or save_requested,
        allow_push=push_requested,
        explicit_global=bool(_GLOBAL_RE.search(text)),
    )


# G3 expansion review (design doc §6): per-class number of expansion
# reviews a single turn may consume. Classes not listed here have no
# expansion budget. Hard bounds always stay with the deterministic
# validator; an LLM judge is only a pluggable second opinion.
EXPANSION_REVIEW_BUDGET = {
    "repository-closeout": 0,
    "bounded-operation": 1,
    "artifact-change": 2,
}
EXPANSION_PERMIT_TTL_SECONDS = 300.0


# ---------------------------------------------------------------------------
# S3-M1 artifact-change: path foundation.
#
# Every path decision for the artifact-change class goes through the single
# deterministic normalizer below. Rejection is expressed as "this path does
# not belong to the locked worktree root", never as "the argument looked
# absolute": the existing read and terminal tools require absolute notation,
# so a notation-based rule would contradict the surrounding convention.
# ---------------------------------------------------------------------------

MAX_SCOPE_PATTERNS = 32
MAX_SCOPE_PATTERN_LENGTH = 256
_SCOPE_PATTERN_CHARS_RE = re.compile(r"^[A-Za-z0-9._*?/\[\]-]+$")


class PathRejected(ValueError):
    """A path argument or scope pattern failed deterministic normalization."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ContractSeedBaseConflict(ValueError):
    """A re-recorded seed states an assignment base the stored row does not.

    Kept distinct from the generic seed disagreement because the two have
    different causes and different resolutions. A differing ceiling means the
    card's declaration changed and the card is what has to be corrected; a
    differing -- or missing -- base means the recorded row was written for a
    workspace that started somewhere else, which no edit to the card can
    reconcile. Only the owner can retire the standing row.
    """


class WorktreeProbeError(ValueError):
    """The repository probe could not be run (transient, not a verdict).

    Kept distinct from a verification mismatch so a timeout or an I/O error
    does not pin a turn in an unrecoverable state on the strength of a
    condition that was never actually evaluated.
    """


def _has_control_characters(text: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in text)


def normalize_scope_pattern(raw: Any) -> str:
    """Validate one repository-relative scope glob pattern."""

    value = str(raw or "").strip()
    if not value:
        raise PathRejected("pattern-empty", "scope patterns must not be empty")
    if _has_control_characters(value):
        raise PathRejected(
            "pattern-control", "scope patterns must not contain control characters"
        )
    if len(value) > MAX_SCOPE_PATTERN_LENGTH:
        raise PathRejected("pattern-length", "scope pattern is too long")
    if not _SCOPE_PATTERN_CHARS_RE.fullmatch(value):
        raise PathRejected(
            "pattern-syntax", "scope pattern uses characters outside the allowed set"
        )
    if value.startswith("/"):
        raise PathRejected("pattern-absolute", "scope patterns are repository relative")
    if any(segment in {"", ".", ".."} for segment in value.split("/")):
        raise PathRejected(
            "pattern-traversal",
            "scope patterns must not contain empty, '.' or '..' segments",
        )
    return value


def normalize_scope_patterns(raw: Any, *, field: str) -> tuple[str, ...]:
    """Validate a closed set of scope patterns (order-normalized, deduplicated)."""

    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        raise PathRejected("pattern-shape", f"{field} must be an array of patterns")
    patterns = [normalize_scope_pattern(item) for item in raw]
    if len(patterns) > MAX_SCOPE_PATTERNS:
        raise PathRejected(
            "pattern-count", f"{field} exceeds the {MAX_SCOPE_PATTERNS} pattern limit"
        )
    return tuple(sorted(set(patterns)))


def _segment_matches(pattern_segment: str, name: str) -> bool:
    # A single segment never contains "/", so in-segment wildcards cannot
    # cross a path boundary.
    return fnmatch.fnmatchcase(name, pattern_segment)


def _match_segments(
    pattern_parts: tuple[str, ...], path_parts: tuple[str, ...]
) -> bool:
    if not pattern_parts:
        return not path_parts
    head = pattern_parts[0]
    if head == "**":
        remainder = pattern_parts[1:]
        if not remainder:
            return True
        return any(
            _match_segments(remainder, path_parts[index:])
            for index in range(len(path_parts) + 1)
        )
    if not path_parts:
        return False
    if not _segment_matches(head, path_parts[0]):
        return False
    return _match_segments(pattern_parts[1:], path_parts[1:])


def scope_pattern_matches(pattern: str, relative_path: str) -> bool:
    """Segment-aware glob: ``*`` stays inside one segment, ``**`` recurses.

    The standard-library pattern matchers translate ``*`` to a wildcard that
    crosses ``/``, which would make an approved pattern permit far more than
    its reviewed text suggests. Example: ``docs/design/*.md`` matches
    ``docs/design/a.md`` but not ``docs/design/sub/a.md``; the recursive form
    is written ``docs/design/**/*.md``.
    """

    return _match_segments(
        tuple(pattern.split("/")), tuple(relative_path.split("/"))
    )


def scope_patterns_match(patterns: tuple[str, ...], relative_path: str) -> bool:
    return any(scope_pattern_matches(pattern, relative_path) for pattern in patterns)


def _entity_resolved(candidate: Path) -> Path:
    """Entity-resolve as much of ``candidate`` as exists on disk.

    The nearest existing ancestor (or the target itself when it already
    exists, including as a symlink) is resolved with ``realpath``; the
    non-existent remainder is appended to the resolved prefix. Every scope
    decision is taken on this path, never on a lexically folded one: a
    lexical fold silently rewrites the destination whenever a path element
    is a link, so the checked path and the written path would differ.
    """

    tail: list[str] = []
    probe = candidate
    while not (probe.exists() or probe.is_symlink()):
        parent = probe.parent
        if parent == probe:
            break
        tail.append(probe.name)
        probe = parent
    resolved = Path(os.path.realpath(str(probe)))
    for name in reversed(tail):
        resolved = resolved / name
    return resolved


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def normalize_repo_relative_path(
    raw: Any,
    *,
    root: str,
    workdir: str | None = None,
) -> tuple[str, Path]:
    """Resolve one path argument against the locked root.

    Returns ``(relative_posix_path, resolved_absolute_path)``. Absolute and
    relative notations are both accepted, and two spellings of the same
    directory resolve to the same result: membership of the locked root is a
    property of the location, not of the notation. Upward references are
    rejected on the raw argument, before any folding, and the returned
    relative path is derived from the entity-resolved location so the glob
    match is taken on the real destination.
    """

    value = str(raw or "")
    if not value.strip():
        raise PathRejected("target-missing", "the target path is empty")
    if _has_control_characters(value):
        raise PathRejected(
            "target-control", "the target path contains control characters"
        )
    candidate = Path(value)
    if ".." in candidate.parts:
        raise PathRejected(
            "target-traversal", "the target path carries an upward reference"
        )
    if not candidate.is_absolute():
        base = Path(str(workdir)) if workdir else Path(root)
        if not base.is_absolute():
            raise PathRejected(
                "target-base", "a relative path needs an absolute resolution base"
            )
        candidate = base / candidate
    real_root = Path(os.path.realpath(str(root)))
    resolved = _entity_resolved(candidate)
    if not _is_inside(resolved, real_root):
        lexical = Path(os.path.normpath(str(candidate)))
        lexical_root = Path(os.path.normpath(str(root)))
        if _is_inside(lexical, lexical_root):
            # The notation named a location inside the locked root, but the
            # real destination is elsewhere.
            raise PathRejected(
                "target-escape",
                "the target's resolved location is outside the locked worktree",
            )
        raise PathRejected(
            "target-closed", "the target path is outside the locked worktree"
        )
    relative = resolved.relative_to(real_root)
    if not relative.parts:
        raise PathRejected(
            "target-root", "the locked worktree root itself is not a write target"
        )
    return relative.as_posix(), resolved


def paths_name_the_same_location(first: str, second: str) -> bool:
    """Whether two absolute spellings name one entity-resolved location."""

    return os.path.realpath(str(first)) == os.path.realpath(str(second))


def _static_pattern_prefix(pattern: str) -> tuple[str, ...]:
    prefix: list[str] = []
    for segment in pattern.split("/"):
        if any(character in segment for character in "*?["):
            break
        prefix.append(segment)
    return tuple(prefix)


def verify_scope_prefixes_are_inside_root(
    patterns: tuple[str, ...], *, root: str
) -> None:
    """Reject scope patterns whose existing ancestors leave the locked root."""

    real_root = Path(os.path.realpath(str(root)))
    for pattern in patterns:
        current = Path(str(root))
        for segment in _static_pattern_prefix(pattern):
            current = current / segment
            if not (current.exists() or current.is_symlink()):
                break
            resolved = Path(os.path.realpath(str(current)))
            if resolved != real_root and real_root not in resolved.parents:
                raise PathRejected(
                    "scope-escape",
                    f"scope pattern {pattern!r} resolves outside the locked worktree",
                )


# ---------------------------------------------------------------------------
# S3-M1 artifact-change: explicit tool catalogue.
#
# Write destinations are identified from a name-to-fields table, not from the
# shape of the arguments. A tool that is not listed here is treated as a
# mutation and falls through to G3 (default deny for mutation); a listed tool
# that carries none of its declared destination fields is denied rather than
# silently admitted.
# ---------------------------------------------------------------------------

# Read/search tools the design admits with an audit record only. The names
# are the ones the running Hermes tool vocabulary actually uses (see the
# vocabulary agreement test): a speculative name here is not a widening, but
# it does read as coverage that is not there, and a missing real name is a
# false deny in the class the design requires zero false denies from.
#
# A name listed here is admitted in every stage, the unbound path included:
# the rationale is that the call reads and writes nothing the first layer
# would have to bound, and that rationale does not depend on a turn.
ARTIFACT_READ_TOOLS = frozenset(
    {
        "read_file",
        "search_files",
        "session_search",
        # Isolated live-run finding (2026-08-24): each reads the agent's own
        # configuration or metadata plane (a skill definition, a tool schema)
        # and acts on neither the repository nor the execution boundary.
        # skill_manage stays out of every catalogue: it can write skill
        # definitions, which are repository files.
        "skill_view",
        "tool_describe",
    }
)

# Tools that only read or annotate the agent's own work-management plane
# (the task board and the step list). D-S3-7 admits them in the first layer
# with an audit record only, in every stage: nothing about annotating the
# board depends on the scope being fixed, and recording a blocked state is
# what INV-S6 asks a stalled turn to do instead of starting repair work.
#
# This is a closed, explicit catalogue of tool names. Membership is never
# inferred from a capability guess or from the shape of the arguments: an
# inferring rule is the defect shape this class already had to remove once,
# and it would re-open by construction as the vocabulary grows. A tool that
# is not named here stays under default deny for mutation.
#
# Deliberately excluded, with reasons:
#   - delegate_task: spawns another agent (class budget `subagents` is 0,
#     and §10 acceptance item 5 denies it).
#   - web_search / web_extract: acquires new outside material, which is an
#     expansion rather than a record of the work in hand.
#   - skill_manage: can write skill definitions, i.e. repository files.
#   - memory / cronjob: writes durable state outside this turn's contract.
#   - kanban_create: creating a card is exactly how a blocker becomes a new
#     task, which INV-S6 forbids doing silently.
#   - kanban_request_changes: the reviewer's verdict, not the worker's
#     (INV-S7 keeps the two authorities apart).
#   - kanban_link / kanban_attach / kanban_attach_url: each carries a
#     destination (a path, a URL, another card) that the first layer does
#     not bound, and the operating procedure does not use them.
ARTIFACT_WORK_RECORD_TOOLS = frozenset(
    {
        "todo",
        "kanban_show",
        "kanban_attachments",
        "kanban_comment",
        "kanban_heartbeat",
        "kanban_block",
    }
)

# Tools that move the run to a terminal state on the durable control plane:
# the orchestrator reads these transitions to decide what to dispatch next.
# They are admitted only in a locked turn. A turn whose contract could not be
# verified has established nothing to report as finished or reviewable, and
# the INV-S6 escape valve it does need (recording a blocked state) is in the
# annotation catalogue above.
ARTIFACT_RUN_SIGNAL_TOOLS = frozenset(
    {
        "kanban_complete",
        "kanban_request_review",
    }
)

# The audit action a run signal admitted past the tool budget is recorded
# under. It is its own reason code, never the ordinary `signal-run-outcome`:
# the exception is the one call in a turn that the budget did not bound, and
# an audit that cannot separate the two cannot see that it stayed a single
# call.
ARTIFACT_RUN_SIGNAL_PAST_BUDGET_ACTION = "complete-past-budget"

# Argument fields that can name the task a run signal is about. Each listed
# field that is present has to carry the bound task id.
ARTIFACT_RUN_SIGNAL_TARGET_FIELDS = ("task_id", "task", "card_id", "card", "id")

# The rest of the argument set the exception admits: report fields that carry
# the worker's own account of the finished run and name no destination.
#
# Together with the target fields above this is a closed, explicit catalogue
# of argument keys, and that closure -- not the target match on its own -- is
# what binds the destination. A key outside the two sets means the exception
# does not apply, so the tool budget denies the call exactly as it did before
# the exception existed. Recognizing some spellings and ignoring the rest
# would leave the destination in the unread keys: the bound id in a listed
# field and the effective target in an unlisted one is one call, and that is
# the open-enumeration shape D-S3-7 補則 ratified as impossible to close.
#
# Deliberately excluded, with reasons -- each carries a destination the first
# layer does not bound, so it belongs in no report:
#   - board: selects which board the task id is resolved on, so the bound id
#     alone stops fixing which card the transition lands on.
#   - created_cards: creates cards as part of the completion, which is how a
#     blocker becomes a new task -- the same reason kanban_create is outside
#     the work-record catalogue (INV-S6).
#   - artifacts: carries paths or URLs, the same destination kanban_attach
#     and kanban_attach_url are kept out of that catalogue for.
#
# Widening this set is a deliberate edit against the board tools' own
# argument schemas, never a guess. The audit trail names the key a denied
# signal carried, so a spelling the live board actually sends is added from
# that record: being too narrow costs the turn the graceful handoff and
# leaves it on the pre-exception behaviour (the orchestrator's retry recovers
# the card), while being too wide hands the exception a destination the first
# layer never read.
ARTIFACT_RUN_SIGNAL_REPORT_FIELDS = ("summary", "result", "metadata", "reviewer")

# How many nested values a report may hold before the exception stops trying
# to establish what it names. A report describes one finished run; a payload
# past this size is not one, and the exception is withheld rather than
# granted on an unfinished walk.
_ARTIFACT_RUN_SIGNAL_REPORT_NODE_LIMIT = 512


def _run_signal_report_names_another_task(value: Any, bound: str) -> bool:
    """Whether a report field names a task other than the bound one.

    The approval metadata a review request carries states the task it is
    about, so the closed key set at the top level is not the whole check: a
    report naming a foreign task is stored on the board as a claim about that
    task. Nested keys are not required to form a closed set -- the approval
    schema is open by design, and the destination the board acts on is a
    top-level argument -- but a target field found at any depth has to name
    the bound task, exactly as at the top level.
    """

    pending: list[Any] = [value]
    visited = 0
    while pending:
        if visited >= _ARTIFACT_RUN_SIGNAL_REPORT_NODE_LIMIT:
            return True
        current = pending.pop()
        visited += 1
        if isinstance(current, dict):
            for key, item in current.items():
                if key in ARTIFACT_RUN_SIGNAL_TARGET_FIELDS:
                    if not isinstance(item, str) or item.strip() != bound:
                        return True
                    continue
                pending.append(item)
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return False


def artifact_run_signal_targets_bound_task(
    turn: sqlite3.Row, tool_name: str, args: dict[str, Any]
) -> bool:
    """Whether this call is a run signal about the turn's own bound task.

    The budget-stranding exception (design §8, 実測課題1) turns on this and
    on nothing else about the arguments. A call that names no target, carries
    any target other than the bound task at any depth, or carries any
    argument key outside the closed catalogue above is not covered: the
    exception exists so a finished turn can report *its own* completion, and
    a foreign card id -- under any spelling, including one this gate does not
    read -- would make it a way to move another task's state after the budget
    stopped bounding the turn.
    """

    if tool_name not in ARTIFACT_RUN_SIGNAL_TOOLS:
        return False
    bound = str(turn["task_id"] or "").strip()
    if not bound:
        return False
    named = False
    for field, value in args.items():
        if field in ARTIFACT_RUN_SIGNAL_TARGET_FIELDS:
            if not isinstance(value, str) or value.strip() != bound:
                return False
            named = True
            continue
        if field not in ARTIFACT_RUN_SIGNAL_REPORT_FIELDS:
            return False
        if _run_signal_report_names_another_task(value, bound):
            return False
    return named


_PATH_PAIR_FIELDS = (
    "path",
    "file_path",
    "source",
    "source_path",
    "src",
    "destination",
    "destination_path",
    "dst",
    "from",
    "to",
)


@dataclass(frozen=True)
class WriteTargetFields:
    """Every argument field of one tool that can name a write destination."""

    single: tuple[str, ...] = ()
    listed: tuple[str, ...] = ()
    nested: tuple[tuple[str, str], ...] = ()


ARTIFACT_WRITE_TOOL_CATALOG: dict[str, WriteTargetFields] = {
    "write_file": WriteTargetFields(single=("path", "file_path")),
    "create_file": WriteTargetFields(single=("path", "file_path")),
    "append_file": WriteTargetFields(single=("path", "file_path")),
    "patch": WriteTargetFields(single=("path", "file_path")),
    "edit_file": WriteTargetFields(single=("path", "file_path")),
    "notebook_edit": WriteTargetFields(single=("path", "notebook_path")),
    "multi_edit": WriteTargetFields(
        single=("path", "file_path"),
        nested=(("edits", "path"), ("edits", "file_path")),
    ),
    "write_files": WriteTargetFields(listed=("paths", "files")),
    "delete_file": WriteTargetFields(single=("path", "file_path")),
    "move_file": WriteTargetFields(single=_PATH_PAIR_FIELDS),
    "rename_file": WriteTargetFields(single=_PATH_PAIR_FIELDS),
    "copy_file": WriteTargetFields(single=_PATH_PAIR_FIELDS),
}


def _path_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PathRejected("target-shape", f"{field} must be a non-empty path string")
    return value


def _paths_from_listed_item(item: Any, field: str) -> list[str]:
    if isinstance(item, str):
        return [_path_string(item, field)]
    if isinstance(item, dict):
        found = [
            _path_string(item[name], name)
            for name in ("path", "file_path")
            if name in item
        ]
        if not found:
            raise PathRejected(
                "target-missing", f"an entry of {field} carried no write destination"
            )
        return found
    raise PathRejected("target-shape", f"{field} entries must be paths or objects")


def collect_write_targets(tool_name: str, args: dict[str, Any]) -> tuple[str, ...]:
    """All write destinations a catalogued tool call can reach."""

    spec = ARTIFACT_WRITE_TOOL_CATALOG.get(tool_name)
    if spec is None:
        raise PathRejected(
            "tool-unlisted",
            f"{tool_name} is not in the artifact-change write catalogue",
        )
    found: list[str] = []
    for field in spec.single:
        if field in args:
            found.append(_path_string(args[field], field))
    for field in spec.listed:
        value = args.get(field)
        if value is None:
            continue
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise PathRejected("target-shape", f"{field} must be an array")
        for item in value:
            found.extend(_paths_from_listed_item(item, field))
    nested_fields: dict[str, list[str]] = {}
    for container, item_field in spec.nested:
        nested_fields.setdefault(container, []).append(item_field)
    for container, item_fields in nested_fields.items():
        if container not in args or args[container] is None:
            continue
        value = args[container]
        # Same closure as the listed branch: a declared container that is
        # present in an unexpected shape is refused, never skipped. Skipping
        # it would leave the destinations it carries uninspected whenever
        # another declared field happened to be in scope.
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise PathRejected("target-shape", f"{container} must be an array")
        for item in value:
            if not isinstance(item, dict):
                raise PathRejected(
                    "target-shape", f"{container} entries must be objects"
                )
            carried = [name for name in item_fields if name in item]
            if not carried:
                raise PathRejected(
                    "target-missing",
                    f"an entry of {container} carried no write destination",
                )
            found.extend(_path_string(item[name], name) for name in carried)
    if not found:
        raise PathRejected(
            "target-missing",
            f"{tool_name} carried none of its declared write destination fields",
        )
    return tuple(found)


# ---------------------------------------------------------------------------
# S3-M1 artifact-change: second-layer verification template registry.
#
# The contract carries template ids only. The mapping from id to inspection
# rule stays here, in a closed registry, so a contract can never carry a
# free-form command string. Argument inspection scans every token, admits
# only an explicit allowlist, and denies anything unknown immediately.
#
# Threat model: the process side effects of an admitted command are outside
# the first layer's write-boundary guarantee. The gate inspects arguments
# only. Namespace-isolated execution and static inspection of collection
# paths are fixed M2 requirements.
# ---------------------------------------------------------------------------

_TEMPLATE_VALUE_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


@dataclass(frozen=True)
class ExecutionTemplate:
    template_id: str
    action: str
    heads: tuple[tuple[str, ...], ...]
    boolean_flags: frozenset[str]
    valued_flags: frozenset[str]


EXECUTION_TEMPLATES: dict[str, ExecutionTemplate] = {
    "focused-test": ExecutionTemplate(
        template_id="focused-test",
        action="run-focused-test",
        heads=(
            ("pytest",),
            ("python", "-m", "pytest"),
            ("python3", "-m", "pytest"),
        ),
        boolean_flags=frozenset(
            {"-x", "-q", "-v", "--quiet", "--exitfirst", "--no-header", "--strict-markers"}
        ),
        valued_flags=frozenset({"--maxfail", "--tb", "--color"}),
    ),
    "syntax-check": ExecutionTemplate(
        template_id="syntax-check",
        action="check-target-syntax",
        heads=(
            ("python", "-m", "py_compile"),
            ("python3", "-m", "py_compile"),
        ),
        boolean_flags=frozenset({"-q", "--quiet"}),
        valued_flags=frozenset(),
    ),
}


def normalize_execution_templates(raw: Any) -> tuple[str, ...]:
    """Validate the second-layer opt-in set against the closed registry."""

    if raw is None:
        return ()
    if isinstance(raw, dict):
        raw = raw.get("templates")
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        raise PathRejected("execution-shape", "execution templates must be an array")
    identifiers = []
    for item in raw:
        value = str(item or "").strip()
        if value not in EXECUTION_TEMPLATES:
            raise PathRejected(
                "execution-unknown", f"{value!r} is not a registered verification template"
            )
        identifiers.append(value)
    if len(identifiers) > 8:
        raise PathRejected("execution-count", "too many verification templates")
    return tuple(sorted(set(identifiers)))


def _template_head_tail(
    template: ExecutionTemplate, tokens: list[str]
) -> list[str] | None:
    for head in sorted(template.heads, key=len, reverse=True):
        if tuple(tokens[: len(head)]) == head:
            return tokens[len(head) :]
    return None


def action_fingerprint(tool_name: str, args: dict[str, Any]) -> str:
    """Canonical sha256 fingerprint of a tool action (name + arguments)."""
    return hashlib.sha256(
        json.dumps([tool_name, args], sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    action: str
    reason: str
    resource: str = ""


class GateStore:
    """SQLite-backed, process-safe scope state and budget reservation."""

    def __init__(
        self,
        path: str | Path,
        *,
        enforce_artifact_change_pre_lock: bool | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.enforce_artifact_change_pre_lock = (
            ARTIFACT_CHANGE_PRELOCK_ENFORCED
            if enforce_artifact_change_pre_lock is None
            else bool(enforce_artifact_change_pre_lock)
        )
        self._initialize()

    # The admission transaction can hold the write lock across the Git
    # worktree probe, so the contention wait has to exceed that probe's own
    # timeouts. A shorter wait turned a concurrent call into a database
    # error instead of a decision.
    _LOCK_WAIT_SECONDS = 12.0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self._LOCK_WAIT_SECONDS)
        connection.row_factory = sqlite3.Row
        connection.execute(
            f"PRAGMA busy_timeout = {int(self._LOCK_WAIT_SECONDS * 1000)}"
        )
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    origin_sha256 TEXT NOT NULL,
                    task_class TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    allow_commit INTEGER NOT NULL,
                    allow_push INTEGER NOT NULL,
                    explicit_global INTEGER NOT NULL,
                    contract_json TEXT,
                    tool_count INTEGER NOT NULL DEFAULT 0,
                    denied_count INTEGER NOT NULL DEFAULT 0,
                    completion_status TEXT
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    turn_id TEXT NOT NULL,
                    call_key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    execution_status TEXT NOT NULL DEFAULT 'pending',
                    evidence_value TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (turn_id, call_key)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    turn_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (turn_id, path)
                );
                CREATE TABLE IF NOT EXISTS contract_seeds (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL DEFAULT '',
                    task_class TEXT NOT NULL,
                    worktree TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    write_paths_json TEXT NOT NULL,
                    test_paths_json TEXT NOT NULL,
                    execution_json TEXT NOT NULL,
                    git_write_json TEXT NOT NULL DEFAULT '[]',
                    base_commit TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    consumed_at REAL,
                    consumed_turn_id TEXT
                );
                CREATE TABLE IF NOT EXISTS self_scope_locks (
                    scope_key TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL DEFAULT '',
                    task_id TEXT NOT NULL DEFAULT '',
                    worktree TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    write_paths_json TEXT NOT NULL,
                    test_paths_json TEXT NOT NULL,
                    execution_json TEXT NOT NULL,
                    git_write_json TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS contract_scope_uses (
                    scope_key TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    used_at REAL NOT NULL,
                    PRIMARY KEY (scope_key, turn_id)
                );
                CREATE TABLE IF NOT EXISTS expansion_permits (
                    turn_id TEXT NOT NULL,
                    action_fingerprint TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    outcome_reason TEXT NOT NULL DEFAULT '',
                    estimated_cost_json TEXT NOT NULL DEFAULT '',
                    verdict TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL,
                    PRIMARY KEY (turn_id, action_fingerprint)
                );
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(turns)").fetchall()
            }
            if "task_id" not in columns:
                connection.execute(
                    "ALTER TABLE turns ADD COLUMN task_id TEXT NOT NULL DEFAULT ''"
                )
            if "contract_origin" not in columns:
                connection.execute(
                    "ALTER TABLE turns ADD COLUMN contract_origin TEXT NOT NULL DEFAULT ''"
                )
            if "classified_class" not in columns:
                # The classifier's own output stays recorded for audit and
                # gold-set calibration; it is not an admission input once a
                # contract record exists for the task.
                connection.execute(
                    "ALTER TABLE turns ADD COLUMN classified_class TEXT NOT NULL DEFAULT ''"
                )
            seed_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(contract_seeds)"
                ).fetchall()
            }
            if seed_columns and "git_write_json" not in seed_columns:
                connection.execute(
                    "ALTER TABLE contract_seeds "
                    "ADD COLUMN git_write_json TEXT NOT NULL DEFAULT '[]'"
                )
            if seed_columns and "base_commit" not in seed_columns:
                # Seeds recorded before the assignment-time base was captured
                # keep an empty value. Backfilling a guess here would turn an
                # unknown base into a stated one, so the absence is preserved
                # and left for the consumer to refuse.
                connection.execute(
                    "ALTER TABLE contract_seeds "
                    "ADD COLUMN base_commit TEXT NOT NULL DEFAULT ''"
                )
            decision_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(decisions)").fetchall()
            }
            if "execution_status" not in decision_columns:
                connection.execute(
                    "ALTER TABLE decisions ADD COLUMN execution_status TEXT NOT NULL DEFAULT 'pending'"
                )
            if "evidence_value" not in decision_columns:
                connection.execute(
                    "ALTER TABLE decisions ADD COLUMN evidence_value TEXT NOT NULL DEFAULT ''"
                )

    def purge_expired(
        self,
        *,
        now: float | None = None,
        retention_days: int = 30,
    ) -> int:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        cutoff = (time.time() if now is None else float(now)) - retention_days * 86400
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT turn_id FROM turns
                WHERE started_at < ?
                """,
                (cutoff,),
            ).fetchall()
            turn_ids = [str(row["turn_id"]) for row in rows]
            if turn_ids:
                placeholders = ",".join("?" for _ in turn_ids)
                for table in ("decisions", "candidates", "expansion_permits"):
                    connection.execute(
                        f"DELETE FROM {table} WHERE turn_id IN ({placeholders})",
                        turn_ids,
                    )
                connection.execute(
                    f"DELETE FROM turns WHERE turn_id IN ({placeholders})",
                    turn_ids,
                )
            # Contract records outlive the turns that used them on purpose,
            # but not the retention window: an expired record must not keep
            # locking new turns of a task nobody is working on any more.
            for table in ("contract_seeds", "self_scope_locks"):
                connection.execute(
                    f"DELETE FROM {table} WHERE created_at < ?", (cutoff,)
                )
            connection.execute(
                "DELETE FROM contract_scope_uses WHERE used_at < ?", (cutoff,)
            )
            connection.commit()
        return len(turn_ids)

    def record_contract_seed(
        self,
        *,
        task_id: str,
        worktree: str,
        branch: str,
        write_paths: Any,
        test_paths: Any = (),
        execution: Any = (),
        git_write: Any = None,
        base_commit: Any = None,
        session_id: str = "",
        task_class: str = "artifact-change",
    ) -> dict[str, Any]:
        """Record an assignment-time contract seed (orchestrator-side only).

        This API is deliberately not reachable through the worker-facing
        ``scope_gate`` control tool: the executing agent must not be able to
        create or widen its own seed. The seed is a standing ceiling for
        every turn of the task, not a one-shot token: it keeps applying to
        later turns of the same task, and a self lock can only stay inside
        it. ``git_write`` narrows which Git writes the contract carries;
        omitted means the class default.
        """

        if task_class != "artifact-change":
            raise ValueError("only artifact-change contracts are seeded in this stage")
        clean_task_id = str(task_id or "").strip()
        if not clean_task_id:
            raise ValueError("a contract seed requires a task id")
        roots = self._canonical_targets([worktree])
        if len(roots) != 1:
            raise ValueError("a contract seed names exactly one worktree")
        clean_branch = str(branch or "").strip()
        if (
            not clean_branch
            or clean_branch.startswith("-")
            or any(character.isspace() for character in clean_branch)
        ):
            raise ValueError("branch names must be concrete, non-option tokens")
        write = normalize_scope_patterns(write_paths, field="write_paths")
        if not write:
            raise ValueError("artifact-change seeds require a non-empty write scope")
        test = normalize_scope_patterns(test_paths, field="test_paths")
        templates = normalize_execution_templates(execution)
        git_writes = normalize_git_write_actions(git_write)
        base = normalize_base_commit(base_commit)
        payload = {
            "task_id": clean_task_id,
            "session_id": str(session_id or ""),
            "task_class": task_class,
            "worktree": roots[0],
            "branch": clean_branch,
            "write_paths": list(write),
            "test_paths": list(test),
            "execution": list(templates),
            "git_write": list(git_writes),
            "base_commit": base,
        }
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM contract_seeds WHERE task_id = ?", (clean_task_id,)
            ).fetchone()
            if existing is not None:
                current = {
                    "task_id": str(existing["task_id"]),
                    "session_id": str(existing["session_id"]),
                    "task_class": str(existing["task_class"]),
                    "worktree": str(existing["worktree"]),
                    "branch": str(existing["branch"]),
                    "write_paths": json.loads(existing["write_paths_json"]),
                    "test_paths": json.loads(existing["test_paths_json"]),
                    "execution": json.loads(existing["execution_json"]),
                    "git_write": json.loads(existing["git_write_json"] or "[]"),
                    "base_commit": str(
                        existing["base_commit"]
                        if "base_commit" in set(existing.keys())
                        else ""
                    ),
                }
                connection.commit()
                self._reject_disagreeing_seed(current, payload)
                # The stored record is returned unchanged: a second call never
                # replaces the standing ceiling, and never overwrites a base
                # commit either.
                return current
            connection.execute(
                """
                INSERT INTO contract_seeds (
                    task_id, session_id, task_class, worktree, branch,
                    write_paths_json, test_paths_json, execution_json,
                    git_write_json, base_commit, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_task_id,
                    payload["session_id"],
                    task_class,
                    payload["worktree"],
                    clean_branch,
                    json.dumps(list(write)),
                    json.dumps(list(test)),
                    json.dumps(list(templates)),
                    json.dumps(list(git_writes)),
                    base,
                    time.time(),
                ),
            )
            connection.commit()
        return payload

    @staticmethod
    def _reject_disagreeing_seed(
        current: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        """Refuse a re-recorded seed that does not state the stored one.

        Everything but the base commit has to match exactly: a differing
        ceiling means the card's declaration changed while the task was in
        flight, and accepting it would install a new ceiling silently.

        The base commit is compared asymmetrically, because the two sides do
        not make the same claim. A caller that offers no base states nothing
        about where the work started and cannot contradict the stored row, so
        that direction is tolerated and the stored value survives. A caller
        that offers one is the assigning side reporting the commit it just
        resolved, and the recorded row has to carry that same value -- an
        absent stored base is not agreement, it is a row that records nothing
        about its own base, which is precisely the guarantee this field
        exists to give. Neither direction rewrites the stored record: the
        disagreement is raised so the assignment fails instead of proceeding
        under a ceiling whose audit range is unknown.
        """

        keys = set(current) | set(payload)
        for key in keys - {"base_commit"}:
            if current.get(key) != payload.get(key):
                raise ValueError(
                    "a different contract seed already exists for this task"
                )
        stored = str(current.get("base_commit") or "")
        offered = str(payload.get("base_commit") or "")
        if not offered or stored == offered:
            return
        raise ContractSeedBaseConflict(
            "the recorded contract seed for this task states a different "
            f"assignment base commit ({stored or 'none recorded'}) than the "
            f"one offered ({offered}); the standing seed has to be retired "
            "before this task can be assigned again"
        )

    @staticmethod
    def _render_scope_record(row: sqlite3.Row, *, origin: str) -> dict[str, Any]:
        keys = set(row.keys())
        return {
            "origin": origin,
            "task_id": str(row["task_id"]),
            "session_id": str(row["session_id"]),
            "task_class": "artifact-change",
            "worktree": str(row["worktree"]),
            "branch": str(row["branch"]),
            "write_paths": json.loads(row["write_paths_json"]),
            "test_paths": json.loads(row["test_paths_json"]),
            "execution": json.loads(row["execution_json"]),
            "git_write": json.loads(row["git_write_json"] or "[]"),
            "base_commit": str(row["base_commit"] if "base_commit" in keys else ""),
            "consumed_at": row["consumed_at"] if "consumed_at" in keys else None,
            "consumed_turn_id": (
                row["consumed_turn_id"] if "consumed_turn_id" in keys else None
            ),
        }

    def get_contract_seed(
        self, task_id: str, *, session_id: str = ""
    ) -> dict[str, Any] | None:
        """The assignment seed for a task, or for a session that carries one.

        The session lookup exists because the fail-closed norm has to hold
        for a call that arrives without a task id: a seeded assignment must
        not become unenforced because one identifier was not wired through.
        """

        clean_task = str(task_id or "").strip()
        clean_session = str(session_id or "").strip()
        if not clean_task and not clean_session:
            return None
        with self._connect() as connection:
            row = None
            if clean_task:
                row = connection.execute(
                    "SELECT * FROM contract_seeds WHERE task_id = ?", (clean_task,)
                ).fetchone()
            if row is None and clean_session:
                row = connection.execute(
                    """
                    SELECT * FROM contract_seeds
                    WHERE session_id = ? AND session_id != ''
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (clean_session,),
                ).fetchone()
        if row is None:
            return None
        return self._render_scope_record(row, origin="assignment")

    @staticmethod
    def scope_key(*, task_id: str = "", session_id: str = "") -> str:
        """Stable key for a task-scoped contract record."""

        clean_task = str(task_id or "").strip()
        if clean_task:
            return clean_task
        clean_session = str(session_id or "").strip()
        return f"session:{clean_session}" if clean_session else ""

    def get_self_scope_lock(
        self, *, task_id: str = "", session_id: str = ""
    ) -> dict[str, Any] | None:
        """The standing self lock for a task or interactive session.

        A self lock is recorded at task scope, not turn scope: the audit
        hooks can fire per LLM call rather than per user turn, and a lock
        that expired with its turn would leave the following call of the
        same task unenforced.
        """

        keys = [
            key
            for key in (
                self.scope_key(task_id=task_id),
                self.scope_key(session_id=session_id),
            )
            if key
        ]
        if not keys:
            return None
        with self._connect() as connection:
            for key in keys:
                row = connection.execute(
                    "SELECT * FROM self_scope_locks WHERE scope_key = ?", (key,)
                ).fetchone()
                if row is not None:
                    return self._render_scope_record(row, origin="self")
        return None

    def has_contract_record(self, *, task_id: str, session_id: str = "") -> bool:
        """Whether binding by these identifiers reaches a contract record.

        The two record kinds that can put a turn in force: an assignment
        seed and a standing self lock. Both lookups already consult the
        session as their own fallback, so this answers the question the
        binding resolution actually asks -- "would a turn bound this way be
        enforced" -- rather than "is this exact key seeded".

        Turn history is deliberately not part of the predicate. It is not a
        record: a turn opened under a task that has history but no record is
        unenforced whichever identifier bound it, so counting history here
        would move bindings without putting any contract back in force.
        """

        return (
            self.get_contract_seed(task_id, session_id=session_id) is not None
            or self.get_self_scope_lock(task_id=task_id, session_id=session_id)
            is not None
        )

    def _record_scope_use(
        self,
        connection: sqlite3.Connection,
        *,
        scope_key: str,
        turn_id: str,
        origin: str,
    ) -> None:
        if not scope_key:
            return
        connection.execute(
            """
            INSERT OR IGNORE INTO contract_scope_uses (
                scope_key, turn_id, origin, used_at
            ) VALUES (?, ?, ?, ?)
            """,
            (scope_key, turn_id, origin, time.time()),
        )

    def contract_scope_uses(self, scope_key: str) -> list[dict[str, Any]]:
        """Every turn that has been locked by one contract record."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT turn_id, origin, used_at FROM contract_scope_uses
                WHERE scope_key = ? ORDER BY used_at ASC
                """,
                (scope_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def start_turn(
        self,
        *,
        turn_id: str,
        session_id: str,
        task_id: str = "",
        user_message: str,
    ) -> TaskIntent:
        """Register one turn and put it in the state its contract implies.

        A contract record for the task is authoritative over the classifier.
        The classifier answers "what does this message look like"; only the
        record answers "what is this executor allowed to do", and a later
        message of the same task must not be able to move that answer. The
        classifier's own verdict is still stored for audit and gold-set work.
        """

        self.purge_expired()
        intent = classify_task(user_message)
        classified = intent.task_class
        digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()
        record = self.get_contract_seed(task_id, session_id=session_id)
        if record is None:
            record = self.get_self_scope_lock(task_id=task_id, session_id=session_id)
        if record is not None:
            # Every permission the turn gets now comes from the record.
            intent = TaskIntent(task_class="artifact-change")
        state = "discovering" if intent.task_class == "repository-closeout" else "audit"
        origin = ""
        contract_json: str | None = None
        if record is not None:
            origin = str(record["origin"])
            try:
                contract = self._build_artifact_change_contract(
                    turn_id=turn_id,
                    origin_sha256=digest,
                    origin=origin,
                    root=record["worktree"],
                    branch=record["branch"],
                    write_paths=record["write_paths"],
                    test_paths=record["test_paths"],
                    templates=record["execution"],
                    git_write=record["git_write"],
                    base_commit=record.get("base_commit", ""),
                )
            except WorktreeProbeError:
                # The verification could not be run (transient I/O, timeout).
                # Registering the turn here would pin an unrecoverable
                # mutation-denied state on a condition that may not hold on
                # the next call, so the turn is left unregistered: the call
                # is still fail-closed through the unbound path, and the
                # next hook retries the verification.
                return intent
            except (ValueError, PathRejected):
                # The verification ran and disagreed with the record. That
                # stays fail-closed: the turn exists with mutation denied,
                # it never falls back to not-enforced.
                state = "mutation-denied"
            else:
                state = "locked"
                contract_json = json.dumps(
                    contract, ensure_ascii=False, sort_keys=True
                )
        elif (
            intent.task_class == "artifact-change"
            and self.enforce_artifact_change_pre_lock
        ):
            state = "pre-lock"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO turns (
                    turn_id, session_id, task_id, origin_sha256, task_class, state,
                    started_at, allow_commit, allow_push, explicit_global,
                    contract_json, contract_origin, classified_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_id) DO NOTHING
                """,
                (
                    turn_id,
                    session_id,
                    task_id,
                    digest,
                    intent.task_class,
                    state,
                    time.time(),
                    int(intent.allow_commit),
                    int(intent.allow_push),
                    int(intent.explicit_global),
                    contract_json,
                    origin,
                    classified,
                ),
            )
            if cursor.rowcount == 1 and record is not None:
                scope_key = self.scope_key(
                    task_id=str(record["task_id"]),
                    session_id=str(record["session_id"]),
                )
                connection.execute(
                    """
                    UPDATE contract_seeds
                       SET consumed_at = COALESCE(consumed_at, ?),
                           consumed_turn_id = COALESCE(consumed_turn_id, ?)
                     WHERE task_id = ?
                    """,
                    (time.time(), turn_id, str(record["task_id"]).strip()),
                )
                self._record_scope_use(
                    connection,
                    scope_key=scope_key,
                    turn_id=turn_id,
                    origin=origin,
                )
            connection.commit()
        return intent

    def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    _FALLBACK_TURN_ORDER = """
        ORDER BY
            (completion_status IS NULL
             AND task_class = 'artifact-change'
             AND state IN ('pre-lock', 'locked', 'mutation-denied')) DESC,
            started_at DESC
        LIMIT 1
    """

    def resolve_turn_id(
        self,
        *,
        turn_id: str = "",
        task_id: str = "",
        session_id: str = "",
    ) -> str:
        """Bind a call to a turn.

        Preference order for the task/session fallback: an open enforced
        turn first, so a newer unenforced turn of the same task cannot cast
        a shadow over a contract that is still in force; otherwise the most
        recent turn, closed or not, because a closed turn has to stay
        reachable for its own refusal to apply. Reaching back to an older
        open turn is never correct: the call belongs to the current turn.
        """

        with self._connect() as connection:
            if turn_id:
                row = connection.execute(
                    "SELECT turn_id FROM turns WHERE turn_id = ?", (turn_id,)
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
            for column, value in (("task_id", task_id), ("session_id", session_id)):
                if not value:
                    continue
                row = connection.execute(
                    "SELECT turn_id FROM turns WHERE "
                    f"{column} = ? AND {column} != ''" + self._FALLBACK_TURN_ORDER,
                    (value,),
                ).fetchone()
                if row is not None:
                    return str(row["turn_id"])
        return ""

    def lock_turn(
        self,
        *,
        turn_id: str,
        repositories: list[str],
        worktrees: list[str],
        branches: list[str],
        write_paths: Any = None,
        test_paths: Any = None,
        execution: Any = None,
    ) -> dict[str, Any]:
        """Atomically lock the turn's contract, dispatched by task class.

        The atomic lock path is shared, the per-class contract construction
        and validation are not: closeout keeps its bounded-discovery
        candidate requirement, artifact-change gets repository entity
        verification plus write-scope validation.
        """

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError("unknown scope turn")
            task_class = str(turn["task_class"])
            if task_class == "repository-closeout":
                contract = self._lock_closeout(
                    connection,
                    turn,
                    repositories=repositories,
                    worktrees=worktrees,
                    branches=branches,
                    write_paths=write_paths,
                    test_paths=test_paths,
                    execution=execution,
                )
            elif task_class == "artifact-change":
                contract = self._lock_artifact_change(
                    connection,
                    turn,
                    repositories=repositories,
                    worktrees=worktrees,
                    branches=branches,
                    write_paths=write_paths,
                    test_paths=test_paths,
                    execution=execution,
                )
            else:
                raise ValueError(f"{task_class} turns cannot lock a scope contract")
            connection.commit()
            return contract

    def _lock_closeout(
        self,
        connection: sqlite3.Connection,
        turn: sqlite3.Row,
        *,
        repositories: list[str],
        worktrees: list[str],
        branches: list[str],
        write_paths: Any,
        test_paths: Any,
        execution: Any,
    ) -> dict[str, Any]:
        if write_paths or test_paths or execution:
            raise ValueError("repository-closeout contracts carry no write scope")
        turn_id = str(turn["turn_id"])
        canonical_repositories = self._canonical_targets(repositories)
        canonical_worktrees = self._canonical_targets(worktrees)
        clean_branches = sorted({str(branch).strip() for branch in branches if str(branch).strip()})
        if not canonical_repositories or not canonical_worktrees or not clean_branches:
            raise ValueError("repository-closeout requires non-empty repositories, worktrees, and branches")
        if any(branch.startswith("-") or any(ch.isspace() for ch in branch) for branch in clean_branches):
            raise ValueError("branch names must be concrete, non-option tokens")

        if turn["state"] == "locked" and turn["contract_json"]:
            return json.loads(turn["contract_json"])
        if turn["state"] != "discovering":
            raise ValueError(f"turn cannot lock from state {turn['state']!r}")
        candidate_rows = connection.execute(
            "SELECT path FROM candidates WHERE turn_id = ?", (turn_id,)
        ).fetchall()
        candidates = {row["path"] for row in candidate_rows}
        requested = set(canonical_repositories) | set(canonical_worktrees)
        if not requested.issubset(candidates):
            raise ValueError("targets must come from this turn's bounded discovery")
        if not turn["explicit_global"] and len(canonical_worktrees) != 1:
            raise ValueError("non-global closeout can lock exactly one worktree")
        worktree_branches = _validated_worktree_branches(canonical_worktrees)
        actual_branches = sorted(set(worktree_branches.values()))
        if set(clean_branches) != set(actual_branches):
            raise ValueError(
                "locked branches must exactly match current worktree branches: "
                + ", ".join(actual_branches)
            )

        target_count = len(canonical_worktrees)
        max_calls = min(32, 8 + 3 * target_count)
        required = []
        if turn["allow_commit"]:
            required.append("commit-existing-content")
        if turn["allow_push"]:
            required.append("push-requested-commit")
        contract: dict[str, Any] = {
            "schema": "pda.scope-contract/v1",
            "turn_id": turn_id,
            "origin_message_sha256": turn["origin_sha256"],
            "task_class": "repository-closeout",
            "objective": "save only existing commit-ready repository content as requested",
            "targets": {
                "repositories": canonical_repositories,
                "worktrees": canonical_worktrees,
                "branches": clean_branches,
                "worktree_branches": worktree_branches,
            },
            "actions": {
                "required": required,
                "prerequisite": [
                    "inventory-status",
                    "inspect-candidate-diff",
                    "targeted-integrity-check",
                ],
                "verification": ["remote-ref-equals-local-head"] if turn["allow_push"] else ["commit-created"],
                "forbidden": [
                    "edit-content",
                    "resolve-conflict",
                    "run-broad-tests",
                    "create-or-delete-worktree",
                    "wait-unrelated-process",
                    "deploy-or-restart",
                    "delegate-or-background",
                ],
            },
            "completion": {
                "all": [
                    "every commit-ready target has the requested commit",
                    *(
                        ["every pushed commit is reachable from its intended remote ref"]
                        if turn["allow_push"]
                        else []
                    ),
                ],
                "blocked_targets_may_be_reported": True,
            },
            "budget": {
                "max_wall_seconds": 900,
                "max_tool_calls": max_calls,
                "max_denied_calls": 3,
                "max_expansions": 0,
                "background_processes": 0,
                "subagents": 0,
            },
            "state": "locked",
        }
        _validate_contract_against_schema(contract)
        encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True)
        connection.execute(
            "UPDATE turns SET state = 'locked', contract_json = ? WHERE turn_id = ?",
            (encoded, turn_id),
        )
        return contract

    def _lock_artifact_change(
        self,
        connection: sqlite3.Connection,
        turn: sqlite3.Row,
        *,
        repositories: list[str],
        worktrees: list[str],
        branches: list[str],
        write_paths: Any,
        test_paths: Any,
        execution: Any,
    ) -> dict[str, Any]:
        """Self lock for a turn with no assignment seed (narrowing only)."""

        del repositories  # derived from the verified worktree, not declared
        turn_id = str(turn["turn_id"])
        canonical_worktrees = self._canonical_targets(worktrees)
        if len(canonical_worktrees) != 1:
            raise ValueError("artifact-change can lock exactly one worktree")
        root = canonical_worktrees[0]
        write = normalize_scope_patterns(write_paths, field="write_paths")
        test = normalize_scope_patterns(test_paths, field="test_paths")
        templates = normalize_execution_templates(execution)
        state = str(turn["state"])

        if state == "locked" and turn["contract_json"]:
            # A seeded turn is already locked. Re-locking returns the same
            # contract idempotently; a declaration that exceeds it is denied.
            contract = json.loads(turn["contract_json"])
            _, existing_write, existing_test, existing_templates = (
                artifact_contract_scope(contract)
            )
            exceeds = (
                not set(write).issubset(set(existing_write))
                or not set(test).issubset(set(existing_test))
                or not set(templates).issubset(set(existing_templates))
                or canonical_worktrees != list(contract["targets"]["worktrees"])
            )
            if exceeds:
                raise ValueError(
                    "the declared scope exceeds the assigned contract seed"
                )
            return contract
        if state == "mutation-denied":
            raise ValueError(
                "the assigned contract seed failed verification; this turn cannot lock"
            )
        if state not in {"audit", "pre-lock"}:
            raise ValueError(f"turn cannot lock from state {state!r}")
        if not write:
            raise ValueError("artifact-change lock requires a non-empty write scope")
        # The seed is consulted here as well, not only at turn start. Relying
        # on "the turn would already be locked if a seed existed" puts the
        # ceiling's guarantee in the host's identifier wiring and in the order
        # the records happened to be written.
        seed = self.get_contract_seed(
            str(turn["task_id"]), session_id=str(turn["session_id"])
        )
        if seed is not None:
            raise ValueError(
                "this task has an assigned contract seed; the turn must be locked "
                "from the seed rather than by declaration"
            )
        requested_branches = sorted(
            {str(branch).strip() for branch in (branches or []) if str(branch).strip()}
        )
        if len(requested_branches) > 1:
            raise ValueError("artifact-change can lock exactly one branch")
        contract = self._build_artifact_change_contract(
            turn_id=turn_id,
            origin_sha256=str(turn["origin_sha256"]),
            origin="self",
            root=root,
            branch=requested_branches[0] if requested_branches else "",
            write_paths=write,
            test_paths=test,
            templates=templates,
        )
        encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True)
        connection.execute(
            """
            UPDATE turns
               SET state = 'locked', contract_json = ?, contract_origin = 'self'
             WHERE turn_id = ?
            """,
            (encoded, turn_id),
        )
        # The self lock is kept at task scope so the next turn of the same
        # work starts locked instead of unenforced.
        scope_key = self.scope_key(
            task_id=str(turn["task_id"]), session_id=str(turn["session_id"])
        )
        if scope_key:
            bindings = contract["targets"]["worktree_branches"]
            connection.execute(
                """
                INSERT INTO self_scope_locks (
                    scope_key, session_id, task_id, worktree, branch,
                    write_paths_json, test_paths_json, execution_json,
                    git_write_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_key) DO NOTHING
                """,
                (
                    scope_key,
                    str(turn["session_id"]),
                    str(turn["task_id"]),
                    contract["targets"]["worktrees"][0],
                    str(next(iter(bindings.values()))),
                    json.dumps(list(write)),
                    json.dumps(list(test)),
                    json.dumps(list(templates)),
                    json.dumps(list(contract["actions"]["git_write"])),
                    time.time(),
                ),
            )
            self._record_scope_use(
                connection, scope_key=scope_key, turn_id=turn_id, origin="self"
            )
        return contract

    @staticmethod
    def _build_artifact_change_contract(
        *,
        turn_id: str,
        origin_sha256: str,
        origin: str,
        root: str,
        branch: str,
        write_paths: Any,
        test_paths: Any,
        templates: Any,
        git_write: Any = None,
        base_commit: Any = None,
        repositories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build and validate one locked artifact-change contract.

        Repository entity verification (worktree root identity, current
        branch, no detached HEAD) uses the same verifier as closeout, and a
        seed branch that does not match the checked-out branch is
        fail-closed.
        """

        write = normalize_scope_patterns(write_paths, field="write_paths")
        test = normalize_scope_patterns(test_paths, field="test_paths")
        opted_in = normalize_execution_templates(templates)
        git_writes = normalize_git_write_actions(git_write)
        base = normalize_base_commit(base_commit)
        if not write:
            raise ValueError("artifact-change contracts require a non-empty write scope")
        worktree_branches = _validated_worktree_branches([str(root)])
        resolved_root = next(iter(worktree_branches))
        actual_branch = worktree_branches[resolved_root]
        if branch and branch != actual_branch:
            raise ValueError(
                "the assigned branch does not match the current worktree branch"
            )
        verify_scope_prefixes_are_inside_root(write + test, root=resolved_root)
        contract: dict[str, Any] = {
            "schema": "pda.scope-contract/v1",
            "turn_id": turn_id,
            "origin_message_sha256": origin_sha256,
            "task_class": "artifact-change",
            "objective": (
                "change only the artifacts inside the locked write scope and "
                "verify them with the opted-in templates"
            ),
            "origin": origin,
            "targets": {
                # Derived from the verified worktree, never taken as free
                # input: the contract is also the audit record, and an
                # unchecked target list there is a false statement about what
                # the turn was allowed to touch.
                "repositories": [resolved_root],
                "worktrees": [resolved_root],
                "branches": [actual_branch],
                "worktree_branches": {resolved_root: actual_branch},
                "write_paths": list(write),
                "test_paths": list(test),
            },
            "execution": {"templates": list(opted_in)},
            "actions": {
                "required": ["change-artifacts-in-scope"],
                "prerequisite": ["inspect-locked-target"],
                "git_write": list(git_writes),
                "verification": (
                    ["focused-verification-of-changed-files"] if opted_in else []
                ),
                "forbidden": [
                    "write-outside-scope",
                    "push-to-remote",
                    "rewrite-history",
                    "bypass-verification-hooks",
                    "run-broad-tests",
                    "create-or-delete-worktree",
                    "deploy-or-restart",
                    "delegate-or-background",
                ],
            },
            "completion": {
                "all": [
                    "every change stays inside the locked write scope",
                    "the requested change is either complete or reported as blocked",
                ],
                "blocked_targets_may_be_reported": True,
            },
            "budget": dict(ARTIFACT_CHANGE_CLASS_BUDGET),
            "state": "locked",
        }
        if base:
            # Only when the assigning side stated one. A self-declared
            # contract has no assignment-time base, and writing an empty
            # string would put a value that is not a commit into the audit
            # record.
            contract["base_commit"] = base
        _validate_contract_against_schema(contract)
        return contract

    @staticmethod
    def _canonical_targets(targets: list[str]) -> list[str]:
        result: set[str] = set()
        for raw in targets:
            value = str(raw).strip()
            path = Path(value)
            if not value or not path.is_absolute():
                raise ValueError("targets must be absolute paths")
            result.add(str(path.resolve()))
        return sorted(result)

    def record_worktree_candidates(self, *, turn_id: str, paths: list[str]) -> int:
        canonical = self._canonical_targets(paths)
        if len(canonical) > 64:
            raise ValueError("worktree inventory exceeds the bounded 64-target limit")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None or turn["task_class"] != "repository-closeout":
                raise ValueError("unknown repository-closeout turn")
            if turn["state"] != "discovering" or not turn["explicit_global"]:
                raise ValueError("worktree candidates require explicit global discovery")
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO candidates (turn_id, path, source) VALUES (?, ?, ?)",
                [(turn_id, path, "inventory-worktrees-result") for path in canonical],
            )
            added = connection.total_changes - before
            connection.commit()
        return added

    def record_tool_result(
        self,
        *,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        status: str,
        result: Any,
    ) -> None:
        fingerprint = hashlib.sha256(
            json.dumps([tool_name, args], sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        call_key = tool_call_id or fingerprint
        execution_status = (
            "succeeded"
            if _tool_result_succeeded(status, result, tool_name=tool_name)
            else "failed"
        )
        evidence_value = _normalized_git_evidence(
            tool_name=tool_name,
            args=args,
            result=result,
            succeeded=execution_status == "succeeded",
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE decisions SET execution_status = ?, evidence_value = ?
                WHERE turn_id = ? AND call_key = ? AND fingerprint = ?
                """,
                (execution_status, evidence_value, turn_id, call_key, fingerprint),
            )
            connection.commit()

    def request_expansion(
        self,
        *,
        turn_id: str,
        tool_name: str,
        args: dict[str, Any],
        reason: str,
        estimated_cost: dict[str, Any] | None = None,
        judge: Any = None,
        ttl_seconds: float = EXPANSION_PERMIT_TTL_SECONDS,
    ) -> dict[str, Any]:
        """G3 expansion review (design doc §6).

        Review order: (1) deterministic deny — no class budget, budget
        exhausted, or a forbidden/foreign action; (2) deterministic allow —
        the contract already permits the action, so no permit is needed;
        (3) independent judge when the class permits one and a ``judge``
        callable is supplied; (4) otherwise fail closed. Permits are bound
        to the exact action fingerprint, are one-use, and expire after
        ``ttl_seconds``. Hard bounds stay with this deterministic validator:
        a judge can only approve what stages 1-2 did not already settle.
        """
        if not tool_name:
            raise ValueError(
                "expansion review requires a candidate tool_name; "
                "repository-closeout has zero expansion budget and always denies"
            )
        fingerprint = action_fingerprint(tool_name, args)
        now = time.time()
        cost_json = json.dumps(estimated_cost or {}, sort_keys=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                connection.commit()
                raise ValueError("unknown turn")
            prior = connection.execute(
                "SELECT * FROM expansion_permits "
                "WHERE turn_id = ? AND action_fingerprint = ?",
                (turn_id, fingerprint),
            ).fetchone()
            if prior is not None:
                connection.commit()
                return self._render_permit(prior)

            task_class = turn["task_class"]
            budget = int(EXPANSION_REVIEW_BUDGET.get(task_class, 0))
            reviews_used = connection.execute(
                "SELECT COUNT(*) FROM expansion_permits WHERE turn_id = ?",
                (turn_id,),
            ).fetchone()[0]

            verdict, reviewer, outcome_reason = "deny", "deterministic-deny", ""
            if budget <= 0:
                outcome_reason = (
                    f"{task_class} has zero expansion budget; report the blocker"
                )
            elif reviews_used >= budget:
                outcome_reason = (
                    f"expansion review budget exhausted ({reviews_used}/{budget})"
                )
            else:
                # Stage 2 deterministic allow: looked up through the same
                # per-class dispatch table admission uses, so a class whose
                # contract already permits an action never burns review
                # budget on it.
                locked_admission = locked_admission_for(task_class)
                if locked_admission is not None and turn["state"] == "locked":
                    # Positional call on purpose: the past-budget run-signal
                    # exception defaults to unavailable here. Expansion review
                    # asks what the contract already permits, and it neither
                    # grants that exception nor records its consumption, so
                    # answering "already permitted" from it would spend the
                    # single call without a decision row to show it.
                    admitted = locked_admission(turn, tool_name, args)
                    if admitted.allowed:
                        # No permit row and no budget charge: the review
                        # found nothing to review, so charging for it would
                        # spend the turn's expansion budget on actions the
                        # contract already covers.
                        connection.commit()
                        return {
                            "ok": True,
                            "verdict": "allow",
                            "reviewer": "deterministic-allow",
                            "reason": (
                                "the contract already permits this action; "
                                "no permit needed"
                            ),
                            "action_fingerprint": fingerprint,
                            "expires_at": now,
                            "consumed": True,
                        }
                if not outcome_reason:
                    if judge is None:
                        reviewer = "fail-closed"
                        outcome_reason = (
                            "no independent scope reviewer is available; "
                            "expansion fails closed"
                        )
                    else:
                        try:
                            payload = {
                                "turn_id": turn_id,
                                "task_class": task_class,
                                "origin_sha256": turn["origin_sha256"],
                                "contract": json.loads(turn["contract_json"])
                                if turn["contract_json"]
                                else None,
                                "tool_name": tool_name,
                                "resource": json.dumps(args, sort_keys=True, default=str)[:500],
                                "reason": reason,
                                "estimated_cost": estimated_cost or {},
                                "action_fingerprint": fingerprint,
                            }
                            result = judge(payload)
                            if isinstance(result, dict) and bool(result.get("allow")):
                                verdict = "allow"
                                reviewer = "judge"
                                outcome_reason = str(
                                    result.get("reason") or "approved by scope reviewer"
                                )
                            else:
                                reviewer = "judge"
                                rejected = (
                                    result.get("reason")
                                    if isinstance(result, dict)
                                    else None
                                )
                                outcome_reason = (
                                    str(rejected)
                                    if rejected
                                    else "rejected by scope reviewer"
                                )
                        except Exception:
                            verdict = "deny"
                            reviewer = "fail-closed"
                            outcome_reason = "scope reviewer failed; expansion fails closed"

            expires_at = now + max(0.0, float(ttl_seconds))
            connection.execute(
                """
                INSERT INTO expansion_permits (
                    turn_id, action_fingerprint, tool_name, resource, reason,
                    outcome_reason, estimated_cost_json, verdict, reviewer,
                    created_at, expires_at, consumed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    fingerprint,
                    tool_name,
                    json.dumps(args, sort_keys=True, default=str)[:500],
                    reason,
                    outcome_reason,
                    cost_json,
                    verdict,
                    reviewer,
                    now,
                    expires_at,
                    None,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM expansion_permits "
                "WHERE turn_id = ? AND action_fingerprint = ?",
                (turn_id, fingerprint),
            ).fetchone()
            return self._render_permit(row)

    @staticmethod
    def _render_permit(row) -> dict[str, Any]:
        return {
            "ok": row["verdict"] == "allow",
            "verdict": row["verdict"],
            "reviewer": row["reviewer"],
            "reason": row["outcome_reason"],
            "action_fingerprint": row["action_fingerprint"],
            "expires_at": row["expires_at"],
            "consumed": row["consumed_at"] is not None,
        }

    def _consume_permit_locked(
        self, connection: sqlite3.Connection, turn_id: str, fingerprint: str
    ) -> bool:
        """One-use consumption inside an open BEGIN IMMEDIATE transaction."""
        cur = connection.execute(
            """
            UPDATE expansion_permits
               SET consumed_at = ?
             WHERE turn_id = ? AND action_fingerprint = ?
               AND verdict = 'allow' AND consumed_at IS NULL
               AND expires_at > ?
            """,
            (time.time(), turn_id, fingerprint, time.time()),
        )
        return cur.rowcount == 1

    def _run_signal_exception_spent(
        self, connection: sqlite3.Connection, turn_id: str
    ) -> bool:
        """Whether this turn already used its past-budget run signal.

        The decision rows are the record: an allowed call is written under
        its own action, so the count of that action in this turn is the
        number of times the exception was granted. No separate counter is
        added, which keeps the audit trail and the idempotence check the same
        fact. A hook replay of the same tool-call id is answered from the
        decision cache before admission runs, so it does not reach here.

        The count is the exception's own, not a census of run signals past
        the budget: a run signal an expansion permit admitted is recorded
        under `expansion-permit`, is bounded by the expansion review budget,
        and rests on the independent reviewer rather than on this exception
        (absent a reviewer that lane is fail-closed). An audit asking how
        many run signals a turn sent after its budget therefore sums both
        actions.
        """

        row = connection.execute(
            """
            SELECT 1 FROM decisions
             WHERE turn_id = ? AND verdict = 'allow' AND action = ?
             LIMIT 1
            """,
            (turn_id, ARTIFACT_RUN_SIGNAL_PAST_BUDGET_ACTION),
        ).fetchone()
        return row is not None

    def finalize_turn(self, *, turn_id: str, status: str) -> dict[str, Any]:
        if status not in {"success", "partial", "blocked", "failed", "interrupted"}:
            raise ValueError("invalid completion status")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError("unknown scope turn")
            if turn["completion_status"] is not None:
                connection.commit()
                return dict(turn)
            if status == "success" and turn["task_class"] == "repository-closeout":
                evidence = connection.execute(
                    """
                    SELECT action, evidence_value, rowid AS sequence FROM decisions
                    WHERE turn_id = ? AND verdict = 'allow' AND execution_status = 'succeeded'
                    ORDER BY rowid ASC
                    """,
                    (turn_id,),
                ).fetchall()
                latest_by_action: dict[str, tuple[int, str]] = {}
                for row in evidence:
                    latest_by_action[str(row["action"])] = (
                        int(row["sequence"]),
                        str(row["evidence_value"] or ""),
                    )
                required: list[str] = []
                if turn["allow_commit"]:
                    required.append("commit-existing-content")
                if turn["allow_push"]:
                    required.append("push-requested-commit")
                missing = [action for action in required if action not in latest_by_action]
                if not required:
                    missing.append("requested-closeout-action")
                if not missing and turn["allow_push"]:
                    last_required = max(latest_by_action[action][0] for action in required)
                    local = latest_by_action.get("verify-local-head", (0, ""))
                    remote = latest_by_action.get("verify-remote-ref", (0, ""))
                    if local[0] <= last_required or remote[0] <= last_required:
                        missing.append("post-push-ref-verification")
                    elif not local[1] or local[1] != remote[1]:
                        missing.append("remote-ref-equals-local-head")
                if missing:
                    connection.rollback()
                    raise ValueError(
                        "missing successful completion evidence: " + ", ".join(missing)
                    )
            next_state = (
                "completed"
                if turn["task_class"] == "repository-closeout"
                or (
                    turn["task_class"] == "artifact-change"
                    and str(turn["state"]) in ARTIFACT_ENFORCED_STATES
                )
                else turn["state"]
            )
            connection.execute(
                "UPDATE turns SET state = ?, completion_status = ? WHERE turn_id = ?",
                (next_state, status, turn_id),
            )
            connection.commit()
        result_row = self.get_turn(turn_id)
        if result_row is None:  # pragma: no cover
            raise RuntimeError("scope turn disappeared after finalization")
        return result_row

    def complete_turn(self, *, turn_id: str, status: str) -> dict[str, Any]:
        if status not in {"success", "partial", "blocked", "failed", "interrupted"}:
            raise ValueError("invalid completion status")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError("unknown scope turn")
            if turn["completion_status"] is not None:
                connection.commit()
                return dict(turn)
            if (
                turn["task_class"] == "repository-closeout"
                or (
                    turn["task_class"] == "artifact-change"
                    and str(turn["state"]) in ARTIFACT_ENFORCED_STATES
                )
            ):
                connection.execute(
                    "UPDATE turns SET state = 'completed', completion_status = ? WHERE turn_id = ?",
                    (status, turn_id),
                )
            else:
                connection.execute(
                    "UPDATE turns SET completion_status = ? WHERE turn_id = ?",
                    (status, turn_id),
                )
            connection.commit()
        result = self.get_turn(turn_id)
        if result is None:  # pragma: no cover - protected by the transaction
            raise RuntimeError("scope turn disappeared after completion")
        return result

    def admit_tool(
        self,
        *,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        task_id: str = "",
        session_id: str = "",
    ) -> GateDecision:
        fingerprint = action_fingerprint(tool_name, args)
        call_key = tool_call_id or fingerprint
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM decisions WHERE turn_id = ? AND call_key = ?",
                (turn_id, call_key),
            ).fetchone()
            if prior is not None:
                if prior["fingerprint"] != fingerprint:
                    connection.execute(
                        "UPDATE turns SET denied_count = denied_count + 1 WHERE turn_id = ?",
                        (turn_id,),
                    )
                    connection.commit()
                    return GateDecision(
                        False,
                        "hook-argument-drift",
                        "the same tool-call id reached the gate with different arguments",
                    )
                connection.commit()
                return GateDecision(
                    allowed=prior["verdict"] == "allow",
                    action=prior["action"],
                    reason=prior["reason"],
                    resource=prior["resource"],
                )
            turn = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                connection.commit()
                # A turn id that names no row is an unbindable call, not an
                # unenforced one: it goes through the same fail-closed test.
                return self.admit_without_turn(
                    task_id=task_id, session_id=session_id, tool_name=tool_name
                )
            task_class = str(turn["task_class"])
            decide = _DECISION_DISPATCH.get(task_class)
            if decide is not None and (
                task_class != "artifact-change"
                or str(turn["state"]) in ARTIFACT_ENFORCED_STATES
            ):
                decision = decide(self, connection, turn, tool_name, args, fingerprint)
            else:
                connection.commit()
                return GateDecision(True, "not-enforced", "initial rollout audits this task class")
            connection.execute(
                """
                INSERT INTO decisions (
                    turn_id, call_key, fingerprint, verdict, action, reason,
                    resource, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    call_key,
                    fingerprint,
                    "allow" if decision.allowed else "deny",
                    decision.action,
                    decision.reason,
                    decision.resource,
                    time.time(),
                ),
            )
            if decision.allowed:
                counter: str | None = "tool_count"
            elif task_class == "artifact-change":
                # D-S3-7 limits the deny ceiling to deviations against the
                # write and execution boundaries, and the 補則 limits it
                # further to determinations admission makes for itself. The
                # rule is scoped to this class: closeout counting is unchanged.
                counter = artifact_deny_counter(decision.action)
            else:
                counter = "denied_count"
            if counter is not None:
                connection.execute(
                    f"UPDATE turns SET {counter} = {counter} + 1 WHERE turn_id = ?",
                    (turn_id,),
                )
            if decision.allowed and decision.resource:
                connection.execute(
                    "INSERT OR IGNORE INTO candidates (turn_id, path, source) VALUES (?, ?, ?)",
                    (turn_id, decision.resource, decision.action),
                )
            connection.commit()
            return decision

    def _closeout_decision(
        self,
        connection: sqlite3.Connection,
        turn: sqlite3.Row,
        tool_name: str,
        args: dict[str, Any],
        fingerprint: str,
    ) -> GateDecision:
        turn_id = str(turn["turn_id"])
        if tool_name == "scope_gate":
            control_action = str(args.get("action") or "")
            if turn["denied_count"] >= 3 and control_action != "complete":
                return GateDecision(
                    False,
                    "deny-budget",
                    "only scope completion is allowed after three denials",
                )
            if control_action in {"lock", "review", "complete"}:
                return GateDecision(
                    True,
                    f"scope-{control_action}",
                    "scope control transition",
                )
            return GateDecision(
                False,
                "scope-control-invalid",
                "scope_gate action must be lock, review, or complete",
            )
        if turn["state"] == "discovering":
            return self._admit_closeout_discovery(turn, tool_name, args)
        if turn["state"] == "locked":
            decision = self._admit_closeout_locked(turn, tool_name, args)
            if not decision.allowed and self._consume_permit_locked(
                connection, turn_id, fingerprint
            ):
                return GateDecision(
                    True,
                    "expansion-permit",
                    "one-use expansion permit approved for this exact action",
                    decision.resource,
                )
            return decision
        return GateDecision(
            False,
            "turn-closed",
            "scope contract is closed; report the result without more tools",
        )

    def _artifact_change_decision(
        self,
        connection: sqlite3.Connection,
        turn: sqlite3.Row,
        tool_name: str,
        args: dict[str, Any],
        fingerprint: str,
    ) -> GateDecision:
        """Enforced admission for one artifact-change turn.

        Independent of the closeout decision path: state semantics, control
        allowances, and every argument rule are written for this class.
        """

        turn_id = str(turn["turn_id"])
        state = str(turn["state"])
        budget = _artifact_turn_budget(turn)
        deny_ceiling = int(budget["max_denied_calls"])
        if tool_name == "scope_gate":
            control_action = str(args.get("action") or "")
            if control_action not in {"lock", "review", "complete"}:
                return GateDecision(
                    False,
                    "scope-control-invalid",
                    "scope_gate action must be lock, review, or complete",
                )
            if (
                int(turn["denied_count"]) >= deny_ceiling
                and control_action not in {"complete", "lock"}
            ):
                # Narrowing the scope and reporting must stay reachable so a
                # turn cannot be stranded by its own denied attempts.
                return GateDecision(
                    False,
                    "deny-budget",
                    "only scope lock and completion remain after repeated denials",
                )
            return GateDecision(
                True, f"scope-{control_action}", "scope control transition"
            )
        if state == "locked":
            locked_admission = locked_admission_for("artifact-change")
            decision = locked_admission(
                turn,
                tool_name,
                args,
                # The past-budget run signal is one call per turn. The record
                # of the consumption is the decision row itself, written by
                # the caller of this function under the same transaction, so
                # the exception cannot be granted twice by concurrent calls.
                run_signal_exception_unspent=not self._run_signal_exception_spent(
                    connection, turn_id
                ),
            )
            if not decision.allowed and self._consume_permit_locked(
                connection, turn_id, fingerprint
            ):
                return GateDecision(
                    True,
                    "expansion-permit",
                    "one-use expansion permit approved for this exact action",
                    decision.resource,
                )
            return decision
        if state in {"pre-lock", "mutation-denied"}:
            # The unlocked stages are bounded by the class budget: the
            # decision that replaced unlimited pre-lock access is only a
            # bounded default deny if the same wall/tool/deny ceilings apply
            # here as in the locked stage.
            exceeded = _artifact_budget_verdict(turn, budget)
            if exceeded is not None:
                return exceeded
            if state == "pre-lock":
                return _admit_artifact_change_pre_lock(
                    tool_name,
                    action="lock-pending",
                    reason=(
                        "the scope contract is not locked yet; "
                        "only reading is allowed"
                    ),
                )
            return _admit_artifact_change_pre_lock(
                tool_name,
                action="seed-verification-failed",
                reason=(
                    "the assigned contract could not be verified; "
                    "mutation stays denied for this turn"
                ),
            )
        return GateDecision(
            False,
            "turn-closed",
            "scope contract is closed; report the result without more tools",
        )

    def _has_enforced_history(self, *, task_id: str, session_id: str) -> bool:
        clauses = [
            (column, value)
            for column, value in (("task_id", task_id), ("session_id", session_id))
            if str(value or "").strip()
        ]
        if not clauses:
            return False
        with self._connect() as connection:
            for column, value in clauses:
                row = connection.execute(
                    f"""
                    SELECT 1 FROM turns
                    WHERE {column} = ? AND {column} != ''
                      AND task_class = 'artifact-change'
                      AND state IN ('pre-lock', 'locked', 'mutation-denied', 'completed')
                    LIMIT 1
                    """,
                    (str(value).strip(),),
                ).fetchone()
                if row is not None:
                    return True
        return False

    def admit_without_turn(
        self,
        *,
        task_id: str,
        session_id: str,
        tool_name: str,
    ) -> GateDecision:
        """Fail-closed admission when no turn could be bound to a tool call.

        An unbindable call must not be read as an unenforced turn wherever a
        contract exists for the work. Both identifiers are consulted, and a
        task or session that has already had an enforced turn counts too, so
        losing the binding cannot be a way back to unenforced.

        The work-record catalogues are deliberately not admitted here. The
        reason they are admitted in the unlocked stages is that INV-S6 needs
        a stalled *turn* to be able to record a blocked state; a call that
        cannot be bound to a turn has no turn whose state it would be
        recording, so the same rationale does not reach this path.
        """

        enforced = self.has_contract_record(
            task_id=task_id, session_id=session_id
        ) or self._has_enforced_history(task_id=task_id, session_id=session_id)
        if not enforced:
            return GateDecision(
                True, "not-enforced", "initial rollout audits this task class"
            )
        if tool_name in ARTIFACT_READ_TOOLS:
            return GateDecision(
                True, "inspect-unbound", "read-only inspection without a bound turn"
            )
        return GateDecision(
            False,
            "contract-unbound",
            "this task has a scope contract but the call cannot be bound to a turn",
        )

    @staticmethod
    def _admit_closeout_discovery(
        turn: sqlite3.Row,
        tool_name: str,
        args: dict[str, Any],
    ) -> GateDecision:
        if turn["state"] != "discovering":
            return GateDecision(False, "state-invalid", "turn is not accepting discovery")
        if turn["tool_count"] >= 3:
            return GateDecision(False, "discovery-budget", "read-only discovery budget exhausted")
        if tool_name != "terminal":
            return GateDecision(False, "lock-required", "lock the closeout target before this tool")
        command = str(args.get("command") or "").strip()
        workdir = str(args.get("workdir") or "").strip()
        if not workdir or not Path(workdir).is_absolute():
            return GateDecision(False, "target-missing", "git discovery requires an absolute workdir")
        if re.fullmatch(r"git status(?:\s+(?:--short|--branch|--porcelain(?:=v1)?))*", command):
            resource = str(Path(workdir).resolve())
            return GateDecision(True, "inventory-status", "bounded target discovery", resource)
        if turn["explicit_global"] and command == "git worktree list --porcelain":
            resource = str(Path(workdir).resolve())
            return GateDecision(True, "inventory-worktrees", "explicit all-worktree discovery", resource)
        return GateDecision(False, "lock-required", "only bounded git status discovery is allowed before lock")

    @staticmethod
    def _admit_closeout_locked(
        turn: sqlite3.Row,
        tool_name: str,
        args: dict[str, Any],
    ) -> GateDecision:
        contract = json.loads(turn["contract_json"] or "{}")
        budget = contract.get("budget", {})
        if time.time() - float(turn["started_at"]) > int(budget.get("max_wall_seconds", 0)):
            return GateDecision(False, "wall-budget", "repository closeout exceeded 15 minutes")
        if turn["tool_count"] >= int(budget.get("max_tool_calls", 0)):
            return GateDecision(False, "tool-budget", "repository closeout tool budget exhausted")
        if turn["denied_count"] >= int(budget.get("max_denied_calls", 0)):
            return GateDecision(False, "deny-budget", "too many denied expansion attempts")

        targets = [str(Path(path).resolve()) for path in contract["targets"]["worktrees"]]
        worktree_branches = {
            str(Path(path).resolve()): str(branch)
            for path, branch in contract["targets"]["worktree_branches"].items()
        }
        if tool_name in {"read_file", "search_files"}:
            raw_path = str(args.get("path") or "")
            if not raw_path or not Path(raw_path).is_absolute():
                return GateDecision(False, "target-missing", "read-only inspection needs an absolute target path")
            resolved = str(Path(raw_path).resolve())
            if not any(_is_within(resolved, target) for target in targets):
                return GateDecision(False, "target-closed", "read target is outside the locked worktree")
            return GateDecision(True, "inspect-candidate-diff", "read-only inspection inside locked target", resolved)

        if tool_name != "terminal":
            return GateDecision(False, "expansion-zero", f"{tool_name} is outside repository-closeout scope")
        if bool(args.get("background")) or bool(args.get("pty")):
            return GateDecision(False, "background-forbidden", "background and interactive commands are not allowed")
        command = str(args.get("command") or "").strip()
        workdir = str(args.get("workdir") or "").strip()
        if not workdir or not Path(workdir).is_absolute():
            return GateDecision(False, "target-missing", "terminal closeout commands require an absolute workdir")
        resolved_workdir = str(Path(workdir).resolve())
        if resolved_workdir not in targets:
            return GateDecision(False, "target-closed", "terminal workdir is outside the locked target set")
        expected_branch = worktree_branches.get(resolved_workdir)
        if not expected_branch:
            return GateDecision(False, "target-closed", "locked worktree has no branch binding")
        branches = {expected_branch}
        try:
            tokens = _tokenize_single_shell_command(command)
        except PermissionError:
            return GateDecision(False, "compound-command", "compound or shell-composed commands are not admitted")
        except ValueError:
            return GateDecision(False, "command-parse", "terminal command could not be parsed")
        if len(tokens) < 2 or tokens[0] != "git":
            return GateDecision(False, "non-git-command", "only recognized git closeout commands are admitted")
        subcommand = tokens[1]
        tail = tokens[2:]
        if subcommand in {"add", "commit", "push"}:
            try:
                current_branch = _validated_worktree_branches([resolved_workdir])[
                    resolved_workdir
                ]
            except ValueError as exc:
                return GateDecision(False, "target-drift", str(exc))
            if current_branch != expected_branch:
                return GateDecision(
                    False,
                    "target-drift",
                    "worktree branch changed after scope lock",
                )

        if subcommand == "status":
            return GateDecision(True, "inventory-status", "status of locked target", resolved_workdir)
        if subcommand == "diff":
            if not _diff_args_are_bounded(tail):
                return GateDecision(False, "diff-unsafe", "diff arguments can inspect outside the locked candidate")
            return GateDecision(True, "inspect-candidate-diff", "read-only diff of locked target", resolved_workdir)
        if subcommand in {"rev-parse", "ls-remote", "branch", "remote"}:
            verification_action = _verification_action(subcommand, tail, branches)
            if verification_action is None:
                return GateDecision(False, "verify-target", "verification arguments are outside the locked ref")
            return GateDecision(True, verification_action, "read-only closeout verification", resolved_workdir)
        if subcommand == "add":
            if not turn["allow_commit"]:
                return GateDecision(False, "commit-not-requested", "the user requested no commit")
            if not _add_args_are_bounded(tail):
                return GateDecision(False, "stage-unsafe", "stage arguments are outside bounded target paths")
            return GateDecision(True, "stage-existing-content", "stage existing locked-target content", resolved_workdir)
        if subcommand == "commit":
            if not turn["allow_commit"]:
                return GateDecision(False, "commit-not-requested", "the user requested no commit")
            forbidden = {
                "--amend",
                "--fixup",
                "--squash",
                "--no-verify",
                "-n",
                "-C",
                "-c",
                "--reuse-message",
                "--reedit-message",
                "--interactive",
                "-i",
            }
            if any(
                token in forbidden
                or token.startswith(("--fixup=", "--squash="))
                or _short_option_bundle_contains(token, {"n", "C", "c", "i"})
                for token in tail
            ):
                return GateDecision(False, "commit-rewrite", "history rewrite or hook bypass is outside closeout")
            if not _commit_args_are_bounded(tail):
                return GateDecision(False, "commit-unsafe", "commit arguments exceed bounded closeout syntax")
            return GateDecision(True, "commit-existing-content", "create the requested commit", resolved_workdir)
        if subcommand == "push":
            if not turn["allow_push"]:
                return GateDecision(False, "push-not-requested", "the user did not request push")
            forbidden_push = {
                "-f",
                "--force",
                "--force-with-lease",
                "--mirror",
                "--delete",
                "-d",
                "--all",
                "--tags",
                "--prune",
                "--no-verify",
            }
            if any(
                token in forbidden_push
                or token.startswith(("--force-with-lease=", "--delete="))
                or _short_option_bundle_contains(token, {"f", "d"})
                for token in tail
            ):
                return GateDecision(False, "push-destructive", "destructive or hook-bypassing push is outside closeout")
            if not _push_args_match_locked_ref(tail, branches):
                return GateDecision(False, "push-target", "push must name origin and only locked branches")
            return GateDecision(True, "push-requested-commit", "push requested locked-target ref", resolved_workdir)
        return GateDecision(False, "git-subcommand", f"git {subcommand} is outside repository-closeout scope")


# ---------------------------------------------------------------------------
# S3-M1 artifact-change admission (independent of the closeout code path).
#
# Nothing below is shared with the closeout admission functions. Closeout is
# the reference for how strict the argument inspection has to be, not a
# source of shared helpers, and the artifact-change staging range is
# deliberately narrower than closeout's.
# ---------------------------------------------------------------------------

ARTIFACT_CHANGE_CLASS_BUDGET: dict[str, int] = {
    "max_wall_seconds": 3600,
    "max_tool_calls": 96,
    "max_denied_calls": 6,
    "max_expansions": 2,
    "background_processes": 0,
    "subagents": 0,
}

ARTIFACT_ENFORCED_STATES = frozenset(
    {"pre-lock", "locked", "mutation-denied", "completed"}
)

# Set to True only when the assignment path is wired for the lane being
# enforced. The gate-side pre-lock default deny and the seed API ship in M1
# regardless; turning this on makes seedless artifact-change turns start in
# the bounded default-deny stage instead of staying audit-only.
ARTIFACT_CHANGE_PRELOCK_ENFORCED = False

_ARTIFACT_COMMIT_REWRITE_TOKENS = frozenset(
    {
        "--amend",
        "--fixup",
        "--squash",
        "--no-verify",
        "-n",
        "-C",
        "-c",
        "--reuse-message",
        "--reedit-message",
        "--interactive",
        "-i",
        "--all",
        "-a",
        "--patch",
        "-p",
    }
)
_ARTIFACT_COMMIT_SAFE_FLAGS = frozenset({"-q", "--quiet", "-s", "--signoff"})

# Closed set of terminal argument fields an artifact-change turn may carry.
# Anything else is denied: the command allowlist only inspects `command`, so
# an unlisted field would be an uninspected second input.
ARTIFACT_TERMINAL_ARGUMENT_FIELDS = frozenset(
    {"command", "workdir", "timeout", "background", "pty"}
)


ARTIFACT_GIT_WRITE_ACTIONS = ("stage", "commit")
_GIT_WRITE_SUBCOMMANDS = {"stage": "add", "commit": "commit"}

# Read-only Git in the first layer (D-S3-7). The argument inspection is the
# closeout allowlist implementation itself, not a second parser written for
# this class: `status` carries no argument allowlist there either, `diff`
# goes through the bounded-pathspec check, and `rev-parse` / `branch` go
# through the verification allowlist. Reusing those functions is what keeps
# the two classes from drifting apart on the same command surface.
#
# Narrower than closeout's read set, in two places:
#   - `ls-remote` / `remote` are excluded: they read over the network to
#     serve push, and push is not in this class at all.
#   - `log` is excluded: closeout has no bounded-argument implementation for
#     it, and adding one would be the new parser this decision rules out.
#     `rev-parse HEAD` supplies the commit id the worker flow needs.
ARTIFACT_GIT_READ_SUBCOMMANDS = frozenset({"status", "diff", "rev-parse", "branch"})

# Read-only Git subcommands this class recognizes but does not admit. They
# are named explicitly so the audit record can say a read was refused rather
# than that an unknown command was rejected.
#
# Audit attribution only. Since D-S3-7 補則 this set and the argument tables
# below no longer decide which budget a denial spends: every refusal in the
# Git read lane spends the tool budget, because admission cannot determine
# from an argument spelling whether the invocation was really a deviation.
# The classification is kept because the reason code is what an operator
# reads when asking why a required step was refused.
#
# Membership still means the subcommand has no state-changing form of its
# own, and the tables below still record which forms of each member reach a
# boundary. Neither statement is load-bearing for safety any more -- the
# admission verdict for every member is deny either way -- so an error in
# them costs audit precision, not a budget.
ARTIFACT_GIT_READ_UNADMITTED = frozenset(
    {
        "log",
        "show",
        "blame",
        "shortlog",
        "describe",
        "ls-files",
        "ls-remote",
        # A pure read that the approval metadata's base/head ancestry needs.
        "merge-base",
    }
)

# Git subcommands that carry a write form under the same subcommand name.
# None of them may appear in the exempt set, and any of them that is admitted
# for its read form (`branch` is) has to carry a read-form allowlist.
ARTIFACT_GIT_WRITE_CAPABLE_SUBCOMMANDS = frozenset(
    {
        "branch",
        "add",
        "commit",
        "push",
        "reset",
        "checkout",
        "switch",
        "restore",
        "rebase",
        "merge",
        "cherry-pick",
        "revert",
        "clean",
        "gc",
        "prune",
        "stash",
        "config",
        "remote",
        "reflog",
        "notes",
        "update-ref",
        "symbolic-ref",
        "worktree",
        "submodule",
        "apply",
        "am",
        "tag",
        "fetch",
        "pull",
        "filter-branch",
        "replace",
        "mv",
        "rm",
    }
)

# The write and execution forms of subcommands whose refusal this class
# classifies, whether it admits their read form or only recognizes it.
# Matching covers the bare option, the joined value (`<marker>=<value>` and
# `-X<value>`), and a value-taking short option packed onto the end of a
# bundle; a longer unrelated option (`--output-indicator-new`) is not swept in.
#
# Audit attribution only (D-S3-7 補則). A marker missing from this table used
# to move a denial off the ceiling; now it only makes the audit record say
# `git-read-*` where `git-write-form` would have been more precise. Spelling
# coverage here is therefore best-effort by design: closing it is not
# possible by enumeration, and no longer needs to be.
#
# `git diff` is a read of the working tree that can nevertheless be told to
# write its output to a file or to hand the comparison to an external
# program, so those two forms are deviations rather than refused reads. The
# same two options belong to the whole diff family: `log`, `show`, `blame`,
# and `shortlog` each accept the output form and each actually creates the
# named file (verified against the installed Git), so the markers are declared
# for them too even though their read form is not admitted at all.
_ARTIFACT_GIT_DIFF_FAMILY_WRITE_MARKERS = frozenset({"--output", "--ext-diff"})

# The write boundary is not the only boundary a recognized read can name. A
# network read can be told which program to run on the far side, and the
# program is named by an argument rather than by the subcommand, so the
# refusal is an attempt at the execution boundary. `--exec` is a synonym that
# the installed Git accepts and actually hands the named program to the
# transport (verified: it reaches a protocol error from the named program's
# output). The single-dash spelling is rejected by the installed Git's parser
# and is declared only so a parser that accepts it cannot reopen the lane --
# over-declaring a marker moves an already-denied call onto the ceiling, which
# is the conservative direction.
_ARTIFACT_GIT_UPLOAD_PACK_EXEC_MARKERS = frozenset({"--upload-pack", "--exec", "-u"})

# Subcommands that take the diff family's options, and therefore have a write
# form regardless of whether this class admits their read form.
ARTIFACT_GIT_DIFF_FAMILY_SUBCOMMANDS = frozenset(
    {"diff", "log", "show", "blame", "shortlog"}
)

# Total over the recognized set: every subcommand this class classifies has an
# entry, and an empty entry is an explicit statement that the member was
# audited and carries no write or execution form of its own. A member with no
# entry at all is what let an execution-boundary option stay in the exempt
# lane while the closed-set invariant was still green, so the invariant
# requires this table to be total rather than merely a subset.
ARTIFACT_GIT_WRITE_FORM_MARKERS: dict[str, frozenset[str]] = {
    # Admitted read subset.
    "status": frozenset(),
    "diff": _ARTIFACT_GIT_DIFF_FAMILY_WRITE_MARKERS,
    "rev-parse": frozenset(),
    # `branch` carries its write forms under the same subcommand name, so they
    # are excluded by the read-form allowlist below rather than by markers.
    "branch": frozenset(),
    # Recognized but unadmitted.
    "log": _ARTIFACT_GIT_DIFF_FAMILY_WRITE_MARKERS,
    "show": _ARTIFACT_GIT_DIFF_FAMILY_WRITE_MARKERS,
    "blame": _ARTIFACT_GIT_DIFF_FAMILY_WRITE_MARKERS,
    "shortlog": _ARTIFACT_GIT_DIFF_FAMILY_WRITE_MARKERS,
    "describe": frozenset(),
    "ls-files": frozenset(),
    "ls-remote": _ARTIFACT_GIT_UPLOAD_PACK_EXEC_MARKERS,
    "merge-base": frozenset(),
}

# Option spellings whose *value* names a filesystem path that Git opens, per
# subcommand. Only these options make the value inside a token a path
# candidate: the value of an option that takes a search pattern, a format
# string, a display prefix, or a line range is not a path.
#
# Audit attribution only (D-S3-7 補則). Over-declaring a spelling here used to
# strand a turn by charging a pure read to the deny ceiling, and
# under-declaring one used to hide a boundary attempt from it. Neither is
# possible now: the Git read lane spends the tool budget whatever this table
# says. What remains is the audit label.
#
# The table is per subcommand because the same spelling means different things
# in different members: the short option below that names a revision file for
# line attribution is a pickaxe *string* in the history family, where a value
# that looks like a path is an ordinary search for that string in the history.
#
# Every spelling here was checked against the installed Git by confirming the
# invocation reaches the file open (an absolute value produces a read failure
# naming that path) rather than being rejected during option parsing. The
# output option is absent on purpose: it writes rather than reads, so it is a
# write marker above and is classified before this table is consulted.
_ARTIFACT_GIT_DIFF_FAMILY_PATH_OPTIONS = frozenset(
    {"-O", "--relative", "--skip-to", "--rotate-to"}
)

ARTIFACT_GIT_PATH_OPTIONS: dict[str, frozenset[str]] = {
    # Admitted read subset.
    "status": frozenset(),
    "diff": _ARTIFACT_GIT_DIFF_FAMILY_PATH_OPTIONS,
    "rev-parse": frozenset({"--git-path", "--resolve-git-dir"}),
    "branch": frozenset(),
    # Recognized but unadmitted.
    "log": _ARTIFACT_GIT_DIFF_FAMILY_PATH_OPTIONS,
    "show": _ARTIFACT_GIT_DIFF_FAMILY_PATH_OPTIONS,
    # Line attribution reads three files of its own on top of the diff
    # family's options.
    "blame": _ARTIFACT_GIT_DIFF_FAMILY_PATH_OPTIONS
    | {"-S", "--contents", "--ignore-revs-file"},
    "shortlog": _ARTIFACT_GIT_DIFF_FAMILY_PATH_OPTIONS,
    "describe": frozenset(),
    "ls-files": frozenset({"-X", "--exclude-from", "--exclude-per-directory"}),
    # The far-side program is an execution form, declared as a marker above.
    "ls-remote": frozenset(),
    "merge-base": frozenset(),
}

# Read-form argument allowlist for an admitted subcommand that doubles as a
# write command. `git branch` creates, deletes, moves, re-points, and
# re-describes refs, so its read side is given as a closed allowlist and
# anything else is refused. The allowlist is load-bearing for *admission* --
# it is what keeps `git branch -D` from being admitted as a read -- and only
# its resulting audit label is affected by D-S3-7 補則.
ARTIFACT_GIT_READ_FORM_FLAGS: dict[str, frozenset[str]] = {
    "branch": frozenset(
        {
            "-a",
            "--all",
            "-r",
            "--remotes",
            "-l",
            "--list",
            "-v",
            "-vv",
            "--verbose",
            "--show-current",
            "-q",
            "--quiet",
            "--no-color",
            "--color=never",
        }
    ),
}

# The reason code for the exhausted per-turn tool ceiling. Named because
# three places have to agree on it: the verdict that issues it, the budget
# deny set below, and the past-budget run-signal exception, which is granted
# only against this one of the three ceilings.
ARTIFACT_TOOL_BUDGET_ACTION = "tool-budget"

# Denials that exhaust a budget are the ceiling itself, not an attempt at
# anything: they consume no counter, so reaching a ceiling cannot inflate
# the count that produced it.
ARTIFACT_BUDGET_DENY_ACTIONS = frozenset(
    {"wall-budget", ARTIFACT_TOOL_BUDGET_ACTION, "deny-budget"}
)

# Reason codes that charge the deny ceiling (D-S3-7 補則, 2026-08-23).
#
# Membership is decided by one rule and one rule only (the litmus): a code
# belongs here when no invocation whose purpose is reading can land on it.
# "Reading" means the paths this class serves reads through -- the read tools,
# the admitted read-only Git subcommands -- plus any terminal command whose
# lane admission has not yet determined.
#
# The per-lane facts below are how that litmus applies, not a second rule to
# check against it: the tool name being in the write catalogue, the Git
# subcommand being `add`/`commit`, the command matching the head form of an
# opted-in execution template, a contract permission field being absent, a
# resolved path failing the write-scope match. Each is a fact admission
# decides for itself, and each excludes every reading invocation.
#
# For the execution lane specifically: matching a template head is what fixes
# the invocation as an act at the execution boundary, regardless of what the
# caller meant by it, because the contract's own opt-in named that program.
# Failing to match any head does not fix the lane -- a command issued to read
# a file lands there too -- so the mismatch codes are uncounted.
#
# This replaces an exempt-list whose default was to count. The polarity is
# inverted because the old default made every unclassified refusal a
# deviation, which put the burden on a heuristic classification of terminal
# arguments to prove that a pure read was *not* one. Three independent
# reviews confirmed the same failure shape in that classification -- an open
# argument space cannot be closed by enumerating spellings -- so a
# misclassification there must no longer decide which budget a denial spends.
# What makes the uncounted default safe is that an uncounted denial still
# consumes a tool slot, so every lane below is bounded by the class tool
# budget and closes the turn on exhaustion rather than failing open.
#
# Codes deliberately absent, with the reason each fails the rule:
#   `git-read-*`, `git-write-form`   issued by the argument classification,
#                                   which is now audit attribution only
#   `git-subcommand`                 an unrecognized subcommand can be a pure
#                                    read, so the lane is undetermined
#   `expansion-required`             an unrecognized *tool* can be a read
#   `execution-not-opted-in`,        no template head matched, so the lane is
#   `execution-template`              undetermined: a command issued to read a
#                                     file reaches these (V3-02, measured)
#   `lock-pending`,                  pre-lock refusals: reads via terminal are
#   `seed-verification-failed`        unadmitted there, so reads reach these
#   `workdir-*`                      decided before the command is tokenized,
#                                    so the lane is not yet known
#   `contract-invalid`, `turn-closed`, `scope-control-invalid`,
#   `terminal-argument-unlisted`, `background-forbidden`, `compound-command`,
#   `command-parse`                  same: reachable by a pure read
ARTIFACT_DEVIATION_DENY_ACTIONS = frozenset(
    {
        # Structured write lane: only a tool in the write catalogue reaches
        # these, so the invocation is a write attempt by tool identity.
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
        # Git write lane: only `git add` / `git commit` reach these.
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
        # Execution lane: reached only after a command matched the head form
        # of a template the contract opted in to, which fixes the invocation
        # as an act at the execution boundary.
        "execution-option",
        "execution-stdin",
        "execution-target",
    }
)


def artifact_deny_counter(action: str) -> str | None:
    """Which turn counter a denied artifact-change call consumes.

    The deny ceiling exists to stop repeated probing of the write and
    execution boundaries. Charging it for anything else strands a turn that is
    following the required flow, so a reason code has to be admitted to the
    ceiling deliberately, and only a determination admission makes for itself
    qualifies (D-S3-7 補則). Every other denial spends the tool budget, which
    still bounds it and still closes the turn on exhaustion.

    This function is deliberately a total map over a finite literal set. It
    reads no classification table: which budget a denial spends must not
    depend on how an argument was spelled.
    """

    if action in ARTIFACT_BUDGET_DENY_ACTIONS:
        return None
    if action in ARTIFACT_DEVIATION_DENY_ACTIONS:
        return "denied_count"
    return "tool_count"


def normalize_base_commit(raw: Any) -> str:
    """Validate the assignment-time base commit carried by a contract seed.

    The value states which commit the assigned worktree started from, so the
    range a later audit takes a diff over is fixed by the assigning side
    rather than by whatever the executing agent reports. It is a full object
    name, never a ref or a short prefix: a ref moves, and a prefix is not a
    commit identity. An empty value is accepted here and means "not recorded"
    -- rows written before this field existed carry that, and a consumer that
    requires the base has to refuse the absence itself rather than read a
    default as a fact.
    """

    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise PathRejected(
            "base-commit-shape", "base_commit must be a Git object name string"
        )
    value = raw.strip()
    if not value:
        return ""
    if not _BASE_COMMIT_RE.fullmatch(value):
        raise PathRejected(
            "base-commit-shape",
            "base_commit must be a full lowercase hexadecimal Git object name",
        )
    return value


def normalize_git_write_actions(raw: Any) -> tuple[str, ...]:
    """Validate the contract field that carries Git write permission.

    Which side effects a turn may take is a property of its contract, not of
    the task class, so an assignment can hand out write access without
    handing out staging or committing.
    """

    if raw is None:
        return tuple(ARTIFACT_GIT_WRITE_ACTIONS)
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        raise PathRejected("git-write-shape", "git_write must be an array of actions")
    actions = []
    for item in raw:
        value = str(item or "").strip()
        if value not in ARTIFACT_GIT_WRITE_ACTIONS:
            raise PathRejected(
                "git-write-unknown", f"{value!r} is not a Git write action"
            )
        actions.append(value)
    return tuple(sorted(set(actions)))


def _artifact_turn_budget(turn: sqlite3.Row) -> dict[str, int]:
    """The locked contract's budget, or the class default before lock."""

    raw = turn["contract_json"]
    if raw:
        try:
            declared = (json.loads(raw) or {}).get("budget") or {}
        except (TypeError, ValueError):
            declared = {}
        if declared:
            merged = dict(ARTIFACT_CHANGE_CLASS_BUDGET)
            merged.update(
                {
                    key: int(value)
                    for key, value in declared.items()
                    if key in merged and isinstance(value, int)
                }
            )
            return merged
    return dict(ARTIFACT_CHANGE_CLASS_BUDGET)


def _artifact_budget_verdict(
    turn: sqlite3.Row, budget: dict[str, int]
) -> GateDecision | None:
    if time.time() - float(turn["started_at"]) > int(budget["max_wall_seconds"]):
        return GateDecision(
            False, "wall-budget", "the artifact-change wall-clock budget is exhausted"
        )
    if int(turn["tool_count"]) >= int(budget["max_tool_calls"]):
        return GateDecision(
            False,
            ARTIFACT_TOOL_BUDGET_ACTION,
            "the artifact-change tool budget is exhausted",
        )
    if int(turn["denied_count"]) >= int(budget["max_denied_calls"]):
        return GateDecision(False, "deny-budget", "too many denied out-of-scope attempts")
    return None


def _artifact_short_bundle_contains(token: str, forbidden: set[str]) -> bool:
    return (
        token.startswith("-")
        and not token.startswith("--")
        and len(token) > 1
        and any(character in forbidden for character in token[1:])
    )


def artifact_contract_scope(
    contract: dict[str, Any],
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Locked root, write patterns, test patterns, opted-in template ids."""

    targets = contract.get("targets") or {}
    worktrees = targets.get("worktrees") or [""]
    root = str(worktrees[0])
    write = tuple(targets.get("write_paths") or ())
    test = tuple(targets.get("test_paths") or ())
    templates = tuple((contract.get("execution") or {}).get("templates") or ())
    return root, write, test, templates


def _artifact_locked_write_scope_is_declared(contract: dict[str, Any]) -> bool:
    """Whether a locked contract carries the write scope every allow needs.

    The same condition the locked admission enforces as `contract-invalid`,
    readable by a lane that runs before that check is reached.
    """

    root, write_patterns, _, _ = artifact_contract_scope(contract)
    return bool(root and write_patterns)


def _admit_artifact_change_pre_lock(
    tool_name: str,
    *,
    action: str,
    reason: str,
) -> GateDecision:
    """Bounded default deny before the contract is locked.

    Known read/search/list tools are admitted with an audit record only.
    Structured writes, execution-bearing tools, and unknown tools are denied.
    Work-record annotation tools are admitted here as well as in the locked
    stage: they act only on the work-management plane, so there is no scope
    for them to exceed, and recording a blocked state is the escape valve
    INV-S6 asks a stalled turn to use instead of starting repair work.

    Run-signal tools are not admitted here. A turn with no verified contract
    has established nothing that a completion or review request could be
    about, and those transitions are what the orchestrator dispatches on.
    """

    if tool_name in ARTIFACT_READ_TOOLS:
        return GateDecision(
            True, "inspect-before-lock", "read-only inspection before scope lock"
        )
    if tool_name in ARTIFACT_WORK_RECORD_TOOLS:
        return GateDecision(
            True, "record-work-state", "work-record tool outside the repository boundary"
        )
    return GateDecision(False, action, reason)


# Git's own metadata directory name. A repository-relative target that names
# this entity is refused for artifact-change regardless of what the locked
# contract declares, because the contract's own guarantees are stated in terms
# of Git's repository discovery from the locked root: the workdir binding, the
# branch-drift check, and the read boundary all resolve through the metadata
# the target names. A write scope broad enough to reach it would let the turn
# restate its own enforcement premises, so breadth must not decide this.
#
# The carve-out is class-local on purpose. D-S3-7 決定 1 keeps the shared
# path-normalisation and pathspec implementations from growing artifact-change
# specific rules, so the refusal lives in this class's admission functions.
ARTIFACT_GIT_METADATA_SEGMENT = ".git"


def artifact_path_is_git_metadata(relative: str, *, root: str) -> bool:
    """True when a repository-relative path names Git's own metadata.

    Two matches, because the spelling of a name is not the identity of the
    entity it opens. The literal segment is the tree-independent one: it holds
    for a destination that does not exist yet, and for a nested repository's
    metadata anywhere under the root. The second walks the prefixes of the
    resolved path and asks the filesystem whether the entity there is the same
    entity as the ``.git`` beside it, which is the comparison every other
    check in this class already makes (``_artifact_git_discovery_verdict``
    compares resolved locations, and ``normalize_repo_relative_path`` decides
    membership by location rather than notation). A spelling the filesystem
    accepts as an alias of the metadata -- a name whose case the filesystem
    folds, a hard link to the pointer file of a linked worktree -- opens the
    same storage while carrying a different segment, so a check that compares
    only the segment refuses one spelling of a destination and admits another
    spelling of the same destination.

    ``root`` has no default. The identity comparison needs the locked root to
    resolve against, and a fence that silently degrades to spelling-only when
    the argument is omitted is the failure this function exists to remove.
    """

    parts = tuple(part for part in str(relative).split("/") if part)
    if ARTIFACT_GIT_METADATA_SEGMENT in parts:
        return True
    base = Path(os.path.realpath(str(root)))
    for depth in range(1, len(parts) + 1):
        candidate = base.joinpath(*parts[:depth])
        try:
            if os.path.samefile(
                str(candidate), str(candidate.parent / ARTIFACT_GIT_METADATA_SEGMENT)
            ):
                return True
        except OSError:
            # Either name is absent on this filesystem, so this prefix is not
            # an alias of the metadata. A destination that does not exist yet
            # is the ordinary case for a write.
            continue
    return False


def _artifact_git_discovery_verdict(root: str) -> GateDecision | None:
    """Refuse a Git write when discovery from the locked root was redirected.

    The metadata carve-out above closes the write form that repoints
    discovery, and this is the independent positive check: whatever the route,
    the directories Git actually resolves from the locked root must not live
    inside that root. A linked worktree resolves both to the primary
    repository, which is outside every worker's ceiling; an ordinary
    repository resolves both to its own ``.git``, which is admitted by name so
    the check adds no refusal for the shapes this class legitimately runs on.
    Anything else inside the root is agent-writable storage standing in for
    the repository, which is what makes hook execution and the identity
    derivation the approval gate performs reachable from a file write.
    """

    real_root = Path(os.path.realpath(str(root)))
    canonical = Path(os.path.realpath(str(real_root / ARTIFACT_GIT_METADATA_SEGMENT)))
    for option, label in (("--git-dir", "git-dir"), ("--git-common-dir", "git-common-dir")):
        try:
            raw = subprocess.run(
                ["git", "-C", str(root), "rev-parse", option],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
        except (
            subprocess.CalledProcessError,
            OSError,
            subprocess.SubprocessError,
        ) as exc:
            return GateDecision(
                False,
                "git-discovery-unverified",
                f"the Git {label} probe for the locked worktree could not run: {exc}",
            )
        if not raw:
            return GateDecision(
                False,
                "git-discovery-unverified",
                f"Git reported no {label} for the locked worktree",
            )
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = real_root / candidate
        resolved = Path(os.path.realpath(str(candidate)))
        if _is_inside(resolved, real_root) and resolved != canonical:
            return GateDecision(
                False,
                "git-discovery-redirected",
                f"the locked worktree's {label} resolves inside the locked root",
            )
    return None


def _artifact_stage_targets(
    tail: list[str], *, root: str, patterns: tuple[str, ...]
) -> tuple[str, ...]:
    tokens = list(tail)
    if tokens and tokens[0] == "--":
        tokens = tokens[1:]
    if not tokens:
        raise PathRejected(
            "stage-unbounded", "staging must name explicit paths inside the write scope"
        )
    resolved: list[str] = []
    for token in tokens:
        if token.startswith("-"):
            raise PathRejected("stage-option", "staging options are not admitted")
        if token.startswith(":"):
            raise PathRejected("stage-magic", "pathspec magic is not admitted")
        if token in {".", "./"} or any(character in token for character in "*?["):
            raise PathRejected(
                "stage-unbounded", "bulk or wildcard staging is not admitted"
            )
        relative, absolute = normalize_repo_relative_path(token, root=root)
        if artifact_path_is_git_metadata(relative, root=root):
            raise PathRejected(
                "stage-git-metadata",
                f"{relative} resolves to Git's own metadata, which is never staged",
            )
        if absolute.is_dir():
            # A directory pathspec stages its whole subtree, which is the
            # bulk form this class does not admit. The glob match below can
            # accept a directory name while rejecting the files under it, so
            # the shape has to be refused before the pattern is consulted.
            raise PathRejected(
                "stage-directory",
                f"{relative} is a directory; staging must name files",
            )
        if not scope_patterns_match(patterns, relative):
            raise PathRejected(
                "stage-scope", f"{relative} is outside the locked write scope"
            )
        resolved.append(relative)
    return tuple(resolved)


def _artifact_commit_verdict(tail: list[str]) -> tuple[bool, str, str]:
    if not tail:
        return (
            False,
            "commit-unsafe",
            "artifact-change commits require an explicit message",
        )
    for token in tail:
        if (
            token in _ARTIFACT_COMMIT_REWRITE_TOKENS
            or token.startswith(
                ("--fixup=", "--squash=", "--reuse-message=", "--reedit-message=")
            )
            or _artifact_short_bundle_contains(token, {"n", "C", "c", "i", "a", "p"})
        ):
            return (
                False,
                "commit-rewrite",
                "history rewrite, bulk staging, or verification bypass is outside artifact-change scope",
            )
    index = 0
    has_message = False
    while index < len(tail):
        token = tail[index]
        if token == "-m":
            if index + 1 >= len(tail) or not str(tail[index + 1]).strip():
                return (False, "commit-unsafe", "the commit message is missing")
            has_message = True
            index += 2
            continue
        if token.startswith("--message=") and len(token) > len("--message="):
            has_message = True
            index += 1
            continue
        if token in _ARTIFACT_COMMIT_SAFE_FLAGS:
            index += 1
            continue
        return (
            False,
            "commit-unsafe",
            "commit arguments exceed the bounded artifact-change syntax",
        )
    if not has_message:
        return (
            False,
            "commit-unsafe",
            "artifact-change commits require an explicit message",
        )
    return (True, "", "")


def _git_token_invokes_option(
    token: str, options: frozenset[str]
) -> tuple[bool, str]:
    """Does one Git argument token invoke one of `options`, and with what value?

    Git's parse-options accepts three spellings for a value-taking option, and
    a rule that reads only one of them leaves the others unclassified: the
    bare option with its value in the next token, the joined value
    (`--opt=<value>` or `-X<value>`), and a short option packed onto the end
    of a bundle of valueless flags (`-abX<value>`), where the value does not
    start at the third character.

    The returned value is the inline one only. A value carried in the next
    token needs no extraction: that token stands on its own and is examined on
    its own.

    The bundle scan stops at the first character that cannot be a flag letter,
    so a letter appearing inside some other option's value cannot be mistaken
    for a bundled option -- the false-deny direction of this widening.
    """

    if not token.startswith("-") or token in {"-", "--"}:
        return (False, "")
    name, separator, joined = token.partition("=")
    if name in options:
        return (True, joined if separator else "")
    if token.startswith("--"):
        return (False, "")
    short = {option[1] for option in options if len(option) == 2}
    if not short:
        return (False, "")
    for index in range(1, len(token)):
        character = token[index]
        if character in short:
            return (True, token[index + 1 :])
        if not character.isalnum():
            break
    return (False, "")


def _git_token_path_candidates(subcommand: str, token: str) -> tuple[str, ...]:
    """The substrings of one Git argument token that could name a path.

    A path is not always the whole token: an option can carry it as a joined
    value or packed onto a single-dash flag. Which options do so is a property
    of the option, not of the token's shape, so the value inside a token
    becomes a candidate only for the options declared as taking a path. The
    earlier shape-only rule -- treat every joined or bundled value as a path
    candidate -- read a search pattern, a format string, a display prefix, and
    a line range as boundary deviations, which put pure reads on the deny
    ceiling and stranded the turn on the sixth one.
    """

    if not token.startswith("-"):
        return (token,)
    options = ARTIFACT_GIT_PATH_OPTIONS.get(subcommand, frozenset())
    matched, value = _git_token_invokes_option(token, options)
    if matched and value:
        return (token, value)
    return (token,)


def _git_token_reaches_outside(subcommand: str, token: str) -> bool:
    """Does one Git argument token name a path outside the locked root?

    Segment-based on purpose. A revision range carries `..` as an operator
    between two revisions, so a substring test would read a pure read as a
    boundary deviation -- which is the false-deny half of the defect this
    classification exists to remove.
    """

    for candidate in _git_token_path_candidates(subcommand, token):
        path = Path(candidate)
        if path.is_absolute() or ".." in path.parts:
            return True
    return False


def _git_token_matches_marker(token: str, markers: frozenset[str]) -> bool:
    """Does one token invoke a declared write or execution form?

    Whether the marker's value is joined, separated, or packed onto a bundle
    does not change that the form was named, so the same spelling rule the
    path options use applies here.
    """

    matched, _ = _git_token_invokes_option(token, markers)
    return matched


def _artifact_git_deviation_action(subcommand: str, tail: list[str]) -> str | None:
    """Label a refused Git read for the audit record (D-S3-7 #3).

    Returns a deviation reason code, or None when the invocation looks like a
    pure read inside the locked root. Both the admitted read subset and the
    recognized-but-unadmitted set go through this.

    Audit attribution only since D-S3-7 補則. This function never admits
    anything, and it no longer selects a budget either: every code it can
    return spends the tool budget. It exists so an operator reading the audit
    trail can tell a refused read from an attempt at a boundary. Being wrong
    here is a labelling error, not a safety or liveness one, which is why the
    spelling coverage it depends on is no longer required to be exhaustive.
    """

    # Most specific label first. All of these branches count, so the order
    # changes only what the audit record says the attempt was.
    markers = ARTIFACT_GIT_WRITE_FORM_MARKERS.get(subcommand)
    if markers and any(_git_token_matches_marker(token, markers) for token in tail):
        return "git-write-form"
    for token in tail:
        if _git_token_reaches_outside(subcommand, token):
            return "git-read-unsafe"
    read_forms = ARTIFACT_GIT_READ_FORM_FLAGS.get(subcommand)
    if read_forms is not None and any(token not in read_forms for token in tail):
        return "git-write-form"
    return None


def artifact_git_read_refusal_action(subcommand: str, tail: list[str]) -> str:
    """Classify a refused read of an *admitted* read subcommand."""

    return _artifact_git_deviation_action(subcommand, tail) or "git-read-unbounded"


def artifact_git_unadmitted_refusal_action(subcommand: str, tail: list[str]) -> str:
    """Classify a refusal of a recognized-but-unadmitted read subcommand.

    Same three-way split as the admitted subset, with a different label for
    the pure-read case. Naming the subcommand is not enough: several members
    of the unadmitted set take the diff family's options, so the write form of
    one of them would otherwise be exempt from the ceiling.
    """

    return _artifact_git_deviation_action(subcommand, tail) or "git-read-unadmitted"


_GIT_READ_REFUSAL_REASONS = {
    "git-read-unsafe": "the git {subcommand} arguments reach outside the locked worktree",
    "git-write-form": "git {subcommand} is being used in its write form",
    "git-read-unbounded": (
        "the git {subcommand} arguments are outside the admitted read form"
    ),
}

_GIT_UNADMITTED_REASONS = dict(_GIT_READ_REFUSAL_REASONS) | {
    "git-read-unadmitted": (
        "git {subcommand} is read-only but is not in the admitted read set"
    ),
}


def _artifact_change_git_read_refusal(
    subcommand: str, tail: list[str]
) -> GateDecision:
    action = artifact_git_read_refusal_action(subcommand, tail)
    return GateDecision(
        False, action, _GIT_READ_REFUSAL_REASONS[action].format(subcommand=subcommand)
    )


def _admit_artifact_change_git_read(
    subcommand: str,
    tail: list[str],
    *,
    root: str,
) -> GateDecision:
    """Read-only Git inside the locked worktree (D-S3-7).

    The argument checks are the closeout allowlist functions themselves. No
    second parser is introduced for this class, and none of those functions
    is widened here: a read this class needs but closeout cannot express is
    a read this class does not admit.

    No branch binding is passed in. The only subcommand `_verification_action`
    resolves against a branch set is the network read this class does not
    admit, so handing it the binding would only suggest that the binding
    constrains reads. The guard test fixes that no admitted subcommand's
    verdict depends on it.
    """

    if subcommand == "status":
        return GateDecision(
            True, "inspect-repository-state", "read-only status of the locked worktree", root
        )
    if subcommand == "diff":
        if not _diff_args_are_bounded(tail):
            return _artifact_change_git_read_refusal(subcommand, tail)
        return GateDecision(
            True, "inspect-repository-diff", "read-only diff of the locked worktree", root
        )
    action = _verification_action(subcommand, tail, set())
    if action is None:
        return _artifact_change_git_read_refusal(subcommand, tail)
    return GateDecision(True, action, "read-only verification of the locked worktree", root)


def _admit_artifact_change_git(
    contract: dict[str, Any],
    tokens: list[str],
    *,
    root: str,
    write_patterns: tuple[str, ...],
    test_patterns: tuple[str, ...],
) -> GateDecision:
    if len(tokens) < 2:
        return GateDecision(False, "git-subcommand", "git needs a concrete subcommand")
    subcommand = tokens[1]
    tail = list(tokens[2:])
    bindings = (contract.get("targets") or {}).get("worktree_branches") or {}
    expected_branch = str(bindings.get(root) or "")
    if subcommand in ARTIFACT_GIT_READ_SUBCOMMANDS:
        # Reads are admitted before the write-permission check: a contract
        # that hands out no Git write permission still has to be able to see
        # the state it is working on. Drift is not re-checked either, because
        # reading is safe on whatever branch the worktree is actually on.
        # What holds the read inside the locked worktree is the seed check
        # that fixed the root at a worktree top level, plus Git's own
        # repository discovery from that root; the workdir binding pins the
        # working directory but does not by itself bound the arguments.
        return _admit_artifact_change_git_read(subcommand, tail, root=root)
    if subcommand in ARTIFACT_GIT_READ_UNADMITTED:
        # Denied either way. The argument classification only chooses the
        # audit label; it does not select a budget (D-S3-7 補則).
        action = artifact_git_unadmitted_refusal_action(subcommand, tail)
        return GateDecision(False, action, _GIT_UNADMITTED_REASONS[action].format(
            subcommand=subcommand
        ))
    if subcommand not in {"add", "commit"}:
        return GateDecision(
            False,
            "git-subcommand",
            f"git {subcommand} is outside the locked artifact-change scope",
        )
    permitted = (contract.get("actions") or {}).get("git_write")
    if not isinstance(permitted, list):
        # A contract that does not carry the field cannot be read as
        # carrying every permission it omits.
        return GateDecision(
            False,
            "git-write-unspecified",
            "the locked contract does not declare any Git write permission",
        )
    required = next(
        name for name, sub in _GIT_WRITE_SUBCOMMANDS.items() if sub == subcommand
    )
    if required not in permitted:
        return GateDecision(
            False,
            "git-write-forbidden",
            f"the locked contract does not permit {required}",
        )
    if not expected_branch:
        return GateDecision(
            False, "target-closed", "the locked worktree has no branch binding"
        )
    try:
        current = _validated_worktree_branches([root])[str(Path(root).resolve())]
    except (ValueError, KeyError) as exc:
        return GateDecision(False, "target-drift", str(exc))
    if current != expected_branch:
        return GateDecision(
            False, "target-drift", "the worktree branch changed after scope lock"
        )
    redirected = _artifact_git_discovery_verdict(root)
    if redirected is not None:
        return redirected
    patterns = tuple(write_patterns) + tuple(test_patterns)
    if subcommand == "add":
        try:
            staged = _artifact_stage_targets(tail, root=root, patterns=patterns)
        except PathRejected as exc:
            return GateDecision(False, exc.code, str(exc))
        return GateDecision(
            True,
            "stage-in-scope-change",
            "stage paths inside the locked write scope",
            ",".join(sorted(staged))[:400],
        )
    allowed, action, reason = _artifact_commit_verdict(tail)
    if not allowed:
        return GateDecision(False, action, reason)
    return GateDecision(
        True, "commit-in-scope-change", "create the local commit for this turn", root
    )


def _scan_template_tokens(
    template: ExecutionTemplate,
    tail: list[str],
    *,
    root: str,
    patterns: tuple[str, ...],
) -> GateDecision:
    """Full-token inspection: explicit allowlist, unknown is denied at once."""

    unsafe = GateDecision(
        False, "execution-option", "an unknown or unsafe verification option was given"
    )
    stdin_form = GateDecision(
        False,
        "execution-stdin",
        "taking verification targets from standard input is not admitted",
    )
    targets: list[str] = []
    index = 0
    target_mode = False
    while index < len(tail):
        token = tail[index]
        if token == "-":
            return stdin_form
        if not target_mode and token == "--":
            target_mode = True
            index += 1
            continue
        if not target_mode and token.startswith("-"):
            name, separator, value = token.partition("=")
            if separator:
                if name not in template.valued_flags or not _TEMPLATE_VALUE_RE.fullmatch(
                    value
                ):
                    return unsafe
                index += 1
                continue
            if token in template.boolean_flags:
                index += 1
                continue
            if token in template.valued_flags:
                if index + 1 >= len(tail) or not _TEMPLATE_VALUE_RE.fullmatch(
                    tail[index + 1]
                ):
                    return unsafe
                index += 2
                continue
            return unsafe
        if any(character in token for character in "*?["):
            return GateDecision(
                False, "execution-target", "verification targets must be named files"
            )
        try:
            relative, absolute = normalize_repo_relative_path(token, root=root)
        except PathRejected as exc:
            return GateDecision(False, exc.code, str(exc))
        if absolute.is_dir():
            return GateDecision(
                False,
                "execution-target",
                "directory-wide verification targets are not admitted",
            )
        if not scope_patterns_match(patterns, relative):
            return GateDecision(
                False,
                "execution-target",
                f"{relative} is outside the locked verification scope",
            )
        targets.append(relative)
        index += 1
    if not targets:
        return GateDecision(
            False, "execution-target", "verification requires explicit file targets"
        )
    return GateDecision(
        True,
        template.action,
        f"opted-in {template.template_id} on locked file targets",
        ",".join(sorted(targets))[:400],
    )


def _admit_artifact_change_execution(
    tokens: list[str],
    *,
    root: str,
    write_patterns: tuple[str, ...],
    test_patterns: tuple[str, ...],
    templates: tuple[str, ...],
) -> GateDecision:
    if not templates:
        return GateDecision(
            False,
            "execution-not-opted-in",
            "this contract did not opt in to execution-bearing verification",
        )
    patterns = tuple(write_patterns) + tuple(test_patterns)
    for template_id in templates:
        template = EXECUTION_TEMPLATES[template_id]
        tail = _template_head_tail(template, tokens)
        if tail is None:
            continue
        return _scan_template_tokens(template, tail, root=root, patterns=patterns)
    return GateDecision(
        False,
        "execution-template",
        "the command matches no opted-in verification template",
    )


def _admit_artifact_change_terminal(
    contract: dict[str, Any],
    args: dict[str, Any],
    *,
    root: str,
    write_patterns: tuple[str, ...],
    test_patterns: tuple[str, ...],
    templates: tuple[str, ...],
) -> GateDecision:
    unlisted = sorted(set(args) - ARTIFACT_TERMINAL_ARGUMENT_FIELDS)
    if unlisted:
        # The write catalogue closes over tool argument fields by name; the
        # same closure has to hold for the one execution-bearing tool, or an
        # argument that never reaches the command allowlist can carry the
        # same substitutions the allowlist exists to refuse.
        return GateDecision(
            False,
            "terminal-argument-unlisted",
            f"terminal argument {unlisted[0]!r} is not in the admitted field set",
        )
    if bool(args.get("background")) or bool(args.get("pty")):
        return GateDecision(
            False,
            "background-forbidden",
            "background and interactive commands are not allowed",
        )
    command = str(args.get("command") or "").strip()
    workdir = str(args.get("workdir") or "").strip()
    # The workdir is checked before the command is tokenized, so these three
    # refusals happen before admission knows which lane the call belongs to: a
    # pure read and a staging attempt reach them alike. They therefore carry
    # their own reason codes rather than the write-target codes they used to
    # share. Counting is driven by the reason code (D-S3-7 補則), so a code
    # issued by two different determinations cannot be mapped soundly to one
    # counter -- the write-target spellings have to mean the write lane only.
    if not workdir or not Path(workdir).is_absolute():
        return GateDecision(
            False, "workdir-missing", "terminal commands require an absolute workdir"
        )
    if ".." in Path(workdir).parts:
        return GateDecision(
            False,
            "workdir-traversal",
            "the terminal workdir carries an upward reference",
        )
    if not paths_name_the_same_location(workdir, root):
        return GateDecision(
            False,
            "workdir-outside",
            "the terminal workdir is outside the locked worktree",
        )
    try:
        tokens = _tokenize_single_shell_command(command)
    except PermissionError:
        return GateDecision(
            False,
            "compound-command",
            "compound or shell-composed commands are not admitted",
        )
    except ValueError:
        return GateDecision(
            False, "command-parse", "the terminal command could not be parsed"
        )
    if not tokens:
        return GateDecision(False, "command-parse", "the terminal command was empty")
    if tokens[0] == "git":
        return _admit_artifact_change_git(
            contract,
            tokens,
            root=root,
            write_patterns=write_patterns,
            test_patterns=test_patterns,
        )
    return _admit_artifact_change_execution(
        tokens,
        root=root,
        write_patterns=write_patterns,
        test_patterns=test_patterns,
        templates=templates,
    )


def _admit_artifact_change_locked(
    turn: sqlite3.Row,
    tool_name: str,
    args: dict[str, Any],
    *,
    run_signal_exception_unspent: bool = False,
) -> GateDecision:
    """Locked admission for artifact-change (first layer plus opted-in second).

    ``run_signal_exception_unspent`` states whether this turn has still not
    used its single past-budget run signal. Only the caller that holds the
    decision transaction can answer that, so it is supplied rather than read
    here; the default is False, which means the exception cannot be granted
    by a caller that is not recording the consumption.
    """

    contract = json.loads(turn["contract_json"] or "{}")
    budget = _artifact_turn_budget(turn)
    exceeded = _artifact_budget_verdict(turn, budget)
    if exceeded is not None:
        # After the tool budget is spent the verdict denies everything, and a
        # turn whose work is already finished then loses the only call that
        # reports it (measured 2026-08-29, run record 課題1). The exception is
        # one run signal for the bound task, once per turn -- not an exempt
        # lane -- and every condition it needs is checked here:
        #   - the blocking verdict is the tool ceiling. The wall verdict
        #     precedes it, so an out-of-time turn never reaches this branch;
        #     the deny ceiling is verified separately because the tool
        #     verdict is reported first when both are exhausted, and a turn
        #     stranded for repeated boundary deviation must stay stranded.
        #   - the locked contract carries a write scope. Every other allow in
        #     this function is downstream of that check, and an exception
        #     that skipped it would be the one allow a scope-less lock could
        #     still produce.
        #   - the call is a run signal whose whole argument set is the bound
        #     task and its own report.
        if (
            exceeded.action == ARTIFACT_TOOL_BUDGET_ACTION
            and run_signal_exception_unspent
            and int(turn["denied_count"]) < int(budget["max_denied_calls"])
            and _artifact_locked_write_scope_is_declared(contract)
            and artifact_run_signal_targets_bound_task(turn, tool_name, args)
        ):
            return GateDecision(
                True,
                ARTIFACT_RUN_SIGNAL_PAST_BUDGET_ACTION,
                "the single run-state transition this turn may report after "
                "the tool budget is exhausted",
            )
        return exceeded
    root, write_patterns, test_patterns, templates = artifact_contract_scope(contract)
    if not root or not write_patterns:
        return GateDecision(
            False, "contract-invalid", "the locked contract carries no write scope"
        )
    if tool_name in ARTIFACT_READ_TOOLS:
        return GateDecision(
            True, "inspect-locked-target", "read-only inspection inside a locked turn"
        )
    if tool_name in ARTIFACT_WORK_RECORD_TOOLS:
        return GateDecision(
            True, "record-work-state", "work-record tool outside the repository boundary"
        )
    if tool_name in ARTIFACT_RUN_SIGNAL_TOOLS:
        return GateDecision(
            True, "signal-run-outcome", "run-state transition on the locked task"
        )
    if tool_name == "terminal":
        return _admit_artifact_change_terminal(
            contract,
            args,
            root=root,
            write_patterns=write_patterns,
            test_patterns=test_patterns,
            templates=templates,
        )
    if tool_name in ARTIFACT_WRITE_TOOL_CATALOG:
        try:
            raw_targets = collect_write_targets(tool_name, args)
        except PathRejected as exc:
            return GateDecision(False, exc.code, str(exc))
        patterns = tuple(write_patterns) + tuple(test_patterns)
        resolved: list[str] = []
        for raw in raw_targets:
            try:
                relative, _ = normalize_repo_relative_path(raw, root=root)
            except PathRejected as exc:
                return GateDecision(False, exc.code, str(exc))
            # Checked before the pattern match so the refusal never depends on
            # how broad the declared ceiling happens to be.
            if artifact_path_is_git_metadata(relative, root=root):
                return GateDecision(
                    False,
                    "write-git-metadata",
                    f"{relative} resolves to Git's own metadata, which is not a "
                    "write destination for this class",
                )
            if not scope_patterns_match(patterns, relative):
                return GateDecision(
                    False,
                    "write-scope",
                    f"{relative} is outside the locked write scope",
                )
            resolved.append(relative)
        return GateDecision(
            True,
            "write-in-scope-change",
            "write inside the locked write scope",
            ",".join(sorted(resolved))[:400],
        )
    return GateDecision(
        False,
        "expansion-required",
        f"{tool_name} is outside the locked artifact-change scope",
    )


# Task class -> locked admission function. Both admission and the G3
# "the contract already permits this" stage read this single table, so a
# newly enforced class never needs a hardcoded branch in either place.
_LOCKED_ADMISSION_DISPATCH: dict[str, Any] = {
    "repository-closeout": GateStore._admit_closeout_locked,
    "artifact-change": _admit_artifact_change_locked,
}


def locked_admission_for(task_class: str) -> Any | None:
    """The locked admission function for a task class, or None if unenforced."""

    return _LOCKED_ADMISSION_DISPATCH.get(task_class)


# Task class -> per-turn decision function. Admission reads this table
# instead of branching on the class, so enforcing a new class is a table
# entry rather than an edit in two places that must agree.
_DECISION_DISPATCH: dict[str, Any] = {
    "repository-closeout": GateStore._closeout_decision,
    "artifact-change": GateStore._artifact_change_decision,
}


def decision_for(task_class: str) -> Any | None:
    """The per-turn decision function for a task class, or None."""

    return _DECISION_DISPATCH.get(task_class)


_CONTRACT_VALIDATOR: Any = None


def _contract_validator() -> Any:
    """Compile the contract validator once per process.

    The schema file was re-read and re-checked on every locked turn, which
    put file I/O on the hook path for a document that cannot change while
    the process runs.
    """

    global _CONTRACT_VALIDATOR
    if _CONTRACT_VALIDATOR is None:
        schema_path = (
            Path(__file__).parent / "schemas" / "scope-contract-v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator_class = import_module("jsonschema").Draft202012Validator
        validator_class.check_schema(schema)
        _CONTRACT_VALIDATOR = validator_class(schema)
    return _CONTRACT_VALIDATOR


def _validate_contract_against_schema(contract: dict[str, Any]) -> None:
    try:
        _contract_validator().validate(contract)
    except Exception as exc:
        raise ValueError(f"ScopeContract schema validation failed: {exc}") from exc


def _validated_worktree_branches(worktrees: list[str]) -> dict[str, str]:
    branches: dict[str, str] = {}
    for worktree in worktrees:
        try:
            top_level = subprocess.run(
                ["git", "-C", worktree, "rev-parse", "--show-toplevel"],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "-C", worktree, "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"cannot verify Git worktree {worktree}: {exc}") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise WorktreeProbeError(
                f"the Git worktree probe for {worktree} could not run: {exc}"
            ) from exc
        if str(Path(top_level).resolve()) != str(Path(worktree).resolve()):
            raise ValueError(f"target is not the Git worktree root: {worktree}")
        if not branch:
            raise ValueError(f"detached HEAD is not supported for closeout: {worktree}")
        branches[str(Path(worktree).resolve())] = branch
    return dict(sorted(branches.items()))


def _pathspec_is_bounded(token: str) -> bool:
    path = Path(token)
    return (
        token not in {".", "./"}
        and not any(character in token for character in "*?[")
        and not path.is_absolute()
        and ".." not in path.parts
    )


def _diff_args_are_bounded(args: list[str]) -> bool:
    safe_flags = {
        "--cached",
        "--staged",
        "--check",
        "--stat",
        "--name-only",
        "--name-status",
        "--summary",
        "--no-color",
        "--color=never",
    }
    path_mode = False
    for token in args:
        if token == "--":
            if path_mode:
                return False
            path_mode = True
        elif path_mode:
            if not _pathspec_is_bounded(token):
                return False
        elif token not in safe_flags:
            return False
    return True


def _verification_action(
    subcommand: str,
    args: list[str],
    branches: set[str],
) -> str | None:
    if subcommand == "rev-parse":
        if args in (["HEAD"], ["--verify", "HEAD"]):
            return "verify-local-head"
        if args == ["--abbrev-ref", "HEAD"]:
            return "verify-branch"
        return None
    if subcommand == "branch":
        return "verify-branch" if args == ["--show-current"] else None
    if subcommand == "remote":
        return "verify-remote" if args == ["get-url", "origin"] else None
    if subcommand == "ls-remote":
        filtered = [token for token in args if token == "--heads"]
        positional = [token for token in args if token != "--heads"]
        if len(filtered) != 1 or len(positional) != 2 or positional[0] != "origin":
            return None
        requested = positional[1]
        requested = requested.removeprefix("refs/heads/")
        return "verify-remote-ref" if requested in branches else None
    return None


def _short_option_bundle_contains(token: str, forbidden: set[str]) -> bool:
    return (
        token.startswith("-")
        and not token.startswith("--")
        and len(token) > 1
        and any(character in forbidden for character in token[1:])
    )


def _add_args_are_bounded(args: list[str]) -> bool:
    if args and args[0] == "--":
        args = args[1:]
    return bool(args) and all(
        not token.startswith("-") and _pathspec_is_bounded(token) for token in args
    )


def _commit_args_are_bounded(args: list[str]) -> bool:
    if not args:
        return False
    index = 0
    has_message = False
    single_flags = {"-a", "--all", "-s", "--signoff", "-q", "--quiet"}
    while index < len(args):
        token = args[index]
        if token == "-m":
            if index + 1 >= len(args):
                return False
            has_message = True
            index += 2
            continue
        if token.startswith("--message=") and len(token) > len("--message="):
            has_message = True
            index += 1
            continue
        if token not in single_flags:
            return False
        index += 1
    return has_message


def _push_args_match_locked_ref(args: list[str], branches: set[str]) -> bool:
    allowed_options = {"-u", "--set-upstream", "--porcelain"}
    positional = [token for token in args if token not in allowed_options]
    if len(positional) < 2 or positional[0] != "origin":
        return False
    for refspec in positional[1:]:
        if refspec.startswith("+"):
            return False
        source, separator, destination = refspec.partition(":")
        if not separator:
            if source not in branches:
                return False
            continue
        if source == "HEAD":
            normalized_destination = destination.removeprefix("refs/heads/")
            if normalized_destination not in branches:
                return False
            continue
        normalized_source = source.removeprefix("refs/heads/")
        normalized_destination = destination.removeprefix("refs/heads/")
        if normalized_source not in branches or normalized_destination not in branches:
            return False
    return True


def _tokenize_single_shell_command(command: str) -> list[str]:
    if "\n" in command or "\r" in command:
        raise PermissionError("multi-line shell command")
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    operators = set("|&;<>")
    for token in tokens:
        if token and all(character in operators for character in token):
            raise PermissionError("shell composition")
        if "$" in token or "`" in token or token.startswith("#"):
            raise PermissionError("shell expansion")
    return tokens


def _result_mapping(result: Any) -> dict[str, Any] | None:
    parsed = result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _normalized_git_evidence(
    *,
    tool_name: str,
    args: dict[str, Any],
    result: Any,
    succeeded: bool,
) -> str:
    if not succeeded or tool_name != "terminal":
        return ""
    command = str(args.get("command") or "")
    try:
        tokens = _tokenize_single_shell_command(command)
    except (PermissionError, ValueError):
        return ""
    if tokens[:2] == ["git", "rev-parse"]:
        if tokens[2:] not in (["HEAD"], ["--verify", "HEAD"]):
            return ""
    elif tokens[:2] == ["git", "ls-remote"]:
        if len(tokens) < 4:
            return ""
    else:
        return ""
    parsed = _result_mapping(result)
    output = parsed.get("output") if parsed is not None else None
    if not isinstance(output, str) or not output.strip():
        return ""
    candidate = output.splitlines()[0].split()[0].lower()
    return candidate if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", candidate) else ""


def _tool_result_succeeded(status: str, result: Any, *, tool_name: str) -> bool:
    if status != "ok":
        return False
    parsed = _result_mapping(result)
    if parsed is None or parsed.get("error"):
        return False
    if tool_name == "terminal":
        exit_value = parsed.get("exit_code", parsed.get("returncode"))
        return type(exit_value) is int and exit_value == 0
    if parsed.get("success") is False or parsed.get("ok") is False:
        return False
    return parsed.get("success") is True or parsed.get("ok") is True


def _is_within(path: str, root: str) -> bool:
    try:
        Path(path).relative_to(Path(root))
        return True
    except ValueError:
        return False


def default_state_path(hermes_home: str | Path | None = None) -> Path:
    if hermes_home is None:
        import os

        raw_home = os.environ.get("HERMES_HOME", "").strip()
        home = Path(raw_home).expanduser() if raw_home else Path.home() / ".hermes"
    else:
        home = Path(hermes_home).expanduser()
    return home.resolve() / "plugin-data" / "pda-scope-gate" / "scope-gate.db"


def validate_shell_payload(
    payload: dict[str, Any],
    *,
    state_path: str | Path | None = None,
) -> dict[str, str]:
    """Validate Hermes shell-hook JSON and return its stdout directive."""

    if not isinstance(payload, dict):
        raise TypeError("hook payload must be an object")
    if payload.get("hook_event_name") != "pre_tool_call":
        raise ValueError("validator accepts only pre_tool_call payloads")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    extra = payload.get("extra")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("hook payload requires tool_name")
    if not isinstance(tool_input, dict) or not isinstance(extra, dict):
        raise TypeError("hook payload requires object tool_input and extra")

    store = GateStore(state_path or default_state_path())
    # One resolution for the whole call: binding the turn by one identifier
    # and admitting against another is how a contract stops covering the very
    # call it was recorded for. The out-of-process surface resolves by the
    # same rule as the in-process one, contract probe included, so a wrong
    # anchor cannot retire a contract here either.
    session_id = str(payload.get("session_id") or "")
    task_id = resolve_task_binding(
        str(extra.get("task_id") or ""),
        has_contract=lambda candidate: store.has_contract_record(
            task_id=candidate, session_id=session_id
        ),
    )
    resolved_turn = store.resolve_turn_id(
        turn_id=str(extra.get("turn_id") or ""),
        task_id=task_id,
        session_id=session_id,
    )
    if not resolved_turn:
        unbound = store.admit_without_turn(
            task_id=task_id,
            session_id=session_id,
            tool_name=tool_name,
        )
        if unbound.allowed:
            return {}
        return {
            "action": "block",
            "message": f"PDA scope gate [{unbound.action}]: {unbound.reason}",
        }
    decision = store.admit_tool(
        turn_id=resolved_turn,
        tool_call_id=str(extra.get("tool_call_id") or ""),
        tool_name=tool_name,
        args=tool_input,
        task_id=task_id,
        session_id=session_id,
    )
    if decision.allowed:
        return {}
    return {
        "action": "block",
        "message": f"PDA scope gate [{decision.action}]: {decision.reason}",
    }
