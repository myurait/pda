# 仕事の流れと実行の永続化の系譜 — 一次資料調査ノート

作業ディレクトリ: `$WT/tmp/research-core-2026-09-20/`
ローカル取得物: `$WT/tmp/research-core-2026-09-20/_src/` 配下
（このディレクトリは他の並行調査エージェントと共有。ACL/actor/KQML系のファイルは本調査と無関係）

---

## 1. Workflow net と soundness — van der Aalst

### 取得状況

| 資料 | URL | HTTP | 備考 |
|---|---|---|---|
| "The Application of Petri Nets to Workflow Management" (JCSC 1998) | 検索のみ、無償PDFの直リンク不発見 | — | 未発見（下記参照） |
| "Workflow Verification: Finding Control-Flow Errors Using Petri-Net-Based Techniques" (van der Aalst, LNCS 1806, 2000) | `https://www.vdaalst.com/publications/p98.pdf` | **200** | 著者本人サイトの正規ミラー。ローカル: `_src/vdaalst_p98.pdf`（23ページ） |
| （参考）Soundness of Workflow Nets with Reset Arcs | `https://www.vdaalst.com/publications/p559.pdf` | 200 | 未使用（参考のみ、ローカル: `_src/vdaalst_p559.pdf`） |

課題本文は「1998年JCSC論文 **または** Workflow Verification論文」のいずれか可、とあるため後者を一次資料として採用。JCSC 1998論文自体は ResearchGate/Springer 経由でのみ言及があり、無償full-text直リンクは発見できなかった（試した検索語: `van der Aalst "The Application of Petri Nets to Workflow Management" 1998 filetype:pdf`、`site:pure.tue.nl OR site:research.tue.nl OR site:vdaalst.com`）。vdaalst.com の出版リストは番号採番（p98, p559 等）で一致するファイル名を特定できなかった。

**PDF抽出の技術的注記**: 本PDFは数式記号（∀, →, ∈ 等）がToUnicode CMapを持たないフォントで埋め込まれており、`pypdf` によるテキスト抽出では数式部分が `/C8/BN/CC` のような文字コードに化ける。地の文（英語散文）は正しく抽出できるため、定義の言明は英語散文部分から逐語引用した。

### 抽象・不変量（Definition 11, 12）

**該当箇所**: p98.pdf ページ7〜8（Definition 11, WF-net）、ページ9（Definition 12, Sound）

Definition 11 (WF-net) の骨子（逐語、地の文）:
- "A WF-net has one input place ( i ) and one output place ( o )"（page 8）

Definition 12 (Sound) — 3条件の逐語引用（各15語以内、ページ9）:

1. **(i) option to complete** に相当する説明文（Definitionの直後の解説）:
   > "it is always possible to reach the state with one token in place o"（page 9）

2. **(ii) proper completion** — 論文自身がこの用語を明示的に使用:
   > "Sometimes the term proper termination is used to describe the first two requirements"（page 9）

3. **(iii) no dead transitions** — 論文自身がこの表現を使用:
   > "there are no dead transitions (tasks) in the initial state i"（page 9）

Definition 12 本文の形式部分（数式）は次の3条件として構成されている（数式記号は文字化けのため構造のみ記載）:
- (i) 任意の到達可能状態 s から状態 o への発火系列が存在する
- (ii) 状態 o は、プレース o にトークンを持つ到達可能状態の中で唯一の状態である
- (iii) 初期状態 (PN, i) においてデッド遷移が存在しない

これは課題が求める「ワークフローが保証する不変量」の最も形式的な定義そのもの。

---

## 2. soundness を実際に検査する実装 — YAWL

### 取得状況

- Clone: `git clone --depth 1 https://github.com/yawlfoundation/yawl` は `.git/config` への書き込みがサンドボックスで拒否されたため、`codeload.github.com` からtarball取得に切替（HTTP 200）→ 展開。ローカル: `_src/yawl/`

### 実装1: 構造的検証（Definition 11 相当）— 仕様ロード時に強制

**file:line**: `_src/yawl/src/org/yawlfoundation/yawl/elements/YNet.java:183-276`

```
205:        //check that all elements in the net are on a directed path from 'i' to 'o'.
206:        verifyDirectedPath(handler);
```
`verifyDirectedPath()` は入力条件からの前方到達集合と出力条件からの後方到達集合を計算し、全要素がその両方に含まれるかを検証する。これは van der Aalst Definition 11(iii)「すべてのノードが i から o への経路上にある」の直接実装。

