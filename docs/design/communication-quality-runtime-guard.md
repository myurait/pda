# Communication quality runtime guard

## Outcome

PDA owner communication is separated into two planes. The owner plane carries only the decision, outcome, change, risk, reversibility, and required action. The evidence plane remains machine-verifiable metadata and may contain commands, repository identities, changed files, and verification results. More evidence never makes worker detail suitable for owner-visible copy.

Approval requests are the first enforced case. A `pda_approval` handoff contains an `owner_message` object with:

- `approval_subject`: what is being approved;
- `purpose`: why it matters and the result the owner receives;
- `changes_after_approval`: what becomes different after approval;
- `risk_and_reversibility`: the material risk and whether the change can be undone;
- `recommendation`: the recommended decision;
- `action`: exactly one operation for the owner.

The remaining `pda_approval` fields are technical evidence. They remain digest-bound but are not returned by the pending-approval API or shown in the default approval-list view.

## Runtime architecture

The standalone `pda-communication-guard` Hermes plugin uses documented hooks and does not patch Hermes core.

1. `pre_llm_call` classifies only high-confidence direct status and stop requests. It injects one-turn instructions without changing the cached system-prompt prefix.
2. `pre_tool_call` blocks new tool execution during a direct status request. During a stop request it permits only process/subagent cancellation and blocks new work.
3. `transform_llm_output` runs before final delivery. It normalizes a bounded list of Japanese plain-style endings and raw English worker terms, removes high-confidence worker-only detail from approval requests, and exposes every missing owner decision field instead of inventing content.
4. `post_llm_call` and `on_session_end` clear turn state so one session or turn cannot affect another.
5. A profile-scoped SQLite audit stores hashes, intent, outcome, and violation codes. It stores no prompt, response, command argument, path, or technical evidence body. Rows older than 30 days are deleted on write.

The plugin keeps turn intent in a `ContextVar`, verifies that the transform callback has the same session, and falls back only when exactly one active intent exists for that session. `pre_tool_call` additionally carries the exact turn identity. Hermes does not currently include `turn_id` in `transform_llm_output`, so ambiguous same-session fallback is treated as a normal response rather than borrowing another turn's status/stop intent. The plugin does not infer eligibility from session-id shape or user-controlled text beyond the bounded direct-request classifier.

## Approval-list boundary

The Dashboard pending endpoint still verifies the full digest-bound artifact, worktree identity, Git state, and finalization contract internally. Its response contains only `owner_message`, eligibility, a generic blocking reason, the opaque task id needed for the action route, and the digest needed to bind approval. The default view does not render branches, worktrees, SHAs, paths, changed files, commands, verification steps/counts, or implementation order.

Invalid or technically contaminated owner copy is not displayed. The card becomes ineligible and shows a generic request to send it back for correction. Detailed validation errors remain inside the verifier and test evidence rather than becoming owner copy.

## Scenario coverage

The regression suite covers:

- direct status requests blocking new investigation;
- direct stop requests allowing cancellation but blocking new work;
- future report instructions not preempting current authorized work;
- polite-language and vocabulary normalization;
- complete approval copy passing unchanged;
- missing approval elements being made explicit;
- worker-only technical detail being removed;
- audit data minimization;
- real Hermes `PluginManager` dispatch;
- approval payload validation and evidence/presentation separation;
- approval-list source containing no default worker-detail fields;
- installer idempotence and disable rollback.

## Limits and risk

Hermes documents plugin callback exceptions as fail-open. This plugin catches expected local audit failures so they do not suppress the deterministic text transform, but an import failure or unexpected host-level callback failure can leave a response unmodified. Treat Plugin Doctor and restart health checks as required cutover evidence.

The `transform_llm_output` hook runs after the model tool loop. On a streaming surface, earlier streaming deltas may already be visible before the final transformed response is delivered. Therefore this design enforces the final response and strongly guides generation, but it is not a strict no-leak boundary for streaming text. Strict pre-display enforcement would require host buffering or a Hermes core change; that tradeoff is intentionally excluded from this local-reversible rollout.

Heuristic language transforms are deliberately narrow. Unknown plain-style constructions or technical wording may pass; ambiguous text is not deleted. Approval requests receive stricter field and worker-detail handling because they are the decision boundary.

## Rollout and rollback

Final rollout is `merge-and-restart`: merge the verified task artifact, run the integration installer against the default Hermes home, atomically apply both `pda-user-escalation` and `pda-autonomous-improvement` plus the matching approval-list API/UI assets, restart only the Hermes processes that load those assets, and replay one status, stop, good-approval, and bad-approval scenario. No Open WebUI, network, credential, or external-publication change is required.

Rollback first verifies that both managed skills and every managed approval-list asset still equal the applied digests. It then disables `pda-communication-guard`, restores all managed files to their exact pre-install bytes, and restarts those same Hermes processes. Drift in any managed file fails closed before any rollback write. The source link and audit database may remain for inspection; disabled plugin discovery does not register its hooks.
