# 第4本 — ログストア

作成・取得日: 2026-09-20 JST。物差しは `docs/requirements.md`、コミット `cdd90e945d938769aefa17a2b8de3236647f6bdc`（`git log -1 --format=%H -- docs/requirements.md` で確認）。設計・製品選定ではなく、要件に対する調査記録である。

一次資料を担当調査者自身が取得して読んだ箇所を「本体確認」とする。本書の外部資料はすべて本体確認。第1本の結論だけを引く箇所は「報告」と明記する。引用の逐語・URL・SHA・path:lineは [根拠集](04-log-store.evidence.md) に全件記録した。親による独立再取得の範囲は `04-review.md` に分離する。

## 1. 結論

ブリーフの3つの問いへの回答は次のとおり。

1. 書き込み時にスキーマを強制する実装は、何を検査するか、どの経路を通るかを限定すると存在する。Pulsarはbrokerでschema登録・互換性を検査するが、確認した標準publish経路は各payloadのschema適合を検査していない。Pulsarの `AutoProduceBytesSchema` とConfluentのJSON serializerはclient側で実payloadを検査する経路を持つ。IcebergのSpark writerは書き込むdatasetのschemaを検査する。Temporalはserverが種別と対応attributesを持つHistoryEventを構築して順序付き履歴へ追加する。いずれも「任意の書き手が送る任意のeventを、ストアの全書込経路で種別別schemaに照らして拒否する」と同じではない。[P2][P3][P4][S2][I2][I3][T2][T3]
2. 「何が記録され、欠落が何を意味するか」を定義した例はある。Certificate TransparencyはSCTを発行した提出物の期限内収録、PeerReviewは正しいnodeと送受信したmessageの記録と観測可能な逸脱の検出、SLiCはcrashで失いうる範囲と不正な削除の区別を定める。Automergeは既知のdocument内のactor別連番欠落を拒否する。一方、どれも「観測できなかった任意の実行器の内部eventまで存在を知り、欠落を検出する」という保証ではない。第1本の「event streamの完全性に抽象が無い」という報告は、この限定を入れて更新する必要がある。[C0][C6][C7][L5][L6][M1][M2]
3. 実行が終わる前の外部出力と共通形式を同時に実現する実装はある。OpenTelemetry Logsの共通LogRecordと `on_emit`、OpenAI Agents SDKの共通StreamEventとasync iterator、TemporalのHistoryEventとlong-pollが該当する。ただし対象は、それぞれ計装済みlog、SDKが観測・生成したrun item、Temporalのworkflow履歴である。PDAのすべての実行器について、受け取った指示・ツールと結果・出した判断を同形式で漏れなく得るところまで、この実装だけで満たすとは確認していない。[O1][O2][O3][A1][A3][A4][T4]

本調査では、限定した性質について抽象・不変量・実装の対を9件確認した。以下の「対」はPDAのコアを完成させる部品という意味ではない。型の一致、履歴の順序、追記中の読取り、記録の完全性、改変検知は別の性質であり、対が成立する範囲を明記する。

## 2. 評価の境界

要件3.1は、ログストアをevent streamの書込先、可視化と監査の読取先と定める。A5は実行器ごとの読取側個別処理を不要にすること、A8はevent streamを根拠に「言っていることとやったこと」の差を検出することを求める。ストア自身が分類を強制するとは定めていない。

ブリーフの「分類は書き込み時にストアが強制する必要がある」は要件本文ではなく、責務配置についての推論である。ラッパーとコアの受け入れ検査で同じ形式に揃えたeventだけを記録し、読む側が共通形式だけを見る場合も、A5の文面とは矛盾しない。後から実行器別に分類し直すことと、記録前に共通形式へ揃えることを区別する。どの位置へ置くかは本調査で決めない。

本書ではschemaに関する検査を次の4つに分ける。

1. schema自体の登録可否と旧版との互換性。
2. recordに付いたschema IDと登録済みschemaの対応。
3. 個々のpayloadがそのschemaに適合するか。
4. 記録するeventの種別と、それに対応するpayloadの形の一致。

種別別の形を定めても、自由文を持つfieldの意味内容を分類する必要はない。第1本のLindaに関する一般化は報告として読む。本書では元論文を再取得していないので、その一般化を不可能性の証明には使わない。今回確認したJSON schema検査や型付きHistoryEventは、形を検査することと文字列の意味を判定することが別であることを示す。[S2][T2]

「満たす」は契約項目または受け入れ条件全体を確認した場合、「一部」はその条件を支える性質だけを確認した場合、「満たさない」は当該対だけではその条件を提供しない場合とする。対象外の機構を製品全体の欠陥とは評価しない。A6にはスマホUIまで含まれるため、ログ機構だけで「満たす」とは判定しない。

## 3. 要素ごとの対

表内の契約は「能力の宣言 / 仕事の受け取り / 成果の返却 / event stream」の順、受け入れ条件は「A5 / A6 / A8 / A9」の順に記す。判定語は「満たす / 一部 / 満たさない」に統一する。実装の完全な位置と固定SHAは4節および根拠集に示す。

