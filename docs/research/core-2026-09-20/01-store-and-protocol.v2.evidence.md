# 作業メモ (検証済み事実の蓄積。最終成果物は 01-store-and-protocol.md)

## KPN / dataflow

### 抽象
Kahn 1974 "The Semantics of a Simple Language for Parallel Programming", IFIP Congress 1974, pp.471-475.
取得: https://www.cs.princeton.edu/courses/archive/fall07/cos595/kahn74.pdf (HTTP 200)

- ブロッキング read のみ: 逐語 "The process stays blocked on a wait until something is being sent on this line" (p.471, §1)
- send は待たされない: 逐語 "nothing can prevent a process from performing a send on a line" (p.471, §1)
- 到着検査の禁止: 逐語 "cannot be waiting on data coming from one or another of its input lines" (p.472, §2, Remarks)
- 局は入力履歴から出力履歴への関数: 逐語 "a function from the histories of its input lines into the histories of its output lines" (p.472, §2.2.1)
- 決定性の主張: 逐語 "it can produce only determinate programs" (p.475, §6)

### 不変量
入力ストリーム列 → 出力ストリーム列 の写像が単一値であり、スケジューリングに依存しない。
Kleene の最小不動点 (Property 1) と Scott の連続性 (Property 2, p.474 §3) により最小解が一意。
実行順序が変わって得られるのは「出力が少ない (未完)」だけで内容は変わらない (p.474, §4)。

### 実装と強制箇所 — 本体で直接検証済み
icyphy/ptII@5dc2aa15edd05efb9d097f1353edb04a21e2358a

`ptolemy/domains/pn/kernel/PNQueueReceiver.java:241-243` — 本体が raw.githubusercontent.com から取得して目視確認:

    @Override
    public boolean hasToken() {
        return true;
    }

同 `:250-253` の `hasToken(int)` も無条件 true。
javadoc (`:236-239`) の逐語: "Return true, since a call to the get() method of the receiver will always return a token if the call to get() ever returns."

これが Kahn の制約を**コードで強制**している形: アクターから「今データがあるか」を問う手段が存在しないため、
到着検査による分岐 (= 非決定性の導入) が書けない。実際のキュー状態は `get()` 内部の `super.hasToken()` (`:169`)
でしか参照されず、空なら `_director.wait()` でブロックする。本体で `:160-180` を目視確認済み。

対照: `ptolemy/domains/sdf/kernel/SDFReceiver.java:253-255` の `hasToken()` は `!_queue.isEmpty()` を返す
(SDF はスケジュール済み実行モデルなので強制の形が違う)。→ **未検証 (エージェント報告)**

非決定を入れたい場合は専用アクター `NondeterministicMerge` を使う必要があり、専用の
`MergeDirector extends PNDirector` まで用意されている (`NondeterministicMerge.java:403-405`)。
= 通常の PNDirector/PNQueueReceiver では非決定が表現不能であることの裏付け。→ **未検証 (エージェント報告)**

SDF のレート不整合検出: `ptolemy/domains/sdf/kernel/SDFScheduler.java:1390-1398, :1417-1425` で
`NotSchedulableException(... "No solution exists for the balance equations.")` を送出。→ **未検証 (エージェント報告)**
SDFDirector `prefire()` (`:723,731`) が宣言レート分のトークンが無ければ発火を拒否。→ **未検証 (エージェント報告)**

### 強制されていないこと / 未発見
- 能力の宣言: PN/SDF カーネルに該当機構なし。`grep -rli "capability" --include="*.java"` で 48 ファイル一致するが
  すべて FMI コシミュレーション等の別モジュール。**未発見**
- メッセージ種別の分類: Kahn が持つのはチャネル毎の要素型 D_e (§2.2.3) のみ。種別を分類する仕組みではない。**未発見**
- 実行の中断と再開: Kahn 論文に該当語彙なし。Ptolemy の `Manager.pause()/resume()` はモデル全体の一括停止で
  プロセス単位の意味論ではない。`ProcessDirector`/`ProcessThread` に public な pause/resume は 0 件。**未発見**

### 物差し当て (本体の判断)
- D1 2 者間: 無関係。KPN はプロセス網であり、コアと実行器という非対称の 2 者を持たない。
- D2 発信の閉鎖: **満たす**。プロセスは宣言されたチャネルへ send する以外の発話手段を持たない。
- D3 仕事と成果が同じプロトコル: 満たす (どちらもチャネル上のトークン列)。ただし仕事と成果の区別自体が無い。
- D4 種別の決定論的分類: **満たさない**。チャネル毎の型 D_e はあるが、成果の種別を分類する仕組みではない。
- D5 コンテキストの絞り込み: 満たす。プロセスは自分の入力線しか見ない。
- D6 取れる state の宣言: **満たさない**。中断・再開の概念が無い。
- D7 event stream: **満たさない**。出力は出力線のトークンのみ。途中の出来事を外へ出す仕組みが無い。

---

## A2A (Agent2Agent) — 本体で直接検証済み

正本: a2aproject/A2A@afda8316c64951a2ecb2a0d3d10867405d2b4095 `specification/a2a.proto` (812 行)
プロトコルバージョン: 1.0 (CHANGELOG の最新は 1.0.1, 2026-05-26)。
仕様は Protocol Buffer ファーストへ移行済みで、JSON Schema はビルド生成物。→ **エージェント報告、本体は proto の存在を確認**

### 本体が目視確認した事実

**Message と Artifact は別型 (D3 に直結)**
`a2a.proto:260-277` `message Message` — フィールド: message_id, context_id, task_id, **role**, parts, metadata, extensions, **reference_task_ids**
`a2a.proto:280-293` `message Artifact` — フィールド: artifact_id, **name**, **description**, parts, metadata, extensions
Artifact に role も reference_task_ids も無く、Message に name/description が無い。フィールド構成が異なる独立した型。
逐語 (`a2a.proto:279`): "Artifacts represent task outputs."
→ **仕事の投入と成果の返却は同じプロトコルメッセージ型ではない。**

**StreamResponse は 4 種の oneof (D7 に直結)**
`a2a.proto:791-803`:
    oneof payload {
      Task task = 1;
      Message message = 2;
      TaskStatusUpdateEvent status_update = 3;
      TaskArtifactUpdateEvent artifact_update = 4;
    }
→ SSE で外へ出るのは「タスクの状態遷移」と「成果物の増分」のみ。
  **呼んだツールとその結果、出した判断を表す event 型が存在しない。**

**費用・到達資源の宣言フィールドは無い (契約「能力の宣言」に直結)**
`grep -n -i -E 'cost|price|pricing|budget|quota'` を proto 全文 (812 行) に実行 → **0 件**。本体で確認。
AgentCard のフィールド一覧 (`a2a.proto:362-399`) は name, description, supported_interfaces, provider, version,
documentation_url, capabilities, security_schemes, security_requirements, default_input_modes,
default_output_modes, skills, signatures, icon_url。→ **エージェント報告 (本体は grep で費用不在のみ確認)**
security_schemes は「このエージェント自身を呼ぶための認証」であって「エージェントが到達できる資源」ではない。

**TaskState は 9 値の閉じた enum (D4 / D6 に直結)**
`a2a.proto:187-208`: UNSPECIFIED, SUBMITTED, WORKING, COMPLETED, FAILED, CANCELED,
INPUT_REQUIRED, REJECTED, AUTH_REQUIRED。本体で全文目視確認。
注目: INPUT_REQUIRED と AUTH_REQUIRED の comment は逐語 "This is an interrupted state."
→ 中断状態が型の上で表現されている。ただしこれは**タスクの状態**であって、
  要件が言う「実行器が取れる state の宣言」(能力の宣言の一項目) ではない。

### 実行時強制 → **未検証 (エージェント報告)**
a2a-python@9a00f9b `src/a2a/server/routes/jsonrpc_dispatcher.py:284-292` が
`ParseDict(params, model_class())` で protobuf 型へパースし、失敗を `InvalidParamsError` (-32602) に変換。
REST 経路は `rest_dispatcher.py:166,189,301` の `Parse(body, params)`。

### 落としているもの
- 費用・到達資源の宣言 (型付きフィールドが無い)
- 実行中の内部の出来事 (ツール呼び出し・判断) の event 化
- 仕事と成果の型の同一性
- metadata はすべて `google.protobuf.Struct` = 任意 JSON で型的強制なし

---

## MCP (Model Context Protocol) — 本体で一部検証済み

spec: modelcontextprotocol/modelcontextprotocol@24efd6e7cbd7a074e6b3b781eb370891df40afad
**現行仕様バージョン: 2026-07-28**。本体が GitHub API で `schema/` 配下を列挙して確認:
2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28, draft。

### エージェント報告 (本体未検証)
- 呼び出し方向: `schema/2026-07-28/schema.ts:1875` 逐語 "Used by the client to invoke a tool provided by the server."
  → MCP は「モデル側が道具を選んで呼ぶ」プロトコル。A2A の Task のような能動的ライフサイクル객체はコアに無い。
- `Tool` 型 (`schema.ts:1973-2015`): name, title, description, inputSchema (必須, JSON Schema 2020-12),
  outputSchema (任意), annotations, _meta。費用フィールド無し。
- `ToolAnnotations`: readOnlyHint, destructiveHint, idempotentHint, openWorldHint — いずれも「ヒント」で保証ではない。
- sampling/createMessage は 2026-07-28 で非推奨化 (`schema.ts:2179`, SEP-2577)。elicitation/create は現役 (`schema.ts:2849`)。
- logging capability も 2026-07-28 で deprecated (`schema.ts:808`)。
- typescript-sdk@6032170 `packages/core/src/constants.ts:1` の `LATEST_PROTOCOL_VERSION = '2025-11-25'` は
  スキーマ最新より 1 世代古く、内部コーデック `packages/core-internal/src/wire/codec.ts:73` は
  `MODERN_WIRE_REVISION = '2026-07-28'` を持つ。
- 実行時検証: `packages/core-internal/src/shared/protocol.ts:1554-1560` (レスポンス),
  `:1744-1746` (リクエスト params)。失敗時に InvalidResult / InvalidParams を投げる。
- `tasks` は `ServerCapabilities.extensions` の拡張 (`schema.ts:873-880`) でありコア仕様ではない。

---

## actor model

### 抽象
Hewitt, Bishop, Steiger, "A Universal Modular ACTOR Formalism for Artificial Intelligence", IJCAI-73, pp.235-245
取得: https://www.ijcai.org/Proceedings/73/Papers/027B.pdf (HTTP 200) → **エージェント報告**

- 逐語 (p.235): 全ての振る舞いは "one kind of behavior: sending messages to actors" に還元される。
- EVENT を四つ組 [C T M N] (継続・宛先・メッセージ・新規生成 actor) と定義。
  HISTORY は EVENT 集合上の**強い半順序** (precedes 関係)。
  **原文は「二つの任意の event が → で関係づけられることを要求しない」と明記 (p.240)。**
  → **actor model 自体はメッセージ到達順序を保証しない。**
- p.240 のメッセージ送信 5 性質: universal control primitive、port 等の仲介を介さず直接対話、
  副作用なし、返信を前提としない単方向、environment/instruction pointer モデルではない。
- p.238 "Global state considered harmful." は**意味論記述**への批判であり、実装の共有変数禁止ではない。
  p.239 の可変 `cell` actor、p.241 "Data bases are actors ..." のとおり、
  複数 actor が同じ cell 参照を共有すれば message send 経由の共有可変状態になる。形式体系はこれを禁じていない。

Agha 1986 は**取得失敗**。dspace.mit.edu の bitstream は HTTP 405 + AWS WAF の CAPTCHA、
osti.gov は curl exit 56、deepblue.lib.umich.edu は HTTP 403。CAPTCHA 回避はしていない。
→ Agha の定式化における順序保証・fairness の扱いは**未確認**。

