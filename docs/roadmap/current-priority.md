# Current PDA priority

Status: active design reassessment; autonomous mutation remains stopped
Latest owner decision date: 2026-09-06

## Current owner decision — 2026-09-06

The first roadmap for PDA v2 is **whole-system design reassessment**, not implementation of the old improvement plan. See [v2-01-whole-system-reassessment.md](v2-01-whole-system-reassessment.md), its [gap assessment](../design/v2-gap-assessment-2026-09-06.md), and the [primary-source platform comparison](../research/pda-v2-platform-landscape-2026-09-06.md).

Self-improvement is a core value, and self-integrity is its first user experience: a failed improvement must not return recovery and context reconstruction to the owner. The [charter](../../pda_charter.md) was amended accordingly. Hermes, memory architecture, execution framework, and UI are all candidates for comparison, with future maintenance and exit cost central to the decision; a full custom rewrite is not the default.

Scope control v2 remains stopped and is not to be patched or re-enabled. Current authorization covers owner-directed documentation, research, isolated disposable research probes, and the requested commit/push, not production changes or renewed autonomous implementation. Restart requires postmortem-led planning, independent evaluation, staged shadow/canary evidence, independent stop/rollback paths, and owner approval. Kanban `t_395213b7` remains unassigned Triage.

The communication integrity rules below remain cross-cutting constraints. The dated 2026-08-22 status and the later identity-injection/core-defer sequencing are historical; where they conflict with this section, **this section and v2-01 govern the next work**. Existing safety/approval boundaries are not relaxed. This change also does not alter the separately configured bounded Kanban review/capture habits.

## Historical sequence (retained as evidence; not execution permission)

## Owner decision update — 2026-08-22

1. Priority 0 (communication integrity) is **not closed**. The 2026-08-22 status recorded implementation/deployment/probe progress for three partial contracts: five-minute cadence, stall display, and plan registration. These are historical claims, not completion of Priority 0 or independent revalidation of the current installation. Individual original probe artifacts were not re-established by this design review, so this paragraph must not be used as current operational evidence. Related dated implementation history is retained in [`autonomous-improvement-goal.md` §2](autonomous-improvement-goal.md). The owner required a standing external communication audit (advisory) by the local Claude runtime; that historical follow-up is Kanban `t_5c02eea5` and is not resumed by this document.
2. **Scope change**: the subordination rule in Priority 0 ("new delegation architecture, Fable pilot work, and identity-injection feature work are subordinate") was premised on the PDA running its own improvement cycle. It does **not** apply to the externally driven upper-layer redesign of the autonomous improvement cycle described in [`autonomous-improvement-goal.md`](autonomous-improvement-goal.md). That redesign is the currently active workstream.
3. The daily reconciler (morning AI sweep) stays frozen. Queued-on-arrival processing via Kanban replaces the daily sweep; a redesigned "normalization process" (a queue of runtime-normalization actions such as required restarts, executed in a defined morning window only when the queue is non-empty) may reintroduce a daily step — see the goal document, milestone M2.

## Priority 0 — Communication integrity and escalation quality

The highest-priority PDA defect is that owner communication is not yet trustworthy during long-running or failed work. On 2026-08-18, a direct `報告せよ` instruction did not preempt internal investigation; the owner waited more than 30 minutes for a report. The eventual report was organized around the agent's internal vocabulary and mechanics, leaving the owner to reconstruct what mattered and what action was required.

This is a failure of communication integrity, not merely a style problem. A PDA that continues thinking instead of answering a direct report request, or that transfers its own cognitive burden to the owner, cannot reliably act as the owner's delegate.

Immediate operating rules:

1. A direct request to report, stop, or state current status preempts all non-emergency investigation and optional tool work. Respond from the currently verified state; label unknowns instead of delaying the response to make it more complete.
2. The first owner-facing paragraph must make clear why the message is being sent, what outcome or risk matters to the owner, and what the owner must do. If no action is required, say so explicitly.
3. Internal model names, task machinery, paths, counts, and validation details are secondary evidence. They must not replace a plain-language account of outcome, impact, remaining risk, and required action.
4. Long-running work must maintain bounded owner visibility. While work remains active, provide an owner-level progress update about every five minutes unless the owner requested silence or the delivery surface makes that impossible. Include elapsed time, an honest approximate percentage, the last meaningful milestone, and the current work or blocker—not tool logs. A stall, blocker, material scope change, or inability to honor a requested report must be surfaced without requiring the owner to chase the PDA.
5. The delegation/Fable task is paused. It must not resume without explicit owner direction; its intermediate state is recorded in [`../status/delegation-fable-pause-2026-08-18.md`](../status/delegation-fable-pause-2026-08-18.md).

This priority is not complete when wording guidance has merely been edited. Its exit gate is runtime-enforced behavior and scenario validation showing that:

- a report or stop request interrupts ordinary investigation immediately;
- a partial but honest status is delivered before optional fact-finding;
- a non-trivial report can be understood in one pass without internal vocabulary;
- the owner can identify the outcome, remaining risk, and required action or `none`;
- long-run progress and blockers remain visible at about the five-minute cadence without owner prompting.

Until this exit gate is met, new delegation architecture, Fable pilot work, and identity-injection feature work are subordinate. Urgent safety, continuity, or recovery incidents may still be handled immediately.

## Existing continuity objective

The prior engineering objective remains to make the current PDA continuity state portable and to inject a source-bound PDA identity into Hermes more strictly than the built-in persona. Replacing Hermes with another core remains deferred.

The first operational step was a verified local continuity backup at 05:00 Asia/Tokyo every day, retaining seven successful generations. The backup policy, implementation, systemd units, and managed-habit declaration are versioned in this repository. Moving or exporting those generations off-host remains deferred to a later decision.

This owner decision defines milestone HP-0 and supersedes only the sequencing in `.hermes/plans/2026-08-17_172757-pda-identity-portability-and-runtime-injection.md` that placed off-host custody before local automation. HP-0 is accepted only when the timer is enabled and active, a current-policy snapshot is fresh, and a real-snapshot restore drill passes. It does not satisfy the plan's later portable-recovery or disaster-recovery gates.

A local generation is not disaster recovery: loss of this host or disk can still destroy both the runtime and these backups. After Priority 0 is resolved, the next engineering step remains the charter-derived PDA identity projection and verified Hermes injection unless the owner changes the sequence.

## Cross-cutting execution policy

The source-controlled design in [`../design/operational-delegation-routing.md`](../design/operational-delegation-routing.md) defines how the current PDA should split work across deterministic tools, the primary Codex Sol runtime, bounded Codex Luna delegates, and durable Claude Code/Fable lanes. Its current design and pilot work are paused as stated above. Existing protective runtime limits remain active.
