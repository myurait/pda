# PDA Identity Portability and Strict Hermes Injection Implementation Plan

> **For Hermes:** Load the `test-driven-development` skill and use `coding-agent-orchestration` or isolated task-by-task execution. Do not mix this work with the pre-existing Open WebUI working-tree changes.

**Goal:** 現在のPDA実行実体を、同一PCの破損後も同一Hermes runtime上へ復元できる可搬な状態にし、PDA憲章に由来するsource-bound identityをHermesのbuilt-in人格ではなく実際のidentity slotへ決定論的・検証可能・段階的にfail-closeで注入する。

**Architecture:** 当面の到達点を「別コアへの交換」ではなく「fresh host上の同一Hermesへのhost portability」と「Hermes上のstrict identity injection」に限定する。PDA憲章を最上位authority、憲章から生成するHermes `SOUL.md`を破棄可能なruntime projection、Hermes/Open WebUIのnative stateを暫定的なcontinuity stateとし、Git管理するrelease plane、暗号化するstate plane、別管理するsecret plane、再構築可能なcache planeへ分離する。起動前guardと実loader試験でprojectionの実注入を検証し、Open WebUI overlay・delegate・cron・resume境界を個別に閉じる。

**Tech Stack:** Python 3.11、uv、pytest、JSON Schema、YAML、SQLite Online Backup API、Hermes Agent v0.18.2系、Hermes profile distribution、OpenSSH署名、age/restic等の暗号化backup、systemd、Docker Compose、Git。

---

## 0. この計画が確定する優先順位

本計画自体を、今回の目標設定と実装順序の最初のリポジトリ内記録とする。実装開始後、同じ内容を`docs/roadmap/current-priority.md`と`docs/design/identity-portability.md`へ昇格する。

優先順位は次のとおり。

1. 現在の実効状態を、dirty stateを含めてオフホストへ退避する。
2. PDA identityのauthorityとHermes projectionをsource-boundにする。
3. Hermesが実際に読み込んだidentityを全対応surfaceで検証可能にする。
4. Hermes、memory、session、skills、Open WebUI、runtime artifactをfresh hostへ復元する。
5. backupとboot attestationを定常運用へ移す。
6. その後にContext Spine／PKBの実装へ戻る。
7. Hermesから別コアへの交換実証はPhase 10相当の後続milestoneへ据え置く。

これは「コア交換可能性を放棄する」決定ではない。host portabilityを先に閉じ、将来のruntime-neutral化を阻害しないcontractだけを残す決定である。

---

## 1. Authority map

憲章の「思想 → 再利用可能な思考 → システム」という主従を保ち、normative authorityを新しいcontract層へ分散させない。

| 層 | 資産 | 権限・意味 | 現在／将来の所在 |
|---|---|---|---|
| A | Canonical norm | PDAの思想と改定権限を定める唯一のnormative authority。ユーザーのみ改定可。promptではない | `pda_charter.md` |
| B | Reusable continuity | memory、user model、session、local skill、判断・作業履歴等。憲章を改定せず、現在のPDAが再利用する内容 | `~/.hermes/`、Open WebUI volume、PDA repoのlocal state |
| C | Derived executable artifacts | 憲章をstable clause IDへcompileしたidentity contract、Hermes `SOUL.md`、projection map、manifest。独立authorityではなく再生成・棄却可能 | 新設する`identity/`、`profiles/pda/` |
| D | Vessel | Hermes、model/provider、Open WebUI、adapter、tool、service、cache | 現在の実装一式 |

重要な境界:

- `pda_charter.md`をそのまま`SOUL.md`へコピーしない。
- `MEMORY.md`の「PDAである」という一文をidentity authorityにしない。
- `SOUL.md`、identity contract、skill、project context、memoryのどれも憲章を改定できない。
- Identity contractへのowner approvalは「憲章に忠実なこの派生artifactを実行してよい」というexact-candidate承認であり、新しいnormを作る権限ではない。
- 憲章にsource-boundできないcontract文は、ownerが候補を承認してもidentity projectionへ入れない。必要なら先にユーザーが憲章を改定する。
- 憲章hashが変わればcontract、projection、release signature、approvalは失効する。
- 「再利用可能な思考」の最終定義はここで固定しない。現段階では失うと再構成不能なnative stateをtransitional continuityとして保全する。

---

## 2. Scope / non-goals

### 2.1 今回のscope

- 同一Hermes familyをfresh Ubuntu hostへ復元するhost portability。
- 現在のHermes identity fallbackをPDA固有のgenerated `SOUL.md`で置換する。
- Charter → contract → projection → active loader → sessionのprovenance chain。
- Hermes full state、memory、user profile、sessions、local skills、cron、plugins、Open WebUI state、PDA integration code、deployed artifact、runtime sourceのbackup/restore。
- Open WebUI、API、CLI、cron、delegate、new session、resume、compression/rebuildのidentity propagation試験。
- 実体が自分のidentity release、source hash、drift、backup freshnessを機械的に確認できる`pda self inspect/verify`。
- owner署名、起動前guard、rollback、fresh-host drill。

### 2.2 今回のnon-goals

- 別orchestrator／別coreへのproduction cutover。
- Context Spine、Event Ledger、PKB、graph storeの先行実装。
- 全memoryをruntime-neutral schemaへ正規化すること。
- provider側のhidden system instructionやmodel weightsのattestation。
- 完全な多層gate、自律的な自己改変、完全な別principal分離。
- 既存の`origin/claude/fable-system-design-d3c203`をそのままmainへmergeすること。

### 2.3 今回の成功を意味しないこと

- `SOUL.md`を置いただけではstrict injection完了ではない。
- profile exportだけではstate portability完了ではない。
- local backupだけではdisaster recovery完了ではない。
- agentが「私はPDA」と回答しただけではloader verification完了ではない。
- fresh hostへ同一Hermesを復元できてもcore replaceability完了ではない。

---

## 3. 現在状態の根拠

調査時点: 2026-08-17 17:27 JST。

### 3.1 Runtime identity

- Hermes: `v0.18.2 (2026.7.7.2)`。
- installed source: `/home/user/.hermes/hermes-agent`、local commit `614dc194ea7d853d39f9e84582ec62156f41a475`。
- profileは`default`のみ。
- `/home/user/.hermes/SOUL.md`はPDA projectionではなく汎用Hermes identity。
- `hermes prompt-size`実測ではsystem prompt 26,819 chars、project context tier 0 chars。
- `agent/prompt_builder.py:139-147`にhardcoded `DEFAULT_AGENT_IDENTITY`がある。
- `agent/prompt_builder.py:1864-1892`が`$HERMES_HOME/SOUL.md`をidentity slotとして読む。
- `agent/system_prompt.py:181-199`はSOULが読めれば先頭へ置き、読めなければbuilt-inへfallbackする。
- `agent/system_prompt.py:457-458`にあるとおり、ephemeral system promptはcached/stored promptへ入らずprovider call時に追加される。

### 3.2 Surface-specific gaps

- `tools/delegate_tool.py:1364-1384`はdelegate childを`skip_context_files=True`、`skip_memory=True`で起動し、`load_soul_identity=True`を渡していない。delegateは現状PDA SOULを継承しない。
- `cron/scheduler.py:3335-3363`は`load_soul_identity=True`を明示しており、cronはSOULを読む設計になっている。
- `integrations/openwebui-hermes-progress/functions/hermes_progress_pipe.py:229-246`はOpen WebUIの`system` messageをHermes Runs APIの`instructions`へ渡す。
- Hermes API serverはclientの`system_message`/`instructions`をephemeral system promptとしてagentへ渡す。SOULと同じ最終system roleへ連結されるため、厳密なauthority階層ではない。
- existing sessionのsystem promptはsession単位で凍結される。SOUL変更後もresumeした旧sessionが新identityへ移るとは仮定できない。

### 3.3 Portability gaps

- `/home/user/.hermes`は約1.9 GiB、`/home/user/openwebui`は約1.1 GiB。
- `/home/user/.hermes/state.db`は438,566,912 bytes。調査時modeは0644であり、private stateとして要修正候補。
- Hermesの`hermes backup`はSQLite Online Backup API経由のsafe copyを行うが、成果物は通常のZIPであり暗号化されない。
- `hermes profile distribution`はSOUL/config/skills/cron/MCP等の宣言的配布に使えるが、memory/session/state/credentialsを意図的に含まない。
- `hermes profile export default`もcredential-freeなuser-facing surfaceであり、full state backupの代替ではない。
- Hermes codebaseはfull backupから除外されるため、local carried commitとpatchの別artifact化が必要。
- PDA working treeにはOpen WebUI関連の既存未コミット変更がある。調査中に`integrations/openwebui-hermes-progress/tests/test_install_hermes_progress_pipe.py`という新しいuntracked fileも観測された。由来を推測せず、削除・上書き・今回のcommitへの混入を禁止する。

### 3.4 Existing designとの関係

- `origin/claude/fable-system-design-d3c203`はContext Spine、backup/restore、runtime-neutral contractの有用なproposalを含む。
- ただしbranchはPDA憲章追加前に作成され、`pda_charter.md`、charter-derived identity、Hermes SOUL projection、actual-loader attestationを扱わない。
- branchをmainと単純比較すると後発の憲章やOpen WebUI integrationが削除に見えるため、merge-baseを基準に扱う。
- 本計画ではbranchのrestore-first、native DB safe snapshot、memory projection、gold set等を選択的に再利用する。authority順序は憲章配下へ修正する。

---

## 4. Target capability levels

### 4.1 Self-recognition levels

| Level | 定義 | 今回 |
|---|---|---|
| SR-0 | Generic runtime identityのみ | 現状のSOUL本体 |
| SR-1 | Memory等にPDAであるというsemantic self-referenceがある | 現状のmain session |
| SR-2 | Charter hashとclause traceabilityを持つsource-bound identity projectionが実loaderから入る | 必須 |
| SR-3 | Signed full-artifact release、bundle外latest checkpoint、control-owned session binding、overlay policy、all-surface attestation、boot guardがある | 必須 |
| SR-4 | Authorityとruntime principalが完全に分離され、runtimeがactive identityを変更不能 | 後続hardening。今回のroot-owned release/read-only service namespaceは部分達成 |
| SR-5 | Alternate coreでも同一identity/governance/evalが通る | deferred |

### 4.2 Portability levels

| Level | 定義 | 今回 |
|---|---|---|
| HP-0 | 同一disk上だけ | 現状 |
| HP-1 | Native stateのconsistent encrypted off-host generationがある | 最初に達成 |
| HP-2 | 隔離directory/profileへrestoreできる | 必須 |
| HP-3 | Source diskを使わずfresh Ubuntu hostへ復元し、bundle外checkpointでold signed releaseを拒否し、identity attestationと代表session/UIが通る | 最終受入 |
| HP-4 | Alternate runtimeへnormalized continuityを移せる | deferred |

今回の終了条件は`SR-3 + HP-3`である。SR-4/HP-4を誤って完了扱いしない。

---

## 5. Four-plane Portable PDA Bundle v1

