# PDAのタスク分解・モデルルーティング設計

Status: D0 Hermes quota guardrails applied; D2 PDA-local Fable probe blocked before inference by inaccessible usage credits
Checked: 2026-08-18 JST
Scope: Hermes primary agent, Hermes delegates, PDA-local Claude Code, and a separate development-Mac executor

## 1. Purpose

この設計の目的は、PDAの主実行体が長時間作業を完遂できる状態を保ちつつ、主モデルであるCodex GPT-5.6 Solへ全ての認知作業を集中させないことである。

特に、次を同時に満たす。

1. Solの利用上限への圧力を下げる。
2. 短く独立した下位作業をCodex GPT-5.6 Lunaへ移す。
3. 高い抽象度、曖昧性、ユーザー視点の再構成をClaude Fable 5へ委ねられるようにする。
4. 長時間・外部ホスト・再開可能な作業を、会話内の一時的なsubagentではなくdurable taskとして扱う。
5. 委譲先の出力をPDAの判断や事実として無検証に昇格させない。
6. ユーザーにモデル間の調整役を担わせない。

これは`pda_charter.md`から独立した権威ではない。憲章、ユーザーの現在の指示、確認済みの判断が常に上位である。Fable 5がユーザーと高く視点を共有できることは重要な能力特性だが、ユーザー本人の決定権や憲章改定権をFableへ移すものではない。

この設計は`docs/roadmap/current-priority.md`のidentity portability / strict injectionを置き換えない。現在の優先工程を進める際を含め、日常の認知資源配分を制御する横断的な運用設計である。

## 2. Authority and evidence

### 2.1 Owner direction

2026-08-18のユーザー指示から、次をRequirementとして扱う。

- ロングラン許容後に強まったCodex利用上限への圧力を下げる。
- 適切なタスク分解と委譲を仕組み化する。
- Hermes配下モデルとしてCodex GPT-5.6 Lunaを使う。
- Claude Code、特にClaude Fable 5の文章力、高い抽象度、曖昧性をユーザーに近い視点で扱う能力を活用する。
- Fable 5をPDAの「ユーザーの代行」に強く作用させる。
- Fableの視点代行はPDA-local Claude Code accountの利用可能なusage creditsで検証・運用する。
- 開発PCのClaude Codeは別用途として扱い、視点代行の実行先やfallback先にしない。

### 2.2 Verified current facts

2026-08-18に実機と公式文書で確認したFactは次のとおり。

- 主モデルは`openai-codex:gpt-5.6-sol`。
- `agent.max_turns`は500、主agentのreasoning effortは`max`。
- 変更前のHermes delegationはmodel/provider未指定で、子はSolを継承する。
- 変更前の`delegation.max_iterations`は250、`max_concurrent_children`の実効値は10、child timeoutは無制限、depthは1。
- per-turnのsubagent spawn capは既定50。従って、長い親turnがSol子を繰り返しspawnする余地が大きい。
- Hermes `delegate_task`のchild executionはprocess-localであり、実行中にowner processが消えた場合は再開されない。child完了後の未配信resultは`state.db`へ保存されrestart後に配信され得るが、これは実行durabilityではない。子はユーザーへ質問できず、返す内容は自己申告summaryである。
- Hermes v0.20.2は`delegation.provider`と`delegation.model`で子のprovider/modelを固定できる。
- GPT-5.6 Lunaはインストール済みHermes sourceでCodex OAuth対応modelとして登録されている。D0設定後の実review runではHermesのcontrol-owned delegation manifestが`model: gpt-5.6-luna`、`provider: openai-codex`、`status: completed`を記録した。
- PDAホスト上のClaude Codeはv2.1.205である。通常のnon-interactive launch pathでは`CLAUDE_CODE_OAUTH_TOKEN`が存在し、`claude auth status --json`は`loggedIn=true`、`authMethod=oauth_token`、`apiProvider=firstParty`を返した。tokenを外すとstored interactive loginは存在しない。
- Claude Code v2.1.205は`claude-fable-5`を認識し、`--bg`、Agent View、structured `-p`を持つ。
- 開発MacのTeam seatへPDA側から直接入る`ssh main`経路は、現在のPDAホストでは名前解決できない。PDA側にreverse SSH listenerも確認できなかった。
- 開発MacからPDAへ入る既存の方向はセットアップ記録上確認済みである。従ってdurable workerはMacからPDA上のboardをpullする構成が、現在の接続事実と合う。
- Claude Code公式文書ではFable 5のfull model IDは`claude-fable-5`。非対話`-p`でusage credits対象になった場合、同意promptなしで課金され得る。
- AnthropicのFable 5 product pageは、safety monitoringのため30日data retentionを必須とし、zero data retentionでは利用できないと明記している。従ってPDA-local accountでもpersonal context minimizationは省略しない。
- 2026-08-18のPDA-local read-only probeはprocess exit 1、`is_error=true`、API 429、`Fable 5 requires usage credits`、`modelUsage={}`、CLI-reported cost 0で終了し、model inferenceには到達しなかった。local stateのsafe read-backは`cachedExtraUsageDisabledReason=org_level_disabled`を示した。従って、現在のlaunch principalからusage creditsへアクセスできず、PerspectiveResultの実品質検証は未完了である。