### 実装と強制箇所 — 本体で直接検証済み
akka/akka@e2441c7ae1b0e500ac30a121863cc7e54d919a79
`akka-actor-typed/src/main/scala/akka/actor/typed/ActorRef.scala` (135 行) を本体が取得して目視確認:

    :25  trait ActorRef[-T] extends RecipientRef[T] with java.lang.Comparable[ActorRef[_]] ...
    :26    this: InternalRecipientRef[T] =>
    :32    def tell(msg: T): Unit
    :37    def narrow[U <: T]: ActorRef[U]
    :45    def unsafeUpcast[U >: T @uncheckedVariance]: ActorRef[U]

→ **型による強制は本物**。反変 `-T` により、`ActorRef[Super]` を `ActorRef[Sub]` の位置で使えず、
  `tell` に T 以外を渡すとコンパイルエラーになる。
→ **ただし脱出口がある**。`:45` の `unsafeUpcast` は javadoc 逐語で
  "it may cause a [[ClassCastException]] when you send a message" と自認している。
  つまり型の強制は**回避可能**であり、要件の「発話の閉鎖」を絶対的には保証しない。
→ 配送の保証について javadoc `:20` 逐語: "(i.e. this delivery is not reliable)"。

以下は**未検証 (エージェント報告)**:
- `Behavior.scala:42-43` の `Behavior[T]` は分散注釈が無く不変。`:56` の `narrow` は
  `asInstanceOf` による無検査キャストで実装され、コンパイラ検査ではない。
- `@DoNotInherit` は Scala コンパイラの制約ではなく MiMa (バイナリ互換性チェッカ) 用の注釈
  (`akka-actor/src/main/java/akka/annotation/DoNotInherit.java:25` の `@Retention(RetentionPolicy.CLASS)`)。
  外部実装を実際に阻んでいるのは self-type 注釈 `this: InternalRecipientRef[T] =>`。

### Erlang — **未検証 (エージェント報告)**
https://www.erlang.org/doc/system/ref_man_processes.html#delivery-of-signals (v29.1)
同一送信元から同一宛先への signal は送信順を保って到達する。**型ではなく BEAM ランタイムの実行時保証**。
Erlang は動的型付けで `pid` に任意の term を送れるため `ActorRef[T]` 相当の型付きチャネルは無い。
順序保証は sender-destination のペア単位に限定され、複数プロセスからなる「service」からの順序は保存されない。

### Orleans — **未検証 (エージェント報告)**
dotnet/orleans@0bfd95e8561699b3bb7c619b0b0d2378d84395bc
- `src/Orleans.Core.Abstractions/Core/IGrainFactory.cs:56` の
  `GetGrain<TGrainInterface>(...) where TGrainInterface : IGrainWithGuidKey`
- `src/Orleans.Analyzers/GrainInterfaceMethodReturnTypeDiagnosticAnalyzer.cs:14-31`
  ORLEANS0009 / DiagnosticSeverity.Error。**C# の型システムではなく Roslyn アナライザによる強制**。
- `src/Orleans.Runtime/Scheduler/WorkItemGroup.cs:19-24, :87-118, :156-171, :206-216`
  activation ごと 1 キュー + 状態機械 (Waiting/Runnable/Running) で単一スレッド実行を強制。
  ただし `[Reentrant]`/`[AlwaysInterleave]`/`[MayInterleave]` でオプトアウト可能。
- `src/Orleans.Core.Abstractions/Concurrency/GrainAttributeConcurrency.cs:42-53` の
  `UnorderedAttribute` は `[Obsolete("Message ordering is not guaranteed regardless of whether this attribute is used.")]`
  → **Orleans は順序を保証しないと明文化している**。
- 中断・再開を一級の概念として持つのは 4 システム中 Orleans のみ。
  `IGrainBase.cs:25 OnActivateAsync`, `:33 OnDeactivateAsync`, `DeactivateOnIdle`, `MigrateOnIdle`。

### 物差し当て (本体の判断)
- D1 2 者間: 無関係。actor 網は N 者ピア。
- D2 発信の閉鎖: **一部**。Akka Typed は型で送れるメッセージを絞るが `unsafeUpcast` で回避可能。
  Hewitt の形式体系は「message send のみ」という意味では閉じているが、宛先も内容も自由。
- D3 仕事と成果が同じプロトコル: 満たさない。返信は単方向送信の連鎖で、仕事/成果の型的区別が無い。
- D4 種別の決定論的分類: **満たさない**。Hewitt の `(=> pattern body)` / `(cases ...)` は
  網羅性検査の無い開いたディスパッチ (p.239)。Akka も `T` に sealed trait を要求せず網羅性検査は強制されない。
- D5 コンテキストの絞り込み: 満たす。actor は受け取ったメッセージしか見ない。
- D6 取れる state の宣言: **Orleans のみ一部**。actor model 自体には無い。
- D7 event stream: **満たさない**。どの実装にも「実行中の出来事を同形式で外へ出す」機構が無い。

---

## multiparty session types (MPST)

### 抽象 — **エージェント報告**
Honda, Yoshida, Carbone "Multiparty Asynchronous Session Types"
POPL'08 取得: http://www.doc.ic.ac.uk/~yoshida/multiparty/multiparty.pdf (HTTP 200)
JACM full version 取得: http://mrg.doc.ic.ac.uk/publications/multiparty-asynchronous-session-types-jacm/jacm.pdf (HTTP 200)
(mrg.doc.ic.ac.uk は https で SNI 証明書不一致のため http でアクセス)

- 逐語 (JACM p.0:1, abstract):
  "communication safety, progress and session fidelity are established for general n-party asynchronous interactions"
- Projection (Definition 4.1, JACM p.0:22): global type を各参加者の local type へ射影する 3 分岐の定義。
- Coherence (Definition 4.2, JACM p.0:22-23): "G is coherent if it is linear and G↾p is well-defined for each p∈pid(G)"
  Theorem 4.3: "Coherence of G is decidable" (JACM p.0:23)。→ **プロトコルの整合性が決定可能**。
- Linearity (Definition 3.12, JACM p.0:19): 同一チャネルへの 2 アクションは input/output 両方の依存を持つ。メッセージ順序保存を保証。

**2 者間と N 者間の境界 (要件が「コアと実行器の 2 者間」なので判断材料として重要)**
論文自身が binary session types の限界を説明している:
- 2 者で足りる理由 (JACM p.0:4): "When composing two parties, we only have to check they have mutually dual types"
- 3 者以上で破綻する理由 (JACM p.0:4, 逐語): "This framework based on duality is no longer effective in multiparty communication"
- 3 セッションに分解すると (JACM p.0:4): "our type abstraction loses essential sequencing information"
→ **要件の「コアと実行器の 2 者間」に限れば binary session types (duality 検査) で足り、
  global type / projection / coherence という MPST の追加装置は要らない。**

**静的な参加者集合 (A2 に直結)**
JACM p.0:42 逐語: "Our session types use a static participant information in the syntax and types"
セッション開始プリミティブ `a[2..n](s̃).P` が参加者数 n を宣言時に固定。動的な参加者追加は
"valuable further study" として未解決課題に留めている (JACM p.0:42)。

**point-to-point 前提 (共有ストアではない)**
型構文 `p → p′ : k⟨U⟩.G′` は常に厳密に 2 参加者間の相互作用を表す。
JACM p.0:7 逐語: "each session name is mapped to a pair of freshly generated IP and a port name"
JACM p.0:11 逐語: "each channel is used exactly by one sender"
マルチキャストは §6.1 で「2 者間送信の展開マクロ」として後付けされる拡張。

### 実装と強制箇所 — 本体で直接検証済み
scribble/scribble-java@723660a81ee40a094163d9c63a93778cbc97af6e

`scribble-runtime/src/main/java/org/scribble/runtime/statechans/LinearSocket.java:42-49` を本体が取得して目視確認:

    protected void use() throws ScribRuntimeException
    {
        if (this.used)
        {
            throw new ScribRuntimeException("Linear socket resource already used: " + this.getClass());
        }
        this.used = true;
    }

→ **同一状態オブジェクトの再利用を実行時例外で拒否している**。linearity の実行時強制。

以下は**未検証 (エージェント報告)**:
- `StateChannelApiGenerator.java:116-137, :162-195` が EFSM の各状態ごとに別クラスを生成し、
  状態種別 (OUTPUT / ACCEPT / UNARY_RECEIVE / POLY_RECIEVE) に応じて生成器を切り替える。
  → **送信しか許されない状態のクラスには send メソッドしか存在しない**。
- `OutputSockGen.java:64-92` が `curr.getDetActions()` (その状態で許可されたアクションのみ) をループして
  send メソッドを生成し、`:92, :136` で戻り値型を後続状態専用クラスにする。
  → 呼び出し後は古い型に戻れず、後続状態にしか存在しないメソッドしか呼べない。
- nuscr/nuscr@9a9631a `lib/mpst/ltype.ml:431-635` の `project'` が Definition 4.1 の実装。
  `merge` (266-377) の `:374` が一致しなければ `Unmergable` を投げ `:375-377` で `UnableToMerge` に変換。

### 強制されていないこと
- 実行の中断・再開: プロセス構文に suspend/resume 相当のプリミティブが無い。全文検索 0 件。
- 能力宣言: "capabilit-" は 12 件ヒットするがすべて delegation (セッション参加権限の委譲) の文脈で、
  アクセス制御/権限宣言の概念ではない。
- メッセージ本文の内容分類: Sort 文法は `S ::= bool | nat | ... | ⟨G⟩` で基底型と委譲型のみ。
  → **型は「量」を保証するが「意味」は保証しない。**

