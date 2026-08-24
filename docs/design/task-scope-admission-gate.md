# PDAタスク・スコープ審査ゲート設計

Status: Implemented through rollout S1; S3-M1 design decided 2026-08-23 (D-S3-1..8 decided, including D-S3-7 の補則 and its 定式化統一; ratification at the M1 exit gate); worker wiring implemented and shipped inert (`scope_seed.enabled` 既定 false); production activation pending
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

### artifact-change の受入項目（D-S3-7 の決定、2026-08-23 新設）

項目 1〜14 は closeout 事例を前提とした一覧であり、改訂しない。項目 13 の既存 fixture は artifact-change への分類と「未強制であること」を固定するものであり、強制状態を通らない。強制状態（locked 契約）での replay は次を別立てで検証する。

15. 自律 worker の通常フロー（作業段階の記録 → 差分確認 → base commit id 取得 → 対象編集 → 焦点検証 → 変更ファイル一覧取得 → ステージ → ステージ内容確認 → ローカルコミット → head commit id とブランチ同一性の取得 → 作業記録の更新 → レビュー要求）が、強制状態で拒否 0 件のまま完走し、拒否上限を消費しない。**承認 metadata の収集手順を列に含める。** 受入項目を実装の許可範囲へ合わせて書くと、許可集合と運用手順の不整合が受入テストを通過してしまう。
16. 拒否される読み取りが混じっても、後続のステージ・コミットが座礁しない。拒否上限の消費は 0 である。対象は次の両方を含む。
    - 第一層の読み取り部分集合の外にある読み取り専用 subcommand。
    - **admit 済み subcommand が allowlist に載っていない引数形を伴う場合**（承認 metadata が要求する worktree / git-dir 同一性の取得形を含む）。運用手順が実際に到達する形はこちらであり、前者のみを固定した受入項目では座礁が残る。
    - **必須手順が到達する拒否の件数が拒否上限（6）を超える場合でも、その後の admit 範囲内の読み取り・write scope 内の書込・ステージ・コミットが成立する。**
17. 元事例の expansion（全体テスト起動、別 worktree への書込、subagent 起動、push、write scope 外への書込）は強制状態でも拒否される。**`push` は S3 第一層の対象外であり、承認後の別 finalization 契約に残す**。
18. （**改訂: 2026-08-23、D-S3-7 補則による**）拒否上限の計上規則そのものを固定する。固定対象は次の 4 点である。
    - 計上対象の理由コード集合が、批准された明示列挙と一致すること。集合は有限なので**全数**で固定する（各メンバーが計上側へ写ること、および集合そのものの同値性）。
    - 計上されない拒否（既定側）が計上ゼロであり、かつ座礁ゼロであること。ヒューリスティック分類段の拒否がどの分類ラベルを付けられた場合でも、その後の admit 範囲内の読み取り・write scope 内の書込・ステージが成立する。**レーン未確定の拒否についても同様に固定する。とくに実行テンプレートに一致しない terminal 呼び出し（opt-in の無い契約と、opt-in 済みで不一致の契約の双方）を上限超まで反復した後に、無条件に許可される読み取りツール・許可読み取り subcommand・write scope 内の書込・ステージがいずれも成立すること**（この形の座礁が V3-02 で実測されたため、固定対象へ加える）。
    - 非計上の拒否経路がクラス予算で有界であること（end-to-end）。予算枯渇まで反復し、tool 予算で閉鎖されること、閉鎖が拒否であって fail-open でないことを固定する。
    - 計上判定が並行分類表を参照しないこと。**静的に**固定する（計上関数が分類表・分類関数を消費しないこと、および計上集合が分類器の値域と交わらないこと）。

    改訂の理由は次の 3 点である。
    1. 旧項目18は D7 ラウンドで課した要件であり、invocation から理由コードへの分類が両方向で正しいことを固定するよう求めていた。この要件は 3 度の独立検証で「開放的な引数空間の双方向分類は列挙では充足不能」と実証された。宣言表の全域性を不変条件へ格上げしても、「宣言が対象コマンドの受け付ける全綴りに効くか」は閉じない。
    2. 安全目的（境界の反復探索の遮断）は tool 予算が引き続き満たす。非計上の拒否も tool 予算を消費し、枯渇時は拒否で閉じる。
    3. 境界（admission）は無変更である。旧項目18が対象としていた逸脱形は、いずれも admission では拒否のまま維持される。改訂が変えるのは計上先の帰属のみである。

    分類ラベルの正しさは受入項目から外れ、audit 品質の回帰テストとして残す。ラベルの誤りは監査記録の精度を損なうが、admission の判定も予算の帰属も変えない。

いずれの項目も、拒否上限の計上規則（後述「第一層」）を同時に固定する。

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

#### S3-M1: 決定論コアの具体設計（2026-08-22 ドラフト、2026-08-23 に D-S3-1〜D-S3-5・D-S3-7・D-S3-8 の決定を反映）

goal M1 が実装するのは S3 の決定論コアと worker 配線である（D-S3-6 は 2026-08-23 に「worker 配線は M1 の成果物」として決定）。judge 実接続・実トラフィック由来 gold set・discovery 段の帰属は M2 に残る。

基本原理: **書込権限と実行権限を、別の保証水準として契約上分離する（二層契約）。**

- 第一層（write 境界）は決定論的に強制できる硬い境界であり、S3-M1 が主張する「スコープ逸脱の機械的遮断」は**この層、すなわち書込・ステージ・ローカルコミットという状態変更の側についての主張である。読み取り面はこの主張の範囲に含まれない**（Judgment B、2026-08-23。読み取り境界の帰属は第二層の M2 必須要件 1 に併合した）。M1 exit gate が批准する主張範囲も同じ限定を負う。
- 第二層（実行を伴う検証）は、契約が明示的に opt-in した場合にのみ、閉じたテンプレート集合として許可する。実行中のプロセス副作用は第一層の保証対象外であることを脅威モデルとして明文化し、残余を M2 の必須要件として固定する。opt-in のない契約では実行を伴うツール呼び出しを一切許可しない（default deny）。

##### 契約の拡張（scope-contract-v1）

- `targets.write_paths`: artifact-change で必須。リポジトリ相対の glob パターン（最大32件、空・上位参照・制御文字を拒否）。ターンの書込許可範囲の閉集合（INV-S2 の write 版）。
- `targets.test_paths`: テスト資産（テストファイル、テスト専用フィクスチャ）の書込許可範囲の閉集合。`write_paths` と対称の構文・件数上限を持つ独立フィールドとする。既定は当該ターンの `write_paths` に対応するテストファイル単位まで絞り、リポジトリのテストディレクトリ全体を無条件には含めない。省略時は空集合（テスト資産の書込を許可しない）。
- `actions.git_write`: 第一層の git 書込権限を運ぶ契約フィールド（`stage` / `commit` の部分集合）。artifact-change で必須。省略された契約は git 書込を許可しない（欠落を「無制限」と読まない）。既定は D-S3-3 に従い `["stage","commit"]` で、割当 seed 側から縮小できる。第5項「権限の出所が契約であること」を第一層でも満たすための欄であり、許可範囲そのものを変更しない。
- `execution`: 第二層の opt-in。許可する検証テンプレートの ID 集合のみを持つ。省略時または空集合のとき、実行を伴うツール呼び出しを全て拒否する。契約側に実行コマンド文字列を自由記述させない（§13 の却下事項「Agent が自由記述した contract を無検証で採用」と整合させる）。テンプレート ID から具体の検査規則への対応は、ゲート実装側の閉じたレジストリに置く。
- glob 構文: `*` はパスセグメント境界を越えず、再帰は `**` として構文上区別する。承認レビュー時に読める文字列と実効許可範囲を一致させるため、標準ライブラリのパターン照合をそのまま用いない。意図した粒度を示す例を1つ本節へ載せる。
- class 別 budget 補正の既存バグを修正する: 実在しないキーへの条件付き制約は常に真であり何も検査していないため、実キー（`max_wall_seconds` / `max_tool_calls`）への制約に置き換える（bounded-operation 側も同様）。
- スキーマ記述規律: 新設フィールドの class 別必須化は、条件節の下に必須キー宣言を伴わせる。プロパティ形状の宣言だけでは欠落を検査できず、上記の既存バグと同種の空振りが再発する。

##### lock（artifact-change）

- `lock_turn` を artifact-change に開放し、closeout と同じ原子的 lock で `write_paths` / `test_paths` / `execution` を含む契約を固定する。lock 到達経路と lock 前の既定は D-S3-4 / D-S3-5 の決定に従い、本節は locked 状態の admission のみを規定する。
- lock 時に、`write_paths` / `test_paths` が指す範囲の祖先ディレクトリに、ロック済み worktree 外を指すシンボリックリンクが存在しないことを検査する。

##### 第一層: write 境界（硬い決定論保証）

