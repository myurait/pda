# PDA v2 bounded independent re-review — 2026-09-06 JST

## Scope and verdict

- **Scope:** Re-review only the three findings F1–F3 from `design-review.md` against the current working-tree versions of:
  - `docs/design/v2-gap-assessment-2026-09-06.md`
  - `docs/roadmap/v2-01-whole-system-reassessment.md`
  - `docs/roadmap/current-priority.md`
- **Out of scope:** comprehensive source/evidence re-audit, production operations, repository edits, and full test suite.
- **Verdict: PASS (bounded scope).** F1–F3 are closed. No bounded-scope regression was found that turns ordinary recovery/resume into an owner rescue task on every occurrence.

## Finding closure

### F1 — R2/R3 entry approval boundary: CLOSED

- `docs/roadmap/v2-01-whole-system-reassessment.md:39-43` adds an explicit `R2/R3` entry gate: completion of R1 documentation alone does not start the batch; candidate, isolation, change scope, data, egress, credential/billing, budget, stop, cleanup, and destruction scope must be presented for **explicit owner entry approval**.
- The same section separates this permission from R4 adoption and R5 production canary/autonomous restart, and expressly excludes runtime install/update, provider credentials, billing, managed egress, real-data migration, and destruction before approval.
- This is consistent with `docs/roadmap/current-priority.md:12-14`: scope v2 remains stopped; current authorization is limited and does not include production changes or renewed autonomous implementation.
- **Close basis:** the formerly implicit R1→R2/R3 transition is now a distinct, scoped, owner-controlled gate; it is not an authorization expansion.

### F2 — rollback versus resume and explicit stop: CLOSED

- `docs/design/v2-gap-assessment-2026-09-06.md:52-54` separates service recovery from activity resume. Rollback itself is not permission to resume; stop, expired approval, or unverified effect leads only to hold/diagnostic. Automatic resume is allowed only after verifying an existing valid approval scope, absence of stop, and effect read-back, with F5 applied as a main-path invariant.
- `docs/roadmap/v2-01-whole-system-reassessment.md:32,61-65` keeps independent recovery, effect reconciliation, no spontaneous PDA-side restart, and stop-epoch precedence as acceptance requirements.
- **Close basis:** the main loop no longer equates returning to a healthy version with resuming work, and it explicitly preserves stop/approval/effect boundaries.

### F3 — historical partial implementation is not Priority 0 completion: CLOSED

- `docs/roadmap/current-priority.md:20` now labels the 2026-08-22 three-part status (cadence, stall display, plan registration) as historical claims, not Priority 0 completion or independent current-installation revalidation; it states the original probe artifacts were not re-established and must not be used as current operational evidence.
- `docs/roadmap/current-priority.md:38-46` retains the complete Priority 0 runtime/scenario exit gate and explicitly says wording edits alone do not close it.
- `docs/design/v2-gap-assessment-2026-09-06.md:19-29` distinguishes historical design/status material from current effective state and warns that old progress/completion text must not be transferred into current permission/state. `docs/roadmap/v2-01-whole-system-reassessment.md:30,57,92-94` likewise marks R0 and later stages as incomplete and treats existing probes as inputs, not completion evidence.
- **Close basis:** the partial claims are explicitly bounded as historical/non-current and cannot be read as Priority 0 completion or current proof.

## Ordinary recovery / owner-return regression check

- `docs/design/v2-gap-assessment-2026-09-06.md:54` explicitly says eligible, already-approved activity may auto-resume after the required checks and that ordinary rescue is not returned to the user each time.
- `docs/roadmap/v2-01-whole-system-reassessment.md:12,32,35,80,88` distinguishes the design goal from owner approval gates: R2 requires no owner rescue operation; R5 requires a no-owner-rescue full cycle; read-only status/diagnostics must not be rejected in a way that returns rescue to the user; owner involvement is for direction and permission boundaries, not performing normal recovery.
- `docs/roadmap/current-priority.md:10-12` keeps the failed-improvement self-integrity objective and limits owner approval to restart/governance boundaries rather than routine recovery.
- **Result:** no reverse change found. Owner approval remains required for scoped experiment/restart/adoption decisions, while ordinary recovery/resume is a separately conditioned system transition.

## Minimal checks and artifacts

- `git diff --check`: **passed** (no output, exit code 0).
- Repository HEAD observed: `a367302f2caf99ddcb01eb978fb3fb581a23b14c`.
- Optional existence-only spot check:
  - `docs/research/evidence/source-map.json`: exists.
  - `docs/research/evidence/dbos-probe/README.md`: exists.
  - Contents were not audited.
- The target repository was not edited; its pre-existing modified/untracked state was left untouched. No production operation or full test suite was run.

## Final target SHA-256 (working-tree files reviewed)

- `docs/design/v2-gap-assessment-2026-09-06.md`: `39c10ac6579d118c7bb5d515acbcf9af46590f9147bd163249ca6f2e61ab52d4`
- `docs/roadmap/v2-01-whole-system-reassessment.md`: `789b64e3336133196df38d12de70279886ba397fd2a58402eef37317f659c4a3`
- `docs/roadmap/current-priority.md`: `c15f4756e5c25cb2788804d29dfc32006d1dc150bf5dbf24e8d55175935a1391`

## Files created or modified

- Created: `/home/user/.hermes/cache/research/pda-v2-20260906/design-rereview.md`
- Target repository files modified: none.