| 対象 | 抽象 | 不変量・保証する性質（逐語引用は根拠集） | 実装（強制箇所） | 契約との対応 | A5/A6/A8/A9との対応 | 足りないもの |
|---|---|---|---|---|---|---|
| Pulsarのschema付きtopic | Pulsar schema仕様・PIP-43 | schema登録を互換性検査に基づける [P1] | `ServerCnx.tryAddSchema` の登録/拒否、clientの `AutoProduceBytesSchema.encode`、persistent topicのledger追加、Reader [P2][P3][P4][P5][P6][P7] | 満たさない / 一部 / 一部 / 一部 | 一部 / 一部 / 満たさない / 満たさない | brokerでの全payload検査、実行器共通event語彙、観測漏れの検出。schema互換性の対として成立 |
| Icebergのwrite schema検査 | format specificationとwrite schema検査API仕様 | 設定が有効なら、必須fieldへのoptional値の書込みを許さない [I4] | `SparkWriteBuilder.validateOrMergeWriteSchema` → `TypeUtil.validateWriteSchema` → 不適合例外 [I2][I3] | 満たさない / 満たさない / 満たさない / 一部 | 一部 / 一部 / 満たさない / 一部 | event単位の発生順序と追記購読、任意bytesの強制検査、監査eventの意味。table書込schema検査の対として成立 |
| TemporalのWorkflow History | History Serviceのevent sourcing仕様 | Workflow Execution HistoryをHistory Eventの線形な列として保持する [T1] | EventFactory、EventStoreのID割当・追加、GetWorkflowExecutionHistoryのlong-poll [T2][T3][T4] | 満たさない / 一部 / 一部 / 一部 | 一部 / 一部 / 一部 / 一部 | Activity内部のツール・判断の観測、すべての開始/再試行eventの即時出力、自己改変理由。workflow履歴について成立 |
| Restateのjournal | 現行service protocolのjournal mismatch定義 | journalと実行コードの不一致を再生エラーとして扱う [R1] | replay commandの型decode・header比較、entry indexに基づく保存 [R2][R4] | 満たさない / 一部 / 一部 / 一部 | 一部 / 一部 / 一部 / 一部 | syscall外部の内部行為、全payload内容の一致、共通監査購読契約。現行protocolの再生照合について成立 |
| OpenTelemetry Logs | Logs Data ModelとLogs SDK仕様 | LogRecordをemitしたthread上で同期的にprocessorを呼ぶ [O2] | LogRecordを共通形に保持し、SimpleLogRecordProcessorがemit時にexport [O3][O4] | 満たさない / 満たさない / 満たさない / 一部 | 一部 / 一部 / 一部 / 満たさない | 名前別payload schemaの強制、永続性・全件性・実行器の全event観測。共通封筒とemit時の出力について成立 |
| CTのappend-only証明 | RFC 6962 §2.1.2、§3 | Merkle consistency proofによりtreeの追記性を検証する [C0] | Trillian sequencer/proof生成、transparency-dev/merkleのroot照合 [C1][C2][C3][C4] | 満たさない / 満たさない / 満たさない / 一部 | 満たさない / 一部 / 一部 / 満たさない | 未提出eventの存在、PDAのevent種別、行為の正しさ。過去の公表済み内容の保持を検証する対として成立 |
| Agents SDKのrun item stream | SDKのStreaming仕様 | 定められたevent名の集合を用いる [A1] | `stream_step_items_to_queue` の型別構築と `stream_events` のqueue読出 [A3][A4] | 満たさない / 一部 / 一部 / 一部 | 一部 / 一部 / 一部 / 満たさない | 永続ログストア、任意外部入力に対するLiteralの実行時検証、全ランタイムの統一。SDK内部のevent生成・出力について成立 |
| Gitの変更履歴 | commit/tree/parentによる履歴、git-revert仕様 | 取消しを新しいcommitとして記録する [V1] | `write_commit_tree` のtree/parent/作者等の記録、sequencerのrevert処理 [V2][V3] | 満たさない / 満たさない / 満たさない / 一部 | 満たさない / 一部 / 一部 / 一部 | 自己改変の根拠の必須記録、実行への反映履歴、全eventの追記・監査。変更と取消しの履歴について成立 |
| Automergeの変更履歴 | Binary Document Formatのactor別連番 | 既知document内でactorの変更列に欠番があれば中止する [M1] | collectorの `seq[actor] + 1` 比較と `ChangesOutOfOrder` [M2] | 満たさない / 満たさない / 満たさない / 一部 | 一部 / 一部 / 一部 / 一部 | 未到着suffixの検出、実行器event、自己改変理由と取消しの業務上の意味。既知document内の変更列について成立 |

## 4. 対の確認結果と制約

### 4.1 PulsarとSchema Registry — 接続時の互換性とpayload検査は異なる

