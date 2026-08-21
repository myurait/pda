# PDA autonomous improvement and owner approvals

This integration turns the `pda-improvement` Hermes Kanban tenant into a two-phase execution lane:

1. a deterministic 30-minute router assigns Ready cards to a fresh task-scoped worker of the `default` profile in task-specific Git worktrees;
2. the forced `pda-autonomous-improvement` skill limits the worker to implementation, focused tests, and a local task-branch commit;
3. the worker requests review with a structured `pda_approval` handoff;
4. the Dashboard `承認` tab verifies the handoff digest, exact non-symlink linked-worktree path, canonical Git common/worktree identities, exact `pda-auto/<task-id>` branch, base/diff, and clean real Git HEAD;
5. only the configured basic-auth owner session can approve or request changes and reopen the card for the displayed finalization contract.

The approval queue and its control-owned approval ledger are stored in the same Hermes Kanban DB. It does not create a second task database. Human-readable comments are notifications only and cannot authorize activation by themselves.

## Managed assets

- `dashboard/manifest.json`, `dashboard/dist/*`, `dashboard/plugin_api.py`: authenticated Hermes Dashboard plugin.
- `operations/improvement/pda_improvement_cycle.py`: deterministic WIP router; no model invocation on an empty queue.
- `profiles/pda/skills/pda-autonomous-improvement/SKILL.md`: force-loaded two-phase worker policy.
- `continuity/autonomous-improvement.json`: desired active configuration.
- `infra/systemd/pda-improvement-cycle.*`: 30-minute user timer.
- `operations/improvement/daily_reconciler_prompt.txt`: daily capture/specify/promote contract.
- `operations/improvement/install.py`: staged and approval-gated installer.

## Staged bootstrap

The bootstrap installs the approval UI and forced skills into the existing default profile, enables a no-op timer, sets `kanban.review_dispatch=false`, and restarts only the Dashboard. It deliberately writes the runtime cycle config with `enabled=false` and leaves the existing daily reconciler unchanged until approval. It does not create or modify another persona or `SOUL.md`.

```text
python operations/improvement/install.py --stage --repo /home/user/projects/pda-autonomous-improvement
```

A staged install is not activation. The router cannot assign a card while disabled.

## Approval-gated activation

The worker must first run the no-side-effect ledger check; a comment alone cannot authorize any finalization:

```text
python operations/improvement/install.py --check-approval \
  --task-id t_xxxxxxxx \
  --approval-id pa_xxxxxxxxxxxxxxxx \
  --digest <64-lowercase-hex>
```

Activation requires the same exact control-ledger record produced by the Dashboard approval API:

```text
python operations/improvement/install.py --activate \
  --repo /home/user/projects/pda \
  --task-id t_xxxxxxxx \
  --approval-id pa_xxxxxxxxxxxxxxxx \
  --digest <64-lowercase-hex>
```

The installer re-reads the shared Kanban DB and refuses activation unless configured owner identity, task/schema, approval ID, digest, latest review run, full approval contract, forced skill, canonical worktree/Git identity, base/diff, and clean Git HEAD all match. After stopping the staged timer it rechecks, claims the approval with an exclusive activation nonce, rechecks before enabling the timer and after the first service tick, and consumes that approval exactly once. While claimed, revocation and duplicate activation fail closed. It captures the prior daily-Cron prompt/skills/workdir in a mode-0600 rollback snapshot and applies the new Cron/runtime transactionally. A failed activation restores disabled runtime state and the prior Cron; it releases the claim only after a complete rollback, leaving a conflicted partial rollback locked for operator recovery.

The approved rollback is executable and does not require reconstructing the old Cron by hand:

```text
python operations/improvement/install.py --rollback-activation --repo /home/user/projects/pda
```

## Safety invariants

- Unassigned Triage capture never launches a worker.
- Stopped cards are ineligible.
- WIP is capped at two; only one new assignment occurs per tick.
- Assignment is the last routing write, after the exact worktree, branch, skill, and audit comment are durable.
- Existing non-matching worktree paths or branches fail closed; they are never reset, removed, or adopted heuristically.
- Approval requires the configured basic-auth owner identity (env-wins, config fallback), valid structured metadata, all verification outcomes passed, a clean non-symlink linked worktree, exact task-bound path, canonical Git common/worktree identities and `pda-auto/<task-id>` branch, matching full Git HEAD, base ancestry, and exact changed-files diff.
- Approval does not authorize any step or target absent from the displayed finalization contract.
- Drift requires a new commit, digest, and approval.
- Profile `SOUL.md` is not modified; policy is force-loaded per task.

## Verification

```text
env -u HERMES_DELEGATED_CHILD_CONTEXT PYTHONPATH=src python -m pytest -q
node --check integrations/hermes-pda-approvals/dashboard/dist/index.js
```

The environment-variable removal above is only for a known parent-session test-harness contamination after spawning a review subagent. Production workers and systemd units retain Hermes' delegated-child Kanban mutation guard.
