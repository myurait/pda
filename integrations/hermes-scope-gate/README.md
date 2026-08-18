# Hermes PDA Scope Gate

This directory is the canonical source for the PDA task-scope admission gate described in
`docs/design/task-scope-admission-gate.md`.

Rollout state: S0 + S1. `repository-closeout` turns are hard-enforced. Other task classes are
recorded as audit-only so implementation and operational work are not accidentally blocked during
the pilot.

## What is enforced

A high-confidence commit/push-only request starts in bounded discovery. Before mutation, the agent
must run a small read-only Git inventory and lock the repository/worktree/branch through the single
`scope_gate` control tool. Once locked, only the following are admitted inside the target:

- Git status and candidate-diff inspection;
- staging only explicitly inspected, bounded paths (`git add -A`, `--all`, `.`, globbing, and
  pathspec files are rejected);
- the commit and/or push explicitly requested by the user;
- direct local/remote ref verification;
- scope completion or blocker reporting.

Content edits, conflict/test repair, broad tests, branch/worktree manipulation, delegation,
`execute_code`, background jobs, deployment/restart, unrelated waits, unknown shell composition,
and target expansion are denied. Three denied expansion attempts close the tool gate except for
completion reporting. The initial budget is 15 minutes and `min(32, 8 + 3 * target_count)` admitted
tool calls.

Successful completion is not accepted from pre-tool intent alone: the post-tool hook must record a
successful requested commit/push and, after a push, a later ref verification. Failed terminal exit
codes do not become completion evidence.

## Architecture

- `__init__.py`: Hermes plugin registration, one control tool, stable policy prompt section,
  lifecycle hooks, and a final tool-execution middleware recheck after any hook argument rewrites.
- `scope_gate.py`: deterministic classifier, contract/JSON-Schema validator, command normalizer,
  SQLite atomic budget/evidence store, and shell-hook wire validator. The hot shell-validation path
  remains standard-library-only; contract lock uses the declared `jsonschema` dependency.
- `plugin_runtime.py`: Hermes hook/tool adapter.
- `pda-scope-gate`: out-of-process shell validator. Invalid JSON, timeout, spawn failure, or DB
  failure becomes a block because the configured shell hook has `fail_closed: true`.
- `schemas/scope-contract-v1.schema.json`: JSON Schema Draft 2020-12 contract.
- `install.py`: transactional, idempotent profile install. It enables the plugin, installs the
  exact fail-closed hook approval, and preserves existing plugin/hook configuration.

Audit state is profile-scoped under
`$HERMES_HOME/plugin-data/pda-scope-gate/scope-gate.db`. It contains prompt hashes and normalized
actions/resources, not raw prompts, raw tool arguments, or tool output. Completed rows are retained
for 30 days.

## Install and verify

Run from the canonical checkout:

```text
python integrations/hermes-scope-gate/install.py
hermes plugins doctor integrations/hermes-scope-gate --ci
hermes hooks doctor
```

A Hermes process restart is required after first enablement because plugin and shell-hook discovery
occurs at process startup. Verify both paths after restart:

```text
hermes plugins list --plain --no-bundled
hermes hooks test pre_tool_call --for-tool terminal
integrations/hermes-scope-gate/pda-scope-gate doctor
```

## Tests

```text
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  integrations/hermes-scope-gate/tests
```

The suite includes incident replay, target lock, denied expansions, completion closure, wall/tool
budgets, parallel atomic reservation, plugin/shell idempotence, argument-drift fail-closed behavior,
corrupt-state failure, transactional installer rollback, schema validation, and a subprocess test
against the installed Hermes runtime.

## Current limitations

- Only repository closeout is hard-enforced in S1. Bounded operations and artifact changes remain
  audit-only until pilot evidence supports S2/S3.
- Classification is deliberately high precision. An ambiguous request stays audit-only rather than
  receiving an overly broad or incorrectly narrow hard contract.
- A successful Git command is evidence of execution, not proof of semantic review quality. The gate
  prevents scope expansion; it does not replace repository policy or Git hooks.
