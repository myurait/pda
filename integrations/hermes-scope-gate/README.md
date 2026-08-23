# Hermes PDA Scope Gate

This directory is the canonical source for the PDA task-scope admission gate described in
`docs/design/task-scope-admission-gate.md`.

Rollout state: S0 + S1, plus the S3-M1 deterministic core for `artifact-change`.
`repository-closeout` turns are hard-enforced. `artifact-change` enforcement is entered per turn:
an assignment contract seed locks the turn before its first tool call, or the executor locks the
turn itself. A turn with neither stays audit-only, so no lane is switched on by this change.
`bounded-operation` and the remaining classes are still recorded as audit-only.

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

For an enforced `artifact-change` turn, write permission and execution permission are separate
contract layers.

- First layer (hard, deterministic): known read/search/list tools are admitted with an audit record.
  Write destinations are identified from an explicit tool-name-to-fields catalogue, so an unlisted
  tool is treated as a mutation and a listed tool carrying none of its declared destination fields
  is denied. Every destination is resolved through one normalizer (resolve to absolute, relativize
  to the single locked worktree root, deny anything outside it, then match the repository-relative
  globs), the nearest existing ancestor is entity-resolved so the real destination cannot leave the
  worktree, and `*` never crosses a path segment (`**` is the recursive form). Staging is limited to
  explicitly named paths that are themselves inside the write scope — bulk, wildcard, and
  pathspec-magic forms are rejected, which is narrower than closeout. One local commit with an
  explicit message is admitted; pushing, history rewriting, and verification-hook bypass are not.
  The branch binding fixed at lock is rechecked before every Git write.
- Second layer (opt-in, not covered by the write-boundary guarantee): with no `execution` opt-in,
  every execution-bearing call is denied. An opted-in contract carries verification template ids
  only; the id to inspection-rule mapping is a closed registry in the gate. Arguments are scanned in
  full against an explicit allowlist with immediate deny for anything unknown, targets are matched
  file by file against the write and test scope, and directory-wide, target-less, and
  standard-input target forms are rejected. The process side effects of an admitted command are
  outside the first layer's guarantee — the gate inspects arguments only. Namespace-isolated
  execution and static inspection of collection paths are fixed M2 requirements, so until they land
  the second layer is declared but not enforced.

Contract lifecycle: an assignment seed is recorded through a store/runtime API that is deliberately
absent from the agent-facing control tool, is consumed at turn start, and locks the turn before its
first tool call. A turn with a seed whose repository verification fails exists with mutation denied
rather than falling back to unenforced, and a tool call that cannot be bound to a turn of a seeded
task is denied the same way. A seedless turn may self-lock (narrowing only, one worktree); before
the lock only reads are admitted. Closure is explicit: the intermediate audit hook does not close an
enforced turn, and a closed turn keeps denying mutation. The contract records its origin, so a
self-declared write scope is auditable as the weaker guarantee.

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

- Bounded operations remain audit-only until pilot evidence supports S2.
- `artifact-change` enforcement is per turn and is not switched on for any lane by default: with no
  assignment seed and no self lock, a turn stays audit-only. Wiring the assignment path for the
  autonomous lane is an owner decision (D-S3-6), not a property of this component.
- The second contract layer is declared but not enforced until namespace-isolated execution and
  static inspection of collection paths land. The first layer's guarantee does not extend to the
  process side effects of an admitted verification command.
- No independent scope reviewer is connected, so every G3 expansion that the contract does not
  already permit fails closed. Expansion budget values cannot be calibrated until it is.
- Classification is deliberately high precision. An ambiguous request stays audit-only rather than
  receiving an overly broad or incorrectly narrow hard contract.
- A successful Git command is evidence of execution, not proof of semantic review quality. The gate
  prevents scope expansion; it does not replace repository policy or Git hooks.