Pulsarの固定コミットは `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。`pulsar-broker/src/main/java/org/apache/pulsar/broker/service/ServerCnx.java:4259-4275` はschemaがあれば登録へ渡し、schemaが無くenforcementが有効なら拒否する。この分岐で比較しているのは各eventの中身ではない。公式のschema説明もmessagesがunstructured byte arraysとして保存されることを明記する。[P2][P0]

標準publish経路の `pulsar-broker/src/main/java/org/apache/pulsar/broker/service/Producer.java:232-304` はchecksumと暗号metadataを確認して `headersAndPayload` を渡す。`pulsar-broker/src/main/java/org/apache/pulsar/broker/service/persistent/PersistentTopic.java:734-744` はこれをledgerへ追加する。ここにevent種別ごとのpayload decode/validationは確認できない。interceptorの呼出箇所はあるが、追加の実装を置けることを既存の強制保証とは数えない。[P3][P6]

一方、`pulsar-client/src/main/java/org/apache/pulsar/client/impl/schema/AutoProduceBytesSchema.java:86-100` は `requireSchemaValidation` のときにpayloadを検査する。`pulsar-client/src/main/java/org/apache/pulsar/client/impl/ReaderImpl.java:195-207` はconsumerから次のmessageを読み出す。Reader APIはmessage到着まで待てるので、producerの実行終了は必要ない。ただしこの確認から複数partition・複数実行器の実際の発生時刻に基づく全順序までは導けない。[P4][P5][P7]

Confluent Schema Registry `ff2583dc173630d09a91f410e29091d6b2591ca4` の `core/src/main/java/io/confluent/kafka/schemaregistry/storage/KafkaSchemaRegistry.java:527-537` はschema登録時の旧版との互換性を調べる。JSON serializerの `json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/AbstractKafkaJsonSchemaSerializer.java:199-252` は実payloadを `schema.validate` へ渡し、不適合ならSerializationExceptionにする。しかし `KafkaJsonSchemaSerializerConfig.java:35-39` の `json.fail.invalid.schema` は既定falseである。producer経路の条件付き保証を、Kafka broker全体の保証とはしない。[S1][S2][S3]

Confluent Platform 7.9の公式説明も、broker-side Schema ID ValidationはIDとsubjectの登録関係を確認し、data introspectionをしないと明記する。brokerの非公開実装を検査したとは主張しない。この製品仕様は今回本体確認した事実であり、第1本のKafka `ByteBuffer` に関する報告に依存せず区別できる。[S0]

### 4.2 Iceberg — 書込datasetのschemaを確認するがeventの順序付き購読ではない

固定コミットは `96d9880d6f8748b1b2f92aea0946b5505b550029`。`spark/v4.0/spark/src/main/java/org/apache/iceberg/spark/source/SparkWriteBuilder.java:200-233` がSparkのdataset schemaをtable schemaと比較し、`api/src/main/java/org/apache/iceberg/types/TypeUtil.java:508-562` が型・nullability等の不一致で例外にする。`TypeUtil.java:499-505` のAPI仕様は `checkNullability` がtrueのときrequired fieldにoptional値を書けないと定める。`checkNullability` と `checkOrdering` は条件に含まれるので、設定を無視した絶対保証にはしない。[I2][I3][I4]

`format/spec.md:82-106` のsequence numberはcommit/snapshotとdata/delete fileの相対的な新旧を表す。これは個々の実行器eventの発生順序を記録するsequenceではない。snapshotを読み直すことと、実行中のeventを一件ずつ購読することも異なる。tableへのschema付き書込みは対として成立するが、問い1と3を一体で満たすログストアとは評価しない。[I1]

### 4.3 Temporal — 構築された履歴の順序と、観測した全出来事は異なる

serverの固定コミットは `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。`service/history/historybuilder/event_factory.go:31-103` はWorkflowExecutionStartedという種別と対応するattributesを組にして生成する。`service/history/historybuilder/event_store.go:58-103` はIDを増分し、履歴へ追加し、workflow終了後の追加を拒む。成立根拠はこの構築経路である。保存ストアへ任意のHistoryEventを書ける全経路を網羅して、未知enum数値や種別とattributesの不一致を拒否することまで証明したものではない。[T2][T3]

`service/history/api/getworkflowexecutionhistory/api.go:220-258` は `wait_new_event` と実行中のcontinuation tokenを扱うので、workflow完了前から履歴を読む経路は実在する。一方、`service/history/workflow/mutable_state_impl.go:4499-4516` はretry policyのあるActivity開始をtransientとして、その時点ではHistoryEventを作らない。完了処理の `:4610-4618` で開始eventを補ってから完了eventを加える。この履歴が「Activity実行中の全出来事を即時に出した記録」とは限らない。[T4][T5][T6]

公式architecture仕様の `docs/architecture/history-service.md:113-124` は復元対象をworkflow stateに限定し、Reset等ではbranchを持つことも明記する。`:318-322` は最新event IDとMutable Stateで履歴の有効性を結び付ける。Temporal内部のstate遷移を記録しても、Activityが外部で行ったtool callや判断そのものを知る根拠は自動的には増えない。[T1][T7]

### 4.4 Restate — 期待するcommandと既知journalの照合

現行server/protocolは `d5425f5bfae4024f4d26bab447bc8e6c6db08bfa`、SDK shared coreは `bcdf52777955b36bed611483abd227db03b9a09c`。前者の `service-protocol/dev/restate/service/protocol.proto:150-164` にjournalとコードの不一致を示すJOURNAL_MISMATCHがある。後者の `src/vm/transitions/journal.rs:917-989` は再生列の先頭を取り出し、期待したmessage型にdecodeし、command indexに対応するheaderを比較し、不一致をエラーにする。[R1][R2]

