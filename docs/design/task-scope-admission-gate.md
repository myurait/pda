# PDAタスク・スコープ審査ゲート設計

Status: Proposed
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

### S0: contract and replay harness

- ScopeContract JSON Schema、normalizer、incident fixturesを実装する。
- 実repositoryを変更しないfixtureでallow/deny、budget、parallel raceを検証する。

Exit: 元事例の不要actionをすべて拒否し、必要なcloseout actionを拒否しない。

### S1: hard gate for `repository-closeout`

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