```text
owner-controlled Git / signing host
┌────────────────────────────────────────────────────────────┐
│ Release plane (small, signed, non-secret, reproducible)     │
│ charter → identity contract → Hermes projection             │
│ profile distribution / runtime locks / schemas / runbooks   │
└──────────────────────────┬─────────────────────────────────┘
                           │ verify + deploy
                           ▼
replacement/current host
┌────────────────────────────────────────────────────────────┐
│ root/control-owned active release                           │
│   └─ Identity Guard ──fail closed──> Hermes gateway/runtime │
│                                      │                      │
│ State plane (encrypted off-host)      ├─ state.db/memory     │
│   Hermes native snapshot              ├─ skills/cron/plugins │
│   Open WebUI DB/attachments           └─ UI/session state    │
│                                                            │
│ Secret plane                                                │
│   encrypted escrow OR reissue inventory; keys off-runtime   │
│                                                            │
│ Cache plane                                                 │
│   venv/images/model cache/index/queues; rebuild or discard   │
└────────────────────────────────────────────────────────────┘
```

### 5.1 Release plane

Git管理し、secretを置かない。`release-manifest.json`のartifact allowlistがsigned runtime/control closureを定義し、repo全fileを暗黙に署名対象とはしない。Charter/contract/projection、runtime/control code、patches、locks、schemas、unit bytes、restore contractはclosureへ含める。Evaluation/status evidenceやhistorical planはGit audit対象だがruntime digestへ含めない。

```text
pda_charter.md
identity/
  identity-contract.yaml
  projection-policy.yaml
  owner-signing-key.pub            # transparency copy only; not the trust bootstrap
profiles/pda/
  distribution.yaml
  SOUL.md                           # generated, contains projection_id only
  projection-map.json               # generated
  release-manifest.json             # generated canonical content; contains no own digest/signature
  release-manifest.json.sig         # detached owner approval/signature, created after canary
  legacy-baseline-manifest.json     # recovery-only full current-runtime baseline
  legacy-baseline-manifest.json.sig
  initial-recovery-authorization.json
  initial-recovery-authorization.json.sig
  config.yaml                       # non-secret desired subset
  .env.template                     # secret names only
  skills/pda-self/SKILL.md
  skills/pda-user-escalation/SKILL.md
runtime/
  runtime.lock.json
  source-artifacts.lock.json
  session-binding-contract.yaml
  control-runtime.lock.json
src/pda/
  identity/                         # renderer/verifier/broker/deploy
  backup/                           # sealed snapshot/selective restore
integrations/hermes/patches/
integrations/openwebui-hermes-progress/
continuity/
  catalog.yaml
  restore-contract.yaml
schemas/
  identity-contract.schema.json
  projection-input.schema.json
  signature-envelope.schema.json
  attestation.schema.json
  release-manifest.schema.json
  recovery-authorization.schema.json
  accepted-checkpoint.schema.json
  session-binding-token.schema.json
  continuity-catalog.schema.json
  snapshot-manifest.schema.json
infra/
  systemd/
  compose/
docs/
  design/
  operations/
  evaluation/
```

### 5.2 Encrypted mutable payload

暗号化されたgenerationとしてオフホストへ置く。論理的にはstate objectとsecret-bearing sealed archiveをmanifest上で区別する。

```text
snapshot-set/<backup_set_id>/
  inner-manifest.json
  hermes/hermes-backup.zip           # sealed native archive; may contain secrets
  hermes/sessions-portable.jsonl.zst
  openwebui/data-snapshot.tar.zst
  deployed/openwebui-function-source/
  repos/pda-working-tree.bundle-or-patch.tar.zst
  runtime/hermes-source.bundle
  audit/backup-verification.json
```

Native stateを暫定的にauthoritative recovery sourceとして保存する。ただしidentity authorityではない。Portable JSONL exportは補助であり、resume/tool-call metadataまで復元できると試験するまではnative DBの代替にしない。Hermes full archiveはsecret plane相当の保護を要求し、wholesale restoreしない。

### 5.3 Secret plane

repoと通常manifestにはsecret値も平文hashも置かない。

各secretを次で分類する。

- `reissue`: Tailscale machine state、失効可能なcredential。
- `escrow`: API server key、Open WebUI/ntfy設定等、復旧に必要でrotation可能なもの。
- `reauth`: OpenAI Codex OAuth、Claude Code OAuth等、provider flowで再認証するもの。
- `derive`: owner-held sourceから再生成できるもの。

暗号化recipient/recovery key、owner signing key、backup-admin credentialはPDA runtimeへ置かない。

### 5.4 Cache plane

venv、node_modules、container layer、model cache、embedding index、Firecrawl queue、通常log等。`runtime.lock`から再構築できるものはbackup必須にしない。

### 5.5 External recovery anchors

Portable bundle自身にtrust/recencyを自己宣言させないため、次はbundle・runtime・通常snapshotの外に置く。

- Owner signing private key。
- Owner public-key fingerprint/trust bootstrap record。
- Latest owner-signed `{sequence, release_digest, parent_digest}` accepted checkpoint。
- Backup recovery key/admin credential。
- 必要なsigned recovery/rollback authorization。

Repoやencrypted snapshotへcopyを含めてもよいが、それをfresh-host trust/recency sourceにしない。Main Mac等のowner-held recovery materialと独立off-host copyから検証する。

---

## 6. Identity contract, projection ID, and signed release digest

### 6.1 Contract shape

`identity/identity-contract.yaml`は独立authorityではなく、憲章からruntime projectionを作るためのderived compiler inputである。

```yaml
schema: pda.identity/v1
pda_id: pda:personal-delegate-agent
source:
  document: pda_charter.md
  sha256: "<full sha256>"
  amendment_actor: owner-only
clauses:
  - id: PDA-EXISTENCE-001
    source_heading: "第一条 存在 — PDAは何であるか"
    source_fragment_sha256: "<full sha256>"
    runtime_statement: "この実行体は、ユーザーの認知を拡張し、同時に外側から異議を述べるPDAの現在の実行実体である。"
  - id: PDA-AUTHORITY-001
    source_heading: "第三条 関係 — ユーザーとPDAの間の原則"
    source_fragment_sha256: "<full sha256>"
    runtime_statement: "最終決定と憲章改定権はユーザーにある。"
  - id: PDA-VESSEL-001
    source_heading: "第六条 主従 — 何が残り、何が交換されるか"
    source_fragment_sha256: "<full sha256>"
    runtime_statement: "Hermes、model、memory方式、toolはPDAそのものではなく現在の器である。"
projection:
  adapter: hermes-soul/v1
  max_chars: 6000
  forbid_dynamic_facts: true
  forbid_unmapped_norms: true
```

実際の全clauseは憲章の各runtime-relevant文へ追跡可能にする。上のstatementはformat例であり、そのままowner-approved候補とはみなさない。Contract自身にapproval hashやsignatureを埋め込まない。

### 6.2 Two-stage, non-self-referential identity

一つの曖昧なIDへsourceと最終bundleを混在させない。次の二段階を使う。

#### A. `projection_id`

SOULへ安全に埋め込めるbuild-input identity。次のdescriptorをRFC 8785相当でcanonical JSON化したbytesのSHA-256とする。

```json
{
  "schema": "pda.projection-input/v1",
  "charter_sha256": "...",
  "identity_contract_sha256": "...",
  "projection_policy_sha256": "...",
  "renderer_source_sha256": "...",
  "renderer_lock_sha256": "...",
  "adapter_spec_sha256": "...",
  "canonicalization": "rfc8785+utf8-lf/v1"
}
```

Rendererの入力、policy、実装bytesが同じならSOULは同じでなければならない。SOULは`projection_id`だけを含み、自身のSHA-256も後段のrelease digestも含めない。

#### B. `release_digest`

全runtime artifactをfreezeした後で作る`release-manifest.json` canonical bytesのSHA-256。Manifest自身はdigest/signature/approvalを含まず、最低限次を含む。

```json
{
  "schema": "pda.signed-release/v1",
  "sequence": 7,
  "parent_release_digest": "sha256:...",
  "projection_id": "sha256:...",
  "source_commit": "<full git sha>",
  "runtime_version": "v0.18.2",
  "recovery_targets": [
    {"release_digest": "sha256:<legacy baseline digest>", "mode": "legacy_recovery_only"}
  ],
  "artifacts": {
    "pda_charter.md": "sha256:...",
    "identity-contract.yaml": "sha256:...",
    "projection-policy.yaml": "sha256:...",
    "projection-input.json": "sha256:...",
    "renderer-source": "sha256:...",
    "SOUL.md": "sha256:...",
    "projection-map.json": "sha256:...",
    "distribution.yaml": "sha256:...",
    "config.yaml": "sha256:...",
    "openwebui-pipe": "sha256:...",
    "hermes-patch-series": "sha256:...",
    "runtime.lock.json": "sha256:...",
    "source-artifacts.lock.json": "sha256:...",
    "session-binding-contract.yaml": "sha256:...",
    "active-skill-and-context-policy": "sha256:...",
    "identity-binding-broker": "sha256:...",
    "control-runtime.lock.json": "sha256:...",
    "backup-selective-restore-code": "sha256:...",
    "snapshot-and-restore-schemas": "sha256:...",
    "deploy-and-accepted-state-code": "sha256:...",
    "systemd-unit-set": "sha256:..."
  }
}
```

- `release_digest = sha256(canonical release-manifest.json bytes)`。
- `release-manifest.json.sig`はowner keyによるdetached signatureであり、release manifestの外に置く。
- Latest checkpoint、recovery/rollback authorization、their signatures、decision evidenceもdetached envelopeでありartifact mapへ自己包含しない。
- Owner approvalはこのexact `release_digest`へのsignatureとして行う。Contractへapproval hashを追記しない。
- Session binding、canary verdict、cutover approval、recovery/rollback authorizationは`projection_id`ではなく`release_digest`へ結び付ける。
- 同じSOULでもPipe、Hermes patch、config、runtime lockのどれかが違えば別releaseになる。
- Buildを2回行い、projection artifactとcanonical manifestがbyte-identicalでなければFAIL。
- Timestamp、host path、model name、port、secretはSOULに入れない。必要なaudit timestampはsignature/approval evidence側に置く。

### 6.3 Trust bootstrap, accepted checkpoint, and rollback

- Owner public keyのrepo内copyはtransparency用でありtrust rootではない。
- Trust rootはmain Mac等のrecovery materialからfingerprintを別経路で確認し、root-owned `/etc/pda/trust/allowed_signers`へbootstrapする。
- Runtime/releaseはこのtrust storeを変更できない。
- Root-owned `/var/lib/pda-control/accepted-release.json`がactive accepted sequenceとdigestを保持する。
- それとは別に、owner-held/off-host recovery materialとして`latest-accepted-checkpoint.json`とdetached signatureを維持する。内容は少なくとも`sequence`、`release_digest`、`parent_digest`、`issued_at`を持つ。
- Fresh-host restoreはrelease/snapshotを選ぶ前にlatest checkpointを取得・検証する。古いが正しく署名されたreleaseをlatestとして自己採用させない。
- 通常updateはstrict monotonic sequenceとexpected parentを要求する。
- Previous releaseへのdowngradeは、`from_digest`、`to_digest`、mode、expiry、reasonを持つowner-signed detached recovery/rollback authorizationがある場合だけ許す。
- `mode=strict_rollback`はtarget自体がSR-3 strict verificationを通る場合だけproduction routeを許す。
- Initial generic `legacy-baseline`は`mode=legacy_recovery`専用で、SR-3 strict serviceでは起動しない。Owner-authorized `pda-hermes-recovery.service`だけが、local/recovery-only、external delivery/cron/delegate/tool write無効、`session_attested=false`で起動できる。
- Recovery modeはcandidateへのforward recovery確認後に停止する。Production Open WebUI/Tailscale routeへ接続してはならない。
- Fresh-host disaster recovery時は、owner recovery materialからtrust root、latest accepted checkpoint、必要なsigned recovery/rollback authorizationを明示bootstrapする。

