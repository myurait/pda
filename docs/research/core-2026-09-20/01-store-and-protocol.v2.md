# 調査 01 — 共通の input/output ストアとランタイム間のプロトコル

- 作成: 2026-09-20 JST
- 物差しにした要件: `docs/requirements.md`。本 worktree の HEAD には存在せず、ブランチ `feature/pda-unified-ui-strategy-4682a9` のコミット `cdd90e945d938769aefa17a2b8de3236647f6bdc` (2026-09-20 14:57 JST) から読んだ。正本が動きうるため SHA を記録する。
- 除外した資料: tag `v0.1-archive` に含まれる `docs/research/pda-v2-platform-landscape-2026-09-06.md` および `docs/research/evidence/` 配下。依頼により参照していない。そこで取得済みの出典も再利用していない。
- 種別: 調査記録。設計・製品選定の宣言ではない。
- 証拠の区別: 本文中の「**本体確認**」は、調査した私自身が一次資料を取得して該当箇所を目視したもの。「**報告**」は調査を分担させた先の報告で、私が再取得していないもの。
- 併置ファイル: `01-store-and-protocol.evidence.md` は本報告書の根拠集で、系譜ごとに逐語引用と path:line を「本体確認」と「報告」に分けて全件記録したもの。本報告書が正本、こちらが裏付けである。
- 並行調査: ブランチ `feature/pda-abstraction-implementation-pairs-767191` は別 worktree に出ているが、HEAD が本ブランチと同一で内容の差が無いことを確認した。並行する調査本は無い。

---

## 1. 結論

**Q6 の答え**: 共有ストアの系譜はメッセージの種別を型で閉じられず、型で閉じる系譜は共有ストアを持たない。この 2 つを 1 つの要素で両立させた対は、本調査では未発見である。

- 前半の根拠: Linda は著者自身が型検査を不可能にすると書き (本体確認)、Kafka はペイロードを `ByteBuffer` として持つだけである (本体確認)。ストアは順序を強制するが種別は強制しない。
- 後半の根拠: session types・π 計算・CSP・choreography はいずれも point-to-point チャネルが前提で、CSP は共有記憶に章を割いて反対している。
- **blackboard は抽象の側にしか存在しない。**提唱者 Nii 自身が、blackboard model は概念であって計算仕様ではないと書いている (本体確認)。
- **LLM 時代の実装は実装の側にしか存在しない。**2025-2026 のプロトコル比較研究 4 本は、古典の形式的抽象との対応を論じていない (報告)。
- **どの抽象にも実装にも無いのは能力の宣言である。**費用と到達できる資源を機械可読に宣言する型付きフィールドは、A2A にも MCP にも無い (A2A は本体確認)。古典側にも該当機構を見つけていない。

**3 条件 (抽象・不変量・実装による強制) がすべて揃った対は 6 件。**これに対 5 (FIPA contract net × JADE) を条件付きで加えて 7 件とした。対 5 は対話順序を FSMBehaviour として実装が強制する一方、performative の有限集合は実装が強制していないため、2 節では「仕様と実装が食い違う対」として扱う。最も要件に近いのは対 7 の choreographic programming (Choral) で、「実行器が自由に発話することは許容しない」を「生成物に存在させない」形で強制する。ただし参加者集合が静的で A2 に届かない。

---

## 2. 対の表

3 条件 (抽象・不変量・実装による強制) が揃ったものを対として採用した。

### 対 1: Kahn process network × Ptolemy II PN domain

- **抽象**: Kahn 1974 "The Semantics of a Simple Language for Parallel Programming", IFIP Congress 1974, pp.471-475 [S1]
- **不変量**: 局は入力線の履歴から出力線の履歴への関数である (p.472 §2.2.1 逐語 "from the histories of its input lines into the histories of its output lines")。最小不動点の一意性によりスケジューリングに依存しない。p.475 §6 逐語 "it can produce only determinate programs"
- **実装 (強制箇所)**: icyphy/ptII@`5dc2aa15edd05efb9d097f1353edb04a21e2358a` `ptolemy/domains/pn/kernel/PNQueueReceiver.java:241-243` が `hasToken()` を無条件 `return true;` にしている (**本体確認**)。アクターから「今データがあるか」を問う手段が存在しないため、到着検査による分岐 = 非決定性の導入が書けない。非決定を入れるには専用の `NondeterministicMerge` と専用 director が要る (報告)
- **契約 4 項目**: 能力の宣言=無関係 / 仕事の受け取り=満たす / 成果の返却=一部 (型 `D_e` はあるが種別分類ではない) / event stream=満たさない
- **A1・A2・A5・A12**: A1=一部 (同じ型の局なら差し替え可) / A2=満たさない (網の構造が静的) / A5=満たさない / A12=満たさない
- **足りないもの**: 種別分類、event stream、能力宣言、中断と再開 (論文に該当語彙なし、報告)

### 対 2: tuple space (Linda) × JavaSpaces / Apache River

- **抽象**: Gelernter "Generative Communication in Linda", ACM TOPLAS 7(1), 1985 [S2]
- **不変量**: 送受信の時間的・空間的分離と `in` の原子性。p.83-84 逐語 "The definitions require that tuples be inserted into and withdrawn from TS atomically." 続けて "one gets it and the other does not; they cannot split it." (**本体確認**)
- **実装 (強制箇所)**: JavaSpaces 仕様 §JS.2.5 逐語 "Two take operations will never return copies of the same entry"。Apache River SVN `tags/3.0.0` の `EntryHandle.java:452-454` の `synchronized boolean remove()`、`Txn.java:382-421` の状態機械が `IllegalStateException` で一方向遷移を強制 (報告)
- **契約 4 項目**: 能力の宣言=無 / 仕事の受け取り=満たす / **成果の返却=原理的に満たさない** / event stream=満たさない
- **A1・A2・A5・A12**: A1=満たす (タプルの形が同じなら誰が取ってもよい) / **A2=満たす (新しい実行器はタプルを取り始めるだけでよく、コアも他の実行器も変更が要らない)** / A5=満たさない / **A12=満たさない**
- **足りないもの**: 種別の決定論的分類。著者自身が p.101 で逐語 "This flexibility is sometimes useful, but it makes runtime type-checking impossible" と書いている。直前で同じ名前のタプルに FALSE と 10 の両方を入れる例を挙げたうえでの結論である (**本体確認**)。要件の「共通の input/output ストア」に形が最も近い一方、A12 を原理的に満たせない

