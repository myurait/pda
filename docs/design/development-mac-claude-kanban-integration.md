# PDA–開発Mac Claude Code 非同期Kanban連携案

Status: Design decision accepted; implementation pending
Decision date: 2026-08-18 JST
Checked against: Hermes Agent v0.20.2 (2026.8.16), current Claude Code official documentation
Parent design: [`operational-delegation-routing.md`](operational-delegation-routing.md)

## 1. Decision

開発PC上のClaude CodeをPDAから同期的に遠隔操作する方式は、中核経路にしない。

代わりに、PDA上のHermes Kanbanをタスクの正本とし、開発Mac上の決定論的worker bridgeがSSH経由で担当カードをpullする。実行は公式Claude Codeのbackground sessionで行い、Agent Viewと通常のsession resumeをClaude側の実行履歴UIとする。

採用する基本形は次のとおりである。

```text
User
  -> PDA / Hermes (intent, priority, decomposition, acceptance)
  -> PDA-hosted Kanban board (durable control record)
  <- SSH pull / state update
  -> development Mac worker bridge (deterministic scheduler)
  -> task-specific Git worktree
  -> official `claude --bg` session
  -> Agent View / saved Claude Code transcript (human audit and intervention)
  -> local outbox + Git artifacts
  -> Kanban result handoff
  -> PDA verification, integration, and owner escalation
```

この設計では、SSHは会話そのものではなく、共有状態を安全に読み書きするtransportである。双方向の意味交換は、一つの長寿命socketではなく、カード、コメント、run、result artifactの状態遷移として行う。

## 2. Why this shape

### 2.1 Synchronous remote control is the wrong abstraction

HermesがClaude Codeの一つのterminal sessionを同期的に保持し続けると、次が結合する。

- SSH connection lifetime
- Hermes turn lifetime
- Claude process lifetime
- user intervention timing
- tool permission prompts
- Git working state
- result delivery

どれか一つが切れるだけで「実行したのか」「結果を受け取ったのか」「再実行すべきか」が不明になる。

Kanbanへ状態を外出しすると、PDA、Mac、Claudeのいずれかが一時停止しても、発注、claim、質問、成果、検証の記録は残る。Hermes KanbanはSQLite上のdurable task boardであり、task、dependency、comment、run、claimをprocess外で保持する。[1]

### 2.2 Claude history must be a native Claude Code session

長時間の開発executorには`claude -p`を使わない。`claude --bg`は`-p`と併用できず、terminalから切り離されたfull Claude Code conversationとしてsupervisorに管理される。[2][3]

background sessionは次の公式surfaceに残る。

- `claude agents`: working、needs input、completed、failedを一覧する。
- `claude attach <job-id>`: full interactive conversationへ入る。
- `claude logs <job-id>`: recent outputを確認する。
- `claude respawn <job-id>`: conversationを保ったまま再起動する。
- `claude agents --json --all --cwd <repo>`: bridgeが状態、job ID、session UUID、待機理由を取得する。
- `claude --resume` / `/resume`: background sessionを`bg`表示付きで再開する。

Claude Codeはbackground sessionも通常のproject session pickerへ含める一方、Agent SDK由来のsessionはpickerへ表示しない。[4] 従って、履歴要件を満たすdurable executorは`--bg`とし、`-p`は必要なら別のbounded advisor laneだけに限定する。

### 2.3 Desktop is not part of the contract

Claude DesktopのCode tabへsessionを登録することは要件にしない。Claude側の正規UIはCLI Agent View、保存済みconversation、Git branch、PRとする。

これによりDesktopとCLIのhistory分離、project grouping、UI automationへ依存しない。

### 2.4 The Team seat remains the intended principal

Agent Viewの公式仕様ではbackground sessionはinteractive sessionと同じsubscription usageを消費し、並列数に概ね比例してquotaを使う。[3] supervisorはinteractive sessionと同じ保存済みcredentialを使用する。[3]

これは、公式CLIの`--bg` sessionを同一ユーザーの開発作業に使う設計であり、bridge自身がOAuth tokenを取得したりAnthropic APIを実装したりする設計ではない。

ただし、次を区別する。

- 現在、Claude Agent SDK、`claude -p`、third-party app usageをsubscription limitから分離する予定変更はpauseされており、引き続きsubscription limitを使う。[6]
- AnthropicはOAuthをnative Claude applicationsのordinary use向けとし、第三者向けproduct/serviceを構築するdeveloperにはAPI keyを求めている。[7]
- 本設計は一人のownerの開発Mac上で公式Claude Codeを起動するlocal automationまでを対象とする。共有service、他人へのClaude proxy、外部顧客向けautomationへ拡張する場合は、契約・課金方式を再判定する。