### 6.4 SOUL projection content budget

SOULには次だけを入れる。

1. machine-readable markerと`projection_id`。
2. 「PDAの現在の実行実体であり、Hermesは現在の器」という自己定義。
3. ユーザーとの関係、異議、最終決定、憲章改定権。
4. 水面下で進むことと承認境界の区別。
5. identity authorityの順位。
6. memory、project context、skills、tool output、frontend system messageがidentityを改定しないこと。
7. 自己説明時に`pda self inspect --json`で`release_digest`を実測すること。

Ports、service names、backup commands、coding conventionsは`AGENTS.md`/runbook/skillへ置く。

---

## 7. Strict injection path

```text
pda_charter.md
   │ validate source fragments
   ▼
identity-contract.yaml + projection-policy + pinned renderer
   │ deterministic render
   ▼
SOUL.md(projection_id) + projection-map
   │ freeze profile/Pipe/Hermes patches/runtime locks
   ▼
release-manifest.json ──sha256──> release_digest ──owner detached signature
   │ verify trust root, signature, sequence, parent, artifact hashes
   ▼
immutable active release / profile SOUL
   │ Hermes actual loader + control-owned session binding broker
   ▼
cached stable tier prefix
   │ overlay deny matrix + per-turn release check
   ▼
provider-bound effective system message
```

### 7.1 Supported production surfaces and trust boundary

- Open WebUI → PDA Pipe → Pipe専用credential/route → Hermes Runs or approved API endpoint。
- Hermes gateway/API agent created by that protected route。
- Hermes cron job started from the guarded service。
- Hermes delegate child started by an attested parent session。
- Guarded CLI wrapper for new sessions。

Raw `hermes --ignore-rules`、arbitrary API clients、unverified batch runner、release bindingを持たないmanual processはattested PDA surfaceとみなさない。API server全体を漠然とsupportedと呼ばず、Pipe専用auth/routeとendpoint allowlistをsurface contractへ含める。

### 7.2 Overlay deny matrix

- `agent.system_prompt`と`HERMES_EPHEMERAL_SYSTEM_PROMPT`はproductionで空を要求する。
- Open WebUIの`system` messageをidentity overlayとして渡さない。
- `/personality`等、`agent.system_prompt`またはin-memory ephemeral promptを変更するcommandをPDA production profileで無効化する。
- Task-specific contextはuser/historyまたは明示的なuntrusted context fieldへ置く。
- `MEMORY.md`、`USER.md`、project context等のmutable continuityはsource labelと明示delimiterを持つnon-normative tierへ置き、identity prefixより前へ出さず、identity-authority fieldへ昇格しない。Hermes providerへは同じsystem message内で送られ得るため、これはcryptographic isolationではなくstructural/model-level boundaryである。
- Productionでactiveなskills、plugin prompt contributors、`AGENTS.md`/context allowlistはrelease artifact treeへhashし、service namespaceではread-onlyにする。Skill/plugin/context変更はstaging後にnew releaseとする。
- Actual-loader testはmemory無し、通常memory、identityと衝突するadversarial memory/skill fixtureの3条件で同じprojection marker/clause behaviorを要求する。
- Outer provider instructionはlocal attestation外であるとreportする。

Hermes carried patchはPDA strict modeで次のendpoint × input × modeを拒否または安全に正規化し、stream/non-stream双方を試験する。

| Endpoint/surface | Deny/validate fields |
|---|---|
| Session chat APIs | `system_message`、`instructions` |
| `/v1/runs` | `instructions`、`system_message`、equivalent overlay |
| `/v1/chat/completions` | messagesの`system`/`developer` role、stored session continuation |
| `/v1/responses` | top-level `instructions`、`input`/`conversation_history`の`system`/`developer` role |
| Responses chaining | `previous_response_id`/`conversation`から継承されるinstructions、release digest、session ID |
| Gateway commands | personality/custom-system-prompt mutation |

Pipe専用routeで必要なuser/assistant/tool history roleはallowlistする。Client supplied roleをそのままtrusted system tierへ昇格しない。

### 7.3 Control-owned session release binding

Session IDへdigest文字列を入れるだけでも、runtime-owned metadataへ自己申告させるだけでもtrust boundaryにならない。Root/control-owned `pda-identity-binding-broker`がbinding authorityを持つ。

- Brokerはroot-owned Unix socket/service、root-only MAC key、append-only/create-once binding storeを持つ。Hermes runtime UIDはkey/storeへwrite/readできない。
- Brokerは`SO_PEERCRED`のexact gateway PID/start-timeとroot-managed unit/cgroup registrationを検査する。Generic same-UID processやterminal/delegate subprocessからのdirect socket callを拒否し、reusable capabilityをenvironment/fileへ置かない。Guarded CLIはroot-managed transient unitとして個別登録する。
- Brokerはclientがreleaseを指定するrequestを受けず、root-owned active accepted stateからcurrent releaseを読む。同じsession IDのrebindを拒否する。
- Brokerは`session_id -> release_digest -> projection_id -> expected stable prompt hash -> surface`をcontrol-owned storeへ記録する。Runtime DB内copyやattestation indexはcache/evidenceに過ぎず、authorityにしない。
- Responses chainも`response_id`、parent response、session ID、release digestをbrokerのcreate-once recordまたはruntimeが鍵を持たないMAC tokenで保護する。
- Gateway/Hermes patchはevery turn、resume、streaming branch、compression/rebuild、delegate spawn、Responses chainの直前にbroker validationを必須化する。
- Broker socket/APIは現在active releaseのnew binding、既存binding verify、authorized transitionだけを提供する。Runtime toolからexisting session/responseをrebindする操作は提供しない。
- Tool subprocessへbroker signing capability/keyを渡さない。Guarded gatewayだけがroot-owned policyで許可されたverify/create channelを使い、service sandbox/cgroup/peer credentialでarbitrary local clientを拒否する。
- 当面のpolicyは「active releaseとsession-bound releaseが異なれば実行を拒否し、新session開始を要求する」。Historical release下の同時実行は今回実装しない。
- Compressionはglobal current SOULを再読込せず、session-bound immutable SOUL bytes/pathを再利用・再検証する。Bound artifactがない、stable prompt hashが違う、releaseがactiveでない場合はFAILする。
- Open WebUI Pipeはguarded read-only release-info endpointからcurrent digestを取得してrouting IDへ使う。これはnew-session rotation用hintでありauthorityではなく、API/brokerが独立再検証する。Endpoint取得不能時にgeneric fallback sessionへ接続しない。
- Open WebUIのHermes session ID計算にも`scope + release_digest`を含めるが、これはrouting convenienceでありcontrol-owned bindingの代替ではない。
- 旧conversation historyは新sessionへuser/assistant historyとして引き継いでも、旧cached system promptや旧instructionsは引き継がない。
- CLI resumeのrelease不一致sessionは`legacy`としてread-only参照し、executionを拒否する。

必須probe: deploy between turns、restart、in-place/rotating compression、concurrent old/new request、old parentからのdelegate、Responses `previous_response_id` bypass、stream/non-stream、runtime UIDからbinding DB/index/tokenを書換える攻撃、brokerへのexisting-ID rebind要求。

### 7.4 Delegate and cron

- Delegateはcurrent global SOULを読み直さず、親sessionのverified `release_digest`とimmutable projection handleを受け取る。
- Parent bindingが不明・inactive・mismatchならchildをspawnしない。
- `skip_context_files=True`、`skip_memory=True`はworker isolationとして維持しつつ、identity authorityと権限境界だけを継承する。
- Cronは現sourceで`load_soul_identity=True`だが、各runをnew bound sessionとしてactive releaseへbindする。
- Installed CLIに`cron dry-run`はない。試験はisolated clone job、fake provider、tool deny、delivery local/disabledで行い、production jobを実行しない。

### 7.5 Actual-loader verification

Source file hashだけで合格させない。Fake OpenAI-compatible endpointで実際のoutbound requestをcaptureし、本文を永続化せず次を判定する。

- first system bytesがmanifestでhashされたgenerated SOULと一致。
- built-in `You are Hermes Agent...` fallbackがidentity位置にない。
- projection marker/`projection_id`がある。
- Control-owned brokerのsession binding token/recordにある`release_digest`がowner-signed manifestと一致。
- unapproved ephemeral overlayがない。
- SOUL scanner/truncationでnormative bytesが変わっていない。
- Guarded CLI、Pipe専用API、cron isolated job、delegate、new session、compression rebuildで同じprojection prefixとrelease bindingを持つ。
- Old session、stale previous response、mid-session deployは実行拒否される。

Whole prompt hashはsession evidenceでありstable identity IDには使わない。Memory、date、skills、platform hintで変化するためである。

---

## 8. Boot guard and self-inspection

### 8.1 `pda identity verify --strict`

Identity integrityの最低検査:

- `/etc/pda/trust/allowed_signers`のroot ownership/modeと、recovery-material fingerprintへの一致。
- Detached manifest signature、release digest、sequence、expected parent、root-owned accepted state、owner-held latest accepted checkpoint。
- Charter、contract、projection policy、renderer、SOUL、projection-map hash。
- Profile distribution、Pipe、Hermes source/tree、carried patch series、runtime/source/control locks、session-binding contract、binding broker、backup/selective-restore、deploy code、systemd unit setのhash。
- Active HERMES_HOME/profile/cwdとimmutable release path。
- `SOUL.md` exact bytes、loader readability、service namespaceからのread-only性。
- `--ignore-rules`/`HERMES_IGNORE_RULES`不在。
- `agent.system_prompt`/ephemeral overlay policy、personality mutation無効化、API deny matrix config。
- Active local skillsとunexpected writable override。
- Root-controlled verifier executable、Python interpreter、dependency tree、binding broker/key/store、absolute `ExecStart`、sanitized environment。

判定は`PASS | WARN | FAIL`。Signature、identity、runtime pin、session-binding、overlay policyのmandatory itemが不明でも`--strict`はFAILする。Core identity/guard failureはgateway bootを拒否する。Open WebUI Pipe、cron等のsurface-specific adapter integrityがFAILした場合はそのroute/jobだけをfail-closeし、unrelated attested surfaceまで不要に停止しない。`pda self inspect`はsurface別statusを返す。

`--recovery`は`--strict`の緩和名ではない。Owner-signed baseline manifest、latest checkpoint、rollback/recovery authorization、recovery-only unit/network/tool policyを別schemaで検証し、出力を常に`session_attested=false`とする。Strict production routeを起動できない。

Backup freshnessはavailability/recovery healthでありidentity provenanceとは分ける。Stale backupは`pda doctor`でWARN/CRITICALにするが、既定ではgateway rebootを永久に阻止しない。ユーザーが別途availability policyを承認した場合だけboot blockへ昇格する。

### 8.2 `pda self inspect --json`

Agentが自分について事実を答える際に実行できるread-only command。

