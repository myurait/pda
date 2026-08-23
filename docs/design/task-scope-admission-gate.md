# PDAタスク・スコープ審査ゲート設計

Status: Implemented through rollout S1; S3-M1 design decided 2026-08-23 (D-S3-6 pending owner decision); production activation pending
Checked: 2026-08-18 JST
Initial target: Hermes Agent v0.20.2 on the PDA runtime

## 1. Purpose

ユーザーの依頼を完了するために必要な作業と、エージェントが追加で「やった方がよい」と判断した作業を分離し、後者が無審査で実行されることを防ぐ。

直接の再現対象は、`commit / push`依頼に対して、全worktree監査、競合解消、広範なテスト、複数branch照合、別cutoverの待機まで実行し、1時間以上を消費した事例である。

このゲートは安全承認だけを扱うものではない。安全でも依頼外なら止める、時間・利用枠・ユーザーの待ち時間を守るためのscope admission controlである。

## 2. Decision

PDAは各ユーザーturnを、実行前に一つの`ScopeContract`へ固定する。以後のtool callは、次のいずれかに分類できる場合だけ実行する。

1. `required`: 依頼された成果を直接作る。
2. `prerequisite`: required actionの直前に不可欠な一段の前提を満たす。
3. `verification`: 固定済みの完了条件だけを確認する。
4. `expansion`: 新しい成果、対象、修復、品質向上、調査、待機を追加する。

`required`、必要最小限の`prerequisite`、固定済みの`verification`は契約内で許可する。`expansion`は別の審査を通らない限り実行しない。狭い終了処理ではexpansion budgetを0とし、審査モデルも自動承認できない。

中核原則は次の二つである。

- Permission is not scope: 「成果があればcommitしてよい」という恒常許可は、commitという外部作用を許可する。全worktreeを修復する目的を追加しない。
- Confidence is not scope: 追加テストや周辺監査で確信度が上がっても、それだけでは依頼上の必要作業にならない。

## 3. Invariants

### INV-S1: one outcome per turn

契約の`objective`は一つの観測可能な成果にする。複数の独立成果が明示されていない限り、一つの依頼から隣接プロジェクトを開始しない。

### INV-S2: target set is closed

対象repository、worktree、branch、service、account、file scopeをdiscovery後に固定する。固定後に見つかった別対象は、自動で追加しない。

### INV-S3: one-hop prerequisites

狭いtaskでは、required actionに直接必要な前提だけを許す。その前提を改善するための追加修復は二段目の目的であり、expansionとする。

例: `git commit`前の差分確認は許可する。競合を解消してcommit可能にする編集は許可しない。

### INV-S4: verification is predeclared

verificationは契約lock時に完了条件と対応付ける。「念のため」を理由に増やさない。実装依頼なら対象テストを許可できるが、repository closeoutだけならfull test suiteは許可しない。

### INV-S5: completion closes execution

完了条件が満たされた後は、最終状態のread-backと報告以外のtool callを拒否する。新たに見つかった改善候補は記録または簡潔な残存事項にし、同じturnで着手しない。

### INV-S6: blockers do not silently become new tasks

競合、失敗テスト、壊れたworktree、別processの未完了を発見しても、現在の成果に必須で契約内でない限り修復しない。必要なら`blocked`として一度だけ報告する。

### INV-S7: authority remains separated

Scope reviewerは、ユーザーの依頼に照らして作業を許可または拒否する。新しいユーザー目的、承認、恒常方針を生成できない。

### INV-S8: enforcement is independent of agent self-restraint

prompt上の注意だけに依存しない。side effectとbudgetはHermesのtool boundaryで機械的に審査する。

## 4. Task classes and initial budgets

初期実装は高精度に判定できる狭いclassから始める。数値はpilotで較正する運用値であり、憲章ではない。

| Class | Typical request | Default boundary | Initial budget | Expansion |
|---|---|---|---|---|
| `answer-only` | 状態確認、短い回答 | read-only | 5分、tool call 12 | 0 |
| `repository-closeout` | commit、push、既存成果の保存 | 既存差分だけ。内容編集なし | 最大15分、`min(32, 8 + 3 × target_count)` calls | 0 |
| `bounded-operation` | 一つの設定変更、restart、明示済みcutover | 一つのnamed target | 20分、32 calls | 必須recoveryを1回審査 |
| `artifact-change` | named feature/doc/fixの作成 | 固定write scopeと対象verification | 60分、96 calls | 最大2回審査 |
| `open-mission` | 長時間調査・実装 | 明示budgetとdurable checkpoint必須 | task固有 | task固有 |

明示的な対象数が不明な場合、最初に最大3回・120秒のread-only discoveryを許す。そこでtarget setと比例budgetを固定する。discovery自体をrepository全体の自由探索にしない。

`open-mission`が20分を越える見込みなら、既存のPDA delegation routingに従い、Git、artifact、Kanban/outbox等をdurable control planeにする。scope gateはdurability policyを置き換えない。

## 5. ScopeContract v1

実行時contractは次の意味を持つ。raw user messageは永続化せず、hashと正規化済みcontractだけを監査状態へ保存する。