従って「bridgeから起動したから自動的にAPI従量課金」「公式CLIだから規模を問わずsubscription利用が保証される」のどちらも前提にしない。実機のlogin method、organization、usage表示をpilot gateとする。

Anthropic側の課金・認証条件とは別に、会社支給PC、Team seat、organization policyがPDA由来のtask実行を許すかも独立したgateである。許可が確認できない場合、このlaneはorganization-authorized workだけへ限定し、personal PDA taskを送らない。

## 3. Authority and responsibility split

### 3.1 PDA / Hermes

PDAは上位発注者兼integratorとして、次を所有する。

- owner intentと優先度
- task decompositionとdependency
- taskごとの情報選別
- account / information boundary
- acceptance criteria
- owner-only decisionの識別
- resultの独立検証
- retry、reframe、abandonの判断
- owner-facing final report

Claudeへraw chat、全memory、全PKBを渡さない。PDAはtaskに必要なcontext capsuleだけを選ぶ。

### 3.2 Kanban board

Kanbanはdurable control planeである。

保持するもの:

- 発注内容とacceptance criteria
- assignee lane
- dependency
- priority
- claim/run identity
- commentと質問
- blocked reason
- result summaryとartifact handle
- review / completion state

保持しないもの:

- remote SQLite mount
- Claudeの全transcript
- 巨大なtool log
- repository checkout
- secret

### 3.3 Development Mac worker bridge

bridgeはLLMではなくdeterministic processである。

責務:

- ready cardの低コストpoll
- atomic claim
- card schema / policy validation
- logical repository mapping
- task-specific worktree作成
- sanitized environmentでのClaude launch
- job ID / session UUID / Kanban run IDのjournal
- Agent View stateの同期
- local outbox
- idempotent result delivery
- crash / reconnect reconciliation

bridgeはtaskの意味を再解釈しない。routeや権限を拡張せず、不正なcontractはClaudeへ渡さずblockする。

### 3.4 Claude Code

Claude Codeは開発executorである。

責務:

- repository理解
- plan、implementation、test、review
- task contractに沿った質問
- task-specific result packet作成
- Git artifactの保全

Claudeのprose上の「完了」はcontrol-plane上の完了ではない。bridgeとPDAがresult packet、Git state、test evidenceを検証して初めて完了となる。

### 3.5 Human operator

ownerは通常、Kanbanの全実行を監視しない。Claudeがpermission、input、usage-credit consentなど人にしか処理できない状態になった場合だけ、Agent Viewでsessionへ入る。

## 4. Board placement and terminal lane

### 4.1 The board lives on the PDA host

boardの正本は常時稼働するPDAへ置く。

理由:

- Macがsleep / rebootしても発注が残る。
- Hermesがpriorityとdependencyを直接管理できる。
- SQLite fileをSSHFS、Syncthing、shared filesystemで複製しなくてよい。
- 通常経路は既にあるMac → PDAのSSH方向だけで成立する。

逆向きSSH tunnelは、direct inspection、rescue、bounded synchronous advisor用の補助経路にできるが、task retentionの依存にはしない。

### 4.2 Dedicated board and assignee

初期構成:

- board slug: `dev-main`
- external assignee lane: `main-claude`
- default concurrency: 1
- hard maximum during pilot: 2

`main-claude`はHermes profileとして作らない。Hermes v0.20.2の現行dispatcherは、実在しないprofile名を持つready taskを`skipped_nonspawnable`へ分類し、自動spawnせず、terminalが`claim_task`相当でpullするcontrol-plane laneとして扱う。

この挙動は2026-08-18にisolated temporary boardで実証した。

```json
{
  "assignee": "main-claude",
  "status_before_claim": "ready",
  "dispatch_bucket": "skipped_nonspawnable",
  "external_claim": "succeeded",
  "guarded_completion": "done"
}
```

これは現行Hermes sourceの実装契約であり、公開Kanban概念だけから永久に保証されるものではない。Hermes upgrade時にregression probeを必ず再実行する。

### 4.3 Do not use PDA workspace paths on the Mac

Hermes Kanbanの`workspace`はsingle-host semanticsでPDA上に解決される。`worktree:<path>`や`dir:<path>`へMacのpathを書いても、PDA worker pathとして扱われるため使わない。

external laneのcardはcontrol-plane workspaceとしてdefault `scratch`を許容するが、Mac bridgeは返されたPDA workspace pathをrepository pathとして使用しない。

cardは`repo_key`を持ち、Mac側allowlistでのみlocal pathへ解決する。

```json
{
  "repo_key": "pda",
  "allowed_path": "/Users/<owner>/projects/pda"
}
```

cardから任意のabsolute pathを受け取って実行してはならない。

## 5. Task contract