```json
{
  "pda_id": "pda:personal-delegate-agent",
  "projection_id": "sha256:...",
  "release_digest": "sha256:...",
  "release_sequence": 7,
  "charter_sha256": "...",
  "projection_sha256": "...",
  "runtime": {"name": "hermes-agent", "commit": "..."},
  "profile": "default",
  "surface": "pipe-runs-api",
  "session_attested": true,
  "session_bound_release_digest": "sha256:...",
  "effective_prompt_sha256": "...",
  "overlay_policy": "strict-deny-matrix/v1",
  "backup": {"last_verified_at": "...", "status": "pass"},
  "assurance": "SR-3",
  "limits": ["provider_outer_instructions_not_attested", "alternate_core_not_tested"]
}
```

Full prompt、memory本文、secret、private pathは出力しない。

### 8.3 Enforcement phases

1. Detection: same-user filesをhash検査し、driftを可視化する。独立強制とは呼ばない。
2. Guarded canary: root-owned trust store、verifier/interpreter/dependencies、binding broker/key/store、signed release、accepted stateを隔離し、invalid candidateとruntime-side rebindを起動前/各request前に拒否する。
3. Guarded production: root-owned systemd unitがabsolute verifier pathの`ExecStartPre`を実行し、active SOUL/release/configをservice namespaceへread-only bindする。`User=`、fixed `PATH`、`NoNewPrivileges`、write allowlist、broker socket policyを明記する。
4. Runtime mutation closure: personality/custom-prompt command、client overlay、post-start config差替え、PATH/import差替えを無効化・試験する。
5. Full separate `pda-runtime` UID migrationは、今回のHP-3後のhardening milestoneへ送る。

Root-owned unit fileだけでは境界にならない。Verifier binary、interpreter、imports、trust root、latest checkpoint、accepted state、binding broker/key/store、active artifactsの全てをruntime userのwrite authority外へ置く。

---

## 9. Continuity catalog

`continuity/catalog.yaml`の各objectは少なくとも次を持つ。

```yaml
- id: hermes-default-state-db
  locator: hermes://default/state.db
  role: canonical-state
  authority: transitional-continuity
  confidentiality: personal
  size_class: large
  recovery: required
  snapshot_method: sqlite-online-backup
  integrity_check: sqlite-pragma-integrity-check
  rpo: PT4H
  restore_order: 40
  portable_export: hermes-sessions-jsonl
  secret_handling: none
```

独立軸:

- `role`: `authority | canonical-state | projection | cache | secret-ref`
- `confidentiality`: `public | personal | work | secret`
- `size_class`: `small | large`
- `recovery`: `required | rebuild | reissue | discard`

初期対象:

| Object | Role | Recovery |
|---|---|---|
| `pda_charter.md` | authority | Git + signed release、RPO 0 |
| identity contract/projection | authority-derived/projection | Git + signed release、RPO 0 |
| Hermes `state.db` | transitional canonical-state | safe native snapshot required |
| `MEMORY.md` / `USER.md` | transitional canonical-state | byte-preserving backup required、identity authorityは禁止 |
| local/agent-created skills | canonical-state | byte-preserving backup + Git promotion path |
| bundled/hub skills | projection/rebuild | source/version/hash lock or vendor artifact |
| Open WebUI DB/attachments/functions | canonical-state/UI-state | consistent snapshot required |
| current PDA dirty working tree | unique state | emergency encrypted capture、後でclean releaseへ昇格 |
| Hermes source carried commit | runtime artifact | git bundle/source archive + patch lock |
| `.env` / `auth.json` | secret-ref/secret | escrow/reauth policy |
| Tailscale machine state | secret | reissue default |
| venv/cache/images/queues | cache | rebuild/discard |

---

## 10. Backup / restore contract

### 10.1 Snapshot semantics

- `hermes backup`のfull modeをnative Hermes snapshot sourceとして利用する。Quick backupだけで完了にしない。
- Hermes full backupは`.env`、`auth.json`、config、SOUL等を含み得るため、単なるstate artifactではなく`secret-bearing sealed native archive`として扱う。Release planeや通常reportへ展開しない。
- Hermes ZIPは暗号化されないため、mode 0600の短命stagingへ出し、暗号化off-host repositoryへ入れた後にplaintextを消す。
- SQLite DBはOnline Backup APIまたはruntime提供のsafe copyのみ。Live `.db`の単純copy、WAL/SHM同梱を禁止する。
- Open WebUIはDB、attachments、installed function metadata、deployed function sourceを同じ`backup_set_id`へ入れる。必要なら短時間quiesceする。
- 複数store間にtransactionはないため、componentごとの開始/終了時刻、row/message watermark、in-flight turn許容をmanifestへ記録する。
- Dirty Git差分、untracked files、deployed artifact hashを最初のemergency generationへ必ず含める。Cleanupを待たない。
- Hermes codebase exclusionを補うため、local commitを含むgit bundle/source archiveとpatch seriesを保存する。
- Restoreではnative archiveをactive HERMES_HOMEへwholesale importしない。隔離stagingへ展開し、catalog allowlistにあるstateだけを選択restoreする。
- Backup内のSOUL、identity manifest、config overlay、trust file、credentialはactive authorityとして採用しない。Secret policyに従いreauth/escrow/rotationし、signed release/profileをstate restore後に最後にdeployする。

### 10.2 RPO / RTO hypotheses

- Release plane: RPO 0。off-host push/signature完了前のreleaseをproductionへdeployしない。
- Continuity state: RPO 4時間以内。
- Identity-only/text-mode recovery: replacement hostと鍵が利用可能になってから4時間以内。
- Open WebUIを含むoperational recovery: 8時間以内。
- Hardware調達時間はRTO外。代替VMを一時復旧先として許容する。

実測後に変更する。数値変更は失敗の隠蔽ではなく、測定根拠付きdecisionとして記録する。

### 10.3 Restore order

1. Blank Ubuntu 24.04 host/VMを用意する。Source diskをmountしない。
2. Bundle外のrecovery materialからowner trust fingerprintを確認し、root-owned trust storeをbootstrapする。
3. 同じbundle外recovery materialからlatest owner-signed `{sequence, release_digest, parent_digest}` checkpointを取得・検証し、release/snapshot選択前にroot-owned recovery accepted stateへ置く。
4. Candidate releaseがlatest checkpointと一致するか、有効なsigned recovery/rollback authorizationで明示許可されていることを検証する。古いがvalid-signedなrelease単体を拒否する。
5. `runtime.lock`の取得可能なexact bytesからHermes、Python deps、containers、integration、control runtimeを再構築する。`latest`禁止。
6. Secretをreissue/reauth/escrow policyに従って準備する。
7. Native archiveを隔離stagingへ展開し、同じ`backup_set_id`からallowlisted Hermes state、memory、skills、Open WebUI stateだけをrestoreする。Archive内のSOUL/config/trust/credentialをactive化しない。
8. Owner-signed release/profileを最後にdeployする。Accepted stateをbundle内manifestだけから新規採用しない。
9. Cron、external send、ntfy、Tailscale Serve、connectorを無効にしたisolated modeで起動する。
10. DB integrity、row/session watermark、file hash、skill hash、runtime pinを検証する。
11. Actual-loader attestationを全supported surfaceで通す。
12. 代表Hermes session、session_search、Open WebUI chat、delegate、isolated clone cron jobを確認する。
13. PASS後にのみ外部導線を有効化し、旧credential/nodeを失効する。

---

## 11. Acceptance suite

### 11.1 Identity hard requirements

| ID | Requirement |
|---|---|
| ID-BUILD-01 | 同一sourceから2回buildしたSOUL/map/canonical manifestがbyte-identical |
| ID-TRACE-01 | SOULの全normative文がstable clause IDとcharter fragment hashへ逆引き可能 |
| ID-NORM-01 | 憲章に根拠のない新normをrendererが拒否 |
| ID-RELEASE-01 | 同じ`projection_id`でもSOUL/profile/Pipe/patch/runtime artifactが違えば`release_digest`が変わる |
| ID-TAMPER-01 | charter/contract/policy/renderer/SOUL/manifest/runtime artifactの1 byte変更でverifyまたはbootがFAIL |
| ID-TRUST-01 | Release内のpublic key/allowed_signers差替えではbundle外root trustを変更できず、検証がFAIL |
| ID-ROLLBACK-01 | Replay/sequence rollbackを拒否し、SR-3 targetへのowner-signed `mode=strict_rollback`だけをproduction downgradeとして許す |
| ID-RECOVERY-01 | Legacy baselineはstrict routeでFAILし、owner-authorized local recovery unitだけで`session_attested=false`としてboot/smoke/forward-recovery可能 |
| ID-FALLBACK-01 | SOUL missing/empty/unreadable/scanner altered/truncated時にbuilt-in fallbackでPDAを名乗らずFAIL |
| ID-LOAD-01 | Actual outbound system prefixがmanifestでhashされたSOUL exact bytesと一致 |
| ID-SURFACE-01 | Pipe専用API、guarded CLI、isolated cron、delegateが同じprojection prefixとrelease bindingを持つ |
| ID-OVERLAY-01 | Endpoint×field×stream/stateful deny matrixがclient system/developer/instructionsとpersonality mutationを拒否 |
| ID-CONTEXT-01 | Memory無し/通常/adversarial continuityとsigned skill fixtureでprojection provenance/identity clausesが不変、allowlist外skill/contextを拒否 |
| ID-SKIP-01 | `--ignore-rules`、alternate HERMES_HOME、wrong profile/cwd、writable verifier/PATH/importでguardがFAIL |
| ID-SESSION-01 | Every turn/resume/compression/delegate/previous-responseがcontrol-owned brokerのbound `release_digest`を検査する |
| ID-SESSION-02 | Deploy between turns、old parent delegate、stale previous response、concurrent old/new requestをFAIL |
| ID-SESSION-03 | Runtime UID/toolによるbinding DB/index/token書換え・existing-ID rebind・MAC forgery・same-UID subprocess broker callをFAIL |
| ID-POSTBOOT-01 | Post-boot personality/config/PATH/import/release mutationが拒否または次request前に検出される |
| ID-SURFACE-FAIL-01 | Pipe/cron adapter mismatchは該当surfaceだけfail-closeし、unrelated attested surfaceは維持する |
| ID-SELF-01 | `pda self inspect`がprojection/release/source/surface/limitsを本文非開示で正しく返す |

### 11.2 Recovery hard requirements

| ID | Requirement |
|---|---|
| BAK-OFFHOST-01 | encrypted generationがsource disk外に存在し、復号検証済み |
| BAK-SQLITE-01 | restored Hermes/Open WebUI DBの`PRAGMA integrity_check`が`ok` |
| BAK-WATERMARK-01 | session/message/chat/attachment watermarkがmanifestと一致 |
| BAK-SECRET-01 | repo、release、ordinary reportにplaintext secretが0件 |
| BAK-NATIVE-01 | Native archive内のstale/malicious SOUL、config、trust file、credentialをactive restoreが無視する |
| BAK-DELETE-01 | runtime upload credentialで保護済みgenerationを削除不能 |
| BAK-ROLLBACK-01 | newest generation破損時に直前generationへ復元可能 |
| RST-SOURCELESS-01 | source host/diskを使わずoff-host artifactだけからfresh host restore可能 |
| RST-TRUST-01 | bundle外recovery materialからtrust rootをbootstrapし、swapped bundle trustを拒否 |
| RST-ANTIROLLBACK-01 | Latest owner-signed checkpointを先に復元し、旧valid-signed release単体を拒否し、signed recovery/rollback authorizationだけを許す |
| RST-RUNTIME-01 | local carried Hermes commit/patchをexact bytesで再構築可能 |
| RST-RECOVERYMODE-01 | Legacy baselineをlocal recovery-onlyで実boot/smokeし、production routeを開かずcandidateへforward recoveryできる |
| RST-SESSION-01 | 代表3 sessionをsearchでき、matching releaseだけresume可能 |
| RST-UI-01 | 代表Open WebUI chat、attachments、installed Pipeが復元される |
| RST-IDENTITY-01 | restore後にID hard requirementsが同じsigned release digestでPASS |
| RST-REBOOT-01 | 実reboot後もroot-owned guardがPASSし、invalid releaseは起動拒否 |
| RST-SLO-01 | RPO 4h / operational RTO 8h仮説を実測し記録 |