### 対 3: actor model × Akka Typed

- **抽象**: Hewitt, Bishop, Steiger, IJCAI-73, pp.235-245 [S3]
- **不変量**: 相互作用は message send のみ (p.235 逐語 "one kind of behavior: sending messages to actors")。**ただし HISTORY は強い半順序であり、原文は任意の 2 event が順序づけられることを要求しないと明記している (p.240、報告)。順序保証は actor model 自体には無い**
- **実装 (強制箇所)**: akka/akka@`e2441c7ae1b0e500ac30a121863cc7e54d919a79` `ActorRef.scala:25` の `trait ActorRef[-T]` と `:32` の `def tell(msg: T): Unit` (**本体確認**)。反変により型 T 以外の送信がコンパイルエラーになる
- **契約 4 項目**: 能力の宣言=無 / 仕事の受け取り=満たす / 成果の返却=満たさない (仕事と成果の型的区別が無い) / event stream=満たさない
- **A1・A2・A5・A12**: A1=一部 / A2=一部 / A5=満たさない / A12=満たさない
- **足りないもの**: **強制に脱出口がある。**同ファイル `:45` の `def unsafeUpcast[U >: T @uncheckedVariance]` は javadoc 自身が逐語 "it may cause a [[ClassCastException]] when you send a message" と認めている (**本体確認**)。配送の保証も `:20` 逐語 "(i.e. this delivery is not reliable)"

### 対 4: multiparty session types × Scribble

- **抽象**: Honda, Yoshida, Carbone "Multiparty Asynchronous Session Types", POPL'08 / JACM [S4]
- **不変量**: JACM p.0:1 逐語 "communication safety, progress and session fidelity are established for general n-party asynchronous interactions"。Coherence は決定可能 (Theorem 4.3、報告)
- **実装 (強制箇所)**: scribble/scribble-java@`723660a81ee40a094163d9c63a93778cbc97af6e` `scribble-runtime/.../LinearSocket.java:42-49` が 2 回目の使用に `ScribRuntimeException("Linear socket resource already used: ")` を投げる (**本体確認**)。加えて状態ごとに別クラスを生成し、その状態で許されたメソッドしか持たせない (報告)
- **契約 4 項目**: 能力の宣言=無 / 仕事の受け取り=満たす / 成果の返却=一部 (ラベル付き分岐は有限だがペイロードの中身は分類しない) / event stream=満たさない
- **A1・A2・A5・A12**: A1=満たす / **A2=満たさない** / A5=満たさない / A12=一部
- **足りないもの**: **参加者集合が静的。**JACM p.0:42 逐語 "Our session types use a static participant information in the syntax and types"。動的な参加者追加は "valuable further study" として未解決 (報告)。また中断・再開のプリミティブが構文に無い
- **2 者間での含意**: 要件のプロトコルは「コアと実行器の 2 者間」なので、論文自身の記述に照らせば MPST の追加装置 (global type・projection・coherence) は要らず binary session types の duality 検査で足りる。JACM p.0:4 逐語 "When composing two parties, we only have to check they have mutually dual types" (報告)

### 対 5: FIPA contract net × JADE — **仕様と実装が食い違う対 (条件付きで採用)**

採用条件: 3 条件のうち「実装による強制」を部分的にしか満たさない。対話順序は FSMBehaviour として実装が強制するが、performative の有限集合は実装が強制しない。**「仕様が有限集合を定めていること」と「実装がそれを拒むこと」が別物である**という、要件 A12 に直結する反例として残す。

- **抽象**: FIPA CAL (SC00037J)、ACL Message Structure (SC00061G)、Contract Net (SC00029H)。いずれも Wayback 経由 [S5]。**原サイト fipa.org は現在ドメインが失われており、オンラインカジノ比較サイトへ 301 で着地する (報告)**
- **不変量**: performative は 22 個の有限集合。ACL の必須パラメータは performative 1 つのみ (§2 逐語 "the only parameter that is mandatory in all ACL messages is the performative")
- **実装 (強制箇所)**: **強制していない。**非公式ミラー ekiwi/jade-mirror@`2723c7b52269c34d7f2ef366816776bcbcd90b8f` `src/jade/lang/acl/ACLMessage.java:460-462` の `setPerformative(int perf) { performative = perf; }` に範囲検査が無い。さらに `:331-333` のコンストラクタは javadoc が「未知の値なら黙って not-understood にする」と書いているのに本体は `performative = perf;` の 1 行で、その検証が存在しない。`:717-724` の `getInteger` はワイヤ上の未知トークンを例外なく -1 に落とす (**本体確認**)
- **契約 4 項目**: 能力の宣言=一部 (DF への service-description 登録。ただし全パラメータ Optional で §4.1.1 逐語 "the DF cannot guarantee the validity or accuracy of the information") / 仕事の受け取り=満たす / **成果の返却=仕様は満たすが実装は満たさない** / event stream=満たさない
- **A1・A2・A5・A12**: A1=満たす / A2=満たす / A5=満たさない / **A12=仕様のみ**
- **足りないもの**: 実装による強制そのもの。Contract Net の順序は FSMBehaviour として構造化されているが、想定外の performative は `handleOutOfSequence` の空実装へ流れて黙って握りつぶされる (報告)。中断・再開は SC00029H §1.2 が逐語 "abnormal or unexpected IP termination, nested IPs, and the like, are explicitly not addressed here" と明示的に対象外としている
- **要件に最も近い点**: **仕事と成果が同じ型である。**cfp も inform-result も同じ ACLMessage で performative だけが違う。契約の「成果を、成果と同じプロトコルに基づくメッセージとして返す」に形が一致する唯一の古典

