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

- First layer (hard, deterministic): known read/search tools are admitted with an audit record.
  Write destinations are identified from an explicit tool-name-to-fields catalogue, so an unlisted
  tool is treated as a mutation, and a listed tool that carries none of its declared destination
  fields — or carries a declared container in an unexpected shape — is denied rather than skipped.
  Every destination goes through one normalizer: upward references are rejected on the raw
  argument, the path is entity-resolved (existing prefix through `realpath`, remainder appended),
  and both the locked-root membership test and the glob match are taken on that resolved location.
  Membership is therefore a property of the location, not of the notation: two spellings of the same
  directory behave alike, and an in-scope name that resolves elsewhere is matched where it really
  lands. `*` never crosses a path segment (`**` is the recursive form). Staging is limited to
  explicitly named non-directory paths inside the write scope — bulk, wildcard, pathspec-magic, and
  directory forms are rejected, which is narrower than closeout. Which Git writes are admitted comes
  from the contract's `actions.git_write` field, not from the task class; a contract without the
  field admits none. One local commit with an explicit message is admitted; pushing, history
  rewriting, and verification-hook bypass are not. The branch binding fixed at lock is rechecked
  before every Git write. The `terminal` argument fields are themselves a closed set: an unlisted
  field is denied instead of passing uninspected.
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
absent from the agent-facing control tool, and it locks the turn before its first tool call. The seed
is a standing ceiling for the task, not a one-shot token: later turns of the same task lock from it
again, and each use is recorded. A contract record is authoritative over the classifier — once one
exists for the task, the turn is an artifact-change turn whatever the message looks like, and the
classifier's own verdict is kept only as an audit field. A self lock (narrowing only, one worktree,
and refused outright while the task carries a seed) is likewise recorded at task scope, so the next
turn of the same work starts locked instead of unenforced. Before any lock, only reads are admitted,
and the unlocked stages carry the same wall/tool/deny ceilings as the locked one.

Verification that disagrees with the record leaves the turn present with mutation denied, never
unenforced; verification that could not run leaves the turn unregistered so the call is still
fail-closed and the next hook can retry. A call that cannot be bound to a turn is denied wherever a
contract record or an enforced turn history exists for the task or the session — an unknown turn id
and a missing task id included. Closure has two triggers: the explicit completion control and
session end. The intermediate audit hook is neither, so it does not close an enforced turn; a closed
turn stays reachable to keep refusing. The contract records its origin, so a self-declared write
scope is auditable as the weaker guarantee.

An artifact-change turn needs at least one of `task_id` / `session_id` from the host: the contract
record is looked up by those identifiers, and a call carrying neither has nothing to look up.

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
- `artifact-change` enforcement is not switched on for any lane by default: with no assignment seed
  and no self lock, a turn stays audit-only. The pre-lock default-deny stage can be turned on with
  `PDA_SCOPE_GATE_ARTIFACT_PRELOCK=1` and is off otherwise. Wiring the assignment path for the
  autonomous lane is an owner decision (D-S3-6), and whether the default-deny stage should already
  apply to the interactive lane is D-S3-8.
- The first layer admits no read-only Git and no work-bookkeeping tools, which the autonomous lane's
  own procedure needs, and their refusals spend the turn's deny budget. Resolving that — the allowed
  set, the tool categories, and what the deny budget counts — is D-S3-7.
- Commit admission inspects the command, not the index: content staged outside the gate still lands
  in the local commit. Push is denied, so this stays inside local history. Recorded as a first-layer
  residue in the design document.
- The second contract layer is declared but not enforced until namespace-isolated execution and
  static inspection of collection paths land. The first layer's guarantee does not extend to the
  process side effects of an admitted verification command.
- No independent scope reviewer is connected, so every G3 expansion that the contract does not
  already permit fails closed. Expansion budget values cannot be calibrated until it is.
- Classification is deliberately high precision. An ambiguous request stays audit-only rather than
  receiving an overly broad or incorrectly narrow hard contract.
- A successful Git command is evidence of execution, not proof of semantic review quality. The gate
  prevents scope expansion; it does not replace repository policy or Git hooks.
