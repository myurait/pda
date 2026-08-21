# PDA autonomous improvement and owner approvals

This integration turns the `pda-improvement` Hermes Kanban tenant into a two-phase execution lane:

1. a deterministic 30-minute router assigns Ready cards to a fresh task-scoped worker of the `default` profile in task-specific Git worktrees;
2. the forced `pda-autonomous-improvement` skill limits the worker to implementation, focused tests, and a local task-branch commit;
3. the worker requests review with a structured `pda_approval` handoff;
4. the Dashboard `承認` tab verifies the handoff digest and the clean real Git HEAD;
5. only owner approval reopens the card for the displayed finalization contract.

The approval queue is derived from Hermes Kanban `review` cards. It does not create a second task database.

## Managed assets

- `dashboard/manifest.json`, `dashboard/dist/*`, `dashboard/plugin_api.py`: authenticated Hermes Dashboard plugin.
- `operations/improvement/pda_improvement_cycle.py`: deterministic WIP router; no model invocation on an empty queue.
- `profiles/pda/skills/pda-autonomous-improvement/SKILL.md`: force-loaded two-phase worker policy.
- `continuity/autonomous-improvement.json`: desired active configuration.
- `infra/systemd/pda-improvement-cycle.*`: 30-minute user timer.
- `operations/improvement/daily_reconciler_prompt.txt`: daily capture/specify/promote contract.
- `operations/improvement/install.py`: staged and approval-gated installer.

## Staged bootstrap

The bootstrap installs the approval UI and forced skills into the existing default profile, enables a no-op timer, sets `kanban.review_dispatch=false`, and restarts only the Dashboard. It deliberately writes the runtime cycle config with `enabled=false`. It does not create or modify another persona or `SOUL.md`.

```text
python operations/improvement/install.py --stage --repo /home/user/projects/pda-autonomous-improvement
```

A staged install is not activation. The router cannot assign a card while disabled.

## Approval-gated activation

Activation requires the exact control-owned marker produced by the Dashboard approval API:

```text
python operations/improvement/install.py --activate \
  --repo /home/user/projects/pda \
  --task-id t_xxxxxxxx \
  --approval-id pa_xxxxxxxxxxxxxxxx \
  --digest <64-lowercase-hex>
```

The installer re-reads the shared Kanban DB and refuses activation unless task, author, schema, approval ID, and digest match. It then writes `enabled=true`, updates the existing daily reconciler, and runs one deterministic routing tick.

## Safety invariants

- Unassigned Triage capture never launches a worker.
- Stopped cards are ineligible.
- WIP is capped at two; only one new assignment occurs per tick.
- Assignment is the last routing write, after the exact worktree, branch, skill, and audit comment are durable.
- Existing non-matching worktree paths or branches fail closed; they are never reset, removed, or adopted heuristically.
- Approval requires valid structured metadata, all verification outcomes passed, a clean worktree, matching full Git HEAD, and base ancestry.
- Approval does not authorize any step or target absent from the displayed finalization contract.
- Drift requires a new commit, digest, and approval.
- Profile `SOUL.md` is not modified; policy is force-loaded per task.

## Verification

```text
env -u HERMES_DELEGATED_CHILD_CONTEXT PYTHONPATH=src python -m pytest -q
node --check integrations/hermes-pda-approvals/dashboard/dist/index.js
```

The environment-variable removal above is only for a known parent-session test-harness contamination after spawning a review subagent. Production workers and systemd units retain Hermes' delegated-child Kanban mutation guard.