- 読み取り系ツール（read/search/list 系）: 許可（audit 記録のみ）。許可集合は実行中のツール語彙から導出し、実在しない名前を並べない（自動テストで語彙との一致を固定する）。
- **作業記録系ツール: 許可（audit 記録のみ）**（D-S3-7 の決定、2026-08-23。カタログの二分は司令塔決定で批准対象）。エージェントの作業管理平面（タスクボード、作業段階リスト）にのみ作用するツール群を、名前付きカテゴリとして第一層で許可する。
  - **閉じた明示カタログ（ツール名の列挙）で定義する。** capability 推論やツール引数の形状ヒューリスティックで判定しない。推論規則は既に一度取り除いた欠陥の形であり、語彙が増えるたびに同型の欠陥が再生する。カタログに無い名前は default deny for mutation のままとする。
  - **カタログは段階別に二分する。** 引数を検査せずに許可するため、許可範囲は「引数によらず安全である」と言える形に限る必要がある。
    - **注記系（全段で許可）**: ボードの参照と注記、心拍、作業段階リスト、blocked 記録。これらは run の終端状態を動かさない。lock 前段（第2項）および契約検証失敗段でも許可する。作業が座礁したターンに対して INV-S6 が求める行動（blocked として記録する）はここに含まれるため、閉じると規範自体が実行不能になる。
    - **run 終端シグナル系（locked 段のみ）**: 完了記録とレビュー要求。カードの run 終端はオーケストレーターが次の割当てを判断する購読対象であり（`docs/design/improvement-orchestrator.md`）、審査ゲート自身の入力面でもある。契約が検証できていないターンは「完了した」「レビューしてほしい」の対象を確立していないため、当該段では許可しない。
  - 明示的な除外（いずれもカタログ外＝default deny for mutation）:
    - 別エージェントを起動するもの（クラス予算 `subagents` は 0、§10 項目 5 でも拒否）。
    - 外部の新規情報を取得するもの（依頼外の調査であり expansion）。
    - スキル定義など**リポジトリのファイルを書き得るもの**、ターンの契約外に永続状態を書くもの。
    - **カード新規作成**。blocker が新しいタスクになる経路そのものであり、INV-S6 が黙って行うことを禁じている行為である。
    - **レビュー差戻しの記録**。レビュアー側の判定であり、実装主体の行為ではない（INV-S7 の権限分離）。
    - **カードへのリンク・添付（パス添付・URL 添付を含む）**。いずれも第一層が境界付けていない宛先（パス、URL、他カード）を引数に運ぶ。運用手順もこれらを用いない。除外することで、当該カテゴリに引数検査を新設する必要が無くなる。
  - ターン束縛を失った呼び出し（`admit_without_turn` 経路）では、注記系も許可しない。当該カテゴリを未 lock 段で許可する根拠は「座礁したターンが自らの状態を記録できること」であり、束縛の無い呼び出しには記録対象のターンが存在しないため、根拠がこの経路へ届かない。
- **読み取り専用 git: 許可**（D-S3-7 の決定、2026-08-23）。`status` / `diff` / `rev-parse` / `branch` を第一層に含める。ステージ対象を列挙するための差分確認手段と、承認 metadata が要求する commit id・ブランチの取得手段が契約内に存在しない状態を解消する。
  - 引数検査は closeout の既存 allowlist 実装をそのまま経由する（**新しいパーサーを作らない**）。当該実装を artifact-change のために拡張することもしない。拡張は共有関数を通じて closeout の受入集合も広げるためである。
  - closeout の読み取り集合より狭い点が2つある。いずれも意図した縮小である: (a) ネットワーク越しの読み取り（remote ref 照会系）は push に奉仕するものであり、push を持たない本クラスでは対象外とする。(b) `log` は closeout 側に境界付き引数検査の実装が無く、追加すれば上記の「新しいパーサー」に当たるため除外する。commit id は `rev-parse HEAD` が供給する。
  - 読み取りは git 書込権限（`actions.git_write`）の検査より**前**に判定する。書込権限を一切持たない契約でも、作業対象の状態は見られる必要がある。ブランチ束縛の drift 再検査は読み取りには適用しない（読み取りは任意のブランチで安全である）。**読み取り admission へブランチ束縛を渡さない。** 束縛を参照する subcommand は本クラスが admit しないネットワーク読み取りのみであり、渡す形は「束縛が読み取りにも効いている」という逆の読みを誘発する。admit 集合のいずれの subcommand も判定が束縛に依存しないことを自動テストで固定する。
  - 読み取りをロック済み worktree 内に留めているのは、seed 検証がロック済み root を worktree の top-level に固定していること、およびその root から起動する git 自身のリポジトリ探索である。workdir 束縛は作業ディレクトリを root に固定するだけで、それ単独では引数を境界付けない。
  - `status` の引数境界は git 自身の pathspec 解決に依存する（ゲート側では検査しない）。共有実装をそのまま経由するという上記の方針の帰結であり、closeout 側と同じ挙動である。`status` に独自の引数 allowlist を新設すれば共有実装の変更となり closeout の受入集合にも影響するため、行わない。
  - 本クラスの読み取り系ツール（`read_file` / `search_files` 等）はパス境界の検査を受けない（基準点から不変の既存残余）。したがって「読み取りがロック済み root 内に留まる」はクラス全体の性質ではなく、読み取り専用 git についての性質である。
  - **この残余は write 境界の残余ではなく confidentiality の残余である**（Judgment B、2026-08-23。以後は両者を分離して記載する）。露出の性質が違う: write 境界側の残余（index の内容、第二層のプロセス副作用）はローカル履歴とロック済み worktree 内に留まるが、読み取り面の残余はロック済み worktree **外**の内容が読める。露出範囲は「ロック済み worktree 外の資産、他タスクの作業領域、セッション記録面」である。
  - **M1 exit 時点でこの露出は運用上発生しない。** 自律レーンの有効化は seed 配線と同時であり（D-S3-8）、seed 配線自体が既定 off（「S3-M1 worker 配線」節）であるため、強制対象のターンが live で発生しない。閉じる手段は第二層の M2 必須要件 1（隔離実行）であり、引数水準の境界を M1 で新設しない理由も同節に記す。
- **書込先の識別はツールカタログで行う。** 「ツール名 → 書込先を表す全フィールド名」の明示 allowlist を持ち、単一パス、パス配列、変更元と変更先の対を持つツールを区別して、書込先になりうる全フィールドを検査する。未列挙のツールは変異系として G3（default deny for mutation）へ落とす。引数の形状に対する名前ヒューリスティックで判定しない。
- **パス正規化は単一の決定論関数へ集約する。** 検査は「パス要素を完全に解決し、上位参照要素の不在と制御文字の不在を確認する」形で行い、文字列前処理の積み増しで実装しない。「絶対パス即 deny」は引数の表記形式ではなく「ロック済み repository / worktree root のいずれにも属さないパス」を意味するものとする（既存の読み取り系ツールと terminal は絶対パスを要求しており、表記形式での一律 deny は既存規約と矛盾する）。ツールが作業ディレクトリを持たない場合の解決基準も同じ関数に含める。
- **照合順序**: 絶対パスへ解決 → ロック済み root への相対化 → root 外は deny → **Git メタデータと同一実体を指すパスは宣言によらず deny** → 相対パスを `write_paths` / `test_paths` の glob へ照合。
- **Git メタデータは宣言の対象外とする**（S3-M1 反証レビュー W-B-01 / W-B-02 の処置、2026-08-23。WV-01 の処置で照合を実体同一性へ拡張。M1 exit gate で批准対象）。ロック済み root への相対パスが Git メタデータを名指す書込先・ステージ対象は、`write_paths` の幅にかかわらず拒否する。根拠は循環の遮断である: 本クラスの保証（workdir 束縛、ブランチ drift 再検査、読み取りがロック済み worktree 内に留まること、承認ゲートが導出する canonical Git 同一性）はいずれも「ロック済み root から起動する git 自身のリポジトリ探索」を経由して述べられており、その探索の入力が書込可能であれば、ターンは自らの強制前提を書き換えられる。上限の幅がこれを決めてはならない。
  - carve-out はクラス局所に置く。共有のパス正規化・pathspec 実装を artifact-change のために拡張しない（D-S3-7 決定 1）。
  - **照合は綴りの一致ではなく実体の同一性で行う**（WV-01 の処置、2026-08-23）。判定は 2 段で、(a) 相対パスが `.git` セグメントを含むこと（ツリーに依存せず成立し、未作成の書込先と入れ子リポジトリのメタデータを覆う）、(b) 解決後パスの各前置部が、その親ディレクトリの `.git` と**同一のファイルシステム実体**であること（`os.path.samefile`）である。(b) が必要な理由は、名前の綴りは実体の同一性ではないことである: ファイルシステムが名前の case を畳む環境では別綴りが同じ格納先を開き、`realpath` は case を正規化しないため綴り照合では通過する。linked worktree の `.git` は pointer file であり、その hard link も同一実体で別名になる。この不一致は「一方の綴りの書込先を拒否し、同一の書込先を指す他方の綴りを許可する」形であり、carve-out が述べる性質そのものが綴りに依存していた。判定はクラス局所（本クラスの admission 関数内）に留め、`root` は必須引数とする（省略時に綴り照合へ静かに退行する形を作らない）。他の検査（解決先の封じ込め、root 帰属判定）が既に実体解決で述べられているため、本判定はその一貫性の回復でもある。
  - 本番の gateway は case-sensitive な ext4 であり、case 変種の綴りは当該環境では別実体である。したがって本項の (b) は当該環境における live な迂回の遮断ではなく、**検査の述べる性質を環境依存でなくすための一貫化**である。開発 PC（case を畳む FS）は同じゲートと同じスイートを走らせる環境であり、実行環境を Linux に限定する検査は無い。回帰テストは FS の実挙動を検出して両方向を固定し（畳む環境では拒否、畳まない環境では別ディレクトリとして許可＝false deny 側）、さらに FS 非依存の経路（pointer file の hard link）で (b) の分岐自体を固定する。
  - **書込形とは独立に、git 書込 admission 直前でリポジトリ解決先の封じ込めを検査する。** ロック済み root から解決した git-dir / git-common-dir が root 配下に入る構成（root 直下の `.git` 自身を除く）では `add` / `commit` を拒否する。linked worktree は両者が primary repository 側（全 worker の上限外）へ解決し、通常のリポジトリは自身の `.git` へ解決するため、本クラスが正当に走る形に false deny を追加しない。書込形の carve-out だけでは「別経路で解決先が変わった場合」を覆えないため、両者を独立の検査として持つ。
  - 承認ゲート側も同じ封じ込めを課す。Judgment A がゲート側導出へ移した canonical Git 同一性 2 項について、解決先が workspace 配下に入る workspace は承認不可とし、同一性を導出しない（fail closed）。導出主体を移すだけでは、導出の入力が worker の上限内にある限り信頼の根は移らない。**消費（finalization）側の再導出にも同じ封じ込めを置く。** 台帳行との比較は承認後に生じた向け替えを捕らえるが、承認時点で既に存在した向け替えは捕らえないため、性質を各実装で局所に述べる（独立実装を突き合わせで固定する既存の規律に合わせる）。
