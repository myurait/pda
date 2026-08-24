"""Hermes-facing runtime adapter for the deterministic scope gate."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any

try:  # Hermes loads the plugin as a namespaced package.
    from .scope_gate import (
        ARTIFACT_ENFORCED_STATES,
        GateStore,
        default_state_path,
        resolve_task_binding,
    )
except ImportError:  # Direct unit-test/script import fallback.
    from scope_gate import (
        ARTIFACT_ENFORCED_STATES,
        GateStore,
        default_state_path,
        resolve_task_binding,
    )


_CLOSEOUT_CONTEXT = """PDA scope contract: repository-closeout (hard enforced).
Objective: save only the already-existing, commit-ready content requested by the user.
Before any mutation, run one bounded `git status` in the intended absolute workdir, then call
`scope_gate` with action=lock and that repository/worktree/branch. After lock, use only the
smallest diff/integrity check, stage only explicit inspected paths, requested commit, requested
`git push origin <locked-branch>`, then verify equality using both `git rev-parse HEAD` and
`git ls-remote --heads origin <locked-branch>`. Do not edit content, fix conflicts/tests,
inspect other branches/worktrees,
delegate, use execute_code/background work, deploy, restart, or wait on unrelated work.
Call scope_gate action=complete once the requested closeout predicate is established or blocked."""

_ARTIFACT_CHANGE_CONTEXT = """PDA scope contract: artifact-change (hard enforced for this turn).
Write permission and execution permission are separate contract layers. Before any mutation the
turn must be locked: either the assignment already locked it, or you call `scope_gate` with
action=lock, one absolute worktree, and the write scope you need (`write_paths`, plus `test_paths`
for test assets and `execution` template ids only if verification must actually run). A lock can
only narrow an assigned scope, never widen it, and the target and write scope cannot be extended
afterwards. Once locked you may write inside the locked scope, stage explicitly named in-scope
paths, and make one local commit with an explicit message. File and search tools are admitted at
every stage, as are the annotation tools for the task board and the step list (`kanban_show`,
`kanban_attachments`, `kanban_comment`, `kanban_heartbeat`, `kanban_block`, `todo`); if you cannot
proceed, record it with `kanban_block` rather than starting repair work. `kanban_complete` and
`kanban_request_review` are admitted only once the turn is locked. Creating cards, recording a
reviewer verdict, and linking or attaching to a card are not admitted at all. Read-only Git is
admitted only after the lock, and only as `git status`, bounded `git diff`, `git rev-parse HEAD`
(also `--verify HEAD` / `--abbrev-ref HEAD`), and `git branch --show-current`, inside the locked
worktree; use `rev-parse HEAD` for the commit id (`git log` is not admitted). Other read-only Git
forms are refused without counting against the deny ceiling, so a refused read never strands the
turn. Pushing, history rewriting, bypassing verification hooks, broad test runs, delegation,
background work, and any write outside the scope are denied. Call scope_gate action=complete when
the change is done or blocked."""


PRELOCK_ENFORCEMENT_ENV = "PDA_SCOPE_GATE_ARTIFACT_PRELOCK"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def prelock_enforcement_setting() -> bool | None:
    """Read the pre-lock default-deny switch from the environment.

    Without a configuration path the stage could only be turned on by
    editing a module constant, which also left operators with no way to read
    back which lanes it is in force for.
    """

    raw = os.environ.get(PRELOCK_ENFORCEMENT_ENV, "").strip().lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return None


class ScopeGatePluginRuntime:
    def __init__(self, state_path: str | Path | None = None) -> None:
        if state_path is None:
            try:
                get_hermes_home = import_module("hermes_constants").get_hermes_home
                state_path = default_state_path(get_hermes_home())
            except (AttributeError, ImportError):
                state_path = default_state_path()
        self.store = GateStore(
            state_path,
            enforce_artifact_change_pre_lock=prelock_enforcement_setting(),
        )

    def pre_llm_call(self, **kwargs: Any) -> dict[str, str] | None:
        try:
            # Inside the boundary: resolving the binding reads the store, so
            # a store failure here has to land on the same fail-closed exit
            # as a registration failure rather than escaping the hook.
            task_id, session_id = self._binding(kwargs)
            turn_id = self._turn_key(kwargs, task_id=task_id, session_id=session_id)
            if not turn_id:
                return None
            intent = self.store.start_turn(
                turn_id=turn_id,
                session_id=session_id,
                task_id=task_id,
                user_message=str(kwargs.get("user_message") or ""),
            )
        except Exception:  # noqa: BLE001 -- registration failure must not
            # take the hook down. No turn row means later tool calls take the
            # unbound path, which is fail-closed wherever a contract exists.
            return None
        if intent.task_class == "repository-closeout":
            return {"context": _CLOSEOUT_CONTEXT}
        if intent.task_class == "artifact-change":
            turn = self.store.get_turn(turn_id)
            if (
                turn is not None
                and str(turn["state"]) in ARTIFACT_ENFORCED_STATES
                and str(turn["state"]) != "completed"
            ):
                return {"context": _ARTIFACT_CHANGE_CONTEXT}
        return None

    def record_contract_seed(self, **kwargs: Any) -> dict[str, Any]:
        """Assignment-side seed recording.

        Exposed on the runtime for the orchestrator's dispatch path only. It
        is intentionally absent from the `scope_gate` tool surface so the
        executing agent cannot seed or widen its own contract.
        """

        return self.store.record_contract_seed(**kwargs)

    def pre_tool_call(self, **kwargs: Any) -> dict[str, str] | None:
        try:
            # Resolution reads the store, so it belongs inside the boundary.
            task_id, session_id = self._binding(kwargs)
            turn_id = self.store.resolve_turn_id(
                turn_id=str(kwargs.get("turn_id") or ""),
                task_id=task_id,
                session_id=session_id,
            )
            if not turn_id:
                decision = self.store.admit_without_turn(
                    task_id=task_id,
                    session_id=session_id,
                    tool_name=str(kwargs.get("tool_name") or ""),
                )
            else:
                raw_args = kwargs.get("args")
                args = raw_args if isinstance(raw_args, dict) else {}
                decision = self.store.admit_tool(
                    turn_id=turn_id,
                    tool_call_id=str(kwargs.get("tool_call_id") or ""),
                    tool_name=str(kwargs.get("tool_name") or ""),
                    args=args,
                    task_id=task_id,
                    session_id=session_id,
                )
        except Exception as exc:  # noqa: BLE001 -- this boundary must fail closed.
            return {
                "action": "block",
                "message": (
                    "PDA scope gate [admission-validator-error]: "
                    f"{type(exc).__name__}: {exc}"
                ),
            }
        if decision.allowed:
            return None
        return {
            "action": "block",
            "message": f"PDA scope gate [{decision.action}]: {decision.reason}",
        }

    def tool_execution_middleware(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        next_call: Callable[[dict[str, Any]], Any],
        **kwargs: Any,
    ) -> Any:
        """Revalidate the final post-hook arguments immediately before dispatch."""

        try:
            # Resolution reads the store, so it belongs inside the boundary.
            task_id, session_id = self._binding(kwargs)
            turn_id = self.store.resolve_turn_id(
                turn_id=str(kwargs.get("turn_id") or ""),
                task_id=task_id,
                session_id=session_id,
            )
            if not turn_id:
                unbound = self.store.admit_without_turn(
                    task_id=task_id,
                    session_id=session_id,
                    tool_name=tool_name,
                )
                if unbound.allowed:
                    return next_call(args)
                return {
                    "error": f"PDA scope gate [{unbound.action}]: {unbound.reason}"
                }
            decision = self.store.admit_tool(
                turn_id=turn_id,
                tool_call_id=str(kwargs.get("tool_call_id") or ""),
                tool_name=tool_name,
                args=args,
                task_id=task_id,
                session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001 -- this boundary must fail closed.
            return {
                "error": (
                    "PDA scope gate [execution-validator-error]: "
                    f"{type(exc).__name__}: {exc}"
                )
            }
        if not decision.allowed:
            return {
                "error": f"PDA scope gate [{decision.action}]: {decision.reason}"
            }
        return next_call(args)

    def handle_scope_gate(self, params: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        action = str(params.get("action") or "")
        try:
            # Resolution reads the store, so it belongs inside the boundary.
            task_id, session_id = self._binding(kwargs)
            turn_id = self.store.resolve_turn_id(
                turn_id=str(kwargs.get("turn_id") or ""),
                task_id=task_id,
                session_id=session_id,
            )
            if not turn_id:
                return {
                    "ok": False,
                    "error": "No active scope turn is bound to this call.",
                }
            if action == "lock":
                targets = params.get("targets")
                if not isinstance(targets, dict):
                    raise ValueError("lock requires targets")
                contract = self.store.lock_turn(
                    turn_id=turn_id,
                    repositories=_optional_string_list(targets.get("repositories")),
                    worktrees=_string_list(targets.get("worktrees")),
                    branches=_optional_string_list(targets.get("branches")),
                    write_paths=_optional_string_list(targets.get("write_paths")),
                    test_paths=_optional_string_list(targets.get("test_paths")),
                    execution=_optional_string_list(params.get("execution")),
                )
                return {"ok": True, "contract": contract}
            if action == "review":
                candidate = params.get("candidate") or {}
                result = self.store.request_expansion(
                    turn_id=turn_id,
                    tool_name=str(candidate.get("tool_name") or ""),
                    args=dict(candidate.get("args") or {}),
                    reason=str(candidate.get("reason") or params.get("reason") or ""),
                    estimated_cost=candidate.get("estimated_cost"),
                    # No independent judge is wired in this rollout stage:
                    # stage 3 fails closed, so only deterministic outcomes
                    # (deny / already-allowed) can occur at runtime.
                    judge=None,
                )
                if result["ok"]:
                    return result
                return {"ok": False, "error": result["reason"], **result}
            if action == "complete":
                status = str(params.get("status") or "success")
                turn = self.store.finalize_turn(turn_id=turn_id, status=status)
                return {
                    "ok": True,
                    "state": turn["state"],
                    "completion_status": turn["completion_status"],
                }
            raise ValueError("action must be lock, review, or complete")
        except (TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 -- a control call must not
            # escape as an exception: the caller would see a tool crash
            # rather than a refused transition.
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def post_tool_call(self, **kwargs: Any) -> None:
        """Record bounded execution evidence and explicit worktree inventory."""

        raw_args = kwargs.get("args")
        if not isinstance(raw_args, dict):
            return
        task_id, session_id = self._binding(kwargs)
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=task_id,
            session_id=session_id,
        )
        if turn_id:
            self.store.record_tool_result(
                turn_id=turn_id,
                tool_call_id=str(kwargs.get("tool_call_id") or ""),
                tool_name=str(kwargs.get("tool_name") or ""),
                args=raw_args,
                status=str(kwargs.get("status") or ""),
                result=kwargs.get("result"),
            )
        if kwargs.get("status") != "ok" or kwargs.get("tool_name") != "terminal":
            return
        if str(raw_args.get("command") or "").strip() != "git worktree list --porcelain":
            return
        result = kwargs.get("result")
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except (TypeError, ValueError):
                parsed = {"output": result}
        elif isinstance(result, dict):
            parsed = result
        else:
            return
        output = parsed.get("output")
        if not isinstance(output, str):
            return
        paths = [
            line[len("worktree ") :]
            for line in output.splitlines()
            if line.startswith("worktree ") and line[len("worktree ") :].startswith("/")
        ]
        if not paths:
            return
        if turn_id:
            self.store.record_worktree_candidates(turn_id=turn_id, paths=paths)

    def post_llm_call(self, **kwargs: Any) -> None:
        try:
            self._close_at_audit_hook(**kwargs)
        except Exception:  # noqa: BLE001 -- a bookkeeping hook must not raise.
            return

    def _close_at_audit_hook(self, **kwargs: Any) -> None:
        task_id, session_id = self._binding(kwargs)
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=task_id,
            session_id=session_id,
        )
        if turn_id:
            turn = self.store.get_turn(turn_id)
            if turn is None or turn["completion_status"] is not None:
                return
            if (
                str(turn["task_class"]) == "artifact-change"
                and str(turn["state"]) in ARTIFACT_ENFORCED_STATES
            ):
                # Closure of an enforced artifact-change turn is explicit
                # only. This hook can fire per LLM call rather than per user
                # turn, so closing here would strand a multi-step contract
                # with every later mutation denied as "closed". Closeout keeps
                # its existing S1 behaviour.
                return
            status = "partial" if turn["task_class"] == "repository-closeout" else "success"
            self.store.complete_turn(turn_id=turn_id, status=status)

    def on_session_end(self, **kwargs: Any) -> None:
        """Close the bound turn when the session ends.

        Session end is one of the two closure triggers, alongside the
        explicit completion control. It is not the intermediate audit hook
        the closure norm excludes, so a clean exit closes the turn too: a
        turn left open keeps binding later calls and eventually refuses them
        on a wall-clock budget that started in a session already over.
        """

        clean_exit = bool(
            kwargs.get("completed")
            and not kwargs.get("failed")
            and not kwargs.get("interrupted")
        )
        try:
            task_id, session_id = self._binding(kwargs)
            turn_id = self.store.resolve_turn_id(
                turn_id=str(kwargs.get("turn_id") or ""),
                task_id=task_id,
                session_id=session_id,
            )
            if not turn_id:
                return
            if clean_exit:
                status = "success"
            elif kwargs.get("interrupted"):
                status = "interrupted"
            else:
                status = "failed"
            self.store.complete_turn(turn_id=turn_id, status=status)
        except Exception:  # noqa: BLE001 -- a bookkeeping hook must not raise.
            return

    def _binding(self, kwargs: dict[str, Any]) -> tuple[str, str]:
        """The (task, session) identifiers this hook call is bound by.

        Resolved once per hook invocation and threaded through every store
        call that invocation makes. Reading the host anchor again mid-hook
        would let a seed lookup and the admission that follows it disagree
        about which task is executing, which is the one way an in-force
        contract can stop covering its own call.

        The resolution is contract-aware: the store answers whether either
        candidate binding reaches a contract record, so an anchor naming a
        card this store knows nothing about cannot displace a payload
        identifier that carries one. The probe runs here, inside the single
        resolution, for the same reason the resolution is single -- a later
        second opinion is how the two halves come apart.

        Deliberately not applied to ``record_contract_seed``: that runs in
        the orchestrator, where the task id is the assigner's explicit key
        for the card being handed out, not the identity of a worker process.
        """

        session_id = str(kwargs.get("session_id") or "")
        return (
            resolve_task_binding(
                str(kwargs.get("task_id") or ""),
                has_contract=lambda candidate: self.store.has_contract_record(
                    task_id=candidate, session_id=session_id
                ),
            ),
            session_id,
        )

    @staticmethod
    def _turn_key(kwargs: dict[str, Any], *, task_id: str, session_id: str) -> str:
        """Identity of the turn being started.

        A task id alone is not a turn key: every message of the task would
        collapse into one row, so the first message's classification, wall
        clock, and budgets would stand for the whole task and no later turn
        would exist for the state machine to act on.

        The scope half of the key takes the already-resolved identifiers, so
        the turn is filed under the same task the contract is looked up by.
        """

        direct = str(kwargs.get("turn_id") or "")
        if direct:
            return direct
        scope = task_id or session_id
        if not scope:
            return ""
        digest = hashlib.sha256(
            str(kwargs.get("user_message") or "").encode("utf-8")
        ).hexdigest()[:16]
        return f"{scope}:{digest}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("target fields must be arrays of strings")
    return value


def _optional_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    return _string_list(value)


def json_result(value: dict[str, Any]) -> str:
    """Hermes tool handlers may safely return a normalized JSON string."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True)