**強制のタイミングと結果**: `_src/yawl/src/org/yawlfoundation/yawl/engine/YEngine.java:555-558`
```
555:                specification.verify(verificationHandler);
556:
557:                //if the error messages are empty or contain only warnings
558:                if (ignoreErrors || ! verificationHandler.hasErrors()) {
```
`hasErrors()` が真かつ `ignoreErrors=false` の場合、`loadSpecification()` 自体が呼ばれない＝仕様はエンジンにロードされず実行不能になる。**エディタ警告止まりではなく、実行そのものを拒否する**（ただし `ignoreErrors=true` を呼び出し元が指定すればバイパス可能）。

**重要な限定**: この `verify()` は Definition 11 相当の**静的構造検証**（単一入出力条件・接続性・ローカル変数束縛）に留まり、van der Aalst Definition 12（生存性・到達可能性に基づく動的 soundness）そのものを計算するコードはこのリポジトリのコア engine には**存在しない**（`grep -rn "soundness"` はゼロ件、`Woflan` への言及もゼロ件）。フルsoundness解析は歴史的に別ツール（Woflan / YAWL Editorの解析プラグイン）の領分であり、このリポジトリのスナップショットには含まれていない。

### 実装2: 実行時のreset net計算（OR-join enabling）— 部分的な動的到達可能性計算

**file:line**: `_src/yawl/src/org/yawlfoundation/yawl/elements/e2wfoj/E2WFOJNet.java:26-30`
```
26: /**
27:  *  A Reset net formalisation of a YAWL net.
28:  *
29:  **/
30: public final class E2WFOJNet {
```
`orJoinEnabled(YMarking M, YTask orJoin)` （同ファイル728行目）は、マーキング集合を探索する到達可能性ベースの計算（`alreadyConsideredMarkings` フィールドで探索済みマーキングを記録）で、OR-join が発火可能かどうかを**実行時**に判定する。

**呼び出し元・強制のタイミング**: `_src/yawl/src/org/yawlfoundation/yawl/elements/YTask.java:1013`
```
1013:                return _net.orJoinEnabled(this, id);
```
これはケース実行中（ランタイム）に呼ばれる。つまりYAWLエンジンは、設計時の完全なsoundness証明ではなく、**実行時に都度reset net理論に基づく到達可能性計算を行ってOR-joinの正しい同期を保証する**という設計。デッドロック検出は「起きた瞬間に動的に防ぐ」形であり、事前の静的証明ではない。

**結論（検査失敗時の挙動）**: 静的検証（Definition 11相当）は失敗するとロード拒否＝実行拒否。動的soundness（Definition 12相当、生存性・到達可能性の全数検証）はこのコードベースには実装されておらず、代わりに実行時のOR-join reset net計算という部分的な動的機構で置き換えられている。

---

## 3. BPMN 2.0 の実行意味論 — OMG公式仕様

### 取得状況

| URL | HTTP |
|---|---|
| `https://www.omg.org/spec/BPMN/2.0/PDF` | **200** |

ローカル: `_src/omg-bpmn-2.0.pdf`（538ページ、OMG Document Number formal/2011-01-03, Version 2.0, January 2011）

### 該当箇所と逐語引用

**Chapter 13 "BPMN Execution Semantics"**（印刷ページ425〜）、**13.1 Process Instantiation and Termination**（印刷ページ426）、**13.2.1 Sequence Flow Considerations**（印刷ページ427）

トークンの流れの定義（逐語、13.2.1、page 427、15語以内）:
> "A token is a theoretical concept that is used as an aid"

> "modeling and execution tools that implement BPMN are NOT REQUIRED to implement any form of token"（page 427。BPMNのトークンはあくまで意味論記述のための概念装置であり、実装必須の機構ではないと明記）

Start Event によるトークン生成の定義（逐語、13.1、page 426、13語）:
> "Each Start Event that occurs creates a token on its outgoing Sequence Flows"

Process完了の3条件（13.1、page 426、逐語・箇条書きそのまま、いずれも15語以内）:
> "There is no token remaining within the Process instance."
> "No Activity of the Process is still active."

---

## 4. Durable execution の保証

### 4-A. Temporal (sdk-go)