serverの `crates/worker/src/partition/state_machine/entries/mod.rs:362-406` はjournal lengthを増分し、entry indexを付けて保存し、invocation statusも更新する。同所の `debug_assert_eq!` はreleaseでの不正入力拒否を保証する根拠には数えない。保存の位置と順序を確認したのであり、debug assertionを強制箇所と取り違えない。[R4]

`src/lib.rs:24-45` の `unstable_serialization` は再生時のpayload bytes比較を省略する選択を持つ。したがって再生不一致の検出と、全payloadを常に同じbytesとして監査することは異なる。今回確認したjournal保存・再生だけでは、監査UIへの追記購読APIまで確認したことにはならない。[R3]

旧 `restatedev/service-protocol@eaebc104834cf3405267ec180912b0e295340501` のprose仕様は、全state transitionをInvocation journalに記録すると述べるが、READMEはarchive/移転を明記している。旧版のその文言を現行v7の全遷移へ無条件に移すことはしない。表の対は現行protoの不一致定義と現行SDKの照合について成立させ、旧prose仕様は系譜の説明にだけ用いる。[R5][R6]

### 4.5 OpenTelemetryとGenAI — 共通形式、実行中出力、全件性を分ける

Logs/Trace仕様は `148f27606cf0352c11a314e7bf9eefa6bf88db86`、Python SDKは `5321c606f216c8262da949e85d46a18621484ea9`。`specification/logs/data-model.md:445-451` はEventNameをstringとし、event構造を一意に識別することをSHOULDで求める。Pythonの `opentelemetry-api/src/opentelemetry/_logs/_internal/__init__.py:97-121` はbodyとevent_nameを保持するが、名前別のpayload schemaを検査する処理ではない。[O1][O4]

`opentelemetry-sdk/src/opentelemetry/sdk/_logs/_internal/export/__init__.py:200-238` は `on_emit` から共通LogRecordをexportする。これはrun終了前の出力を支える。一方、同SDKの `trace/export/__init__.py:116-127` はSpanを `on_end` でexportし、sampledでなければ返る。親runが長い場合に、そのSpan自体が終了前から逐次読めるという保証にはならない。[O2][O3][O6]

`specification/trace/sdk.md:395-399` のDROPは記録しないことを認め、Logs SDK `:551-555` はbatch queue上限を超えたlogのdropを定める。Dapper原論文p.7 §4.4も低頻度の出来事をsamplingで見逃しうると述べる。samplingされたtraceにeventが無いことから、その行為が無かったと判定することはできない。全件samplingに変えるだけでも、未計装・export失敗・queue欠落が解消したことにはならない。[O5][O7][L4]

GenAI規約は本取得時点で別repositoryへ移っていた。旧repository `d0472f4ae331e8ef01aa571fe024d0d6a1a9b5e1` の `docs/gen-ai/gen-ai-events.md:5-11` から移転先をたどり、`open-telemetry/semantic-conventions-genai@c88d504ab3d9879f8e50d3cc87e69775e11db234` を取得した。[G1]

移転先には `execute_tool`、agent、input/output messages等の語彙とmessages用JSON schemaへの規約がある。ただし `docs/gen-ai/README.md:7` はDevelopment、`model/gen-ai/spans.yaml:87-93` では入出力messagesはopt_in、`docs/gen-ai/gen-ai-agent-spans.md:127-139` ではoperation nameにcustom valueを許す。`:380-412` のJSON schema準拠は計装側への要求であり、汎用OTel storeがそれを検査する実装は今回未確認である。[G2][G3][G4][G5]

### 4.6 CTとTrillian — 保存後の改変と、提出されなかった出来事

Trillianは `5061cfc7eb9ada638e810414577deb6575d89eef`、Merkle検証ライブラリは `a490ef305a5bc3e556495fd824681d090d832d27`。`google/trillian/log/sequencer.go:343-390` は既存のcompact rangeから新しいleafを追加してrootとsizeを作り、`server/log_rpc_server.go:394-408` はconsistency proofを構築する。`transparency-dev/merkle/proof/verify.go:36-51,96-104` はproofから計算したrootが期待値と一致するかを検査する。[C1][C2][C3][C4]

この対の直接の抽象はRFC 6962である。実装中の `rfc6962` をRFC 9162準拠の証明とは扱わない。RFC 6962 §2.1.2の不変量は公表済みの古いtreeのprefixが新しいtreeでも同一であること。§3はSCTを出したcertificateをMMD内に収録する義務を定める。提出の証拠と期限があるから、約束した記録の欠落を検査できる。[C0][C6]

Trillianは汎用leaf storeの上に用途別personalityを必要とする。ログが実行器内部を見ていない場合、そもそもleafとして提出されなかったtool callの存在をMerkle proofから導くことはできない。またRFC 9162 §1は、相手ごとに矛盾したviewを見せる問題を明記する。既知rootの保持・比較条件を省いて「欠落は必ず分かる」とは書けない。[C5][C7]

