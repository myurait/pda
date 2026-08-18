# PDA-local Fable perspective pilot

Status: Blocked before model inference
Checked: 2026-08-18 JST
Parent design: [`operational-delegation-routing.md`](operational-delegation-routing.md)

## Decision under test

The Fable owner-perspective lane uses the PDA-local Claude Code account. The development-PC Claude account is a separate development executor and is neither the test principal nor a fallback.

The owner's authorization covers a bounded validation using already-available PDA-local usage credits. It does not cover buying credits, enabling unlimited billing, changing organization policy, or using the development-PC account.

Fable 5 access depends on plan and seat tier. For plans where it uses usage credits, Claude Code's non-interactive mode does not show a consent prompt before billing an accessible credit balance.[1][2]

Usage-credit access, balance, spend caps, and auto-reload are managed from Claude Settings > Usage.[3]

Fable 5 requires 30-day data retention for safety monitoring and is unavailable under zero data retention, so minimizing personal context remains a real privacy boundary even on the intended PDA-local account.[4]

## Launch-path evidence

The tested host had Claude Code v2.1.205. The non-interactive launch path had no `ANTHROPIC_API_KEY` or cloud-provider override and did have `CLAUDE_CODE_OAUTH_TOKEN`.

`claude auth status --json` reported:

- `loggedIn: true`
- `authMethod: oauth_token`
- `apiProvider: firstParty`

Removing `CLAUDE_CODE_OAUTH_TOKEN` caused `claude auth status --text` to report no stored login. The tested principal is therefore the PDA-local token path, not the development Mac and not a Console API key.

## Bounded probe

The probe requested `claude-fable-5` through `claude -p`, disabled tools, denied interactive permission prompts, allowed one turn, disabled session persistence, and requested JSON output. The prompt contained no personal context and requested only an exact `OK` response.

Observed terminal outcome:

- process exit: 1
- result `subtype`: `success`
- result `is_error`: `true`
- API status: 429
- result text: `Fable 5 requires usage credits. /model to switch models.`
- `modelUsage`: empty
- reported cost: 0
- input/output model tokens: 0

A safe read-back of local Claude state reported `cachedExtraUsageDisabledReason: org_level_disabled`.

A schema-valid delegation-level blocked result is recorded at [`examples/fable-perspective-blocked-result.json`](examples/fable-perspective-blocked-result.json).

## Interpretation

Authentication succeeded, but the current PDA-local principal cannot access the usage-credit path required for Fable 5. The CLI reported zero model tokens and cost 0, but no provider billing ledger or balance was read back; this probe therefore makes no stronger credit-consumption claim and does not validate Fable's perspective quality.

The result also establishes a validator requirement: `subtype=success` is not sufficient. The wrapper must require process exit 0, `is_error=false`, no API error, a terminal result, exact Fable evidence in raw `modelUsage`, and a schema-valid `PerspectiveResult`; it maps the raw model keys into typed `runtime_outcome.models_used`.

## Next gate

Before retrying, the owner must make existing usage credits accessible through an account-authorized path, or wait until the account has an included Fable allowance.[2][3] While local state reports `org_level_disabled`, the PDA worker and wrapper remain blocked and must not mutate Settings, organization policy, billing, purchase, auto-reload, or spend caps.

A retry is executable only after control-owned evidence resolves both an existing positive credit balance and a finite spend cap. New credit purchase, unlimited billing, auto-reload, or organization-policy changes require separate authorization.

After access is restored, rerun one minimized, read-only, no-tools perspective task and verify:

1. PDA-local OAuth principal;
2. exact effective Fable 5 model;
3. successful terminal result and non-empty `modelUsage`;
4. schema-valid `PerspectiveResult`;
5. observed credit cost/usage;
6. no development-PC fallback.

## Sources

[1] https://code.claude.com/docs/en/model-config
[2] https://support.claude.com/en/articles/15424964-claude-fable-5-on-your-plan
[3] https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans
[4] https://www.anthropic.com/claude/fable