- **実体解決を含める。** 書込先の直近の既存祖先ディレクトリを実体解決し、解決後の絶対パスがロック済み worktree root 配下であることを検査する。レキシカルな文字列照合のみで書込を許可しない。
- `git add` とメッセージ指定付きの `git commit` を決定論 allowlist に含める。`push` は含めず、承認後の別 finalization 契約に残す。
  - ステージ範囲は write scope に従属させる。ステージ対象は `write_paths` ∪ `test_paths` へ照合済みのパス指定経由のみとし、対象を列挙しない一括ステージ系の指定は許可しない。closeout は「既存差分を保存する」意味論のため一括指定を許容できるが、artifact-change では許容しない。**「closeout 同水準」は検査の厳密さの下限であり、許可範囲の上限ではない。**
  - 履歴書換および検証フック迂回に相当する指定は deny する。
  - artifact-change 用の terminal admission は、**判定関数（どの subcommand をどの状態で許すか、および状態意味論と許可範囲）** を closeout と共有しない独立実装とする。git 書込の可否を、分類器が偶然立てないフラグの副作用に依存させない。一方、コマンド字句解析と引数 allowlist（トークナイザ、境界付き pathspec 検査、検証用引数 allowlist）は closeout の実装を共有する（D-S3-7）。同一のコマンド表面に対して二つのパーサーを持てば、厳密さが片側だけ劣化しても検出できない。
  - lock 時に固定したブランチ束縛に対する drift 再検査を、git 書込の admission 前に行う（ブランチ束縛の持ち方は D-S3-5 に従う）。
- 上記以外の変異系: G3 expansion へ（default deny for mutation）。
- **拒否上限（`max_denied_calls`）の計上は、write 境界・実行境界への逸脱試行に限定する**（D-S3-7 の決定、2026-08-23）。上限の目的は境界の反復的な探索を止めることであり、必要手順の一部である読み取り拒否や作業記録の拒否を計上すると、規定のフローに従うターンが自らの拒否で座礁する。上限値（6）は維持する。
  - **計上対象の判定規則は次の一文（litmus）のみである**（D-S3-7 補則の決定、2026-08-23。単一定式化への統一は 2026-08-23 の司令塔決定）。

    > **読み取りを目的とする呼び出しが到達しうる理由コードは、計上対象に入れない。**

    ここで「読み取りを目的とする呼び出し」とは、本クラスが読み取り経路として許可しているもの（読み取り系ツール、許可した読み取り専用 git subcommand）に加え、**admission がまだレーンを確定できていない terminal コマンド**を含む。裏返せば、計上できるのは「その理由コードを受け取りうる invocation が、admission が自ら決める事実だけで write / 実行境界への行為と確定しているもの」に限る。
  - **レーン別の確定事実は litmus の適用結果であり、litmus と並ぶ第二の規則ではない。** 判定に迷いが生じたときに参照するのは常に litmus の側であり、下記の列挙が litmus と食い違った場合は列挙が誤りである（二つの定式化を対等に置くと、両者が乖離したまま実装がどちらかを選ぶ状態が再発する。V3-02 がその実例）。確定事実は次の 5 つである。
    1. ツール名が write カタログに属すること。
    2. git subcommand が `add` / `commit` であること。
    3. **コマンドが opt-in 済み実行テンプレートの起動形に一致すること**（後述の実行レーン）。
    4. 契約の権限欄が当該操作を許可していないこと。
    5. 解決後のパスが write scope 照合に失敗すること。
  - **実行レーンの確定点はテンプレート起動形への一致である。** 一致した時点で、その invocation は呼び出しの目的を問わず実行境界への行為として確定する（契約自身の opt-in がそのプログラムを名指しているため）。したがって一致後の引数形の拒否（未知・危険な指定、標準入力形、対象ファイルの scope 外・ディレクトリ・glob）は計上する。一方**どのテンプレート起動形にも一致しない拒否（opt-in の無い契約での実行系呼び出し、および opt-in 済み契約でテンプレートに一致しないコマンド）はレーンを確定しないため計上しない**。ファイル内容を読む目的の terminal 呼び出しが同じ理由コードへ到達する（V3-02 で実測）。
  - **認識できなかったことを理由とする拒否は計上しない。** 認識外の git subcommand、認識外のツール（G3 へ落ちる形）は、いずれも純粋な読み取りが到達しうるためレーンが未確定である。admission は拒否のまま維持され、変わるのは計上先のみである。
  - **コマンドの字句解析より前に決まる拒否は計上しない。** terminal の workdir 検査（絶対パス要求・上位参照・ロック済み worktree 外）はこの類型であり、許可した読み取り subcommand も到達する。字句解析の後に workdir を再判定してレーン確定後の計上へ回す形は M2 の検討残余とする（M1 では admission 無変更の制約から判定順序を動かさない）。
  - 計上対象の理由コードは有限の明示集合として実装側に持つ。集合に無い拒否理由は計上しない（既定は非計上）。新しい拒否理由が計上対象になるのは、集合へ明示的に追加したときだけである。**集合の縮小（計上 → 非計上）は litmus の適用誤りの修正であり、拡大（非計上 → 計上）は litmus に照らした新たな確定事実の主張である。両者を同一の変更で混ぜない。**
  - **terminal 引数のヒューリスティック分類（どの綴りがパスを開くか、どの綴りが書込形か）に由来する拒否は計上しない。** 分類は audit の帰属表示にのみ用いる。計上判定はこの分類表を参照しない（実装側で静的に固定する）。理由は §10 受入項目18（改訂）に記載する。
  - 計上しない拒否は、代わりに tool 予算を消費する。拒否が無償になる経路を作らないためであり、これにより計上されない拒否経路もクラス予算（wall time / tool calls）で有界であり、枯渇時は拒否で閉じる（fail-open しない）。
  - 予算枯渇そのものによる拒否（wall / tool / deny）は上限そのものであって試行ではないため、いずれの計数も消費しない。
  - **litmus の明示例外（唯一）**: 冪等性ガード（同一の tool-call id が異なる引数で再到達した場合）の拒否は、理由コードの写像を経由せず直接上限へ計上する。admission 判定より前に位置し、クラス非依存であり、ゲート自身が記録した fingerprint の比較という確定判定である。読み取り目的の呼び出し id を引数を変えて再送する形も到達しうるため litmus には厳密には適合しないが、フック protocol の整合性ガードであり、非計上にすると改竄側の反復が上限で有界でなくなる。**この一件が litmus の例外であることを明示し、他の理由コードへ例外を拡張しない**（例外を暗黙に増やせば litmus は再び二つの規則に分裂する）。
  - lock 宣言が seed を超える場合と scope パターンがロック済み root 外へ解決する場合の拒否は、lock API が例外として送出する。per-call の admission 経路を通らないため、計上規則の対象ではない。
  - 理由コードは判定を一意に表す必要がある。同一の綴りを二つの異なる判定が発行する状態では、コードから計数先への写像が健全にならない。terminal の workdir 検査（絶対パス要求・上位参照・ロック済み worktree 外）は、コマンドの字句解析より前に行われるため純粋な読み取りも到達する。よってこれらは write 対象のパス検査と同じ綴りを共有せず、独自の理由コードを持つ。
  - G3 の第二段（契約が既に許している既知 action の決定論 allow）は permit 行を作らず審査予算を消費しない（既存規則）。
  - **逸脱かどうかは invocation 全体（subcommand + 引数）の性質であり、subcommand の性質ではない。** subcommand 単位で読み取り側へ寄せると両方向に誤分類が生じる（状態変更形が読み取り側へ落ち、境界内の純粋な読み取りが境界側へ落ちる）。この分類は**許可された読み取り subcommand と、認識のみで許可しない読み取り subcommand の双方**に適用する。後者を subcommand 名だけで免除すると、同じ粒度の誤りが引数水準で再発する（下記の diff 系オプションを参照）。拒否は**三分類**する。

    **この三分類が決めるのは、audit の帰属ラベルと、読み取り形が許可された subcommand における引数形の admission である。予算の帰属は決めない**（D-S3-7 補則。本段の拒否はいずれも非計上であり、tool 予算で有界である）。計上先は上記 litmus のみが決める。以下の分類名は境界側ラベルと読み取り側ラベルの区別であり、予算の区別ではない。
    1. **ロック済み root の外を指す引数** → 境界側ラベル（境界への逸脱試行として監査記録する）。`..` の判定はパス要素単位で行う。リビジョン範囲は `..` を演算子として運ぶため、文字列包含での判定は純粋な読み取りを逸脱と誤判定する。**パスはトークン全体であるとは限らない**ため、結合値（`--opt=<path>`）と単一ダッシュのフラグに詰めた形（`-X<path>`）の値部分も同じ判定にかける。値取り形は値のない短縮フラグを束ねた末尾にも置けるため、値の開始位置を 3 文字目に固定しない。
        - **ただしトークン内部の値をパス候補とするのは、パスを取ると宣言したオプションに限る**（subcommand 単位の明示列挙。同じ綴りが member によって意味を変えるため、綴り単位の単一表では必ずどちらかの方向を誤る）。値の意味を見ずに形だけで候補化すると、検索パターン・書式文字列・表示接頭辞・行範囲の正規表現など**値がパスに見えるだけの純粋な読み取り**が境界側ラベルへ落ちる（この誤りが計上先を動かしていた旧規則では、上限回数に達したターンが自らの拒否で座礁した。補則の後は監査記録の精度の問題に留まる）。
    2. **読み取り形が許可された subcommand の書込形** → 境界側ラベル。判定は閉じた明示列挙で行う: (a) 書込形を持つ subcommand には書込指定の明示マーカー集合を与える（結合形 `--opt=value` と分離形の双方を同一規則で扱う）、(b) 読み取りと書込を同一 subcommand 名で兼ねるもの（ブランチ操作系）には**読み取り形の allowlist** を与え、それ以外を境界側とする。**この (b) の allowlist は admission に対して load-bearing である**（allowlist 外の形を読み取りとして admit しない）。
    3. **ロック済み root 内の純粋な読み取りで、引数形が allowlist に載っていないもの** → 読み取り側ラベル。承認 metadata が要求する同一性読み取りはこの類型に属する。なお本類型を計上側へ置いた旧規則は、規定フローに従うターンを上限回数の拒否だけで座礁させた（補則による非計上化の経緯）。
  - **読み取りとして許可する subcommand 集合には、それ自身の目的が状態変更を含む subcommand を入れない。** 読み取り形と状態変更形を同一 subcommand 名で兼ねるもの（リモート設定系、reflog 系）は認識外扱いとする。これらを読み取りとして admit するには状態変更形の全綴りを列挙して除外する必要があり、3 巡の独立検証が閉じないと実証した列挙形そのものになる。admission の側で認識外に留めることが健全である。
  - **集合への所属それ自体が読み取りの証明ではない。** 認識集合の member のうち diff 系オプションを受け取るもの（履歴表示系・単一コミット表示系・行帰属系・集計系）は、出力先指定で実際にファイルを作成でき、外部プログラム駆動の指定も受け取る。**書込境界だけが引数で名指される境界ではない**: ネットワーク読み取り系は遠隔側で起動するプログラムを引数で名指せるため、その拒否は実行境界への試行である。したがって読み取り側ラベルに到達するのは「書込・実行形のマーカーを含まず、ロック済み root の外を指す引数も含まない」invocation に限る。
    - **宣言義務は認識集合の全 member に課す**（許可された読み取り subcommand と認識のみの member の双方）。マーカー表とパスオプション表はいずれも認識集合上の**全域写像**とし、空の宣言を「監査済みで宣言すべきものが無い」の明示とする。宣言の**欠落**を許すと、義務が「既に監査した族の列挙」に縮み、誰も見ていない族は原理的にテストで落ちない（実行境界を名指す指定が読み取り側に残ったのはこの形である）。全域性と非空虚性を自動テストで固定し、認識集合へ member を加えた際に宣言なしでは落ちるようにする。
  - 三分類は audit の帰属と（許可された読み取り subcommand については）引数形の admission を決める。**予算の帰属は決めない。** いずれの分類も何かを許可することはなく、既に拒否された呼び出しの記録のされ方を決めるだけである。
  - 計上規則は artifact-change に限定し、S1 で有効化済みの closeout の計上は変更しない。

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
  1. ファイルシステム名前空間をロック済み worktree（および読み取り専用の依存関係）へ制限した隔離実行。**この要件は第二層の実行副作用のためだけでなく、本クラスの読み取り面の境界も供給する**（Judgment B、2026-08-23）。隔離実行は OS 水準で全段・全ツールの読み取りを束縛するため、引数検査を必要としない。引数水準の読み取り境界を M1 で新設しない理由は次の 4 点である。(a) D-S3-7 で確定した第一層の許可集合に読み取り系ツールの引数検査は含まれず、exit gate 直前の許可範囲の縮小は批准対象を動かす。(b) 本クラスは false deny ゼロを要求するが、worker が実際に読むパスの全体について実機証拠が無い。(c) unbound 段と lock 前段には照合基準となるロック済み root が存在しないため M1 で入れられる境界は locked 段限定であり、加えて `session_search` はファイルパス引数を持たないため carve-out が必要になりその carve-out がそのまま穴になる。(d) 上位機構が M2 で入る時点で引数水準の境界は二重になる。
  2. 収集経路上に置かれた `write_paths` / `test_paths` 外の資産に対する静的検査。