### 4.7 Agents SDKとA2A — 見えるeventの粒度

Agents SDKの固定コミットは `9415f7e1452d507420c64893d820869637656c84`。`src/agents/stream_events.py:23-48` のRunItemStreamEventは11値のLiteralを持つ通常のdataclassである。Literalは型注釈であり、それだけで外部入力の値を拒否する検証器ではない。実際の標準値生成は `src/agents/run_internal/streaming.py:33-65` で、RunItemの型からtool_called/tool_output等を選びqueueに入れる。`src/agents/result.py:1013-1042` はqueueから取り出してyieldする。[A2][A3][A4]

このためSDKの通常経路では実行中にtool callと結果を区別して受け取れる。ただしToolApprovalItemとCompactionItemにはstreamに出さない分岐があり、未知itemもwarning後に出さない。公開仕様のrun itemの範囲と、内部処理全体を同一視しない。またこのqueueとiteratorを永続ログストアとは数えない。[A1][A3]

A2A `afda8316c64951a2ecb2a0d3d10867405d2b4095` の `specification/a2a.proto:790-802` はtask、message、status_update、artifact_updateを標準候補に持つ。message等に独自内容を入れる余地と、tool call/tool resultを共通の独立event種別として定義していることは別である。A2A単独の定義から、監査が実行器別解釈なしに内部行為を読めるとは判定できない。[A5]

Protocol Buffersの公式資料 `4b88f52a8f830d4b4fbdad161dee33618ebc617f` の `content/programming-guides/enum.md:81-85` はproto3のopen enum、`proto3.md:1221-1229` はoneofを高々一個と説明する。A2AのoneofやTemporalのenum宣言だけで、未知値の拒否や必須値の存在が実行時に保証されるという第1本由来の読み方は採用しない。[B1][B2]

### 4.8 GitとAutomerge — A9の「前後を残して戻せる」の範囲

Git `d38352cd43ab9745686d697872408bc3249a153f` の `commit.c:1686-1723` はtree、parent、作者/committerとmessageを記録する。`sequencer.c:2398-2423` はrevertでcommitからparentへの逆向きの差分を扱う。`Documentation/git-revert.adoc:17-23` はその取消しを新しいcommitで記録することを定める。したがって記録された定義の前後を比較し、変更を打ち消す履歴はあるが、commit messageが自己改変の根拠を必ず含むとは保証しない。[V1][V2][V3]

具体的なworkflow定義への適用例はn8nの公式文書 `n8n-io/n8n-docs@d6f969044f09a928e5d1459a080f6289b68d7be5` の `docs/administer/use-source-control-and-environments/push-and-pull-changes.md:85-94` にある。workflowを選んでGitへ記録する仕様である。ここは公式仕様のみを確認し、n8n本体の強制箇所は今回調べていない。選択してcommitできることから「自己改変の全件と判断根拠が自動記録される」とはしない。[V4]

AutomergeのBinary Document Format `e24b3077eaeabf6c7eef0111d0175be0885a898f` はactor別連番の欠落を拒否すると定める。実装 `4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903` の `rust/automerge/src/op_set2/change/collector.rs:917-934` が連番を確認してChangesOutOfOrderを返す。`rust/automerge/src/op_set2/change/batch.rs:1067-1082` は既知hashを再適用せず、同じactor/seqの異なる変更を拒否する。[M1][M2][M3]

これは、読んだdocumentの既知の変更列の整合性である。まだ受け取っていない最後の変更が存在することや、記録されなかったworkflow判断を検出する不変量ではない。またCRDTのmergeが成立することから、業務上の取消しが自動的に定義されるわけではない。A9は双方とも一部と判定する。

## 5. 完全性・欠落・順序の意味

問い2では、何を母集団にして「欠落」と呼ぶかが決定的である。今回確認した定義は次のように異なる。

| 対象 | 「必ずある」とする対象 | 欠落を判定する前提 | 欠落が意味しないこと |
|---|---|---|---|
| CT | SCTを発行したcertificate | SCT、MMD、検証対象root/proof、正しい検証者 | そもそも提出されなかった実行器内部eventが無かったこと |
| PeerReview | 正しいnodeと送受信したmessage、および参照state machineとの観測可能な不一致 | 決定論的state machine、参照実装、署名、正しいnode/witness、最終的な通信 | 全内部行為を観測済みであること、無応答が即座に不正の証明になること |
| SLiC | logging algorithmへ入力済みのeventと、許容されるcrash損失範囲 | 初期検証状態、cache容量等のモデル、暗号上の前提 | 観測されずLogへ渡されなかったeventの存在 |
| Temporal / Restate | 対象runtimeが履歴/journalへ入れたstate遷移・command | runtimeの制御下にある操作、既知の履歴、再生規則 | 外部ツールやLLM内部の全行為の存在/不在 |
| Automerge | 読取り対象documentのactor別変更列 | actor識別と既知の連番/変更内容 | 未取得suffixや未作成changeの存在 |
| OTel / Dapper | 計装とsampling/filter/exportを通ったrecord | 計装範囲とsampling/drop条件が既知 | recordが無いことから行為が無かったと結論すること |

