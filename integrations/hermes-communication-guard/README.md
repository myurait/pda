# Hermes PDA communication guard

This integration provides runtime preemption, owner-approval copy enforcement, language normalization, and data-minimized audit for PDA communication.

## Install

From the canonical PDA checkout:

```text
python integrations/hermes-communication-guard/install.py
hermes plugins doctor integrations/hermes-communication-guard --ci
```

Restart the Hermes processes that serve the target surface after first enablement. Plugin and hook registration is process-start state.

The installer is transactional, refuses to replace an unrelated plugin path, preserves other plugin settings, and is idempotent. It links the profile plugin directory to this canonical source, adds only `pda-communication-guard` to `plugins.enabled`, applies both canonical skills required by the contract (`pda-user-escalation` and `pda-autonomous-improvement`), and deploys the matching `pda-approvals` API/UI assets. All prior bytes and applied digests are recorded together in profile-scoped install state.

## Verify

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  integrations/hermes-communication-guard/tests
hermes plugins doctor integrations/hermes-communication-guard --ci
```

After restart, replay these owner-visible scenarios:

1. Ask for current status; no new investigation tool should run before the answer.
2. Ask to stop; cancellation is permitted, new work is denied.
3. Call `kanban_request_review` with valid `owner_message` metadata and a generic worker summary; the summary should be replaced by the complete fixed approval template before the tool executes.
4. Call it with missing or worker-facing `owner_message` content; the review request itself should be blocked.
5. Submit approval prose outside the review tool with missing fields and worker detail; the detail should be removed and each missing decision field made explicit.

The audit database is profile-scoped at:

```text
$HERMES_HOME/plugin-data/pda-communication-guard/audit.db
```

It contains only timestamps, hashes, intent/outcome, and violation codes. Retention is 30 days. It does not contain raw user messages, assistant responses, commands, tool arguments, paths, or approval evidence.

## Disable / rollback

```text
python integrations/hermes-communication-guard/install.py --disable
```

Restart the same Hermes processes afterward. Disable preflights both managed skills and every managed approval-list asset before any write, removes only this plugin id from `plugins.enabled`, and restores all managed files to their exact prior bytes. Drift in either skill or an approval asset fails closed before configuration or any managed file changes. The source link and audit evidence remain for inspection.

## Boundaries

Hermes plugin hook exceptions are fail-open, and `transform_llm_output` cannot recall streaming deltas that a surface already displayed. The plugin therefore enforces the final response and pre-tool behavior without a Hermes core patch, but it is not a strict streaming no-leak boundary. See `docs/design/communication-quality-runtime-guard.md` for the decision model and residual risk.