```json
{
  "schema": "pda.scope-contract/v1",
  "turn_id": "opaque-hermes-turn-id",
  "origin_message_sha256": "...",
  "task_class": "repository-closeout",
  "objective": "現在の依頼で発生したcommit-ready成果をcommitし、remoteへpushする",
  "targets": {
    "repositories": ["/home/user/projects/pda"],
    "worktrees": ["/home/user/projects/pda"],
    "branches": ["main"]
  },
  "actions": {
    "required": ["commit-existing-content", "push-created-commit"],
    "prerequisite": ["inventory-status", "inspect-candidate-diff", "targeted-secret-check"],
    "verification": ["remote-ref-equals-local-head"],
    "forbidden": [
      "edit-content",
      "resolve-conflict",
      "run-broad-tests",
      "create-or-delete-worktree",
      "wait-unrelated-process",
      "deploy-or-restart"
    ]
  },
  "completion": {
    "all": [
      "every commit-ready target has a commit",
      "every created commit is reachable from its intended remote ref"
    ],
    "blocked_targets_may_be_reported": true
  },
  "budget": {
    "max_wall_seconds": 900,
    "max_tool_calls": 11,
    "max_denied_calls": 3,
    "max_expansions": 0,
    "background_processes": 0,
    "subagents": 0
  },
  "state": "locked"
}
```

`target_count=1`の例なのでtool budgetは`8 + 3 = 11`である。複数worktreeをユーザーが明示的に対象にした場合だけ、discovery結果に応じて上限を増やす。

Contract schemaは実装時にJSON Schema Draft 2020-12として固定する。validatorは少なくとも次を拒否する。

- objective、completion、target setの欠落。
- 狭いclassでの空または無制限write scope。
- `repository-closeout`で`max_expansions > 0`、background、subagent、content editを許す契約。
- 上限なしのwall time、tool calls、retry。
- ユーザー指示に存在しないproduction side effect。

## 6. Gate pipeline

```text
User message
  -> G0 high-precision class detection
  -> G1 bounded discovery and ScopeContract lock
  -> G2 pre-tool deterministic admission
       -> allow required/prerequisite/verification
       -> block unknown or expansion
  -> G3 explicit expansion review when class permits
       -> one-use permit for exact action fingerprint, or deny
  -> execute tool
  -> update atomic counters and evidence
  -> G4 completion check
  -> final response
  -> G5 post-turn audit
```

### G0: high-precision class detection

`pre_llm_call`で、原文、現在のturn、standing permissionsからclass候補を作る。

- `commit`, `push`, `保存して`, `close out`等だけが成果なら`repository-closeout`。
- `fix`, `実装`, `変更して`, `テストして`が明示されていれば、closeoutへ誤分類しない。
- 低confidence時は広い許可へ倒さない。read-only discoveryだけを許してagentにcontract案を出させる。

恒常許可はauthorization fieldにだけ反映し、objectiveやtarget setへ展開しない。

### G1: bounded discovery and lock

明示targetがある場合は直ちにlockする。`すべての未commit資源`のような依頼では、1回のbatched inventoryで候補を列挙し、対象集合を固定する。

lock前に許可するのは、対象を確定するためのread-only actionだけである。lockされていないturnからwrite、push、送信、restart、background、delegationを要求された場合は拒否する。

schema footprintを抑えるため、`scope_gate(action=lock|review|complete)`という一つのbootstrap control toolだけを別allowlistに置く。外部resourceへ作用せず、引数schema、current turn binding、state transitionをvalidator自身が確認できる場合だけcontract未lock時にも許可する。通常toolと同じ広い例外にはしない。

### G2: deterministic pre-tool admission

各tool callについて、次をatomicに行う。

1. `turn_id`に対応するactive contractを取得する。
2. wall time、tool count、target、background/subagent budgetを確認する。
3. toolと引数からaction class、resource、side-effect classを正規化する。
4. contractのallowlistと照合する。
5. allowならcounterを予約して実行する。denyならreason codeを返す。

並列tool callでは、SQLite transactionまたはprocess-local lockでbudgetを先に予約し、同時callが上限をすり抜けないようにする。

denyも`max_denied_calls`へatomicに計上する。同じturnで3回拒否された後は、`scope_gate(action=complete)`または最終報告へ閉じるためのcontrol action以外を拒否する。拒否された別toolを順番に試して500 iterationまで消費する経路を残さない。

Tool名だけでは判定しない。特に`terminal`はshell文字列をtokenizeし、認識できない複合commandを狭いclassでは拒否する。regexだけで安全またはscope内とみなさない。

### G3: expansion review

allowlist外のactionを自動実行せず、次の候補を作る。

```json
{
  "turn_id": "...",
  "tool_name": "...",
  "normalized_action": "...",
  "resource": "...",
  "reason": "why the original completion predicate cannot be met otherwise",
  "estimated_cost": {"seconds": 120, "tool_calls": 4},
  "action_fingerprint": "sha256(canonical tool name and arguments)"
}
```

審査順序:

1. Deterministic deny: forbidden action、closed target外、budget超過、classのexpansion budget 0。
2. Deterministic allow: contractが既に許すがnormalizerだけが未認識だった既知action。
3. Independent scope review: classが許す場合だけ、ユーザー原文、contract、候補actionをno-tools structured judgeへ渡す。
4. Unavailable/ambiguous: expansionはfail closed。必要ならownerへ一問だけ上げる。

reviewerは「有益か」ではなく、次の全条件だけを判定する。

- 元のcompletion predicateに不可欠か。
- より狭い代替がないか。
- target、risk、timeの増加がcontract上許されるか。
- optional hardeningや別taskではないか。

許可はexact fingerprint、短いTTL、one-useにする。executorの自己申告だけではpermitを発行しない。独立LLM reviewは品質上のsecond opinionでありsecurity boundaryではないため、hard boundsはdeterministic validatorが保持する。

### G4: completion check

完了判定はglobal cleanlinessではなくcontractのcompletionだけを見る。

- 成功: completion evidenceが揃った。
- partial: 一部targetのみ完了し、残りは契約外修復が必要。
- blocked: required actionを実行できず、安全な契約内回復がない。
- failed: 実行または検証が失敗した。

`repository-closeout`では、対象branchのlocal HEADとintended remote refの一致が成功証拠である。全worktree clean、全test green、別service healthyは、明示されない限り成功条件ではない。

### G5: audit

永続化するのは次だけとする。

- turn/sessionのopaque ID。
- task class、contract hash、targetの正規化識別子。
- tool count、duration、verdict、reason code、action fingerprint。
- completion statusとscope expansion数。

raw prompt、raw tool arguments、tool result、secretをscope auditへ複製しない。保持期間は初期30日とし、運用評価後に短縮可能とする。

## 7. `repository-closeout` policy

### Allowed

- 明示targetまたはbounded discoveryで確定したworktreeの`git status`。
- candidate diffのfile list、staged/unstaged contentの必要最小限の確認。
- candidate差分だけを対象にしたsecret・credential checkと`git diff --check`。
- 既存内容のstage、commit、push。
- local HEADとintended remote refのread-back。
- repositoryが要求するcommit hookがcommit command内で自動実行されること。

### Denied

- `write_file`、`patch`、editor、formatによる内容変更。
- merge conflict、unmerged index、失敗testの修復。
- full test suite、広範なlint、全branch review。
- branch/worktreeの作成、削除、reset、stash、rebase、merge。
- deploy、service restart、cutover、別processのwait/poll。
- `delegate_task`、Claude Code、background terminal。
- `execute_code`。内部で複数tool callを行えて親hookの意味的budgetを迂回し得るため、closeoutでは不要かつ禁止する。

### Blocker behavior

commit不能なconflictや所有権不明の差分を見つけた場合、内容を直さない。commit-ready targetだけを完了し、残りを一行のblockerとして報告する。ユーザーが修復まで明示した次turnで、新しい`artifact-change` contractを作る。

### Completion

1. 対象候補を一度だけ列挙した。
2. commit-ready差分を必要最小限確認した。
3. 作成したcommitがintended remote refから到達可能である。
4. commit不能対象があれば、原因と未保存状態を捏造せず報告した。

## 8. Hermes integration

Hermes coreを直接forkしない。canonical sourceはPDA repositoryの`integrations/hermes-scope-gate/`へ置き、active Hermes profileへplugin、validator、shell-hook configとしてdeployする。現在の実行profile名は`default`であり、repository内のportable PDA profileと混同しない。実装は`HERMES_HOME`からprofile-scoped state pathを解決する。

### Plugin responsibilities

- cache-safeな短いsystem prompt sectionとしてscope invariantsを登録する。
- `pre_llm_call`でturn contract候補を作り、current user messageへ注入する。
- `scope_gate`という一つのcontrol toolを提供し、`action=lock|review|complete`でstate transitionを分ける。
- SQLite stateとauditを管理する。
- `post_tool_call`と`post_llm_call`でevidenceと結果を記録する。

### Hard enforcement

公式の`pre_tool_call`はtool実行直前に発火し、`block`を返せる。インストール済みv0.20.2 sourceでも、agent-level toolsを含む共通`invoke_tool()`が、`todo`、`memory`、`delegate_task`等の分岐より先にhookを呼ぶことを確認した。

ただしPython plugin callbackの例外はHermesによりlogされ、base runtimeは継続する。したがってhard boundaryは同じvalidator executableを呼ぶshell `pre_tool_call`にも登録し、`fail_closed: true`にする。plugin hookは低遅延の通常経路、shell hookはfailure boundaryとする。

実装ではさらに`pre_tool_call`の全`modify` directiveが集約された後の実引数を`tool_execution` middlewareで再審査する。同一`tool_call_id`でfingerprintが変わればfail closedし、downstream handlerを呼ばない。これは善意のhook rewriteによる迂回を閉じる。任意コードを実行できる別のenabled plugin自体は同一信頼境界にあり、後段execution middlewareを追加する場合はS1の互換審査対象とする。

```yaml
hooks:
  pre_tool_call:
    - matcher: ".*"
      command: "/absolute/path/to/pda-scope-gate validate-tool"
      timeout: 3
      fail_closed: true
```

