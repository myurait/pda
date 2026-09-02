# PDA scope control v2

This directory is the canonical runtime implementation for
`docs/design/task-scope-admission-gate.md` and
`docs/design/process-degeneration-monitor.md`.

Version 0.2 replaces natural-language task classification with a three-phase,
source-bound loop:

1. the executor infers a ScopeFrame and a plain work plan from the current
   authenticated instruction;
2. a fresh, no-tools Terra session independently reviews that frame, plan,
   risk, and deterministic containment before mutation;
3. the executor and, when Terra requires it, another fresh Terra session audit
   observed effects before the scope contract can complete.

Regexes, keyword lists, task classes, and deterministic parsing do not infer
instruction meaning or risk in the v2 runtime. Deterministic code handles only
provenance, record shape, assignment ceilings, target/effect containment,
budgets, stale arguments, completion state, and telemetry.

## Runtime components

- `__init__.py` registers one `scope_gate` tool, a byte-stable policy section,
  the Hermes lifecycle hooks, and the post-hook execution recheck.
- `plugin_runtime_v2.py` binds each Hermes turn to the current instruction
  digest, invokes fresh safe-mode Terra sessions (`hermes -z … --safe-mode -t todo`,
  the smallest valid toolset), observes tool effects, and
  adapts the v2 store to Hermes.
- `scope_v2.py` persists ScopeFrames, reviewed plans, deterministic
  containment, observed effects, and final audit state. It contains no
  natural-language classifier.
- `process_monitor.py` is the generic deterministic monitor for registered
  binary decision processes.
- `pda-scope-gate` is both the fail-closed out-of-process tool validator and the
  process-monitor reconcile/status CLI.
- `install.py` atomically installs the plugin symlink, shell hook, and hourly
  monitor timer while preserving concurrent configuration.
- `scope_gate.py` and `plugin_runtime.py` are retained only for v1 state/seed
  migration and rollback of already-running turns. New `pre_llm_call` traffic
  does not invoke their classifier.

State is profile-scoped at
`$HERMES_HOME/plugin-data/pda-scope-gate/scope-gate.db`. Raw instructions are
held only in the live plugin process for the current turn; the database stores
their SHA-256 digest, reviewed structured data, effect evidence digests, and
monitor events. Raw prompts, tool output, and secrets are not copied into the
scope or monitor tables.

## Scope lifecycle

Read-only work is admitted without a Terra call. A no-effect response is closed
at Hermes' final-response `post_llm_call` hook and emits one
`final_scope_conformant=true` decision.

Before the first mutation, the agent calls:

1. `scope_gate(action=review, scope_frame=..., plan=..., containment=...)`;
2. `scope_gate(action=lock)` after a `pass` result;
3. only tools and targets admitted by the reviewed containment;
4. `scope_gate(action=complete, observed_effects=...,
   final_scope_conformant=..., completion_summary=...)` before claiming
   completion.

If the work diverges from the reviewed frame, the agent returns to the current
instruction and calls `review` again; re-review is allowed from `locked` and
`audit-blocked`. The previous evaluation is kept as superseded history, the
reviewer receives the effects observed so far, and
`additional_assurance_required` is sticky: once true it cannot be lowered by a
later re-review. `lock` refuses a turn that requires an independent audit when
no audit path exists, so that condition stops before any effect.

Board annotations (`kanban_heartbeat`, `kanban_comment`, `kanban_block`,
`kanban_unblock`, `kanban_show`, `kanban_list`, `kanban_attachments`) and
`delegate_task` are control actions admitted in every state. A delegated child
session is bound to the parent's current turn at `pre_llm_call`
(`parent_session_id`) and never opens a turn of its own, because its "user
message" was authored by the parent model. Terminal board transitions
(`kanban_complete`, `kanban_request_review`) pass only after `complete`
succeeded, or when the turn produced no effect.

Review timeout, process failure, invalid JSON, `revise`, or `block` leaves
mutation closed. An assignment seed from the autonomous improvement router is a
hard ceiling: the Terra-reviewed containment may narrow it but never widen it.
The execution middleware and the out-of-process shell hook both re-evaluate the
same final tool arguments; a post-hook rewrite is rejected.

The post-tool hook records effects independently of the executor's completion
payload. Final audit uses the union, preferring the observed record for the same
kind and target. When pre-work Terra sets
`additional_assurance_required=true`, `complete` launches a separate fresh
Terra audit and refuses closure on a finding, timeout, process failure, or
invalid output.

Hermes v0.20.2 has no generic blocking `pre_finalize` hook. Therefore v2 does
not claim it can suppress arbitrary response text. It does block state-changing
tools until review/lock and refuses scope-contract completion without the final
audit. A response emitted without explicit completion creates a due final-audit
event; the monitor surfaces it as `missing-decision`.

