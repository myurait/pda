---
name: pda-autonomous-improvement
description: "Use for PDA Kanban self-improvement implementation and approval handoff."
version: 1.0.0
author: PDA
license: MIT
metadata:
  hermes:
    tags: [pda, kanban, autonomy, approval, worktree]
    related_skills: [test-driven-development, task-scope-control, pda-user-escalation]
---

# PDA Autonomous Improvement

## Contract

A PDA improvement card is executed in two separate phases. The card, Git worktree, Kanban run history, and control-owned approval comment are the durable control plane. Never treat user intent to improve the PDA as blanket approval for final cutover.

## Phase 1: implementation and verification

Use this phase unless the current card contains a valid latest comment authored exactly `pda-owner-approval` whose JSON marker has `schema=PDA_OWNER_APPROVAL_V1` and matches the latest review handoff digest and the clean current Git HEAD.

1. Call `kanban_show` first and operate only on the current card.
2. Inspect the assigned worktree and preserve every other branch, worktree, and uncommitted change. Never reset, stash, or repair another thread.
3. Convert the stated outcome into bounded acceptance criteria yourself. Record them on the card; do not ask the owner about reversible implementation details.
4. Implement directly in the assigned worktree using focused TDD and bounded checks. A reasoning delegate is optional, never the execution owner. After two failed or non-progressing delegate attempts, continue directly; an exhausted `delegate_task` allowance is not a reason to stop the card.
5. Commit only the card's files on its task branch. Do not merge, push, deploy, restart services, alter runtime/profile state outside the worktree, send externally, change credentials, delete durable data, or perform an irreversible operation.
6. Build a `pda_approval` metadata object with:
   - `schema_version: 1` and the exact `task_id`;
   - owner outcome, impact, risk class, base SHA, head SHA, changed files;
   - every verification command with `outcome=passed` and a short result;
   - residual risks;
   - an exact finalization contract: kind, targets, ordered steps, rollback.
7. Call `kanban_request_review` with an owner-readable summary and the metadata. Never call `kanban_complete` in Phase 1.

Allowed risk classes are `local-reversible`, `service-restart`, `external-visible`, and `security-sensitive`. Allowed finalization kinds are `merge-only`, `merge-and-restart`, `apply-artifacts`, and `no-runtime-change`. Secret values must never enter summaries, metadata, comments, commits, or logs.

## Phase 2: approved finalization

Proceed only when all of these are true:

- the approval comment author is exactly `pda-owner-approval`;
- its JSON marker schema is `PDA_OWNER_APPROVAL_V1`;
- task ID, approval digest, review run ID, and head SHA match the latest review request;
- the task worktree is clean and still at the approved head;
- every intended side effect is explicitly included in the approved finalization steps and targets.

Then:

1. Execute only the approved finalization contract. Do not add an extra cleanup, repair, audit, dependency upgrade, or unrelated deployment.
2. If the approved artifact has drifted, a new change becomes necessary, or any target differs, stop finalization and return to review with a new digest. Never stretch the old approval.
3. Verify the real target after finalization, including service health or UI behavior when included in the approved scope.
4. Call `kanban_complete` with outcome, applied commit/artifact, checks actually run, rollback, and residual risk.

A rejection comment authored `pda-owner-changes` returns the task to Phase 1. Incorporate the stated change, create a new commit and approval digest, and request review again.

## Failure handling

- Heartbeat during work longer than a few minutes.
- Change strategy after two identical failures; do not loop.
- Resolve local, reversible blockers directly.
- Use `kanban_block` only for a real missing capability, credential, unreachable required system, information boundary, or contradiction that cannot be safely resolved.
- Do not ask the owner mid-implementation. The normal owner interaction is the final approval list.