実装は`hermes hooks doctor`とsynthetic payload testに合格しなければ有効化しない。validator停止時にside effectを通すより、短いscope-gate障害として停止する。

### Current Hermes surfaces used

- `pre_llm_call`: 1 user turnにつき1回。contract contextの注入に使う。
- `pre_tool_call`: 全tool実行直前。block/modifyが可能。
- `post_tool_call`: 実行結果とcounterの観測。
- `post_llm_call`: 成功turnの監査。
- plugin system prompt section: session中byte-stableな常設policy。

`pre_verify`はcode edit後にagentを継続させるhookであり、一般的なscope縮小またはfinalization gateではないため中核に使わない。現在の公開hookには全surface共通のhard `pre_finalize`がないため、初期実装ではside effectをhard-blockし、`scope_gate(action=complete)`とprompt policyでfinal statusを閉じ、post-turn auditで逸脱を検知する。final claimまで機械的に拒否する必要性がpilotで確認された場合だけ、汎用`pre_finalize` contractをHermes upstreamへ提案する。

## 9. Bypass controls

- `terminal`: command parserでsubcommandとtargetを確認。認識不能なshell compositionは狭いclassでdeny。
- `execute_code`: nested tool useを内包するため、狭いclassではdeny。広いclassではscript hash、許可toolset、nested budgetを別contractにする。
- `delegate_task`: childへ親contractの縮小copyを必須化する。親scopeを広げられない。
- background process: task classが明示許可し、process lifetimeとcompletion evidenceをcontract化した場合だけ許可する。
- browser/MCP/plugin tools: tool名ではなくnetwork、write、external-side-effect capabilityで分類する。未知toolはdefault deny for mutation。
- direct filesystem or Git action from a plugin: scope-gate control tools以外のplugin dispatchも同じpre-tool pathを通すことをtestする。通らないhost APIが見つかれば、狭いclassではそのplugin capabilityを無効化する。

## 10. Incident replay acceptance tests

元事例をfixtureとして、少なくとも次を自動検証する。

1. `commit, pushしていない資源があればcommit, pushして`は`repository-closeout`になる。
2. explicit global wordingがない場合、current task-owned worktree以外へtargetを広げない。
3. explicit global wordingがある場合、worktree inventoryは許可するが、target setは最初のinventory後に固定される。
4. `git status`、candidate diff確認、secret check、stage、commit、push、remote ref確認は許可される。
5. `pytest`、全branch review、別cutover wait、`delegate_task`は拒否される。
6. conflict解消の`patch`または`write_file`は拒否され、conflicted worktreeはblockerになる。
7. commit hook失敗後、hookを直す編集やfull testは開始されない。
8. completion成立後の追加tool callは拒否される。
9. 15分または算出tool budget到達後、追加tool callは拒否される。
10. 並列callはatomic reservationによりbudgetを超えない。
11. validator timeout、invalid JSON、state DB failureはside-effect toolをfail closedする。
12. `execute_code`でcloseout policyを迂回できない。
13. userが`失敗testも修正し、全test後にcommit/push`と明示した別fixtureは`artifact-change`となり、対象修正とverificationを誤って拒否しない。
14. userが`commitだけ`と明示したfixtureではpushを実行しない。

成功基準は、元事例でcommit-ready資源の保存だけが完了し、競合資源が修復されずにblockerとして残り、広範テストとcutover waitが0回であることとする。

## 11. Rollout

### S0: contract and replay harness (implemented)

- ScopeContract JSON Schema、normalizer、incident fixturesを実装する。
- 実repositoryを変更しないfixtureでallow/deny、budget、parallel raceを検証する。

Exit: 元事例の不要actionをすべて拒否し、必要なcloseout actionを拒否しない。

### S1: hard gate for `repository-closeout` (implemented; pilot metrics pending)

- このclassだけhard enforcementを有効化する。
- 他classはcontract/auditのみで、既存作業を突然blockしない。
- 最初の10件をreviewし、false allow/denyとdurationを確認する。

Exit: closeout taskの95%が15分以内、expansion 0、必要actionのfalse deny 0。

### S2: bounded operations

- named config/restart/cutoverへtarget lockとone-use recovery permitを拡張する。
- production safety approvalとscope admissionを別判定として維持する。

### S3: artifact changes

- write scope、targeted verification、expansion reviewを有効化する。
- broad implementationを狭く誤分類しないgold setを通す。

#### S3-M1: 決定論コアの具体設計（2026-08-22 ドラフト、2026-08-23 に D-S3-1・D-S3-2・D-S3-3 の決定を反映）

goal M1 が実装するのは S3 の決定論コアである。worker profile への配線・judge 実接続・実トラフィック由来 gold set・discovery 段の帰属は D-S3-6（オーナー判断）の決定に従う。

基本原理: **書込権限と実行権限を、別の保証水準として契約上分離する（二層契約）。**

