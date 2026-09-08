# Hermes minimal standard configuration — bounded M2 candidate verdict

Verdict: VALIDATED AS A LIMITED M3 CANDIDATE, not production adoption or full PDA self-integrity. Main PDA alone executed the probes. No independent review was performed.

Source: official NousResearch/hermes-agent fef0e16fe19b79ded929209f87c7434270b03825, reported 0.21.1, frozen uv lock with messaging extra. Existing production's 0.20.2/local patch stack was not this test object. The existing OpenAI Codex account was used only through the same official Hermes provider for synthetic prompts; no third-party/cloud token transfer. No product source patch, bespoke business-state machine, DBOS/control continuation, recovery daemon, model relay or dispatcher was added.

Final shape: one non-root, read-only-root Docker Compose service; built-in memory and native session/run stores; 2 GiB memory/no swap, 2 CPU, 96 PIDs, 64 MiB/2048-inode work tmpfs, bounded /tmp and logs, loopback-only normal port 19450. Docker socket and production home are absent. This is a minimal source deployment using standard Docker, not a claim that an official all-feature image was used.

## Observations

- Abrupt main death: final unless-stopped declaration recovered four successive times in 3.735–3.911 seconds before actual model readback. A later explicit stop and a separate in-flight owner death also recovered in 3.804/3.787 seconds. Native cancelled/interrupted records and exact idempotency replay survived; old delayed command processes disappeared.
- Work-output limits: ENOSPC at 67,108,864 bytes and at 2,046 empty files. A memory injector exited 137 with cgroup oom_kill=1. Body remained responsive; activity/memory hashes and session set survived; the real model read all four state categories while resource limits were hit.
- Startup-incompatible release: predeclared Compose health-gated deployment refused a synthetic startup RuntimeError and restored the pinned source in 7.694 seconds. This is a one-shot deployment failure branch, not a general always-on corruption detector. The code-only bad release did not migrate data.
- Compatible full-state restoration: official full backup taken with admissions quiesced, a deliberately invalid working database, then official import --force plus Compose up. Native cancelled/interrupted runs, idempotency IDs, synthetic receipts, all prior sessions, activity file and memory survived; standard restore took 8.616 seconds, followed by 14.445-second model readback. The old generation was retained. No work was accepted between the snapshot and fault. This does NOT prove zero-RPO recovery for arbitrary writes after an older backup, destructive migration, host/disk loss, or corruption recognition by an unattended service.
- Memory dependency denial: the memory file really returned PermissionError. Body and native interrupted-run display stayed available; model reported missing memory rather than inventing it. Predeclared permission restoration/restart recovered memory, with exact hash and semantic readback.
- Model egress outage: a Docker internal network removed routed egress. Native stored run state remained queryable at the private bridge IP; the real provider request failed in 27.207 seconds with a connectivity error, not a fabricated answer. Normal network restored in 6.311 seconds; subsequent model readback succeeded. The fixture also removes published NAT ingress, so it does not prove the original host front door stays reachable during network reconfiguration.
- After recovery the real model performed a bounded file repair and the observer read its actual repaired contents. This proves file-tool repair capability, not authority to mutate immutable runtime source or the production host.

For ordinary crashes, Docker itself restarted the body without the observer issuing start/restart. Update/restore and transient dependency release used fixed commands declared before the injected failure; no LLM diagnosed or repaired the failure in that measured path. Owner rescue was not requested. Startup/state probes and actual semantic checks are separate evidence. Full model-response times are not the small HTTP times quoted above; aggregate timings are produced from JSON at final exit.

## Preservation and limits

The four base categories are synthetic saved request, durable memory, explicitly stopped activity and outcome-unknown operation. Native live-turn tests additionally exercised a real terminal side effect: one fsynced synthetic file receipt, then interruption before tool acknowledgement. Replay returned the same cancelled/interrupted run, no second receipt, and the recovered model said an already-started effect was not undone and must not be blindly retried. This is not a real business-system receipt or a universal send fence. API idempotency retention is documented as 24h; admission after expiry, activities across long windows, activity UI, real sink reconciliation and safe continuation remain M3.

The work tmpfs is intentionally disposable. Accepted task state is in HERMES_HOME. The persistent state bind itself has no hard aggregate byte/inode quota: this proof covers one job's output in /work, not an agent deliberately or accidentally redirecting arbitrary bulk output into its state home. Authority to update the isolated body and its immutable artifacts was held by the main test executor, outside the candidate. End-to-end deployment authority/independent production recovery are not proven here.

## Rejected/invalid intermediate configurations

- on-failure:3 exhausted cumulatively on the fourth crash. Replaced with the documented standard unless-stopped; affected trials were rerun. Old passing runs are not evidence for the final declaration.
- Initial UV interpreter mount used the canonical directory while the venv symlink targeted an alias; corrected the bind. Missing messaging extra prevented API startup; installed the official frozen extra. No source fix.
- Three first crash probes selected both Docker init and the real main; injection assertion prevented any kill. They are invalid observer trials, not product recovery failures. Their needless repeated 120-second waits are retained as an observer defect; injector now aborts on failed injection.
- Online backup returned exit 0 while saying incomplete because of two live Unix sockets. It was not used as the accepted restore image; a quiesced official backup completed and was restored.
- First dependency observer used a nonexistent GET session endpoint (404), and the first internal-network probe expected published NAT. Both were corrected at the observer boundary, with original evidence preserved and the valid probes rerun.

## Custody

All raw JSON: evidence/. Reproduction declarations: compose.yaml, hermes-config.yaml, try-release.sh, restore-data.sh; probe scripts are disposable test instrumentation, not production deliverables. Private source/venvs/state/credential-bearing backups live under ignored .runtime and must never be attached or committed. Only sanitized synthetic observations are distributable. Cleanup evidence follows separately.