**取得**: `git clone` は `.git/config` 書き込みがサンドボックスで拒否されたため、`codeload.github.com/temporalio/sdk-go/tar.gz/refs/heads/main`（HTTP 200）に切替。ローカル: `_src/sdk-go/`。関連proto定義は `codeload.github.com/temporalio/api/tar.gz/refs/heads/master`（HTTP 200）、ローカル: `_src/api/`

#### 非決定性検出（何を比較しているか）

**file:line**: `_src/sdk-go/internal/internal_task_handlers.go:1581-1632`（`matchReplayWithHistory` 関数）

この関数は、リプレイ時にワークフローコードが生成した **commands**（`replayCommands`）と、サーバーに保存された **historyEvents** を先頭から順に1件ずつ突き合わせる（`di`, `hi` の2ポインタでウォーク）。

比較の実体は `isCommandMatchEvent(d, e, msgs)`（同ファイル1642行目〜）。例えば `COMMAND_TYPE_SCHEDULE_ACTIVITY_TASK` の場合:
```go
1660:		if eventAttributes.GetActivityId() != commandAttributes.GetActivityId() ||
1661:			lastPartOfName(eventAttributes.ActivityType.GetName()) != lastPartOfName(commandAttributes.ActivityType.GetName()) {
1662:			return false
```
つまり **ActivityId と ActivityType名の一致**で比較している。一致しない、片方が欠ける（`d == nil` または `e == nil`）場合は下記のエラーを返す:

```go
1616:		return historyMismatchErrorf("[TMPRL1100] nondeterministic workflow: missing replay command for %s", ...)
1620:		return historyMismatchErrorf("[TMPRL1100] nondeterministic workflow: extra replay command for %s", ...)
1624:		return historyMismatchErrorf("[TMPRL1100] nondeterministic workflow: history event is %s, replay command is %s", ...)
```

もう一つの検出経路（コマンドをIDで引く際に見つからない場合）: `_src/sdk-go/internal/internal_command_state_machine.go:1069-1076`
```go
1069: func (h *commandsHelper) getCommand(id commandID) commandStateMachine {
1070: 	command, ok := h.commands[id]
1071: 	if !ok {
1072: 		panicMsg := fmt.Sprintf(
1073: 			"[TMPRL1100] During replay, a matching %v command was expected in history event position %s. However, the replayed code did not produce that. "+
1074: 				"Possible causes are nondeterministic workflow definition code, or an incompatible change in the workflow definition.", id.commandType, id.id)
1075: 		panicIllegalState(panicMsg)
```

#### ワークフローコードへの制約（決定論的でなければならない）とその強制

**強制のタイミング**: **実行時検出**（replay時、history と replay commands の突合）。これは全ワーカーで自動的に走る（オプトインではない）。

**結果（検出後どうなるか）**: `_src/sdk-go/internal/internal_task_handlers.go:1305-1345`（`applyWorkflowPanicPolicy`）
```go
1332: 		switch w.wth.workflowPanicPolicy {
1333: 		case FailWorkflow:
1334: 			// complete workflow with custom error will fail the workflow
...
1338: 		case BlockWorkflow:
1339: 			// return error here will be convert to WorkflowTaskFailed for the first time, and ignored for subsequent
1340: 			// attempts which will cause WorkflowTaskTimeout and server will retry forever until issue got fixed or
1341: 			// workflow timeout.
1342: 			return nil, workflowError
```
デフォルトポリシーは `BlockWorkflow`。定義: `_src/sdk-go/internal/worker.go:542,548`
```go
542: // BlockWorkflow is the default policy for handling workflow panics and detected non-determinism.
...
548: 	BlockWorkflow WorkflowPanicPolicy = iota
```
つまり**デフォルトでは非決定性検出時にワークフローは失敗させず、WorkflowTaskFailedを経てサーバーが無限リトライする（＝実行を止めて人間が直すまでブロックする）**。`FailWorkflow` を明示指定した場合のみワークフロー自体を失敗させる。

**静的検査（オプトインの別ツール）**: `_src/sdk-go/contrib/tools/workflowcheck/determinism/checker.go:1-52` — `go/analysis` ベースのリンター。`Config.AcceptsNonDeterministicParameters` 等を持つ独立ツールで、SDK本体のビルド・実行フローには組み込まれていない（`contrib/tools/` 配下、別途実行が必要なCLI）。**つまり静的検査はオプトインのリンターのみで、コンパイラによる強制はない。実行時検出（replay照合）がSDKに組み込まれた唯一の自動強制経路。**

#### 仕事と成果を置くストアの形（event history）