- 第一層（write 境界）は決定論的に強制できる硬い境界であり、S3-M1 が主張する「スコープ逸脱の機械的遮断」はこの層についての主張である。
- 第二層（実行を伴う検証）は、契約が明示的に opt-in した場合にのみ、閉じたテンプレート集合として許可する。実行中のプロセス副作用は第一層の保証対象外であることを脅威モデルとして明文化し、残余を M2 の必須要件として固定する。opt-in のない契約では実行を伴うツール呼び出しを一切許可しない（default deny）。

##### 契約の拡張（scope-contract-v1）

- `targets.write_paths`: artifact-change で必須。リポジトリ相対の glob パターン（最大32件、空・上位参照・制御文字を拒否）。ターンの書込許可範囲の閉集合（INV-S2 の write 版）。
- `targets.test_paths`: テスト資産（テストファイル、テスト専用フィクスチャ）の書込許可範囲の閉集合。`write_paths` と対称の構文・件数上限を持つ独立フィールドとする。既定は当該ターンの `write_paths` に対応するテストファイル単位まで絞り、リポジトリのテストディレクトリ全体を無条件には含めない。省略時は空集合（テスト資産の書込を許可しない）。
- `execution`: 第二層の opt-in。許可する検証テンプレートの ID 集合のみを持つ。省略時または空集合のとき、実行を伴うツール呼び出しを全て拒否する。契約側に実行コマンド文字列を自由記述させない（§13 の却下事項「Agent が自由記述した contract を無検証で採用」と整合させる）。テンプレート ID から具体の検査規則への対応は、ゲート実装側の閉じたレジストリに置く。
- glob 構文: `*` はパスセグメント境界を越えず、再帰は `**` として構文上区別する。承認レビュー時に読める文字列と実効許可範囲を一致させるため、標準ライブラリのパターン照合をそのまま用いない。意図した粒度を示す例を1つ本節へ載せる。
- class 別 budget 補正の既存バグを修正する: 実在しないキーへの条件付き制約は常に真であり何も検査していないため、実キー（`max_wall_seconds` / `max_tool_calls`）への制約に置き換える（bounded-operation 側も同様）。
- スキーマ記述規律: 新設フィールドの class 別必須化は、条件節の下に必須キー宣言を伴わせる。プロパティ形状の宣言だけでは欠落を検査できず、上記の既存バグと同種の空振りが再発する。

##### lock（artifact-change）

- `lock_turn` を artifact-change に開放し、closeout と同じ原子的 lock で `write_paths` / `test_paths` / `execution` を含む契約を固定する。lock 到達経路と lock 前の既定は D-S3-4 / D-S3-5 の決定に従い、本節は locked 状態の admission のみを規定する。
- lock 時に、`write_paths` / `test_paths` が指す範囲の祖先ディレクトリに、ロック済み worktree 外を指すシンボリックリンクが存在しないことを検査する。

##### 第一層: write 境界（硬い決定論保証）

- 読み取り系ツール（read/search/list 系）: 許可（audit 記録のみ）。
- **書込先の識別はツールカタログで行う。** 「ツール名 → 書込先を表す全フィールド名」の明示 allowlist を持ち、単一パス、パス配列、変更元と変更先の対を持つツールを区別して、書込先になりうる全フィールドを検査する。未列挙のツールは変異系として G3（default deny for mutation）へ落とす。引数の形状に対する名前ヒューリスティックで判定しない。
- **パス正規化は単一の決定論関数へ集約する。** 検査は「パス要素を完全に解決し、上位参照要素の不在と制御文字の不在を確認する」形で行い、文字列前処理の積み増しで実装しない。「絶対パス即 deny」は引数の表記形式ではなく「ロック済み repository / worktree root のいずれにも属さないパス」を意味するものとする（既存の読み取り系ツールと terminal は絶対パスを要求しており、表記形式での一律 deny は既存規約と矛盾する）。ツールが作業ディレクトリを持たない場合の解決基準も同じ関数に含める。
- **照合順序**: 絶対パスへ解決 → ロック済み root への相対化 → root 外は deny → 相対パスを `write_paths` / `test_paths` の glob へ照合。
- **実体解決を含める。** 書込先の直近の既存祖先ディレクトリを実体解決し、解決後の絶対パスがロック済み worktree root 配下であることを検査する。レキシカルな文字列照合のみで書込を許可しない。
- `git add` とメッセージ指定付きの `git commit` を決定論 allowlist に含める。`push` は含めず、承認後の別 finalization 契約に残す。
  - ステージ範囲は write scope に従属させる。ステージ対象は `write_paths` ∪ `test_paths` へ照合済みのパス指定経由のみとし、対象を列挙しない一括ステージ系の指定は許可しない。closeout は「既存差分を保存する」意味論のため一括指定を許容できるが、artifact-change では許容しない。**「closeout 同水準」は検査の厳密さの下限であり、許可範囲の上限ではない。**
  - 履歴書換および検証フック迂回に相当する指定は deny する。
  - artifact-change 用の terminal admission は closeout 用関数とコードパスを共有しない独立実装とする。git 書込の可否を、分類器が偶然立てないフラグの副作用に依存させない。
  - lock 時に固定したブランチ束縛に対する drift 再検査を、git 書込の admission 前に行う（ブランチ束縛の持ち方は D-S3-5 に従う）。