- 将来、実行を実装 worker とは別主体（独立検証者ステージ）へ移す場合、その接続点はこの第二層とする（検証者ステージの契約自体は M2）。

##### G3 と予算の較正順序

- ローカルコミットとテスト資産の書込を決定論許可へ取り込み、G3 が真に例外的な拡張のみを扱う状態にしたうえで、実トラフィックの gold set で審査予算を較正する。judge 未接続の間は回数に関わらず全て fail-closed であり、予算値の妥当性は検証不能であることを明記する。
- G3 の第二段（契約が既に許すが normalizer だけが未認識だった既知 action の決定論 allow）は、task class のハードコード分岐をやめ、「その task class の locked admission 関数」を引く dispatch テーブルへ一般化する。

##### S3-M1 契約ライフサイクル（D-S3-4 / D-S3-5 の決定、2026-08-23）

**1. 権限の出所と二つの lock 経路**

artifact-change の書込境界を実行主体の自発的な宣言に依存させない（INV-S8）。契約は次の二経路のいずれかで `locked` に到達する。

- **割当 seed（正規経路）**: オーケストレーターがタスク割当時に、対象 worktree・branch・write scope・許可アクションを含む契約 seed をゲート状態へ記録する。ゲートはターン開始時にこの seed を読み、最初の tool call より前にターンを `locked` として作る。実行主体側の操作を必要とせず、実行主体は seed を広げられない。**seed は一回消費されるトークンではなく、タスク（および seed が session を伴う場合はその session）に対する持続的な上限である**。同一タスクの後続ターンも同じ seed から再 lock される。使用履歴はターン単位で記録する。
- **自己 lock（seed が無いターン）**: 対話ターンなど seed の無い場合に限り、lock 前段（第2項）を経て実行主体が lock を要求できる。seed があるターンで lock が要求された場合は、seed 契約をそのまま冪等に返す（既存 closeout の再 lock と同じ挙動）。seed を超える宣言は拒否する。自己 lock はクラス上限（単一 worktree、相対指定、件数上限）に対して検査する。lock 時には**ターンの state に依らず seed を照会する**。「seed があればターンは既に locked のはずだ」という推論に依存させると、上限の担保が host の識別子配線と記録順序に移るため、seed が存在するタスクでの自己 lock は拒否する。
- **自己 lock も契約記録としてタスク単位で持続させる**。監査フックの発火粒度がユーザーターン単位でない構成では、ターンと同時に失効する lock は次の呼び出しを未強制へ戻す。一度自己 lock したタスク（task_id が無い対話では session）の後続ターンは `locked` として作る。
- **分類器の出力は admission の入力にしない**。契約記録が存在するタスクでは、当該ターンの task class は記録が決める（`artifact-change`）。分類器の判定はターン行の監査欄に別途保存し、gold set 較正に使う。分類が別クラス（closeout を含む）へ振れることを権限変更の根拠にしない。真に別タスクなら別 task_id を割り当てるのはオーケストレーター側の責務である。
- **ターン識別子はメッセージ単位である**。task_id だけをターンキーにすると、タスクの全メッセージが1行に退化し、初回分類・壁時計・予算がタスク全体を固定して後続ターンが状態機械上に現れない。

契約には出所（`assignment` / `self`）を記録する。自己 lock 由来の契約は、狭い write scope が独立した権限から与えられていないため、監査上は弱い保証として扱う。自律 worker レーンは常に seed 経路とする。

**2. lock 前の既定（D-S3-4）**

lock されていない artifact-change ターンでは、既知の読み取り系ツール（read/search/list 相当）と作業記録系カテゴリの注記系（D-S3-7、「第一層」参照。run 終端シグナル系は locked 段のみ）だけを許可し、監査記録のみを行う。構造化書込・変異系ツール、`terminal` を含む実行系、未知ツールは既定拒否とし、理由コードを「lock 未了」とする。拒否の計上は「第一層」の計上規則に従う。「lock 未了」は lock 前の段階で発行される単一の理由コードであり、純粋な読み取りも到達する（読み取り専用 git は lock 前段では許可しないため）。したがって確定判定に当たらず、拒否上限へは計上しない。この段はクラス予算で有界である（後述 D-S3-7 補則および「第一層」の計上規則）。読み取り専用 git は lock 前段では許可しない。照合基準となるロック済み root がまだ存在せず、workdir 束縛を検査できないためである。

M1 では artifact-change 専用の discovery 予算を新設しない（discovery 段自体は M2 残余のまま）。上限はクラス予算（wall time / tool calls）とする。**この予算検査は lock 前段と契約検証失敗段の両方に適用する**（`locked` 段と同じ順序で wall → tool → deny）。予算が locked 段にしか掛からなければ、bounded な既定拒否段は実際には無制限であり、D-S3-4 の決定を満たさない。lock 前段の有効化は設定（環境変数）から到達でき、実効値を運用側から確認できるものとする。

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