ユーザーはPDA-local accountに既に存在する残creditの消費を明示的に許可した。この指示は新規credit購入、uncapped billingの有効化、organization policy変更までは許可せず、開発MacのTeam accountを代替経路にも指定しない。視点代行と開発executorはaccount、host、purposeを分離する。

### 2.3 Proposal sources

`origin/claude/fable-system-design-d3c203`のruntime-neutral TaskSpec / RunResult、capability registry、principal separationは有用なProposalである。ただし憲章追加前の未統合branchであり、現在のauthorityやlive stateではない。本設計はその考えを現在の狭い運用課題へ再構成したものである。

このbranch上の`pda.delegation-task/v1`と`pda.delegation-result/v1`も未deployのpre-adoption contractである。今回のaccount/host変更はadoption前のowner correctionとしてv1 draftを修正する。v1をruntimeや外部consumerへ公開した後は同じIDをin-place変更せず、versionを上げる。

## 3. Core invariants

### INV-R1: deterministic first

単一のtool call、既知のcommand、構文検査、集計、format変換など、決定論で完了できる作業にはLLMを追加しない。

### INV-R2: the primary owns intent and integration

主PDA/Solは、ユーザー意図の保持、分解、route選択、結果統合、検証、ユーザー向け報告を手放さない。委譲先は下位deliverableを返すexecutor/advisorであり、PDAの代わりに最終回答する主体ではない。

### INV-R3: delegation is by deliverable, not by activity

「調べる」「考える」「実装する」のような曖昧な活動ではなく、独立に合否判定できる成果物単位へ分ける。各subtaskはobjective、acceptance criteria、non-goals、result contractを持つ。

### INV-R4: no shared write ownership

同時に編集する二つのrunへ同じworktree/write scopeを与えない。既存dirty worktreeをcleanにする目的でstash、reset、stage、delete、fold-inを行わない。

### INV-R5: privacy before capability

model品質より先にaccount principal、information class、egress先、write権限を判定する。処理能力が高くても、許可されないdata boundaryは越えない。

### INV-R6: model output is a proposal until verified

子agentの「完了した」「検証した」「変更した」というsummaryは証拠ではない。artifact handle、Git diff、file read-back、test result、URL、runtime metadataを親が確認する。

### INV-R7: owner-only decisions remain owner-only

憲章改定、本人の価値観の確定、不可逆な外部作用、個人情報を会社principalへ渡す包括許可、追加従量課金の包括許可は委譲先が決めない。

### INV-R8: long work is durable work

親session、SSH、model processの終了を越えて残る必要がある作業は`delegate_task`へ渡さない。Kanban/task board、local outbox、Git/artifactをcontrol planeにする。

## 4. Execution lanes

### 4.1 `primary-sol`: PDA orchestrator and integrator

Use when:

- ユーザー意図の解釈が中心である。
- 複数subtask間の依存を解く必要がある。
- owner decisionの要否を判定する。
- 最終的な整合性、risk、完了判定を行う。
- 高riskな変更や本番cutoverを統合する。

Do not use as default for:

- 独立したread-only調査。
- 機械的なfile inventoryやschema validation。
- 同じ観点の反復review。

### 4.2 `codex-luna`: bounded in-session cognitive worker

Use when all are true:

- 親が今のturnで結果を必要とする。
- subtaskは独立し、子がユーザーへ質問しなくても完了できる。
- objectiveとacceptance criteriaを短く記述できる。
- 失敗しても親が安全に棄却または再構成できる。
- 原則としてread-only、または隔離worktree内の狭い変更である。
- durable resumeを必要としない。

Good fits:

- 一つの設計論点への反証。
- 既知scopeのcode/doc review。
- 複数sourceからの構造化抽出。
- 親contextを膨らませる中間探索。
- test case候補、risk list、比較表の作成。

Bad fits:

- リポジトリ全体の自由探索と実装を一つのgoalにまとめる。
- ownerの意図が未確定な仕事。
- 20分を越える見込みの実装。
- 本番反映、push、送信、削除。
- 子同士が同じfileを編集するfan-out。

### 4.3 `claude-fable`: perspective and ambiguity delegate

Fable 5は「高価な一般executor」ではなく、PDAのowner-perspective cognitionを補うspecialistとして扱う。

Use when the bottleneck is:

- 高い抽象度での意味付け。
- 要件に明示されない価値の緊張関係。
- ユーザーの温度感や過去の選好を踏まえた解釈。
- 複数の妥当な設計案から、ユーザーに近い観点で推薦すること。
- 長文の思想、方針、設計、意思決定文書を人間的に統合すること。
- 曖昧な問題を、ユーザーが答えられる最小のdecisionへ変換すること。

Default mode is read-only advisor. Fableが返すのは`PerspectiveResult`であり、外部送信やcanonical writeの許可ではない。

Fableへ「ユーザー本人として決定せよ」とは指示しない。代わりに「確認済みの選好から最も整合する推奨を出し、推測を明示せよ」と依頼する。Fableの高い一致度は、推定精度を上げるがauthorityを上げない。

初期control surfaceはPDA-localのbounded/read-only advisorだけに限定する。fixed wrapperは`claude -p --model claude-fable-5 --output-format json --json-schema ... --tools "" --permission-mode dontAsk --max-turns 1 --no-session-persistence`相当を一度だけ起動し、10分以内、concurrency 1、retry 0とする。

wrapperはOS exitだけでなくterminal resultの`is_error`、`api_error_status`、`terminal_reason`、`modelUsage`を検証する。`subtype=success`でも`is_error=true`ならblocked/failedであり、成功へ昇格させない。`modelUsage`にexact Fable 5 evidenceがなくても成功にしない。

PDA-local principal内でもraw conversation、全memory、全PKBを渡さず、task固有のminimized context capsuleだけを送る。初期段階ではdurableなFable perspective missionを作らない。credit gate、timeout、scope超過時はSolがreframeまたは保留し、開発Macへfallbackしない。

### 4.4 `claude-code`: separate durable development executor

Use when:

- repository、toolchain、credential、Agent View / CLI session historyがある開発Macで実行すべき開発作業である。
- 長時間作業、再開、人間の途中介入、session履歴が必要である。
- task単位のworktreeとGit artifactを作れる。

このlaneはowner-perspective delegateではなく、会社PC・Team principal上の開発executorである。使用modelはdevelopment taskのpolicyとaccount条件から別に決める。将来Fableをcoding modelとして使う場合も、PDA-local perspective laneの検証やfallbackとは数えず、exact modelとbillingをそのtask内で検証する。

### 4.5 `deterministic`: tools and scripts

Use for arithmetic、file parsing、Git state、test execution、schema validation、format conversion、queue polling、retry/outbox delivery。empty queueをmodelにpollさせない。

## 5. Routing decision table

| Task shape | Route | Why |
|---|---|---|
| 既知のcommand/toolで完了 | deterministic | model不要 |
| 独立・bounded・即時・no user interaction | codex-luna | Sol context/turnを節約 |
| 曖昧性・価値判断・抽象統合が主 | claude-fable | owner-perspective specialist |
| 長時間・Mac toolchain・resume必須 | Claude Code durable lane | process/session durability |
| 複数結果の統合、owner gate、final answer | primary-sol | PDAの責任境界 |
| 外部作用を伴うが許可未確定 | primary-sol → owner | model routeでは解消不能 |

Tie-breakers, in order:

1. Information boundary
2. Side-effect/approval boundary
3. Durability requirement
4. Ambiguity and owner-perspective requirement
5. Execution locality
6. Expected quota/cost
7. Latency