- 上記以外の変異系: G3 expansion へ（default deny for mutation）。

##### 第二層: 実行を伴う検証（契約単位の opt-in、write 境界の保証対象外）

- `execution` が空の契約では、実行を伴うツール呼び出しを全て deny する。
- opt-in された契約では、レジストリに登録された検証テンプレート（対象ファイルを明示した焦点テストの実行、対象ファイルの構文検査）のみを許可する。
- **引数検査は closeout の既存 allowlist 実装と同水準に揃える。** 規範:
  1. 位置引数に限定せず、全トークンを走査する。
  2. 安全な指定のみを明示 allowlist とし、未知の指定は即 deny する。
  3. 値を取る指定は、値の結合形と分離形を同一の規則で扱う。
  4. 設定の探索経路、収集経路、プラグイン読込経路、出力先および一時領域を差し替える指定は deny する。
  5. 標準入力から対象を受け取る起動形態は deny する（または terminal の標準入力を常に空へ固定する）。いずれを採るかを M1 の受入テストで固定する。
  6. 対象は**ファイル単位**で `write_paths` ∪ `test_paths` へ照合する。ディレクトリ単位の指定、および対象指定を伴わない全体起動は許可しない。
  7. 実運用で常用される安全な指定を allowlist に含め、正当な検証が false deny にならないことを受入テストで固定する。
  - 具体トークン列は本設計へ列挙せず、実装時に closeout 側の allowlist 実装を正本として確定し、受入テストで固定する。
- **脅威モデルの明文化**: 第二層で許可されたコマンドのプロセス副作用（キャッシュおよびコンパイル成果物の生成、収集経路上の資産の読込と実行を含む）は、第一層の write 境界の保証対象外である。ゲートはコマンド引数のみを検査する。これは closeout における commit フック自動実行の許容と同じ扱いの拡張であり、S3-M1 の「スコープ逸脱の機械的遮断」の主張は第一層に限る。
- **M2 の必須要件として固定する残余**（この2点が入るまで第二層は「宣言済み・未強制」である）:
  1. ファイルシステム名前空間をロック済み worktree（および読み取り専用の依存関係）へ制限した隔離実行。
  2. 収集経路上に置かれた `write_paths` / `test_paths` 外の資産に対する静的検査。
- 将来、実行を実装 worker とは別主体（独立検証者ステージ）へ移す場合、その接続点はこの第二層とする（検証者ステージの契約自体は M2）。

##### G3 と予算の較正順序

- ローカルコミットとテスト資産の書込を決定論許可へ取り込み、G3 が真に例外的な拡張のみを扱う状態にしたうえで、実トラフィックの gold set で審査予算を較正する。judge 未接続の間は回数に関わらず全て fail-closed であり、予算値の妥当性は検証不能であることを明記する。
- G3 の第二段（契約が既に許すが normalizer だけが未認識だった既知 action の決定論 allow）は、task class のハードコード分岐をやめ、「その task class の locked admission 関数」を引く dispatch テーブルへ一般化する。

##### S3-M1 契約ライフサイクル（D-S3-4 / D-S3-5 の決定、2026-08-23）

**1. 権限の出所と二つの lock 経路**

artifact-change の書込境界を実行主体の自発的な宣言に依存させない（INV-S8）。契約は次の二経路のいずれかで `locked` に到達する。

- **割当 seed（正規経路）**: オーケストレーターがタスク割当時に、対象 worktree・branch・write scope・許可アクションを含む契約 seed をゲート状態へ記録する。ゲートはターン開始時にこの seed を消費し、最初の tool call より前にターンを `locked` として作る。実行主体側の操作を必要とせず、実行主体は seed を広げられない。
- **自己 lock（seed が無いターン）**: 対話ターンなど seed の無い場合に限り、lock 前段（第2項）を経て実行主体が lock を要求できる。seed があるターンで lock が要求された場合は、seed 契約をそのまま冪等に返す（既存 closeout の再 lock と同じ挙動）。seed を超える宣言は拒否する。自己 lock はクラス上限（単一 worktree、相対指定、件数上限）に対して検査する。

契約には出所（`assignment` / `self`）を記録する。自己 lock 由来の契約は、狭い write scope が独立した権限から与えられていないため、監査上は弱い保証として扱う。自律 worker レーンは常に seed 経路とする。

**2. lock 前の既定（D-S3-4）**

lock されていない artifact-change ターンでは、既知の読み取り系ツール（read/search/list 相当）だけを許可し、監査記録のみを行う。構造化書込・変異系ツール、`terminal` を含む実行系、未知ツールは既定拒否とし、理由コードを「lock 未了」とする。拒否は既存の拒否計上に載せる。

M1 では artifact-change 専用の discovery 予算を新設しない（discovery 段自体は M2 残余のまま）。上限はクラス予算（wall time / tool calls）とする。

**3. lock 到達経路と対象集合の閉鎖（D-S3-5）**

