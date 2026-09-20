# 第4本 ログストア — 根拠集

本文 `04-log-store.md` が正本。本書はその全引用位置を系譜ごとに記録する。取得日は全件 2026-09-20 JST。担当調査者が一次資料を取得して該当範囲を読んだものを「本体確認」とする。親による独立再取得の範囲は `04-review.md` が示す。

コードはコミットSHAに固定。RFC・論文・製品HTMLにはコミットがないため、版、取得日、取得バイト列のSHA-256で固定する。path:lineは固定したソースの行であり、HTMLを整形した後の行ではない。PDFは取得版のPDFページと本文の節を使い、引用ページは画像でも確認した。

## 1. コードと仕様の引用

<a id="p1"></a>
### P1 — 仕様は新規schema取得・登録を互換性検査に基づける。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pip/pip-43.md#L67)。`pip/pip-43.md:67-68`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `64ab70d42e196ba144b42bfabe20a75ed93aaa01f963dbe094b95bcbf45f2ea5`。

> built on top of compatibility check

<a id="p2"></a>
### P2 — schemaありは登録、無しでenforcedなら接続拒否。payloadの内容検査とは異なる。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-broker/src/main/java/org/apache/pulsar/broker/service/ServerCnx.java#L4259)。`pulsar-broker/src/main/java/org/apache/pulsar/broker/service/ServerCnx.java:4259-4275`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `16433f8a45e7586d818cbfa69c810363a959b7cbf66d28eb3e1a06251a81f037`。

> return topic.addSchema(schema, isReplicatorProducer);

<a id="p3"></a>
### P3 — 標準publish経路のchecksum・暗号metadata検査とbytes受渡し。独自interceptor追加とは区別する。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-broker/src/main/java/org/apache/pulsar/broker/service/Producer.java#L232)。`pulsar-broker/src/main/java/org/apache/pulsar/broker/service/Producer.java:232-304`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `58ac27c57c933c7630ef9576fb128f7b8f87b19dd9f7859818ea8b3997bad390`。

> topic.publishMessage(headersAndPayload, messagePublishContext);

<a id="p4"></a>
### P4 — requireSchemaValidationの条件下でclientのencodeがpayloadを検査する。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-client/src/main/java/org/apache/pulsar/client/impl/schema/AutoProduceBytesSchema.java#L86)。`pulsar-client/src/main/java/org/apache/pulsar/client/impl/schema/AutoProduceBytesSchema.java:86-100`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `5f4289f4aac2665bf524410997414026130e588ba4a7c56dd0e222cb0f66483d`。

> localSchema.validate(message);

<a id="p5"></a>
### P5 — 追記される次のmessageを待って読むAPI。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-client-api/src/main/java/org/apache/pulsar/client/api/Reader.java#L41)。`pulsar-client-api/src/main/java/org/apache/pulsar/client/api/Reader.java:41-49`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `130384fb6314cae7f6ce35ebef215aed58e54e9311c0f27e912e632ca35db980`。

> This method will block until a message is available.

<a id="s1"></a>
### S1 — schema登録時に旧版との互換性を検査。force等による例外がある。