## 6. Decomposition algorithm

主agentは大きな依頼を次の順序で処理する。

1. Outcomeを一文で固定する。
2. Acceptance criteriaを、観測可能な条件へ変換する。
3. Owner-only decisionを先に分離する。安全なdefaultで進められる場合は止めない。
4. 作業をdeliverable単位へ分ける。同じartifactへ書く単位は分割しない。
5. 各deliverableが独立しているかを判定する。結果を得ないと次を定義できない場合は並列化しない。
6. deterministicで閉じるものを除外する。
7. 残りをrouting tableへ通す。
8. 各taskへ最小context capsuleとbudgetを付ける。
9. 期待節約量がhandoff/integration overheadを上回る場合だけ委譲する。
10. 結果をartifact/evidenceから検証し、矛盾を解消してから次のtaskまたは最終回答へ進む。

Do not decompose by org chart. 「researcher」「coder」「reviewer」を必ず作るのではなく、必要な独立deliverableが一つなら一つだけ委譲する。

## 7. Context capsule contract

Machine-readable contractは`schemas/delegation-task-v1.schema.json`を正とする。これはdispatch可能なexecution contractであり、未承認のdraft cardはこのschemaに合格させない。最低限、次を含める。

- `objective`: 一つの成果。
- `acceptance_criteria`: 親が合否判定できる条件。
- `non_goals`: scope膨張を止める条件。
- `task_class`, `ambiguity`, `information_class`。
- `context_capsule`:
  - `facts`: source付きの確認済み事実。
  - `decisions`: ownerまたはauthoritative sourceの決定。
  - `preferences`: `confirmed`と`inferred`を分離。
  - `assumptions`: 検証されていない仮定。
- `route`: lane、requested model、execution host、durability。
- `permissions`: read/write/networkとowner gate。
- `egress`: 送信先account class、`not_required|granted`のauthorization status、control-owned authorization reference、選択済みcontext reference。`claude-fable`はPDA-local Claude principalとminimized context selectionへ固定する。Personal→Teamの明示許可は開発Mac executorにだけ適用する。
- `billing_policy`: billing mode、既存credit限定、purchase / auto-reload / unlimited spend / settings mutationの可否、control-owned balance evidenceとfinite spend-cap evidence。Fable perspectiveでは既存credit以外を全てfalseに固定する。
- `budget`: iterations、wall time、concurrency、retry。
- `result_contract`: 必須artifactとverification。

Raw conversation全体、memory全文、secret、無関係なPKBを渡さない。子はこのconversationを知らないため、必要情報を省略して「親と同じように理解している」と仮定もしない。

`permissions.network`はdelegateへ公開するnetwork toolとtask-level external accessを表す。Claude provider endpointへのfixed control transportはaccount routeの一部であり、`network=deny`でもCLI inference transportまで遮断する意味ではない。

`docs/design/examples/`のauthorization、credit balance、spend cap、runtime evidence URIはcontract shapeを示すexampleであり、実taskのapprovalやbilling evidenceとして再利用できない。実行時はcontrol plane上のtask固有recordへ解決する。

## 8. Result contract

Machine-readable contractは`schemas/delegation-result-v1.schema.json`を正とする。development-Mac laneでは`task_id`をPDA-issued `request_id`としてserializeし、`run_id`はbridge-owned Kanban attempt表現とする。`kanban_task_id`をschema上の`task_id`へ代入しない。詳細mappingは[`development-mac-claude-kanban-integration.md`](development-mac-claude-kanban-integration.md)を正とする。

結果は少なくとも次を含む。

- task/run IDとstatus。
- requested/effective route and model。
- execution hostと、trusted wrapper/runtime initが生成したtyped `principal_attestation`。account class、auth method、host、attestation source、evidence URI、verified stateを含む。
- typed `runtime_outcome`: process exit、terminal result受領、result subtype、`is_error`、API error status、terminal reason、`models_used`、raw evidence URI。
- concise summary。
- artifact handles。
- 実際に行ったverificationとevidence。
- remaining uncertainties。
- owner decisionが必要か、必要なら一問と推奨。
- wall time、model iteration等、取得できたusage。取得不能値を推測しない。
- failure category and retryability。