- `lock` 制御アクションを artifact-change に開放する。原子的 lock は closeout と同じ経路を用いるが、admission は task class ごとの dispatch とし、closeout 専用ロジックとコードパスを共有しない。
- M1 の artifact-change は **単一 worktree** のみ lock できる。この単一 root が書込先パス照合の相対化基準となる（照合規則そのものは D-S3-2 の決定に従う）。
- INV-S2（対象集合の閉鎖）は、closeout の候補集合機構を流用せず、**lock 時のリポジトリ実体検証**で満たす。指定対象が Git worktree の root と一致すること、現在ブランチが取得できること（detached HEAD は拒否）を、closeout と同じ検証器で確認する。seed 経路では、seed の branch と実ブランチの不一致を fail-closed とする。
- 対象と write scope の追加は lock 後に行えない。必要な場合は G3 の拡張審査に載せる。

**4. 状態と遷移、および closure の規範**

- 分類直後: 強制対象クラスは lock 前段（既定拒否）、未強制クラスは従来どおり監査のみ。
- seed 消費に成功したターン: 直ちに `locked`。
- 自己 lock 成功: lock 前段から `locked`。
- 完了: 明示的な完了制御アクション、または session 終了。

規範要件:

- **closure は明示のみ**: 強制クラスのターンを中間の監査フックで閉じない。閉じたターンでは変異系を拒否したままにする。
- **バインディング不能時は fail-closed**: 当該タスクに seed が存在する場合、契約へバインドできない tool call の変異系を拒否する。ターン未登録を「未強制」として扱わない。
- **seed 検証失敗も fail-closed**: seed の実体検証に失敗したターンは「変異拒否のまま存在する」状態とし、未強制へ落とさない。

**5. 契約が運ぶ権限（分類器フラグに依存しない）**

git 書込その他の副作用を許すかどうかは **locked 契約のフィールド**で表す。分類器が推定したフラグの既定値に依存させない。許可内容そのものの決定は D-S3-1..3 の決定（第一層・第二層）に従い、本項が定めるのは「その出所が契約であること」だけである。

**6. スキーマと配線**

- artifact-change の lock は、write scope を含むスキーマ妥当な契約を生成する唯一の経路である。契約スキーマ側の必須指定・上限反映と、lock 制御ハンドラで write scope（`write_paths` / `test_paths` / `execution` を含む）をロック関数へ渡す配線は、本改訂と同一の変更で入れる。
- 契約の出所フィールドを追加するため、契約スキーマの追加プロパティ許可範囲も同時に更新する。

**7. 本決定に伴う M1 実装チェックリスト追加分**

- `lock` のクラス分岐を変更する前に、closeout 専用ガードの回帰テストを先行追加する。
- admission を task class の dispatch テーブルへ一般化し、G3 の「既に契約が許可している」判定も同じ dispatch を用いる。
- LLM 呼び出し後の監査フックの発火粒度が「ユーザーターン単位」か「LLM 呼び出し単位」かを、有効化前に synthetic payload で確認する。ターン単位でない場合も第4項の closure 規範で閉じられることを受入テストで示す。この前提は S1（closeout）が既に依存しているものであり、artifact-change 固有の新規リスクではないが、反復回数が多いクラスでは露出が大きい。
- 敵対系受入テスト: lock 未了での変異拒否、seed を超える自己 lock の拒否、lock 後の対象・write scope 追加の拒否、seed 検証失敗時の変異拒否、閉じたターンでの変異拒否、バインディング不能時の変異拒否。

**8. D-S3-6（オーナー判断）の両分岐での適用範囲**

- worker 適用を M1 に保つ場合: seed 記録の呼び出し側（割当経路）も M1 の成果物に含める。
- M2 へ付け替える場合: ゲート側の seed API と lock 前段の既定拒否は M1 で入れるが、自律 worker レーンでの artifact-change 強制は seed が配線されるまで有効化しない。
- いずれの分岐でも「seed 無しで自律レーンを強制する」構成は採らない。

##### M2 への残余（本設計で明示的に先送り）

- judge の実接続、artifact-change 用 discovery 段、実トラフィックからの S3 exit 用 gold set、pre_llm_call のクラス別 policy 注入の拡充、verification 契約（検証者ハンドオフ）との統合、第二層の隔離実行と収集経路の静的検査。
- worker profile への配線と有効化は本節で先送りしない。帰属は D-S3-6（オーナー判断）の決定に従う。

#### S3-M1 未解決の設計判断（2026-08-22 反証レビュー結果、2026-08-23 に D-S3-1・2・3 決定）

上記ドラフトは実装着手前の並列反証レビュー（運用細則2）を通し、確証欠陥 20 件（blocker 6 / major 7 / minor 7）が返った。各欠陥の根拠と対応方針、および欠陥 ID（R-01〜R-20）の採番対応表は `docs/status/restricted-s3-write-scope-review-2026-08-22.md` にある。同ファイルは迂回手法の具体形を含み Fable セッションでは直接読まない扱いのため、対応は Opus のサブエージェントへ委譲する。

