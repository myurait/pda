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

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

# The fenced block that carries the machine-readable declaration. The info
# string is matched exactly so an ordinary JSON example in a card body cannot
# be mistaken for a scope declaration.
SCOPE_BLOCK_INFO = "pda-scope"
_SCOPE_BLOCK_RE = re.compile(
    r"^[ \t]*```[ \t]*" + re.escape(SCOPE_BLOCK_INFO) + r"[ \t]*\r?\n(.*?)^[ \t]*```",
    re.DOTALL | re.MULTILINE,
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


def parse_scope_declaration(body: Any) -> dict[str, Any]:
    """Extract the scope declaration from a card body.

    Exactly one ``pda-scope`` block must be present. Zero blocks means the
    card is not Ready for the seeded lane; more than one is ambiguous and is
    refused rather than resolved by picking one.
    """

    text = body if isinstance(body, str) else ""
    blocks = _SCOPE_BLOCK_RE.findall(text)
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


def derive_seed_payload(*, task_id: str, body: Any) -> dict[str, Any]:
    """Turn a card body into the keyword arguments for a contract seed.

    The derivation is deterministic and performs no ordering or de-duplication
    of its own: pattern normalisation is the gate's single responsibility
    (``normalize_scope_patterns``).  Re-deriving from an unchanged card must
    produce a byte-identical payload, because the gate refuses a second seed
    whose payload differs from the first.
    """

    declaration = parse_scope_declaration(body)
    write_paths = _string_list(declaration.get("write_paths"), "write_paths")
    if not write_paths:
        raise ScopeSeedError(
            "invalid-scope-declaration",
            "write_paths must declare at least one pattern",
        )
    # Defaults: test asset writes are not granted unless declared, and the
    # second contract layer stays closed unless the card opts in.
    test_paths = _string_list(declaration.get("test_paths", []), "test_paths")
    execution = _string_list(declaration.get("execution", []), "execution")

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
    state_path: Path | str | None = None,
) -> dict[str, Any]:
    """Record the assignment-time contract seed for one task.

    Raises ``ScopeSeedError`` for every failure, including a second seed whose
    payload differs from the one already recorded.  A differing payload means
    the card's declaration changed while the task was in flight; the gate
    refuses it, and surfacing that as an error keeps the ceiling meaningful
    instead of silently accepting a new one.
    """

    payload = derive_seed_payload(task_id=task_id, body=body)
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
    except ValueError as exc:
        raise ScopeSeedError("scope-seed-rejected", str(exc)) from exc
    except OSError as exc:
        raise ScopeSeedError("scope-seed-unavailable", str(exc)) from exc
