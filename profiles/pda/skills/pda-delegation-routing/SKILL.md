---
name: pda-delegation-routing
description: "Use when decomposing PDA work across Sol, Luna, or Fable."
version: 0.2.0
author: PDA
license: MIT
metadata:
  hermes:
    tags: [pda, delegation, routing, codex, claude-code, fable]
    related_skills: [coding-agent-orchestration, claude-code, codex]
---

# PDA Delegation Routing

## Purpose

Use this skill before spawning a subagent, invoking Claude Code, or turning one user request into parallel work. The canonical design is `docs/design/operational-delegation-routing.md` in the PDA repository.

The goal is not maximum fan-out. The goal is to minimize primary-model pressure and owner cognitive load while preserving correctness, privacy, and integration responsibility.

## Routing order

Apply these gates in order:

1. Can a deterministic tool or script finish it? If yes, do not delegate.
2. Does it cross an information/account boundary? If not allowed, do not route there.
3. Does it require an owner decision or external authorization? Keep it with the primary and escalate once.
4. Must it survive the current process/session? Use Kanban or a durable worker, not `delegate_task`.
5. Is it independent, bounded, and answerable without user interaction? Use Luna.
6. Is the bottleneck ambiguity, owner-perspective interpretation, architecture, or high-level writing? Use Fable.
7. Is it long-running development beside the Mac checkout/toolchain? Use Claude Code as a durable task.
8. Keep final integration, verification, and user communication with the primary PDA/Sol.

## Required decomposition

Before delegation, write:

- one objective;
- observable acceptance criteria;
- explicit non-goals;
- source-labelled facts, decisions, confirmed/inferred preferences, and assumptions;
- information class;
- lane, model, host, and durability;
- read/write/network permissions and owner gate;
- target account class, authorization status, control-owned authorization reference, and selected-context reference;
- billing mode, existing-credit-only flag, purchase/auto-reload/unlimited/settings-mutation denials, and control-owned balance/spend-cap evidence;
- iteration/time/concurrency/retry budget;
- expected artifacts and verification.

Use `schemas/delegation-task-v1.schema.json` for nontrivial handoffs.

`permissions.network` governs tools and task-level external access, not the fixed provider transport required to call the selected model.

Do not split tasks that write the same artifact. Do not parallelize a task when a later subtask cannot be defined until an earlier result exists.

## Luna lane

Use Hermes `delegate_task` only for short, reasoning-heavy subtasks whose result the parent needs in the current turn.

Defaults:

- model: `gpt-5.6-luna`;
- one child normally, two only for disjoint work;
- flat delegation only;
- read-only by default;
- no user interaction;
- no production side effects;
- one reframing after failure, never blind repeated retry.

The executable task contract must enforce no more than 32 model iterations, 1200 seconds, concurrency 2, and one retry. Parent runtime guards separately enforce two simultaneous children and four cumulative child spawns per turn.

Do not use Luna for a single tool call, mechanical loops, long missions, or shared-worktree editing.

## Fable lane

Use `claude-fable-5` when ambiguity and user-aligned perspective are the main difficulty.

Provide confirmed and inferred preferences separately. Ask for:

- owner-view interpretation;
- recommendation and reason;
- tensions/tradeoffs;
- uncertainties;
- one owner-only decision if needed;
- what must not be inferred;
- a concise handoff to the primary.

Require the typed `perspective_result` in `schemas/delegation-result-v1.schema.json`; a generic success summary is not a valid Fable result.

Fable is an advisor, not the owner. It cannot amend the charter, fabricate approval, impersonate the user externally, or turn inferred preferences into confirmed ones.

Run the perspective lane on the PDA host with the PDA-local Claude Code account. Use one verified fixed-wrapper `claude -p` call with no tools, structured output, no session persistence, and bounded turns/time. The development Mac is a separate durable development lane and must not receive or silently inherit a perspective task.

Use an exact minimized-context selection even though personal context remains within the PDA-local principal. Do not send the raw parent transcript, full memory, or full PKB. Verify process exit, `is_error`, API status, terminal reason, exact `modelUsage`, and account route; a result object with `subtype=success` is not success when `is_error=true`.

If Fable requires inaccessible usage credits, fail closed and return a blocked result. The owner's instruction authorizes consuming already-available PDA-local credits for validation; it does not authorize purchasing credits, enabling uncapped billing, or falling back to the development-PC account.

## Durable Claude Code lane

This lane is separate from Fable perspective delegation. Use a durable board card and task-ID-specific worktree. The Mac worker must:

- pull/claim tasks deterministically;
- run beside the checkout as the correct macOS user;
- persist job ID, session UUID, effective model, result, and outbox before delivery;
- use task ID for idempotency;
- reconcile the outbox before rerun;
- return Git/artifact/test evidence;
- leave an offline task queued rather than falling back to the wrong principal.

## Verification and integration

Treat every child result as self-report until verified.

Verify:

- requested versus effective model;
- expected account class versus typed `principal_attestation`, including read-back of the referenced auth/model evidence;
- typed runtime outcome: process exit, terminal result, `is_error`, API status, terminal reason, exact models used, and raw evidence URI;
- billing policy and resolvable existing-balance/finite-spend-cap evidence;
- actual artifact handle and contents;
- Git diff/worktree ownership;
- tests/checks actually run;
- unresolved risk and owner decision;
- result schema for structured handoffs.

A `succeeded` result is valid only when every verification outcome is `passed`. Unrun or failed verification makes the result partial/failed/blocked, never succeeded.

The primary resolves contradictions and sends one owner-level result. Do not dump parallel agent transcripts into the final response.

## Hard boundaries

- No secret text in model capsules.
- PDA-local Fable gets only the selected minimized context; never the whole conversation or memory store.
- A Fable perspective task never falls back to the development-PC account.
- No overlapping write scope across concurrent runs.
- No nested subagent swarms.
- No child success claim without parent read-back.
- No model polling of an empty durable queue.
- While `org_level_disabled` or billing evidence is unresolved, keep Fable blocked; never mutate Settings or organization billing from the worker.
- No Fable retry, new credit purchase, auto-reload, unlimited spend, or billing-policy change after a credit gate without owner authorization.