### 対 6: workflow net の soundness × WoPeD / pm4py

- **抽象**: van der Aalst 1998 "The Application of Petri Nets to Workflow Management" [S6]
- **不変量**: Definition 7 (Sound) の 3 条件。第 3 条件 逐語 "There are no dead transitions in (PN, i)"。Theorem 1 逐語 "A WF-net PN is sound if and only if (PN, i) is live and bounded." (**本体確認**)
- **実装 (強制箇所)**: WoPeD@`65fef37ad2bea141a8c1f4f574d50b6a3a693a39` の `WorkflowCheckImplement.java:38-56` が Theorem 1 の t* 構成を実装、`AbstractQualanalysisService.java:259-276` の `isSound()` が Definition 7 を集約。pm4py-core@`24a3bf610aea6ecc4938b1864b3ad71fcfb82084` の `algorithm.py:284` `short_circuit_petri_net()` (報告)
- **契約 4 項目**: どれも直接には対応しない。これは「ワークフローが健全かを機械的に検査できる」という別の軸の対
- **A1・A2・A5・A12**: いずれも無関係
- **足りないもの**: 計算量。逐語 "soundness is decidable but also expensive in terms of time and space complexity"。多項式時間で済むのは構造的部分クラスに限られる。Corollary 1 逐語 "A free-choice WF-net can be checked for soundness in polynomial time." (**本体確認**)
- **要件への含意**: 周辺要件 5 (自己改変) を持つなら、改変後のワークフローが soundness を保つかを機械検査できる形にする選択肢がある。ただし部分クラスに制限する設計判断が要る

### 対 7: choreographic programming × Choral — **最も要件に近い対**

- **抽象**: Montesi "Choreographic Programming", ITU Copenhagen, 2013 [S7]
- **不変量**: Corollary 2.5.1.1 "Deadlock-freedom-by-design"。linear かつ well-typed な choreography から射影した実装は deadlock free (報告)
- **実装 (強制箇所)**: choral-lang/choral@`5fec88ef2cd1773585eab86dbfc585db1c74f07e` `choral/src/main/java/choral/compiler/soloist/ExpressionProjector.java:303-305` の `atWorld` が `w.contains(this.world())` を判定し、`:177-183` の `visit(FieldAccessExpression)` がそのロールに属さない式を `UnitRepresentation.UnitFD(this.world())` に置き換えて消す (**本体確認**)。HasChor@`f1d269ae16cb4d67cb61a4d47b30967eb7799e4e` `src/Choreography/Location.hs` の `data a @ (l :: LocTy) = Wrap a | Empty` と `unwrap Empty = error "this should never happen for a well-typed choreography"` (**本体確認**)
- **契約 4 項目**: 能力の宣言=無 / 仕事の受け取り=満たす / 成果の返却=一部 / event stream=満たさない
- **A1・A2・A5・A12**: A1=満たす / **A2=素朴には満たさない** / A5=満たさない / A12=満たさない
- **足りないもの**: **参加者集合が静的。**EPP は「各ロールについて 1 つずつプロセスを生成する」操作であり、ロール集合が生成対象そのもの。例外は Dynamic Choreographies の拡張 "Guess Who's Coming" (Gabbrielli ら 2019) [S8] で、逐語 "we extend Dynamic Choreographies to include new participants at runtime"。ただし新ロールを受け入れる scope を元のソースに**あらかじめ用意**しておく必要があり、coordinator 側は新ロール対応ロジックを最初から含む (報告)
- **要件に最も近い点**: **「実行器が自由に発話することは許容しない」を最強の形で満たす。**許されていない通信は生成物に存在しないので、Akka の `unsafeUpcast` のような脱出口が原理的に無い

### 補足: durable execution (Temporal) — 対だが軸が違う

- **抽象**: Schneider 1990 の state machine approach に連なる。逐語 "Each command is implemented by a deterministic program" (報告)
- **不変量**: replay 時に再生成したコマンド列が記録済み event history と一致すること
- **実装 (強制箇所)**: temporalio/api@`1c27468c756fc8abc800235c33b74c6eba638c88` `temporal/api/enums/v1/event_type.proto` の `EventType` が **61 値**の閉じた enum (**本体確認**)。違反検出は sdk-core の `Nondeterminism` エラー (報告)
- **要件との関係**: **契約の「取れる state」の宣言と「event stream」に、現存する実装のなかで最も近い。**有限種の event が起きた順に永続化され、外から読める
- **足りないもの**: **event の値がすべて「システムが起こした出来事」で、業務上の成果の種別を表す語彙を 1 つも含まない (本体確認)。**要件 A12 が求めるのは後者であり、ここは埋まらない

---

## 3. 片側だけ

### 抽象のみ (実装による強制が無い)

- **blackboard アーキテクチャ (Hearsay-II / Nii)** — 提唱者自身が形式化されていないと書いている。Nii 1986 逐語 "the blackboard model is a conceptual entity, not a computational specification" (**本体確認**)。KS 間通信の制約 逐語 "Communication and interaction among the knowledge sources take place solely through the blackboard." も、Hearsay-II 論文の脚注 3 が KS 内部を逐語 "The condition and action components of a KS are realized as arbitrary programs" としているため、強制する機構が無い (報告)。制御についても Nii 逐語 "There is no control component specified in the blackboard model" (PDF 抽出では直前の脚注記号に吸われて先頭の T が落ちる。原文は There)
  - 例外に近いもの: Marmsoler FASE 2018 と Archive of Formal Proofs の `Architectural_Design_Patterns` が blackboard pattern を Isabelle/HOL で機械検証している (報告)。ただし (a) 対象は Hearsay-II そのものではなく一般化されたパターン、(b) **これは実行時強制ではなく証明支援系による検証**で、locale の公理を実際のコードが満たすかを検査する仕組みは含まれない