PeerReview原論文の§4.5（取得PDF p.6）は完全性を正しいnodeとの各message送受信に限定し、送信/受信の署名証拠を相手側へ渡す。§3.4（PDF p.4）の保証は、観測可能な故障について最終的にexposedまたはsuspectedになることである。§4.3（PDF p.5-6）では決定論的state machineと参照実装、正しいwitness等を前提とし、§6は非決定性への対応を要求する。A8に関係する抽象は存在するが、これを改変不能な任意のLLMランタイムへそのまま適用できるとは言えない。[L6]

SLiCのAlgorithm 4（取得PDF p.6）は、入力済みeventのうちcrashにより失ってよい範囲を計算し、それ以外の欠落を不正と判定する。cacheの前提を持つloggingのモデルであり、実行器の実際の行為集合を自動発見するモデルではない。[L5]

順序については、LamportのClock Condition（取得版p.560）は `a → b` なら `C(a) < C(b)` と定め、逆を保証しない。Matternの取得版p.127 Theorem 10はvector timeによって因果関係と並行を表す。いずれも、実行器内の発生順、観測時刻、ストアへの追記順、実行器間の因果順を同一とする根拠ではない。共通timestamp fieldがあることだけで、A6に必要な受け渡し関係の順序まで確定しない。[L2][L3]

KleppmannらのOLEPは、同じlogを購読する側に同じ更新列を同順で適用させ、複数のviewを整合させる。これは「可視化と監査が同じ記録を見る」ことに関係する抽象である。しかし、producerが必要なeventをすべて生成したという別の不変量を与えるものではない。[L1]

## 6. 片側だけ確認できたもの

| 対象 | 確認できた側 | 揃わない理由 | 契約4項目 / A5・A6・A8・A9 |
|---|---|---|---|
| PeerReview | 論文の抽象・完全性/正確性の条件 | 公式サイトにsource配布はある。今回は固定commitの実装強制箇所を取得・照合していない。「実装が存在しない」とはしない | 満たさない / 一部 / 一部 / 一部。A5=満たさない、A6=一部、A8=一部、A9=満たさない |
| SLiC | 論文のアルゴリズム・脅威モデル・解析 | 論文中の評価実装の記述は読めるが、再取得可能な固定commitの実装強制箇所は未確認 | 満たさない / 満たさない / 満たさない / 一部。A5=満たさない、A6=一部、A8=一部、A9=満たさない |
| Dapper | 原論文のspanモデル・sampling・Google内実装の説明 | Google内の実装を公開commitのpath:lineに対応させていない。OTel PythonをDapperそのものの実装とは呼ばない | 満たさない / 満たさない / 満たさない / 一部。A5=一部、A6=一部、A8=一部、A9=満たさない |
| Lamport / Mattern | 論文の順序・clockの抽象とアルゴリズム | 今回のログ実装にそれぞれの不変量を強制する同一実装箇所まで結び付けていない | 満たさない / 満たさない / 満たさない / 一部。A5=満たさない、A6=一部、A8=満たさない、A9=満たさない |
| A2AのStreamResponse | 標準schema・streamの外形 | 今回はA2A serverの永続ログ書込と入力拒否まで確認していない。proto宣言をその代用にしない | 一部 / 一部 / 一部 / 一部。A5=一部、A6=一部、A8=満たさない、A9=満たさない |
| GenAI意味規約 | 共通語彙とmessages用schema規約 | 汎用OTelの保存経路で、この意味規約の全payload検査を強制する実装を確認していない | 満たさない / 満たさない / 満たさない / 一部。A5=一部、A6=一部、A8=一部、A9=満たさない |
| n8nのworkflow Git記録 | 公式文書での具体的利用例 | workflowを保存する仕様は確認したがn8n本体の強制箇所は未確認 | 満たさない / 満たさない / 満たさない / 一部。A5=満たさない、A6=一部、A8=一部、A9=一部 |

## 7. 未発見と取得できなかった資料

「未発見」は本調査範囲での結果であり、存在しないとの結論ではない。

| 探索したもの | 検索語・当たった資料 | 到達点 |
|---|---|---|
| 任意の実行器について、指示・tool call/結果・判断の全件生成をラッパー外から保証する抽象と実装 | `"audit log" "completeness" "untrusted" "event" formal verification`、`"secure logging" "completeness"`、PeerReview、SLiC、CT、Temporal、Restate | 観測範囲と信頼条件を限定した完全性は発見。改変不能な任意の実行器に無条件の全件性を与える対は未発見 |
| Pulsar/Confluent broker標準経路での各payloadのschema適合拒否 | `schema payload broker validate content bytes`、`schema validation does not introspect data payload`、Pulsar ServerCnx/Producer/AutoProduceBytesSchema、Registry/JSON serializer、公式製品文書 | 登録互換性、ID確認、client側payload検査は分離できた。確認したbroker経路の全payload検査は未発見 |
| GenAI意味規約と名前別schemaを保存時に強制する汎用OTelストア | Logs SDK/Data Model、OTel PythonのLogRecord/processor、現行GenAI repository | 共通形式とschema規約はある。名前別payload検証を汎用保存先で強制する箇所は未発見 |
| A9の改変根拠を必須で記録し取消しへ結び付ける対 | `workflow Git version control rollback`、Git commit/revert、Automerge format/collector、n8n公式source control文書 | 定義の変更履歴の実装は発見。割り振り判断根拠と実行への適用まで同じ記録として強制する対は未発見 |

