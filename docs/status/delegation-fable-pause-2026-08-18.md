# Delegation and Fable work — paused checkpoint

Status: paused by owner
Paused: 2026-08-18 JST
Resume gate: explicit owner direction

## Why this record exists

This is an intermediate-state record, not a completion report. The task to design and validate model delegation, including the PDA-local Fable 5 perspective path, was stopped by the owner after a serious communication failure. No further model pilot, implementation, integration, or account change is authorized by this record.

## What is already true

1. Protective Hermes delegation limits are active in the default PDA runtime. Delegates are pinned to `openai-codex:gpt-5.6-luna`; child work is bounded to 32 iterations, 20 minutes, two concurrent children, four spawns per parent turn, and no nested orchestration.
2. A versioned routing design, schemas, examples, and routing skill exist on the isolated, pushed branch `design/delegation-routing` at `898fc61`.
3. That branch contains the owner's correction that Fable perspective work belongs to the PDA-local Claude Code account and that the development-PC account is a separate executor, never a perspective fallback.
4. A minimal no-personal-context probe reached the intended PDA-local first-party OAuth launch path but stopped before model inference with an API 429 stating that Fable 5 requires usage credits. It produced no Fable output and no model-usage evidence. Therefore Fable's perspective quality has not been tested.
5. At the stop point, no delegated agent or tracked background process was running.

## What is not complete or proven

- The corrected PDA-local Fable design is not integrated into `main`; `main` still contains the earlier development-Mac-oriented draft.
- No Fable `PerspectiveResult` has been produced, so owner-perspective quality is unassessed.
- Accessible existing-credit balance and a finite account spend cap have not been verified from a provider-authoritative source.
- The PDA-local fixed wrapper is not implemented.
- The Luna operating pilot and its effect on Codex quota pressure are not complete.
- The separate durable development-PC Claude worker is designed only on the isolated branch and is not implemented.
- The overall routing design has not passed an owner-facing operational pilot.

## Stop boundary

Until the owner explicitly resumes this task:

- do not run another Fable or Claude perspective probe;
- do not purchase credits, enable auto-reload, change billing or organization policy, or use another Claude account as a fallback;
- do not merge the isolated delegation branch into `main`;
- do not begin the durable development-PC worker implementation.

The already-active Luna guardrails remain in place because they reduce uncontrolled Codex fan-out; keeping those limits is not a continuation of the paused pilot.

## Safe restart point

If the owner later resumes the work, first satisfy the communication-integrity priority in [`../roadmap/current-priority.md`](../roadmap/current-priority.md). Then reconcile `design/delegation-routing` with the current `main` without overwriting parallel work, re-verify the intended PDA-local account and existing-credit cap, and run at most one minimized read-only pilot.