`authorization_ref`はmodelが生成した文字列では合格しない。Control planeが保持するowner approvalへ解決でき、taskの送信先account classとcontext selectionに一致する必要がある。`principal_attestation`もmodelの自己申告ではなく、PDA-local wrapperまたはMac trusted wrapperが取得したmodel metadataと`claude auth status`相当のevidenceへ解決し、親がread-backして初めて成功受理される。Schemaは構造を拘束し、reference解決と署名・所有者確認はworker/control-plane policy validatorがfail closedで行う。

`lane=claude-fable`ではstatusに関係なくhost/principalをPDA-localへ固定する。`status=succeeded`では、runtime outcomeもexit 0、result受領、`is_error=false`、API errorなし、non-empty exact Fable model evidenceへ固定し、全verification outcomeを`passed`にする。`failed`、`blocked`、`cancelled`、`partial`だけが`failed|not_run`を含められる。

親はeffective model、artifact、verificationをread-backする。result contractが不正なら「成功した文章」があってもfailed contractとして扱う。

## 9. Fable perspective protocol

Fable taskは通常のcoding taskと別の出力契約を持つ。`lane=claude-fable`の成功resultには、`schemas/delegation-result-v1.schema.json`のtyped `perspective_result`が必須であり、generic summaryだけでは成功にならない。

Input:

1. 解釈してほしい曖昧なproblem。
2. ownerが明示した目的。
3. confirmed preferences。
4. inferred preferences。必ず推定と表示。
5. 既に棄却された選択肢と理由。
6. authority boundaryと、Fableが決めてはいけない事項。
7. 必要な情報だけを含むdata classification済みcontext。
8. 既存credit balanceとfinite spend capへ解決できるcontrol-owned evidence。wrapperによるbilling settings mutationは禁止。

Output:

1. `owner_view_interpretation`: ユーザー視点で何が本質か。
2. `recommended_direction`: 推奨と最小の理由。
3. `tensions`: 両立しない価値やtradeoff。
4. `uncertainties`: 推測している点。
5. `owner_decision_needed`: 本人にしか決められない一問。不要ならfalse。
6. `do_not_infer`: 証拠不足で確定してはいけない事項。
7. `handoff`: Solが統合できる短いproposal。

Fableは外部でユーザーを名乗らない。ユーザーの承認を偽装しない。憲章やconfirmed preferenceを変更しない。advisor modeではfile writeやnetwork side effectを持たない。

## 10. Short-run flow: Sol → Luna

```text
User request
  -> Sol fixes outcome and acceptance
  -> deterministic work removed
  -> one or two independent capsules
  -> delegate_task on gpt-5.6-luna
  -> Luna returns bounded result
  -> Sol verifies artifacts/evidence
  -> Sol integrates or rejects
  -> one owner-facing result
```

Rules:

- Default concurrency: 1. Use 2 only when write scopes and dependencies are disjoint.
- Nested delegation: disabled.
- One failed task may be reframed once. Repeated blind retry is prohibited.
- Parent does not spawn a child merely to confirm a trivial conclusion it can deterministically verify.
- Independent review is useful cognitive diversity but not a security boundary.

## 11. Separate durable flow: PDA Kanban → development Mac → Claude Code

The detailed integration contract is [`development-mac-claude-kanban-integration.md`](development-mac-claude-kanban-integration.md). This section fixes only the routing-level invariants for development execution. It is not the Fable perspective path and cannot receive one as a fallback.

```text
PDA / Sol
  -> creates a classified task on the PDA-hosted `dev-main` board
  -> assigns the external terminal lane `main-claude`
  -> Mac launchd bridge polls over Mac -> PDA SSH without invoking a model
  -> atomically claims the card and records its Kanban run ID
  -> reconciles local journal, outbox, worktree, and Claude session
  -> creates a deterministic task worktree when no prior execution exists
  -> starts one official `claude --bg` conversation in that worktree
  -> records Claude job ID and full session UUID
  -> mirrors needs-input / done / failed state back to Kanban
  -> persists and validates the local result before remote delivery
  -> Sol verifies Git, artifact, test, principal, and owner-gate evidence
  -> follow-up, review, owner escalation, or completion
```

The queue is the control plane; Git and bridge-owned outbox are the deliverable plane; Claude's saved conversation is the execution-history plane. SQLite board files are never mounted or synchronized across hosts.

Use the existing Mac → PDA SSH direction for normal queue operation. A reverse SSH tunnel is optional for direct inspection or rescue and is not a dependency of task retention.