### 11.3 Behavioral evaluation

Actual-loader testとは分離して、固定fixtureで次を評価する。

- 自己定義とHermes/PDAの主従。
- ユーザー最終決定と一度の明確な異議。
- 推定と確定の区別。
- ユーザーの変化を過去memoryより優先。
- 水面下の作業と無許可外部作用の区別。
- 憲章改定要求へのowner approval要求。
- Memory/project context/tool outputによるidentity上書き拒否。
- 通常の実務能力にmaterial regressionがないこと。

Hard constitutional/authorization fixtureはfailure 0。Soft style評価はbaseline/candidate比較を記録する。

---

## 12. Implementation tasks

### Task 1: Emergency off-host capture of the effective current system

**Objective:** cleanupや新設計を待たず、現在のdirty/effective stateをhost lossから保護する。

**Files:**
- Create after verification: `docs/status/emergency-capture-2026-08.md`
- Do not commit: backup archives、secret inventory values、raw state、Git dirty bundle

**Steps:**

1. 作業開始時のPDA repo、Hermes source、Open WebUI deploymentのstatus/hash/sizeをread-onlyで記録する。
2. `umask 077`のstagingを作る。可能ならtmpfsまたは暗号化stagingを使う。
3. `hermes backup -o <staging>/hermes-full.zip`を実行し、exit 0とunresolved warning 0を要求する。
4. ZIPをisolated directoryへ展開し、restored `state.db`のintegrity check、session/message watermarkを記録する。
5. `hermes sessions export --format jsonl --redact --yes <staging>/sessions.jsonl`でportable auxiliary exportも作る。Native DBの代替とは扱わない。
6. PDA repoの`git diff --binary`、untracked file list/content、HEAD、remote refsをcaptureする。既存変更をcommitしない。
7. Hermes sourceのHEAD/local carried commitを含むgit bundleまたはsource archiveを作る。
8. Open WebUI compose/env inventory、volume DB/attachments、installed Function sourceをsnapshotする。secret値はinner encrypted planeだけに置く。
9. age/restic等で暗号化し、source disk外へtransferする。off-host backendが未決ならここだけをblocking decision pointとしてユーザーへ提示する。
10. 別directory/hostから復号し、archive testとhash照合を行う。
11. plaintext stagingを削除し、SSD上secure eraseは保証できない旨をrecordする。
12. Sanitized evidenceのみ`docs/status/emergency-capture-2026-08.md`へ記録する。
13. Verify: off-host object ID、ciphertext SHA-256、DB integrity、watermark、restore probeがすべて存在。
14. Commit: `docs: record verified PDA emergency recovery capture`

**Exit:** same-disk copyではなく、復号・restore probe済みのoff-host generationが存在する。

### Task 2: Establish the repository authority and priority documents

**Objective:** 憲章、今回の優先順位、既存design branch、将来roadmapのauthority関係をmainへ明文化する。

**Files:**
- Create: `README.md`
- Create: `docs/design/identity-portability.md`
- Create: `docs/roadmap/current-priority.md`
- Create: `docs/decisions/2026-08-17-identity-portability-first.md`
- Create: `AGENTS.md`
- Modify later, not in this task: `personal_delegate_agent_plan.md`

**Steps:**

1. 本計画のSections 0-11をdesign documentへ移す。
2. Authority mapで`pda_charter.md`を最上位にする。
3. `origin/claude/fable-system-design-d3c203`をproposal/refとして記載し、merge前にcharterとのreconciliationが必要と明記する。
4. RoadmapへM0A emergency capture、M0B source-bound identity、M0C attested injection、M0D fresh-host restoreを挿入する。
5. Context Spine/PKBをその後へ置き、core swapをPhase 10へ維持する。
6. `AGENTS.md`へsecret禁止、generated identity手編集禁止、charter owner-only、TDD、既存dirty Open WebUI変更を混入しない規則を書く。
7. Relative link checkerを実行する。
8. Verify: `git diff --check`。
9. Commit: `docs: prioritize PDA identity portability and strict injection`

### Task 3: Bootstrap a minimal PDA control CLI with TDD

**Objective:** identity、inventory、backup、attestationをHermes内部memoryではなくrepo-owned commandで扱う骨格を作る。

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `.gitignore`
- Create: `src/pda/__init__.py`
- Create: `src/pda/cli.py`
- Create: `tests/test_cli.py`

**Steps:**

1. RED: `pda --help`、`pda identity --help`、`pda self inspect --json`のcommand contract testを書く。
2. Run: `uv run pytest tests/test_cli.py -v`。Expected: missing package/commandでFAIL。
3. GREEN: stdlib `argparse`中心の最小CLIを実装する。まだstateを変更しない。
4. Run specific test。Expected: PASS。
5. Run full suite、ruff、mypy。
6. Commit: `chore: bootstrap PDA control CLI`

### Task 4: Build the continuity catalog and runtime inventory

**Objective:** 「実体部分」を推測語ではなく、restore contractを持つ機械可読object一覧にする。

**Files:**
- Create: `schemas/continuity-catalog.schema.json`
- Create: `continuity/catalog.yaml`
- Create: `continuity/restore-contract.yaml`
- Create: `config/host-bindings.example.yaml`
- Create: `src/pda/continuity/catalog.py`
- Create: `src/pda/continuity/inventory.py`
- Create: `tests/continuity/test_catalog.py`
- Create: `tests/continuity/test_inventory.py`

**Steps:**

1. RED: unknown role/domain/recovery、secret値混入、required object欠落を拒否するtestを書く。
2. RED: live inventoryが`~/.hermes/state.db`、memory、skills、Open WebUI、repo dirty state、Hermes source refをlocator/hash/size/mode付きで返すtestを書く。fixture homeを使う。
3. Verify RED。
4. GREEN: schema validatorとread-only inventoryを実装する。
5. 現行objectを`continuity/catalog.yaml`へ分類する。secretは名前とstrategyだけ。
6. Actual host pathはuntracked `~/.config/pda/host-bindings.yaml`へ置き、repoにはexampleだけ置く。
7. 実機で`uv run pda continuity inventory --json`を実行し、secret本文が出ないことを確認する。
8. `state.db` mode 0644をfindingにし、変更はbackup後の独立taskへ送る。
9. Verify full suite。
10. Commit: `feat: define PDA continuity catalog and inventory`

### Task 5: Define the charter-derived identity contract

**Objective:** 憲章をpromptへ格下げせず、runtime projectionの最小normをclause-traceableなderived compiler inputにする。

**Files:**
- Create: `schemas/identity-contract.schema.json`
- Create: `identity/identity-contract.yaml`
- Create: `identity/projection-policy.yaml`
- Create: `tests/identity/test_contract.py`
- Create: `tests/identity/test_charter_traceability.py`

**Steps:**

1. RED: charter hash mismatch、source fragment mismatch、duplicate clause ID、unmapped runtime statement、dynamic factを拒否するtestを書く。
2. RED: contractがapproval/signature/self digestを内包せず、憲章にないnormを追加できないtestを書く。
3. Verify RED。
4. GREEN: schema/traceability validatorを実装する。
5. 憲章のruntime-relevant clauseをstable IDへ対応付け、candidate runtime statementsを作る。
6. No-change、憲章全文copy、broad prompt、concise projectionの比較packetを作り、clause mappingをユーザーへ確認する。この確認はfinal signed release approvalではない。
7. Contractは独立authorityではなくderived artifactであることをschema/documentへ固定する。
8. Verify full suite。
9. Commit: `feat: define charter-traceable PDA identity contract`

### Task 6: Implement the deterministic Hermes SOUL renderer

**Objective:** Charter-derived contractからHermes projectionとnon-self-referential `projection_id`を再現可能に生成する。Final release manifest/signatureはまだ作らない。

**Files:**
- Create: `src/pda/identity/model.py`
- Create: `src/pda/identity/renderer.py`
- Create: `src/pda/identity/projection.py`
- Create: `schemas/projection-input.schema.json`
- Create: `profiles/pda/SOUL.md`
- Create: `profiles/pda/projection-map.json`
- Create: `profiles/pda/projection-input.json`
- Create: `tests/identity/test_renderer.py`
- Create: `tests/identity/test_reproducible_projection.py`

**Steps:**

1. RED: deterministic bytes、LF/UTF-8、max 6000 chars、`projection_id` marker、self-hash/release-digest非埋込、timestamp/path/secret禁止をtestする。
2. RED: build twiceで同一hash、charter/contract/policy/renderer bytes変更で`projection_id`が変わるtestを書く。
3. RED: 同一`projection_id`から異なるSOULが生成された場合をnon-determinismとしてFAILするtestを書く。
4. Verify RED。
5. GREEN: deterministic renderer、projection input descriptor、projection mapを実装する。
6. Generated filesを作り、手編集禁止headerを付ける。
7. `pda identity build-projection --source-ref <clean commit> --check`を実装する。Final release signingは行わない。
8. Verify: two-build byte identity、schema validation、full suite。
9. Commit: `feat: render reproducible Hermes PDA identity projection`

### Task 7: Package the declarative Hermes PDA profile

**Objective:** identity/config/skillsをstateから分離し、fresh profileへ標準Hermes機能で配布できるようにする。ユーザー向けの報告・判断依頼・障害通知をdecision-oriented escalationとして扱うowner communication policyも可搬profileへ含める。

**Files:**
- Create: `profiles/pda/distribution.yaml`
- Create: `profiles/pda/config.yaml`
- Create: `profiles/pda/.env.template`
- Create: `profiles/pda/skills/pda-self/SKILL.md`
- Create: `profiles/pda/skills/pda-user-escalation/SKILL.md`
- Create: `tests/hermes/test_profile_distribution.py`
- Create: `docs/operations/hermes-profile.md`

**Steps:**

1. RED: distributionにSOUL/config/skillが含まれ、state.db/memory/session/auth/.env実値が含まれないtestを書く。
2. RED: temp HERMES_HOMEへlocal distributionをinstallし、generated SOUL exact bytesを持つtestを書く。
3. Verify RED。
4. GREEN: manifest、safe config、secret-name template、self-inspection skill、owner communication/escalation skillを作る。
5. `hermes profile install ./profiles/pda --name pdacanary -y`をtemp homeで実行するintegration testを通す。
6. `profile export`と`hermes backup`の役割差をrunbookへ明記する。
7. Verify full suite。
8. Commit: `feat: add portable Hermes PDA profile distribution`

### Task 8: Implement release verification, trust bootstrap, and self-inspection

