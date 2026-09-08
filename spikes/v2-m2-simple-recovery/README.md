# M2 simple recovery — limited candidate selected

Verdict: PARTIAL / LIMITED M3 CANDIDATE SELECTED. This proof is closed, not a production system.

Read [M2-REPORT.md](M2-REPORT.md) or open [M2-REPORT.html](M2-REPORT.html). Machine-readable decisions are in [VERDICT.json](VERDICT.json), raw observations in evidence/, and the resume boundary in [CHECKPOINT.md](CHECKPOINT.md).

Run `python verify_evidence.py` for offline evidence assertions. This does not rerun the live model/fault drills. Do not blindly rerun one-shot probes against retained state.

What worked: clean Hermes standard restart, compatible quiesced restoration, native stopped/interrupted preservation, actual model readback and bounded file repair.

What did not qualify: Letta local configuration did not establish model readback. Managed/hybrid candidates remain unverified, not performance losers. Persistent state-home quota, arbitrary rollback zero RPO, real business reconciliation, independent review, whole-PDA recovery and adoption remain unproven.

Private .runtime is excluded from Git and delivery; it contains credentials and backup generations. No product-source patch or custom recovery daemon was created. Main and other worktrees were preserved.
