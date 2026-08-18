"""Hermes-facing runtime adapter for the deterministic scope gate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any

try:  # Hermes loads the plugin as a namespaced package.
    from .scope_gate import GateStore, default_state_path
except ImportError:  # Direct unit-test/script import fallback.
    from scope_gate import GateStore, default_state_path


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


class ScopeGatePluginRuntime:
    def __init__(self, state_path: str | Path | None = None) -> None:
        if state_path is None:
            try:
                get_hermes_home = import_module("hermes_constants").get_hermes_home
                state_path = default_state_path(get_hermes_home())
            except (AttributeError, ImportError):
                state_path = default_state_path()
        self.store = GateStore(state_path)

    def pre_llm_call(self, **kwargs: Any) -> dict[str, str] | None:
        turn_id = self._turn_key(kwargs)
        if not turn_id:
            return None
        intent = self.store.start_turn(
            turn_id=turn_id,
            session_id=str(kwargs.get("session_id") or ""),
            task_id=str(kwargs.get("task_id") or ""),
            user_message=str(kwargs.get("user_message") or ""),
        )
        if intent.task_class != "repository-closeout":
            return None
        return {"context": _CLOSEOUT_CONTEXT}

    def pre_tool_call(self, **kwargs: Any) -> dict[str, str] | None:
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=str(kwargs.get("task_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
        )
        if not turn_id:
            return None
        raw_args = kwargs.get("args")
        args = raw_args if isinstance(raw_args, dict) else {}
        decision = self.store.admit_tool(
            turn_id=turn_id,
            tool_call_id=str(kwargs.get("tool_call_id") or ""),
            tool_name=str(kwargs.get("tool_name") or ""),
            args=args,
        )
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
            turn_id = self.store.resolve_turn_id(
                turn_id=str(kwargs.get("turn_id") or ""),
                task_id=str(kwargs.get("task_id") or ""),
                session_id=str(kwargs.get("session_id") or ""),
            )
            if not turn_id:
                return next_call(args)
            decision = self.store.admit_tool(
                turn_id=turn_id,
                tool_call_id=str(kwargs.get("tool_call_id") or ""),
                tool_name=tool_name,
                args=args,
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
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=str(kwargs.get("task_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
        )
        if not turn_id:
            return {"ok": False, "error": "No active scope turn is bound to this call."}
        action = str(params.get("action") or "")
        try:
            if action == "lock":
                targets = params.get("targets")
                if not isinstance(targets, dict):
                    raise ValueError("lock requires targets")
                contract = self.store.lock_turn(
                    turn_id=turn_id,
                    repositories=_string_list(targets.get("repositories")),
                    worktrees=_string_list(targets.get("worktrees")),
                    branches=_string_list(targets.get("branches")),
                )
                return {"ok": True, "contract": contract}
            if action == "review":
                return {
                    "ok": False,
                    "error": "repository-closeout has zero expansion budget; report the blocker",
                }
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

    def post_tool_call(self, **kwargs: Any) -> None:
        """Record bounded execution evidence and explicit worktree inventory."""

        raw_args = kwargs.get("args")
        if not isinstance(raw_args, dict):
            return
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=str(kwargs.get("task_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
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
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=str(kwargs.get("task_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
        )
        if turn_id:
            turn = self.store.get_turn(turn_id)
            if turn is None or turn["completion_status"] is not None:
                return
            status = "partial" if turn["task_class"] == "repository-closeout" else "success"
            self.store.complete_turn(turn_id=turn_id, status=status)

    def on_session_end(self, **kwargs: Any) -> None:
        if kwargs.get("completed") and not kwargs.get("failed") and not kwargs.get("interrupted"):
            return
        turn_id = self.store.resolve_turn_id(
            turn_id=str(kwargs.get("turn_id") or ""),
            task_id=str(kwargs.get("task_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
        )
        if turn_id:
            status = "interrupted" if kwargs.get("interrupted") else "failed"
            self.store.complete_turn(turn_id=turn_id, status=status)

    @staticmethod
    def _turn_key(kwargs: dict[str, Any]) -> str:
        direct = str(kwargs.get("turn_id") or kwargs.get("task_id") or "")
        if direct:
            return direct
        session_id = str(kwargs.get("session_id") or "")
        if not session_id:
            return ""
        digest = hashlib.sha256(
            str(kwargs.get("user_message") or "").encode("utf-8")
        ).hexdigest()[:16]
        return f"{session_id}:{digest}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("target fields must be arrays of strings")
    return value


def json_result(value: dict[str, Any]) -> str:
    """Hermes tool handlers may safely return a normalized JSON string."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True)
