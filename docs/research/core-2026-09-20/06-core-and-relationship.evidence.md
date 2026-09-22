# 第6本の根拠集 — コアの機能と、コアと実行器の関係

取得日: 2026-09-21 JST。物差し: `docs/requirements.md` commit `aa2c92c42cf7941406534eb5b99846a4dcdee86c`。本文は [06-core-and-relationship.md](06-core-and-relationship.md)。本書の外部資料はすべて本体確認。前5本の成果は本文で「報告」と区別する。

## 1. 取得物の固定

Git資料は取得時のHEADを以下の40桁SHAに固定して取得した。release版や導入済み版とは同一視しない。コードの行番号はこのSHAのもの。HTMLは取得した版のSHA-256で固定し、抽出テキストの行は位置の補助とする。PDFページは表紙を含む物理ページである。

| リポジトリ | commit SHA | 取得tarball SHA-256 |
|---|---|---|
| conductor-oss/conductor | `8ac94cf398d230a35bb5835b27760f52cf7aa8b7` | `4536fd60ae11a01351cd3324d98318da5ff387697c0e756c5e29f91ca211a43a` |
| apache/airflow | `01fc0c5ffff2a274bf5d797faf9c73819b61d528` | `fb6cb8a0b7055158f0a5a219f4273c39ce8f7368378a647500df68bac3e7ed75` |
| erlang/otp | `d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6` | `368bde494365eb9c95b8b470701f6742e5ad98e266a38dd4e00dcb79cc6fc020` |
| kubernetes/kubernetes | `57c05b7d223db659c973768beeb079a3d64f76c0` | `7bf9a30cf4510c2ca0a9666b4b43aeab46b94a58f771a9563006f593668ffd24` |
| resilience4j/resilience4j | `a8a33164256ddb6e4bbc168f5c47ac34a348ee7f` | `17e277b9860fa876fe4151e75e7e7056e76508a06d06e313bd01fb7c985b60fd` |
| open-policy-agent/opa | `8cb390243358936dca23cc3c2822266587ded08f` | `4479f4523ecb65d36679bbe1ee23bf0c7c25ac6523e08c878fc348cddfa0a0f9` |
| racket/racket | `45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b` | `c13798d205e826dbb4f62c7e3e2546e3a05ad0b2018df160a08cec39590b0b76` |
| gems-uff/noworkflow | `4a2c4c8bdea2be73570a1aa598042940f4f4270f` | `69e57aa316b4c2a9cf3d42f42d20f4b0a823d8fd9b58be5e0e357f2b46548fb2` |
| langfuse/langfuse-python | `65392c73731e07711828745de337fdf7bba31fbc` | `20c060168d091b33268a3dc3bbcac2befdaf66a0bf3773268a1c95984bee82ec` |
| mlflow/mlflow | `3e1b7122cd9b9e887763fb0e7729bb4464fba0c4` | `0a5952366a6d3ca7a50ca406a67c50d85f3f2a8a90e1a602aa1e06803f14f0ab` |
| apache/pekko | `1f573c993284158aea9bdd51818b4d6e949c76ab` | `e9ad7831903e4f31fef6ec437d2e74dff8c40f1cdc4abd0e2490f8a856a8f6de` |
| temporalio/temporal | `f9ddbdac35b3db1ea744319201c3ad798fe3aa60` | `f548f5b012ca6a65acea4d285a55d7d43630ce5aa026704a04315f2d18f364b7` |
| argoproj/argo-workflows | `5642521e2a1349803c097a00db2b08f0b96c10ca` | `92da3e8e2db70b1a81362bade93c8d76ac784beb95dc63f7320669906fdc5078` |
| dananau/GTPyhop | `1ca7773963443476d0e83d03f10efab325327565` | `4b5497b7a1297d09a696a07a4ca055b7e65f291f0bd3fd3bb779ddb7bd1dcc00` |
| stanfordnlp/dspy | `40a6e168914a7b81a78b1a081d93f26de18c8d0d` | `3479c466cae3e4bab7cb674be80a5fdf02ae215cc8a3a992ed8484429499fe72` |

各tarballは `https://codeload.github.com/<リポジトリ>/tar.gz/<SHA>` でHTTP 200。tarballの実行やインストールはしていない。

