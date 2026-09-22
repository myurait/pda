# PDA v0.2 増分1 実装報告

実施日: 2026-09-22 JST。作業ブランチ: `increment-1`。分岐元 `main`: `3bc522a`。実行環境: 開発MacのDocker Desktop、Linux arm64、Docker Engine 27.4.0、8 CPU、割当メモリ約10.93 GiB。ミニPCへの配置は未実施です。

## 1. 作ったもの

| 置き場所 | 内容 |
|---|---|
| `pyproject.toml`、`uv.lock` | Python 3.12と依存の固定。ホストの試験は3.12.7、コンテナは3.12.12 |
| `registry/` | 7 type、6実行器、7事前プロンプト、4問、2回分のfixture、DO_WHILE雛形 |
| `tools/` | 19タスク定義と1ワークフローの生成、dry-run、冪等な作成・更新 |
| `src/pda_wrapper/` | Conductor SDKワーカー、ACP/jev/tools操作役、分類・スキーマ検査、OTLPログ・スパン |
| `src/pda_fake_agent/` | ACP SDKによる echo / invalid / slow / permission エージェント |
| `src/pda_mirror/` | 3秒ごとの状態差分と終了後の最終取得、動的セルの出所記録 |
| `deploy/` | 固定イメージのCompose、Collector設定、実行器Dockerfile、環境変数例 |
| `tests/` | 単体試験と `PDA_E2E=1` でのみ実行する6シナリオ |
| `docs/runbook/` | 配置、認証、実Codex、jev検証の人向け手順 |
| `docs/reports/evidence/increment-1/` | 実際のConductor記録、イベント、SQL応答、試験結果、使用イメージ、メモリ計測 |

`docs/requirements.md`、`docs/design/`、`docs/research/`、`docs/process/` は変更していません。`main` の先端も変更していません。秘密情報用の `secrets/`、`*.credentials`、`.env` はGit対象外です。Dockerのビルドコンテキストからも除外しています。

## 2. 使ったイメージと版、依存パッケージと版

| 実行イメージ | 今回のアーキテクチャ |
|---|---|
| conductoross/conductor:3.32.4 | arm64 |
| docker.elastic.co/elasticsearch/elasticsearch:7.17.29 | arm64 |
| otel/opentelemetry-collector-contrib:0.148.0 | arm64 |
| pda-executor:increment-1 | arm64 |
| pda-executor:increment-1-real | arm64 |
| public.ecr.aws/zinclabs/openobserve:v0.60.1 | arm64 |
| redis:6.2.21-alpine | arm64 |

Conductor UIは公式のサーバイメージに同梱されたUIを、別サービスからnginxだけ起動して配信しています。Javaサーバを二重起動しません。イメージIDと取得済みdigestは [images.json](evidence/increment-1/images.json) にあります。

ビルドに使用した固定イメージは `python:3.12.12-slim-bookworm`、`ghcr.io/astral-sh/uv:0.12.17`、real用の `node:22.22.2-bookworm-slim` です。real用イメージのビルドは成功しました。real profileの実行器は起動していません。e2eは環境の設定にかかわらずJEV_MODE=fixture、real profile無効を指定します。

| Python直接依存 | 版 |
|---|---|
| conductor-python | 2.0.0 |
| agent-client-protocol | 0.12.1 |
| opentelemetry-sdk | 1.44.0 |
| opentelemetry-exporter-otlp-proto-http | 1.44.0 |
| jsonschema | 4.26.0 |
| pyyaml | 6.0.3 |
| httpx | 0.28.1 |
| pytest | 9.1.1 |
| ruff | 0.16.8 |

ビルド依存は `hatchling==1.29.0`、uvは0.12.17です。推移依存は `uv.lock` に固定しています。npmのACPアダプタは指定どおりCodexが版指定なし、Claudeが `@preview` なので、その取得版は固定されていません。今回取得・起動していません。

## 3. 確かめたこと