- **closure は明示のみ**: 強制クラスのターンを中間の監査フックで閉じない。閉じたターンでは変異系を拒否したままにする。session 終了は中間フックではないため、正常終了・異常終了のいずれでも閉鎖契機として機能させる。閉じたターンは policy 注入の対象から外す。
- **閉じたターンは到達可能に保つ**: 「閉じたターンでは変異系を拒否する」は、そのターンにバインドできることが前提である。ターン束縛の優先順位は「未完了の強制ターン → 直近のターン（完了済みを含む）」とする。より古い未完了ターンへ遡ってバインドしない（遡ると明示完了が未強制への遷移になる）。
- **バインディング不能時は fail-closed**: 契約記録（割当 seed または持続的な自己 lock）が task_id か session_id のいずれかで見つかる場合、または当該 task/session に強制クラスのターン履歴がある場合、契約へバインドできない tool call の変異系を拒否する。ターン未登録・未知の turn_id を「未強制」として扱わない。
- **契約検証失敗も fail-closed**: 契約の実体検証に失敗したターンは「変異拒否のまま存在する」状態とし、未強制へ落とさない。ただし**検証結果としての不一致**と**検証の実行失敗**（timeout、一時的 I/O エラー）を区別する。後者ではターンを登録せず、当該呼び出しは未バインド経路で fail-closed のまま、次のフックで検証を再試行できる状態に留める。一度の一過性失敗を回復不能な状態として固定しない。

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

**8. D-S3-6 の適用範囲（2026-08-23 に案A で決定済み）**

- 決定は「worker 適用を M1 に保つ」であり、seed 記録の呼び出し側（割当経路）も M1 の成果物に含まれる。実装は「S3-M1 worker 配線」節に記載する。
- 却下された分岐（M2 へ付け替える場合）は「ゲート側の seed API と lock 前段の既定拒否は M1 で入れるが、自律 worker レーンでの artifact-change 強制は seed が配線されるまで有効化しない」であった。
- いずれの分岐でも「seed 無しで自律レーンを強制する」構成は採らない。この不変条件は配線後も維持される。強制の発効セレクタは seed の存在そのものであり、seed を記録しない設定では従来どおり監査のみである。

**9. 第一層で明文化する残余（2026-08-23 の実装反証レビュー結果）**

- **index の内容は第一層の閉集合主張の外**: commit の admission は引数構文を検査し、その時点の index の内容は照合しない。ゲート経由のステージは write scope に従属するが、ゲートを通らない経路（別プロセス、未強制の窓）で index に入った変更は commit に載る。push は禁止のため影響はローカル履歴に留まる。閉じるならゲート内部の副作用として staged パス集合の照合を admission へ入れる（第二層の opt-in とは独立）。帰属は司令塔判断。
- **terminal 引数フィールドの閉鎖**: 書込ツールに適用した「未列挙は既定拒否」を terminal の引数キーにも適用する。`command` 以外のフィールドは、コマンド allowlist を一切通らない第二の入力になる。
- **host 識別子の解決順序（2026-08-24 の実機確認で確定）**: 契約記録はタスク単位で記録されるため、照会にはそのタスクを名指す識別子が必要である。実機で確認された事実は「フック payload の task_id / session_id はいずれも会話の識別子であり、契約が記録される作業単位（ボードカード）を名指さない」ことであった。したがって照会の正本は **dispatcher が worker プロセスの環境変数へ供給するカード識別子**（`HERMES_KANBAN_TASK`）とし、これが無い場合に payload の task_id → session_id へ落ちる。dispatcher が起動しない経路（対話セッション）は後者で従来どおり束縛される。解決は一つの呼び出しの中で一度だけ行い、seed 照会・ターン生成・バインド不能時の enforced 判定・admission のすべてへ同じ値を渡す（片方の識別子で束縛して他方で admission すると、発効中の契約が自らの呼び出しを覆わなくなる）。in-process フックと out-of-process shell hook は独立した解決点であり、同じ順序に従う。
  - **優先順位は契約を失効させない（2026-08-24 の反証レビュー TB-01 の処置）。** 「アンカーを最優先」は*どの識別子が作業を名指すか*の規則であり、*契約が適用されるか*まで決めてはならない。**いずれかの識別子で契約記録（seed または自己 lock）が引ける場合、解決はそれを失効させる方向へ倒してはならない。** 実装は、両識別子が食い違うときに限り「その識別子で束縛したターンは強制されるか」を照会し、アンカー側が引けず payload 側が引ける場合のみ payload を採る。両方が引ける場合・アンカー側が引ける場合・どちらも引けない場合はいずれも従来どおりアンカーが勝つ。照会は seed・自己 lock の両方を対象とし、それぞれが持つ session フォールバックを含む（アンカーの鍵自体が未 seed でも session 経由で強制が成立するなら、アンカーを維持するのが正しい）。ターン履歴は照会に含めない（記録ではないため、履歴だけを根拠に束縛を動かしても契約は発効しない）。**ただし、前掲のバインディング不能時 fail-closed の enforced 判定（本節前掲）自体は、記録2種に加えて解決済み識別子の強制クラスのターン履歴も根拠に数える（2026-08-24 の再検証 TB2-02）。この判定は解決済みの一つの識別子についてのみ行われるため、識別子が食い違い、記録も強制履歴も持たない側（アンカー）が解決結果として選ばれた場合、選ばれなかった側（payload）にのみ強制履歴があってもこの判定には反映されない。したがって、履歴を照会から除外することの帰結は「契約が発効する」ことではなく、この組合せが未強制側（audited、束縛不能時は allow）に留まることである。**
    - **区別すべき 2 条件**: 「ホスト供給の欠落」（アンカー不在）は不在そのものが payload へのフォールバックを生むため元から fail-closed である。「ホスト供給の誤り」（アンカーが別値）は別条件であり、照会を伴わない優先順位では払い出し済みの契約が無言で失効し、未強制（全許可）へ落ちた。設計はこの 2 条件を区別していなかった。
    - 訂正の向きは強制を*加える*方向のみであるため、偽装面は開かない（実行主体が payload 側の識別子を選べたとしても、選べるのは「その識別子で引ける契約に束縛される」ことだけであり、上限は狭まる）。
    - 照会は解決の内部で一度だけ行う。解決後に二度目の判断を挟むと、束縛と admission が食い違う形（本項冒頭が禁じたもの）が戻る。
    - **解決は各経路の例外境界の内側で行う。** 照会を伴う解決は store 読取を含むため store 障害で失敗し得る。境界の外に置けば下記「ゲート自身の失敗は fail-closed」に反し、拒否ではなく例外が呼び出し元へ抜ける。失敗時は各経路の既定の fail-closed 出口（admission は拒否、ターン登録は未登録のまま＝後続呼び出しが束縛不能経路で fail-closed）へ落とす。**照会側で例外を飲んで「契約なし」を返してはならない**（アンカーが採られ未強制側へ倒れる）。
  - **割当側の seed 記録には適用しない。** そこでの task_id は「配る相手のカード」を指す割当者の鍵であり、実行中の worker プロセスの同一性ではない。両者を統一すると seed が誤ったタスクへ記録される。
  - 環境変数が両方の識別子より優先されるため、テストや検査を worker 環境の中で走らせると明示した識別子が上書きされる。リポジトリの pytest ガードで当該変数を除去対象に加える（同一インシデント類型の既存規定と同じ扱い）。
- **カード単位のターン fallback はプロセス境界を跨ぐ（宣言済み残余、2026-08-24 の反証レビュー TB-03）。** ターン解決は task 識別子を session より先に試すため、アンカー優先化によって同一カードの全 worker が同じ fallback 鍵を共有する。通常は「開いている強制ターン優先 → 新しい順」により自分のターンが勝つが、先行ターンが開いたまま残り（異常終了で closure 未発火）後続 worker のターン登録が成立しなかった場合、その呼び出しは先行セッションのターンへ解決される。**scope 面は fail-closed**（同一カードの契約であるため admit されるパス集合は同じ）であり、拡張 permit は turn 単位鍵のためカード横断の消費も起きない。残るのはターン単位予算の相互消費と監査帰属の混線である。本ラウンドで機構を入れない根拠は次の 2 点:
  - 安価な変種（task 列の照会を session 一致で先に試す）は**当該露出を閉じない**。露出条件は「後続 worker が自分のターンを持たない」ことであり、session 一致の照会は空振りして同じ task 照会へ落ちるため結果が変わらない。
  - 閉じる変種は「プロセス境界を跨ぐ task fallback を外す」ことになる。これはターン解決の共有意味論（closeout も同じ経路に乗る）の変更であり、かつ現在は境界付きで許可されている呼び出しを拒否へ変える admission 変更である。TB-01 の処置範囲（契約を失効させない方向の解決）を超える。
  - したがって帰属は司令塔判断とし、閉じるなら「ターン解決を session 一致へ限定し、跨ぐ呼び出しは束縛不能として fail-closed 経路へ落とす」形で別ラウンドに置く。
- **ゲート自身の失敗は fail-closed**: admission を呼ぶ全経路（pre フック、tool 実行 middleware、制御ハンドラ、shell hook）に例外境界を置く。二重化のうち片側だけが fail-closed である状態を許容しない。記録専用フック（post_tool_call / post_llm_call / on_session_end）は失敗を飲むが例外を外へ出さない。
- **保持期間**: 契約記録（seed・自己 lock）と拡張 permit も保持期間管理の対象とする。失効した記録が新しいターンをロックし続ける状態を作らない。