- **KQML** — 落とした理由: 有限集合ではない。原論文は予約済み performative の集合について逐語 "it is neither a minimal required set nor a closed one" と書く (報告)。不変量として「有限の発話種別」を置けない
- **Hewitt の actor 形式体系そのもの** — 順序も配送も保証しない (上記対 3 参照)。実装が追加している性質と混ざりやすいので分けて記録する
- **BPMN 2.0** — 落とした理由: 仕様自身が自己矛盾している (報告)。§2.3.1 は逐語 "The BPMN execution semantics have been fully formalized in this version of the International Standard" と書き、Clause 13.1 は逐語 "The execution semantics are described informally (textually), and this is based on prior research" と書く。**この 2 箇所は本体未検証**

### 実装のみ (対応する抽象が無い)

- **MetaGPT の message pool** — `Message.cause_by` の宣言型が `str` で、バリデータは文字列へ強制変換するだけ。有限 enum ではない (報告)。`_observe` は 2 つの決め打ちフィールドへの集合所属判定であり、Linda の連想マッチング (任意形状のタプル全体へのテンプレートマッチ) とは別物。tuple space に見えるが不変量が特定できない
- **LangGraph の状態遷移** — 宣言済みエッジは静的に検証されるが (`add_edge` が `ValueError`)、`Command(goto=)` / `Send` は登録済みの任意のノードへ実行時にジャンプできる。`add_node(destinations=...)` は描画専用と明記されている (報告)。**未知のノード名を指す `Send` は例外にならず `_algo.py:977-979` で `logger.warning(f"Ignoring unknown node name {packet.node} in pending sends")` を出して黙って無視される (本体確認)**
- **Kafka のログ** — 順序は強制するが種別は強制しない。`DefaultRecord.java:81-82` が `private final ByteBuffer key; private final ByteBuffer value;` (**本体確認**)。スキーマ互換性検査は別プロダクトの Schema Registry の中だけで行われ、Kafka から見れば Schema Registry も一介のプロデューサにすぎない (報告)
- **Go の channel** — 型はあるがプロトコルが無い。仕様の `ChannelType = ( "chan" | "chan" "<-" | "<-" "chan" ) ElementType .` は方向と単一要素型しか持たず、仕様全文で "protocol" の出現は 2 件でどちらも構造体タグ例の "protocol buffer" (**本体確認**)

### 不変量が特定できない / 落としたもの

- **AutoGen** — ハンドラ選択層は `type()` によるディスパッチで `CantHandleException` を投げる強制があるが、`runtime.publish_message` 自体は `message: Any` を受け購読者全員に配送するだけで型検査しない (報告)。層によって強制の有無が違うため単一の不変量として書けない
- **MCP** — 落とした理由: **そもそも「実行器が仕事を受け取り成果を返す」プロトコルではない。**`schema.ts:1875` 逐語 "Used by the client to invoke a tool provided by the server." で、モデル側が道具を選んで呼ぶ向き (報告)。要件の「ランタイム間のプロトコル」の位置には入らない。ただし自己宣言の要素 (調査 03) では中心に来る
- **event sourcing / CQRS** — 査読論文による形式化が**未発見** (探索経路は 5 節)

---

## 4. LLM 時代の実装の対応表

### A2A (プロトコルバージョン 1.0、a2aproject/A2A@`afda8316c64951a2ecb2a0d3d10867405d2b4095`)

- **対応する抽象**: 該当なし。サーベイ調査の結果、古典の形式的抽象との対応は論じられていない (報告)
- **保っている不変量**: `TaskState` が 9 値の閉じた proto enum (**本体確認**)。`Part` は `oneof` なので text/raw/url/data のうち 1 つだけが有効になり種別は決定論的に分類できる (報告)。`StreamResponse` も 4 種の `oneof` (**本体確認**)
- **落としている不変量**: (a) **仕事と成果が別型。**`message Message` (`:260-277`) と `message Artifact` (`:280-293`) はフィールド構成が異なる独立した型で、Artifact に `role` も `reference_task_ids` も無い (**本体確認**)。契約の「成果と同じプロトコルに基づくメッセージ」を満たさない。(b) **実行中の内部の出来事が出ない。**外へ出るのはタスクの状態遷移と成果物の増分だけで、呼んだツールとその結果、出した判断を表す event 型が存在しない (**本体確認**)。(c) **費用と到達できる資源の宣言が無い。**proto 全文 812 行に `cost|price|pricing|budget|quota` が **0 件** (**本体確認**)
- **根拠**: `specification/a2a.proto` の該当行。`:279` 逐語 "Artifacts represent task outputs."

### MCP (仕様バージョン 2026-07-28、modelcontextprotocol@`24efd6e7cbd7a074e6b3b781eb370891df40afad`)

- **対応する抽象**: 該当なし
- **保っている不変量**: `Tool` の `inputSchema` が JSON Schema 2020-12 で必須。typescript-sdk が zod で実行時検証し `InvalidParams` / `InvalidResult` を投げる (報告)
- **落としている不変量**: 向きが逆 (上記 3 節参照)。費用・レート制限・到達可能資源の型付き宣言が無い (報告)
- **根拠**: `schema/` 配下のバージョンディレクトリを GitHub API で列挙し `2026-07-28` が最新であることを確認 (**本体確認**)。SDK の公開定数 `LATEST_PROTOCOL_VERSION` は `2025-11-25` のままで 1 世代遅れている (報告)

### MetaGPT (@`11cdf466d042aece04fc6cfd13b28e1a70341b1f`)