本体確認。[一次資料](https://github.com/confluentinc/schema-registry/blob/ff2583dc173630d09a91f410e29091d6b2591ca4/core/src/main/java/io/confluent/kafka/schemaregistry/storage/KafkaSchemaRegistry.java#L527)。`core/src/main/java/io/confluent/kafka/schemaregistry/storage/KafkaSchemaRegistry.java:527-537`。

コミット: `ff2583dc173630d09a91f410e29091d6b2591ca4`。

取得内容 SHA-256: `50a0c87eb347455aacfdd1420838951da7a952e2ea578e5c1b7e42e38ca36912`。

> isCompatibleWithPrevious(config,

<a id="s2"></a>
### S2 — validate設定時のserialize経路で実データを検査し不適合をSerializationExceptionにする。

本体確認。[一次資料](https://github.com/confluentinc/schema-registry/blob/ff2583dc173630d09a91f410e29091d6b2591ca4/json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/AbstractKafkaJsonSchemaSerializer.java#L199)。`json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/AbstractKafkaJsonSchemaSerializer.java:199-252`。

コミット: `ff2583dc173630d09a91f410e29091d6b2591ca4`。

取得内容 SHA-256: `d2262a9eee37fe9929a85540e7d166a7baa7a50481e1b4fa4a1dabcd5ea0470f`。

> jsonNode = schema.validate(jsonNode);

<a id="s3"></a>
### S3 — JSON payload検査は既定で無効。

本体確認。[一次資料](https://github.com/confluentinc/schema-registry/blob/ff2583dc173630d09a91f410e29091d6b2591ca4/json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/KafkaJsonSchemaSerializerConfig.java#L35)。`json-schema-serializer/src/main/java/io/confluent/kafka/serializers/json/KafkaJsonSchemaSerializerConfig.java:35-39`。

コミット: `ff2583dc173630d09a91f410e29091d6b2591ca4`。

取得内容 SHA-256: `8a6680828f26f3a7e25d28ecfa4d3391794d49edf3b0eb582ad0e50ffd964e27`。

> FAIL_INVALID_SCHEMA_DEFAULT = false;

<a id="i1"></a>
### I1 — snapshot単位の順序とmetadata交換。個々のeventの発生順序ではない。

本体確認。[一次資料](https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/format/spec.md#L82)。`format/spec.md:82-106`。

コミット: `96d9880d6f8748b1b2f92aea0946b5505b550029`。

取得内容 SHA-256: `af9123ae77d68e76e99df9d6ab47d7771fad2bf5518e86b73712d69a76f4c1b1`。

> The relative age of data and delete files relies on a sequence number

<a id="i2"></a>
### I2 — write schemaの型・nullability・ordering不一致の例外。schema比較であり任意bytes全件検査ではない。

本体確認。[一次資料](https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/api/src/main/java/org/apache/iceberg/types/TypeUtil.java#L508)。`api/src/main/java/org/apache/iceberg/types/TypeUtil.java:508-562`。

コミット: `96d9880d6f8748b1b2f92aea0946b5505b550029`。

取得内容 SHA-256: `2019e74af7e71f32f783e81ec21f5c74bef927ec28b4316673104e50506b1fed`。

> throw new IllegalArgumentException(sb.toString());

<a id="i3"></a>
### I3 — Spark write経路でdataset schemaをtable schemaに照合する。

本体確認。[一次資料](https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/spark/v4.0/spark/src/main/java/org/apache/iceberg/spark/source/SparkWriteBuilder.java#L200)。`spark/v4.0/spark/src/main/java/org/apache/iceberg/spark/source/SparkWriteBuilder.java:200-233`。

コミット: `96d9880d6f8748b1b2f92aea0946b5505b550029`。

取得内容 SHA-256: `e91cacf8892eadb81d3dd7c1f49e04aeb5cfdb35cfb62059f2be73c51b34981a`。

> TypeUtil.validateWriteSchema(

<a id="t1"></a>
### T1 — Reset等によるbranchの例外、state再構築範囲も同所に明記。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/docs/architecture/history-service.md#L113)。`docs/architecture/history-service.md:113-124`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `78c073d00672c33fb339e6c01ca24487c1ea0a2573fea77aa88a3b19593ec7e2`。

> Workflow Execution History is a linear sequence of History Events

<a id="t2"></a>
### T2 — 型付きfactoryで種別と対応attributesを構築。protoの型宣言だけを根拠にしない。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/historybuilder/event_factory.go#L31)。`service/history/historybuilder/event_factory.go:31-103`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `ad7386927de66485b861d0b9ed6e24751b5638800c3bfbfdd808a7fc557ef298`。

> event := b.createHistoryEvent(enumspb.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED, startTime)

<a id="t3"></a>
### T3 — history内のID割当と追記。終了後追加はpanic、buffer分岐あり。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/historybuilder/event_store.go#L58)。`service/history/historybuilder/event_store.go:58-103`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `d09dde80387762a283466551faa447fc2ed80ff67fe35fa7ebb74b264f8d4cb8`。

> b.nextEventID++

<a id="t4"></a>
### T4 — 実行中の履歴増分をlong-pollする経路。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/api/getworkflowexecutionhistory/api.go#L220)。`service/history/api/getworkflowexecutionhistory/api.go:220-258`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `f489c690192becadd01ad01cec0b11af7f308cdfbdfe418c6eea9bcfb587213c`。

> isLongPoll := request.Request.GetWaitNewEvent()

<a id="t5"></a>
### T5 — retry policyがあるActivityは開始時にHistoryEventを作らない経路がある。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/workflow/mutable_state_impl.go#L4499)。`service/history/workflow/mutable_state_impl.go:4499-4516`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `cbd9f2a6fff6982ab97b471e04018a2baf070f6871ff76afb09cc900a856682e`。

> if !ai.HasRetryPolicy {

<a id="t6"></a>
### T6 — Activity完了イベント前にtransientな開始eventを追加。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/service/history/workflow/mutable_state_impl.go#L4610)。`service/history/workflow/mutable_state_impl.go:4610-4618`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `cbd9f2a6fff6982ab97b471e04018a2baf070f6871ff76afb09cc900a856682e`。

> ms.addStartedEventForTransientActivity(scheduledEventID, request.WorkerVersion)

<a id="t7"></a>
### T7 — 最新HistoryEvent IDとMutable Stateによる整合性。

本体確認。[一次資料](https://github.com/temporalio/temporal/blob/ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a/docs/architecture/history-service.md#L318)。`docs/architecture/history-service.md:318-322`。

コミット: `ea83bf5f6d85d2e9a6236e948bc56ef36d1aa24a`。

取得内容 SHA-256: `78c073d00672c33fb339e6c01ca24487c1ea0a2573fea77aa88a3b19593ec7e2`。

> only "valid" if it is in Mutable State

<a id="r1"></a>
### R1 — 再生journalと実コード不一致のprotocol上の失敗。

本体確認。[一次資料](https://github.com/restatedev/restate/blob/d5425f5bfae4024f4d26bab447bc8e6c6db08bfa/service-protocol/dev/restate/service/protocol.proto#L150)。`service-protocol/dev/restate/service/protocol.proto:150-164`。

コミット: `d5425f5bfae4024f4d26bab447bc8e6c6db08bfa`。

取得内容 SHA-256: `3ce5c3c57834ed59f348f15b930051ac982be04b8654e5c6b64f244bde31ce98`。

> cannot replay a journal due to the mismatch between the journal and the actual code

<a id="r2"></a>
### R2 — replaying時の先頭command取出し、型decode、indexに対応する比較と不一致例外。

本体確認。[一次資料](https://github.com/restatedev/sdk-shared-core/blob/bcdf52777955b36bed611483abd227db03b9a09c/src/vm/transitions/journal.rs#L917)。`src/vm/transitions/journal.rs:917-989`。

コミット: `bcdf52777955b36bed611483abd227db03b9a09c`。

取得内容 SHA-256: `1e4b17ce8a18452b4cadc8589a2d0511975216e36dddd0e446ffc671bdc3ef9a`。

> if !actual.header_eq(expected, ignore_payload_equality) {

<a id="r3"></a>
### R3 — 非決定的serialization指定ではpayload bytes同一性検査を省略できる。

本体確認。[一次資料](https://github.com/restatedev/sdk-shared-core/blob/bcdf52777955b36bed611483abd227db03b9a09c/src/lib.rs#L24)。`src/lib.rs:24-45`。

コミット: `bcdf52777955b36bed611483abd227db03b9a09c`。

取得内容 SHA-256: `2d1a19cab5612cb16d1df48353b231984270120337f7aade917f18f4c4563744`。

> If true, skip payload byte equality checks during replay.

<a id="r4"></a>
### R4 — entry indexに基づくjournal保存とstatus更新。debug_assertをproduction拒否と誤読しない。

本体確認。[一次資料](https://github.com/restatedev/restate/blob/d5425f5bfae4024f4d26bab447bc8e6c6db08bfa/crates/worker/src/partition/state_machine/entries/mod.rs#L362)。`crates/worker/src/partition/state_machine/entries/mod.rs:362-406`。

コミット: `d5425f5bfae4024f4d26bab447bc8e6c6db08bfa`。

取得内容 SHA-256: `0a6064953c72fad043f8b12db7ba9c98bff32d07e613f464e5fc048e5ab646e4`。

> journal_meta.length += 1;

<a id="r5"></a>
### R5 — 旧prose仕様は移転済。現行v7との完全一致の証明には使わない。

本体確認。[一次資料](https://github.com/restatedev/service-protocol/blob/eaebc104834cf3405267ec180912b0e295340501/README.md#L1)。`README.md:1-3`。

コミット: `eaebc104834cf3405267ec180912b0e295340501`。

取得内容 SHA-256: `54b2181411f66899f6be8a3a892f67afd81c0ac44b34a343dc8f04fa69a6e70f`。

> ARCHIVED:

<a id="r6"></a>
### R6 — 旧仕様が対象にするのはinvocation state machineの遷移。任意内部処理ではない。

本体確認。[一次資料](https://github.com/restatedev/service-protocol/blob/eaebc104834cf3405267ec180912b0e295340501/service-invocation-protocol.md#L14)。`service-invocation-protocol.md:14-22`。

コミット: `eaebc104834cf3405267ec180912b0e295340501`。

取得内容 SHA-256: `0d2a1c7fd70ebfc576cbc3b3a154af2e1163eebdcc6edffb35656fd3e2347e43`。

> Every state transition is logged in the _Invocation journal_

<a id="o1"></a>
### O1 — EventNameはstringでevent構造識別はSHOULD。共通封筒と固定schema検証は別。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/logs/data-model.md#L445)。`specification/logs/data-model.md:445-451`。

コミット: `148f27606cf0352c11a314e7bf9eefa6bf88db86`。

取得内容 SHA-256: `3ee2c391a5d3262130582df89a3dc5a5640d837d010734ea79458fe3ece31173`。

> This name SHOULD uniquely identify the event structure (both attributes and body).

<a id="o2"></a>
### O2 — LogRecord emit時のprocessor呼出。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/logs/sdk.md#L402)。`specification/logs/sdk.md:402-406`。

コミット: `148f27606cf0352c11a314e7bf9eefa6bf88db86`。

取得内容 SHA-256: `610e092e19b3cf85366fe4b28b9ebb671a12258025c000c5a6d48fcaa455ef3b`。

> method is called synchronously on the thread that emitted the `LogRecord`

<a id="o3"></a>
### O3 — SimpleLogRecordProcessorは実行終了を待たずemitごとに共通LogRecordを外へ出す。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-python/blob/5321c606f216c8262da949e85d46a18621484ea9/opentelemetry-sdk/src/opentelemetry/sdk/_logs/_internal/export/__init__.py#L200)。`opentelemetry-sdk/src/opentelemetry/sdk/_logs/_internal/export/__init__.py:200-238`。

コミット: `5321c606f216c8262da949e85d46a18621484ea9`。

取得内容 SHA-256: `d4fb8ea88d73d7831e6d8e0322a1cb6008823a9a80cb763b48110c9430a0bcf6`。

> self._exporter.export((readable_log_record,))

<a id="o4"></a>
### O4 — event name/bodyは保存されるが名前別JSON schemaをこのコンストラクタは検査しない。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-python/blob/5321c606f216c8262da949e85d46a18621484ea9/opentelemetry-api/src/opentelemetry/_logs/_internal/__init__.py#L97)。`opentelemetry-api/src/opentelemetry/_logs/_internal/__init__.py:97-121`。

コミット: `5321c606f216c8262da949e85d46a18621484ea9`。

取得内容 SHA-256: `8edbf0bf6cc20f78124d5847e19f9fa73b87b1a2ad3b21f6646324607758dce7`。

> self.event_name = event_name

<a id="o5"></a>
### O5 — sampling DROPは記録しないことが仕様内。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/trace/sdk.md#L395)。`specification/trace/sdk.md:395-399`。

コミット: `148f27606cf0352c11a314e7bf9eefa6bf88db86`。

取得内容 SHA-256: `fb59a77b27dfdbdeaf78bb6947f4a54881c43cefab6c563fce0c9c9a40ff3f56`。

> the `Span` will not be recorded

<a id="o6"></a>
### O6 — 標準SimpleSpanProcessorはon_endでsampledを検査してからexport。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-python/blob/5321c606f216c8262da949e85d46a18621484ea9/opentelemetry-sdk/src/opentelemetry/sdk/trace/export/__init__.py#L116)。`opentelemetry-sdk/src/opentelemetry/sdk/trace/export/__init__.py:116-127`。

コミット: `5321c606f216c8262da949e85d46a18621484ea9`。

取得内容 SHA-256: `ea5e93aa63c87733ec6cfe0cdbd7686668650a15c424b4cdd2f4281ac150cfef`。

> if not (span.context and span.context.trace_flags.sampled):

<a id="o7"></a>
### O7 — batch queue上限超過はdrop。欠落ゼロの永続監査を含意しない。

本体確認。[一次資料](https://github.com/open-telemetry/opentelemetry-specification/blob/148f27606cf0352c11a314e7bf9eefa6bf88db86/specification/logs/sdk.md#L551)。`specification/logs/sdk.md:551-555`。

コミット: `148f27606cf0352c11a314e7bf9eefa6bf88db86`。

取得内容 SHA-256: `610e092e19b3cf85366fe4b28b9ebb671a12258025c000c5a6d48fcaa455ef3b`。

> After the size is reached logs are

<a id="g1"></a>
### G1 — GenAI規約の移転先を確認。

本体確認。[一次資料](https://github.com/open-telemetry/semantic-conventions/blob/d0472f4ae331e8ef01aa571fe024d0d6a1a9b5e1/docs/gen-ai/gen-ai-events.md#L5)。`docs/gen-ai/gen-ai-events.md:5-11`。

コミット: `d0472f4ae331e8ef01aa571fe024d0d6a1a9b5e1`。

取得内容 SHA-256: `3b873322528382c2c9a28109d3e7067b764bb1e22230332abd392e91800335f0`。

> GenAI semantic conventions have moved to the

<a id="g2"></a>
### G2 — 移転先のGenAI規約の成熟度。

本体確認。[一次資料](https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/docs/gen-ai/README.md#L1)。`docs/gen-ai/README.md:1-9`。

コミット: `c88d504ab3d9879f8e50d3cc87e69775e11db234`。

取得内容 SHA-256: `4145af3ec45572af5e539b6c778019b3d82561f355995d2ec1ba14722b165f39`。

> [Development][DocumentStatus]

<a id="g3"></a>
### G3 — 入力と出力messagesはopt_in。

本体確認。[一次資料](https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/model/gen-ai/spans.yaml#L87)。`model/gen-ai/spans.yaml:87-93`。

コミット: `c88d504ab3d9879f8e50d3cc87e69775e11db234`。

取得内容 SHA-256: `27fbba77b611e3b4670ebe1a36f15da60b3b6e224762b3227e4748d9bab1e498`。

> - ref: gen_ai.input.messages

<a id="g4"></a>
### G4 — operation nameは既知語彙を列挙するが閉じたenumではない。

本体確認。[一次資料](https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/docs/gen-ai/gen-ai-agent-spans.md#L127)。`docs/gen-ai/gen-ai-agent-spans.md:127-139`。

コミット: `c88d504ab3d9879f8e50d3cc87e69775e11db234`。

取得内容 SHA-256: `8363cc776fa9acc09345411bb1e09c162b7df785925f35e072ab6093bd18ba97`。

> otherwise, a custom value MAY be used.

<a id="g5"></a>
### G5 — 入力messagesのschema規約はあるがstorageのvalidator実装とは別。

本体確認。[一次資料](https://github.com/open-telemetry/semantic-conventions-genai/blob/c88d504ab3d9879f8e50d3cc87e69775e11db234/docs/gen-ai/gen-ai-agent-spans.md#L380)。`docs/gen-ai/gen-ai-agent-spans.md:380-412`。

コミット: `c88d504ab3d9879f8e50d3cc87e69775e11db234`。

取得内容 SHA-256: `8363cc776fa9acc09345411bb1e09c162b7df785925f35e072ab6093bd18ba97`。

```text
Instrumentations MUST follow [JSON schema](/model/gen-ai/gen-ai-input-messages.json).
```

<a id="c1"></a>
### C1 — 既存compact rangeの末尾からleaf群を加えてrootとsizeを作る。

本体確認。[一次資料](https://github.com/google/trillian/blob/5061cfc7eb9ada638e810414577deb6575d89eef/log/sequencer.go#L343)。`log/sequencer.go:343-390`。

コミット: `5061cfc7eb9ada638e810414577deb6575d89eef`。

取得内容 SHA-256: `5520345ff99c1b8f05718facf774873b81370d43a0dc7e8b4f40d1e651c3f8cf`。

> tx.SetMerkleNodes(ctx, targetNodes)

<a id="c2"></a>
### C2 — consistency proof生成。GetLeavesByRangeはintegration前のqueued leafを見せない。

本体確認。[一次資料](https://github.com/google/trillian/blob/5061cfc7eb9ada638e810414577deb6575d89eef/server/log_rpc_server.go#L394)。`server/log_rpc_server.go:394-408`。

コミット: `5061cfc7eb9ada638e810414577deb6575d89eef`。

取得内容 SHA-256: `d32286cdc96eba58a5abb19242ae579a39bc2772c20a89543cdeda415b6fac27`。

> proof.Consistency(firstTreeSize, secondTreeSize)

<a id="c3"></a>
### C3 — inclusion proofから再計算したrootを既知rootと照合。

本体確認。[一次資料](https://github.com/transparency-dev/merkle/blob/a490ef305a5bc3e556495fd824681d090d832d27/proof/verify.go#L36)。`proof/verify.go:36-51`。

コミット: `a490ef305a5bc3e556495fd824681d090d832d27`。

取得内容 SHA-256: `1cc3a995d81121d069fbf3dde41b6bcf7f1fe2e455ba15e3a7eb55834e11c476`。

> return verifyMatch(calcRoot, root)

<a id="c4"></a>
### C4 — consistency proofを二つのrootとtree sizeに対して検証。

本体確認。[一次資料](https://github.com/transparency-dev/merkle/blob/a490ef305a5bc3e556495fd824681d090d832d27/proof/verify.go#L96)。`proof/verify.go:96-104`。

コミット: `a490ef305a5bc3e556495fd824681d090d832d27`。

取得内容 SHA-256: `1cc3a995d81121d069fbf3dde41b6bcf7f1fe2e455ba15e3a7eb55834e11c476`。

> return verifyMatch(hash2, root2)

<a id="c5"></a>
### C5 — 任意アプリはpersonalityが必要。CT証明を任意event完全性に一般化しない。

本体確認。[一次資料](https://github.com/google/trillian/blob/5061cfc7eb9ada638e810414577deb6575d89eef/README.md#L43)。`README.md:43-58`。

コミット: `5061cfc7eb9ada638e810414577deb6575d89eef`。

取得内容 SHA-256: `7187a64f790a3dad34f12fe64502b24addebae53d0419026b39909a0fb307fb8`。

> Note that Trillian requires particular applications to provide their own

<a id="a1"></a>
### A1 — 公開streaming仕様の有限な標準event名。

本体確認。[一次資料](https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/docs/streaming.md#L70)。`docs/streaming.md:70-90`。

コミット: `9415f7e1452d507420c64893d820869637656c84`。

取得内容 SHA-256: `945de2f5196c0a9fa0c9c53dc4b3229cb31e3d73424f796806f60b3f5ed981e3`。

> `RunItemStreamEvent.name` uses a fixed set of semantic event names:

<a id="a2"></a>
### A2 — 11値は型注釈。通常dataclassであり外部データを実行時検証するvalidatorではない。

本体確認。[一次資料](https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/src/agents/stream_events.py#L23)。`src/agents/stream_events.py:23-48`。

コミット: `9415f7e1452d507420c64893d820869637656c84`。

取得内容 SHA-256: `d28151397c5d15da9e11ee3c5ea6f917a2005b6f614a9c6d0fed32ee380e0aee`。

> name: Literal[

<a id="a3"></a>
### A3 — run itemの型に応じて標準名を構築しqueueへ入れる。approval/compaction除外分岐あり。

本体確認。[一次資料](https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/src/agents/run_internal/streaming.py#L33)。`src/agents/run_internal/streaming.py:33-65`。

コミット: `9415f7e1452d507420c64893d820869637656c84`。

取得内容 SHA-256: `dd83880b86aa077f993ad2647a42b039c57ee0e2f8c7c2f039c33d0c1da769e9`。

> event = RunItemStreamEvent(item=item, name="tool_called")

<a id="a4"></a>
### A4 — queue getで逐次返す。永続log storeの実装ではない。

本体確認。[一次資料](https://github.com/openai/openai-agents-python/blob/9415f7e1452d507420c64893d820869637656c84/src/agents/result.py#L1013)。`src/agents/result.py:1013-1042`。

コミット: `9415f7e1452d507420c64893d820869637656c84`。

取得内容 SHA-256: `b1cce269e9f9321f7a5a8c04d456ba8e45c7df05aef14c2f7e5ef1083ec087a6`。

> yield item

<a id="a5"></a>
### A5 — task/message/status_update/artifact_updateの4候補。tool_call内部eventの標準候補なし。

本体確認。[一次資料](https://github.com/a2aproject/A2A/blob/afda8316c64951a2ecb2a0d3d10867405d2b4095/specification/a2a.proto#L790)。`specification/a2a.proto:790-802`。

コミット: `afda8316c64951a2ecb2a0d3d10867405d2b4095`。

取得内容 SHA-256: `945df6e34001b2bfd0fd62d9484b63094dfad9d78705e41e2873441c419ae2d1`。

> oneof payload {

<a id="v1"></a>
### V1 — 過去commitの変更を逆にした新しいcommitとして記録する仕様。

本体確認。[一次資料](https://github.com/git/git/blob/d38352cd43ab9745686d697872408bc3249a153f/Documentation/git-revert.adoc#L17)。`Documentation/git-revert.adoc:17-23`。

コミット: `d38352cd43ab9745686d697872408bc3249a153f`。

取得内容 SHA-256: `63cd3400c56f2c55e61ac2d6048e72c0b700071caabe8d9b337a37d8b180b5fd`。

> record some new commits

<a id="v2"></a>
### V2 — commitにtree,parent,author,committer,messageを記録する。

本体確認。[一次資料](https://github.com/git/git/blob/d38352cd43ab9745686d697872408bc3249a153f/commit.c#L1686)。`commit.c:1686-1723`。

コミット: `d38352cd43ab9745686d697872408bc3249a153f`。

取得内容 SHA-256: `eeaf0b342bd6e9290fcd1120a70398922b3dbed6e4d26a686b15a2d5f679bf9d`。

> strbuf_addf(buffer, "parent %s\n", oid_to_hex(&parents[i]));

<a id="v3"></a>
### V3 — revert時は現在commitをbase、parentをnextとして逆方向を求める。

本体確認。[一次資料](https://github.com/git/git/blob/d38352cd43ab9745686d697872408bc3249a153f/sequencer.c#L2398)。`sequencer.c:2398-2423`。

コミット: `d38352cd43ab9745686d697872408bc3249a153f`。

取得内容 SHA-256: `1e6d20ffca289dac02f5cf4a4a2142dc1cabf4bb8fd3439152101413c2be4488`。

> base = commit;

<a id="m1"></a>
### M1 — document内のactor連番欠落の拒否。未到着の最新suffix検知ではない。

本体確認。[一次資料](https://github.com/automerge/automerge-binary-format-spec/blob/e24b3077eaeabf6c7eef0111d0175be0885a898f/src/index.adoc#L509)。`src/index.adoc:509-512`。

コミット: `e24b3077eaeabf6c7eef0111d0175be0885a898f`。

取得内容 SHA-256: `aaea40b02f5809babc3f2aa769255231f0cc197e25c9c0bd6aa718380c20d4ec`。

> Implementations MUST abort
> if there are missing changes for a given actor ID.

<a id="m2"></a>
### M2 — actorごとseq+1を照合して欠番を拒否。

本体確認。[一次資料](https://github.com/automerge/automerge/blob/4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903/rust/automerge/src/op_set2/change/collector.rs#L917)。`rust/automerge/src/op_set2/change/collector.rs:917-934`。

コミット: `4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903`。

取得内容 SHA-256: `ea38bb00ea80ffe0740a0a63a1959da9c1f5046adf4b8ba92dfcf494dffbe7bf`。

> return Err(Error::ChangesOutOfOrder);

<a id="m3"></a>
### M3 — 同一change hash再適用はskip。同actor seqの異なる重複は拒否。

本体確認。[一次資料](https://github.com/automerge/automerge/blob/4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903/rust/automerge/src/op_set2/change/batch.rs#L1067)。`rust/automerge/src/op_set2/change/batch.rs:1067-1082`。

コミット: `4d2a8f6bfecfb7f1e4fca126e6d2122ac526f903`。

取得内容 SHA-256: `90d238c6a24756dca56e5355b6953f3d3e63503af9519bb7135b72a18058f630`。

> if self.change_graph.has_change(&hash) || seen.contains(&hash) {

<a id="p6"></a>
### P6 — persistent topicはmessage bytesをledgerへ追記する。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-broker/src/main/java/org/apache/pulsar/broker/service/persistent/PersistentTopic.java#L734)。`pulsar-broker/src/main/java/org/apache/pulsar/broker/service/persistent/PersistentTopic.java:734-744`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `67e4ff571cb2243d38afd2890e46aad214b963857b1483b522cc61ecf2a34dcb`。

> ledger.asyncAddEntry(headersAndPayload,

<a id="p7"></a>
### P7 — 実装はreaderの次のmessageをconsumer.receiveで取得する。

本体確認。[一次資料](https://github.com/apache/pulsar/blob/776248a7fe0f93b213b9f06658ca7f7e64c87c42/pulsar-client/src/main/java/org/apache/pulsar/client/impl/ReaderImpl.java#L195)。`pulsar-client/src/main/java/org/apache/pulsar/client/impl/ReaderImpl.java:195-207`。

コミット: `776248a7fe0f93b213b9f06658ca7f7e64c87c42`。

取得内容 SHA-256: `9423e4f892f4c9a24e82db64a56eda63b202c9a14e0c4d70b30106e3ee6d353d`。

> Message<T> msg = consumer.receive();

<a id="i4"></a>
### I4 — write schema検査APIの仕様。checkNullability有効時にrequired fieldへoptional値を書けない。

本体確認。[一次資料](https://github.com/apache/iceberg/blob/96d9880d6f8748b1b2f92aea0946b5505b550029/api/src/main/java/org/apache/iceberg/types/TypeUtil.java#L499)。`api/src/main/java/org/apache/iceberg/types/TypeUtil.java:499-505`。

コミット: `96d9880d6f8748b1b2f92aea0946b5505b550029`。

取得内容 SHA-256: `2019e74af7e71f32f783e81ec21f5c74bef927ec28b4316673104e50506b1fed`。

> If true, not allow to write optional values to a required field.

<a id="s0"></a>
### S0 — broker-side schema ID validationはpayload検査ではない。製品仕様の確認であり非公開brokerのコード検査ではない。

本体確認。[一次資料](https://docs.confluent.io/platform/7.9/schema-registry/schema-validation.html)。`confluent.html:1338-1338`。

コミット: 該当なし。固定版URLと取得日による。

取得内容 SHA-256: `7bc065ab2bdcac18318ff86d3b2592b53d1bb7f7b67e4af39632d86f76fed84d`。

> Schema Validation does not perform data introspection

<a id="p0"></a>
### P0 — 公式説明もschema metadataによるproducer/consumer間の合意と接続互換性を説明。

本体確認。[一次資料](https://pulsar.apache.org/docs/4.2.x/schema-overview/)。`pulsar-schema.html:31-31`。

コミット: 該当なし。固定版URLと取得日による。

取得内容 SHA-256: `7a4a519ed61cd1964c3c0fbbc9f07c7d3441657ea2fc1b11fccce8d59800f6b5`。

> Pulsar messages are stored as unstructured byte arrays

<a id="c0"></a>
### C0 — RFC 6962 §2.1.2。公表済み旧rootと新rootでprefix保持を証明する。

本体確認。[一次資料](https://www.rfc-editor.org/rfc/rfc6962.txt)。`rfc6962.txt:298-308`。

コミット: 該当なし。固定版URLと取得日による。

取得内容 SHA-256: `08fdf31c10b9f20872a65c027a9fe8cee27280f930120784241a57de744752af`。

> Merkle consistency proofs prove the append-only property of the tree.

<a id="c6"></a>
### C6 — RFC 6962 §3。SCT後MMD内に収録する義務。

本体確認。[一次資料](https://www.rfc-editor.org/rfc/rfc6962.txt)。`rfc6962.txt:463-477`。

コミット: 該当なし。固定版URLと取得日による。

取得内容 SHA-256: `08fdf31c10b9f20872a65c027a9fe8cee27280f930120784241a57de744752af`。

> the log's promise to incorporate the certificate

<a id="c7"></a>
### C7 — RFC 9162 §1。同じlogが相手ごとに異なるviewを示す限界。Trillianのv2準拠を示す引用ではない。

本体確認。[一次資料](https://www.rfc-editor.org/rfc/rfc9162.txt)。`rfc9162.txt:198-217`。

コミット: 該当なし。固定版URLと取得日による。

取得内容 SHA-256: `a0e432ce7580c99fcc8faf0cf3f6191f9ce6b4864f949158e020d4ecb295081f`。

> different, inconsistent

<a id="v4"></a>
### V4 — ワークフロー定義をGitへcommitする既存例。選択したworkflowの保存であり自己改変判断根拠の強制ではない。

本体確認。[一次資料](https://raw.githubusercontent.com/n8n-io/n8n-docs/d6f969044f09a928e5d1459a080f6289b68d7be5/docs/administer/use-source-control-and-environments/push-and-pull-changes.md)。`docs/administer/use-source-control-and-environments/push-and-pull-changes.md:85-94`。

コミット: `d6f969044f09a928e5d1459a080f6289b68d7be5`。

取得内容 SHA-256: `a034dc3c22910ac9d8e70aa812ec7761fb40da1fa85feccfbd3ccf73ea32bf08`。

> You can choose which workflows to push.

<a id="b1"></a>
### B1 — proto3 enumが閉じた数値集合とは限らない。

本体確認。[一次資料](https://raw.githubusercontent.com/protocolbuffers/protocolbuffers.github.io/4b88f52a8f830d4b4fbdad161dee33618ebc617f/content/programming-guides/enum.md)。`content/programming-guides/enum.md:81-85`。

コミット: `4b88f52a8f830d4b4fbdad161dee33618ebc617f`。

取得内容 SHA-256: `4f929ca89a33edc272331258edb24fe6ba800b30118acee787ea8a4f24f8d506`。

> and editions use *open* enums

<a id="b2"></a>
### B2 — oneofは高々一個。必ず一個とは異なる。

本体確認。[一次資料](https://raw.githubusercontent.com/protocolbuffers/protocolbuffers.github.io/4b88f52a8f830d4b4fbdad161dee33618ebc617f/content/programming-guides/proto3.md)。`content/programming-guides/proto3.md:1221-1229`。

コミット: `4b88f52a8f830d4b4fbdad161dee33618ebc617f`。

取得内容 SHA-256: `1941a0a9f810714d7556fbcf77e51cd960bb59a593325d1dd5bd0b6654ea8523`。

> in a oneof is set (if any)

## 2. 論文の引用

<a id="l1"></a>
### L1 — Kleppmann/Beresford/Svingen OLEP。log購読者に同じ更新列を同順で適用する。これは本文PDFを目視した短い引用。

本体確認。[一次資料](https://martin.kleppmann.com/papers/olep-acm-queue.pdf)。ACM Queue版 2019, PDF 7/21, 冊子p.122, Figure 2の説明。

コミット: 該当なし。取得内容 SHA-256: `f4b10a04ab4408e99d317ec2ee1d44efa991af1396856f12c8b188c8393fde79`。

> the same set of writes in the same order

<a id="l2"></a>
### L2 — 因果関係からclockの大小は言えるが、逆は言えない。

本体確認。[一次資料](https://lamport.azurewebsites.net/pubs/time-clocks.pdf)。1978, 冊子p.560, Clock Condition。PDF画像目視で矢印を転記。

コミット: 該当なし。取得内容 SHA-256: `c55e7cab4230aa3d7126748a149b2db6f0d7a67296d5eccfdd50a210299a96b2`。

> if a → b then C(a) < C(b).

<a id="l3"></a>
### L3 — vector timeは定義されたevent間の因果関係を表現する。時刻があるだけで未記録eventを知れるわけではない。

本体確認。[一次資料](https://www.vs.inf.ethz.ch/publ/papers/VirtTimeGlobStates.pdf)。著者配布版 冊子p.127, Theorem 10。PDF画像目視で式を転記。

コミット: 該当なし。取得内容 SHA-256: `9dea637ae03a9ec2cdeae442a2c99739d6437bf2941b2b024590d4d684078fd7`。

> e < e′ iff C(e) < C(e′)

<a id="l4"></a>
### L4 — Dapper §4.4のsamplingによる取りこぼし。samplingを完全監査と扱わない。

本体確認。[一次資料](https://research.google.com/archive/papers/dapper-2010-1.pdf)。Google Technical Report dapper-2010-1, 2010, p.7 §4.4。

コミット: 該当なし。取得内容 SHA-256: `41baea09d066e0167ca0943968d44f7f07790be700440427f78c034910e5765d`。

> lower traffic workloads may miss important events

<a id="l5"></a>
### L5 — SLiC Algorithm 4はcache上限と初期状態から許容されるcrash損失範囲を使って欠落を検査する。

本体確認。[一次資料](https://eprint.iacr.org/2017/107.pdf)。Blass/Noubir, Secure Logging with Crash Tolerance, IACR ePrint 2017/107版, PDF p.6 Algorithm 4。

コミット: 該当なし。取得内容 SHA-256: `b3c53d59edf791f54984adb2b76d93a3a586c170a22e5e877625c3b5718a7817`。

> Check plausibility

<a id="l6"></a>
### L6 — PeerReview §4.5のcompleteの範囲。§3.4 PDF p.4 はdetectable faultのeventual detection、§4.3 p.5-6は決定論等、§6 p.9-10は統合前提。

本体確認。[一次資料](https://people.mpi-sws.org/~druschel/publications/peerreview-sosp07.pdf)。Haeberlen/Kouznetsov/Druschel, SOSP 2007著者配布版, PDF p.6 §4.5。

コミット: 該当なし。取得内容 SHA-256: `9f8e97481b95a96306cd1f6aaaf2de123a35705bc7987bce5f36677ca4c65fe7`。

> for each message sent or received by the node to or from a correct node.

## 3. 再取得用台帳

`/private/tmp/pda-research-04/manifest.json` はテキスト資料の URL・SHA・path・開始/終了行・短い引用を記録する。`manifest-papers.json` はPDFのURL・取得内容SHA-256・ページ・引用を記録する。引用の存在検査は書き出し時に実施した。台帳は作業中の補助ファイルであり、本根拠集に必要情報を全件転記してある。

## 4. 取得失敗・未確認の扱い

本文の「取得できなかった資料」にHTTP結果を記載する。成功して取得した資料の範囲からだけ結論を導いた。OpSetsの誤ったPDF URLはHTTP 200のHTMLを返し、PDFとして読めなかったため、その本文の主張は引用していない。