1. e2e 1: 正常完了。job_id=`88c1a6b2-1e82-42c7-94d2-61cbab132e06`。`judge__1` が `break-down.fake-a` と `verify.test.tools` を生成し、両方が `COMPLETED`、`judge__2` がfinishを返し、ワークフローが `COMPLETED` になりました。tools側のpytestも終了コード0です。[Conductor全記録](evidence/increment-1/normal-workflow.json)
2. e2e 2: Collectorの名前付きボリュームにある `/var/lib/pda/events/events.jsonl` から、同じjob_idの `job.received`、`input.assembled`、`tool.call`、`tool.result`、`turn.end`、`output.classified`、`command.run`、`judge.answer`、`engine.task` を取得しました。動的セルの `pda.origin_cell` は `judge__1` です。[取得したイベント](evidence/increment-1/normal-events.json)
3. e2e 3: OpenObserveのSQL検索はHTTP 200、同じjob_idの行が 36 件返りました。クエリは `SELECT * FROM "pda" WHERE pda_job_id = '<job_id>' LIMIT 100` です。[SQLと実応答](evidence/increment-1/openobserve-search.json)
4. e2e 4: job_id=`8b163b46-d1d7-407a-bbd5-0885cdd9133b`。invalidモードの `implement.fake-b` は `FAILED_WITH_TERMINAL_ERROR`、`retryCount=0`、理由 `invalid_kind_or_missing_payload`。`output.rejected` も記録されました。[タスク記録](evidence/increment-1/invalid-workflow.json)、[出来事](evidence/increment-1/invalid-events.json)
5. e2e 5: job_id=`f2f6abd3-838f-4fa3-bf86-4a98c839bd78`。応答時間切れ、`retryCount` の増加、両試行の `inputData` の完全一致、復旧した実行器による再試行のCOMPLETED、`engine.task` の理由と再試行回数を確認しました。試験用定義は応答30秒、再試行1回、待機1秒です。通常設定のリース延長は有効であり、試験対象fake-bだけSDKのリース延長を無効にしました。タイムアウト後はfake-bをechoモードで再作成し、SIGTERMによる旧セッションの中断後に同じ入力の再試行を実行し、ワークフロー全体の完了まで確認しました。[Conductor記録](evidence/increment-1/timeout-workflow.json)、[出来事](evidence/increment-1/timeout-events.json)
6. e2e 6: 当該Composeプロジェクトのコンテナに対する `docker stats --no-stream` を保存しました。[計測原本](evidence/increment-1/docker-stats.txt)

単体試験: `53 passed in 3.09s`。e2e: `6 passed in 86.04s (0:01:26)`。`ruff check` と `git diff --check` は成功しました。通常の `pytest -q` は53件成功・e2e 6件skipでした。 [単体試験](evidence/increment-1/unit-tests.txt)、[e2e試験](evidence/increment-1/e2e-tests.txt)、[既定の試験](evidence/increment-1/default-tests.txt)、[ruff](evidence/increment-1/ruff.txt) に結果を保存しています。既存定義に対する登録を続けて2回実行し、双方で成功しました。新規作成と既存更新のHTTP分岐は単体試験でも確認しています。[登録応答](evidence/increment-1/registration.json)

ACPはモック通信だけでなく実際の子プロセスとのSDK往復、権限選択、キャンセルを単体試験で確認しました。jevのHTTP送信はモックで送信先、Bearer認証、state/model/questionsの形式を確認しており、実APIは呼んでいません。Conductor UIのHTTP配信とUI経由のAPIプロキシはいずれも200でした。

## 4. 5節のどちらの形で動いたか

DO_WHILE内に判定器、SWITCH、動的フォーク、JOINを置く形で動きました。SWITCHは指定の `value-param` のままです。correlationIdで別ワークフローを連結する代替は使用していません。

最初は指定雛形のループ条件 `$.judge['output']['payload']['then'] == 'continue'` で失敗しました。実際のConductorの応答は次のとおりです。