**file:line**: `_src/api/temporal/api/history/v1/message.proto:1154-1160`
```protobuf
1154: // History events are the method by which Temporal SDKs advance (or recreate) workflow state.
1155: // See the `EventType` enum for more info about what each event is for.
1156: message HistoryEvent {
1157:     // Monotonically increasing event number, starts at 1.
1158:     int64 event_id = 1;
1159:     google.protobuf.Timestamp event_time = 2;
1160:     temporal.api.enums.v1.EventType event_type = 3;
```
`HistoryEvent` はprotobufで機械可読なスキーマとして規定されており、`event_id` は「モノトニックに増加、1始まり」＝順序保証つき。

#### event streamの形（有限enum）

**file:line**: `_src/api/temporal/api/enums/v1/event_type.proto:13-178`
```protobuf
13: enum EventType {
14:     // Place holder and should never appear in a Workflow execution history
15:     EVENT_TYPE_UNSPECIFIED = 0;
16:     // Workflow execution has been triggered/started
17:     EVENT_TYPE_WORKFLOW_EXECUTION_STARTED = 1;
...
178: }
```
72個の `EVENT_TYPE_*` 値（`UNSPECIFIED` 含む）を持つ有限enum。ファイル冒頭のコメント:
> "Whenever this list of events is changed do change the function shouldBufferEvent"
（このコメント自体がenumが有限かつサーバー側の順序制御ロジックと同期すべき閉じた集合であることを示す）

#### 異種の実行主体（言語非依存性）

`api.tar.gz` の `.proto` 定義（`go_package`, `java_package` オプション付き、`_src/api/temporal/api/enums/v1/event_type.proto:5-6`）自体がprotobuf/gRPCによる多言語コード生成を前提とした設計であることを示す。sdk-go, sdk-java, sdk-python, sdk-typescript が同一の `temporalio/api` リポジトリのprotoを共有している（本リポジトリはそのGo向け実装）。

---

### 4-B. DBOS (dbos-transact-py)

**取得**: `codeload.github.com/dbos-inc/dbos-transact-py/tar.gz/refs/heads/main`（HTTP 200）。ローカル: `_src/dbos-transact-py/`

#### 公式ドキュメントの逐語引用（保証）

URL: `https://docs.dbos.dev/python/tutorials/workflow-tutorial`（HTTP 200、ローカル保存: `_src/dbos_doc_docs.dbos.dev_python_tutorials_workflow-tutorial.html`）

> "Steps are tried at least once but are never re-executed after they complete."（13語）

> "Transactions commit exactly once."（5語。DBの原子的トランザクションに限っては exactly-once、一般のstepは at-least-once と明示的に区別している）

#### 実装: ステップ結果のチェックポイントと再実行時の再利用

**file:line**: `_src/dbos-transact-py/dbos/_core.py:2297-2328`（`check_existing_result`）
```python
2297:     def check_existing_result() -> Union[NoResult, R]:
2298:         ctx = assert_current_dbos_context()
2299:         recorded_output = dbos._sys_db.check_operation_execution(
2300:             ctx.workflow_id, ctx.function_id, step_name
2301:         )
2302:         if recorded_output:
2303:             dbos.logger.debug(
2304:                 f"Replaying step, id: {ctx.function_id}, name: {attributes['name']}"
2305:             )
2306:             if recorded_output["error"] is not None:
2307:                 ...raise deserialized_error
2308:             elif recorded_output["output"] is not None:
2309:                 return cast(R, deserialize_value(...))
```
既存の記録があれば **`func()` を再実行せずに保存済みの出力/エラーをそのまま返す/送出する**。記録の書き込みは同ファイル `_core.py:2265-2295`（`record_step_result`）:
```python
2277:         try:
2278:             output = func()
...
2289:             dbos._sys_db.record_operation_result(step_output)
...
2294:         dbos._sys_db.record_operation_result(step_output)
```

**永続化先の実装**: `_src/dbos-transact-py/dbos/_sys_db.py:3016-3035`（`record_operation_result`）が `operation_outputs` テーブルへINSERTする。

#### 仕事と成果を置くストアの形（機械可読スキーマ）