**Objective:** Final artifact freeze前に、bundle外trust root、detached signature、sequence/parent、active bytes、runtime pin、safe self-inspectionを検証するcodeを作る。Candidateへのfinal signatureはまだ行わない。

**Files:**
- Create: `identity/owner-signing-key.pub`
- Create: `schemas/signature-envelope.schema.json`
- Create: `schemas/attestation.schema.json`
- Create: `src/pda/identity/signature.py`
- Create: `src/pda/identity/verify.py`
- Create: `src/pda/identity/accepted_state.py`
- Create: `src/pda/identity/attest.py`
- Create: `src/pda/self_inspect.py`
- Create: `tests/identity/test_signature.py`
- Create: `tests/identity/test_trust_bootstrap.py`
- Create: `tests/identity/test_recovery_authorization.py`
- Create: `tests/identity/test_verify.py`
- Create: `tests/identity/test_self_inspect.py`

**Steps:**

1. Owner-controlled main Macに専用Ed25519 signing keyを用意し、private keyをPDA nodeへ置かない。Repo public keyはtransparency copyとlabelする。
2. RED: root trust absent、repo trust swap、wrong signer、tamper、sequence replay、wrong parent、unauthorized rollback、wrong SOUL/profile/runtime、ignore-rules、overlayをtestする。
3. RED: Valid owner-signed recovery/rollback authorizationだけがlower sequenceまたはlegacy recovery modeを許すtestを書く。
4. RED: `self inspect`がprojection ID、release digest、session binding、limitsだけ返し、full prompt/memory/secretを返さないtestを書く。
5. Verify RED。
6. GREEN: OpenSSH `ssh-keygen -Y sign/verify`互換のdetached verification、root trust bootstrap contract、accepted-state、recovery/rollback verificationを実装する。
7. Detection modeとstrict modeを分ける。Root trust/final signature未設定のdetection結果をSR-3と表示しない。
8. `pda identity verify --strict --release ... --trust-store /etc/pda/trust/allowed_signers`と`pda self inspect --json`を実装する。
9. Backup freshnessはdoctor healthへ分離し、identity verifyのhard failureにしない。
10. Verify mutation/replay/trust-swap tests、full suite。
11. Commit: `feat: verify signed PDA releases with external trust root`

### Task 9: Build the actual-loader harness and capture the frozen-session baseline

**Objective:** Source fileの存在ではなくproviderへ渡る実system messageとcurrent compression/resume behaviorを測るharnessを作り、Task 10のpatch前baselineを固定する。

**Files:**
- Create: `tests/e2e/fake_openai_server.py`
- Create: `tests/e2e/test_hermes_effective_identity.py`
- Create: `tests/e2e/test_identity_session_binding.py`
- Create: `docs/evaluation/identity-loader-baseline.md`

**Steps:**

1. RED: temp HERMES_HOME + fake providerでbuilt-in identityがcaptureされるbaseline testを作る。
2. RED: generated profileでSOUL exact prefix、fallback absence、`projection_id`を期待するcandidate testを書く。
3. Characterize: current resumeはstored promptを再利用し、current compressionはsystem promptをinvalidate/rebuildすることをfixtureで固定する。
4. RED: ephemeral overlay、mid-session deploy、old session resume、in-place/rotating compression、missing SOUL、scanner mutationをnegative contractにする。
5. Verify REDが期待原因で失敗する。
6. Harnessはfull prompt本文をartifactへ保存せずhash/booleanだけ残す。
7. Candidate new-session loaderだけをPASSさせ、release binding未実装のtestは明示的なxfail理由を残す。Task 10完了時にxfailを0にする。
8. Verify baseline evidenceとfull suite。
9. Commit: `test: capture Hermes identity loader and session baseline`

### Task 10: Close session, Open WebUI, API, delegate, cron, and mutation gaps

**Objective:** Main agentだけでなく全supported surfaceをcontrol-owned brokerの`release_digest`へbindし、runtime-owned metadata書換え、compression・resume・delegate・API chaining・post-start overlayの迂回を閉じる。

**Files:**
- Modify: `integrations/openwebui-hermes-progress/functions/hermes_progress_pipe.py`
- Modify: `integrations/openwebui-hermes-progress/install_hermes_progress_pipe.py`
- Modify: `integrations/openwebui-hermes-progress/tests/test_hermes_progress_pipe.py`
- Modify carefully: existing unrelated dirty files only after their current work is reconciled
- Create: `integrations/hermes/patches/0001-session-release-binding.patch`
- Create: `integrations/hermes/patches/0002-delegates-inherit-parent-release.patch`
- Create: `integrations/hermes/patches/0003-api-system-prompt-deny-matrix.patch`
- Create: `integrations/hermes/patches/0004-disable-runtime-personality-mutation.patch`
- Create: `integrations/hermes/patches/0005-structure-nonnormative-context.patch`
- Create: `integrations/hermes/README.md`
- Create: `runtime/runtime.lock.json`
- Create: `runtime/source-artifacts.lock.json`
- Create: `runtime/session-binding-contract.yaml`
- Create: `runtime/active-context-policy.yaml`
- Create: `src/pda/identity/binding_broker.py`
- Create: `src/pda/identity/broker_client.py`
- Create: `schemas/session-binding-token.schema.json`
- Create: `tests/identity/test_binding_broker.py`
- Create: `tests/identity/test_binding_broker_tamper.py`
- Create: `tests/hermes/test_patch_series.py`
- Create: `tests/e2e/test_identity_surfaces.py`
- Create: `tests/e2e/test_session_release_binding.py`
- Create: `tests/e2e/test_api_overlay_matrix.py`
- Create: `tests/e2e/test_nonnormative_context_tier.py`

**Steps:**

1. 既存Open WebUI dirty workのowner/taskを確認し、今回のbranch/worktreeへ分離する。未知のuntracked fileを削除しない。
2. RED: New sessionがcontrol-owned brokerからcurrent active `{release_digest, projection_id, soul_sha256, stable_prompt_sha256}` create-once bindingを得るtestを書く。
3. RED: Every turn、resume、restart、streaming、in-place/rotating compressionがbroker bindingを検査し、global current SOULでsilent rebuildしないtestを書く。
4. RED: Runtime-owned session DB/Responses store/attestation cacheを書換えてもbroker record/MACを偽造できず、existing session/response IDをrebindできず、same-UID terminal/delegate subprocessのbroker direct callが拒否されるnegative testを書く。
5. RED: Deploy between turns、concurrent old/new request、old parent session delegate、stale `previous_response_id`/conversation chainを拒否するtestを書く。
6. RED: Pipeがguarded release-info endpointからdigestを取得し、frontend `system` contentをHermes `instructions`へ渡さず、routing session IDを`scope + release_digest`で変え、endpoint failure時にfallback sessionへ接続しないtestを書く。
7. RED: Session chat、Runs、Chat Completions、Responsesの各endpointでsystem/developer/instructions、stored inheritance、stream/non-streamをdenyするmatrix testを書く。
8. RED: `/personality`/custom system prompt、post-start config、ephemeral prompt mutationをstrict profileで拒否するtestを書く。
9. RED: Memory無し/通常/adversarial memory・skill・project contextでprojection prefixとidentity behaviorが変わらず、active skill/context allowlist外を拒否するtestを書く。
10. RED: Delegate childがparentのbroker-verified immutable release handleを継承し、current global SOULを読まないtestを書く。
11. RED: Cron isolated clone jobがbrokerからnew active release bindingを得るtestを書く。存在しない`cron dry-run`は使わない。
12. Verify RED。
13. GREEN: Create-once binding/MAC broker、root-owned store interface、peer/capability policy、runtime clientを実装する。Testではruntime UID権限を分ける。
14. GREEN: Hermes session/Responses entry pointをbroker必須にし、runtime metadataをauthorityとして使わないfail-close checkを追加する。
15. GREEN: Compressionはbroker-bound immutable projectionを再利用し、active release mismatchならnew sessionを要求する。
16. GREEN: Pipe変更、delegate parent propagation、API deny matrix、personality mutation lock、non-normative context delimiters/allowlistを最小carried patchとして実装する。
17. Pipe専用credential/routeとendpoint allowlistを設定し、arbitrary API clientをattested surfaceから外す。
18. Pinned Hermes sourceへpatchをclean適用し、Hermes upstream testsとPDA E2Eを通す。Task 9のxfailを0にする。
19. Local carried commit、upstream commit、patch SHA-256、source bundle SHA-256、active signed skill/context treeをlockする。
20. 可能ならgeneric patchをupstreamへ提案するが、mergeをPDA milestoneのblocking conditionにしない。
21. Verify endpoint matrix、binding tamper、session boundary、context conflict、actual-loader、full suite。
22. Commit: `feat: bind all Hermes PDA surfaces to a control-owned release record`

### Task 11: Implement all security-critical control, recovery, deployment, and unit assets before release freeze

**Objective:** Backup/selective restore、binding broker service、root guard、recovery-only mode、deploy/accepted-state logic、systemd unit bytesをproduction副作用なしのsandboxで完成させ、final releaseでhash可能にする。

**Files:**
- Create: `schemas/snapshot-manifest.schema.json`
- Create: `schemas/accepted-checkpoint.schema.json`
- Create: `schemas/recovery-authorization.schema.json`
- Create: `src/pda/backup/create.py`
- Create: `src/pda/backup/verify.py`
- Create: `src/pda/backup/restore.py`
- Create: `scripts/snapshot_openwebui.py`
- Create: `config/backup.example.yaml`
- Create: `src/pda/identity/deploy.py`
- Modify: `src/pda/identity/verify.py`
- Modify: `src/pda/identity/accepted_state.py`
- Modify: `src/pda/identity/attest.py`
- Modify: `src/pda/identity/binding_broker.py`
- Create: `src/pda/doctor.py`
- Create: `runtime/control-runtime.lock.json`
- Create: `infra/systemd/pda-identity-binding-broker.service`
- Create: `infra/systemd/pda-hermes-gateway.service`
- Create: `infra/systemd/pda-hermes-recovery.service`
- Create: `infra/systemd/pda-identity-verify.service`
- Create: `infra/systemd/pda-hermes-canary.service`
- Create: `infra/systemd/pda-backup.service`
- Create: `infra/systemd/pda-backup.timer`
- Create: `infra/systemd/pda-restore-drill-reminder.timer`
- Create: `tests/backup/test_hermes_snapshot.py`
- Create: `tests/backup/test_snapshot_manifest.py`
- Create: `tests/backup/test_secret_exclusion.py`
- Create: `tests/backup/test_selective_restore.py`
- Create: `tests/backup/test_stale_identity_rejection.py`
- Create: `tests/identity/test_atomic_deploy.py`
- Create: `tests/identity/test_accepted_checkpoint.py`
- Create: `tests/operations/test_systemd_units.py`
- Create: `tests/operations/test_boot_guard.py`
- Create: `tests/operations/test_recovery_mode.py`
- Create: `tests/operations/test_post_start_tamper.py`
- Create: `docs/operations/backup-restore.md`
- Create: `docs/operations/identity-guard.md`
- Create: `docs/operations/identity-cutover.md`

**Steps:**