`main-claude` is deliberately not a Hermes profile. The current Hermes v0.20.2 dispatcher classifies a ready card assigned to a non-profile lane as `skipped_nonspawnable`; the Mac terminal claims it explicitly. This behavior, external claim, guarded completion, and stale-run rejection were verified on an isolated board on 2026-08-18. Re-run that probe after Hermes upgrades.

Mac worker invariants:

- Run as the same macOS user and config identity as the Team-authenticated interactive Claude Code.
- Resolve a logical `repo_key` through a local allowlist; never interpret the PDA board's workspace path as a Mac path.
- Start inside a bridge-created task-specific linked worktree so existing dirty checkouts and concurrent threads remain untouched.
- In v1 Claude edits and tests only; the bridge owns branch mutation, commit, push, and PR actions after independent verification and the relevant gate.
- Do not forward the PDA host's environment, OAuth token, API key, or arbitrary path.
- Remove higher-priority provider/API credential variables and verify the Team login path before enabling the lane.
- Use a PDA-issued `request_id` as the card-creation idempotency key, then use the returned `kanban_task_id` for local journal, branch, worktree, Claude session name, and outbox delivery.
- Use the Kanban run ID as a fencing token on complete, block, request-review, and other terminal lifecycle writes.
- Set claim TTL from the bounded task runtime plus grace. In v0.20.2, CLI `heartbeat` calls `heartbeat_worker()` and does not extend `claim_expires`; the distinct internal `heartbeat_claim()` is not the external CLI contract.
- Reconcile a local outbox or existing Claude session before re-running a claimed task after SSH loss.
- Mac offline means a development task remains queued; it does not fall back to PDA-local Fable. Conversely, a local perspective task never moves to the Mac.

The Mac has one launch contract in this design: `claude-executor`, using official `claude --bg --name pda-<repo_key>-<kanban_task_id> ...` for repository work that needs a resumable, human-inspectable Claude Code conversation. Agent View, `claude attach`, `claude logs`, `claude respawn`, and the normal resume picker are the human control and history surfaces. The PDA-local `fable-advisor` wrapper is outside this worker and board contract.

For the durable development lane, `claude -p` is not a substitute for `--bg`: print/Agent SDK sessions do not satisfy the normal session-picker requirement. The background session writes a model-authored executor payload into its documented Claude job scratch area; the bridge copies it to its own outbox, independently verifies its claims, and wraps it with control-owned principal/run evidence before producing the final delegation result. Agent View's `done` label and model prose are audit material, not the machine result protocol.

Exact model routing remains fail-closed whenever a development task requests a model. The documented `claude agents --json` contract does not currently expose effective model, so the worker must obtain control-owned evidence or block exact-model acceptance. No Mac result counts as evidence that the PDA-local Fable perspective lane works.

The fixed local wrapper reads and validates a task file, resolves authorization and context references, renders a bounded instruction, and passes it as one subprocess argv item. It never pastes untrusted task text into a remote shell command. The PDA SSH key is restricted to one board, one lane, and a narrow structured wrapper rather than arbitrary shell access.

## 12. Information and account boundaries

The PDA-local Claude account, the development Mac's Team account, and the Codex OAuth account are distinct principals with distinct purposes.

| Class | Luna on PDA | PDA-local Fable perspective | Development-Mac Claude executor |
|---|---|---|---|
| public | allowed | allowed with minimized capsule | only when relevant to an authorized development task |
| personal | allowed under current PDA policy | allowed under current PDA policy with minimized capsule | denied for perspective delegation; separate explicit policy required for any other transfer |
| work | only under separate work policy | deny by default | only organization-authorized workspace/context |
| secret | never put in model capsule | never put in model capsule | never put in model capsule |

The user has explicitly chosen the PDA-local account for Fable perspective work and reserved the development PC for a separate use. This authorizes a bounded pilot using already-accessible local credits, while context minimization remains mandatory because Fable 5 carries a 30-day retention requirement. It does not authorize copying the whole memory store, purchasing credits, or changing organization billing policy.

## 13. Initial quota guardrail profile

The intended starting profile is deliberately narrow:

```yaml
delegation:
  provider: openai-codex
  model: gpt-5.6-luna
  reasoning_effort: high
  max_iterations: 32
  max_concurrent_children: 2
  max_spawn_depth: 1
  orchestrator_enabled: false
  child_timeout_seconds: 1200
  max_summary_chars: 12000

tool_loop_guardrails:
  loop_caps:
    max_subagents: 4
```

Meaning:

- Main Sol can remain long-running; child missions cannot inherit the same 500-turn posture.
- Luna is a bounded helper, not a second full PDA.
- At most two children run in parallel and four can be spawned in one parent turn.
- A child that needs more than 20 minutes or 32 agent iterations belongs in a durable lane or needs re-decomposition.
- Disabling nested orchestration prevents multiplicative quota expansion.

These are starting values, not constitutional constants. Adjust only from measured run outcomes.

Task schemaのLuna budgetは各childの上限を拘束する。`max_concurrent_children=2`とper-turn `max_subagents=4`は親runtimeが強制する別の集約guardであり、child payloadの自己申告では変更できない。

## 14. Usage and quality observation

Provider subscription limits are not fully observable from local token counts. Lunaへのroute変更とfan-out制限は一runあたりの重さと同時消費を下げるが、OpenAI側でSol/Lunaが同一poolとしてどのように重み付けされるかはlocal evidenceだけでは確定しない。従って「Lunaなら必ず利用可能時間が比例して伸びる」とは主張せず、provider usage表示と実taskの継続可能性で検証する。Hermes estimatesをprovider billing truthとして提示しない。

Define two different quantities instead of conflating them:

- `primary_sol_turn_pressure`: main-session Sol API calls/tool iterations/output tokens plus any Sol child calls, per user request.
- `provider_account_quota_pressure`: provider-side usage/limit evidence across Sol and Luna. This is unknown when provider evidence is unavailable.

Initial baseline is five comparable pre-D0 tasks from available session metadata. The pilot cohort is ten tasks. The initial go hypothesis is at least a 20% reduction in median `primary_sol_turn_pressure`, with no increase in verification failures, parent rework, or owner interruptions. Do not claim provider-account quota reduction unless provider usage evidence also moves in the expected direction.

For every nontrivial delegated run, record when available:

- task ID and route reason;
- requested/effective model;
- start/end/duration;
- model iterations or turns;
- status and failure category;
- artifact verification pass/fail;
- parent rework count;
- whether owner interruption was required;
- whether delegation saved primary work or only added integration overhead.

Initial evaluation window: 10 representative tasks, including at least:

- 3 deterministic tasks that should not delegate;
- 3 Luna bounded tasks;
- 2 Fable perspective tasks;
- 2 durable Claude Code tasks.

Go criteria:

- No wrong-account execution.
- No shared-worktree collision.
- No unverified child success claim reaches the user.
- Luna tasks usually complete within the child budget.
- Fable output reduces owner clarification or materially improves decision framing.
- Median `primary_sol_turn_pressure` falls by the initial 20% hypothesis without increased rework or owner cognitive load.

Stop/revise criteria:

- Repeated task reframing or result-contract failures.
- Fable use consumes usage credits unexpectedly or runs on a substituted model.
- Integration overhead exceeds work saved.
- Personal/work boundary cannot be enforced.
- Queue reconnect causes duplicate model execution or side effects.

## 15. Implementation sequence

### D0 — immediate guardrails

- Pin Hermes delegates to Luna.
- Reduce child width, depth, iterations, timeout, and per-turn spawn cap.
- Version this design, schemas, examples, and routing skill.
- Verify active config read-back.

Exit: new sessions cannot create unbounded Sol child fan-out by default.

### D1 — Luna operating pilot

- Use the source-controlled routing skill in normal PDA work.
- Require capsule/result contracts for nontrivial delegation.
- Measure 3-5 bounded tasks.
- Revise thresholds from actual failure/rework evidence.

Exit: Luna lane is useful and bounded, not merely cheaper in theory.

### D2 — Fable perspective pilot on the PDA-local account

- Use the existing first-party `CLAUDE_CODE_OAUTH_TOKEN` launch path without forwarding an API key or changing account principal.
- Verify that existing usage credits are accessible before sending a real context capsule.
- Run one minimized, read-only, no-tools perspective task with structured output and no session persistence.
- Require typed runtime success, exact Fable `runtime_outcome.models_used`, schema-valid PerspectiveResult, control-owned principal evidence, and resolvable balance/spend-cap evidence.
- Compare the Fable recommendation with Sol integration and owner response.