- **対応する抽象**: 形の上では tuple space に近いが、本質的な不変量 (原子性・連想マッチング) を持たない
- **保っている不変量**: `content` の必須性と pydantic による型強制 (報告)
- **落としている不変量**: `cause_by` が開いた `str` で有限 enum ではない。publish 側は任意の時点で任意の内容を送れる。実行中の型付きイベントが**未発見** (報告)
- **根拠**: `schema.py:239,266-269`、`role.py:284-291,399-427`

### AutoGen (@`027ecf0a379bcc1d09956d46d12d44a3ad9cee14`)

- **対応する抽象**: actor model (型付きメッセージのディスパッチという点で)
- **保っている不変量**: ハンドラ選択が `type()` の完全一致で、strict モードで `CantHandleException`。agentchat のメッセージは `Field(discriminator="type")` の判別共用体 (報告)
- **落としている不変量**: publish 層が無型。未対応型でも例外にならず info ログのみ (報告)
- **根拠**: `_routed_agent.py:478-479,145,264,385`、`_single_threaded_agent_runtime.py:387-408`

### LangGraph (@`aa742fb31e2827d569b843e3600aeda2e0528e4b`)

- **対応する抽象**: 状態遷移系に見えるが、実行時の遷移が静的グラフに縛られないため対応しない
- **保っている不変量**: 静的エッジの宣言時検証、`StreamMode` の閉じた Literal (報告)
- **落としている不変量**: **経路の強制。**未知ノード名の `Send` が警告で黙殺される (**本体確認**)。checkpointer はオプトインで、未設定なら永続化がスキップされる (報告)
- **根拠**: `pregel/_algo.py:977-979`、`graph/state.py:404,414`

### OpenAI Agents SDK (@`9415f7e1452d507420c64893d820869637656c84`)

- **対応する抽象**: 該当なし。ただし handoff の解決は有限写像として決定論的
- **保っている不変量**: `default_tool_name` が `transfer_to_{agent.name}` を生成し (**本体確認**)、`handoff_map` という**有限の辞書**でツール名から Agent へ決定論的に解決する (報告)。`RunItemStreamEvent.name` が 11 値の有限 Literal で、ツール呼び出しが独立した種別として**実行中に**出る (報告)
- **落としている不変量**: 自由文の内容自体は無制限。ガードレールはオプトイン。`tool_not_found_behavior` の設定で例外強制を回避できる (報告)
- **根拠**: `src/agents/handoffs/__init__.py:206-211`、`stream_events.py:9-61`
- **判定**: **4 フレームワーク中、要件の event stream に最も近い。**

### サーベイから見た全体

2025-2026 の相互運用プロトコル比較研究 4 本 (arXiv:2505.02279 ほか) はいずれも FIPA-ACL を歴史的先行例として名前だけ挙げ、actor model・session types・process calculi・tuple space・blackboard との対応を論じていない (報告)。例外的に形式手法を当てた論文は存在し、arXiv:2603.24747 が π 計算で MCP を形式化している。同論文は session types を不採用とした理由を逐語 "However, all these frameworks assume static protocols. Agent systems require runtime schema interpretation." と書いており (報告)、**MPST と choreography で見つかった静的前提の問題を、独立に同じ形で指摘している**。

---

## 5. 未発見

いずれも「不在」ではなく「探して見つからなかった」ものである。

1. **共有ストアと型で閉じた発話を両立させた対** — 探索経路: 本調査の 12 系譜すべて。tuple space 側は型検査を原理的に諦めており、session types / choreography 側は point-to-point を前提にしている。両者を接続した資料を見つけていない
2. **tuple space (Linda) を LLM エージェントに適用した論文** — export.arxiv.org の abs 検索で `"tuple space" AND agent` (2 件、無関係)、`"tuple space" AND "large language model"` (2 件、無関係)、`"Linda" AND "tuple space"` (2 件、2016 年以前)、`"Linda" AND "large language model"` (0 件)
3. **異種の実行主体を平等に扱う抽象の形式化** — 検索語: `"heterogeneous agents" AND formal` (20 件精査)、`"heterogeneous" AND "agents" AND "type system"` (2 件)、`"capability-based" AND "multi-agent"` (9 件)、`"actor model" AND "multi-agent" AND LLM` (2 件)、`"typed protocol" AND "agent communication"` (0 件)。最も近い部分一致は arXiv:2603.00991 と arXiv:2601.14567 だが、いずれも異種性そのものの統一的形式意味論を主張していない
4. **event sourcing / CQRS の査読論文による形式化** — 検索語: `"event sourcing" formal semantics peer-reviewed paper CQRS formalization`、`"event sourcing" formal model operational semantics ACM IEEE paper`、`"event sourcing" formal specification site:dl.acm.org`。除外した候補: TESLA (10.1145/1827418.1827427) と LEAD (10.1145/3328905.3329501) はいずれも Complex Event Processing の形式化で Event Sourcing とは別問題
5. **blackboard を形式化した 1991 年の試み** — Velthuijsen "Formalization of the Blackboard Architecture" (TI-ER-91-948) と Velthuijsen & Braspenning (5th AAAI Workshop, 1991) はいずれも本文 PDF 未発見。著者サイトは TLS 証明書不一致で取得不可
6. **古典 MAS 形式検証と LLM マルチエージェント検証を接続する論文** — MCMAS/ATL/認識論理の系譜と TLA+/Verus の系譜が別系統で並走しており、両者を接続する文献を見つけていない
7. **MetaGPT の role/environment 層での型付き実行中イベント** — `yield` / `AsyncGenerator` / `StreamEvent` / `class.*Callback` / `on_tool_call` を該当ディレクトリで検索してヒットなし
8. **Restate 単体の査読論文** — 検索語: `"Restate" durable execution paper`、`"Restate" journal invocation VLDB CIDR arxiv`
9. **Montesi "Introduction to Choreographies" (CUP 2023) の無料全文** — 検索語: "Introduction to Choreographies Montesi Cambridge University Press draft pdf"

### 取得できなかった資料