取得できなかった資料と、代替取得の結果は次のとおり。

1. `https://api.github.com/repos/temporalio/documentation/commits/HEAD` はHTTP 403（rate limit exceeded）。このrepositoryの未取得本文の主張は根拠に使わず、取得済みTemporal server内architecture文書と実装を用いた。
2. `https://martin.kleppmann.com/papers/opsets.pdf` はHTTP 200だがHTMLを返し、PDFとして読めなかった。OpSets本文の主張は使用しない。Automergeについては公式Binary Document Formatと固定実装を直接確認した。
3. `https://docs.n8n.io/source-control-environments/understand/git/` はweb取得でPage Not Foundを返した（web出力にHTTP番号は未提示）。該当ページの主張は使わず、公式n8n-docsの固定commitにあるpush-and-pull文書をHTTP 200で取得した。
4. Lamport、Dapper、MatternのPDFはwebツールの画像取得では取得不能の応答となった箇所があるが、原URLの直接取得はHTTP 200で成功した。保存したPDFをPopplerで画像化して引用ページを確認した。HTTP未取得の資料として主張を排除する対象ではない。

## 8. 第5本へ渡す問い

1. event streamの共通形式をラッパー・受け入れ検査・ストアのどこで成立させるかを要件の固定事項と取り違えず、各対の強制箇所と接続時の条件を照合できるか。
2. 実行器から実際に観測できる指示・tool call/結果・判断の範囲を、第3本のランタイム調査と対応させられるか。観測されなかった行為を「無かった」と解釈していないか。
3. 生成、受入れ、永続化、外部読取り、sampling/drop、欠落検知のそれぞれについて、どの一次資料が何を保証するかを区別したまま全体を評価できるか。
4. A9について、workflow定義の旧版へ戻すことと、改変の根拠・反映時点をevent streamに記録することの両方が、全体のどの既存実装で確認できるか。


<!-- 一次資料への参照定義 -->