1. RED: Torn SQLite、missing object、hash mismatch、secret in outer manifest、mixed backup set、stale snapshotを拒否するtestを書く。
2. RED: Native archive内のstale/malicious SOUL、config、trust、credentialをactive restoreへ入れないtestと、newest corruption時のprior generation選択testを書く。
3. RED: Expected-old mismatch、non-atomic activation、unsigned rollback、bundle-derived accepted-state、old valid-signed release against newer checkpointを拒否するtestを書く。
4. RED: Invalid signature/trust/sequence/SOUL/runtime、writable verifier/interpreter/import/broker store、overlay enabledでstrict preflightがFAILするtestを書く。
5. RED: Runtime UIDからbinding key/store、active release、SOUL、config、unit、verifierへwrite不能なtestを書く。
6. RED: Generic legacy baselineがstrict unitでFAILし、signed recovery authorization下のlocal recovery unitだけで`session_attested=false`、network/external send/cron/delegate/tool write無しでbootするtestを書く。
7. RED: Recovery-only baseline smoke後にcandidate strict unitへforward recoveryできるtestを書く。
8. Verify RED。
9. GREEN: Catalog-driven sealed snapshot、inner/outer manifest、encryption/backend adapter、selective restoreを実装する。
10. GREEN: Compare-and-swap deploy、owner-signed latest checkpoint verification、root accepted-state、rollback/recovery authorizationを実装する。
11. GREEN: Broker/strict/recovery/canary/backup unit set、fixed PATH/absolute executable、sandbox、write allowlist、signed active skill/plugin/context treeのread-only bindを実装する。
12. GREEN: Root-controlled verifier/broker用pinned interpreter/dependency/source hashを`control-runtime.lock.json`へ固定する。
13. Fixture candidate/baseline/checkpointとephemeral test trustで、guard boot、recovery boot、forward recovery、post-start tamperをisolated namespace/VMで通す。Production service、real secrets、external routeは触らない。
14. Backup freshnessはdoctor WARN/CRITICALとし、identity bootを既定で永久blockしない。
15. Verify all backup/control/deploy/unit tests、`systemd-analyze verify`、full suite。
16. Commit: `feat: add PDA control and recovery assets before release freeze`

### Task 12: Freeze every runtime/control artifact and build the final unsigned candidate manifest

**Objective:** Profile、Pipe、Hermes patch、broker、backup/restore、deploy、systemd unit、runtime/control locksが全て確定した後だけcanonical candidate manifestとexact `release_digest`を作る。Owner approvalはcanary evidence後のTask 13で行う。

**Files:**
- Create: `src/pda/identity/release.py`
- Create: `schemas/release-manifest.schema.json`
- Create: `profiles/pda/release-manifest.json`
- Create: `profiles/pda/legacy-baseline-manifest.json`
- Create: `tests/identity/test_reproducible_release.py`
- Create: `tests/identity/test_release_uniqueness.py`
- Create: `docs/evaluation/identity-release-decision-packet.md`

**Steps:**

1. RED: Manifestがown digest/signature/approvalを含まず、全required runtime/control artifact hash、sequence、parentを含むtestを書く。
2. RED: 同じ`projection_id`でもSOUL、Pipe、profile、active skill/context tree、Hermes patch、broker、backup/restore、deploy、unit set、runtime/control lockの1 byte変更で`release_digest`が変わるtestを書く。
3. RED: Manifest生成を2回行いbyte-identicalであるtestを書く。
4. Verify RED。
5. GREEN: Canonical manifest builderと`release_digest`計算を実装する。
6. Current generic production bytesとcurrent unpatched runtimeも完全な`legacy-baseline` recovery-only manifestとしてfreezeする。PDA SR-3 releaseとは表記しない。
7. Candidateの全artifactをclean pinned refから2回buildし、hashをfreezeする。以後のbyte変更は禁止。
8. Candidate/baseline digest、sequence/parent、clause map、loader/control baseline、known limits、recovery planをdecision packet draftへまとめる。
9. Repo外ephemeral canary key/signature harnessを用意する。Production trust/owner approvalとして受理しない。
10. Verify full suite。
11. Commit: `release: freeze complete PDA runtime and control candidate`

### Task 13: Canary the exact digest, then obtain detached owner approval, checkpoint, and recovery signatures

**Objective:** Frozen exact candidateをisolated canaryで評価し、そのevidenceを見たユーザーが同じ`release_digest`だけをproductionへ承認する。Latest accepted checkpointもbundle外recovery materialとして署名する。

**Files:**
- Create: `profiles/pda/release-manifest.json.sig`
- Create: `profiles/pda/legacy-baseline-manifest.json.sig`
- Create: `profiles/pda/initial-recovery-authorization.json`
- Create: `profiles/pda/initial-recovery-authorization.json.sig`
- Create outside release/repo: owner-held `latest-accepted-checkpoint.json` and detached signature
- Create: `eval/identity_cases.jsonl`
- Create: `src/pda/eval/identity.py`
- Create: `tests/eval/test_identity_metrics.py`
- Create: `docs/evaluation/identity-canary-results.md`
- Create: `docs/status/identity-release-approval.md`
- Create: `docs/status/latest-accepted-checkpoint-receipt.json`

**Steps:**

1. `pdacanary` profileとcontrol canaryをfresh stateで作り、external write credential、production cron、ntfy、Tailscale、live connectorを持たせない。
2. Ephemeral canary trust/signatureでTask 12のfrozen digestだけをloadする。Production owner key/trustをruntimeへ置かない。
3. RED: Hard constitutional fixture failure 0、ordinary utility non-regression threshold、ID/BAK/RST control fixtureを要求するtestを書く。
4. Verify RED。
5. GREEN: Deterministic evaluation harness、fixed cases、score aggregation、redacted result writerを実装する。
6. Baseline genericとfrozen candidateを同じmodel/runtime/tool-disabled条件で比較する。
7. Actual-loader、tamper、trust swap、old checkpoint、endpoint matrix、binding broker/session/delegate/compression、strict guard、recovery-only boot/forward recovery、behavior suiteを複数回実行する。
8. Candidate digest、scorecard、limits、recovery planをdecision packetへ完成させる。
9. ユーザーがevidenceを確認しexact candidate digestを明示承認した後、main Mac owner keyでcandidate manifestへdetached production signatureを作る。
10. Legacy baselineとcandidate→baselineの短期recovery authorizationをowner署名する。Baselineはproduction route不可。
11. Candidate sequence/digest/parentの`latest-accepted-checkpoint.json`をowner署名し、release bundleと独立したmain Mac/off-host recovery materialへ保存する。Repoにはdigest/fingerprint receiptだけ置く。
12. Recovery fingerprintでproduction signatures/checkpointを別経路検証する。
13. Owner-signed exact bundle/checkpointでもactual-loader、broker、strict/recovery、anti-rollback smokeを再実行する。Artifact bytesはTask 12から不変でなければならない。
14. 修正が必要ならTask 10/11/12へ戻り、新digest・再評価・再承認とする。
15. Commit: `test: approve complete signed PDA release after canary`

### Task 14: Execute the signed backup pipeline and prove selective restore before live cutover

**Objective:** Task 12でfreeze済みのexact codeを使い、actual off-host generationとselective restore probeを完了する。ここでsecurity-critical codeを新規作成・変更しない。

**Files:**
- Create after run: `docs/status/verified-backup-generation.md`
- Create: `docs/evaluation/recovery-probe-results.md`

**Steps:**

1. Task 13のowner-signed release内にあるbackup/restore code hashがactive codeと一致することを確認する。
2. Hermes full backup、redacted portable sessions、Open WebUI quiesced snapshot、repo dirty capture、runtime source bundleを同じbackup setへまとめる。
3. Secret-bearing native archiveを暗号化し、delete権限のないupload credentialでactual off-host backendへ置く。
4. 別stagingへ復号し、allowlisted stateだけをfresh temp profileへrestoreする。Archive内SOUL/config/trust/credentialはactive化せず、signed releaseを最後にdeployする。
5. DB integrity、watermark、file hash、outer secret scan、stale identity rejection、previous generation recoveryを検証する。
6. `state.db`等private fileのrestore modeを0600へ固定し、現行0644はverified backup後だけ安全に是正する。
7. Pipeline code/unit/schemaの変更が必要ならTask 11へ戻り、Task 12/13のnew digest/signature/canaryをやり直す。
8. Sanitized evidenceを記録する。
9. Commit: `ops: verify signed PDA off-host recovery generation`

### Task 15: Install the signed root/control-owned guard and exercise recovery mode

**Objective:** Task 13で署名されたverifier/interpreter/dependencies、broker、unit set、release artifactsだけをroot/control-owned pathへ配置し、runtime UIDから独立したboundaryを実機canaryで証明する。

**Files:**
- Create after run: `docs/status/identity-guard-staging-result.md`

**Steps:**

1. Bundle外recovery fingerprintから`/etc/pda/trust/allowed_signers`とlatest accepted checkpointをroot-ownedでbootstrapする。Repo/bundle copyをtrust sourceにしない。
2. `/opt/pda-control/<control_digest>`へsigned/pinned verifier、interpreter、dependencies、brokerを置き、absolute path unitだけから呼ぶ。
3. `/opt/pda/releases/<release_digest>`とsigned legacy baselineをroot-owned/read-onlyで配置し、accepted state/broker key/storeを`/var/lib/pda-control`へ分離する。
4. Signed unit setをinstallし、explicit `User=`、fixed environment、`NoNewPrivileges`、read-only bind、minimal `ReadWritePaths`、broker peer/capability policyを検証する。
5. Separate canary portでcandidate strict serviceを起動し、invalid candidate boot denial、runtime UID binding DB/key/index tamper、existing-ID rebind、post-start personality/config/PATH/import/release mutationを実機確認する。
6. Production routeを閉じたままsigned recovery authorizationでlegacy baselineを`pda-hermes-recovery.service`に実bootし、`session_attested=false`、external send/cron/delegate/tool write無効を確認する。
7. Recovery serviceを停止し、candidate strict canaryへforward recoveryしてattested new sessionを確認する。
8. Backup freshnessはdoctor WARN/CRITICALでありstrict identity boot blockerではないことを確認する。
9. `systemd-analyze verify`、unit hash、canary health、strict/recovery/forward probesを通す。
10. Artifact修正が必要ならTask 11へ戻り、再freeze/署名/backupを行う。
11. Commit: `ops: install signed PDA identity guard and recovery path`

### Task 16: Cut over the live default continuity state through the guarded service

**Objective:** State migrationを同時に行わず、現在のdefault continuityを保ったままowner-signed candidateをguarded production pathへ切り替える。

**Files:**
- Create after run: `docs/status/identity-cutover-result.md`

**Steps:**

