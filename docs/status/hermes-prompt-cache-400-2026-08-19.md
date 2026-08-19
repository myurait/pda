# Hermes prompt_cache_retention 400 — incident record

Status: mitigated; fix committed on the PDA host, production deployment pending owner approval
Incident window: 2026-08-19 11:32–11:44 JST (3 request failures)
Recorded: 2026-08-19 JST

## Symptom

Open WebUI turns failed with `Hermesエラー: HTTP 400: prompt_cache_retention is not supported on this model`. The Hermes conversation loop classified the 400 as a non-retryable client error and aborted the owning turn, so no response reached Open WebUI.

## Observed facts

1. Three failures at 11:32:49, 11:36:41, and 11:44:02 JST, all with `provider=openai-codex`, `base_url=https://chatgpt.com/backend-api/codex`, `model=gpt-5.6-sol`, error body `param=prompt_cache_retention`, `code=invalid_parameter`.
2. The first failure followed an `HTTP 507: exceeded request buffer limit while retrying upstream` on the same conversation thread at 11:28:09. A transient `HTTP 503: upstream connect error` occurred at 15:01 and recovered on retry.
3. The running gateway process, its code checkout (`hermes-agent` at `0778d86c`), and `config.yaml` were all unchanged since 2026-08-18 18:57 JST — no deploy, restart, or reload preceded the window.
4. Client-side injection was ruled out across the reachable surface: hermes-agent gates `prompt_cache_retention` to Bedrock Mantle hosts and a model allowlist that excludes gpt-5.6 models; the Open WebUI pipe posts a fixed payload (`input` / `conversation_history` / `session_id` / `model` / `instructions` only); the API server does not merge unknown client body fields; the only installed plugin (`pda-scope-gate`) registers tool middleware only; no LLM request middleware is registered; request kwargs are not persisted; the Open WebUI `model` table holds no custom parameter presets.
5. No recurrence after 11:44:03. An end-to-end `/v1/runs` probe at 16:34 JST completed normally (`run.completed`, output `ok`).

## Assessment

The explanation most consistent with the evidence: the Codex backend's upstream proxy layer transiently attached `prompt_cache_retention` (or rejected requests as if they carried it) during the same backend fault window that produced the 507. This is an inference from elimination, not a directly observed backend fact — Hermes does not log outbound request bodies, and upstream `NousResearch/hermes-agent` has no related fix or issue as of 2026-08-19.

## Mitigation

hermes-agent commit `9a9f7281` (branch `fix/prompt-cache-hint-400-retryable` on the PDA host) classifies a 400 that names a prompt-cache hint (`prompt_cache_key` / `prompt_cache_retention`) as a retryable `server_error` instead of a fatal `format_error`, keeping the turn alive through transient upstream injection. Prompt-cache hints are optimization-only fields, so retrying the unchanged request is always safe; a genuinely persistent rejection still exhausts the normal bounded retry budget.

The patch is archived with checksums in [`integrations/hermes-error-resilience/hermes-core/`](../../integrations/hermes-error-resilience/hermes-core/README.md). `tests/agent/test_error_classifier.py` passes in full (100 tests, including 3 added for this case).

## Deployment state

The fix is committed but not yet loaded by the running gateway. To deploy, on the PDA host:

```bash
git -C ~/.hermes/hermes-agent merge --ff-only fix/prompt-cache-hint-400-retryable
systemctl --user reload hermes-gateway
```

The reload sends SIGUSR1, which drains in-flight turns before restarting. Verify afterwards that `systemctl --user status hermes-gateway` shows a fresh start time and that a short Open WebUI turn completes.

## If it recurs before deployment

The fault was instance-local and cleared on re-route: retry the Open WebUI turn. Confirm the signature with `journalctl --user -u hermes-gateway | grep prompt_cache_retention`.

## Related, out of scope

`agent.agent_runtime_helpers` logged "two routing keys are mapped to one session_id" concurrent-turn warnings for owui sessions during the same period. This is unrelated to the 400 failures and is not addressed here.
