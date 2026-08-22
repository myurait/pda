---
name: pda-autonomous-improvement
description: "Use for PDA Kanban self-improvement implementation and approval handoff."
version: 1.1.0
author: PDA
license: MIT
metadata:
  hermes:
    tags: [pda, kanban, autonomy, approval, worktree]
    related_skills: [test-driven-development, task-scope-control, pda-user-escalation]
---

# PDA Autonomous Improvement

## Contract

A PDA improvement card is executed in two separate phases. The card, Git worktree, Kanban run history, and the plugin-owned approval ledger in the shared Kanban DB are the durable control plane. Approval comments are worker notifications, not authority. Never treat user intent to improve the PDA as blanket approval for final cutover.

## Phase 1: implementation and verification

Use this phase unless a latest `pda-owner-approval` notification provides task ID, approval ID, and digest and the no-side-effect ledger check documented in Phase 2 succeeds. A comment or matching-looking JSON alone never changes phase.

1. Call `kanban_show` first and operate only on the current card.
2. Inspect the assigned worktree and preserve every other branch, worktree, and uncommitted change. Never reset, stash, or repair another thread.
3. Convert the stated outcome into bounded acceptance criteria yourself. Record them on the card; do not ask the owner about reversible implementation details.
4. Implement directly in the assigned worktree using focused TDD and bounded checks. A reasoning delegate is optional, never the execution owner. After two failed or non-progressing delegate attempts, continue directly; an exhausted `delegate_task` allowance is not a reason to stop the card.
5. Commit only the card's files on its task branch. Do not merge, push, deploy, restart services, alter runtime/profile state outside the worktree, send externally, change credentials, delete durable data, or perform an irreversible operation.
6. Build a `pda_approval` metadata object with:
   - `schema_version: 1` and the exact `task_id`;
   - owner outcome, impact, risk class, base SHA, head SHA, changed files;
   - the exact absolute non-symlink linked-worktree root, canonical Git common-dir/worktree git-dir identities, and exact `pda-auto/<task_id>` branch;
   - every verification command with `outcome=passed` and a short result;
   - residual risks;
   - an `independent_verification` report (schema: `schemas/verification-report-v1.schema.json`) produced by a verifier that is not the implementer — self-verification is never approvable (governance ADR D2; applies to every change per the 2026-08-22 owner decision). Interim honesty note: until the M2 verifier stage exists, enforcement checks label consistency (verifier ≠ implementer ≠ task assignee, `verified_head_sha` bound to the real Git HEAD); it does not yet prove a separate principal executed the verification;
   - an exact finalization contract: kind, targets, ordered steps, rollback.
7. Call `kanban_request_review` with an owner-readable summary and the metadata. Never call `kanban_complete` in Phase 1.

Governance surfaces are never a worker deliverable: an approval whose changed files touch the charter, the governance ADR, roadmap decisions, gate/approval/guard code, or the suspension policy is refused mechanically (ADR D3). Such changes reach the repository only as owner-committed changes.

Allowed risk classes are `local-reversible`, `service-restart`, `external-visible`, and `security-sensitive`. Allowed finalization kinds are `merge-only`, `merge-and-restart`, `apply-artifacts`, and `no-runtime-change`. Secret values must never enter summaries, metadata, comments, commits, or logs.

## Phase 2: approved finalization

Proceed only after extracting `task_id`, `approval_id`, and `digest` from the latest approval notification and running this no-side-effect check from the task worktree:

`python operations/improvement/install.py --check-approval --task-id <task> --approval-id <approval> --digest <digest>`

The command must return `ok=true` and `mode=checked`. It independently requires a non-revoked owner-identity row in the plugin-owned approval ledger and proves that the full approval contract, task ID, digest, latest review run ID, base/head ancestry, exact changed-files diff, canonical non-symlink linked-worktree root and Git identities, exact `pda-auto/<task_id>` branch, finalizer profile, forced skill, task state, and clean Git worktree still match. A generic comment cannot satisfy this check.

Then verify that every intended side effect is explicitly included in the approved finalization steps and targets.

Then:

1. Execute only the approved finalization contract. Do not add an extra cleanup, repair, audit, dependency upgrade, or unrelated deployment. The ledger check above must occur before the first merge, deployment, restart, external call, or write outside the task worktree.
2. If the approved artifact has drifted, a new change becomes necessary, any target differs, or claim recovery is required, stop finalization. Never stretch or silently clear the old approval. A stale claim is operator-recoverable only after runtime is disabled and the 15-minute recovery threshold has passed.
3. Verify the real target after finalization, including service health or UI behavior when included in the approved scope.
4. Call `kanban_complete` with outcome, applied commit/artifact, checks actually run, rollback, and residual risk.

A rejection comment authored `pda-owner-changes` returns the task to Phase 1. Incorporate the stated change, create a new commit and approval digest, and request review again.

## Failure handling

- Heartbeat during work longer than a few minutes.
- Change strategy after two identical failures; do not loop.
- Resolve local, reversible blockers directly.
- Use `kanban_block` only for a real missing capability, credential, unreachable required system, information boundary, or contradiction that cannot be safely resolved.
- Do not ask the owner mid-implementation. The normal owner interaction is the final approval list.