- **fipa.org 全体** — ドメインが失われ、`http://www.fipa.org/specs/...` は 301 の連鎖の末にオンラインカジノ比較サイトへ 200 で着地する。FIPA 仕様 4 件はすべて Wayback Machine 経由で取得した
- **dl.acm.org** — Gelernter 1985、Hearsay-II、Kobayashi/Pierce/Turner ほかすべて HTTP 403。著者・大学ホストの公開版で代替した
- **Springer (link.springer.com)** — Honda 1993、Honda-Vasconcelos-Kubo 1998、Wooldridge の AAMAS 2000 版はいずれも認証壁 (303 → idp.springer.com)。Honda 1993 のみ京都大学数理解析研究所講究録 851 号の著者本人名義の再録で取得できた
- **Agha 1986** — dspace.mit.edu の bitstream が HTTP 405 + AWS WAF の CAPTCHA、osti.gov は接続失敗、deepblue.lib.umich.edu は 403。CAPTCHA の回避はしていない。**この文献の主張は本報告書で一切使っていない**
- **usingcsp.com** — 恒常的に 502。Wayback のミラーで代替
- **api.semanticscholar.org** — 複数のエージェントから HTTP 429
- **export.arxiv.org の API** — 空応答を返した (原因未特定)。`https://arxiv.org/abs/<id>` の citation メタタグで代替し、主要 4 件の実在を確認した (**本体確認**)
- **OMG BPMN 2.0.2 PDF の該当 2 箇所** — 本調査の主題から外れるため本体では未検証

### 調査の範囲について明記すること

私の指示に誤りが 3 件あり、いずれも調査先が一次資料に当たって訂正した。

- Linda のプリミティブとして `eval` を挙げたが、Gelernter 1985 に `eval` は**一度も出現しない** (本体が全文検索して 0 件を確認)。原論文が挙げるのは `out` / `in` / `read` の 3 つ (p.101 は out / in / read の 3 つについて逐語 "the primitive instructions of a virtual Linda machine" と書く)
- MCMAS の GitHub の場所として "sail-project/MCMAS" を挙げたが誤り。公式は https://sail.doc.ic.ac.uk/software/mcmas/ で GitHub 公式リポジトリは無い
- CSP のオープンソース checker として "csp-solver" を挙げたが、これは Constraint Satisfaction Problem 用ソルバと混同される語。実在するのは HST と PAT

---

## 6. 他の要素への含意

### ランタイムのラッパー (調査 02 で問うべきこと)

**対 7 が示すのは、ラッパーを「包む」ものとして作るか「生成する」ものとして作るかで強制力が変わることである。**Choral はコンパイラが射影の段階で、そのロールに属さない処理を生成物から消す。一方 Akka は型で絞るが `unsafeUpcast` という脱出口が残り、JADE に至っては javadoc が主張する検証がコードに存在しない。

調査 02 で立てるべき問い: **異なるベンダーのランタイム (Claude Code、Codex、Gemini API、jev) を包むラッパーで、「契約の形に揃える」以上のことができるのか。**包む対象のプロセスが何を出力するかをラッパーが決められない以上、Choral 型の「生成による強制」は原理的に取れない可能性がある。取れないなら、強制の位置はラッパーではなくコア側の受け入れ検査になる。その場合「実行器が自由に発話することは許容しない」は「自由な発話をコアが受け取らない」という意味に変わる。これは要件の文言と同じことか、違うことか。

### MCP 的な自己宣言 (調査 03 で問うべきこと)

**この調査で最も明確な空白は能力の宣言である。**A2A の proto 全文 812 行に費用を表す語が 1 つも無く (本体確認)、MCP の `Tool` にも無い (報告)。古典側にも、FIPA の DF 登録が唯一それらしいが全パラメータ Optional で、仕様自身が内容の正しさを保証しないと書いている。

調査 03 で立てるべき問い: **要件が「能力の宣言」に挙げた 5 項目 (得意・不得意、費用、到達できる資源、扱える入力と出力の種類、取れる state) のうち、既存のどのスキーマがどれを持つか。**とくに「取れる state」は、対 7 と対 4 がそろって中断・再開の概念を持たず、durable execution だけがそこを扱っていた。宣言としての state と、システムが一律に決める checkpoint は別物である。

また、MCP は本調査で「ランタイム間のプロトコル」の位置には入らないと判定した (向きが逆)。調査 03 では自己宣言の側で中心に来るはずで、**同じ MCP を 2 つの要素にまたがって使うのか、自己宣言だけに使うのか**が論点になる。

### ログストア (調査 04 で問うべきこと)

**この調査で分かったのは、順序の保証と種別の保証が別の場所にあることである。**Kafka は順序を強制するがペイロードは `ByteBuffer` (本体確認)、Schema Registry は種別を検査するが Kafka から見れば一介のプロデューサにすぎない (報告)。Temporal は 61 値の閉じた enum を持つが、値はすべてシステムの出来事で業務上の成果の種別を含まない (本体確認)。

調査 04 で立てるべき問い: **A5 が求める「実行器の種類に関係なく同じ形式」は、ストアが強制するのか、書き手が守るのか。**ストア側に強制を置くなら書き込み時のスキーマ検査が要り、それは Kafka + Schema Registry の構成に近づく。書き手側に置くならラッパーの責務になり、調査 02 の問いと合流する。

現存で最も近いのは OpenAI Agents SDK の `RunItemStreamEvent` で、11 値の有限 Literal としてツール呼び出しが独立した種別で実行中に出る (報告)。A2A の 4 種 `oneof` には内部の出来事が無い (本体確認)。**event の粒度をどちらに置くかが、可視化と監査で見えるものを決める。**

### 要件への疑義

要件を書き換えてはいないので、疑義としてここに置く。

**A12 の「決定論的に分類可能」が 2 つの異なる意味を持ちうる。**state machine replication における決定論は「複製技術を適用してよいための前提条件」であって、任意の入力に対する分類関数が全域かつ決定論的に定義できることの保証ではない (報告)。前者は必要条件を述べているだけで、後者の存在を証明しない。

