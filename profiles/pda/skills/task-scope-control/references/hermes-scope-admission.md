# Hermes scope-admission reference

This reference captures the enforceable design derived from a PDA incident where a commit/push request expanded into an hour-long all-worktree audit, conflict repair, broad tests, branch comparison, and unrelated cutover waiting.

## Contract model

Lock one `ScopeContract` per user turn before mutation:

- one observable objective;
- frozen targets;
- required actions;
- one-hop prerequisites;
- declared verification;
- explicit non-goals;
- wall-time/tool/denial/background/delegate budgets;
- success, partial, blocked, and failed predicates.

Normalize each proposed action as `required`, `prerequisite`, `verification`, or `expansion`. Deterministically admit the first three within target and budget. Unknown actions and expansions fail closed for narrow tasks. Count denied attempts so the model cannot try alternate tools until the global iteration limit.

## Hermes v0.20.2 integration facts

Official Hermes surfaces support a no-core-fork implementation:

- `pre_llm_call` fires once per user turn and can inject contract context into the current user message.
- `pre_tool_call` fires immediately before tool execution and can return `block`, `approve`, or `modify`.
- `post_tool_call` observes blocked, failed, and successful calls.
- A plugin system-prompt section supplies byte-stable, session-frozen invariants.
- Python plugin hook exceptions are logged and skipped; do not treat that alone as a fail-closed boundary.
- A shell `pre_tool_call` hook supports `fail_closed: true`; use the same validator executable as the hard fallback.
- Installed source confirmed common `invoke_tool()` calls `pre_tool_call` before branching to agent-level tools such as `todo`, `memory`, and `delegate_task`.
- `pre_verify` only applies after code edits and can continue a turn; it is not a general stop/finalization gate.

Use one plugin tool, `scope_gate(action=lock|review|complete)`, rather than three schemas. Bootstrap-allow only this control tool and bounded read-only discovery before contract lock.

Canonical source belongs in the PDA repository and deploys profile-safely through `HERMES_HOME`. The current runtime profile may be named `default`; do not confuse that deployment name with a portable repository profile.

## Narrow closeout enforcement

For `repository-closeout`, use an initial 15-minute wall budget, zero expansion, zero delegates, zero background jobs, and at most three denied attempts.

Allow:

- bounded status/worktree inventory when explicitly requested;
- candidate diff and targeted secret/whitespace checks;
- stage, commit, requested push;
- local HEAD versus intended remote-ref read-back;
- commit hooks that run as part of the commit itself.

Deny:

- content edits and conflict resolution;
- broad tests, lint, review, or branch audit;
- branch/worktree creation, deletion, reset, stash, rebase, or merge;
- unrelated process waits, restart, deploy, or cutover;
- delegation and background terminal work;
- `execute_code`, because one outer call can contain nested tool activity not represented by the parent semantic budget.

If one target is conflicted, close commit-ready targets if safe and report the conflicted target as blocked. Do not repair it under a closeout-only contract.

## Required replay tests

1. A commit/push-only prompt selects `repository-closeout`.
2. A global worktree inventory is allowed only with explicit global wording.
3. The target set freezes after one bounded inventory.
4. Git closeout actions pass; broad tests, conflict edits, delegation, and cutover waits are blocked.
5. Parallel calls reserve budget atomically.
6. Validator crash, timeout, invalid output, or state failure blocks side effects.
7. Repeated denials close tool execution rather than consuming hundreds of iterations.
8. An explicit “fix failures, test, then commit/push” request selects an artifact-change contract and is not falsely blocked.
9. “Commit only” does not silently push.

## Sources

- https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/
- https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop/
- PDA design artifact: `docs/design/task-scope-admission-gate.md`