**file:line**: `_src/dbos-transact-py/dbos/_schemas/system_database.py:100-118`
```python
100:     operation_outputs = Table(
101:         "operation_outputs",
102:         metadata_obj,
103:         Column("workflow_uuid", Text, nullable=False),
104:         Column("function_id", Integer, nullable=False),
105:         Column("function_name", Text, nullable=False),
106:         Column("output", Text, nullable=True),
107:         Column("error", Text, nullable=True),
108:         Column("child_workflow_id", Text, nullable=True),
109:         Column("started_at_epoch_ms", BigInteger, nullable=True),
110:         Column("completed_at_epoch_ms", BigInteger, nullable=True),
111:         Column("serialization", Text()),
...
117:         PrimaryKeyConstraint("workflow_uuid", "function_id"),
118:     )
```
SQLAlchemy `Table` として機械可読に定義。`PrimaryKeyConstraint("workflow_uuid", "function_id")` が **1ワークフロー内のステップ番号ごとに1行**という制約をDBレベルで強制している（同じキーでの二重INSERTは制約違反になる＝この制約自体が「記録は一度きり」を担保する不変量）。対応するPython側の型: `_src/dbos-transact-py/dbos/_sys_db.py:306-313`（`OperationResultInternal` TypedDict）。

#### 保証の限界（コードからの推論）

ドキュメントは "Steps are tried at least once" と明言しており、exactly-onceではなくat-least-onceが公式な保証。コード上も、`func()`の実行（2278行目）と`record_operation_result`の呼び出し（2294行目）の間にプロセスクラッシュが起きた場合、その間に発生した外部副作用（例: HTTPコールが実際に飛んだ）は記録されないため、再起動後に`check_existing_result`が記録なしと判断し**同じstepを再実行する＝外部副作用が二重に起きうる**。これはドキュメントの明示的記述ではなく、コード構造（record前にクラッシュし得るtry/exceptの外側にrecordがある構造）からの直接的推論。公式ドキュメントに「二重実行の可能性」を明言する専用ページは発見できなかった（試したURL: `https://docs.dbos.dev/python/tutorials/idempotency-tutorial` → 404）。

---

### 4-C. Restate

**取得**: `codeload.github.com/restatedev/restate/tar.gz/refs/heads/main`（HTTP 200）。ローカル: `_src/restate/`（サーバー本体のRustリポジトリ。SDK別リポジトリは未取得）

#### journaling と決定性強制

**file:line**: `_src/restate/crates/invoker-impl/src/error.rs:385-397`
```rust
385: impl fmt::Display for SdkInvocationError {
386:     fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
387:         if self.error.code() == codes::JOURNAL_MISMATCH {
388:             writeln!(
389:                 f,
390:                 "Detected journal mismatch. Either some code within the handler is non-deterministic, or the code was updated without registering a new service deployment."
391:             )?;
```
エラーコード定義: `_src/restate/crates/types/src/errors.rs:104`
```rust
104:         JOURNAL_MISMATCH 570 "Journal mismatch",
```

**強制のタイミング**: SDK側（ハンドラを動かす言語ランタイム）がジャーナルを再生し、そこで生じた不一致を `JOURNAL_MISMATCH` としてサーバーに報告する形（**実行時検出**）。本リポジトリ（restate本体）はこのエラーを受け取って処理する側であり、実際の「再生して比較する」ロジック自体は言語別SDKリポジトリ（`restatedev/sdk-typescript` 等、未取得）にある。この点は本リポジトリのコードからは file:line で直接示せないため、ここでは「サーバー側が何が起きたかをどう扱うか」のみを一次資料として確定する。

**検出後の挙動**: `_src/restate/crates/invoker-impl/src/error.rs:282-291`
```rust
282: 	pub(crate) fn requested_error_behavior(&self) -> RequestedErrorBehavior {
283: 		match self {
...
288: 			InvokerError::Sdk(SdkInvocationError {
289: 				next_retry_interval_override,
290: 				..
291: 			}) => RequestedErrorBehavior::retry(*next_retry_interval_override),
```
`JOURNAL_MISMATCH` を含むSDKエラーはデフォルトで **retry**（設定済みリトライポリシーに従い再試行）として扱われる。Temporalの `BlockWorkflow` と同型（＝黙って先へ進ませず、実行を止めてリトライへ回す）。

#### 仕事と成果を置くストアの形（journal）

**file:line**: `_src/restate/crates/partition-store/src/journal_table_v2/mod.rs:21-31`
```rust
21:     JournalEntryIndex, NotificationEntryIndex, ReadJournalTable, ScanJournalTable,
22:     ScanJournalTableRange, StoredEntry, WriteJournalTable,
...
31: use restate_types::storage::{StoredRawEntry, StoredRawEntryHeader};
```
`JournalEntryId` でキーされた `StoredEntry`/`StoredRawEntry` として各invocationのジャーナルが永続化される（`WriteJournalTable`/`ReadJournalTable` トレイト）。