- **D-S3-1（検証実行の位置づけ）— 決定済み（2026-08-23）**: 実行を伴う検証は許可するが、契約単位の明示 opt-in を必須とする。実行中のプロセス副作用は write 境界の保証対象外であることを脅威モデルとして明文化し、名前空間の隔離と収集経路の静的検査を M2 の必須要件として固定する。テスト資産の新規作成・編集は、テストディレクトリ全体の無条件免除ではなく `targets.test_paths` の閉集合として許可する。詳細は上記「契約の拡張」「第二層」。
- **D-S3-2（引数検査の水準）— 決定済み（2026-08-23）**: 許可コマンドの引数検査を closeout の既存実装と同水準（全トークン走査、安全な指定の明示 allowlist、未知の指定は即 deny）へ揃える。パス照合の健全性（正規化基準の一元化、glob のセグメント境界扱い、実体解決、書込先フィールドの網羅）を同じ改訂で扱う。詳細は上記「第一層」「第二層」。
- **D-S3-3（ローカルコミットの扱い）— 決定済み（2026-08-23）**: worker のローカルコミットを決定論 allowlist へ含める。ステージ範囲は write scope へ従属させ、一括ステージ系の指定は許可しない。push は承認後の別契約に残す。詳細は上記「第一層」。
- **D-S3-4 / D-S3-5（lock 前の既定・lock 到達性）— 決定済み（2026-08-23）**: 契約ライフサイクルは上記「S3-M1 契約ライフサイクル」で決定した。lock 前の無制限許可を廃し bounded な既定拒否段に置き換え、`locked` への到達は「割当由来の seed 契約（正規経路・自律 worker レーンは必須）」と「seed が無いターンでの自己 lock（縮小のみ）」の二経路とする。
- **D-S3-6（M1/M2 の境界。オーナー判断事項）**: ドラフトは S3 の worker 配線を M2 へ先送りしたが、ADR D2 と goal M1 はこれを M1 の成果物と規定している。M1 として実装するか、ADR 改訂（＝オーナー承認）を経て M2 へ付け替えるかを決める。設計側で一方的に格下げしない。

決定間の整合（D-S3-1..3 が置いた前提の充足状況）:

- 契約の作成主体: 自律 worker レーンは割当 seed（契約が worker の外で作成・注入される）で充足。自己 lock レーン（対話ターン）では `execution` opt-in と `test_paths` の幅が実行主体の宣言に残るため、契約出所フィールドにより監査上の弱い保証として明示する。これは対話ターン限定の宣言済み残余である。
- lock 前の既定と lock 到達経路: 「S3-M1 契約ライフサイクル」で決定済み。第一層の硬い保証は locked 状態で発効し、lock 前は bounded な既定拒否段が覆う。
- ブランチ束縛と drift 再検査: lock 時のリポジトリ実体検証（branch 取得・detached HEAD 拒否・seed branch 不一致 fail-closed）が束縛を供給し、git 書込前の drift 再検査はこれを参照する。
- lock 時のシンボリックリンク不在検査: lock 機構側の検査として「lock（artifact-change）」節に含めた。
- M1 exit gate の主張範囲（第一層に限る旨）は D-S3-6 のオーナー判断に含める。

実装チェックリストへ回す項目: 期待審査経路（G3）の実効性の再確認、契約スキーマの必須指定漏れと上限反映、runtime ハンドラでの write scope 配線漏れ（新設 `test_paths` / `execution` を含む）、judge 接続時の自己申告フィールドに対する M2 受入テストの先行定義。

## 12. Metrics and review triggers

記録する主指標:

- task class別wall timeとtool call数。
- `scope_expansion_denied_total`とreason。
- scope reviewのallow/deny、owner escalation数。
- false deny、false allow、parent rework。
- completion後tool attempt数。

次の場合はpolicyを止めて見直す。

- 必要actionのfalse denyが1件でも起き、safe retry pathがない。
- unknown toolがmutationを通過する。
- gate障害がsilent fail-openになる。
- narrow taskのdurationまたはowner interruptionが導入前より増える。
- model reviewerがoptional hardeningを繰り返し承認する。

## 13. Rejected alternatives

- Prompt instruction only: 今回事例はagent自身のscope判断が原因なので、自己抑制だけでは独立gateにならない。
- `agent.max_turns`を下げる: 全taskを一律に短くし、長時間の正当な実装を未完了にする。scopeとiteration budgetは別問題である。
- 毎tool callを別LLMで審査: latency、利用枠、failure surfaceを増やす。通常actionはdeterministic allowlist、未知expansionだけsecond opinionにする。
- 全taskでfull testsを必須化: closeoutやdocumentationだけの依頼を再び肥大化させる。
- Post-hoc telemetry only: 原因分析には使えるが、実行済みのscope expansionを防げない。
- Agentが自由記述したcontractを無検証で採用: executorが自分で広いscopeを書けばgateを無効化できる。

## 14. References

- PDA authority: `pda_charter.md`
- Owner communication: `profiles/pda/skills/pda-user-escalation/SKILL.md`
- Delegation and durability: `docs/design/operational-delegation-routing.md`
- Hermes Event Hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks/
- Hermes Plugins: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/
- Hermes Agent Loop: https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop/
- Hermes Context Files: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files/
- Installed hook path checked: `/home/user/.hermes/hermes-agent/agent/agent_runtime_helpers.py::invoke_tool`