## Deterministic containment

The reviewed containment carries absolute worktrees, repository-relative write
and test patterns, a finite effect-kind set, optional exact commands, service
units, remote refs, verification templates, and a bounded tool count.

The runtime admits:

- read/search/control tools before and after lock;
- file writes only inside reviewed worktrees and path patterns;
- explicit Git stage/commit/push forms only when their effect and exact targets
  were reviewed;
- exact service units only when service reload was reviewed;
- an exact command only when both the command and the `process-manage` effect
  were reviewed;
- tools whose effect is fixed by the tool name only when that effect kind was
  reviewed: `memory` → `memory-write`, `cronjob` → `schedule-write`,
  `skill_manage` → `skill-write`, `kanban_create` / `kanban_link` /
  `kanban_attach*` / `kanban_request_changes` → `board-write`,
  `execute_code` → `code-exec`, `process` / `close_terminal` / `setup_mcp` →
  `process-manage`, browser interaction, messaging, Home Assistant calls, and
  media generation → `external-send`.

Unknown effectful tools, compound shell syntax, target drift, history rewrite,
hook bypass, and effect kinds without a deterministic mapping fail closed.

## Process-degeneration monitor

The registry initially contains:

- `scope.prework.additional-assurance-required`;
- `scope.final.final-scope-conformant`.

Each monitor uses the same policy:

- rolling window: 72 hours;
- minimum valid decisions: 10;
- alert threshold: one boolean value is at least 95% of valid decisions.

`N < 10` never starts a degeneration episode, even at 100%. `N >= 10` uses the
unrounded integer ratio. The monitor supports arbitrary additional registered
binary processes without per-process branches.

Expected events are joined one-to-one to JSON booleans. Missing, late, invalid,
duplicate, conflicting, orphaned, and unavailable data are not coerced or
silently discarded; they create separate telemetry-failure episodes. A
false-to-true threshold transition creates one stable episode and one durable
outbox key. Re-evaluation updates the same task, recovery closes the episode
state without auto-closing the task, and recurrence creates a new generation.

The hourly `pda-process-monitor.timer` reconciles every registry entry and
delivers pending outbox rows to the default board, tenant `pda-improvement`, as
unassigned Triage tasks. Kanban idempotency keys prevent duplicate cards; a
changed payload for the same episode becomes an idempotent card comment.
Delivery failure is stored in `process_monitor_health` and
`owner_alert_outbox`, emitted as `pda.process-monitor.health/v1` to the system
journal, and exits non-zero. It never changes the original verdict, work,
approval, or finalization.

## Install and activate

From the canonical checkout:

```text
~/.hermes/hermes-agent/venv/bin/python integrations/hermes-scope-gate/install.py
systemctl --user daemon-reload
systemctl --user enable --now pda-process-monitor.timer
```

Run the installer with the Hermes venv interpreter: the monitor unit embeds that
interpreter, and Kanban delivery imports `hermes_cli`, which system Python cannot.
The installer itself does not manipulate a running process. A Hermes process
must be reloaded after changing the active source. Verify the installed paths:

```text
hermes plugins doctor integrations/hermes-scope-gate --ci
hermes hooks doctor
integrations/hermes-scope-gate/pda-scope-gate doctor
integrations/hermes-scope-gate/pda-scope-gate monitor-status
```

Use `monitor-reconcile --no-delivery` for isolated or pre-cutover evaluation;
it persists monitor state/outbox but never touches Kanban.

## Tests

```text
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  integrations/hermes-scope-gate/tests
```

The focused suite covers the 9/10 sample boundary, inclusive 95% threshold in
both directions, window expiry and recurrence, persistence after reopen,
duplicate/conflicting/missing events, unknown monitor attribution, fresh Terra
adapter behavior, reviewer and auditor fail-closed paths, assignment-seed
narrowing, observed effects, shell-hook revalidation, transactional install and
rollback, and a real Hermes plugin-dispatch subprocess against an isolated
`HERMES_HOME`. It also fixes the owner's acceptance checks: a new explicit
instruction is not capped by a previous report-only turn, tool-result text
cannot replace the bound instruction, re-review keeps the assurance flag, an
effect outside the re-reviewed containment blocks completion, a required audit
without an audit path stops at lock, board annotations and delegation stay
admitted, and the shell hook never routes into the v1 classifier.

## Rollback

The active plugin is a symlink to the tracked source. Roll back with a normal
Git revert to the prior main content, run the installer again, disable the
monitor timer if reverting before v2, and reload Hermes. v2 adds SQLite tables
without dropping or rewriting v1 tables, so the legacy runtime can ignore them.
The installer restores only files it still owns and refuses to overwrite a
concurrent configuration change during rollback.
