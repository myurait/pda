# Current PDA priority

Status: active
Owner decision date: 2026-08-17

The immediate objective is to make the current PDA continuity state portable and to inject a source-bound PDA identity into Hermes more strictly than the built-in persona. Replacing Hermes with another core is deferred.

The current first operational step is a verified local continuity backup at 05:00 Asia/Tokyo every day, retaining seven successful generations. The backup policy, implementation, systemd units, and managed-habit declaration are versioned in this repository. Moving or exporting those generations off-host is intentionally deferred to a later decision.

This owner decision defines milestone HP-0 and supersedes only the sequencing in `.hermes/plans/2026-08-17_172757-pda-identity-portability-and-runtime-injection.md` that placed off-host custody before local automation. HP-0 is accepted only when the timer is enabled and active, a current-policy snapshot is fresh, and a real-snapshot restore drill passes. It does not satisfy the plan's later portable-recovery or disaster-recovery gates.

A local generation is not disaster recovery: loss of this host or disk can still destroy both the runtime and these backups. The next active engineering step after this habit is stable is the charter-derived PDA identity projection and verified Hermes injection.

## Cross-cutting execution policy

The source-controlled design in [`../design/operational-delegation-routing.md`](../design/operational-delegation-routing.md) defines how the current PDA should split work across deterministic tools, the primary Codex Sol runtime, bounded Codex Luna delegates, and durable Claude Code/Fable lanes. The development-Mac lane is specified separately in [`../design/development-mac-claude-kanban-integration.md`](../design/development-mac-claude-kanban-integration.md): PDA-hosted Kanban is the durable control plane, a deterministic Mac bridge pulls tasks over SSH, and official Claude Code background sessions provide resumable execution history. This is an operational resource-allocation policy and does not replace or defer the identity-portability priority above.