#### event streamの形（有限enum）

**file:line**: `_src/restate/crates/types/src/journal_v2/command.rs:40-71`
```rust
40: #[enum_dispatch(EntryMetadata, CommandMetadata)]
41: #[derive(Debug, Clone, PartialEq, Eq, strum::EnumDiscriminants, Serialize, Deserialize)]
42: #[strum_discriminants(vis(pub))]
43: #[strum_discriminants(name(CommandType))]
...
50: pub enum Command {
51:     Input(InputCommand),
52:     Output(OutputCommand),
53:     GetLazyState(GetLazyStateCommand),
...
70:     CompleteAwakeable(CompleteAwakeableCommand),
71: }
```
20種の variant を持つ有限enum `Command`（判別子 `CommandType` は `strum::EnumDiscriminants` により自動導出）。`EntryType`（`_src/restate/crates/types/src/journal_v2/mod.rs:60-63`）は `Command`/`Notification` の2系統からなる。

#### 異種の実行主体（言語非依存性）

**file:line**: `_src/restate/service-protocol/dev/restate/service/protocol.proto:9-15`
```protobuf
9:  syntax = "proto3";
10:
11: package dev.restate.service.protocol;
12:
13: option java_package = "dev.restate.generated.service.protocol";
14: option go_package = "restate.dev/sdk-go/pb/service/protocol";
```
サービス間のワイヤプロトコルがprotobuf(proto3)で規定されており、`java_package`/`go_package` オプションが明示されている＝Go・Java双方のSDKが同一プロトコル定義から生成される、言語非依存の設計。

---

## 未発見・積み残し

1. **van der Aalst "The Application of Petri Nets to Workflow Management" (JCSC 1998)原文PDF** — 無償入手先を発見できず。試した検索: `van der Aalst "The Application of Petri Nets to Workflow Management" 1998 filetype:pdf`（結果は全て引用元論文のみ、原文なし）。代替として同著者の "Workflow Verification: Finding Control-Flow Errors Using Petri-Net-Based Techniques"（vdaalst.com公式ミラー、HTTP 200）を一次資料として使用（課題の「または」条件を満たす）。
2. **Restate SDK側の実際のジャーナル再生・決定性比較コード** — `restatedev/restate`本体はサーバー側でエラーコードを受信・処理するのみで、実際に「再生して前回のジャーナルと突き合わせる」ロジックは言語別SDKリポジトリ（例: `restatedev/sdk-typescript`）にある可能性が高い。時間の制約上、本調査ではclone・確認していない。file:lineでの直接証拠なし。
3. **DBOSの「ステップ内副作用が二重に起きうる」ことを明言する公式ドキュメント文言** — 専用ページ（`idempotency-tutorial`）はHTTP 404。`workflow-tutorial`ページの "at least once" 記述から論理的に導かれる限界であり、コード構造（`_core.py:2277-2295`）からも裏付けられるが、"twice"/"duplicate side effect" を明言する一次資料の文は発見できず。
4. **YAWLまたはWoPeDの完全な動的soundness（生存性）検査コード** — 本YAWLリポジトリのコアengineには存在しないと判定（`grep -rn "soundness|Woflan"` 共にゼロ件）。WoPeD側は未clone（時間都合、YAWLで十分な反証・実証が得られたため）。

## 取得物一覧（ローカルパス）

- `_src/vdaalst_p98.pdf`（HTTP 200）
- `_src/vdaalst_p559.pdf`（HTTP 200、未使用）
- `_src/omg-bpmn-2.0.pdf`（HTTP 200、538ページ）
- `_src/yawl/`（tarball展開、YAWL Foundation main branch相当）
- `_src/sdk-go/`（tarball展開、temporalio/sdk-go main branch）
- `_src/api/`（tarball展開、temporalio/api master branch）
- `_src/dbos-transact-py/`（tarball展開、dbos-inc/dbos-transact-py main branch）
- `_src/restate/`（tarball展開、restatedev/restate main branch）
- `_src/dbos_doc_docs.dbos.dev_python_tutorials_workflow-tutorial.html`（HTTP 200）
- `_src/dbos_doc_docs.dbos.dev_python_tutorials_step-tutorial.html`（HTTP 200）