Kanban bodyは会話文ではなく、versioned execution envelopeとする。generic cognitive contractを`task`として埋め込み、`../../schemas/delegation-task-v1.schema.json`で検証する。Mac transport固有情報は`execution`へ分離する。

初期envelopeのillustrative shape:

```json
{
  "schema": "pda.dev-mac-task/v1",
  "task": {
    "schema": "pda.delegation-task/v1",
    "task_id": "pda-issued-stable-request-id",
    "objective": "one observable outcome",
    "acceptance_criteria": ["observable pass condition"],
    "non_goals": ["scope exclusions"],
    "task_class": "durable_execution",
    "ambiguity": "medium",
    "information_class": "public",
    "context_capsule": {
      "facts": [],
      "decisions": [],
      "preferences": [],
      "assumptions": []
    },
    "route": {
      "lane": "claude-code",
      "requested_model": null,
      "execution_host": "dev-mac",
      "durable": true
    },
    "permissions": {
      "mode": "workspace-write",
      "write_scope": ["repo:pda"],
      "network": "allowlisted",
      "owner_gate": "before_external_side_effect"
    },
    "egress": {
      "target_account_class": "dev-mac-team-claude",
      "authorization_status": "not_required",
      "authorization_ref": null,
      "context_selection_ref": null
    },
    "budget": {
      "max_model_iterations": 100,
      "max_wall_seconds": 7200,
      "max_concurrency": 1,
      "retry_limit": 0
    },
    "result_contract": {
      "required_artifacts": ["pda-result.json"],
      "verification": ["task-specific acceptance checks pass"],
      "effective_model_required": false
    }
  },
  "execution": {
    "repo_key": "pda",
    "base_ref": "origin/main",
    "session_mode": "claude-background",
    "bridge_claim_grace_seconds": 600
  }
}
```

ここで`task.task_id`はPDAがcard作成前に発行するstable request identityであり、以後`request_id`と呼ぶ。Kanban createの`idempotency_key`にも同じ値を使う。Kanban自身が返す`id`は別のboard identityで、以後`kanban_task_id`と呼ぶ。bridgeは`kanban_task_id`をlist / claim responseから取得し、run fencing、branch、worktree、session name、outbox keyに使う。生成後の`kanban_task_id`を作成前のbodyへ埋め込めるとは仮定しない。

D3実装前に、このenvelopeをJSON Schemaとしてversion controlへ追加する。実装が先行して暗黙のfieldを増やしてはならない。

Card creation invariants:

- 一つのcardは一つのobservable outcomeだけを持つ。
- `idempotency_key`を必須にし、Hermes retryでduplicate cardを作らない。
- write scopeが重なるcardを同時実行しない。
- personal contextをTeam accountへ送るtaskはtask固有authorization referenceを持つ。
- secretはbody、comment、attachmentへ置かない。
- external side effectは実装taskと分け、owner gateを持つ。
- large contextは最初のpilotでは送らない。将来attachment取得を実装する場合も、restricted bridge APIを通す。

## 6. Claim, run fencing, and idempotency

### 6.1 At-least-once, not exactly-once

network、process、machine failureがあるため、transport全体をexactly-onceとは見なさない。

代わりに次を組み合わせる。

- `request_id` (`task.task_id`) / Kanban `idempotency_key`: duplicate submissionを防ぐrequest identity
- `kanban_task_id` (Kanban row `id`): claim後のboard / execution identity
- `run_id` (Kanban current run ID): attempt fencing token
- Claude job ID / session UUID: execution identity
- Git branch / worktree: durable code identity
- local journal: launch identity
- local outbox: delivery identity

### 6.2 Claim protocol

bridgeは次の順序を守る。

1. `ready + assignee=main-claude`をJSONでlistする。
2. local policyで一件選ぶ。
3. exact `kanban_task_id`をatomic claimする。
4. claim直後にcurrent running run IDを取得する。
5. `(request_id, kanban_task_id, run_id)`をlocal journalへfsync相当で保存する。
6. 既存Claude mapping / outboxをreconcileする。
7. launch直前にtaskが同じrun IDでrunningであることをread-backする。
8. 新規実行が必要でclaimが有効な場合だけworktreeとClaude sessionを作る。

現行CLIの`hermes kanban claim --ttl`はdefault 900秒である。2026-08-18のv0.20.2 source確認では、CLI action `hermes kanban heartbeat`は`heartbeat_worker()`へ入りlivenessを記録するが、`claim_expires`を延長しない。別のinternal API `heartbeat_claim()`はleaseを延長するがCLI heartbeatからは呼ばれず、さらにCLIをSSHごとに起動するとclaimer PIDが変わるため、外部workerが別processから所有者として安全に使える契約ではない。isolated temporary boardでも60秒TTLのclaimにCLI heartbeatを発行し、`last_heartbeat_at`だけが記録され`claim_expires`が同値のままであることを実測した。

