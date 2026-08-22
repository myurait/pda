---
name: task-scope-control
description: "Use for narrow tasks. Lock scope and stop expansion."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [scope-control, bounded-execution, verification, git, operations]
    related_skills: [pda-user-escalation, pda-delegation-routing]
---

# Task Scope Control

Use this skill before executing a narrow operational request, especially commit/push, status/report, restart, configuration, cleanup, migration closeout, or any request whose completion predicate is small and observable.

The goal is minimum sufficient completion. Do not turn confidence-improving work into new scope.

## Core rules

1. Permission is not scope. Standing permission to commit, push, restart, or deploy authorizes that side effect when relevant; it does not create a new objective or broaden the target set.
2. Confidence is not scope. Extra audits, broad tests, cleanup, reviews, and waits may improve confidence but are not automatically required.
3. Preserve user-owned and concurrent work. Never clean, reset, stash, merge, resolve, delete, or fold another worktree merely to make a narrow closeout look complete.
4. One-hop prerequisites only. A direct prerequisite may be allowed; repairing that prerequisite is a new task unless the request explicitly includes repair.
5. Verification must match the promise. Verify the requested outcome, not global repository or system health.
6. Completion closes execution. Once the acceptance predicate is met, stop calling tools and report.

## Build a scope contract before acting

For every non-trivial request, fix these fields internally before the first mutating tool call:

- `objective`: one observable outcome;
- `targets`: exact repositories, worktrees, branches, files, services, accounts, or destinations;
- `required_actions`: actions that directly create the outcome;
- `prerequisites`: one-hop necessities only;
- `verification`: evidence that proves the stated outcome;
- `non_goals`: tempting adjacent work that must not be started;
- `budget`: wall time, tool calls, retries, background processes, and delegates;
- `completion`: success, partial, blocked, and failed conditions.

If target discovery is necessary, perform one bounded read-only inventory, then freeze the target set. Do not let discovery become free exploration.

## Action admission

Classify every proposed action as exactly one of:

- `required`: directly produces the requested outcome;
- `prerequisite`: immediately necessary for one required action;
- `verification`: directly proves one completion condition;
- `expansion`: adds a target, artifact, repair, quality step, investigation, wait, or side effect.

Proceed with the first three only when they remain inside the fixed target and budget. Do not execute an expansion merely because it is useful.

When an out-of-scope action appears:

1. Ask whether the original completion predicate is impossible without it.
2. Look for a narrower in-scope alternative.
3. If optional, skip it and record it only when owner-relevant.
4. If necessary but unauthorized or materially broader, stop that target and report one blocker or one decision request.
5. Never self-authorize by rewriting the objective more broadly.

## Narrow task defaults

For narrow closeout and operational requests:

- no subagent or external coding-agent delegation;
- no background process unless the request explicitly requires one;
- no broad test suite unless named by the user or automatically required by the direct action;
- no unrelated process polling or cutover waiting;
- no new branches, worktrees, refactors, or cleanup;
- no repeated alternative-tool attempts after the same scope denial;
- batch independent read-only checks, but do not hide unrelated work inside a giant script.

Use a short wall-time budget appropriate to the action. If a task expected to take minutes approaches 15 minutes, re-check the contract before doing anything else. Time already spent is not justification for broader recovery work.

## Repository closeout profile

Use this profile for requests such as “commit this,” “commit and push,” or “save any uncommitted requested-work artifacts.”

### Default target

The default is the worktree and artifacts owned by the current requested task. A standing preference to commit meaningful results does not authorize a global worktree audit.

A repository-wide or all-worktree inventory is in scope only when the user explicitly asks about all uncommitted resources. Even then, inventory and closeout are allowed; content repair is not.

### Allowed sequence

1. Read the relevant worktree status and intended branch/remote.
2. Inspect candidate filenames and the candidate diff only enough to establish ownership, coherence, and secret safety.
3. Run `git diff --check` or an equivalent targeted check.
4. Stage only the intended existing content.
5. Commit with a concise task-aligned message.
6. Push only when requested or already included in the standing task contract.
7. Read back local HEAD and the intended remote ref.
8. Stop.

Required commit hooks may run as part of `git commit`. A failing hook is a blocker for a closeout-only task; it is not permission to repair tests, reformat unrelated files, or launch a full debugging mission.

### Forbidden without explicit repair scope

- editing file contents;
- resolving merge conflicts or an unmerged index;
- running a broad test/lint/review campaign;
- creating, deleting, resetting, stashing, rebasing, or merging branches/worktrees;
- waiting for an unrelated deployment or background process;
- delegating the closeout to another agent;
- deploying, restarting, or cutting over another system.

If some targets are commit-ready and one is conflicted, close the commit-ready targets if safe and report the conflicted target as blocked. Do not manufacture a clean result.

## Verification discipline

Map every check to a completion claim:

- “committed” → a commit contains the intended staged changes;
- “pushed” → the intended remote ref resolves to the local commit;
- “service restarted” → the requested service has the new process state;
- “configuration changed” → the effective runtime reads the intended value;
- “fixed” → the reproducer and the smallest relevant regression check pass.

Do not substitute stronger but unrelated evidence. “All tests pass” does not prove the correct branch was pushed; “all worktrees clean” is not required to prove one requested artifact was saved.

## Stop and report

Use `pda-user-escalation` for the owner-facing message when work is non-trivial.

A narrow completion report should contain only:

- the requested outcome now established;
- a blocker or remaining risk only if it changes what the owner can rely on;
- required owner action, explicitly `none` when none;
- a commit/ref/path only when it is useful audit evidence.

Do not report labor volume as value. Do not end a completed request with an invitation to expand the task.

## Verification checklist

Before finishing, confirm:

- Did every action map to required, one-hop prerequisite, or declared verification?
- Did the target set remain fixed after discovery?
- Did any optional audit, repair, test, review, or wait slip in?
- Were concurrent worktrees preserved?
- Is the completion evidence specific to the promise?
- Did tool use stop once completion was established?

For the Hermes hook-based enforcement architecture and incident replay criteria behind this policy, read `references/hermes-scope-admission.md`.

## Pitfalls

- Treating “do it properly” as permission for unlimited hardening.
- Treating a discovered defect as an instruction to fix it.
- Running a full suite because targeted verification feels insufficient.
- Auditing every branch because one commit target was ambiguous.
- Waiting on a separate operation before reporting an already-complete closeout.
- Using a second agent to validate a trivial deterministic action.
- Confusing safety approval, task scope, and completion evidence; they are separate gates.