Current state: the initial credit-access probe failed closed with API 429 and `org_level_disabled` before model inference. The CLI reported zero model tokens and cost 0, and no PerspectiveResult was produced; provider billing ledger or balance was not read back, so no stronger credit-consumption claim is made. The control-owned record is [`pda-local-fable-perspective-pilot.md`](pda-local-fable-perspective-pilot.md).

Exit: local account, exact model, credit path, minimized context boundary, and result handoff are proven. This exit is not yet met.

### D3 — durable board worker

- Create a dedicated board or hard information-boundary lane.
- Implement deterministic launchd polling, atomic claim, stable lease, local journal/outbox, worktree mapping, model invocation, result delivery, and reconciliation.
- Test SSH loss after model completion before result delivery.

Exit: disconnect does not lose work or re-run the model.

### D4 — routing evaluation and adaptation

- Aggregate route outcomes.
- Promote stable rules into policy.
- Keep automated routing advisory until a gold set shows it improves quality/cost without boundary violations.

Exit: route changes are evidence-based and reversible.

## 16. Acceptance tests

1. New Hermes delegate run reports effective model `gpt-5.6-luna`.
2. One batch requesting 3 simultaneous children is rejected by the width cap of 2; Hermes does not silently wave it into 2+1.
3. Across sequential dispatches, more than 4 child spawns in one parent turn is blocked by the separate cumulative spawn cap.
4. Nested child delegation is unavailable.
5. A trivial deterministic task completes without any child model.
6. A child completion claim is not accepted until artifact/test evidence is independently read.
7. Two editing tasks receive distinct worktrees and cannot modify the same checkout.
8. A Fable-required task fails closed if effective model evidence is not exactly `claude-fable-5`.
9. Every Fable result status requires the PDA-local Claude principal; a blocked/failed result claiming the development-Mac Team principal is schema-invalid.
10. A result with `subtype=success` but `is_error=true`, API 429, empty `models_used`, or non-zero process exit is blocked/failed, never succeeded.
11. A Fable task without resolvable existing-balance and finite-spend-cap evidence is rejected before model launch.
12. Purchase, auto-reload, unlimited spend, billing/settings mutation, and development-Mac fallback are all rejected for the perspective lane.
13. A local perspective task carries only its explicit minimized context selection, not raw conversation or full memory.
14. Mac offline leaves a development task queued and does not trigger a wrong-principal fallback.
15. SSH loss after Mac-local completion preserves the development result in the outbox and later delivers it without model re-execution.
16. Invalid result schema is classified as contract failure even if prose says success.
17. Parent final response contains one integrated result and one explicit owner ask at most.

## 17. Open decisions

### OD-1: PDA-local usage-credit access

Question: PDA-local accountでcurrently disabledなusage creditsを有効化するか、included Fable allowanceまたはpolicy resetを待つか。

Recommendation: 現在の指示どおり既存creditだけを使う。`org_level_disabled`の間はD2をblockedに保ち、worker/wrapperはSettings、organization policy、billing、purchase、auto-reloadを変更しない。ownerが別経路で既存balanceとfinite spend capを確認し、control-owned evidenceを発行できた後だけD2を再実行する。追加購入やpolicy変更が必要なら別の明示承認を求める。

This blocks only the live Fable quality pilot. D0/D1, schema/design work, and the separate development-Mac lane remain unblocked.

## 18. References

- PDA authority: `pda_charter.md`
- PDA system concept: `personal_delegate_agent_plan.md`
- Current priority: `docs/roadmap/current-priority.md`
- Earlier Fable proposal: `origin/claude/fable-system-design-d3c203`
- Hermes configuration: https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Hermes delegation: https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
- Hermes Kanban: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- Claude models: https://platform.claude.com/docs/en/about-claude/models/overview
- Claude Code model configuration: https://code.claude.com/docs/en/model-config
- Fable 5 plan behavior: https://support.claude.com/en/articles/15424964-claude-fable-5-on-your-plan
- Usage-credit management: https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans
- Fable 5 retention: https://www.anthropic.com/claude/fable
- Claude Code CLI: https://code.claude.com/docs/en/cli-reference
- Claude Code Agent View: https://code.claude.com/docs/en/agent-view