従ってv1 bridgeは、claim時に`task.budget.max_wall_seconds + execution.bridge_claim_grace_seconds`をTTLとして指定し、CLI heartbeatだけでlease延長できると仮定しない。人間入力待ちで長時間停止する前にはcardを`blocked/needs_input`へ移し、そのrunを閉じる。将来Hermesがstable external claim tokenを公開した場合にだけrenewal方式を再評価する。

### 6.3 Run fencing

全terminal lifecycle writeは、claim後に取得したrun IDを一緒に送る。

restricted PDA wrapperは次をremote environmentへ設定してからHermes CLIを呼ぶ。

```text
HERMES_KANBAN_TASK=<kanban_task_id>
HERMES_KANBAN_RUN_ID=<run_id>
```

`run_id`はClaudeへ渡すtask contractにもmodel-authored executor payloadにも含めない。これはbridge / PDAだけが所有するattempt identityである。Claude sessionが`needs_input`を跨いで同じ`request_id`の作業を継続しても、bridgeはunblock後に得たcurrent `run_id`へexecutor payloadをbindingし、control-owned final resultを生成する。modelはKanban lifecycle commandを直接実行せず、古いrun identityを持ち越すこともない。

これにより、lease切れ後の古いMac processが、新しいrunを誤ってcomplete / block / request-reviewすることを拒否できる。

isolated board probeでは、run 2をreclaim後にrun 3をclaimし、古いrun 2からのcompletionはexit 1で拒否され、run 3だけがtaskをdoneへ移せた。

### 6.4 Local journal states

bridge journalは最低限、次を保持する。

```text
claimed
worktree_ready
claude_starting
claude_running
needs_input
result_local
result_delivered
verified
closed
```

再起動時は「cardがrunningだからClaudeを起動する」と短絡しない。journal、Agent View、worktree、outboxを照合してから、新規launch、reattach、result resend、blockのいずれかを決める。

## 7. Git isolation

bridgeが`kanban_task_id`からdeterministic branchとworktreeを先に作り、そのworktree内で`claude --bg`を起動する。

```text
branch:   pda/<kanban_task_id>
worktree: <repo>/.worktrees/pda/<kanban_task_id>
```

Claude Codeはbackground sessionを通常、edit前に`.claude/worktrees/`へ移すが、既にlinked worktree内で起動したsessionは追加worktreeを作らない。[3] 同じ公式文書は、Claude自身が作っていないcheckoutではcommitやbranch switchの前に確認を求め得ることも示す。[3] v1ではこの差をunattended promptで解消せず、Git lifecycleをbridge側へ固定する。

bridge-created worktreeを使う理由:

- `kanban_task_id`からpathとbranchを再構成できる。
- Agent View session削除とworktree削除を結合しない。
- 既存dirty checkoutへ書かない。
- 並行中の別threadをstash / reset / stageしない。
- Claudeが自動生成したworktree pathの解析へ依存しない。

Rules:

- base refをfetch後のcommitへpinする。
- 既存branch/pathがある場合は、journalと一致しなければfail closedする。
- v1ではClaudeにbranch switch、commit、push、PR作成、mergeを許可しない。Claudeは既に選ばれたworktreeでedit / testし、executor payloadを返す。
- bridgeがdiffとacceptance evidenceを独立検証した後、cardが許可する場合だけdeterministic local commitを作る。push / PR作成は別の明示permission / owner gateを要求する。
- `main` / `master`へ直接commit、force push、mergeしない。
- sessionを削除する前にlocal commit、push、または明示的artifact退避を確認する。
- unknown dirty stateをcleanup目的で変更しない。
- M1/M4でpre-created linked worktree内のedit / testが追加のcommit・branch promptなしで完了し、禁止したGit操作へClaudeが進まないことを実機確認する。

## 8. Claude launch contract

### 8.1 Command shape

bridgeはshell stringではなくargv arrayで公式CLIを起動する。

```text
claude
  --bg
  --name pda-<repo_key>-<kanban_task_id>
  [--model <requested_model>]
  <fixed instruction pointing to a validated local task file>
```

`--bg`のpromptはpositional argumentであり、`-p`を付けない。[3] `task.route.requested_model`が`null`なら`--model` flag自体を省略し、verified Team defaultを使う。non-nullの場合だけflagを渡す。どちらの場合もrequested valueと、取得可能なcontrol-owned effective-model evidenceを別に記録する。

Untrusted card bodyをremote shell commandへ展開しない。bridgeはJSONをvalidationし、Mac上のtask fileへ保存し、Claudeにはそのpathと固定instructionだけを渡す。

### 8.2 Permission posture

pilotでは`--dangerously-skip-permissions`を使用しない。