要件が求めているのが後者、つまり「LLM が返した自由文を含む成果を、人が読み替えずに有限の種別へ写す関数が書ける」ことなら、本調査で見つかった実装のうちそれを達成しているものは 1 つも無い。A2A の `Part` も Temporal の `EventType` も OpenAI Agents SDK の `RunItemStreamEvent` も、分類しているのは「どの形式で来たか」「システムが何をしたか」であって「成果が何であるか」ではない。

Linda の著者が 40 年前に書いた逐語 "This flexibility is sometimes useful, but it makes runtime type-checking impossible" (本体確認) は、共有ストアに任意の内容を置ける自由と、置かれたものを機械的に分類できることが、原理的に両立しないことを述べている。**要件はこの 2 つを同じ 1 つの要素 (共通の input/output ストア) に同時に求めている。**設計でどちらを優先するかの判断が要る。

---

## 7. Sources

すべて 2026-09-20 に取得。

- [S1] Kahn, G. "The Semantics of a Simple Language for Parallel Programming", IFIP Congress 1974, pp.471-475. https://www.cs.princeton.edu/courses/archive/fall07/cos595/kahn74.pdf (HTTP 200)
- [S2] Gelernter, D. "Generative Communication in Linda", ACM TOPLAS 7(1), 1985, pp.80-112. https://www.cs.unc.edu/~stotts/COMP590-059-f21/slides/lindaGenerative.pdf (HTTP 200, 33 ページ, 本体が pypdf で抽出して確認)
- [S3] Hewitt, C., Bishop, P., Steiger, R. "A Universal Modular ACTOR Formalism for Artificial Intelligence", IJCAI-73, pp.235-245. https://www.ijcai.org/Proceedings/73/Papers/027B.pdf (HTTP 200)
- [S4] Honda, K., Yoshida, N., Carbone, M. "Multiparty Asynchronous Session Types", POPL'08. http://www.doc.ic.ac.uk/~yoshida/multiparty/multiparty.pdf (HTTP 200) / JACM full version http://mrg.doc.ic.ac.uk/publications/multiparty-asynchronous-session-types-jacm/jacm.pdf (HTTP 200, https は SNI 証明書不一致のため http で取得)
- [S5] FIPA 仕様 4 件。すべて Wayback Machine 経由 (原サイト fipa.org は失効):
  - Communicative Act Library (SC00037J) http://web.archive.org/web/20201214192852id_/http://www.fipa.org/specs/fipa00037/SC00037J.html
  - ACL Message Structure (SC00061G) http://web.archive.org/web/20201213151053id_/http://www.fipa.org/specs/fipa00061/SC00061G.html
  - Contract Net Interaction Protocol (SC00029H) http://web.archive.org/web/20210224184530id_/http://www.fipa.org/specs/fipa00029/SC00029H.html
  - Agent Management (SC00023J) http://web.archive.org/web/20211017033623id_/http://www.fipa.org/specs/fipa00023/SC00023J.html
- [S6] van der Aalst, W.M.P. "The Application of Petri Nets to Workflow Management", J. Circuits, Systems and Computers 8(1), 1998, pp.21-66. https://www.vdaalst.com/publications/p53.pdf (HTTP 200, 本体が pypdf で抽出して確認。ページ番号は self-archive 版のノンブル)
- [S7] Montesi, F. "Choreographic Programming", PhD thesis, IT University of Copenhagen, 2013. https://www.fabriziomontesi.com/files/choreographic-programming.pdf (HTTP 200)
- [S8] Gabbrielli, M., Giallorenzo, S., Lanese, I., Mauro, J. "Guess Who's Coming: Runtime Inclusion of Participants in Choreographies", LNCS 11760, 2019. https://zenodo.org/records/10363155/files/published%20-%20Ivan%20Lanese.pdf?download=1 (HTTP 200)
- [S9] Nii, H.P. "Blackboard Systems", AI Magazine 7(2) と 7(3), 1986. 著者 self-archive: Stanford Report STAN-CS-86-1123 / KSL-86-18. http://i.stanford.edu/pub/cstr/reports/cs/tr/86/1123/CS-TR-86-1123.pdf (HTTP 200, 本体が pypdf で抽出して確認)
- [S10] Erman, L.D., Hayes-Roth, F., Lesser, V.R., Reddy, D.R. "The Hearsay-II Speech-Understanding System", ACM Computing Surveys 12(2), 1980, pp.213-253. https://mas.cs.umass.edu/Documents/Erman_Hearsay80.pdf (HTTP 200。ACM 本体は 403)
- [S11] Hoare, C.A.R. "Communicating Sequential Processes", 1985 / 2004 電子版. https://web.archive.org/web/2020/http://www.usingcsp.com/cspbook.pdf (HTTP 200。原配布元 usingcsp.com は 502)
- [S12] Milner, R., Parrow, J., Walker, D. "A Calculus of Mobile Processes, I", Information and Computation 100(1), 1992, pp.1-40. https://www.pure.ed.ac.uk/ws/files/16426053/A_Calculus_of_Mobile_Processes_I.pdf (HTTP 200)
- [S13] Honda, K. "Types for Dyadic Interaction", CONCUR'93. 京都大学数理解析研究所講究録 851 号への著者本人名義の再録. https://www.kurims.kyoto-u.ac.jp/~kyodo/kokyuroku/contents/pdf/0851-05.pdf (HTTP 200)
- [S14] Schneider, F.B. "Implementing Fault-Tolerant Services Using the State Machine Approach: A Tutorial", ACM Computing Surveys 22(4), 1990. https://www.cs.cornell.edu/fbs/publications/SMSurvey.pdf (HTTP 200)
- [S15] Ongaro, D., Ousterhout, J. "In Search of an Understandable Consensus Algorithm", USENIX ATC 2014. https://raft.github.io/raft.pdf (HTTP 200)
- [S16] Défago, X., Schiper, A., Urbán, P. "Total Order Broadcast and Multicast Algorithms: Taxonomy and Survey", ACM Computing Surveys 36(4), 2004. Wayback 経由の JAIST ミラー http://web.archive.org/web/2015id_/http://www.jaist.ac.jp/jinzai/Paper/p372-defago.pdf (HTTP 200)
- [S17] Wooldridge, M. "Verifiable Semantics for Agent Communication Languages", ICMAS'98. https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/icmas98.pdf (HTTP 200)
- [S18] The Go Programming Language Specification (go1.27, 2026-05-26). https://go.dev/ref/spec (HTTP 200, 本体確認)
- [S19] Go/JCSP 以外の CSP ツール: FDR Manual Release 4.2.7, University of Oxford, 2020-05-11. https://dl.cocotec.io/fdr/fdr-manual.pdf (HTTP 200)
- [S20] Marmsoler, D. "Hierarchical Specification and Verification of Architectural Design Patterns", FASE 2018, LNCS 10802, pp.149-168. https://link.springer.com/content/pdf/10.1007/978-3-319-89363-1_9.pdf (HTTP 200)。機械検証済み理論: https://isa-afp.org/entries/Architectural_Design_Patterns.html
- [S21] Stonebraker, M., Zhou, Q., Kraft, P., Li, Q. "Consistency and Correctness in Data-Oriented Workflow Systems", CIDR 2026. https://www.vldb.org/cidrdb/papers/2026/p9-stonebraker.pdf
- [S22] Ehtesham, A., Singh, A., Gupta, G.K. ほか "A survey of agent interoperability protocols: MCP, ACP, A2A, ANP", arXiv:2505.02279 (2025-05-04). https://arxiv.org/abs/2505.02279 (本体が citation メタタグで実在確認)
- [S23] Schlapbach, A. "Formal Semantics for Agentic Tool Protocols: A Process Calculus Approach", arXiv:2603.24747 (2026-03-25). https://arxiv.org/abs/2603.24747 (本体が実在確認)
- [S24] Li, Y., Hou, P., Yoshida, N. "Specification-Guided Synthesis of Deadlock-Free Communication Protocol Refinements with Large Language Models", arXiv:2607.27964 (2026-07-30). https://arxiv.org/abs/2607.27964 (本体が実在確認)
- [S25] Salemi, A., Parmar, M., Goyal, P. ほか "LLM-Based Multi-Agent Blackboard System for Information Discovery in Data Science", arXiv:2510.01285 (2025-09-30). https://arxiv.org/abs/2510.01285 (本体が実在確認)