```json
{
  "workflowId": "1d2335ba-1e6a-422b-ac39-3adacb1bf285",
  "status": "FAILED",
  "reasonForIncompletion": "Task eef40ec2-af01-4b43-9604-413d20f2f566 failed with status: FAILED and reason: 'Unable to evaluate condition $.judge['output']['payload']['then'] == 'continue', exception Error evaluating the script `TypeError: Cannot read property 'payload' of undefined` at line 1'"
}
```

[元の全記録](evidence/increment-1/initial-loop-failure.json)。Conductor 3.32.4の [DoWhile.evaluateCondition](https://github.com/conductor-oss/conductor/blob/v3.32.4/core/src/main/java/com/netflix/conductor/core/execution/tasks/DoWhile.java) は条件用の `judge` に `outputData` を直接設定するため、条件を `$.judge['payload']['then'] == 'continue'` に修正しました。登録拒否、2周目の参照解決失敗、SWITCHの評価失敗は発生しませんでした。この条件の修正は指示に無かった判断です。保護された設計文書は修正していません。

## 5. 時間切れ、再試行、終端失敗の実際の欄

以下は保存したConductor JSONから対象欄を抜粋したものです。全文は3節のリンク先にあります。

時間切れと再試行:

```json
[
  {
    "taskId": "2f09d28d-3caf-4390-9eb7-7fc1bc0c04e3",
    "referenceTaskName": "c1__1",
    "taskDefName": "implement.fake-b",
    "status": "TIMED_OUT",
    "retryCount": 0,
    "reasonForIncompletion": "responseTimeout: 30 exceeded for the taskId: 2f09d28d-3caf-4390-9eb7-7fc1bc0c04e3 with Task Definition: implement.fake-b",
    "responseTimeoutSeconds": 30,
    "workerId": "fake-b",
    "startTime": 1790068421463,
    "inputData": {
      "input": "README を要約せよ",
      "job_id": "f2f6abd3-838f-4fa3-bf86-4a98c839bd78",
      "context": {},
      "prompt_ref": {
        "id": "implement",
        "version": 1
      },
      "type": "implement",
      "cell_id": "c1"
    }
  },
  {
    "taskId": "bc96d281-cd0f-42fa-bccc-a001155de6c9",
    "referenceTaskName": "c1__1",
    "taskDefName": "implement.fake-b",
    "status": "COMPLETED",
    "retryCount": 1,
    "reasonForIncompletion": null,
    "responseTimeoutSeconds": 30,
    "workerId": "fake-b",
    "startTime": 1790068456230,
    "inputData": {
      "context": {},
      "input": "README を要約せよ",
      "prompt_ref": {
        "id": "implement",
        "version": 1
      },
      "type": "implement",
      "job_id": "f2f6abd3-838f-4fa3-bf86-4a98c839bd78",
      "cell_id": "c1"
    }
  }
]
```

終端失敗:

```json
[
  {
    "taskId": "10000d2c-2eac-4498-ba99-b891499614c9",
    "referenceTaskName": "c1__1",
    "taskDefName": "implement.fake-b",
    "status": "FAILED_WITH_TERMINAL_ERROR",
    "retryCount": 0,
    "reasonForIncompletion": "invalid_kind_or_missing_payload",
    "responseTimeoutSeconds": 600,
    "workerId": "fake-b",
    "startTime": 1790068416406,
    "inputData": {
      "input": "README を要約せよ",
      "job_id": "8b163b46-d1d7-407a-bbd5-0885cdd9133b",
      "context": {},
      "prompt_ref": {
        "id": "implement",
        "version": 1
      },
      "type": "implement",
      "cell_id": "c1"
    }
  }
]
```

時間切れの規則は `responseTimeoutSeconds` と `reasonForIncompletion` に表れます。再試行は別の `taskId` で作成され、同じ `referenceTaskName` と入力を保持して `retryCount` が増えます。再試行側自身の `reasonForIncompletion` がnullでも、直前試行のTIMED_OUTの理由を同じセル参照で追跡できます。終端失敗はラッパーの `NonRetryableException` がSDKにより `FAILED_WITH_TERMINAL_ERROR` と理由へ変換されます。写しはこれらの実記録を `pda.status`、`pda.retry_count`、`pda.reason` に記録します。

## 6. ACP Python SDKとCodexの権限要求

`agent-client-protocol==0.12.1` はクライアント側の `spawn_agent_process` を提供しました。JSON-RPCの自作はしていません。`initialize`、`session/new`、`session/prompt`、`session/cancel` をSDK経由で使用しています。未知の通知をSDKの型検査より前に拾うため、SDKのstream observerで通知を辞書として受けています。[SDK公式資料](https://agentclientprotocol.github.io/python-sdk/)

試験用エージェントのpermissionモードでは権限要求に `allow_once` で応答することを確認しました。拒否種別は `reject_once` を選び、該当する選択肢がなければcancelledを返します。実Codexアダプタが権限要求を出すかは未確認です。fakeの結果から実Codexの動作は判断していません。

## 7. docker statsの結果

```text
CONTAINER ID   NAME                                        CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O         PIDS
7b709e9d077c   pda-increment-1-conductor-elasticsearch-1   2.36%     872.5MiB / 10.93GiB   7.79%     1.82MB / 794kB    4.1kB / 30.7MB    105
89730bf8c191   pda-increment-1-conductor-mirror-1          0.12%     34.65MiB / 10.93GiB   0.31%     868kB / 63.4kB    0B / 5.23MB       4
e5b9075bad0b   pda-increment-1-conductor-redis-1           4.11%     12.14MiB / 10.93GiB   0.11%     167MB / 288MB     12.3kB / 21.1MB   6
3afe2f2ad954   pda-increment-1-conductor-server-1          23.11%    760MiB / 10.93GiB     6.79%     297MB / 193MB     668kB / 2.83MB    225
0eea656e86df   pda-increment-1-conductor-ui-1              0.00%     8.832MiB / 10.93GiB   0.08%     5.97kB / 6.1kB    2.08MB / 324kB    9
8b45dc311153   pda-increment-1-exec-fake-a-1               2.02%     292.8MiB / 10.93GiB   2.62%     178kB / 165kB     0B / 11.6MB       13
085476a32c6a   pda-increment-1-exec-fake-b-1               1.73%     307.2MiB / 10.93GiB   2.74%     35.8kB / 33.6kB   0B / 3.04MB       13
6b6b711e8e7c   pda-increment-1-exec-jev-1                  0.50%     150.4MiB / 10.93GiB   1.34%     161kB / 56.8kB    508kB / 12.1MB    10
108f70995d91   pda-increment-1-exec-tools-1                1.13%     195.8MiB / 10.93GiB   1.75%     91.8kB / 87.5kB   0B / 18.7MB       11
e55c1e143cef   pda-increment-1-openobserve-1               0.19%     349.8MiB / 10.93GiB   3.12%     82.1MB / 477kB    2.72MB / 80.1MB   53
2a1c1413e6b0   pda-increment-1-otel-collector-1            0.16%     44.88MiB / 10.93GiB   0.40%     564kB / 334kB     0B / 664kB        12
```

この値は開発MacのDocker Desktopでの1回の観測です。同じDocker上では既存の他プロジェクトも動いています。ミニPC上の値ではありません。試験後はタスク定義を通常の応答600秒・再試行3回に戻し、試験用Composeを停止しました。名前付きボリュームは保持しています。

## 8. 指示に無かった判断と、指示どおりにできなかったこと

1. 4節のループ条件を修正しました。動的フォークの実行記録では `taskType` が `FORK`、`workflowTask.type` が `FORK_JOIN_DYNAMIC` になることも実機で確認し、後者と入力のdynamicTasksを使って出所を辿っています。
2. ConductorのinputSchema/outputSchemaは、JSON Schemaを直接置く形ではなく `{name, version, type: "JSON", data}` のSchemaDefに包んで登録しました。タスクの `enforceSchema` はtrueです。出力の検査はラッパーでも行います。
3. UIは公式サーバイメージ同梱の静的UIを別サービスで配信します。Docker Desktopではinternalネットワークだけに接続したコンテナの公開ポートが到達不能だったため、公開対象の3サービスだけにingressネットワークを追加しました。実行器ごとの内部ネットワークは分離しています。
4. このMacのControl Centerが5000番を使用していたため、Git対象外の `.env` にだけ `CONDUCTOR_UI_PORT=15000` を設定しました。Composeの既定は5000番です。APIは8080、OpenObserveは5080です。
5. Dockerネットワークだけでは外向き通信を宛先ドメインに制限していません。jev、Codex、Claudeのegressは許可ドメイン以外にも到達可能です。Codex/Claudeの指定npxコマンドにはnpmからの取得も必要です。fakeとtoolsは外向きネットワークに接続していません。名前付きボリューム `/work` は指定どおり共有します。
6. Collectorのfile exporterは100 MBで回転する設定です。日付による独立した24時間回転は設定していません。[file exporterの設定型](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.148.0/exporter/fileexporter/config.go) の `max_days` は保持期間の指定であり、日次回転と混同しないため設定していません。100 MB到達時の実際の回転試験は未実施です。
7. 応答時間切れの試験は、通常の心拍延長と両立しないため試験対象だけ無効化しています。最初に使ったドット入り環境変数名はエントリポイントのシェルが引き継がず、心拍が続きました。SDKが対応する大文字とアンダースコアの名前に変更しました。通常の `worker_task` は `lease_extend_enabled=True` です。
8. ACP 0.12.1のusage_updateにある `used`/`size` はコンテキスト占有量/容量なので、入出力トークン数へ置き換えていません。その形しか無い場合はunknownで元データを記録し、明示的なinputTokens/outputTokensがある場合だけusageへ写します。Codexの起動モードは権限要求の有無にかかわらずjob.receivedへ記録します。
9. 指定の3秒ポーリングでは、起動・終了の全体が取得間隔より短い仕事やプロセス停止中の仕事を見落とす場合があります。今回のe2eは実際に記録を取得できる時間のfixtureで確認しました。写しの終了時取得がHTTPエラーの場合は取得できるまで次回へ持ち越します。
10. 停止処理の追加試験では、キャンセル後にSDKへ戻る旧ワーカーが再試行を受け取り得る問題を確認しました。再試行も時間切れになった [実記録](evidence/increment-1/recovery-failure-workflow.json) と [出来事](evidence/increment-1/recovery-failure-events.json) を保存しています。SIGTERM時はキャンセルと送出を終えてワーカープロセスを終了し、SDKのポーリングへ戻らないよう修正しました。子プロセスにSIGTERMを送る回帰試験を追加しました。
11. Conductorの応答時間切れは再試行をキューに入れますが、稼働中のACP子プロセスを自動で停止しません。ラッパーは指定どおりSIGTERMでsession/cancelを送ります。試験では実行器の再作成で復旧させました。
12. 入力でcontextを省略したときのConductorのnullを判定器で空オブジェクトへ正規化します。プロンプト版は1のみです。未検証の実API費用は宣言でnullにしています。実行器の権限、型選択、固定コマンド以外の割り振りや追加機能は実装していません。

## 9. 未実施のこと

1. ミニPCへの配置とその機械上のリソース計測。
2. 個人契約Codexと会社契約Claudeのログイン、認証ディレクトリの可用性確認、実アダプタでの実行。
3. jev実APIの呼び出しと `jev-verify` による実データ検証。`is_complete=0.7` は未検証の仮値です。
4. Codex/Claudeの実際の権限要求、課金、通知の網羅性。

これらの認証と実機操作の手順は [手順書](../runbook/increment-1.md) に記載しました。