##### S3-M1 worker 配線（D-S3-6 案A の決定、2026-08-23）

第一層・第二層とライフサイクルはゲート側の規定である。本節は「その契約が実運用のタスクへどう供給されるか」を定める。

**1. seed 呼び出しの配置と順序**

- 配置はオーケストレーターの割当点（`operations/improvement/pda_improvement_cycle.py` の割当関数）である。実行主体の起動と lifecycle は gateway 内蔵の Kanban dispatcher が持つため、配線点は「dispatcher を起こす通知」より前でなければならない。
- 順序は **worktree 用意 → seed 記録 → 割当 CAS → 割当通知** に固定する。
- seed store とタスクボードは別 DB であり同一トランザクションに入れられない。したがって失敗モードは順序で処理する。seed が失敗したら割当へ進まない。逆順（CAS 先行）を採ると seed 無しの worker が起動しうる経路が生まれ、第8項の不変条件（seed 無しで自律レーンを強制しない）の意味が失われる。
- 割当が競合で失敗した場合、未割当タスクに seed が残る。seed はタスクを鍵とする上限であり、割当されないタスクに上限があること自体は無害である。次周期で同一 payload が再導出され、seed の冪等経路を通る。

**2. write scope の出所**

- **カード側の機械可読な宣言を必須とする。** 宣言はオーケストレーターが読むため、出所は実行主体の外にある（INV-S8）。
- 宣言の無いカードは**割当しない**（エラーとし、カードへ一度だけ理由をコメントする）。tenant 既定値（リポジトリ全体など）は置かない。seed の目的は狭い上限であり、既定で広い集合を配れば seed 経路の意味が失われる。
- **拒否は当該カード単位に閉じる**（S3-M1 反証レビュー W-B-06 / W-C-02 の処置、2026-08-23。M1 exit gate で批准対象）。適格リストは優先度順であり、先頭カードの拒否で周期を打ち切ると、宣言を持たない 1 枚が以後すべての適格カードを塞ぐ。有効化初日は既存 Ready カードのいずれも宣言欄を持たないため、この形は確実に起こる。したがって拒否したカードは飛ばして次の候補へ進み、周期の戻り値へ `refused`（カード ID と理由種別）として並べる。1 周期で飛ばす拒否件数には上限を置く（拒否 1 件あたりの作業がカードコメントであるため、走査を盤面サイズに比例させない）。可視性はカードコメント（1 件）と `refused` の 2 経路で確保する。周期内で成立した割当は戻り値の `assigned` に必ず残す（成立済みの割当を「割当ゼロ」と報告しない）。
  - **戻り値 `ok` の意味論が変わる範囲は「割当ループの失敗報告全体」である**（WV-03 の訂正、2026-08-23。M1 exit gate で批准対象）。per-card 回復は割当ループ内の `CycleError` を種別で選別せず捕らえるため、宣言不備に限らず `workspace-collision` / `dirty-worktree` / `claim-race` でも `ok: true` を返す（改訂前は `ok: false`）。`scope_seed.enabled` が false の構成（M1 exit 時点の live 構成）でも同様であり、seed 経路の有効化と独立に発効している。拒否は `refused` に必ず出るため不可視にはならないが、周期の `ok` のみを見る監視から見える形は変わる。周期そのものの失敗（設定不正・方針ファイル読取不能・盤面接続不能など割当ループの外側）は従来どおり `ok: false` である。
- **宣言の検査は worktree 作成より前に行う。** 導出はカード本文と対象ツリーのみを入力とするため先に判定できる。**宣言解析段および幅検査段の拒否**では割当されないカードに branch と worktree を残さず、拒否を飛ばして次を探す際の費用も有界になる。**seed 記録段の拒否（ゲートが契約 seed を受理しない形）では worktree は残る**（記録は worktree の同一性を入力とするため、worktree が存在しないと判定できない）。残った worktree は次周期の `_ensure_worktree` が同一 branch の worktree として再利用する（宣言が修正されればそのまま割当へ進む）。
- **宣言由来の上限には機械的な上限を課す**（S3-M1 反証レビュー W-B-01 の処置、2026-08-23。WV-02 の処置で機構を改訂。M1 exit gate で批准対象）。§3.2 が tenant 既定値を退けた理由は「既定で広い集合を配れば seed 経路の意味が失われる」であり、カード本文から同じ盤面へ到達できるならその理由は満たされない。上限の幅を決めるのは AI が書くカード本文であるため、散文の指示（最小範囲だけを書く）だけを制約にしない。検査はルータ側に置く（ゲートの共有パターン正規化を artifact-change のために拡張しない。D-S3-7 決定 1。照合関数は読み取り専用で利用する）。機構は 2 層で、後段が保証を担う。
  - **綴りの床**: パターンの先頭セグメントが `*` または `**` である宣言は拒否する。ツリーを要さずに成立する点だけが役割であり、**この規則は上限の保証ではない**。パターン言語は同じ幅を別の綴りで書けるため（計上規則の改訂で同型の失敗を確証済み: 開いた引数空間は綴りの列挙では閉じない）、綴りの照合に保証を負わせない。
  - **実効幅の測定**: 宣言（`write_paths` と `test_paths` の**和**。ゲートは書込 admission で両者を合わせて照合するため、実効上限は和である）を**実ツリーへ照合し、被覆する最上位エントリ数**を測る。上限（既定 3）を超える宣言は拒否する。測定量は綴りに依存しないため、綴りを変えても回避されない。上限値は所有者コミットの方針ファイル（`scope_seed.max_top_level_entries`）から変更できる。測定は導出の 2 箇所で行う（割当前検査ではプライマリリポジトリのツリー、seed 記録では対象 worktree のツリー。後者が記録される上限の測定である。前者は worktree 未作成時点の近似で、いずれも拒否側であるため近似が許可を広げることはない）。ツリーが測定できない場合（不在・過大）は拒否する（未測定の上限を狭いと仮定しない）。
  - **統治面の被覆は常に拒否する。** 統治面（ADR D3。`install.py` の `GOVERNANCE_PATHS` と同一集合をルータ側に持ち、突き合わせテストで固定する）は最終承認の段で差分が無条件に拒否されるため、被覆する宣言は最終化できない作業を買うことになる。判定は 2 経路で行う: パターンの字面が統治面に置かれている場合（未作成のファイル名を名指す形を含む）と、実ツリーで統治面のファイルを被覆する場合。**運用手順・reconciler prompt の宣言例も統治面を名指さない形へ改める**（下記の「手順の例は受理形と一致」要求と両立させるため）。
  - 制限は幅のみで、形は制限しない — 再帰形・前方一致・単一セグメント glob はいずれも、被覆する最上位エントリ数が上限内であれば通る。false deny ゼロ要求クラスで通常形を狭めない。測定はツリー相対であるため、同一パターンでも対象ツリーの構成によって判定が変わりうる（統治面のファイルを含むツリーでは、それを被覆する広めの単一セグメント glob が拒否される）。これは意図した性質である。
- **宣言ブロックの認識は Markdown の不活性領域を区別する**（S3-M1 反証レビュー W-B-04 の処置）。4 桁以上インデントした fence、および別の fence の内側にある fence は宣言として読まない。区別しない実装は双方向に壊れる: 図解として書かれたテキストが実効上限になる方向と、実宣言と図解を併記したカードが「2 ブロックある」として拒否される方向である。後者は false deny ゼロ要求クラスの Ready 化条件では許容できない。**運用手順に示す例は受理形と一致していなければならない**（正本手順どおり写したカードが拒否される形を作らない）。自動テストで手順書の例が受理形であることを固定する。
- 宣言は Ready 化条件に加える（運用手順は `docs/operations/pda-improvement-cycle.md`）。
- 各欄の既定: `write_paths` は宣言必須、`test_paths` は無宣言なら空集合、`execution` は既定で空集合（第二層 opt-in 無し）、`actions.git_write` はクラス既定（D-S3-3）から**縮小のみ**受ける。
- **導出はカードから決定論的でなければならない。** 同一タスクに対する二度目の seed 記録が異 payload だとゲートは硬く失敗するため、パターンの正規化・順序はゲートの正規化関数に一任し、呼び出し側で並べ替えない。
- タスク進行中に宣言が編集されると、次周期で異 payload となりタスクが詰まる。これはオーナー操作の領域とし、エラーとカードコメントで表面化させる。**無言で新 payload を通す経路は作らない**（seed の上限性が失われる）。スコープ変更は新カードとして扱う。

**3. 記録した契約と実行中の worker を結ぶ識別子（2026-08-24 の実機確認で確定）**