- project settingsでknown read/edit/test commandとread-only Git (`status`, `diff`, `log`)だけを許可し、`commit`, `checkout`, `switch`, `push`, `gh pr`等のGit mutationをdenyする。
- unknown network、credential access、external side effectはAgent Viewでhuman inputにする。
- permission promptを「自動化の失敗」ではなく、明示的な`needs_input` stateとして扱う。

### 8.3 Authentication posture

bridgeは通常Claude Codeを使うのと同じmacOS user、同じClaude config directoryで動かす。

Claude Codeはcloud provider credential、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY`、`apiKeyHelper`、`CLAUDE_CODE_OAUTH_TOKEN`、profile/federation credentialをsubscription `/login`より優先する。[5]

launchd environmentから、Team OAuthより優先される不要なcredential / provider variableを除外する。少なくとも次をpreflight対象にする。

```text
CLAUDE_CODE_USE_BEDROCK
CLAUDE_CODE_USE_VERTEX
CLAUDE_CODE_USE_FOUNDRY
ANTHROPIC_AUTH_TOKEN
ANTHROPIC_API_KEY
CLAUDE_CODE_OAUTH_TOKEN
ANTHROPIC_PROFILE
ANTHROPIC_FEDERATION_RULE_ID
ANTHROPIC_ORGANIZATION_ID
ANTHROPIC_BASE_URL
```

`apiKeyHelper`やproject settingsも確認する。最初のsupervisorはsanitized environmentから起動する。`claude auth status`とinteractive `/status`でTeam organization / login methodを確認し、そのevidenceをcontrol-owned preflight recordへ保存する。

wrong account、unknown account、API key、personal OAuthを検出した場合、cardをblockし、PDAホストのpersonal Claudeへfallbackしない。

### 8.4 Model and usage-credit posture

Fable必須taskでは`claude-fable-5`をrequestするが、request文字列だけをeffective model証明にしない。organization allowlist等によりstartup時にmodel substitutionが起こり得る。[9]

またFable 5はplan / seatによってusage creditsを使う場合がある。interactive sessionではconsent promptが出るが、`-p` / Agent SDKではpromptなしで課金される。[9] `--bg`はfull interactive sessionなので本設計に適するが、background時の実際のconsent挙動はMac pilotで確認する。

現行`claude agents --json`のdocumented fieldにはeffective modelがない。[3] 従って、D3でsupportされたmachine-readable attestationを確立するまで、Fable-specific taskの完全自動acceptanceは行わない。最初のpilotはAgent View / `/status`で人がmodelとbilling stateを確認し、control-owned evidenceを残す。

## 9. Session state synchronization

bridgeは次をpollする。

```text
claude agents --json --all --cwd <allowed-repo-path>
```

job IDとsession UUIDをjournalへ保存し、`kanban_task_id`をsession nameに含めてcrash reconciliationを可能にする。

Launch commit protocol:

1. `claude --bg --name ...`のstdoutからshort job IDを取得する。
2. `claude agents --json --all --cwd <repo>`から同じjob IDのsession UUIDとnameをread-backする。
3. `(request_id, kanban_task_id, run_id, job_id, session_uuid, name)`を一つのatomic journal recordとして保存して初めて`claude_running`とする。
4. bridgeがlaunch後・journal前にcrashした場合、restart時にexact deterministic nameでinventoryを検索する。unique matchならadoptし、0件または複数件ならduplicateを起動せずblockしてmanual reconciliationへ回す。

PDAホスト上のClaude Code v2.1.205では、explicit `--name pda-recovery-probe`で起動したidle background sessionが`claude agents --json --all`に同じ`name`、job ID、session UUIDを返すことを2026-08-18に確認した。Mac M1でも同じ契約を再確認し、name fieldが得られないversionではこのrecovery pathを有効化しない。

Mapping:

| Claude state | Kanban action |
|---|---|
| working | runningを維持し、bounded heartbeat / progress comment |
| blocked + permission prompt | `blocked/needs_input`; Agent View link instruction |
| blocked + input needed | `blocked/needs_input`; one concrete question |
| done + valid local result | request-reviewまたはcomplete handoff |
| done + missing/invalid result | contract failureとしてblock |
| failed | failure categoryを記録し、PDAがretry可否判断 |
| stopped | operator stopかcrashかを判定し、blind respawnしない |

### 9.1 Human input loop

v1では、実行中sessionへHermesがshellから任意promptを注入する非公開workaroundを作らない。

1. bridgeがClaudeの`waitingFor`を検出する。
2. boardへ一問、session name、job IDを記録して`needs_input` blockする。
3. ownerが`claude agents`または`claude attach <job-id>`で回答する。
4. bridgeがsessionの再開を検出する。
5. boardをunblockし、新runをclaimする。
6. 同じClaude session mappingを再利用し、新しいsessionを作らない。

将来、Hermesが自動回答すべき価値が明確になった場合だけClaude Code Channelsを評価する。ChannelsはResearch Previewであり、Team / Enterpriseではadmin enablementが必要で、eventはsessionが開いている間だけ届くため、v1の必須依存にしない。[10]

## 10. Result and outbox protocol

Agent Viewの`done`表示だけでtaskを完了しない。

Claudeへ、documented `$CLAUDE_JOB_DIR/tmp`配下へexecutor payloadを書かせる。[3]

```text
$CLAUDE_JOB_DIR/tmp/pda-result.json
```

このfileはmodel-authored `pda.executor-result/v1`であり、未検証の主張として扱う。最低限次を含む。

- task identity (`request_id`)
- concise summary
- worktree / branch reference and changed paths
- suggested commit message when useful
- tests and reported outcomes
- unresolved uncertainty
- owner decision request
- reported failure category

Claudeに`principal_attestation`、effective account、verified state、commit / PR handle、最終`status=succeeded`を自己申告させない。bridgeがexecutor payloadを検証し、Git / test / auth evidenceをread-backし、許可されたGit actionを実行した後、control-owned fieldsを加えて`../../schemas/delegation-result-v1.schema.json`に適合するfinal handoffを組み立てる。`pda.executor-result/v1`自身のschemaもD3実装前にversion controlへ追加する。

bridgeはClaude job directoryからexecutor payloadを検出したら、Claude session削除より先にbridge-owned storageへatomic copyする。cardがその時点でblockedなどcurrent runを持たない場合は、まず`intake/<job_id>/<digest>.json`へunbound payloadとして保存し、同じsession mappingを確認してunblock / claimした後にだけrun-specific outboxへbindingする。

```text
~/Library/Application Support/pda-claude-bridge/outbox/intake/<job_id>/<digest>.json
~/Library/Application Support/pda-claude-bridge/outbox/<kanban_task_id>/<run_id>.json
```

delivery rules:

- journalでcurrent `kanban_task_id`へmappingされたjob directoryだけからpayloadを読む。
- executor payloadの`request_id`がcard contractと一致し、payload digestが未配信であることを確認する。
- result payloadをschema validationする。
- branch、commit、test evidenceをMac上で独立read-backする。
- final handoff作成直前にcardがcurrent `run_id`でrunningであることをread-backする。
- outboxを書いてからSSH deliveryする。
- delivery acknowledgementを得てから`result_delivered`へ進める。
- SSH切断時は同じdigestのresultだけ再送し、modelを再実行しない。
- stale run IDのresultはPDA側で拒否する。
- raw transcriptや巨大logはboardへ貼らず、session ID / artifact referenceだけを置く。

## 11. SSH boundary

通常operationはMac → PDAのSSHだけで成立する。

本番bridge用には既存の人間用SSH keyと別のdedicated keyを使い、PDA側`authorized_keys`でforced command wrapperへ限定する。entryは概ね次の形とし、実際のabsolute pathとpublic keyを入れる。

```text
restrict,command="/absolute/path/pda-kanban-bridge" ssh-ed25519 <bridge-public-key>
```

`restrict`でPTY、agent forwarding、port forwarding、X11 forwarding等を無効化し、wrapper以外のshellを起動させない。

wrapper allowlist:

- board: `dev-main` only
- assignee: `main-claude` only
- reads: list, show, runs, context
- worker writes: claim, heartbeat, comment, block, request-review, complete
- guarded resume: unblock + claim for an already-mapped session
- no archive, arbitrary assign, board switch, profile management, shell, file read

Inputはstructured JSON over stdinとし、`request_id`、`kanban_task_id`、`run_id`、field size、state transitionをvalidateする。任意の`hermes kanban ...`文字列をSSH commandとして受け入れない。

## 12. Failure semantics

| Failure point | Required behavior |
|---|---|
| Mac offline before claim | card remains ready |
| PDA / SSH offline | Mac does not invent work; retries with backoff |
| SSH drops after claim, before launch | journaled claim is reconciled; no blind duplicate |
| bridge crashes after `claude --bg`, before mapping write | exact deterministic nameでinventoryを検索し、unique matchだけをadoptする; 0/複数ならduplicate launchせずblock |
| Claude completes, SSH is down | local outbox persists; deliver later without rerun |
| claim expires | old run is fenced; existing Claude session is reconciled before new launch |
| Claude needs input | board blocks; owner attaches through Agent View |
| Mac sleeps | session and card remain; supervisor reconnects on wake |
| Mac shuts down | session may show failed; attach/respawn from saved conversation, never create a second session first |
| wrong auth / quota / usage-credit gate | block; no personal-account fallback |
| session deleted before artifact safety | policy violation; do not auto-delete until commit/push/outbox verified |

Agent Viewはsleepではsessionを保存するが、machine shutdownはrunning sessionを停止し、後からattach / reply等で再開する。[3]

## 13. History and retention

Claude Code transcriptはlocalに継続保存され、background sessionをAgent View listから削除しても`claude --resume`から利用できる。[3]

ただしlocal transcriptのdefault cleanup periodは30日である。[8] 「履歴が残る」を長期保証にするには、Macのorganization policyを確認した上で`cleanupPeriodDays`を決める。

推奨初期値:

- active development transcript: 365 days if Team policy permits
- canonical result: Git / PR / Kanban summary
- raw transcript: audit aid, canonical fact sourceではない
- session UUID: Kanban result metadataへ保持

Agent ViewはResearch Previewである。[3] Claude Code upgrade時にはCLI flags、JSON fields、session picker、worktree behaviorをsmoke testする。

## 14. Security and information boundaries

- Team accountへ送るcontextはpublicまたはtask単位で明示選択した範囲に限定する。
- personal contextの包括送信は、この設計承認に含まれない。
- company workとpersonal PDA workを同じcardへ混ぜない。
- secretはcard、prompt、resultへ入れず、Mac上のapproved credential mechanismからtoolへ渡す。
- Claude sessionはuser authorizationを偽装しない。
- bridgeはowner gateを自動解除しない。
- task content、comment、resultはuntrusted dataとしてparseする。
- Kanban board isolationはcontrol boundary、assignee名はrouting labelでありOS security boundaryではない。

Team / EnterpriseのClaude Code dataはcommercial policyに従い、標準retentionは30日、model trainingにはorganizationの明示opt-inがない限り使われない。[8] ただしorganization admin visibility、company policy、送信可能情報はAnthropicの一般仕様だけでなく所属組織のpolicyに従う。

## 15. Implementation sequence

### M0 — design record

- この文書をversion controlへ置く。
- parent routing designから参照する。
- external terminal laneとrun fencingのisolated probeを残す。

Exit: architecture、authority、risk、pilot gateが明示されている。

### M1 — Mac capability and billing preflight

- Claude Codeをcurrent supported versionへupdateする。
- `claude --bg`、`claude agents --json --all`、`attach`、`respawn`をharmless taskで確認する。
- explicit `--name`がAgent View JSONへ返り、launch後・journal前crashからunique adoptionできることをinjection testする。
- bridge-created throwaway linked worktree内でedit / testを実行し、Claudeがcommit / branch switchへ進まず追加promptなしでexecutor payloadまで到達することを確認する。
- background sessionがAgent Viewと`--resume` pickerへ残ることを確認する。
- Team organization / login method / higher-priority credential不在を確認する。
- 会社PC / Team seatで対象task classを実行してよいことをorganization policy上確認する。
- default modelでsubscription usage attributionを確認する。
- Fable 5のavailability、effective model、usage-credit consentを別のread-only taskで確認する。

Exit: session history、principal、billing behaviorが実機で確認済み。

### M2 — restricted PDA board surface

- `dev-main` boardを作る。
- `main-claude` external laneを作る。
- dedicated SSH keyとforced wrapperを導入する。
- idempotent create、list、claim、run-fenced lifecycle writeをtestする。
- short TTLでclaimし、CLI heartbeat後もexpiry時刻が延長されずsafe reclaimされることを実時間probeする。

Exit: Mac keyは許可board / lane以外を操作できない。

### M3 — deterministic Mac bridge

- launchd jobを導入する。
- repo allowlist、schema validator、worktree managerを実装する。
- local journal、outbox、Agent View reconcilerを実装する。
- concurrency 1、bounded backoff、quota stopを設定する。

Exit: empty queueはmodelを使わず、card一件が一sessionだけを作る。

### M4 — harmless end-to-end pilot

- public / throwaway repositoryで一cardを作る。
- create → claim → worktree → `--bg` → result → verification → doneを通す。
- SSH lossをClaude完了後・result delivery前に発生させる。
- bridge再起動後、model再実行なしでresultだけ届くことを確認する。
- `needs_input`を一度発生させ、Agent View回答後に同じsessionが再開することを確認する。payloadがnew run claimより先に完成するcaseも注入し、unbound intakeからcurrent runへ一度だけbindingされることを確認する。

Exit: disconnect、human input、history、artifact safetyを含むE2Eが通る。

### M5 — production hardening

- retention、cleanup、observability、quota policyを確定する。
- real repositoryの一つだけをallowlistへ追加する。
- personal context / Fable policyは別owner decisionとして扱う。
- Hermes / Claude upgrade regression probesを定例化する。

Exit: limited production laneとして利用可能。

## 16. Acceptance tests

1. 同じidempotency keyで二度createしてもcardは一件だけである。
2. `main-claude` cardをHermes dispatcherが自動spawnせず、`skipped_nonspawnable`として残す。
3. Mac bridgeだけがready cardをclaimできる。
4. claim後のrun IDがjournalへ保存される。
5. reclaim後の古いrunからcomplete / block / request-reviewできない。
6. 一cardにつきClaude sessionは一つだけ作られ、launch後・journal前crashでもexact nameのunique sessionをadoptしてduplicateを作らない。
7. `claude --bg` sessionがAgent View、`claude agents --json --all`、session pickerに現れる。
8. sessionは正しいbridge-created worktreeでedit / testし、既存dirty checkoutを変更せず、Git mutationはbridgeだけが行う。
9. active credentialがMac Team OAuthであり、API key / personal OAuth / gatewayへ逸れていない。
10. empty pollはClaude model requestを発生させない。
11. permission / input waitがKanban `needs_input`へ反映される。
12. owner回答後、新sessionではなく同じsessionが継続する。payloadがreacquireより先に完成してもunbound intakeへ保全され、bridge-built final resultだけがcurrent `run_id`へ一度だけbindingされる。
13. Claudeの`done`だけではcardをcompleteできず、valid executor payloadとbridge-built final resultが必要である。
14. SSH loss後、outboxからresultだけが再送され、Claudeは再実行されない。
15. Mac shutdown後、保存sessionをrespawnして継続できる。
16. branch / commit / test evidenceをPDAが独立に確認する。
17. wrong account、model mismatch、unexpected usage creditでfail closedする。
18. sessionを削除しても必要なGit artifactとresultが残る。
19. 30日を越えるhistory retention policyが明示される。
20. ownerは`claude agents`からtask名、状態、質問、full conversationを確認できる。

## 17. Open decisions

### OD-M1: Personal context on the Team principal

Question: public / minimized contextを越えて、PDAのpersonal contextを会社Team accountへ送ってよいか。

Recommendation: pilotでは許可しない。organization policyと実価値を確認してからtask classごとに決める。

### OD-M2: Fable usage credits

Question: Team seatのincluded limit外でFable 5がusage creditsを使う場合、自動継続を許すか。

Recommendation: 初回のinteractive consentとusage表示を確認するまで自動継続しない。以後も月額上限をcontrol-owned policyにする。

### OD-M3: Transcript retention

Question: local Claude Code transcriptを何日保持するか。

Recommendation: Team policyが許せば365日。canonical evidenceはGit / PR / Kanban resultとし、raw transcriptだけへ依存しない。

### OD-M4: Automated follow-up input

Question: HermesがClaudeの質問へ自動回答する二方向pushを追加するか。

Recommendation: v1はAgent Viewでhuman reply。E2Eが安定した後だけChannelsを評価し、UI injectionやundocumented transcript writeは行わない。

## 18. Current verified state

2026-08-18時点:

- 作成開始時のPDA repository main working treeには別threadの未commit変更があったため、本設計はisolated `design/delegation-routing` worktreeで作成した。
- Hermes v0.20.2のisolated temporary boardで、non-profile assigneeのdispatcher skip、external claim、guarded heartbeat、guarded complete、stale run rejectionを実行確認した。CLI heartbeatが`claim_expires`を更新しない点はsource read-backで確認し、実時間のTTL-expiry probeはM2に残した。
- PDAホスト上のClaude Code v2.1.205で、explicit `--name`がAgent View JSONのname / job ID / session UUIDへread-backされることをharmless idle sessionで確認し、probe sessionは削除した。
- 開発MacへのPDA側reverse SSH listenerは未確認であるが、通常設計はMac → PDA方向だけを使うためblockerではない。
- Mac上のTeam-authenticated Claude Code、Agent View表示、subscription attribution、Fable consentの実機E2Eは未実施であり、M1 gateとして残る。
- この文書はimplementation完了を主張しない。

## Sources

[1] https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban — Hermes Kanban
[2] https://code.claude.com/docs/en/cli-reference — Claude Code CLI reference
[3] https://code.claude.com/docs/en/agent-view — Claude Code Agent View
[4] https://code.claude.com/docs/en/sessions — Claude Code sessions
[5] https://code.claude.com/docs/en/authentication — Claude Code authentication
[6] https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan — Use the Claude Agent SDK with your Claude plan
[7] https://code.claude.com/docs/en/legal-and-compliance — Claude Code legal and compliance
[8] https://code.claude.com/docs/en/data-usage — Claude Code data usage
[9] https://code.claude.com/docs/en/model-config — Claude Code model configuration
[10] https://code.claude.com/docs/en/channels — Claude Code channels