取得失敗: Honda 1993 "Types for Dyadic Interaction" (CONCUR'93) と
Honda-Vasconcelos-Kubo 1998 (ESOP'98) はいずれも Springer のペイウォール (303 → idp.springer.com/authorize)、
researchgate 403、citeseerx 接続不可 (HTTP 000) で本文取得できず。
→ binary session types の性質は POPL08/JACM 論文自身の記述で代替した。原典ではない。

### 物差し当て (本体の判断)
- D1 2 者間: **満たす** (binary session types なら)。MPST は N 者だが 2 者に退化できる。
  ただし**参加者集合が静的**なので、実行器を動的に足す形では A2 に届かない。
- D2 発信の閉鎖: **満たす (最も強い形で)**。状態ごとに別クラスを生成し、その状態で許されたメソッドしか存在しない。
  Akka の `unsafeUpcast` のような脱出口が API の設計上存在しない。
- D3 仕事と成果が同じプロトコル: 満たす。どちらも同じセッション上のメッセージ。
- D4 種別の決定論的分類: **一部**。ラベル付き分岐 (branching) は有限集合だが、
  ペイロードの中身の分類はしない。
- D5 コンテキストの絞り込み: 満たす。各参加者は自分の local type の範囲しか見ない。
- D6 取れる state の宣言: **満たさない**。中断・再開の概念が無い。
- D7 event stream: **満たさない**。

---

## durable execution (Temporal / DBOS / Restate)

### Temporal — 決定論の強制
temporalio/sdk-python@eb642b14947bd8bcdf8816cffb6a63869803f5c6
temporalio/api@1c27468c756fc8abc800235c33b74c6eba638c88
temporalio/sdk-core@0eb03f213079e539c18fb738c32a70bc191aadf4

**本体で直接検証済み — Event History の enum**
`temporal/api/enums/v1/event_type.proto` を取得し、
`grep -c -E '^\s+EVENT_TYPE_[A-Z_]+ = [0-9]+;'` → **61**。
先頭 6 値を目視: EVENT_TYPE_UNSPECIFIED=0, WORKFLOW_EXECUTION_STARTED=1, WORKFLOW_EXECUTION_COMPLETED=2,
WORKFLOW_EXECUTION_FAILED=3, WORKFLOW_EXECUTION_TIMED_OUT=4, WORKFLOW_TASK_SCHEDULED=5。
→ **有限 (61 値) の閉じた集合で、機械的に分類可能。**
→ ただし値はすべて「システムが起こした出来事の種別」(スケジュールされた/開始した/完了した/失敗した)。
  **業務上の成果の種別 (承認された/却下された等) を表す語彙は 1 つも無い。**
  要件 A12 が求めるのは後者であり、Temporal の EventType はそこを埋めない。

以下は**未検証 (エージェント報告)**:
- 決定論違反の検出本体は Rust 側。`sdk-core/src/worker/workflow/mod.rs:1707-1709` の
  `#[error("[TMPRL1100] Nondeterminism error: {0}")] Nondeterminism(String)`。
  実際の不一致検出は `machines/workflow_machines.rs:969` の逐語 "No command scheduled for event {event}"、
  同ファイル 249, 371, 904, 1534, 1570, 1698, 1796 行にも複数。
- Python 側は `temporalio/worker/_replayer.py:224-230` が core の eviction 理由 NONDETERMINISM を
  `NondeterminismError` (`temporalio/workflow/_exceptions.py:17-23`) に変換。
- `workflow_sandbox/_restrictions.py:95-168, 605-788` が random / time / uuid / os / socket / subprocess /
  threading / datetime を制限し、`_importer.py:92,279` と `_restrictions.py:856` で
  `RestrictedWorkflowAccessError` を raise。
  **ただし sandbox は既知のブラックリスト方式で抜け穴が自認されており** (`:734-736` の
  `# TODO(cretz): Can't currently restrict anything on sys`)、`with_passthrough_all_modules()` で無効化可能。
  → **真の強制源は replay 比較の方**。sandbox は早期にエラーを出す補助レイヤー。
- workflow/activity の分離: `_definition.py:41` の `sandboxed: bool = True` (workflow のデフォルト) に対し、
  `temporalio/worker/_activity.py` に "sandbox" の出現数は **0**。
  → 「activity は任意の非決定的コードでよい / workflow は決定的でなければならない」が構造で強制されている。

### DBOS — **未検証 (エージェント報告)**
dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59
`dbos/_datasource.py:754-780` の `_body()` で、ユーザーの SQL (`func(*args, **kwargs)`) と
チェックポイント書き込み (`_record_result`) が同じ `session` (= 同じ DB トランザクション) 内にあり、
`session.begin()` ブロック終了時に両方同時に commit/rollback される。
→ 「同一トランザクションで書かれるか」の答えは **Yes**。
査読論文: Stonebraker, Zhou, Kraft, Li "Consistency and Correctness in Data-Oriented Workflow Systems",
CIDR 2026, https://www.vldb.org/cidrdb/papers/2026/p9-stonebraker.pdf
逐語 (p.6-7): "both the workflow log entry and the application database modifications commit atomically"

### Restate — **未検証 (エージェント報告)**
restatedev/restate@d5425f5bfae4024f4d26bab447bc8e6c6db08bfa
restatedev/sdk-shared-core@bcdf52777955b36bed611483abd227db03b9a09c
`crates/types/src/journal_v2/mod.rs:60-63,84-105` の `CommandType` は 20 種の閉じた集合。
`sdk-shared-core/src/vm/errors.rs:71` の `JOURNAL_MISMATCH: InvocationErrorCode = InvocationErrorCode(570)`。
`:180-215` の `CommandTypeMismatchError` 逐語:
"Found a mismatch between the code paths taken during the previous execution"
送出は `src/vm/transitions/journal.rs:465, 631, 988`。
→ Temporal と違い、比較対象は「workflow 全体の再実行結果」ではなく「個々の durable call 1 件ごと」の
  型・パラメータ一致。粒度がより局所的。
Restate 単体の査読論文は**未発見** (検索語: `"Restate" durable execution paper`,
`"Restate" journal invocation VLDB CIDR arxiv`)。

### 強制されていないこと (3 システム共通)
- 異種の実行主体の能力宣言: 見当たらない。Temporal の `NamespaceCapabilities`
  (`sdk-core/src/worker/mod.rs:465-528`) は namespace 単位のサーバ機能フラグで、実行主体の能力宣言ではない。
- メッセージ種別の**意味的**分類: EventType (61) も CommandType (20) も操作の種別であって成果の種別ではない。
- 実行主体の平等性: Temporal の `build_id` は非空チェックのみ (`sdk-core/src/worker/mod.rs:410-421`)。
  同一 task queue を共有する worker が同一コードを実行しているかの検証機構は無い。
  ズレの**事後的な**検出手段が決定論チェックであり、事前の平等性保証は存在しない。

### 物差し当て (本体の判断)
- D1 2 者間: **満たす**。Temporal は「サーバ ↔ worker」の 2 者間プロトコル。worker を足してもプロトコルは変わらない。
- D2 発信の閉鎖: **満たす**。worker がサーバへ返せるのは有限種の command のみ。
- D3 仕事と成果が同じプロトコル: 満たさない。task の投入と結果は別の型。
- D4 種別の決定論的分類: **満たさない**。enum は有限だが「システムの出来事」であって「成果の種別」ではない。
- D5 コンテキストの絞り込み: 満たす。activity は引数しか受け取らない。
- D6 取れる state の宣言: **最も近い**。中断後の再開が checkpoint/journal として一級で扱われる。
  ただし「実行器が自分の再開可否を宣言する」形ではなく、システムが一律に決める。
- D7 event stream: **最も近い**。有限種の event が起きた順に永続化され、外から読める。
  ただし event は「システムが起こした出来事」に限られ、実行器内部の判断は入らない。

---

## 追記ログ / state machine replication
### (起点リスト外。加えた理由: 要件の「共通の input/output ストア」と「ログストア」は
###  形の上で順序つき追記ログそのものであり、この系譜を外すと穴が残るため)

### 抽象 — **エージェント報告**

**Schneider 1990** "Implementing Fault-Tolerant Services Using the State Machine Approach: A Tutorial",
ACM Computing Surveys 22(4)。取得: https://www.cs.cornell.edu/fbs/publications/SMSurvey.pdf (HTTP 200, 著者本人の Cornell ページ)
- 状態機械の定義 (p.301) 逐語: "Each command is implemented by a deterministic program"
- Semantic Characterization (p.301-302) 逐語:
  "Outputs of a state machine are completely determined by the sequence of requests it processes"
- Replica Coordination (p.303) を Agreement ("Every nonfaulty state machine replica receives every request")
  と Order ("processes the requests it receives in the same relative order") に分解。
- 限界 (p.305) 逐語: "no deterministic protocol can implement agreement under these conditions"

**Défago, Schiper, Urbán 2004** "Total Order Broadcast and Multicast Algorithms", ACM Computing Surveys 36(4)
取得: Wayback 経由の JAIST ミラー (http://web.archive.org/web/2015id_/http://www.jaist.ac.jp/jinzai/Paper/p372-defago.pdf, HTTP 200)
→ **archive 経由であることを明記**。定義の原典は Hadzilacos-Toueg 1994 / Chandra-Toueg 1996 に帰属 (p.375)。
- UNIFORM TOTAL ORDER (p.375-376) 逐語:
  "if processes p and q both TO-deliver messages m and m′, then p TO-delivers m before m′, if and only if q"

**Ongaro & Ousterhout 2014** "In Search of an Understandable Consensus Algorithm", USENIX ATC 2014
取得: https://raft.github.io/raft.pdf (HTTP 200)
- Log Matching (Figure 3) 逐語:
  "if two logs contain an entry with the same index and term, then the logs are identical"
- State Machine Safety (Figure 3, §5.4.3) 逐語:
  "if a server has applied a log entry at a given index to its state machine, no other server"

### 実装と強制箇所

**Kafka — 本体で直接検証済み (種別を強制しないこと)**
apache/kafka@869426ff7bb7198f595414063408b678cb2a4d58
`clients/src/main/java/org/apache/kafka/common/record/internal/DefaultRecord.java:81-82` を取得して目視確認:

    private final ByteBuffer key;
    private final ByteBuffer value;

`:146` の `key()` と `:156` の `value()` はいずれも `ByteBuffer` を返す。
→ **ログの物理フォーマットに型・スキーマの概念が存在しない。**

以下は**未検証 (エージェント報告)**:
- 順序の強制: `storage/.../UnifiedLog.java:1554-1557` がバッチ間 offset の単調増加を検査し、
  `:1591-1596` で `OffsetsOutOfOrderException` を投げる。
- `storage/.../ProducerAppendInfo.java:162-206` の `checkSequence` が producer の sequence 連続性を検査し、
  `:171, :177, :184, :201` で `OutOfOrderSequenceException` を投げる。
- スキーマ互換性検査は別プロダクト。confluentinc/schema-registry@ff2583d
  `client/.../CompatibilityChecker.java:24-125` と
  `core/.../KafkaSchemaRegistry.java:528-537, :604-608` (`IncompatibleSchemaException`)。
  Schema Registry 自身の永続化先も普通の Kafka トピックであり、Kafka から見れば一介のプロデューサに過ぎない。

→ **結論: ストアは順序を強制するが、メッセージ種別の分類は強制しない。**
  順序強制はログの構造的不変量であり、型/スキーマ強制はオプトインのアプリケーション層機能。

**Raft の Log Matching — 未検証 (エージェント報告)**
etcd-io/raft@3cbf6a74be3fa392edd8b64253fcd11c3ce5649b
`log.go:110-111` の `if !l.matchTerm(a.prev) { return 0, false }`、`log.go:447-453` の `matchTerm`。
`log.go:117-121` は commit 済み entry との競合時に `Panicf("entry %d conflict with committed entry ...")`
→ ドキュメントではなくプロセスをクラッシュさせる実行時チェック。
`raft.go:1791-1825` の `handleAppendEntries` が成否で応答を送り分ける。

### 強制されていないこと
3 本 (Schneider / Défago ら / Raft) の全文を `capability|heterogeneous|suspend|resume|executor` で検索して
**ヒットなし**。異種実行主体の能力宣言、仕事と成果の区別、中断・再開の宣言、実行器の平等性を
いずれも扱っていない。

event sourcing / CQRS の査読論文による形式化は**未発見**。
検索語: `"event sourcing" formal semantics peer-reviewed paper CQRS formalization`,
`"event sourcing" formal model operational semantics ACM IEEE paper`,
`"event sourcing" formal specification site:dl.acm.org`,
`Kleppmann "Designing Data-Intensive" event sourcing formalization paper CIDR VLDB`
除外した候補: arXiv:2510.18040 (査読の裏取り不能かつ主題が別)、
TESLA (10.1145/1827418.1827427) と LEAD (10.1145/3328905.3329501) は
Complex Event Processing の形式化であり Event Sourcing とは別問題。

### ★ 要件への疑義 (6 節へ送る)
Schneider の Semantic Characterization は「**複製技術を適用してよいための構造的前提条件**」であって、
「あるオープンエンドな入力に対する分類関数が全域かつ決定論的に定義できる」ことの保証ではない。
前者は必要条件を述べているに過ぎず、後者の存在証明を一切与えない。
要件 A12 の「成果の種別を決定論的に分類可能」がどちらを指すかで、満たし方も検証方法も変わる。

### 物差し当て (本体の判断)
- D1 2 者間: 無関係。SMR はレプリカ群、Kafka は多対多。
- D2 発信の閉鎖: **満たさない**。Kafka は任意のバイト列を誰でも書ける。
- D3 仕事と成果が同じプロトコル: 形式上は満たす (どちらもレコード) が、区別する概念が無い。
- D4 種別の決定論的分類: **満たさない**。本体で確認したとおりペイロードは ByteBuffer。
- D5 コンテキストの絞り込み: 満たさない。consumer は offset から全件読む構図。
- D6 取れる state の宣言: 満たさない。consumer の offset はあるが実行器の state 宣言ではない。
- D7 event stream: **順序の面では満たす**。同一形式・順序つき・実行中に読める。
  ただし「実行器の種類に関係なく同じ形式」はストアが与えるのではなく、書き手の規約に委ねられる。

---

## FIPA-ACL / KQML / contract net / JADE

### 抽象 — **エージェント報告 (すべて Wayback 経由)**

**重要: fipa.org は現在ドメインが失われている。**
エージェントの実測: `http://www.fipa.org/specs/...` → 301 → `https://www.fipa.org/...` → 301 → `https://fipa.org/...`
→ 301 (Location: `/`) → `https://fipa.org/` (200)。着地先はノルウェー語のオンラインカジノ比較サイト
(`<title>Casino på nett...` , dateModified 2026-09-19)。
→ **FIPA 仕様は原 URL から一切取得できない。以下はすべて Wayback Machine 経由。**

- CAL (SC00037J): http://web.archive.org/web/20201214192852id_/http://www.fipa.org/specs/fipa00037/SC00037J.html
- ACL Message Structure (SC00061G): http://web.archive.org/web/20201213151053id_/http://www.fipa.org/specs/fipa00061/SC00061G.html
- Contract Net (SC00029H): http://web.archive.org/web/20210224184530id_/http://www.fipa.org/specs/fipa00029/SC00029H.html
- Agent Management (SC00023J): http://web.archive.org/web/20211017033623id_/http://www.fipa.org/specs/fipa00023/SC00023J.html

**CAL: performative は 22 個**
§3.1〜§3.22 に 22 個: accept-proposal, agree, cancel, cfp, confirm, disconfirm, failure, inform,
inform-if, inform-ref, not-understood, propagate, propose, proxy, query-if, query-ref, refuse,
reject-proposal, request, request-when, request-whenever, subscribe。
§2.1 逐語: "FIPA is responsible for maintaining a consistent list of approved and proposed communicative act names"
実装義務 逐語: "FIPA-compliant agents are not required to implement any of the CAL languages, except the not-understood composite act."
→ **22 個のうち実装必須は not-understood のみ。**

**ACL Message Structure: 必須パラメータは 1 個だけ**
Table 1 に 13 パラメータ。§2 逐語: "the only parameter that is mandatory in all ACL messages is the performative"
→ sender / receiver / content すら必須ではない。

**Contract Net (SC00029H)**
cfp → {propose | refuse} → {accept-proposal | reject-proposal} → {inform-done | inform-result | failure}。
not-understood はどの時点でも割り込み可、cancel は別のメタプロトコル。
脚注 "[1] Originally developed by Smith and Davis." が原典を明示。
§1.2 逐語 (**要件に直結**):
"Real world issues such as the effects of cancelling actions, asynchrony, abnormal or unexpected IP termination, nested IPs, and the like, are explicitly not addressed here."
→ **中断・再開を明示的に対象外と宣言している。**

**Smith 1980** "The Contract Net Protocol", IEEE Trans. Computers C-29(12):1104-1113
取得: https://www.reidgsmith.com/The_Contract_Net_Protocol_Dec-1980.pdf (著者本人サイト)
p.1105 逐語: "available contractors evaluate task announcements made by several managers and submit bids"

**KQML — 調査前提の訂正**
取得: https://research.cs.umbc.edu/kqml/papers/kqml-acl-html/section3.3.html (著者 Finin の研究グループ)
原文逐語: "Though there is a predefined set of reserved performatives, it is neither a minimal required set nor a closed one."
→ **KQML の performative 集合は有限でも閉じてもいない。FIPA-ACL と対照的。**
全数を示す図は `figure157.xbm` という X11 XBM ラスタ画像で、テキスト化されておらず**未発見**。

**Agent Management (SC00023J) — 能力の宣言に相当するもの**
DF の機能は register / deregister / modify / search の 4 つ (§4.1.2)。
`df-agent-description` (§6.1.2) / `service-description` (§6.1.3) がフレーム定義だが **全パラメータ Optional**。
§4.1.1 逐語: "the DF cannot guarantee the validity or accuracy of the information"
→ **宣言の仕組みはあるが、内容の正しさを保証・検証する機構ではない。**

### 実装と強制箇所 — 本体で直接検証済み
非公式ミラー ekiwi/jade-mirror@2723c7b52269c34d7f2ef366816776bcbcd90b8f (JADE 4.3.3 相当)
**ミラーであることを明記する。** JADE 公式 jade.tilab.com は TLS 証明書エラー (curl exit 60) で未取得。

本体が `src/jade/lang/acl/ACLMessage.java` (1262 行) を取得して目視確認:

    :460  public void setPerformative(int perf) {
    :461      performative = perf;
    :462  }

    // コンストラクタの javadoc:
    //   "If the passed integer does not correspond to any of
    //    the known performatives, it silently initializes the message to not-understood."
    :331  public ACLMessage(int perf) {
    :332      performative = perf;
    :333  }

    :717  public static int getInteger(String perf)
    :718  {
    :719      String tmp = perf.toUpperCase();
    :720      for (int i=0; i<performatives.length; i++)
    :721          if (performatives[i].equals(tmp))
    :722              return i;
    :723      return -1;
    :724  }

→ **★ この調査で最も重要な判定点。**
  **仕様は 22 個の有限集合を定めているが、実装は範囲検査を一切していない。**
  `setPerformative(int)` は無検査の代入。
  さらに**コンストラクタの javadoc が「未知の値なら黙って not-understood にする」と書いているのに、
  本体は `performative = perf;` の 1 行だけで、その検証は存在しない。ドキュメントとコードが矛盾している。**
  `getInteger` はワイヤ上の未知の performative 文字列を例外なく -1 (UNKNOWN) に落とす。

以下は**未検証 (エージェント報告)**:
- `ACLMessage.java:90-134` に 22 個の `public static final int` 定数 + `UNKNOWN=-1`。`:141-165` に `String[22]`。
- `:705-711` の `getPerformative(int)` は配列外アクセスを try/catch して "NOT-UNDERSTOOD" を返すが、
  これは**文字列化時のみのフォールバック**で、内部フィールドは不正値のまま保持される。
- `src/jade/lang/acl/ACLParser.jj:153` が `msg.setPerformative(ACLMessage.getInteger(t.image));`。
- 対話順序は FSMBehaviour として構造的に実装:
  `ContractNetInitiator.java:133 extends Initiator`、`Initiator.java:45 abstract class Initiator extends FSMBehaviour`。
  `Initiator.java:148-166` の CHECK_IN_SEQ が `checkInSequence(reply)` で分岐。
  `:101-103` で NOT_UNDERSTOOD / FAILURE の遷移と `registerDefaultTransition(CHECK_IN_SEQ, HANDLE_OUT_OF_SEQ)`。
  `ContractNetInitiator.java:209-217` が PROPOSE/REFUSE/INFORM を追加登録。
  `FSMBehaviour.java:355-357, :527-535, :660-666` が遷移解決。
- **ただし強制の形は緩い**: `Initiator.java:347-348` の `handleOutOfSequence` のデフォルト実装は**空 (no-op)**。
  想定外の performative は黙って握りつぶされる。真の例外 (`FSMBehaviour.java:376-378` の
  `RuntimeException("Inconsistent FSM...")`) はデフォルト遷移が無い状態でのみ発火し、
  Contract Net の主要状態には該当しない。

### 強制されていないこと
- performative の値域 (上記のとおり)
- ACL メッセージの 12/13 パラメータ (仕様上そもそも任意)
- 共有ストア: **対象外と確認**。SC00023J §4.3 逐語 "only messages addressed to an agent can be sent to the MTS"、
  SC00061G §2.2.2 "receiver...a single agent name or a non-empty set of agent names"。
  → ACL/MTS はエージェント宛の point-to-point / マルチキャスト配送のみが前提で、共有メモリ的抽象は規定していない。
- 実行の中断・再開 (SC00029H §1.2 が明示的に対象外)
- 連続的な event stream: subscribe / request-when / request-whenever (§3.20-3.22) はあるが、
  離散的な ACL メッセージの反復であって連続的な生イベントチャネルの抽象化ではない。

### 物差し当て (本体の判断)
- D1 2 者間: **満たす**。Contract Net は Initiator と Participant の 2 役。
- D2 発信の閉鎖: **仕様は満たすが実装は満たさない**。本体で検証した `setPerformative` の無検査が根拠。
- D3 仕事と成果が同じプロトコル: **満たす**。cfp も inform-result も同じ ACLMessage 型で、
  performative だけが違う。→ **この点は要件に最も近い形。**
- D4 種別の決定論的分類: **仕様は満たすが実装は満たさない**。22 個の有限集合はあるが強制されていない。
- D5 コンテキストの絞り込み: 満たす。メッセージの content だけが渡る。
- D6 取れる state の宣言: **満たさない** (§1.2 で明示的に対象外)。
- D7 event stream: **満たさない**。

---

## LLM エージェントプロトコルのサーベイと形式検証

### 本体で実在を検証済みの文献 (arXiv abs ページの citation_title / citation_author / citation_date を確認)
- **arXiv:2505.02279** "A survey of agent interoperability protocols: Model Context Protocol (MCP),
  Agent Communication Protocol (ACP), Agent-to-Agent Protocol (A2A), and Agent Network Protocol (ANP)"
  Ehtesham, Singh, Gupta ほか / 2025-05-04
- **arXiv:2603.24747** "Formal Semantics for Agentic Tool Protocols: A Process Calculus Approach"
  Schlapbach, Andreas / 2026-03-25
- **arXiv:2607.27964** "Specification-Guided Synthesis of Deadlock-Free Communication Protocol Refinements
  with Large Language Models" / Li Yang, Hou Ping, **Yoshida Nobuko** / 2026-07-30
- **arXiv:2510.01285** "LLM-Based Multi-Agent Blackboard System for Information Discovery in Data Science"
  Salemi, Parmar, Goyal ほか / 2025-09-30

### ★ Q6 に直結する発見 — **エージェント報告**
2025-2026 の相互運用プロトコル比較研究 4 本 (2505.02279, 2607.23884, 2504.16736, 2606.31498) を
本文走査した結果、いずれも FIPA-ACL を**歴史的先行例として名前だけ**挙げるにとどまり、
"actor model" / "session type" / "process calculi" / "pi-calculus" / "tuple space" / "blackboard" の
語は**ほぼ 0 件**。
→ **LLM 時代の実装は、古典の形式的抽象との対応を論じないまま作られている。**
唯一の例外 arXiv:2510.14133 も "This fragmentation creates a semantic gap" と述べつつ、
FIPA / actor model / session type / tuple space / blackboard / MCMAS への言及は自身も 0 件で、
古典 MAS 形式手法とは独立に再発明している。

### 形式手法の適用 — **エージェント報告 (実在は本体が 2 件検証)**
- arXiv:2603.24747 (π 計算で MCP を形式化) 逐語:
  "the first process calculus formalization of SGD and MCP, proving they are structurally bisimilar"
  session types を**明示的に不採用**とした理由の逐語:
  "However, all these frameworks assume static protocols. Agent systems require runtime schema interpretation."
  → **要件の A2 (新しい実行器を変更なしに追加) と session types の静的前提の衝突を、別の論文も同じ形で指摘している。**
- arXiv:2607.27964 (Yoshida 共著) は MPST を**LLM が生成するコードの正しさの仕様**として使ったもので、
  LLM 同士の通信プロトコル自体をセッション型で型付けしたものではない。
- arXiv:2601.00219 "μACP" は FIPA-ACL の BDI 意味論を 4 動詞基底への trace-simulation として証明し
  TLA+ / Coq で検証。**実在は本体未検証。**
- arXiv:2606.17182 は TLA+ / Verus で LLM マルチエージェントの並行性異常を検証。**実在は本体未検証。**

### FIPA-ACL semantics の検証事例 — **エージェント報告**
Wooldridge "Verifiable Semantics for Agent Communication Languages", ICMAS'98
取得: http://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/icmas98.pdf (著者本人の Oxford ページ)
拡張版は AAMAS 3(1):9–31 (2000), DOI 10.1023/A:1010090027213 (Springer ペイウォールで本文未取得)
- §3.1 逐語: "if the semantics of $L_S$ are ungrounded...then we have no semantics for programs"
- §4 Example 3 逐語: "it should come as no surprise that such a framework is not verifiable"
- §5 逐語: "verification of conformance to ACLs using current techniques is not likely to be possible"
→ **performative の semantics が形式的に定義されていても、実装が準拠しているかは検証できない、
  という指摘が 1998 年時点で存在する。** これは JADE の無検査実装 (本体で確認済み) と符合する。

### 多エージェント系の形式検証ツール — **エージェント報告 + 一部訂正**
MCMAS 公式: https://sail.doc.ic.ac.uk/software/mcmas/ (Imperial College SAIL)。
**私の指示に書いた "sail-project/MCMAS" という GitHub の場所は誤りだった。**
GitHub の `SAIL-project` 組織は実在するが内容は流体力学データセットで無関係。
非公式ミラー: https://github.com/mattvonrocketstein/mcmas
入力言語 ISPL、検査対象は時相論理 (AG/EF/AX) + 認識論理 (K/GK/GCK/DK)。
→ 古典 MAS 形式検証 (MCMAS/ATL/認識論理) と LLM マルチエージェント検証 (TLA+/Verus) は
  **別系統として並走しており、両者を接続する論文は未発見。**

### 未発見 (探索経路つき)
- tuple space / Linda を LLM エージェントに適用した論文: **未発見**。
  export.arxiv.org の abs: 検索で `"tuple space" AND agent` (2 件、いずれも無関係)、
  `"tuple space" AND "large language model"` (2 件、無関係)、
  `"Linda" AND "tuple space"` (2 件、2016 年以前)、`"Linda" AND "large language model"` (0 件)。
- 「異種の実行主体を平等に扱う抽象」の形式化: **未発見**。
  `"heterogeneous agents" AND formal` (20 件精査、無関係)、
  `"heterogeneous" AND "agents" AND "type system"` (2 件、無関係)、
  `"capability-based" AND "multi-agent"` (9 件)、
  `"Kahn process networks"` (5 件、すべて古典データフロー/EDA で LLM と無接続)、
  `"actor model" AND "multi-agent" AND LLM` (2 件、無関係)。
  最も近い部分一致は arXiv:2603.00991 (Scala 3 capture checking による capability 型追跡) と
  arXiv:2601.14567 (capability-based discovery の位相不変性証明) だが、
  いずれも異種性そのものの統一的形式意味論を主張していない。**実在は本体未検証。**
- `"typed protocol" AND "agent communication"` → 0 件。
- blackboard + LLM は 2025 年後半に 3 本立ち上がっている (2510.01285 は本体で実在検証済み、
  ほかに 2510.14312, 2507.01701 — **実在は本体未検証**)。

### 取得失敗
- api.semanticscholar.org は 5 回すべて HTTP 429。
- link.springer.com の AAMAS 2000 版は認証壁。
- **本体の実測**: `http://export.arxiv.org/api/query` は空応答を返した (原因未特定)。
  代わりに `https://arxiv.org/abs/<id>` の citation_* メタタグで実在を検証した。

---

## tuple space / Linda

### 抽象 — **エージェント報告**
Gelernter, "Generative Communication in Linda", ACM TOPLAS 7(1), 1985
取得: www.cs.unc.edu ホストの PDF (33 ページ)。
**本体が https://www.cs.unc.edu/~stotts/720/Linda/lindaGenerative.pdf を試したところ HTTP 404。
正しいパスは https://www.cs.unc.edu/~stotts/COMP590-059-f21/slides/lindaGenerative.pdf (WebSearch で特定)。
本体はサンドボックスに pdftotext が無く、逐語の再確認はできていない。**
dl.acm.org の PDF は HTTP 403。

- 空間分離 (p.85, §2.3) 逐語: "a tuple in TS tagged 'P' may be input by any number of address-space-disjoint processes"
- 時間分離 (p.86) 逐語: "Linda allows communication between time-disjoint processes as well"
- `out` (p.82-83, §2.1.2) 逐語: "insertion of the tuple N, P2, ..., Pj into TS; the executing process continues immediately"
- `in` 逐語: "the tuple is withdrawn from TS, the values of its actuals are assigned to the... formals"
- `read` 逐語: "identical to the in() statement except... the tuple remains in TS"
- **`eval` は本論文に一度も出現しない (全文検索 0 件)。** p.101 逐語:
  "We propose to think of out( ), in( ), and read( ) as the primitive instructions of a virtual Linda machine"
  → **私の指示は `eval` を原論文のプリミティブとして挙げたが、これは誤りだった。**
- `in` の原子性 (p.83-84) 逐語: "The definitions require that tuples be inserted into and withdrawn from TS atomically."
  および "one gets it and the other does not; they cannot split it."
- 照合 (p.84-85, §2.2): 論文自身は "associative" ではなく "content-addressable" / "pattern-matching" と表現。

### ★ 要件に直結する発見 — **エージェント報告**
p.100-101 逐語: "the two statements out(P, FALSE) and out(P, 10) may legitimately appear in the same program"
著者自身の結論 (p.101) 逐語: "This flexibility... makes runtime type-checking impossible"
→ **Linda は設計として型検査を不可能にしている。D4 を原理的に満たせない。**
オプションの "type-checked mode" は仮想的提案として触れられるのみで、この論文では仕様化・実装されていない。

### JavaSpaces 仕様 — **エージェント報告**
取得: https://river.apache.org/release-doc/current/specs/html/js-spec.html (HTTP 200)
- take (§JS.2.5) 逐語: "Two take operations will never return copies of the same entry"
- 照合 (§JS.1.1) 逐語: "templates, which are entry objects that have some or all of its fields set to specified values that must be matched exactly"
- トランザクション分離 (§JS.3.1) 逐語: "Such an entry may not be read or taken by any other transaction."

### 実装と強制箇所 — **すべて未検証 (エージェント報告)**
github.com/apache/river は HTTP 404 (Apache Attic 移管)。
SVN `svn.apache.org/repos/asf/river/jtsk/tags/3.0.0/src/org/apache/river/outrigger/` を使用。
- take の原子性: `EntryHandle.java:452-454` の `public synchronized boolean remove()`。
  `EntryHolder.java:803-821` が `synchronized (h)` 内で `h.remove()` → `idMap.remove(...)`、
  `:809` のコメント "// Ensure removal of EntryHandle is atomic."
- トランザクション状態機械: `Txn.java:382-421` の `commit()` が
  ACTIVE→PREPARED→COMMITTED/ABORTED の一方向遷移を `IllegalStateException` で強制。
- 型照合: `OutriggerServerImpl.java:1114-1134` の `typeCheck(EntryRep)` が 8 箇所から呼ばれ、
  `:1143-1160` の `checkClass` がクラス名と構造ハッシュの不一致に `UnmarshalException` を投げる。
  `EntryRep.java:675-699` の `matches` が非 null フィールドの `.equals()` 一致を検査。
→ **注意: River が強制しているのは「同一クラス名は同一構造ハッシュを持つ」という
  実装が追加した不変量であって、Gelernter の論文にある不変量ではない。**

### 強制されていないこと
- 有限のメッセージ種別 (上記のとおり原理的に不可能)
- 発話の制限: プロセスは任意の名前・型のタプルを無制限に `out()` できる
- 能力宣言: "capabilit" の唯一のヒット (p.100) は "Dynamic process creation is the one capability of
  the generative communication operators" で、機能の意味であってアクセス制御ではない
- 実行の中断と再開: "resume" / "checkpoint" / "migrat" いずれも全文検索 0 件

### 取得失敗
- Busi, Gorrieri, Zavattaro "A Process Algebraic View of Linda Coordination Primitives", TCS 192(2), 1998
  → sciencedirect HTTP 403。書誌と要旨のみで本文未読。
- "Process Calculi for Coordination: From Linda to JavaSpaces" → Springer 303 (ペイウォール)
- "On the Semantics of JavaSpaces" (FMOODS'00) → 著者公開の PostScript は取得できたが
  ビットマップ Type3 フォントでテキスト抽出不可
- mahalo (2 相コミットの調整役) のソースは未取得。分散トランザクションの強制点は範囲外。

### 物差し当て (本体の判断)
- D1 2 者間: **満たさない**。tuple space は N 者が同じ空間を共有する構図。
- D2 発信の閉鎖: **満たさない**。任意のタプルを誰でも out できる。
- D3 仕事と成果が同じプロトコル: **満たす**。どちらもタプル。要件の「共通の input/output ストア」に形が最も近い。
- D4 種別の決定論的分類: **原理的に満たさない** (著者自身が型検査不可能と明言)。
- D5 コンテキストの絞り込み: **満たす**。`in` はテンプレートに合う 1 タプルだけを返す。
- D6 取れる state の宣言: **満たさない**。
- D7 event stream: **満たさない**。JavaSpaces の notify は登録した template への通知であって
  実行中の出来事の順序つきストリームではない。

---

## choreographic programming
### (起点リスト外。加えた理由: 「実行器が自由に発話することは許容しない」を
###  型検査より強い「構成による強制」で実現する系譜であり、session types とは別の実装系統のため)

### 抽象 — **エージェント報告**
Montesi 博士論文 "Choreographic Programming", IT University of Copenhagen, 2013
取得: https://www.fabriziomontesi.com/files/choreographic-programming.pdf (全文読了)
- p.3 §1.2 逐語: "the code produced by their EPP procedure is always free from deadlocks and race conditions"
- Corollary 2.5.1.1 "Deadlock-freedom-by-design" (p.42) 逐語の前提: "Let C be linear and well-typed."
- Theorem 2.3.2 (p.20) 逐語: "Let C be well-sorted and contain no free variable names"

HasChor (Shen, Kashiwa, Kuper, ICFP'23), https://arxiv.org/abs/2303.00924
- p.207:2 §1 逐語: "If endpoint projection is sound, the resulting distributed system enjoys a guarantee of deadlock freedom"
- **ただし HasChor 自身の EPP 正しさは未証明**。§7 で今後の課題と明記。
  Montesi の calculus / Choral の基礎理論 / Dynamic Choreographies は証明済み。

Dynamic Choreographies (Dalla Preda ほか), LMCS 13(2:1), 2017, https://arxiv.org/abs/1611.09067
- Abstract 逐語: "DPOCs generated from DIOC specifications are deadlock free and race free"
- Theorem 7.2 (weak system bisimilarity) + Corollary 7.25/7.28。
- Connectedness (Def 6.2) は多項式時間で検査可能 (Theorem 6.3)。

### 実装と強制箇所 — 本体で直接検証済み

**Choral** choral-lang/choral@5fec88ef2cd1773585eab86dbfc585db1c74f07e
**正しいパスは `choral/src/main/java/choral/compiler/soloist/ExpressionProjector.java`**
(エージェント報告は `soloist/` を落としていた。本体が GitHub API のツリーで特定して訂正)
本体が取得して目視確認 (440 行):

    :303  private boolean atWorld( Collection< WorldArgument > w ) {
    :304      return w.contains( this.world() );
    :305  }

    :177  public Expression visit( FieldAccessExpression n ) {
    :178      if( atWorld( worlds( n ) ) ) {
    :179          return n;
    :180      } else {
    :181          return UnitRepresentation.UnitFD( this.world() );
    :182      }
    :183  }

→ **★ 「構成による強制」の直接証拠。**
  射影対象のロールに属さない式は、コンパイラが AST 変換の段階で空値に置き換えて消す。
  そのロールのコードには、そもそも許されていない通信・処理が**存在しない**。
  Akka の `unsafeUpcast` のような脱出口が原理的に無い (生成物に無いものは呼べない)。

**HasChor** gshen42/HasChor@f1d269ae16cb4d67cb61a4d47b30967eb7799e4e
本体が `src/Choreography/Location.hs` を取得して目視確認 (:24-38 付近):

    data a @ (l :: LocTy)
      = Wrap a -- ^ A located value @a \@ l@ from location @l@'s perspective.
      | Empty  -- ^ A located value @a \@ l@ from locations other than @l@'s
               -- perspective.

    unwrap :: a @ l-> a
    unwrap (Wrap a) = a
    unwrap Empty    = error "this should never happen for a well-typed choreography"

→ 「その値はこのロールに存在しない」が型で表現され、違反は実行時エラーになる。

以下は**未検証 (エージェント報告)**:
- Choral `SoloistProjector.java:79-95, :110-132` が `WorldArgument w` を注入して 1 ロール分のクラスを生成。
  `StatementsProjector.java:251-274` が `if( t.worldArguments().contains( this.world() ) )` で
  代入文を残すか `UnitRepresentation.unitMC(...)` (no-op) に置換するか決める。
- Choral のチャネルは非対称: `runtime/.../DiDataChannel_A.java:26-28` は送信専用 (`Unit com( S m )`)、
  `DiDataChannel_B.java:26-30` は受信専用 (`S com( Unit m )`)。
- HasChor `src/Choreography/Choreo.hs:16-18` の `type Unwrap l = forall a. a @ l -> a` により、
  `locally l m` の中では `l` に束縛された unwrap しか使えず、他ロールの値を型検査時点で unwrap できない。
  `:53-67` の `epp` が「送信者なら send、受信者なら recv、それ以外は `return Empty`」。
- ChoRus lsd-ucsc/ChoRus@8c6e0372f100fc30a1d5a9bd8d810288e0d584a6
  `chorus_lib/src/core.rs:38, :45, :54-67` の `Located<V,L1>` は内部が `Option<V>`。
  `:747-802` の `EppOp` は**静的コード生成ではなく実行時のトレイト実装差し替え**で同じ分岐を行う。
  → Choral と ChoRus は強制メカニズムのアーキテクチャが異なる。

### ★ A2 (新しい実行器をコアと既存実行器を変更せずに追加できる) への答え — **エージェント報告**

主流の実装 (Montesi の CC 本体 / Choral / HasChor / ChoRus) は例外なく
**参加者集合が EPP 実行前に静的に確定していること**を前提とする。
EPP は「大域プロトコルの各ロールについて 1 つずつプロセスを生成する」操作であり、
ロール集合が生成対象そのものだから。
Montesi の Compositional Choreographies (博士論文 Ch.3) でも、実行時に選べるのは
「宣言済みロールを**誰が**担うか」だけで、ロール集合自体は増減しない。

**例外が 1 つある**: "Guess Who's Coming: Runtime Inclusion of Participants in Choreographies"
(Gabbrielli, Giallorenzo, Lanese, Mauro, Palamidessi Festschrift LNCS 11760, 2019)
取得: https://zenodo.org/records/10363155/files/published%20-%20Ivan%20Lanese.pdf?download=1
Abstract 逐語: "we extend Dynamic Choreographies to include new participants at runtime"
DIOC に `newRoles` 宣言、DPOC に `spawn @R {P}` 命令を追加し、稼働中の choreography に
事前の大域型に無かった新規ロールを注入できる。Theorem 1 (p.131) で
finite weak trace equivalence が保たれることを証明。

**ただし A2 を無条件には満たさない (エージェントの判断、根拠つき)**:
1. 新ロールを受け入れられる scope は元の DIOC ソースに**あらかじめ用意**されていなければならない。
2. scope の coordinator (既存の実行器) は新ロールへのコード配布・spawn 要求・完了待ち合わせを
   実際に実行する。生成される DPOC プロセスは新ロール対応ロジックを最初から含んでいる。
   → 「元のソースを書き換えない」は成立するが「デプロイ済みバイナリが一切変わらない」わけではない。

### 強制されていないこと
- メッセージの意味分類・能力宣言: いずれの実装にも独立した型・宣言として存在しない。
- サスペンド/レジューム: 基礎理論に汎用プリミティブが無い。最も近い AIOCJ の scope 置換と
  Jolie の correlation sets は「別のセッションを進行中の実行に結びつける」機構であって汎用の中断再開ではない。
- 共有ストア: DIOC の大域状態 Σ は `Σ(R, x) = ΣR(x)` という制約で各ロールのローカル状態の直和。
  他ロールの変数を直接読み書きする経路は無い。通信は厳密に 2 者間が基本形で、
  multicast は明示的な別プリミティブ。

### 取得失敗
- Montesi "Introduction to Choreographies" (CUP 2023) の無料全文は**未発見**。
  検索語: "Introduction to Choreographies Montesi Cambridge University Press draft pdf",
  "fabriziomontesi.com Introduction to Choreographies"。
- Choral の `Typer.java` (74KB) は未読。コンパイル時点で他ロールの値へのアクセスがエラーになるかは**未検証**。
- Pirouette (Coq 機械化証明), Chor-λ, Jolie 本体, AIOCJ の Jolie ソースは未読。

### 物差し当て (本体の判断)
- D1 2 者間: **満たす**。通信は厳密に 2 者間が基本形。
- D2 発信の閉鎖: **最強の形で満たす**。許されていない通信は生成物に存在しない (Choral で本体が確認)。
- D3 仕事と成果が同じプロトコル: 満たす。どちらも choreography 上の通信。
- D4 種別の決定論的分類: **満たさない**。メッセージの意味分類の機構が無い。
- D5 コンテキストの絞り込み: **満たす**。located value により他ロールの値は型の上で存在しない。
- D6 取れる state の宣言: **満たさない**。
- D7 event stream: **満たさない**。
- A2: **素朴には満たさない**。AIOCJ 拡張でのみ、事前に用意したフックからの動的追加として限定的に達成。

---

## process calculi (CSP / π 計算)

### 抽象 — **エージェント報告**

**Hoare, Communicating Sequential Processes** (1985 Prentice Hall / 著者による 2004 電子版)
**取得経路の注記**: usingcsp.com の配布元 (http://www.usingcsp.com/cspbook.pdf) は恒常的に 502 Bad Gateway。
Wayback のミラー (https://web.archive.org/web/2020/http://www.usingcsp.com/cspbook.pdf, 200) を使用。
→ **archive 経由であることを明記。**
- 同期ランデブー (p.10, Summary) 逐語: "outputs a message at the same time as the other one inputs it"
- 定式化 (p.114, §4.2) 逐語:
  "communication will occur on channel c on each occasion that P outputs a message and Q simultaneously inputs"
- チャネルの制約 (p.114) 逐語:
  "channels are used for communication in only one direction and between only two processes"
- 共有記憶への反対 (§6.3, p.187) 逐語: "pure storage should not be shared in the design of a system using concurrency"
  節の冒頭 逐語: "The purpose of this section is to argue against the use of shared storage"
  → **共有変数の排除は CSP の設計意図そのもの。**

**Milner, Parrow, Walker "A Calculus of Mobile Processes, I"**, Information and Computation 100(1):1-40, 1992
取得: https://www.pure.ed.ac.uk/ws/files/16426053/A_Calculus_of_Mobile_Processes_I.pdf (200)
1989 年の TR (ECS-LFCS-89-85) は .ps のみでサンドボックスに変換ツールが無く未変換。
アブストラクト文言の一致で 1992 年版を同一の一次資料として採用。
- Abstract 逐語: "communication links are identified by names, and computation is represented purely as the communication of names"
- §1 逐語 (actor との対比): "we shall instead achieve it by allowing references to processes, i.e., links, to be communicated"

### ★ 実装と強制箇所 — 本体で直接検証済み (Go)

The Go Programming Language Specification, https://go.dev/ref/spec (本体が取得、341,470 bytes)

    ChannelType = ( "chan" | "chan" "<-" | "<-" "chan" ) ElementType .

チャネル型が持つのは**方向 (送信専用/受信専用/双方向) と単一の要素型だけ**。
本体が仕様全文で "protocol" を検索した結果は **2 件のみ**で、いずれも
構造体タグの例にある "protocol buffer" (`// A struct corresponding to a TimeStamp protocol buffer.`) であり、
通信の順序やプロトコルという概念は仕様に一度も登場しない。

→ **★ 「型はあるがプロトコルは無い」ことの直接証拠。**
  どの順で何を送るかを表現する構文要素が言語仕様に存在しない。

### 実装と強制箇所 — **未検証 (エージェント報告)**

**occam / occam-π** — コンパイル時のエイリアス禁止と排他使用検査
occam 2.1 Reference Manual (INMOS/SGS-THOMSON, 1995-05-12)
取得: https://www.wotug.org/occam/documentation/oc21refman.pdf (200)
- §2.5.1 (p.25) 逐語: "variables and channels used in parallels are subject to usage rules"
  具体規則: "A channel may not be used for input in more than one component of a parallel"
- コンパイラの適合性条項 (p.4) 逐語:
  "to accept all programs specified by this manual and to reject all illegal ones with"
- チャネルプロトコル (p.47) 逐語: "Channel protocols enable the compiler to check the usage of channels"
  **ただし occam の PROTOCOL は「1 回の通信で送られる値の型・構造」の規定であり、
  チャネルの生涯にわたる複数回通信の順序制御ではない。** 後者は occam-π の Two-Way Protocols 拡張研究の範囲。
- occam-π (Barnes & Welch, https://www.cs.kent.ac.uk/projects/ofa/kroc/occam-pi.pdf)
  共有可動チャネル端の排他所有 (p.11) 逐語: "Before a process may use any of the component channels within a shared end, it must"
  静的検査 (p.17) 逐語: "Any attempt to do so is a language violation and will not be compiled"

**JCSP** CSPforJAVA/jcsp@6a089f975876307419303b9443ee002aa4805839
`src/main/java/jcsp/lang/ChannelOutput.java:68,75` の `public void write(T object);`
`src/main/java/jcsp/lang/ChannelInput.java:111,118` の `public T read();`
→ Go と同型。型パラメータ T は単一の要素型で、複数回の read/write の順序を型が検査する仕組みは無い。

**FDR** (CSP の refinement checker) — University of Oxford, FDR Manual Release 4.2.7 (2020-05-11)
取得: https://dl.cocotec.io/fdr/fdr-manual.pdf (200)
§4.1.8 (印刷ページ 51-52): `assert P [T= Q` が refinement を検査。3 意味モデル
"The traces model, written as [T=; The failures model, written as [F=; The failures-divergences model, written as [FD="。
deadlock freedom は内部的に `DF(A) ⊑ P` へ変換され 逐語 "the process can never get into a state where no event is offered"。
divergence freedom は `CHAOS(A) ⊑ P` へ変換。
オープンソースの代替: **HST** (github.com/hst/hst-cpp, description "An open-source refinement checker for CSP",
最終更新 2017-03-27) と **PAT** (https://pat.comp.nus.edu.sg, NUS)。
→ **私の指示に書いた "csp-solver" は Constraint Satisfaction Problem 用ソルバ群と混同される語だった。**

**線形型 / 使用型** — チャネル 1 回使用の型による保証
原論文 Kobayashi, Pierce, Turner "Linearity and the Pi-Calculus" (POPL'96 / TOPLAS 21(5), 1999) は**取得失敗**
(acm.org 403、dl.acm.org ペイウォール、著者サイト 403、Semantic Scholar 429)。
代替: Kobayashi 本人のチュートリアル https://www-kb.is.s.u-tokyo.ac.jp/~koba/papers/tutorial-type-extended.pdf (200)
§5 逐語: "1 means that the channel should be used once for that operation"
多重度 `0|1|ω` をチャネル型 `[τ1,...,τn] chan(?m1,!m2)` に付与する。

**Honda 1993 "Types for Dyadic Interaction"** (CONCUR'93) — session types の先駆
Springer / CiteSeerX は取得失敗。京都大学数理解析研究所講究録 851 号への著者本人名義の再録
https://www.kurims.kyoto-u.ac.jp/~kyodo/kokyuroku/contents/pdf/0851-05.pdf (200) で読了。
p.61 §1 逐語: "Sequencing composes two types sequentially and is denoted by [;]"
→ 型 δ1;δ2 が「まず δ1 の動作、次に δ2 の動作」という**順序を型として符号化**する。
  **これが Go のチャネル型に欠けている「プロトコル順序」を型に載せた最初期の一次資料。**
  (session types 調査で取得失敗だった Honda 1993 が、こちらで別ルートから取得できた)

### 強制されていないこと
- 共有ストア: CSP/π とも通信は点対点チャネル経由に限定。両論文の全文検索で "broadcast" は **0 件**。
- メッセージの種別分類: "performative" / "speech act" / "message type" は実質 0 件。
  メッセージは単なる値であり、発話行為タイプの分類機構は無い。
- 能力宣言: Hoare 本の "capability" の唯一のヒットは自販機の例え話
  ("unexercised capability of dispensing toffee") で無関係。Milner 論文も 0 件。
- **実行の中断と再開**: CSP の割り込み演算子 `P △ Q` は §5.4 (p.161) で逐語
  "the progress of P is just interrupted on occurrence of the first event of Q" と定義され、
  続けて **"P is never resumed"** と明言されている。
  → **`△` は「P を永久に放棄して Q に移る」演算子であり、状態を保存して再開する機構ではない。**
  Milner 論文にも "resume"/"suspend" は 0 件。
- 異種実行主体の平等性: 構文カテゴリは単一の "process"(Hoare) / "agent"(Milner) のみで、
  主体の種類を区別する属性が文法に無い。**区別する手段が無いために自動的に対称になっている**という
  消極的な意味での不在。

### 取得失敗
- usingcsp.com は 502 (5 回リトライ)。Wayback で代替。
- ECS-LFCS-89-85.ps はダウンロード成功だが ps→text 変換ツールが無く未変換。
- Kobayashi/Pierce/Turner の原論文は全経路で取得失敗 (上記)。著者のチュートリアルで代替。
- occam 2.1 Manual 中の "aliasing" という語自体は CFF Type1 フォントで機械抽出できず、
  前後の地の文から意味は確定するが語そのものは**目視確認できていない**。

### 物差し当て (本体の判断)
- D1 2 者間: **満たす**。CSP のチャネルは 2 プロセス間に限定されると明文化されている。
- D2 発信の閉鎖: **一部**。チャネルの型は絞るが、順序は絞らない (Go で本体が確認)。
  occam-π はコンパイル時に排他使用を拒否する。
- D3 仕事と成果が同じプロトコル: 満たす (どちらもチャネル上の値)。区別の概念は無い。
- D4 種別の決定論的分類: **満たさない**。
- D5 コンテキストの絞り込み: 満たす。
- D6 取れる state の宣言: **満たさない**。CSP の `△` は明示的に "P is never resumed"。
- D7 event stream: **満たさない**。ただし FDR の trace は形式的な「起きた事象の列」であり、
  検査の対象としての event 列という発想自体は存在する。

---

## blackboard (Hearsay-II / Nii)

### ★ 判定: blackboard は形式的定義ではない — 本体で直接検証済み

**Nii 1986 "Blackboard Systems"** (AI Magazine 7(2):38-53, 7(3):82-106)
著者 self-archive: Stanford Report STAN-CS-86-1123 / KSL-86-18, June 1986
取得: http://i.stanford.edu/pub/cstr/reports/cs/tr/86/1123/CS-TR-86-1123.pdf (HTTP 200, 1,476,378 bytes)
**本体が PDF を取得し pypdf でテキスト抽出して逐語を確認した。**

逐語 (著者自身の明言):
  "the blackboard model is a conceptual entity, not a computational specification"
  前後: "...the model does not specify how it is to be realized as a computational entity, that is,
  the blackboard model is a conceptual entity, not a computational specification."

逐語 (KS 間通信の制約):
  "Communication and interaction among the knowledge sources take place solely through the blackboard."

逐語 (制御の不在):
  "here is no control component specified in the blackboard model"
  (先頭の T は脚注記号のアーティファクト。原文は "There is no control component specified in the blackboard model.")
  続き: "The model merely specifies a general problem-solving ..."

→ **★ この調査で最も明快な「片側だけ」。blackboard は抽象の側にしか存在しないと、提唱者自身が書いている。**

### Hearsay-II 原典 — **エージェント報告**
Erman, Hayes-Roth, Lesser, Reddy 1980 "The Hearsay-II Speech-Understanding System",
ACM Computing Surveys 12(2):213-253
取得: https://mas.cs.umass.edu/Documents/Erman_Hearsay80.pdf
(ACM 本体 https://dl.acm.org/doi/10.1145/356810.356816 は HTTP 403)

**判定: 形式的定義ではなくシステム記述。** 根拠:
- 全文検索で "invariant" / "theorem" / "proof" / "axiom" が blackboard の文脈で一度も出現しない。
- KS は条件-行動対 (p.218) 逐語: "Each KS can be schematized as a condition-action pair"
  **ただし脚注 3 逐語: "The condition and action components of a KS are realized as arbitrary programs"**
  → KS 内部は無制約な任意プログラム。「blackboard 経由でのみ通信する」を強制する機構は論文に無い。
- 著者ら自身が形式化を他へ委ねている (p.248) 逐語:
  "Hearsay-II has also influenced some attempts at developing general techniques for formal descriptions"

### 後続の形式化 — **エージェント報告 (重要な発見)**
Diego Marmsoler, "Hierarchical Specification and Verification of Architectural Design Patterns",
FASE 2018 (ETAPS), Springer LNCS 10802, pp.149-168, DOI 10.1007/978-3-319-89363-1_9
取得成功: https://link.springer.com/content/pdf/10.1007/978-3-319-89363-1_9.pdf
(初回は idp.springer.com がサンドボックス許可外で失敗、ホスト追加で再試行し 200)

Archive of Formal Proofs に機械検証済みの Isabelle 理論が実在:
https://isa-afp.org/entries/Architectural_Design_Patterns.html (tarball 取得・展開確認済み)
- `Blackboard.thy:28-50` の `locale blackboard` が公理 `ks1`, `bhvbb1`, `bhvbb2` 等を仮定
- `Blackboard.thy:537-544` の `theorem pSolved` を well-founded induction で証明 (`:145` の `wf_induct`)
- `Blackboard.thy:134` のコメント 逐語:
  "a problem is eventually solved by the pattern even if no knowledge source exist"

**ただし注意点 2 つ**:
1. 対象は Hearsay-II そのものではなく、一般化された "blackboard pattern" (Nii/Buschmann 系譜)。
2. **これは「実行時強制」ではなく「証明支援系による機械検証」**。locale の公理を満たすという前提の下での
   条件付き保証であり、実際に動くコードがその時相論理の仮定を満たすかを検査する仕組みは含まれない。

### 未発見
Velthuijsen 1991 "Formalization of the Blackboard Architecture" (TI-ER-91-948, PTT Research) と
Velthuijsen & Braspenning "Results of Formalizing the Blackboard Architecture" (5th AAAI Workshop, 1991)
はいずれも本文 PDF **未発見**。
検索語: "Velthuijsen 1991 Formalization of the Blackboard Architecture technical report",
"Velthuijsen Braspenning Results of Formalizing the Blackboard Architecture AAAI workshop blackboard systems pdf",
"Velthuijsen blackboard formalization TI-ER-91 PTT research Braspenning 1991"。
著者サイト http://www.hugovelthuijsen.net/publicaties.html は TLS 証明書不一致で取得不可。

### 物差し当て (本体の判断)
- D1〜D7: **抽象の側にしか存在しないため、実装による強制はどの軸も満たさない。**
  D3 (仕事と成果が同じプロトコル) と D5 (コンテキストの絞り込み) は構図として要件に近いが、
  強制する機構が無い以上「対」としては採用できない。

---

## workflow の形式化 (Petri net / workflow net / BPMN)

### 抽象 — 本体で直接検証済み
van der Aalst 1998 "The Application of Petri Nets to Workflow Management",
Journal of Circuits, Systems and Computers 8(1):21-66
著者 self-archive: https://www.vdaalst.com/publications/p53.pdf (HTTP 200, 259,049 bytes)
**本体が PDF を取得し pypdf で抽出して逐語を確認した。** (ページ番号は self-archive 版のノンブル)

- Definition 7 (Sound) の第 3 条件 逐語: **"There are no dead transitions in (PN, i)"**
- Theorem 1 逐語: **"A WF-net PN is sound if and only if (PN, i) is live and bounded."**
- 計算量 逐語: **"For arbitrary WF-nets soundness is decidable but also expensive in terms of time and space complexity"**
- Corollary 1 逐語: **"A free-choice WF-net can be checked for soundness in polynomial time."**

→ **soundness は決定可能だが安価ではない。多項式時間で検査できるのは free-choice または
  well-structured という構造的部分クラスに限られる。**
→ Definition 6 (WF-net) は source place `i` と sink place `o` を持ち、`o→i` の遷移を足すと強連結、
  という構造条件。→ **未検証 (エージェント報告)**

### BPMN 2.0 — **未検証 (エージェント報告)**
OMG 仕様 (formal/2013-12-09, BPMN 2.0.2, 2013-12) https://www.omg.org/spec/BPMN/2.0.2/PDF
エージェントは仕様書自身が自己矛盾すると報告:
- §2.3.1 (p.10) 逐語: "The BPMN execution semantics have been fully formalized in this version of the International Standard"
- Clause 13.1 (p.425) 逐語: "The execution semantics are described informally (textually), and this is based on prior research"
**本体はこの 2 箇所を未検証。** (OMG の PDF が大きく、本調査の主題から外れるため深追いしなかった)

BPMN 1.0 に形式意味論が無いことを指摘した論文: Wong & Gibbons "A Process Semantics for BPMN",
Oxford CS preprint 2007 / iFM 2008, https://www.cs.ox.ac.uk/jeremy.gibbons/publications/bpmn-csp.pdf
p.1 逐語: "the specification of the notation does not include a formal semantics"
**ただし対象は BPMN 2006 年仕様 (1.0 系) であり、2.0 への指摘ではない。**

### 実装と強制箇所 — **未検証 (エージェント報告)**
- **WoPeD** github.com/woped/WoPeD@65fef37ad2bea141a8c1f4f574d50b6a3a693a39
  `WoPeD-QualAnalysis/.../soundness/WorkflowCheckImplement.java:38-56` の `getLolNetWithTStar()` が
  Theorem 1 の t* (sink→source 短絡遷移) 構成を実装。
  `.../deadtransition/DeadTransitionTest.java:28-43` が Definition 7(iii) の直接実装。
  `.../service/AbstractQualanalysisService.java:259-276` の `isSound()` が Definition 7 の集約。
  時間のかかる部分は TU/e 製の Woflan (woflan.dll) へ委譲。
- **pm4py-core** github.com/pm4py/pm4py-core@24a3bf610aea6ecc4938b1864b3ad71fcfb82084
  `pm4py/algo/analysis/woflan/algorithm.py:284` の `short_circuit_petri_net()` が Theorem 1 の PN̄ 構成。
  `:645` の `step_10()` が `graphs/utility.py:142` の `check_for_dead_tasks()` を呼ぶ。
  `:747` の `apply()` が step_1〜step_12 を連鎖。
- **LoLA** (非公式ミラー github.com/hlisdero/lola@fe5f1aecb6ff8a193bd450299bd75e2ceb9a3bc5)
  `lola/doc/lola.texi:1243-1252` 逐語:
  "A workflow net is sound if the final marking is reachable from all reachable markings"
  **ただし単一の soundness 機能は無く**、逐語 "we recommend to split the soundness check into many individual runs of LoLA"。
  ユーザーが CTL/LTL クエリに手で分解する必要がある。
  `:1258-1262` で home-state 判定はこのリリースでは非対応と明記。

### 物差し当て (本体の判断)
- D1 2 者間: 無関係。workflow net はプロセス全体の構造。
- D2 発信の閉鎖: **満たす (静的検査として)**。遷移として定義されていない動作は起こせない。
- D3 仕事と成果が同じプロトコル: 無関係。token に型の概念が無い。
- D4 種別の決定論的分類: **満たさない**。
- D5 コンテキストの絞り込み: 無関係。
- D6 取れる state の宣言: **一部**。marking が状態そのものだが、実行器の宣言ではない。
- D7 event stream: **満たさない**。ただし firing sequence は形式的な出来事の列。
- **要件への含意**: soundness は「決定可能な検査」の実例として価値がある。
  要件が「割り振り規則やワークフローの自己改変」(周辺要件 5) を持つなら、
  改変後のワークフローが soundness を保つかを機械的に検査できる形にしておく選択肢がある。
  ただし一般ケースは EXPSPACE-hard であり、部分クラスに制限する設計判断が要る。

---

## LLM エージェントフレームワーク

### MetaGPT @11cdf466d042aece04fc6cfd13b28e1a70341b1f — **未検証 (エージェント報告)**
- `metagpt/environment/base_env.py:175-195` の `publish_message` が `member_addrs` (role→address の set, `:133`) を
  舐めて `is_send_to(message, addrs)` (`metagpt/utils/common.py:423-431`) が真の role にだけ
  `role.put_message()` (`role.py:448-452`) で配送。
- `role.py:284-288` の `_watch` は `self.rc.watch = {any_to_str(t) for t in actions}`。
  `:290-291` の `is_watch` は `caused_by in self.rc.watch` という単純なメンバーシップ。
- **`Message.cause_by` の宣言型は `str`** (`schema.py:239`)。バリデータ (`schema.py:266-269`) が
  `any_to_str(...)` で文字列へ強制変換するだけ。
  → **有限 enum ではなく開いた str。型システムによる決定論的分類の保証は無い。**
    Action クラス名を使うのは運用上の慣習にすぎない。
- `role.py:399-427` (条件は `:411`) の `_observe` は `n.cause_by in self.rc.watch or self.name in n.send_to`。
  → **Linda の連想マッチング (任意形状のタプル全体へのテンプレートマッチ) とは異なり、
    2 つの決め打ちフィールドへの集合所属判定にとどまる。**
- `Message.content: str` は必須 (`schema.py:236`)、`instruct_content: Optional[BaseModel]` は任意 (`:237`)。
  → 自由文が常に必須で、構造化フィールドはそれに**追加される**形。
- A (自由に発話できるか): publish 側は**無制限**。受信側フィルタは 2 フィールドの所属判定のみ。
- B (実行中の型付きイベント): **未発見**。`metagpt/roles/`, `metagpt/environment/` で
  `yield` / `AsyncGenerator` / `StreamEvent` / `class.*Callback` / `on_tool_call` を検索してヒットなし。
- C (モデル抽象): あり。`provider/base_llm.py:35` の `BaseLLM(ABC)` と
  `configs/llm_config.py:19-46` の `LLMType(Enum)` (30 種)。

### AutoGen @027ecf0a379bcc1d09956d46d12d44a3ad9cee14 — **未検証 (エージェント報告)**
- `autogen-core` (低レベル actor/runtime 層) と `autogen-agentchat` (会話エージェント層) が分離。
- **ハンドラ振り分けは Python の `type()` でディスパッチ**:
  `_routed_agent.py:478-479` の `key_type = type(message); handlers = self._handlers.get(key_type)`。
  `@message_handler` / `@event` / `@rpc` は `strict=True` (既定) の下で型不一致時に
  `CantHandleException` を raise (`_routed_agent.py:145,264,385`)。
- **ただし `runtime.publish_message` 自体は `message: Any` を受け取り購読者全員に配送するだけで
  型チェックしない** (`_single_threaded_agent_runtime.py:387-408`)。
  未対応型でも例外にならず `on_unhandled_message` の info ログのみ。
- `TopicId` (`_topic.py:11-12,19,27,33-35`) の type/source は生の str だが `__post_init__` が正規表現検証。
  照合は文字列完全一致 (`_type_subscription.py:53-54`)。
- `autogen-agentchat/messages.py`: `BaseChatMessage` / `BaseAgentEvent` を頂点に
  `TextMessage` / `HandoffMessage` / `ToolCallRequestEvent` / `ThoughtEvent` 等の具象 pydantic モデル。
  `ChatMessage` / `AgentEvent` (`:647-665`) は `Field(discriminator="type")` 付きの**判別共用体**。
- A: **ハイブリッド**。publish 層は自由 (型無制限のブロードキャスト)、ハンドラ選択層は型で厳格強制。
- B: **あり**。`_base_chat_agent.py:155-161` の `run_stream` が
  `AsyncGenerator[BaseAgentEvent | BaseChatMessage | TaskResult, None]` を返し `:185,190,199` で yield。
- C: あり。`models/_model_client.py:209-221` の `ChatCompletionClient(ABC)` を
  `autogen-ext/.../models/{openai,anthropic,azure,ollama,llama_cpp,semantic_kernel,replay}/` が実装。

### LangGraph @aa742fb31e2827d569b843e3600aeda2e0528e4b

**★ 本体で直接検証済み — 経路の強制が無いこと**
`libs/langgraph/langgraph/pregel/_algo.py:977-979` を本体が取得して目視確認:

    if packet.node not in processes:
        logger.warning(f"Ignoring unknown node name {packet.node} in pending sends")
        return

→ **未知のノード名を指す `Send` は例外にならず、警告を出して黙って無視される。**

以下は**未検証 (エージェント報告)**:
- `graph/state.py:216-222` の `StateGraph.__init__(state_schema: type[StateT], ...)` は
  TypedDict / dataclass / pydantic の任意の型を受ける。
  `:1815-1834` の `_get_channels` が `get_type_hints(schema, include_extras=True)` で
  `Annotated[T, reducer]` を読み、2 引数 callable なら `BinaryOperatorAggregate`、
  無ければ `LastValue` (上書き) にフォールバック (`:1849-1873`)。
- `add_edge` (`state.py:928,969-977`) は未登録ノード参照に `ValueError` を raise し**静的には検証する**。
- **しかし `Command(goto=<node>)` / `Send` は宣言済みエッジと無関係に登録済みの任意のノードへ実行時にジャンプできる。**
  合法な遷移先を明示する `add_node(destinations=...)` は
  「グラフ描画にのみ使われ、実行には一切影響しない」と明記 (`state.py:404,414`)。
- `checkpoint/base/__init__.py:177` の `BaseCheckpointSaver`、`:240-252` の `get_tuple` は未実装で NotImplementedError。
  pregel ループは `_loop.py:718/971/1033/1333` の `_put_checkpoint` を経て `:1544-1547` で `checkpointer.put(...)`。
  **checkpointer 未設定なら永続化自体スキップされる (オプトインであり強制ではない)。**
- A: **NO (強い意味で)**。宣言済みエッジは既定経路にすぎず、実行時は登録済みノード空間内で自由に goto でき、
  その存在確認すら失敗時は警告止まり (本体で確認済み)。
- B: あり (粒度は粗い)。`types.py:131-133` の
  `StreamMode = Literal["values","updates","checkpoints","tasks","debug","messages","custom"]`。
  "tasks" モードは実行中のタスク開始・終了・結果・エラーを流す。
- C: **未発見**。`libs/langgraph/langgraph/` 配下に Model 抽象は無い。
  `libs/prebuilt/.../chat_agent_executor.py:13-17` が外部の `langchain_core.language_models` から import しているのみ。

### OpenAI Agents SDK @9415f7e1452d507420c64893d820869637656c84

**★ 本体で直接検証済み — handoff のツール名生成**
`src/agents/handoffs/__init__.py:206-211` を本体が取得して目視確認:

    @classmethod
    def default_tool_name(cls, agent: AgentBase[Any]) -> str:
        return _transforms.transform_string_function_style(
            f"transfer_to_{agent.name}",
            warn_on_whitespace=False,
        )

**注記: `handoffs.py` は `src/agents/handoffs/` パッケージに、`_run_impl.py` は
`src/agents/run_internal/{turn_preparation,turn_resolution,run_steps,run_loop,guardrails}.py` に再編されている。**
私の指示に書いた旧パスは現行構成と異なっていた。

以下は**未検証 (エージェント報告)**:
- `turn_resolution.py:2716/3454` の `handoff_map = {handoff.tool_name: handoff for handoff in handoffs}` という
  **有限の辞書**。`:207-214` の `is_handoff_tool_call` (`output.name in handoff_tool_names`) で
  メンバーシップ判定後、`:3348,3356-3359` の `handoff_map[output.name]` で決定論的に Handoff→Agent へ解決。
  マッチしないツール名は既定で `:3403-3406` の `raise ModelBehaviorError(...)`。
  **ただし `run_config.tool_not_found_behavior="return_error_to_model"` で例外を回避する設定も可能。**
- `exceptions.py:519-540` の `InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered`。
  `guardrails.py:142-157,168-213` が `asyncio.as_completed` で並行実行し、最初の tripwire で他をキャンセルして raise。
- `stream_events.py:9-61` の `StreamEvent = RawResponsesStreamEvent | RunItemStreamEvent | AgentUpdatedStreamEvent`。
  `RunItemStreamEvent.name` は **有限の Literal**:
  "message_output_created", "handoff_requested", "handoff_occured", "tool_called", "tool_search_called",
  "tool_search_output_created", "tool_output", "reasoning_item_created", "mcp_approval_requested",
  "mcp_approval_response", "mcp_list_tools"。
  `run_streamed(...).stream_events()` により**実行中に段階的に出る**。
  → **★ 4 フレームワーク中、要件の event stream に最も近い。ツール呼び出しが独立した種別として出る。**
- `models/interface.py:37,138` の `Model(abc.ABC)` / `ModelProvider(abc.ABC)` と
  `extensions/models/litellm_model.py:147` の `LitellmModel(Model)`。
- A: **制約あり**。モデル出力は閉じた `RunItem` 型共用体にパースされねばならず、
  handoff 経路は有限文字列辞書 + 例外で強制。自由文 (`MessageOutputItem` の内容) 自体は無制限。