- seed はカードを鍵として記録される。したがって供給が成立するには、実行中の worker のターンが同じ鍵で照会されなければならない。**実機では、フックへ届く task_id / session_id はいずれも Hermes セッションの識別子であり、カードを名指さない**（両欄が同値で届く）。payload だけを見る解決では seed は結合せず、ターンは監査のみとして開く。
- 結合の正本は **dispatcher が worker プロセスの環境変数へ供給するカード識別子**である。これは実行主体の外（ホスト）が与える値であり、INV-S8（上限の出所は実行主体の外）と同じ性質を持つ。実行主体はこれを書き換えて自分の上限を広げることはできない — 書き換えて別カードの上限が当たれば有界になり、何も引けない値にしても**第 9 項の解決規則により払い出し済みの契約は維持される**（引ける識別子側が採られる）。「契約が見つからない」ことを安全側とみなす推論は成立しない: 契約不在は未強制（全許可）を意味し、payload 側が持っていた上限より広い。この点は 2026-08-24 の反証レビュー TB-01 で実測により反証され、解決規則の側で処置した。
- **本項はゲート側の運用条件であり、割当側の追加実装を要さない。** 環境変数を供給するのは gateway 内蔵の dispatcher であって本リポジトリのオーケストレーターではないため、seed 記録の順序（第1項）は変わらない。
- ホスト側の供給が失われた場合、および誤った値が供給された場合の挙動はいずれも fail-closed である: 結合できないターンで seed 済みカードの変異は「契約はあるが呼び出しを束縛できない」として拒否され、監査のみへは落ちない。実機では供給欠落の経路が実際に発火し、worker は自ら変異を諦めてカードを理由付きで block した。供給が誤っている経路（アンカーが別カードを名指す）は当初この保証を満たしておらず、第 9 項の解決規則で閉じた。
- **アンカーが seed 済みカードを指すとき、そのターンの分類は closeout を含めて契約側が上書きする**（2026-08-24 の反証レビュー TB-04 の射程訂正、2026-08-24 の再検証 TB2-01 でさらに訂正）。「契約記録は分類器より優越する」（本節の分類器方針）の文字どおりの帰結であり意図された挙動だが、**「アンカー優先化は closeout 挙動を変えない」という主張の射程は「アンカー不在時、または当該カードが未 seed のとき」に限られる。ただし、payload 側の識別子が契約（seed または自己 lock、session フォールバックを含む）へ到達し、かつアンカー側がいずれの経路（鍵自体または session フォールバック）でも到達しない場合は、この限りではない**。この場合は TB-01 の解決規則により束縛が payload 側へ移り、payload 側の契約の class（例: `artifact-change`）がターンを locked として束縛するため、closeout は保たれない。dispatcher レーンでは改訂前は seed が結合しなかったため closeout が保たれており、そこは live 挙動が変わった箇所である。方向は fail-closed（push が使えなくなる）であり安全性の後退は無い。**運用条件（TB-04 の運用含意、司令塔決定 2026-08-24）: closeout を要する作業は seed 済みカードへ割り当てない。**真に別クラスの作業なら別カード（別 task_id、未 seed）を割り当てるのが割当側の責務である。

**4. worker profile への適用方法**

- **profile 単位の plugin/hook 適用は不要であり、存在しない。** ゲートは gateway 水準の plugin であり、profile 別の有効化スイッチを持たない。**レーンの強制セレクタは seed の存在**であって profile 設定ではない。
- profile 側が担うのは強制スキルの付与と、手順記述が admit 済み集合と整合していることの 2 点のみである。後者の整合化の方向は「admit 済みの読み取り形を positive に名指す」ことであり、admit されない形へ手を伸ばさせないためである。

**5. 有効化経路（2 つのスイッチは別物）**

1. **割当側 seed フラグ（新設、既定 false）**: 委任方針ファイル（`continuity/autonomous-improvement.json`）の `scope_seed.enabled`。false なら seed を記録せず、従来どおり監査のみの worker になる。**割当関数の当該引数に既定値を置かない**（S3-M1 反証レビュー W-B-03 の処置）。既定値があると呼び出し側の省略が強制なしの割当を成功として完了させる fail-open 形になるため、省略は呼び出し時エラーとする。既定 false はコミット済み方針ファイル側の既定として持つ。**これが自律レーンの opt-in である。** seed を記録すること自体が強制の発効であるため、他にスイッチは要らない（D-S3-8 の「自律 worker レーンの有効化は seed 配線と同時」の文字どおりの実装）。フラグは委任方針側（オーナーコミット）に置き、レンダリング済みの実行時設定側には置かない。発効判断は導出状態ではなくオーナーがコミットしたファイルに属す。
2. **lock 前段の既定拒否スイッチ（既存、既定 off）**: **seed が無いターン**の lock 前段を制御する。自己 lock レーン（対話ターン）のための D-S3-8 スイッチであり、seeded レーンには関与しない。設定先は gateway プロセスであって割当プロセスではない。

M1 成果物としては呼び出し側を配置し、フラグ既定 false で inert に出荷する。加えて委任方針自体がオーナー停止中であるため、M1 exit 時点で live 影響はゼロである。本番有効化は次 gate の承認事項。

**6. Judgment A（承認 metadata の canonical Git 同一性 2 項の供給手段）— 決定済み（2026-08-23、司令塔）**

第一層は承認 metadata が要求する Git ディレクトリ同一性 2 項（worktree の git-dir と共有 git-dir）の取得形を admit しない。当該取得形を共有 allowlist へ足す案は D-S3-7 決定 1（共有実装を artifact-change のために拡張しない）に抵触するため不採用である。決定は**承認ゲート側での導出（案b）**である。

- 台帳へ書く値を実行主体の申告値からゲート自身の導出値へ差し替える。導出コードは承認時・消費時の両検証点に既に存在する。
- 承認 metadata スキーマから当該 2 欄を外し、スキーマ版を上げる。**申告されていた場合は拒否する**（検査主体がいなくなった欄が承認 digest の中を通ることを許さない）。独立実装の 2 つの validator は同一挙動を回帰テストで固定する。
- digest は実行主体が作成したオブジェクト（2 欄を除いたもの）に対して取る。**ゲート側で augment してから digest を取る形は採らない** — digest 実装は独立に 2 つあり、両者が同一に augment し続ける保証を要求する形を避ける。
- 2 点 drift 検査は「承認時のゲート導出値 vs 消費時のゲート導出値」となり、台帳行が両者を媒介する。実質的な安全性質（対象が linked worktree であること = 実行主体が primary repository 上で作業していないこと）は元から導出値のみで判定されており、申告値を参照していなかったため、この変更で境界は弱まらない。
- **導出の入力自体を worker の上限外へ置く**（S3-M1 反証レビュー W-B-02 の処置、2026-08-23）。導出主体を申告者からゲートへ移すだけでは、導出が読む先が worker の書込可能面の内側にある限り、provenance は「worker が申告した値」から「worker が書き得るファイルが述べる値」へ移るだけである。したがって (i) 第一層は `.git` セグメントを含む書込・ステージを宣言の幅によらず拒否し、(ii) 承認ゲートは解決先が workspace 配下に入る workspace を承認不可として同一性を導出しない。上記「第一層」の当該項を参照。
- **スキーマ版上げの移行**（S3-M1 反証レビュー W-C-03 の処置）。両 validator は当該 2 欄の**存在自体**を拒否するため、本変更以前に作られた未消費の承認行は消費経路・再承認経路の双方で受理されない。互換分岐は置かない（受理する分岐は「検査主体がいなくなった欄を digest の中で通さない」という本決定の趣旨と衝突する）。復旧は新しい review handoff とオーナー再承認であり、台帳の `UNIQUE(task_id, review_run_id, digest)` により旧行と衝突しない。**有効化手順書へ「本変更以前の未消費承認は再ハンドオフが必要」を明記し、有効化前に未消費行の有無を確認する**（`docs/operations/pda-improvement-cycle.md`）。
- **正直な残余**: オーナーが承認する digest が worktree 同一性を覆わなくなる。同一性の束縛はゲートが書いた台帳行へ移り、監査者は digest ではなく台帳行を見る。これが案(a)（割当 seed が値を供給する）と比較したときの唯一の実質的な後退である。ただし消費時の実地再導出が残るため、「承認された台帳行の同一性が消費時点でも成立していること」は引き続き機械的に検査される。
- 案(a) を採らなかった理由: (i) 第5項（S2）が定める「production safety approval と scope admission を別判定として維持する」に反し、承認契約のスキーマが scope gate のスキーマに依存する。(ii) 値は結局 seed の read-back 経路を通って実行主体から承認オブジェクトへ転記されるため、provenance は本質的に改善しない。(iii) worktree が正当に再作成されると seed の値と実地導出値が乖離し、scope admission と無関係な値のために承認が fail-closed で止まる。(iv) スキーマ変更が 2 箇所になる。

##### M2 への残余（本設計で明示的に先送り）

- judge の実接続、artifact-change 用 discovery 段、実トラフィックからの S3 exit 用 gold set、pre_llm_call のクラス別 policy 注入の拡充、verification 契約（検証者ハンドオフ）との統合、第二層の隔離実行と収集経路の静的検査。
- 読み取り系ツールのパス境界（下記「第二層」の M2 必須要件 1 に併合。Judgment B、2026-08-23）。
- worker profile への配線は M1 の成果物である（D-S3-6 は案A で決定済み）。本番有効化は次 gate の承認事項として残る。

#### S3-M1 未解決の設計判断（2026-08-22 反証レビュー結果、2026-08-23 に D-S3-1・2・3 決定）

上記ドラフトは実装着手前の並列反証レビュー（運用細則2）を通し、確証欠陥 20 件（blocker 6 / major 7 / minor 7）が返った。各欠陥の根拠と対応方針、および欠陥 ID（R-01〜R-20）の採番対応表は `docs/status/restricted-s3-write-scope-review-2026-08-22.md` にある。同ファイルは迂回手法の具体形を含み Fable セッションでは直接読まない扱いのため、対応は Opus のサブエージェントへ委譲する。