1. Task 14のfresh verified generation、Task 15のguard/recovery/forward PASS、Task 13のlatest checkpointをpreflightする。
2. Active generic bytesがowner-signed legacy baseline digestと一致することを確認する。違えば停止する。
3. Existing user serviceをbounded stop/disableし、port/process解放とproduction route閉鎖を確認する。二重起動禁止。
4. Production停止中にsigned deploy codeでimmutable candidate releaseをcompare-and-swap activateし、root accepted stateをverified owner-signed checkpointへ一致させる。
5. Root-owned control pathから`pda identity verify --strict`を実行し、candidate/accepted state/checkpoint/broker/unit/runtime全体がPASSすることを確認する。
6. その後にだけsigned root-owned production unitをstartし、health/attestation PASS後にproduction routeを再公開する。
7. New release-bound Open WebUI session、guarded CLI、Pipe専用API、delegate、isolated clone cron、Responses stream/non-streamでsame broker bindingとactual-loader prefixを確認する。
8. 旧sessionはlegacy/non-attestedとしてexecutionを拒否し、新sessionへuser/assistant historyだけを移す。
9. Activation、strict verify、startup、critical E2Eのいずれかが失敗したらproduction routeを閉じたままにし、signed recovery authorizationでlegacy baselineをlocal recovery-only unitへ起動する。Generic baselineをstrict/attested PDAとして公開しない。
10. Recovery smoke後はcandidateへのforward recoveryを試みる。成功しなければlocal recovery-onlyまたは停止状態を維持し、ユーザーへ明示する。Unsigned symlink rollbackは禁止する。
11. Bounded health/browser/E2E、systemd status、listener、broker/attestation evidenceを確認する。
12. Commit: `ops: cut over live Hermes through the signed PDA identity guard`

### Task 17: Complete a source-disk-independent fresh-host restore drill

**Objective:** 可搬性とanti-rollbackを、blank environment上の復元結果で証明する。

**Files:**
- Create: `docs/operations/fresh-host-restore.md`
- Create: `docs/evaluation/fresh-host-restore-results.md`
- Create: `tests/e2e/test_restored_pda_acceptance.py`

**Steps:**

1. Main Mac上のfresh Ubuntu 24.04 VMまたは同等の別hostを用意する。Source disk mount禁止。
2. Release/state artifactsとは別に、owner-held trust fingerprintとlatest signed checkpointを最初に取得・検証する。
3. Root trust/checkpointをbootstrapした後、旧valid-signed releaseだけを提示して拒否されることを確認する。Signed recovery authorizationがある場合だけlegacy baselineを許す。
4. Runtime/control locksからexact Hermes source/patch、broker/verifier deps、Open WebUI image digestを復元する。
5. Secretsはtest credentialまたはreauth/reissue flowを使い、production external sendを無効にする。
6. Native archiveをstagingへ展開し、allowlisted stateだけをrestoreしてowner-signed releaseを最後にdeployする。
7. ID、BAK、RST acceptance suiteを実行する。
8. 代表3 session、session_search、Open WebUI chat、Pipe、broker、delegate、isolated clone cronを検証する。
9. Signed legacy baselineをlocal recovery-onlyで実boot/smokeし、production routeを開かずcandidateへforward recoveryする。
10. VMを実rebootし、root-owned guard/broker、checkpoint/accepted state、new-session attestationを再検証する。
11. Restore timerを計測しRPO/RTO仮説と比較する。
12. 最新snapshotを意図的に破損させprevious generationを実証する。
13. Source hostからしか取れなかったartifactが1つでもあればHP-3をFAILとし、catalog/backupへ戻る。
14. Sanitized evidenceを記録する。
15. Commit: `test: prove anti-rollback PDA recovery on a fresh host`

### Task 18: Enable signed automation, monitoring, and milestone closure

**Objective:** 一度通った復元を継続的な運用保証へ変える。Automation unit bytesはTask 11で実装、Task 12でfreeze、Task 13でsign済みであり、ここではそのexact bytesをenableする。

**Files:**
- Create: `docs/status/current-state.md`
- Modify: `docs/roadmap/current-priority.md`
- Modify: `.hermes/plans/2026-07-20_202237-pda-current-state-and-next-roadmap.md` only by superseding note, not silent rewrite
- Modify: `pda_minipc_setup_record.md`

**Steps:**

1. Signed backup service/timerをenableし、change-triggered release backupと4時間以内state generationをscheduleする。
2. Backup age > 5hでwarning、2周期失敗でcriticalとする。通知にprivate contentを含めずidentity service rebootを既定ではblockしない。
3. Signed reminder unitでmonthly isolated restore、quarterly fresh-host drillをschedule/remindする。
4. `pda doctor --json`がprojection/release、control-owned session binding、runtime/control pin、DB、backup age、last restore evidenceを返すことをtestする。
5. Schedule/unit/code変更が必要なら新releaseとしてTask 11以降をやり直す。
6. 現在地を`SR-3 + HP-3`として記録する。Separate runtime principal、alternate core、Context Spine未達を併記する。
7. Existing roadmapへsuperseding linkを置き、古いP0 orderをsilentに改変しない。
8. Context Spine/PKB milestoneを次のactive priorityへ戻す。
9. Verify full suite、`git diff --check`、relative links、secret scan、clean intended diff。
10. Commit: `docs: close PDA identity portability milestone`

---

## 13. Dependency order and gates

```text
Task 1 emergency off-host capture
   ├─> Tasks 2-4 repository/control foundation
   └─> Tasks 5-8 projection + verifier foundation
               └─> Task 9 loader/session baseline
                           └─> Task 10 runtime adapters + control-owned binding
                                       └─> Task 11 all security-critical recovery/control/deploy/unit assets
                                                   └─> Task 12 final full-artifact freeze + candidate digest
                                                               └─> Task 13 exact-digest canary + owner signatures/checkpoint

Tasks 1 + 4 + 8 + 11 + 13 ─> Task 14 actual off-host generation/selective restore
Tasks 8 + 10 + 11 + 12 + 13 + 14 ─> Task 15 root-owned guard/recovery staging
Tasks 13 + 14 + 15 ─> Task 16 guarded live cutover
Tasks 14 + 15 + 16 ─> Task 17 fresh-host anti-rollback restore
Task 17 ─> Task 18 signed automation and closure
```

番号順を実行順とする。Security-critical code/unit/schemaをTask 12のfreeze後に追加・変更しない。

Mandatory stop/go gates:

- Task 1未完了ならproduction identityを変更しない。
- Broker、backup/restore、deploy、systemd units、Hermes/Pipe patches、runtime/control locksをfreezeする前にfinal manifestへ署名しない。
- Bundle外trust rootで検証したowner-signed exact `release_digest`とlatest accepted checkpointがなければTask 14以降へ進まない。
- Actual-loader、endpoint matrix、broker tamper、session/compression/delegate、strict/recovery/forward hard testが1件でもfailならlive cutoverしない。
- Repeatable off-host generationとselective restore probeがなければTask 16へ進まない。
- Root-owned guard canary、runtime UID tamper、legacy recovery boot、candidate forward recoveryが通らなければTask 16へ進まない。
- Legacy generic baselineをstrict/attested production routeで起動しない。
- Fresh-hostでlatest checkpointに対するold valid-signed release rejectionが通らなければ「portable/anti-rollback」と呼ばない。
- Off-host restore verificationがなければ「portable」と呼ばない。
- Fresh-host acceptanceがfailならPKB大量取込へ進まない。

---

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| 憲章をprompt化してauthorityを逆転する | Concise clause-traceable derived projection、charter-only normative authority |
| Generated SOULが新しい手編集正本になる | Deterministic renderer、generated marker、CI diff check |
| Projection IDとfinal bundle IDを混同する | `projection_id`とcanonical `release_digest`を二段階化 |
| Approval/signatureがself-referentialになる | Contract/manifest外のdetached signatureをexact release digestへbind |
| Releaseがtrust rootを自己供給する | Bundle外recovery material + root-owned trust store |
| Anti-rollbackと緊急recoveryが衝突する | Monotonic accepted state + owner-held latest checkpoint + owner-signed recovery authorization |
| 古いvalid-signed bundleがfresh hostでlatestを自称する | Bundle外latest checkpointをrelease選択前に復元しold releaseを拒否 |
| Legacy generic baselineがstrict guardを通らない | Strict routeでは拒否し、local/non-attested recovery-only unitでのみbootしてforward recover |
| 署名後にguard/restore/deploy codeが変わる | 全security-critical code/unit/schemaをTask 11で完成、Task 12でfreeze、変更時は再署名 |
| Memory/skill/frontendがidentityを上書きする | Tier separation、endpoint deny matrix、personality lock、actual-loader test |
| Delegate/compressionだけ別releaseになる | Control-owned broker binding、parent immutable release propagation、per-turn check |
| Runtime UIDがsession bindingを書換える | Root-only key/create-once store、MAC token、broker rebind deny、runtime-UID negative probe |
| 旧sessionが旧generic promptを保持する | Active-release mismatch execution deny、new session、legacy read-only |
| Profile distributionをfull backupと誤認する | Release/state/secret plane分離、native restore test |
| Hermes full backupがstale identity/credentialを復元する | Secret-bearing sealed archive、allowlist selective restore、signed release last |
| ZIPにsecretを含めたままoff-hostへ置く | Encryption before transfer、outer report secret scan、keys off-runtime |
| Cleanup中にdirty production stateを失う | Emergency captureを最初に実施 |
| Version pinが取得不能 | Git bundle/source archive/image digest/patch artifactを保存 |
| Root unitのverifier自体がruntime-writable | Root-controlled verifier/interpreter/deps/PATH/imports + sandbox |
| Same UIDで自己改変可能 | Detectionとpartial enforcementを区別、root-owned guard/read-only namespace、full UID splitは未達明記 |
| Open WebUIの既存dirty workを破壊する | Worktree/branch分離、未知fileを削除しない、commit scope制限 |
| Backupはあるがrestore不能 | Source-disk-independent fresh-host drillをexit conditionにする |
| ScopeがContext Spineまで膨らむ | HP-3/SR-3を今回の明示的終了条件に固定 |

---

## 15. Decisions that can wait until their blocking point

今は質問で作業を止めず、安全側のdefaultを採用する。

1. Off-host backend
   - Default: encrypted、versioned、append-only/object-lock相当。runtime credentialはdelete不可。
   - Decision point: Task 1のactual transfer直前。

2. Owner signing key
   - Default: main Mac上の専用Ed25519 key。Repo public keyはtransparency copyであり、trust bootstrapは別管理fingerprintからroot-owned storeへ行う。
   - Decision point: Task 8でkey contract、Task 13でexact release/checkpoint署名。

3. Secret recovery
   - Default: Tailscaleはreissue、OAuthはreauth、random application secretsはencrypted escrow + restore後rotation。
   - Decision point: Task 4 catalog review。

4. Fresh host
   - Default: main Mac上のfresh Ubuntu VM。Private stateを第三者cloudへ出さない。
   - Decision point: Task 17。

5. Live profile name
   - Default: First cutoverはcurrent `default` continuity stateを維持し、identity changeとstate migrationを分離する。Fresh-host restoreでnamed `pda` profileへの移行可否を評価する。
   - Decision point: Task 17後。

---

## 16. Final completion statement template

このmilestone完了時に言えること:

「PDA憲章に由来するowner-approved projectionが、identity、broker、guard、backup/restore、deployを含む全security-critical artifactをhashしたowner-signed releaseからHermesのactual identity slotへ全supported production surfaceで読み込まれる。各session/response chainはruntime-writable stateではなくcontrol-owned brokerでexact release digestへ固定され、unapproved overlay、compression/delegate drift、trust swap、post-start mutationはguard/request boundaryで拒否される。現在のHermes/Open WebUI continuity stateは暗号化off-host generationからsource diskなしでfresh hostへ選択復元され、bundle外latest checkpointに反するold signed releaseを拒否し、代表session/UIとidentity attestationが合格している。」

まだ言えないこと:

「PDAの全continuityがruntime-neutralである」「Hermesを任意coreへ交換できる」「provider外側のinstructionまでattestした」「PDA runtimeが自分のauthorityを一切変更不能である」。