| ID | 論文・仕様・公式資料URL | HTTP | SHA-256 |
|---|---|---|---|
| FF | [取得元](https://users.cs.northwestern.edu/~robby/pubs/papers/ho-contracts-icfp2002.pdf) | 200 | `c840e433f256dd05e18ee1f5fde303e04ea44cd652dc8e72845dd551a02c18e1` |
| CT | [取得元](https://www.cs.toronto.edu/~christoff/files/UnreliableFailureDetectorsForReliableDistributedSystems.pdf) | 200 | `f2c4b22a63e43c462286ce740e38528bac275d87e769d794bb830a434e1362cf` |
| HY | [取得元](https://cseweb.ucsd.edu/classes/wi19/cse221-a/papers/wulf74.pdf) | 200 | `1c77f6279e955e1302ba51caaa9b77bfa9b66c71491ef2e6195265fe6d540983` |
| NW | [取得元](https://www.vldb.org/pvldb/vol10/p1841-pimentel.pdf) | 200 | `27cc4e233a6479eeef303999359c756c79d0d21023b9389be6c090c88fb4e74e` |
| HT | [取得元](https://www.cs.umd.edu/users/nau/papers/bansod2022htn.pdf) | 200 | `68e445b9f836ba8de51396ee92e710c6a931dfbfb76823ee697ab97b595cf55b` |
| PR | [取得元](https://www.w3.org/TR/prov-constraints/) | 200 | `0e65d02339347af6f6e5744cb69a99cf56430e8fd9dd904ac476541634361287` |
| PA | [取得元](https://www.w3.org/TR/prov-aq/) | 200 | `00ac5c1455da2e04ad3d94f4dad6969c78b11e0062c154faab70b680d24c0fc7` |
| BP | [取得元](https://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.pdf) | 200 | `86e7f871c2a0a1f2d0451c9001a0b11c10979fe537e86ae2514ea6e811229932` |
| CD | [取得元](https://www.w3.org/TR/ws-cdl-10/) | 200 | `9b27f423c90a478831a24cb34bf3d763262e6dacfd9bc750e85ac00ac9b5a2da` |
| KB | [取得元](https://kubernetes.io/docs/concepts/workloads/controllers/job/) | 200 | `6f72923b37690274aa64f35a01716734cc33772a36197381cd3d3488e9a39fa5` |
| KA | [取得元](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/) | 200 | `839ae4e18e97cb0001d882dadcdfd32c318566f16edea75518561e43fc4e1719` |
| OP | [取得元](https://www.openpolicyagent.org/docs/management-decision-logs) | 200 | `df7d7996c37fff91488064abbb13bd86ebc21d7d00df7cd3ad161ee6aea97f20` |
| RC | [取得元](https://docs.racket-lang.org/guide/contracts-general-functions.html) | 200 | `c60dba0d569edd159941145dbf194f28f2313c88e1cfe83fe151f9a491bd5151` |
| SQ | [取得元](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html) | 200 | `bac1ddd7349065223d1a93a3b864c27b9153abfd27a4531ed358972f10ed8510` |
| KF | [取得元](https://kafka.apache.org/41/design/design/) | 200 | `7a56f6a8e496fb4377d270eb076f98dd4fbba2b3a4190f12fbf361502cc39c4c` |
| PF | [取得元](https://pekko.apache.org/docs/pekko/current/typed/failure-detector.html) | 200 | `d489dee63e185ce6b93eff7b77533c7fbe63c7beb84b8a04ba339c61b3ead71a` |
| CB | [取得元](https://resilience4j.readme.io/docs/circuitbreaker) | 200 | `5136226b6f17e5cf5590ff3141161d8446dff2283cdcd312762cb56f0a6b7338` |
| RE | [取得元](https://docs.drools.org/7.0.0.Final/kie-api-javadoc/org/kie/api/event/rule/AgendaEventListener.html) | 200 | `9e02a4b29fb373403c34efbca43c48b39596770ddc541eedae55b0ffec3c5522` |
| LF | [取得元](https://langfuse.com/docs/prompt-management/get-started) | 200 | `de55108aba71f20fe7246133eb8fc10e08adaaff55bce5edf0f783fe8bd39369` |
| ML | [取得元](https://mlflow.org/docs/latest/genai/prompt-registry/) | 200 | `98fd94b6031199626c7054d085e5c4e4698c5005c85e88e8d88a442ebd8458f8` |
| VA | [取得元](https://www2.informatik.uni-hamburg.de/TGI/publikationen/public/biblio_valk_eng.html) | 200 | `c425b0155532ecfbd52f5427005f108ae7c03175f2d16c5b1c7e4981c8a4c017` |
| AI | [取得元](https://arxiv.org/pdf/1611.09067) | 200 | `9c62300bd62c5b9c163f0d2de2aae7aa409eac901e3f2e9ba1b3ca49a3095b94` |
| GR | [取得元](https://groove.cs.utwente.nl/grammars/sttt2011.pdf) | 200 | `e3f6d465030fce909584eb6fd5ad8ce06aa1cc4a9d602a516a076d05f122eb47` |
| BD | [取得元](https://jason-lang.github.io/jason/tech/concurrency.html) | 200 | `11fdcd5ccae861be548112f4730607d0e53f42933990fd91ced074d8303d0d18` |
| RB | [取得元](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/circuit_breaking) | 200 | `1c7bd42e6672ef21ba29095b9d347618eaeda6df696c7258d0e1b2d24d6170ae` |
| TR | [取得元](https://docs.temporal.io/encyclopedia/retry-policies) | 200 | `8978a0f38c1db41301ae65f6faeea6f0be400999d58abb2b7c9c4d375253e210` |
| TC | [取得元](https://docs.temporal.io/encyclopedia/child-workflows) | None | `未取得` |
| TS | [取得元](https://docs.temporal.io/handling-messages) | 200 | `0d4b1626feb8eba56587d5ee157f16f0a295990df96d39189722016aeed4048e` |
| DS | [取得元](https://dspy.ai/learn/programming/signatures/) | 200 | `77051b8dd9a6e39b64e266de7306277419c4abb0bf4d81b42ba25533a6c48eb9` |
| DSC | [取得元](https://dspy.ai/current/learn/programming/signatures/) | 200 | `85108e2fe641751dd94858b3aaffe5da7692f9c8cc272efd0501079b250e8ce7` |
| DSF | [取得元](https://dspy.ai/current/getting-started/expanding-signatures/) | 200 | `ba6101a053a1bde670f995fb13646924f7817fceec6b8315ae978903642e8016` |
| KV | [取得元](https://kubernetes.io/docs/reference/using-api/api-concepts/) | 200 | `555c9c8ca5f31884cf48138032e8c110bc7853ef5c163297782251bca6ee4c40` |

## 2. 逐語引用と確認箇所

仕様の文言とコードの実行経路を区別して記録する。引用は要点のみとし、拒否・省略・代替経路を含む周辺範囲も確認した。本文のコード参照は下記IDへ対応する。

<a id="con0"></a>
### CON0

位置: [docs/documentation/configuration/workflowdef/operators/dynamic-fork-task.md:29–39](https://github.com/conductor-oss/conductor/blob/8ac94cf398d230a35bb5835b27760f52cf7aa8b7/docs/documentation/configuration/workflowdef/operators/dynamic-fork-task.md#L29-L39)。commit `8ac94cf398d230a35bb5835b27760f52cf7aa8b7`。ファイルSHA-256 `ee0cd50ae22d5cc490db5be129b52b1afaa4b8377edc855289c7bca645e08de3`。

> The list of task configurations that will be executed across forks

動的forkの入力listが実行するtask定義を列挙する仕様。

<a id="con1"></a>
### CON1

位置: [core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinDynamicTaskMapper.java:126–179](https://github.com/conductor-oss/conductor/blob/8ac94cf398d230a35bb5835b27760f52cf7aa8b7/core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinDynamicTaskMapper.java#L126-L179)。commit `8ac94cf398d230a35bb5835b27760f52cf7aa8b7`。ファイルSHA-256 `9db3c48b009639949f117f1f1210d0f39cd812b11d7e7e640263499b0ed1395c`。

> getDynamicForkTasksAndInput(

入力を解決し、動的task列と入力mapを得る。

<a id="con2"></a>
### CON2

位置: [core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinDynamicTaskMapper.java:195–278](https://github.com/conductor-oss/conductor/blob/8ac94cf398d230a35bb5835b27760f52cf7aa8b7/core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinDynamicTaskMapper.java#L195-L278)。commit `8ac94cf398d230a35bb5835b27760f52cf7aa8b7`。ファイルSHA-256 `9db3c48b009639949f117f1f1210d0f39cd812b11d7e7e640263499b0ed1395c`。

> mappedTasks.addAll(forkedTasks);

指定taskを生成。入力不正、taskを生成できない場合、後続JOIN不在は例外。

<a id="con3"></a>
### CON3

位置: [core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinDynamicTaskMapper.java:369–414](https://github.com/conductor-oss/conductor/blob/8ac94cf398d230a35bb5835b27760f52cf7aa8b7/core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinDynamicTaskMapper.java#L369-L414)。commit `8ac94cf398d230a35bb5835b27760f52cf7aa8b7`。ファイルSHA-256 `9db3c48b009639949f117f1f1210d0f39cd812b11d7e7e640263499b0ed1395c`。

> if (!(dynamicForkTasksInput instanceof Map))

入力map、taskのdeserialize、taskReferenceNameを検査。

<a id="con4"></a>
### CON4

位置: [docs/devguide/cookbook/dynamic-parallelism.md:12–37](https://github.com/conductor-oss/conductor/blob/8ac94cf398d230a35bb5835b27760f52cf7aa8b7/docs/devguide/cookbook/dynamic-parallelism.md#L12-L37)。commit `8ac94cf398d230a35bb5835b27760f52cf7aa8b7`。ファイルSHA-256 `02920b2bd59a42ac8ddf04a54f649fb84a90341a34ede51a28414cbe5fa5e7bf`。

> ${prepare.output.result.dynamicTasks}

前段出力を参照する例。prepareはINLINEのJavaScriptである。

<a id="con5"></a>
### CON5

位置: [core/src/main/java/com/netflix/conductor/core/utils/ParametersUtils.java:95–168](https://github.com/conductor-oss/conductor/blob/8ac94cf398d230a35bb5835b27760f52cf7aa8b7/core/src/main/java/com/netflix/conductor/core/utils/ParametersUtils.java#L95-L168)。commit `8ac94cf398d230a35bb5835b27760f52cf7aa8b7`。ファイルSHA-256 `2338abf7309825c58cb0c4a01deb9c5ece9c833bfeb17a45e47709a5573f9dc9`。

> workflowParams.put("input", workflow.getInput());

参照元にはworkflow入力・出力や各taskの入力・出力も入る。直前出力だけには制限しない。

<a id="af0"></a>
### AF0

位置: [airflow-core/docs/authoring-and-scheduling/dynamic-task-mapping.rst:25–35](https://github.com/apache/airflow/blob/01fc0c5ffff2a274bf5d797faf9c73819b61d528/airflow-core/docs/authoring-and-scheduling/dynamic-task-mapping.rst#L25-L35)。commit `01fc0c5ffff2a274bf5d797faf9c73819b61d528`。ファイルSHA-256 `f337bab8c82abbf17ce51b869ee960a822417d36df6446fa15708bf26a4c9694`。

> the scheduler will create *n* copies of the task, one for each input.

展開対象は既定taskのinstance。literal listも許す。

<a id="af1"></a>
### AF1

位置: [airflow-core/src/airflow/models/expandinput.py:125–155](https://github.com/apache/airflow/blob/01fc0c5ffff2a274bf5d797faf9c73819b61d528/airflow-core/src/airflow/models/expandinput.py#L125-L155)。commit `01fc0c5ffff2a274bf5d797faf9c73819b61d528`。ファイルSHA-256 `0ffa3ff9717d77d7339943bf718410cefbcb2ded69d958f23a83289912973974`。

> return get_task_map_length(v, run_id, session=session)

XCom参照とliteralで長さの取得経路が分岐。

<a id="af2"></a>
### AF2

位置: [airflow-core/src/airflow/models/taskmap.py:160–293](https://github.com/apache/airflow/blob/01fc0c5ffff2a274bf5d797faf9c73819b61d528/airflow-core/src/airflow/models/taskmap.py#L160-L293)。commit `01fc0c5ffff2a274bf5d797faf9c73819b61d528`。ファイルSHA-256 `9132320e8ff3787a2c79d38cfc4373ed06e7cde317612a6667ba2fd10c7130af`。

> unmapped_ti.state = TaskInstanceState.SKIPPED

未解決、空列、instance生成、不要index除去の処理。

<a id="ar0"></a>
### AR0

位置: [docs/walk-through/loops.md:3–12](https://github.com/argoproj/argo-workflows/blob/5642521e2a1349803c097a00db2b08f0b96c10ca/docs/walk-through/loops.md#L3-L12)。commit `5642521e2a1349803c097a00db2b08f0b96c10ca`。ファイルSHA-256 `ac9efee7fff8fa4797cedff08bc758286740466b3e766aa19b15c6ba0f5e8b94`。

> `withParam` takes a JSON array of items, and iterates over it

JSON配列に基づく既定templateの反復。

<a id="ar1"></a>
### AR1

位置: [workflow/controller/dag.go:931–988](https://github.com/argoproj/argo-workflows/blob/5642521e2a1349803c097a00db2b08f0b96c10ca/workflow/controller/dag.go#L931-L988)。commit `5642521e2a1349803c097a00db2b08f0b96c10ca`。ファイルSHA-256 `6602162ea47abe38058ced9f725cdf069340f994e4527d745bd2eb761bd8a61e`。

> newTask.Template = task.Template

withParamをJSON listへdecodeし要素ごとに同じtemplateを展開。不正値はwhenの条件付きでエラー。

<a id="ar2"></a>
### AR2

位置: [workflow/controller/dag.go:633–680](https://github.com/argoproj/argo-workflows/blob/5642521e2a1349803c097a00db2b08f0b96c10ca/workflow/controller/dag.go#L633-L680)。commit `5642521e2a1349803c097a00db2b08f0b96c10ca`。ファイルSHA-256 `6602162ea47abe38058ced9f725cdf069340f994e4527d745bd2eb761bd8a61e`。

> wfv1.NodeError

展開エラーをNodeErrorへ、空配列をNodeSkippedへ反映し、group nodeと依存を構成する。

<a id="te0"></a>
### TE0

位置: [docs/architecture/history-service.md:9–21](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/docs/architecture/history-service.md#L9-L21)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `78c073d00672c33fb339e6c01ca24487c1ea0a2573fea77aa88a3b19593ec7e2`。

> Requests originating from Temporal Workers

利用者要求とWorker完了要求を受け、履歴・taskを中央が構築する仕様。

<a id="te1"></a>
### TE1

位置: [service/history/api/respondworkflowtaskcompleted/workflow_task_completed_handler.go:293–379](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/api/respondworkflowtaskcompleted/workflow_task_completed_handler.go#L293-L379)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `2d30dcaa722a53ee13a08639e1b71f9a376d71ba77f30c88d8ce7383449c26b2`。

> Unknown command type: %v

列挙commandと登録済拡張handlerへ分岐し、どちらにもなければInvalidArgument。

<a id="te2"></a>
### TE2

位置: [service/history/api/respondworkflowtaskcompleted/workflow_task_completed_handler.go:1244–1266](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/api/respondworkflowtaskcompleted/workflow_task_completed_handler.go#L1244-L1266)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `2d30dcaa722a53ee13a08639e1b71f9a376d71ba77f30c88d8ce7383449c26b2`。

> handler.workflowTaskCompletedID, attr, targetNamespaceID,

子workflow開始を、指示を返したWorkflowTaskの完了eventに結ぶ。

<a id="te3"></a>
### TE3

位置: [service/history/workflow/retry.go:32–113](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/workflow/retry.go#L32-L113)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `555ef300965d4c29c32417c6ab6fb18689a87d26f750896d1f170c56cd75a7f3`。

> currentAttempt >= maxAttempts

非再試行失敗、回数、期限、backoffと終了理由。WorkerのNextRetryDelayも入力になる。

<a id="te4"></a>
### TE4

位置: [service/history/workflow/mutable_state_impl.go:6877–6974](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/workflow/mutable_state_impl.go#L6877-L6974)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `cbd9f2a6fff6982ab97b471e04018a2baf070f6871ff76afb09cc900a856682e`。

> GenerateActivityRetryTasks(ai)

取消し・失敗種別・回数を検査して試行回数とretry taskを更新。

<a id="te5"></a>
### TE5

位置: [service/history/timer_queue_active_task_executor.go:230–278](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/timer_queue_active_task_executor.go#L230-L278)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `5d11afeb179d8c8bb2f22d88489d370be9c7711eda59e0c4b62baf289d80ef36`。

> queues.IsTimeExpired

server時刻とactivity timerによる期限判定。

<a id="te6"></a>
### TE6

位置: [service/history/api/describeworkflow/api.go:94–128](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/api/describeworkflow/api.go#L94-L128)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `3bf1caf087452476b9eef0bb3592853b941976a3489c1ffedac0fb0b667863cd`。

> mutableState.GetExecutionState()

中央MutableStateからworkflow状態を返す。

<a id="te7"></a>
### TE7

位置: [service/history/api/describeworkflow/api.go:205–222](https://github.com/temporalio/temporal/blob/f9ddbdac35b3db1ea744319201c3ad798fe3aa60/service/history/api/describeworkflow/api.go#L205-L222)。commit `f9ddbdac35b3db1ea744319201c3ad798fe3aa60`。ファイルSHA-256 `3bf1caf087452476b9eef0bb3592853b941976a3489c1ffedac0fb0b667863cd`。

> result.PendingActivities = append(result.PendingActivities, p)

pending activity/childも中央記録から構成。

<a id="er0"></a>
### ER0

位置: [system/doc/design_principles/sup_princ.md:240–258](https://github.com/erlang/otp/blob/d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6/system/doc/design_principles/sup_princ.md#L240-L258)。commit `d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6`。ファイルSHA-256 `f87be77fb52f1156ee52b2f8b455bf1ceab6023628c62c0a1dd8627a9f1f84e4`。

> If more than `MaxR` number of restarts occur in the last `MaxT` seconds

期間内再起動上限の仕様。超過時は子とsupervisorを終了する。

<a id="er1"></a>
### ER1

位置: [lib/stdlib/src/supervisor.erl:1426–1491](https://github.com/erlang/otp/blob/d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6/lib/stdlib/src/supervisor.erl#L1426-L1491)。commit `d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6`。ファイルSHA-256 `58a8f0831be5178bf9fcf6b253747cc2c64cd50d8d2046d0fa08cea16514c1c2`。

> reached_max_restart_intensity

permanent/transient/temporaryと終了reasonで分岐し、超過理由をreportする。

<a id="er2"></a>
### ER2

位置: [lib/stdlib/src/supervisor.erl:2258–2290](https://github.com/erlang/otp/blob/d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6/lib/stdlib/src/supervisor.erl#L2258-L2290)。commit `d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6`。ファイルSHA-256 `58a8f0831be5178bf9fcf6b253747cc2c64cd50d8d2046d0fa08cea16514c1c2`。

> Threshold = Now - P

monotonic時刻、再起動履歴、上限で判定。

<a id="er3"></a>
### ER3

位置: [lib/stdlib/src/supervisor.erl:1287–1300](https://github.com/erlang/otp/blob/d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6/lib/stdlib/src/supervisor.erl#L1287-L1300)。commit `d7a2b73d19e9132ca30da2a7875c1f3ec2ccf7d6`。ファイルSHA-256 `58a8f0831be5178bf9fcf6b253747cc2c64cd50d8d2046d0fa08cea16514c1c2`。

> Supervisor received unexpected message: ~tp~n

未知infoはerror log後に状態を維持。意味判断の別セルへの委譲ではない。

<a id="kj1"></a>
### KJ1

位置: [pkg/controller/job/pod_failure_policy.go:27–76](https://github.com/kubernetes/kubernetes/blob/57c05b7d223db659c973768beeb079a3d64f76c0/pkg/controller/job/pod_failure_policy.go#L27-L76)。commit `57c05b7d223db659c973768beeb079a3d64f76c0`。ファイルSHA-256 `4347663e49f10cdb44ac580f8433bba44dcfd2d26a8d855ace6de3dd62f34009`。

> matching %v rule at index %d

規則を順に照合。FailJobにrule indexを含む理由を構築。未一致はCount相当。

<a id="kj2"></a>
### KJ2

位置: [pkg/controller/job/job_controller.go:1075–1105](https://github.com/kubernetes/kubernetes/blob/57c05b7d223db659c973768beeb079a3d64f76c0/pkg/controller/job/job_controller.go#L1075-L1105)。commit `57c05b7d223db659c973768beeb079a3d64f76c0`。ファイルSHA-256 `3037216d28806d71c50be449b81c65a1f4a8222702033f42b0a222aa4d09edd1`。

> batch.JobReasonBackoffLimitExceeded

失敗数、deadline、podFailurePolicyからconditionと理由を構築する。

<a id="kj3"></a>
### KJ3

位置: [pkg/controller/job/job_controller.go:1170–1200](https://github.com/kubernetes/kubernetes/blob/57c05b7d223db659c973768beeb079a3d64f76c0/pkg/controller/job/job_controller.go#L1170-L1200)。commit `57c05b7d223db659c973768beeb079a3d64f76c0`。ファイルSHA-256 `3037216d28806d71c50be449b81c65a1f4a8222702033f42b0a222aa4d09edd1`。

> "Job suspended"

suspend/resumeのconditionとeventを構築する。

<a id="ka1"></a>
### KA1

位置: [staging/src/k8s.io/apiserver/pkg/endpoints/handlers/create.go:120–151](https://github.com/kubernetes/kubernetes/blob/57c05b7d223db659c973768beeb079a3d64f76c0/staging/src/k8s.io/apiserver/pkg/endpoints/handlers/create.go#L120-L151)。commit `57c05b7d223db659c973768beeb079a3d64f76c0`。ファイルSHA-256 `2f17325a969d02a31057d3241bf99d9b3837746a991c12d1784ef067f53117ac`。

> validationDirective == metav1.FieldValidationWarn

strict decodingの不正を拒否する経路と、Warnで継続する例外。

<a id="ka2"></a>
### KA2

位置: [staging/src/k8s.io/apiserver/pkg/endpoints/filters/audit.go:38–109](https://github.com/kubernetes/kubernetes/blob/57c05b7d223db659c973768beeb079a3d64f76c0/staging/src/k8s.io/apiserver/pkg/endpoints/filters/audit.go#L38-L109)。commit `57c05b7d223db659c973768beeb079a3d64f76c0`。ファイルSHA-256 `a30877d4d9d6d85c864c9fcc81c44ebe52afb0efed0b32ee26e0b5bc10387592`。

> auditinternal.StageResponseComplete

audit有効時、HTTP statusを受け完了stageをsinkへ渡す。

<a id="ka3"></a>
### KA3

位置: [staging/src/k8s.io/apiserver/pkg/endpoints/filters/audit.go:119–147](https://github.com/kubernetes/kubernetes/blob/57c05b7d223db659c973768beeb079a3d64f76c0/staging/src/k8s.io/apiserver/pkg/endpoints/filters/audit.go#L119-L147)。commit `57c05b7d223db659c973768beeb079a3d64f76c0`。ファイルSHA-256 `a30877d4d9d6d85c864c9fcc81c44ebe52afb0efed0b32ee26e0b5bc10387592`。

> rac.Level == auditinternal.LevelNone

Noneは監査しない。sink/policy未設定もKA2で素通りする。

<a id="ph1"></a>
### PH1

位置: [remote/src/main/scala/org/apache/pekko/remote/PhiAccrualFailureDetector.scala:136–166](https://github.com/apache/pekko/blob/1f573c993284158aea9bdd51818b4d6e949c76ab/remote/src/main/scala/org/apache/pekko/remote/PhiAccrualFailureDetector.scala#L136-L166)。commit `1f573c993284158aea9bdd51818b4d6e949c76ab`。ファイルSHA-256 `d785fb036ac128a5a6591872d1c9ed3864a2629f6c0bb72872cc61b7768933cb`。

> phi(timestamp) < threshold

heartbeat履歴とthresholdからavailabilityを返す。

<a id="ph2"></a>
### PH2

位置: [remote/src/main/scala/org/apache/pekko/remote/PhiAccrualFailureDetector.scala:188–222](https://github.com/apache/pekko/blob/1f573c993284158aea9bdd51818b4d6e949c76ab/remote/src/main/scala/org/apache/pekko/remote/PhiAccrualFailureDetector.scala#L188-L222)。commit `1f573c993284158aea9bdd51818b4d6e949c76ab`。ファイルSHA-256 `d785fb036ac128a5a6591872d1c9ed3864a2629f6c0bb72872cc61b7768933cb`。

> if (oldTimestamp.isEmpty) 0.0

未監視を正常扱いし、経過時間・平均・偏差からphiを近似計算する。

<a id="cb1"></a>
### CB1

位置: [resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerMetrics.java:141–174](https://github.com/resilience4j/resilience4j/blob/a8a33164256ddb6e4bbc168f5c47ac34a348ee7f/resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerMetrics.java#L141-L174)。commit `a8a33164256ddb6e4bbc168f5c47ac34a348ee7f`。ファイルSHA-256 `dba3cc73cf9d3b1a542e474235a4a71162377b6b312a8811b9f3ca0afb7906a1`。

> Result.BELOW_MINIMUM_CALLS_THRESHOLD

最低呼出数未満では閾値超過とせず、失敗率・遅延率を比較する。

<a id="cb2"></a>
### CB2

位置: [resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine.java:659–669](https://github.com/resilience4j/resilience4j/blob/a8a33164256ddb6e4bbc168f5c47ac34a348ee7f/resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine.java#L659-L669)。commit `a8a33164256ddb6e4bbc168f5c47ac34a348ee7f`。ファイルSHA-256 `00984d1771d03b47556f927f3ab96c446edd97cc56dfa6e850ee1ea4ffee687f`。

> transitionToOpenState();

CLOSEDから閾値超過のevent発行とOPENへの遷移。

<a id="cb3"></a>
### CB3

位置: [resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine.java:383–414](https://github.com/resilience4j/resilience4j/blob/a8a33164256ddb6e4bbc168f5c47ac34a348ee7f/resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine.java#L383-L414)。commit `a8a33164256ddb6e4bbc168f5c47ac34a348ee7f`。ファイルSHA-256 `00984d1771d03b47556f927f3ab96c446edd97cc56dfa6e850ee1ea4ffee687f`。

> if (!eventProcessor.hasConsumers())

listener不在ではeventを発行せず、listener例外もcatchする。

<a id="op0"></a>
### OP0

位置: [docs/docs/policy-language.md:2738–2750](https://github.com/open-policy-agent/opa/blob/8cb390243358936dca23cc3c2822266587ded08f/docs/docs/policy-language.md#L2738-L2750)。commit `8cb390243358936dca23cc3c2822266587ded08f`。ファイルSHA-256 `89df3b6a493516f871b6ab312c8fe381ad8f51e3dff7370d2390257bfff47531`。

> Identical merged maps across rules are deduplicated.

成立した規則のlabelsを結合・記録する仕様。同じlabel mapは統合される。

<a id="op1"></a>
### OP1

位置: [v1/server/server.go:1525–1597](https://github.com/open-policy-agent/opa/blob/8cb390243358936dca23cc3c2822266587ded08f/v1/server/server.go#L1525-L1597)。commit `8cb390243358936dca23cc3c2822266587ded08f`。ファイルSHA-256 `74ef388f56daad5c88a16fb94047b837bbe6433e48086517bf7e33e214a294e9`。

> rego.EvalEvaluatedRuleTracker(tracker)

評価trackerを登録。undefinedはresult無しのHTTP成功、成立結果はlabelsと共にloggerへ。

<a id="op2"></a>
### OP2

位置: [v1/plugins/logs/plugin.go:771–871](https://github.com/open-policy-agent/opa/blob/8cb390243358936dca23cc3c2822266587ded08f/v1/plugins/logs/plugin.go#L771-L871)。commit `8cb390243358936dca23cc3c2822266587ded08f`。ファイルSHA-256 `6510910d4c067cc2171ca0bb12551ab2a8ecce95799a12a89a44b3697a5597e9`。

> RuleLabels:          decision.EvaluatedRuleLabels,

decision ID、bundle revision、input、result、rule labelsをeventへ入れる。

<a id="op4"></a>
### OP4

位置: [v1/topdown/evaluated.go:34–50](https://github.com/open-policy-agent/opa/blob/8cb390243358936dca23cc3c2822266587ded08f/v1/topdown/evaluated.go#L34-L50)。commit `8cb390243358936dca23cc3c2822266587ded08f`。ファイルSHA-256 `4fd1fd0499aa7ed4643d02b0d4154c7a47e6c31211f1ba502303e51060bf7a29`。

> t.Labels = append(t.Labels, labels)

無labelは無記録、既出ruleと同じlabel mapを抑制する。

<a id="op3"></a>
### OP3

位置: [v1/plugins/logs/plugin.go:819–852](https://github.com/open-policy-agent/opa/blob/8cb390243358936dca23cc3c2822266587ded08f/v1/plugins/logs/plugin.go#L819-L852)。commit `8cb390243358936dca23cc3c2822266587ded08f`。ファイルSHA-256 `6510910d4c067cc2171ca0bb12551ab2a8ecce95799a12a89a44b3697a5597e9`。

> if drop {

drop/maskにより記録を省略しうる。

<a id="ra1"></a>
### RA1

位置: [racket/collects/racket/contract/private/blame.rkt:280–285](https://github.com/racket/racket/blob/45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b/racket/collects/racket/contract/private/blame.rkt#L280-L285)。commit `45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b`。ファイルSHA-256 `d35ff3852ca0ad463ce65013de273d059cedb66412929dcda2a9121473cbe22b`。

> blame-no-swap

正負の責任側を反転する。

<a id="ra2"></a>
### RA2

位置: [racket/collects/racket/contract/private/arrow-val-first.rkt:675–692](https://github.com/racket/racket/blob/45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b/racket/collects/racket/contract/private/arrow-val-first.rkt#L675-L692)。commit `45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b`。ファイルSHA-256 `271078a008dea702a68f48668796c07b3f15cb888541594580905de449b20475`。

> (raise-blame-error (blame-swap blame)

引数個数違反でcaller側のblameを持つ例外を上げる。

<a id="ra3"></a>
### RA3

位置: [racket/collects/racket/contract/private/blame.rkt:347–385](https://github.com/racket/racket/blob/45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b/racket/collects/racket/contract/private/blame.rkt#L347-L385)。commit `45f34393ed36f5d1bcf4dfe473dd2fd19c39e93b`。ファイルSHA-256 `d35ff3852ca0ad463ce65013de273d059cedb66412929dcda2a9121473cbe22b`。

> make-exn:fail:contract:blame

blame objectを例外へ格納。永続ログへの書込ではない。

<a id="lf1"></a>
### LF1

位置: [langfuse/model.py:88–114](https://github.com/langfuse/langfuse-python/blob/65392c73731e07711828745de337fdf7bba31fbc/langfuse/model.py#L88-L114)。commit `65392c73731e07711828745de337fdf7bba31fbc`。ファイルSHA-256 `9c72893f5a75431ac4f50de411f84ca013ed11df5a3ff5b84bc70b7ba0925a66`。

> return "".join(result_list)

固定textの部分と変数値を連結。未定義変数は元のplaceholderを残す。

<a id="lf2"></a>
### LF2

位置: [langfuse/_client/client.py:3874–3905](https://github.com/langfuse/langfuse-python/blob/65392c73731e07711828745de337fdf7bba31fbc/langfuse/_client/client.py#L3874-L3905)。commit `65392c73731e07711828745de337fdf7bba31fbc`。ファイルSHA-256 `f70853deb8ec1b9dc1895c6f5e83e02240d67e4b6d57ee598b3c5d33f6b59e58`。

> version: Optional[int] = None,

name/version/labelで取得しcacheやfallbackを使うAPI。

<a id="lf3"></a>
### LF3

位置: [langfuse/_client/attributes.py:133–146](https://github.com/langfuse/langfuse-python/blob/65392c73731e07711828745de337fdf7bba31fbc/langfuse/_client/attributes.py#L133-L146)。commit `65392c73731e07711828745de337fdf7bba31fbc`。ファイルSHA-256 `e7016e216e1aac43dde20cdceeabe4a66ee88056bebfcc8b49ca1b07708e6376`。

> if prompt and not prompt.is_fallback

promptがありfallbackでないときname/versionをtrace属性へ入れる。inputは別引数。

<a id="ml1"></a>
### ML1

位置: [mlflow/genai/prompts/utils.py:1–12](https://github.com/mlflow/mlflow/blob/3e1b7122cd9b9e887763fb0e7729bb4464fba0c4/mlflow/genai/prompts/utils.py#L1-L12)。commit `3e1b7122cd9b9e887763fb0e7729bb4464fba0c4`。ファイルSHA-256 `aebf51f29453f1139e3dd68f1ca68d028b67700f41da145640d4bddc8b07f884`。

> return prompt

double-brace形式の機械的置換。

<a id="ml2"></a>
### ML2

位置: [mlflow/entities/model_registry/prompt_version.py:537–573](https://github.com/mlflow/mlflow/blob/3e1b7122cd9b9e887763fb0e7729bb4464fba0c4/mlflow/entities/model_registry/prompt_version.py#L537-L573)。commit `3e1b7122cd9b9e887763fb0e7729bb4464fba0c4`。ファイルSHA-256 `d495ebdf614524cbab070fdba7b38d6be209947b4e9ae71921e6aac922841794`。

> if missing_keys := self.variables - input_keys:

通常は欠けた変数を拒否。allow_partialなら途中のPromptVersionを返す。

<a id="ml3"></a>
### ML3

位置: [mlflow/tracking/_model_registry/fluent.py:831–889](https://github.com/mlflow/mlflow/blob/3e1b7122cd9b9e887763fb0e7729bb4464fba0c4/mlflow/tracking/_model_registry/fluent.py#L831-L889)。commit `3e1b7122cd9b9e887763fb0e7729bb4464fba0c4`。ファイルSHA-256 `3ef2368114bd1d0adbf1794404f895702c2cec6bfe2fd4a5226dbfbaf28ca9e9`。

> InMemoryTraceManager.get_instance().register_prompt(

取得promptをactive run/traceへ関連付ける。実際の最終入力同一性の検査ではない。

<a id="nw1"></a>
### NW1

位置: [src/noworkflow/now/collection/prov_definition/definition.py:89–134](https://github.com/gems-uff/noworkflow/blob/4a2c4c8bdea2be73570a1aa598042940f4f4270f/src/noworkflow/now/collection/prov_definition/definition.py#L89-L134)。commit `4a2c4c8bdea2be73570a1aa598042940f4f4270f`。ファイルSHA-256 `72b3f16949255e2f73a74a300bb9184aa9f5788bbbe91e56c62d8368c22147d0`。

> tree = visitor.visit(tree)

AST変換して計測可能なコードをcompileする。source無編集とruntime非介入は違う。

<a id="nw2"></a>
### NW2

位置: [src/noworkflow/now/collection/prov_execution/collector.py:2011–2046](https://github.com/gems-uff/noworkflow/blob/4a2c4c8bdea2be73570a1aa598042940f4f4270f/src/noworkflow/now/collection/prov_execution/collector.py#L2011-L2046)。commit `4a2c4c8bdea2be73570a1aa598042940f4f4270f`。ファイルSHA-256 `4a1d73aef591de82b8585f2038100c32ebf9680c08210ae25b3867634819f014`。

> self.dependencies.add(

評価ID間の依存関係を記録する。

<a id="ht1"></a>
### HT1

位置: [gtpyhop.py:869–937](https://github.com/dananau/GTPyhop/blob/1ca7773963443476d0e83d03f10efab325327565/gtpyhop.py#L869-L937)。commit `1ca7773963443476d0e83d03f10efab325327565`。ファイルSHA-256 `13f68999e07bd6dc3d327e44c1fa317ff480e0f9d522acf3a5c21aa03a7401ff`。

> plan = find_plan(state, todo_list)

plannerを呼び、command失敗時に再計画するactor。外部セル境界はこのAPIに含まれない。

<a id="ds1"></a>
### DS1

位置: [dspy/signatures/signature.py:35–38](https://github.com/stanfordnlp/dspy/blob/40a6e168914a7b81a78b1a081d93f26de18c8d0d/dspy/signatures/signature.py#L35-L38)。commit `40a6e168914a7b81a78b1a081d93f26de18c8d0d`。ファイルSHA-256 `6dc35055b0a3690fb559816c19d89f7a3d5f841c04b409d817ee21f7389b892c`。

> Given the fields

instruction未指定時の既定指示文を組み立てる。

<a id="ds2"></a>
### DS2

位置: [dspy/signatures/signature.py:185–201](https://github.com/stanfordnlp/dspy/blob/40a6e168914a7b81a78b1a081d93f26de18c8d0d/dspy/signatures/signature.py#L185-L201)。commit `40a6e168914a7b81a78b1a081d93f26de18c8d0d`。ファイルSHA-256 `6dc35055b0a3690fb559816c19d89f7a3d5f841c04b409d817ee21f7389b892c`。

> cls.__doc__ = _default_instructions(cls)

instruction未指定時に既定指示の生成を実際に呼ぶ。

<a id="hkj"></a>
### HKJ

位置: [KB](https://kubernetes.io/docs/concepts/workloads/controllers/job/)、抽出テキスト 1524 行付近。SHA-256は取得表参照。

> Once a rule matches a Pod failure, the remaining rules

podFailurePolicyは順序を持つ規則。

<a id="hkv"></a>
### HKV

位置: [KV](https://kubernetes.io/docs/reference/using-api/api-concepts/)、抽出テキスト 1866 行付近。SHA-256は取得表参照。

> The API server rejects the request with a 400 Bad Request error

Strictのfield validationで不正fieldを拒否する仕様。Warn/Ignoreと区別する。

<a id="hka2"></a>
### HKA2

位置: [KA](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)、抽出テキスト 955 行付近。SHA-256は取得表参照。

> ResponseComplete - The response body has been completed

応答完了stageの定義。policyとbackendの条件付きaudit。

<a id="hka"></a>
### HKA

位置: [KA](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)、抽出テキスト 1137 行付近。SHA-256は取得表参照。

> events are dropped.

batch auditのbuffer超過による脱落。

<a id="hph"></a>
### HPH

位置: [PF](https://pekko.apache.org/docs/pekko/current/typed/failure-detector.html)、抽出テキスト 207 行付近。SHA-256は取得表参照。

> phi = -log10(1 - F(timeSinceLastHeartbeat))

phiの計算仕様。完璧な故障判定の保証ではない。

<a id="hcb"></a>
### HCB

位置: [CB](https://resilience4j.readme.io/docs/circuitbreaker)、抽出テキスト 69 行付近。SHA-256は取得表参照。

> The state of the CircuitBreaker changes from CLOSED to OPEN when the failure rate is equal or greater than a configurable threshold.

最低呼出数等の前提の下で、失敗率が閾値以上ならCLOSEDからOPENへ移る仕様。

<a id="hlf"></a>
### HLF

位置: [LF](https://langfuse.com/docs/prompt-management/get-started)、抽出テキスト 163 行付近。SHA-256は取得表参照。

> Insert variables into prompt template

事前promptを取り出して変数を展開する利用仕様。

<a id="hml"></a>
### HML

位置: [ML](https://mlflow.org/docs/latest/genai/prompt-registry/)、抽出テキスト 132 行付近。SHA-256は取得表参照。

> fill in the variables using the

版を取得してformatする利用仕様。immutabilityの案内はあるが、全書込経路の強制確認とはしていない。

<a id="htr"></a>
### HTR

位置: [TR](https://docs.temporal.io/encyclopedia/retry-policies)、抽出テキスト 141 行付近。SHA-256は取得表参照。

> If this limit is exceeded, the execution fails without retrying again.

Maximum Attemptsによる再試行終了の仕様。

<a id="htr2"></a>
### HTR2

位置: [TR](https://docs.temporal.io/encyclopedia/retry-policies)、抽出テキスト 252 行付近。SHA-256は取得表参照。

> Use the Describe API to get a pending Activity

Activity再試行中の開始eventをhistoryへ直ちに載せないという説明。

<a id="hsq"></a>
### HSQ

位置: [SQ](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)、抽出テキスト 78 行付近。SHA-256は取得表参照。

> there's no absolute guarantee that a

visibility timeout内でも重複配信を絶対排除しない。再配信と故障証明を分ける。

<a id="hkf"></a>
### HKF

位置: [KF](https://kafka.apache.org/41/design/design/)、抽出テキスト 301 行付近。SHA-256は取得表参照。

> It can read the messages, process the messages, and finally save its position.

処理後のoffset記録前の停止による重複。PDAの仕事の中断状態とは異なる。

<a id="hpr"></a>
### HPR

位置: [PR](https://www.w3.org/TR/prov-constraints/)、抽出テキスト 150 行付近。SHA-256は取得表参照。

> A PROV instance is a set of PROV statements.

PROVは記述のデータモデルと整合性制約であり、全行為の自動捕捉器ではない。

<a id="hpa"></a>
### HPA

位置: [PA](https://www.w3.org/TR/prov-aq/)、抽出テキスト 158 行付近。SHA-256は取得表参照。

> A provenance record is not of itself guaranteed to be authoritative or correct.

provenance記録の真実性を別に扱う明記。

<a id="hcd"></a>
### HCD

位置: [CD](https://www.w3.org/TR/ws-cdl-10/)、抽出テキスト 7 行付近。SHA-256は取得表参照。

> their common and complementary observable behavior

WS-CDLのglobalな参加者関係。Candidate Recommendationの地位も取得文面で確認。

<a id="hre"></a>
### HRE

位置: [RE](https://docs.drools.org/7.0.0.Final/kie-api-javadoc/org/kie/api/event/rule/AgendaEventListener.html)、抽出テキスト 40 行付近。SHA-256は取得表参照。

> afterMatchFired

発火後listenerのAPI。強制記録の実装対としては未確認。

<a id="hva"></a>
### HVA

位置: [VA](https://www2.informatik.uni-hamburg.de/TGI/publikationen/public/biblio_valk_eng.html)、抽出テキスト 307 行付近。SHA-256は取得表参照。

> Self-modifying nets, a natural extension of Petri nets.

著者書誌で1978年論文の所在だけを確認。本文の性質の根拠にはしない。

<a id="hbd"></a>
### HBD

位置: [BD](https://jason-lang.github.io/jason/tech/concurrency.html)、抽出テキスト 90 行付近。SHA-256は取得表参照。

> sense, deliberate, and act.

BDI cycleと外部eventによるintention生成。前段出力だけへの制限ではない。

<a id="hrb"></a>
### HRB

位置: [RB](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/circuit_breaking)、抽出テキスト 87 行付近。SHA-256は取得表参照。

> the overall retry volume cannot

retry budgetは全体再試行量の制限という指定起点。固定実装の照合は未実施。

<a id="hds"></a>
### HDS

位置: [DSF](https://dspy.ai/current/getting-started/expanding-signatures/)、抽出テキスト 28 行付近。SHA-256は取得表参照。

> Adding additional inputs and outputs

signatureの入力・出力fieldを追加・型付けする仕様。

<a id="pff"></a>
### PFF

位置: [FF](https://users.cs.northwestern.edu/~robby/pubs/papers/ho-contracts-icfp2002.pdf)、PDF物理 4 ページ。SHA-256は取得表参照。

> the function’s caller is responsible.

高階契約の負位置でcallerへ責任を帰す規則。現行Racket全体の同一計算体系の証明とはしない。

<a id="pct"></a>
### PCT

位置: [CT](https://www.cs.toronto.edu/~christoff/files/UnreliableFailureDetectorsForReliableDistributedSystems.pdf)、PDF物理 8 ページ。SHA-256は取得表参照。

> No process is suspected before it crashes.

strong accuracyの定義。Pekkoがこの性質を満たすとは主張しない。

<a id="phy"></a>
### PHY

位置: [HY](https://cseweb.ucsd.edu/classes/wi19/cse221-a/papers/wulf74.pdf)、PDF物理 2 ページ。SHA-256は取得表参照。

> Separation of mechanism and policy.

方針と機構を分ける設計原則。PDAやOPAとの形式的refinement証明ではない。

<a id="pnw"></a>
### PNW

位置: [NW](https://www.vldb.org/pvldb/vol10/p1841-pimentel.pdf)、PDF物理 2 ページ。SHA-256は取得表参照。

> and other variable dependencies

細粒度計測で変数依存を採取する説明。

<a id="pnw2"></a>
### PNW2

位置: [NW](https://www.vldb.org/pvldb/vol10/p1841-pimentel.pdf)、PDF物理 4 ページ。SHA-256は取得表参照。

> network activity or database accesses directly

network/DBを直接採取せず、その呼出しを採取する限界。

<a id="pht"></a>
### PHT

位置: [HT](https://www.cs.umd.edu/users/nau/papers/bansod2022htn.pdf)、PDF物理 1 ページ。SHA-256は取得表参照。

> unexpected states

実行中の予想外状態と再計画を分離する研究の動機。

<a id="pbp"></a>
### PBP

位置: [BP](https://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.pdf)、PDF物理 2 ページ。SHA-256は取得表参照。

> Executable business processes model actual

WS-BPELは参加者の実行可能processと抽象processを区別する。

<a id="pai"></a>
### PAI

位置: [AI](https://arxiv.org/pdf/1611.09067)、PDF物理 3 ページ。SHA-256は取得表参照。

> Each scope identifies a coordinator

scopeごとの更新調停主体を持つ動的choreography。

<a id="pai2"></a>
### PAI2

位置: [AI](https://arxiv.org/pdf/1611.09067)、PDF物理 48 ページ。SHA-256は取得表参照。

> queries the Adaptation Manager

runtimeに更新候補を外部のmanager/serverへ問い合わせる。

<a id="pgr"></a>
### PGR

位置: [GR](https://groove.cs.utwente.nl/grammars/sttt2011.pdf)、PDF物理 2 ページ。SHA-256は取得表参照。

> Graphs are transformed by applying rules.

グラフの適用条件と追加削除を表現。前段指示の必須性は対象modelに依存。

## 3. 取得状態と探索の限界

採用した資料と固定Git資料は全件HTTP 200で取得した。DSPyのDS/DSCはHTTP 200だが誘導HTMLだった。誘導先DSFで本文を取得し、HDSと固定Git sourceのDS1/DS2を根拠にした。Valkは著者の書誌を取得したが論文本体の取得先を確定できず、本文未取得である。論文本体へHTTP要求を送っていないため、これを403/404等の取得失敗とは記録しない。Chandra–Touegは大学配布PDFを用いた。HYDRA、GROOVE、AIOC、WS-BPEL/WS-CDL、BDI、PROV、SQS、Kafka、retry budget、Droolsについて、記載した範囲を超える固定実装の強制位置は確認していない。

専用のdeep_research実行ツールはこの環境に公開されていないため、HANDOVERのdeep research手順に従い、一次資料探索、固定取得、コード読解、再取得照合を行った。別サービスによる調査を実行したという意味ではない。

実行検証・障害注入・複数部品の接続・PDA受け入れ試験は行っていない。引用の再取得結果と修正点は [06-review.md](06-review.md) に記録する。