[P1]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pip/pip-43.md#L67
[P2]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-broker/src/main/java/org/apache/pulsar/broker/service/ServerCnx.java#L4259
[P3]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-broker/src/main/java/org/apache/pulsar/broker/service/Producer.java#L232
[P4]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-client/src/main/java/org/apache/pulsar/client/impl/schema/AutoProduceBytesSchema.java#L86
[P5]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-client-api/src/main/java/org/apache/pulsar/client/api/Reader.java#L41
[S1]: https://github.com/confluentinc/schema-registry/blob/ff2583dc173630d09a91f410e29091d6b2591ca4/core/src/main/java/io/confluent/kafka/schemaregistry/storage/KafkaSchemaRegistry.java#L527
[S2]: https://github.com/confluentinc/schema-registry/blob/ff2583dc173630d09a91f410e29091d6b2591ca4/json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/AbstractKafkaJsonSchemaSerializer.java#L199
[S3]: https://github.com/confluentinc/schema-registry/blob/ff2583dc173630d09a91f410e29091d6b2591ca4/json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/KafkaJsonSchemaSerializerConfig.java#L35
[I1]: https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/format/spec.md#L82
[I2]: https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/api/src/main/java/org/apache/iceberg/types/TypeUtil.java#L508
[I3]: https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/spark/v4.0/spark/src/main/java/org/apache/iceberg/spark/source/SparkWriteBuilder.java#L200
[T1]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/docs/architecture/history-service.md#L113
[T2]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/historybuilder/event_factory.go#L31
[T3]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/historybuilder/event_store.go#L58
[T4]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/api/getworkflowexecutionhistory/api.go#L220
[T5]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/workflow/mutable_state_impl.go#L4499
[T6]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/workflow/mutable_state_impl.go#L4610
[T7]: https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/docs/architecture/history-service.md#L318
[R1]: https://github.com/restatedev/restate/blob/d5425f5bfae4024f4d26bab447bc8e6c6db08bfa/service-protocol/dev/restate/service/protocol.proto#L150
[R2]: https://github.com/restatedev/sdk-shared-core/blob/bcdf52777955b36bed611483abd227db03b9a09c/src/vm/transitions/journal.rs#L917
[R3]: https://github.com/restatedev/sdk-shared-core/blob/bcdf52777955b36bed611483abd227db03b9a09c/src/lib.rs#L24
[R4]: https://github.com/restatedev/restate/blob/d5425f5bfae4024f4d26bab447bc8e6c6db08bfa/crates/worker/src/partition/state_machine/entries/mod.rs#L362
[R5]: https://github.com/restatedev/service-protocol/blob/eaebc104834cf3405267ec180912b0e295340501/README.md#L1
[R6]: https://github.com/restatedev/service-protocol/blob/eaebc104834cf3405267ec180912b0e295340501/service-invocation-protocol.md#L14
[O1]: https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/logs/data-model.md#L445
[O2]: https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/logs/sdk.md#L402
[O3]: https://github.com/open-telemetry/opentelemetry-python/blob/5321c606f216c8262da949e85d46a18621484ea9/opentelemetry-sdk/src/opentelemetry/sdk/_logs/_internal/export/__init__.py#L200
[O4]: https://github.com/open-telemetry/opentelemetry-python/blob/5321c606f216c8262da949e85d46a18621484ea9/opentelemetry-api/src/opentelemetry/_logs/_internal/__init__.py#L97
[O5]: https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/trace/sdk.md#L395
[O6]: https://github.com/open-telemetry/opentelemetry-python/blob/5321c606f216c8262da949e85d46a18621484ea9/opentelemetry-sdk/src/opentelemetry/sdk/trace/export/__init__.py#L116
[O7]: https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/logs/sdk.md#L551
[G1]: https://github.com/open-telemetry/semantic-conventions/blob/d0472f4ae331e8ef01aa571fe024d0d6a1a9b5e1/docs/gen-ai/gen-ai-events.md#L5
[G2]: https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/docs/gen-ai/README.md#L1
[G3]: https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/model/gen-ai/spans.yaml#L87
[G4]: https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/docs/gen-ai/gen-ai-agent-spans.md#L127
[G5]: https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/docs/gen-ai/gen-ai-agent-spans.md#L380
[C1]: https://github.com/google/trillian/blob/5061cfc7eb9ada638e810414577deb6575d89eef/log/sequencer.go#L343
[C2]: https://github.com/google/trillian/blob/5061cfc7eb9ada638e810414577deb6575d89eef/server/log_rpc_server.go#L394
[C3]: https://github.com/transparency-dev/merkle/blob/a490ef305a5bc3e556495fd824681d090d832d27/proof/verify.go#L36
[C4]: https://github.com/transparency-dev/merkle/blob/a490ef305a5bc3e556495fd824681d090d832d27/proof/verify.go#L96
[C5]: https://github.com/google/trillian/blob/5061cfc7eb9ada638e810414577deb6575d89eef/README.md#L43
[A1]: https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/docs/streaming.md#L70
[A2]: https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/src/agents/stream_events.py#L23
[A3]: https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/src/agents/run_internal/streaming.py#L33
[A4]: https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/src/agents/result.py#L1013
[A5]: https://github.com/a2aproject/A2A/blob/afda8316c64951a2ecb2a0d3d10867405d2b4095/specification/a2a.proto#L790
[V1]: https://github.com/git/git/blob/d38352cd43ab9745686d697872408bc3249a153f/Documentation/git-revert.adoc#L17
[V2]: https://github.com/git/git/blob/d38352cd43ab9745686d697872408bc3249a153f/commit.c#L1686
[V3]: https://github.com/git/git/blob/d38352cd43ab9745686d697872408bc3249a153f/sequencer.c#L2398
[M1]: https://github.com/automerge/automerge-binary-format-spec/blob/e24b3077eaeabf6c7eef0111d0175be0885a898f/src/index.adoc#L509
[M2]: https://github.com/automerge/automerge/blob/4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903/rust/automerge/src/op_set2/change/collector.rs#L917
[M3]: https://github.com/automerge/automerge/blob/4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903/rust/automerge/src/op_set2/change/batch.rs#L1067
[P6]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-broker/src/main/java/org/apache/pulsar/broker/service/persistent/PersistentTopic.java#L734
[P7]: https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-client/src/main/java/org/apache/pulsar/client/impl/ReaderImpl.java#L195
[S0]: https://docs.confluent.io/platform/7.9/schema-registry/schema-validation.html
[P0]: https://pulsar.apache.org/docs/4.2.x/schema-overview/
[C0]: https://www.rfc-editor.org/rfc/rfc6962.txt
[C6]: https://www.rfc-editor.org/rfc/rfc6962.txt
[C7]: https://www.rfc-editor.org/rfc/rfc9162.txt
[V4]: https://raw.githubusercontent.com/n8n-io/n8n-docs/d6f969044f09a928e5d1459a080f6289b68d7be5/docs/administer/use-source-control-and-environments/push-and-pull-changes.md
[B1]: https://raw.githubusercontent.com/protocolbuffers/protocolbuffers.github.io/4b88f52a8f830d4b4fbdad161dee33618ebc617f/content/programming-guides/enum.md
[B2]: https://raw.githubusercontent.com/protocolbuffers/protocolbuffers.github.io/4b88f52a8f830d4b4fbdad161dee33618ebc617f/content/programming-guides/proto3.md
[L1]: https://martin.kleppmann.com/papers/olep-acm-queue.pdf
[L2]: https://lamport.azurewebsites.net/pubs/time-clocks.pdf
[L3]: https://www.vs.inf.ethz.ch/publ/papers/VirtTimeGlobStates.pdf
[L4]: https://research.google.com/archive/papers/dapper-2010-1.pdf
[L5]: https://eprint.iacr.org/2017/107.pdf
[L6]: https://people.mpi-sws.org/~druschel/publications/peerreview-sosp07.pdf

[I4]: https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/api/src/main/java/org/apache/iceberg/types/TypeUtil.java#L499