### リポジトリ (すべてコミット SHA で固定)

- icyphy/ptII@`5dc2aa15edd05efb9d097f1353edb04a21e2358a`
- akka/akka@`e2441c7ae1b0e500ac30a121863cc7e54d919a79`
- dotnet/orleans@`0bfd95e8561699b3bb7c619b0b0d2378d84395bc`
- scribble/scribble-java@`723660a81ee40a094163d9c63a93778cbc97af6e`
- nuscr/nuscr@`9a9631a9d8924f2515144b01c8160805bf0e6fc6`
- ekiwi/jade-mirror@`2723c7b52269c34d7f2ef366816776bcbcd90b8f` (**非公式ミラー**。JADE 4.3.3 相当。公式 jade.tilab.com は TLS 証明書エラーで未取得)
- Apache River: SVN `svn.apache.org/repos/asf/river/jtsk/tags/3.0.0/` (github.com/apache/river は HTTP 404、Apache Attic 移管)
- a2aproject/A2A@`afda8316c64951a2ecb2a0d3d10867405d2b4095` / a2aproject/a2a-python@`9a00f9b91fd4e85019c8983278a39d65f67fdd04`
- modelcontextprotocol/modelcontextprotocol@`24efd6e7cbd7a074e6b3b781eb370891df40afad` / typescript-sdk@`60321700871029401a2e3bed8fdf4f02c9ec3331`
- temporalio/api@`1c27468c756fc8abc800235c33b74c6eba638c88` / sdk-python@`eb642b14947bd8bcdf8816cffb6a63869803f5c6` / sdk-core@`0eb03f213079e539c18fb738c32a70bc191aadf4`
- dbos-inc/dbos-transact-py@`a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59`
- restatedev/restate@`d5425f5bfae4024f4d26bab447bc8e6c6db08bfa` / sdk-shared-core@`bcdf52777955b36bed611483abd227db03b9a09c`
- apache/kafka@`869426ff7bb7198f595414063408b678cb2a4d58` / confluentinc/schema-registry@`ff2583dc173630d09a91f410e29091d6b2591ca4`
- etcd-io/raft@`3cbf6a74be3fa392edd8b64253fcd11c3ce5649b`
- choral-lang/choral@`5fec88ef2cd1773585eab86dbfc585db1c74f07e`
- gshen42/HasChor@`f1d269ae16cb4d67cb61a4d47b30967eb7799e4e`
- lsd-ucsc/ChoRus@`8c6e0372f100fc30a1d5a9bd8d810288e0d584a6`
- FoundationAgents/MetaGPT@`11cdf466d042aece04fc6cfd13b28e1a70341b1f`
- microsoft/autogen@`027ecf0a379bcc1d09956d46d12d44a3ad9cee14`
- langchain-ai/langgraph@`aa742fb31e2827d569b843e3600aeda2e0528e4b`
- openai/openai-agents-python@`9415f7e1452d507420c64893d820869637656c84`
- woped/WoPeD@`65fef37ad2bea141a8c1f4f574d50b6a3a693a39`
- pm4py/pm4py-core@`24a3bf610aea6ecc4938b1864b3ad71fcfb82084`
- hlisdero/lola@`fe5f1aecb6ff8a193bd450299bd75e2ceb9a3bc5` (**非公式ミラー**)
- CSPforJAVA/jcsp@`6a089f975876307419303b9443ee002aa4805839`