- **D-S3-1（検証実行の位置づけ）— 決定済み（2026-08-23）**: 実行を伴う検証は許可するが、契約単位の明示 opt-in を必須とする。実行中のプロセス副作用は write 境界の保証対象外であることを脅威モデルとして明文化し、名前空間の隔離と収集経路の静的検査を M2 の必須要件として固定する。テスト資産の新規作成・編集は、テストディレクトリ全体の無条件免除ではなく `targets.test_paths` の閉集合として許可する。詳細は上記「契約の拡張」「第二層」。
- **D-S3-2（引数検査の水準）— 決定済み（2026-08-23）**: 許可コマンドの引数検査を closeout の既存実装と同水準（全トークン走査、安全な指定の明示 allowlist、未知の指定は即 deny）へ揃える。パス照合の健全性（正規化基準の一元化、glob のセグメント境界扱い、実体解決、書込先フィールドの網羅）を同じ改訂で扱う。詳細は上記「第一層」「第二層」。
- **D-S3-3（ローカルコミットの扱い）— 決定済み（2026-08-23）**: worker のローカルコミットを決定論 allowlist へ含める。ステージ範囲は write scope へ従属させ、一括ステージ系の指定は許可しない。push は承認後の別契約に残す。詳細は上記「第一層」。
- **D-S3-4 / D-S3-5（lock 前の既定・lock 到達性）— 決定済み（2026-08-23）**: 契約ライフサイクルは上記「S3-M1 契約ライフサイクル」で決定した。lock 前の無制限許可を廃し bounded な既定拒否段に置き換え、`locked` への到達は「割当由来の seed 契約（正規経路・自律 worker レーンは必須）」と「seed が無いターンでの自己 lock（縮小のみ）」の二経路とする。
- **D-S3-6（M1/M2 の境界）— 決定済み（2026-08-23、オーナー承認）**: ドラフトは S3 の worker 配線を M2 へ先送りしたが、ADR D2 と goal M1 はこれを M1 の成果物と規定していた。決定は**案A（worker 配線を M1 の成果物とする）**であり、ADR 改訂は行わない。したがって第8項の 2 分岐のうち前者が確定し、seed 記録の呼び出し側（割当経路）も M1 に含まれる。実装は「S3-M1 worker 配線」節に記載する。有効化は seed フラグの既定 off により M1 exit 時点では発効しない（本番有効化は次 gate の承認事項）。

- **D-S3-7（第一層の許可集合と運用手順の整合）— オーナー判断事項として 2026-08-23 に起票、同日の司令塔決定で解決。M1 exit gate で批准対象**: 起票時の第一層は、書込・ステージ・ローカルコミット・opt-in 検証のみを許可し、読み取り専用 git と作業記録系ツール（kanban 系・todo 系）を拒否していた。これは §11 第一層の列挙に対する厳密読みだが、(a) ステージ対象を列挙するための差分確認手段が契約内に無く、(b) 自律 worker レーンの必須手順（承認 metadata の commit id・changed files・ブランチ同一性、カード更新）が契約内で完結せず、(c) それらの拒否が拒否上限を消費してターンを座礁させうる。決定は次の4点で、いずれも上記「第一層」「§10 artifact-change の受入項目」に反映済みである。
  1. 読み取り専用 git（`status` / `diff` / `rev-parse` / `branch`）を第一層へ加える。引数検査は closeout と同一の tokenizer / allowlist 実装を経由し、新しいパーサーを作らない。`log` とネットワーク越しの読み取りは含めない（理由は「第一層」に記載）。
  2. 作業記録系カテゴリを新設し、閉じた明示カタログで定義して第一層で許可する（audit 記録のみ）。capability 推論やツール形状ヒューリスティックで判定しない。未列挙ツールの default deny for mutation は不変。
  3. 拒否上限への計上を write 境界・実行境界への逸脱試行に限定する。上限値（6）は維持する。計上されない拒否経路はクラス予算で有界に保つ。
  4. artifact-change 版の受入 replay 項目（強制状態を通す）を §10 へ別立てで新設する。既存項目 1〜14 は改訂しない。`push` は S3 第一層の対象外である。

  実装後の反証レビュー（2026-08-23）を受けた適合化。決定 2・3 はカタログの中身と分類の粒度を実装へ委ねているが、初回実装の粒度が決定文の意図から外れていた。次の 2 点を「第一層」へ反映済みである。設計判断の変更ではなく決定文への適合化であるが、(b) の段階別二分は許可範囲の縮小を伴うため批准対象として記載する。
  - (a) 計上の分類単位を subcommand 名から invocation 単位へ改めた。subcommand 粒度では、状態変更形を併せ持つ subcommand 族が免除側に載り（write 境界の反復探索が拒否上限で有界にならない）、境界内の純粋な読み取りが計上側に落ちる（必須手順に従うターンが上限で座礁する）という両方向の誤りが同時に成立する。三分類の内容は「第一層」の計上規則に記載。
  - (b) 作業記録系カタログを段階別に二分し、run 終端シグナル系を locked 段のみへ限定した。併せて、宛先（パス・URL・他カード）を引数に運ぶツールと統治権限に属するツール（カード新規作成、レビュー差戻し記録）をカタログ外へ出した。引数無検査で許可する範囲は「引数によらず安全である」と言える形に限る必要があり、run 終端は審査ゲート自身の入力面である。

  **D-S3-7 補則（計上規則の確定判定由来化）— 司令塔決定、2026-08-23。M1 exit gate で批准対象**: 決定 3 の計上規則を、terminal 引数の分類由来から admission の確定判定由来へ改める。内容は「第一層」の計上規則に反映済みである。

  経緯: 決定 3 の実装は、拒否を「逸脱試行か否か」の二方向へ分類する必要を生み、上記適合化 (a) はその分類単位を invocation へ改めた。しかしその分類は、terminal 引数の綴り（どの option がパスを開き、どの綴りが書込形か）の並行列挙に依存する。この列挙は 3 巡連続で同型の網羅漏れを確証され（各巡の詳細は `restricted-s3-impl-fix-2026-08-23-disposition.md`）、独立検証者は「開放的な引数空間の双方向分類は列挙では原理的に閉じない」と指摘した。網羅漏れは両方向に成立し、計上側であるべきものが免除側へ落ちる（境界の反復探索が tool 予算でしか有界にならない）と同時に、免除側であるべきものが計上側へ落ちる（必須手順に従うターンが上限で座礁する）。

  補則の要点は次の 3 点である。

  1. 計上は admission の確定判定が発行する理由コードのみを対象とする（有限の明示集合、既定は非計上）。
  2. ヒューリスティック分類段の拒否は計上しない。分類は audit の帰属表示へ降格し、計上判定は分類表を参照しない。
  3. admission は無変更である。全ての拒否は拒否のまま維持され、変わるのは計上先の帰属のみである。境界（第一層の硬い保証）は影響を受けない。

  安全目的の担保: 上限の目的（境界の反復探索の遮断）は、確定判定由来の逸脱については引き続き拒否上限が満たす。非計上へ移った経路は tool 予算（クラス予算）で有界であり、枯渇時は拒否で閉じる。座礁防止の目的は、非計上が既定になることで従前より強く満たされる。

  **補則の定式化統一と帰属確定 — 司令塔決定、2026-08-23。M1 exit gate で批准対象**: 補則の初版は帰属規則を二通りに書いていた（レーン別の確定事実の列挙と、読み取りが到達しうるかを問う litmus）。両者は「同値な言い方」と述べられていたが実行レーンで乖離し、実装は列挙側を採ったため、ファイル内容を読む目的の terminal 呼び出しが上限を消費して規定フローのターンを座礁させた（V3-02 で実測）。決定は次のとおり。

  - **litmus を唯一の規範とする。** レーン別の確定事実は litmus の適用結果として位置づけ、両者が食い違う場合は列挙側を誤りとして扱う。
  - 個別帰属を次のとおり確定する（詳細は「第一層」の計上規則）。
    1. 認識外の subcommand・認識外のツールの拒否は**非計上**。admission は拒否のままであり、tool 予算で有界である。
    2. terminal の workdir がロック済み worktree 外である拒否は**非計上**（字句解析より前に決まるためレーンが未確定）。字句解析後の workdir 再判定は M2 の検討残余とする。
    3. ステージ・コミットの引数形の拒否は**計上を維持**（`git add` / `commit` の名前でレーンが確定しており、純粋な読み取りは到達しない）。実行テンプレート**不一致**の拒否は**非計上へ改める**（レーン未確定。読み取り目的の呼び出しが到達する）。テンプレート起動形に**一致した後**の引数形の拒否は計上を維持する。
    4. 冪等性ガードの直接計上は**維持**し、litmus の明示例外として記載する。

  この決定による計上集合の変更は計上 → 非計上の一方向のみであり（非計上 → 計上はゼロ）、admission は無変更である。
- **D-S3-8（lock 前段の既定値の適用範囲）— オーナー判断事項として 2026-08-23 に起票、同日の司令塔決定で既定 off を批准。M1 exit gate で批准対象**: 実装は lock 前段の既定拒否を全レーンで既定 off にしている。第8項の M2 分岐が免除しているのは「自律 worker レーンでの強制」だけで、seed 配線に依存しない自己 lock レーン（対話ターン）まで既定 off にするのは設計より広い、という起票内容であった。決定は次のとおり: **既定 off は INV-S8 の恒久緩和ではなく、S1 と同じ段階的 rollout 方針（他クラスは契約・audit のみとし、既存作業を突然 block しない）の適用である**。lock 前段の既定拒否は rollout 制御下に置き、既定は無効、有効化は設定経路（環境変数）による明示操作とする。自己 lock レーンの有効化は S3 rollout の実運用評価で判断し、自律 worker レーンの有効化は seed 配線と同時とする（D-S3-6 の分岐に従属）。設定経路の実効値は運用側から確認できるものとする。

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
