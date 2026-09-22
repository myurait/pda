# 増分 2 の実装報告

実施日: 2026-09-22。作業ブランチ: `increment-2`。起点 `main`: `31a6a5b648b5ffd73e0178eb77c2a95f0c042bce`。要件ファイルの Git blob は `3580fc7017b1264e22b1669e476338722f3ce4b6`。

実行指示書 `docs/codex-runs/2026-09-22-increment-2.md` に従って実装した。指定された要件・基本設計・増分 1 の設計を読み、既存の報告書や他の実行指示書は参照していない。要件、設計、調査、プロセス文書と既存報告書は変更していない。

## 1. 作ったもの

| 場所 | 内容 |
|---|---|
| `pyproject.toml`、`uv.lock`、`.python-version` | Python 3.12 の pda パッケージと依存の固定 |
| `registry/types/` | 7 type の Draft 7 入出力スキーマ、再試行、期限 |
| `registry/prompts/` | 日本語の事前プロンプト 7 ファイル |
| `registry/executors/` | 6 実行器の宣言 |
| `registry/judge/` | 4 問、閾値、3 段の fixture |
| `registry/workflows/` | 指示書と同一の `pda_job` 雛形 |
| `tools/` | 19 タスク定義と 1 ワークフローの生成・冪等登録 |
| `src/pda_wrapper/` | asyncio ワーカー、分類、スキーマ検査、OTLP 送信、ACP・jev・tools 操作役 |
| `src/pda_fake_agent/` | ACP SDK の試験用エージェント 4 モード |
| `src/pda_mirror/` | 3 秒間隔の差分取得、最終取得、動的セルの出所の照合 |
| `deploy/` | Compose、Conductor・nginx・Collector 設定、実行器 Dockerfile |
| `tests/` | 単体試験と、`PDA_E2E=1` のときだけ動く e2e 8 項目 |
| `docs/runbook/` | ミニ PC 配置、認証、実 Codex 確認の人手用手順 |
| `docs/reports/evidence/increment-2/` | 実測の抜粋。各ファイル 300 行以下 |

## 2. 使ったイメージと版、依存パッケージと版

| 用途 | イメージ |
|---|---|
| Conductor サーバ・UI | `conductoross/conductor:3.32.4` |
| Redis | `redis:6.2.21-alpine` |
| Elasticsearch | `docker.elastic.co/elasticsearch/elasticsearch:7.17.29` |
| Collector | `otel/opentelemetry-collector-contrib:0.148.0` |
| OpenObserve | `public.ecr.aws/zinclabs/openobserve:v0.60.1` |
| Python 基底 | `python:3.12.12-slim-bookworm` |
| real profile の Node.js 基底 | `node:22.22.0-bookworm-slim` |
| ビルド用 uv | `ghcr.io/astral-sh/uv:0.12.17` |
| 自作の通常実行器・写し | `pda-executor:increment-2` |
| 自作の実 ACP 実行器 | `pda-executor-real:increment-2` |

通常実行器と real profile のイメージはビルド成功。real profile のコンテナは起動していない。取得したイメージ ID と digest は [images.json](evidence/increment-2/images.json)。ホストでの単体試験は Python 3.12.7、uv 0.12.17、Docker Engine 27.4.0。コンテナの Python は 3.12.12。

`uv.lock` に記録されたパッケージは以下のとおり。`colorama` は Windows 条件付き依存を含む。`conductor-python` は使用していない。

ビルドバックエンドは `hatchling==1.29.0` を pyproject.toml で指定した。

| パッケージ | 版 |
|---|---|
| `agent-client-protocol` | `0.12.1` |
| `annotated-types` | `0.8.0` |
| `anyio` | `4.15.1` |
| `attrs` | `26.1.0` |
| `certifi` | `2026.7.22` |
| `charset-normalizer` | `3.5.1` |
| `colorama` | `0.4.6` |
| `googleapis-common-protos` | `1.75.3` |
| `h11` | `0.16.0` |
| `httpcore` | `1.0.9` |
| `httpx` | `0.28.1` |
| `idna` | `3.20` |
| `iniconfig` | `2.3.0` |
| `jsonschema` | `4.26.0` |
| `jsonschema-specifications` | `2025.9.1` |
| `opentelemetry-api` | `1.44.0` |
| `opentelemetry-exporter-otlp-proto-common` | `1.44.0` |
| `opentelemetry-exporter-otlp-proto-http` | `1.44.0` |
| `opentelemetry-proto` | `1.44.0` |
| `opentelemetry-sdk` | `1.44.0` |
| `opentelemetry-semantic-conventions` | `0.65b0` |
| `packaging` | `26.3` |
| `pda` | `0.2.0` |
| `pluggy` | `1.6.0` |
| `protobuf` | `7.36.2` |
| `pydantic` | `2.13.5` |
| `pydantic-core` | `2.46.5` |
| `pygments` | `2.21.0` |
| `pytest` | `9.1.1` |
| `pyyaml` | `6.0.3` |
| `referencing` | `0.37.0` |
| `requests` | `2.34.2` |
| `rpds-py` | `2026.6.3` |
| `ruff` | `0.16.8` |
| `typing-extensions` | `4.16.0` |
| `typing-inspection` | `0.4.4` |
| `urllib3` | `2.8.0` |

## 3. 部品ごとの受け入れ条件の合否と確かめ方

`ruff check` 成功、`pytest tests/unit` は 65 件成功。実行結果は [quality.txt](evidence/increment-2/quality.txt)。

| 条件（指示書 10 節） | 合否 | 確かめ方 |
|---|---|---|
| 正本 | 合 | 7 type、6 実行器、4 問、fixture 3 段を検査。全スキーマに `Draft7Validator.check_schema`。雛形を指示書の JSON と完全比較 |
| 定義の生成と登録 | 合 | サーバなしの dry-run、19+1 の生成を単体試験。実 Conductor に連続 2 回登録して成功 |
| 起動とポーリング | 合 | 定義ファイルの読み取り回数を記録し各 1 回。宣言した 4 タスク名だけのポーリング。別プロセスへの SIGTERM 後にポーリング要求がないことを記録 |
| ラッパーの期限 | 合 | タスク JSON の `responseTimeoutSeconds=30` と fake slow で約 20 秒後に `FAILED/runtime_deadline`。`turn.end=cancelled` を確認 |
| ラッパーの停止 | 合 | 別プロセスへの SIGTERM で `FAILED/interrupted`、`turn.end=cancelled`、20 秒以内の終了を確認。ACP 直接接続でも cancel への応答 `cancelled` を確認 |
| 分類とスキーマ検査 | 合 | 4 段の分類、2 種の拒否理由、jev/tools の非構造化出力拒否、continue の空 cells・空 dynamicTasks 拒否を試験 |
| 出来事 | 合 | 表の全 18 種と未知の種別の unknown 変換。10 KB 切り詰め。SDK が生成した OTLP の log/span ID を SHA-256 の期待値と比較 |
| ACP の操作役 | 合 | SDK の子プロセスと echo、invalid、slow、permission の実往復。許可・拒否・選択肢不在の応答、raw observer、usage、stderr の分離を試験 |
| jev の操作役 | 合 | 3 段と試験用 override、最終回の最大 retryCount 選択、数値順の入力連結、API の URL・認証ヘッダ・本文をモック検査、未対応ペア拒否 |
| tools の操作役 | 合 | 終了コード 0 と 7 の passed、workdir、stdout/stderr を検査。期限後に子プロセス PID が存在しないことを確認 |
| 試験用エージェント | 合 | 4 モードを実行し、slow は session/cancel だけで prompt 応答を cancelled にすることを確認 |
| 写し | 合 | 同じ状態の再取得で出来事を重複送出しないこと、最終取得の HTTP エラー持ち越し、成功後の記録破棄、出所の一致・不一致を試験 |
| compose | 合 | 公開ポート・内部ネットワーク所属を検査。fake-a コンテナから openobserve:5080 に接続できないこと、UI と /api プロキシの HTTP 200 を実測 |

## 4. e2e の 1〜8 の結果

実行: `PDA_E2E=1 .venv/bin/pytest tests/e2e -x -vv`。8 件成功、151.75 秒。[e2e.txt](evidence/increment-2/e2e.txt)

| 番号 | 結果 | 証拠 |
|---|---|---|
| 1 | `COMPLETED`。判定器は judge__1〜judge__3 の 3 回。初回は break-down.fake-a と verify.test.tools、次回は summarize.fake-a。2 セルの payload の JSON 文字列を c1、c2 順に改行連結した値と、次回入力が一致 | [ワークフロー](evidence/increment-2/01-workflow.json) |
| 2 | 指定の 10 種を含む 61 件のログ。同じ trace ID、動的セルの origin_cell は judge__1 または judge__2 | [イベント](evidence/increment-2/02-events.jsonl) |
| 3 | OpenObserve の SQL 検索で同じ job ID の行を取得 | [SQL と 3 行](evidence/increment-2/03-openobserve.json) |
| 4 | invalid 出力を `FAILED_WITH_TERMINAL_ERROR/invalid_kind_or_missing_payload` として拒否。output.rejected を記録 | [ワークフロー](evidence/increment-2/04-invalid-workflow.json)、[イベント](evidence/increment-2/04-invalid-events.jsonl) |
| 5 | ワーカーを kill。応答時間切れが TIMED_OUT、再起動後の retryCount=1 が COMPLETED。2 試行の inputData は完全一致。engine.task に retry_count と responseTimeout 理由を記録 | [ワークフロー](evidence/increment-2/05-retry-workflow.json)、[イベント](evidence/increment-2/05-retry-events.jsonl) |
| 6 | タスク開始から 50.109 秒で FAILED/runtime_deadline。turn.end=cancelled。確認後に DELETE でワークフローを終了、定義を復元 | [ワークフロー](evidence/increment-2/06-deadline-workflow.json)、[時間](evidence/increment-2/06-deadline-timing.json)、[イベント](evidence/increment-2/06-deadline-events.jsonl) |
| 7 | initial_input 欠落の開始要求は HTTP 200。judge__1 に initial_input=null が渡り、ラッパーが input_schema_mismatch で終端失敗。ワークフローは FAILED、COMPLETED にならない | [HTTP 応答](evidence/increment-2/07-schema-response.json)、[ワークフロー](evidence/increment-2/07-schema-workflow.json) |
| 8 | 対象の 11 コンテナについて docker stats を保存。ネットワーク分離と UI の HTTP 応答も確認 | [stats](evidence/increment-2/08-docker-stats.txt)、[分離](evidence/increment-2/08-isolation.json) |

基本シナリオの job ID は `9cdf997a-2a70-4e04-8cd7-a26fd9504c27`。`/work` は空の名前付きボリュームなので、verify.test はテスト未検出の終了コード 5、payload.passed=false を返した。fixture はその内容で判断を変えず、指定の 3 回目で finish する。これは検証結果の受け渡しの確認であり、作業成果の品質の確認ではない。

## 5. Conductor のタスクの記録

ラッパーの期限による失敗。status と reasonForIncompletion にワーカーの返却値が保存された。

```json
{
  "referenceTaskName": "c1__1",
  "taskDefName": "implement.fake-b",
  "status": "FAILED",
  "retryCount": 0,
  "reasonForIncompletion": "runtime_deadline",
  "responseTimeoutSeconds": 60,
  "workerId": "fake-b"
}
```

ワーカー消失による応答時間切れ。Conductor が規則名と秒数を reasonForIncompletion に保存した。

```json
{
  "referenceTaskName": "c1__1",
  "taskDefName": "implement.fake-b",
  "status": "TIMED_OUT",
  "retryCount": 0,
  "reasonForIncompletion": "responseTimeout: 60 exceeded for the taskId: 54c5df1a-af57-4d6e-81b4-0f60e4596330 with Task Definition: implement.fake-b",
  "responseTimeoutSeconds": 60,
  "workerId": "fake-b"
}
```

再試行。同じ referenceTaskName に別 taskId が割り当てられ、retryCount が 1 に増えた。inputData は最初の試行と同一だった。証拠のタスク抜粋は指示された欄だけを保存している。

```json
{
  "referenceTaskName": "c1__1",
  "taskDefName": "implement.fake-b",
  "status": "COMPLETED",
  "retryCount": 1,
  "reasonForIncompletion": null,
  "responseTimeoutSeconds": 60,
  "workerId": "fake-b"
}
```

終端失敗。再試行せず、出力の拒否理由を reasonForIncompletion に保存した。

```json
{
  "referenceTaskName": "c1__1",
  "taskDefName": "implement.fake-b",
  "status": "FAILED_WITH_TERMINAL_ERROR",
  "retryCount": 0,
  "reasonForIncompletion": "invalid_kind_or_missing_payload",
  "responseTimeoutSeconds": 600,
  "workerId": "fake-b"
}
```

## 6. Codex のアダプタが権限要求を出したか

未確認。実 Codex を起動していないため、試験用エージェントの permission モードの結果からは分からない。ラッパーは権限要求を受けたときに宣言に従って応答し、Codex の job.received には INITIAL_AGENT_MODE の値を pda.agent_mode に入れる。

## 7. docker stats の結果

Docker Desktop 上で e2e 終了時に測定した。ミニ PC での実測ではない。real profile は含まない。

| サービス | メモリ使用量 | CPU |
|---|---|---|
| conductor-elasticsearch | 859.9MiB | 0.89% |
| conductor-mirror | 31.83MiB | 0.01% |
| conductor-redis | 12.53MiB | 3.88% |
| conductor-server | 836.6MiB | 14.94% |
| conductor-ui | 2.652MiB | 0.00% |
| exec-fake-a | 49.82MiB | 2.41% |
| exec-fake-b | 49.8MiB | 1.98% |
| exec-jev | 49.79MiB | 1.13% |
| exec-tools | 50.66MiB | 1.25% |
| openobserve | 413.7MiB | 0.36% |
| otel-collector | 44.76MiB | 0.10% |

元の出力は [08-docker-stats.txt](evidence/increment-2/08-docker-stats.txt)。

## 8. 指示に無かった判断と、指示どおりにできなかったこと

1. 雛形の判定器入力には cell_id がないため、judge の入力スキーマでは cell_id を任意にした。他 type は必須。イベントの cell_id には Conductor の referenceTaskName を使う。context は null を許し、処理時には空オブジェクトへ正規化する。
2. 単一 asyncio ループで停止処理と送信を両立するため、OTel SDK の Simple processor からキューへ渡し、SDK の protobuf encoder と httpx.AsyncClient で OTLP HTTP を送る。スパンはタスク単位で生成し、ログは実行中から送信する。SDK の内部 encoder を使用するため、依存の再現は uv.lock に従う。
3. Conductor への結果送信は HTTP エラー時に最大 3 回試し、通常の HTTP タイムアウトを 2 秒とした。OTLP の終了時 flush は最大 5 秒とし、送信できないときは JSON の標準出力に失敗を残す。送信先が利用不能のままの完全配送は保証しない。
4. file exporter の 100 MB 回転に加え、バックアップは 5 ファイルとした。名前付きボリュームに書く Collector は root で起動する。ログとトレースを同じファイルへ出し、証拠では対象 job のログレコードだけを抜粋した。
5. Conductor サーバは Java を直接起動し、UI は nginx だけを起動する。Java のヒープを 256〜768 MB とした。ホストの UI ポートは試験時に 15000 を使用した。
6. jev のローカルスクリプトと、その参照先 lib/jev_api.py を照合した。URL、Bearer ヘッダ、state/model/questions の本文、answers の形式は一致。キーのファイルパスはコンテナ向け指示 `/secrets/typesafe_credentials` を使用した。問いの criteria はローカルテンプレートと同じ選択肢名をキーにするオブジェクトで定義した。is_complete の 0.7 は未検証。
7. 実 ACP アダプタの npm 指定は指示どおり、Codex は版指定なし、Claude は preview のままとした。Python 依存と Docker の基底イメージは固定したが、npm の解決版は未固定・未実行。実行器の外向き通信について宛先ドメインの制限は Docker では掛けていない。
8. enforceSchema=true の定義を登録したが、Conductor は initial_input 欠落のワークフロー開始を拒否しなかった。ラッパーの入力検査が終端失敗にした。Conductor 自体による入力スキーマ強制が成立したとは報告しない。
9. 3 秒ポーリングの写しは、その間に開始・完了して実行中一覧に一度も出なかったワークフローや短い状態遷移を拾えない。今回の基本シナリオでは engine.workflow と engine.task を取得した。e2e は動的セルの記録と最終 COMPLETED イベントが揃うまで待つ。
10. 人手用の認証手順を確認する際、ホストの `codex login --help` は同梱バイナリの ENOENT で失敗した。既存のホスト CLI は変更せず、認証手順は [OpenAI 公式資料](https://learn.chatgpt.com/docs/auth) と [Claude Code 公式資料](https://code.claude.com/docs/en/authentication) を確認して記載した。
11. e2e 後は試験用の定義と fixture の上書きを復元した。検証用 Compose サービスは停止・削除し、名前付きボリュームの記録は保持した。秘密情報は Git 管理外の deploy/.env にのみ試験用認証として作成した。外部サービスへの認証は行っていない。

実装時に参照した SDK と構成の一次資料: [ACP Python SDK](https://agentclientprotocol.github.io/python-sdk/)、[Conductor v3.32.4 の Redis 設定](https://github.com/conductor-oss/conductor/blob/v3.32.4/docker/server/config/config-redis.properties)、[OpenObserve の OTLP 取り込み](https://openobserve.ai/docs/ingestion/logs/otlp/)。API と SDK の振る舞いは、上記資料に加えて固定版のインストール済みソースと実試験で確認した。

## 9. 未実施のこと

1. 個人契約 Codex と会社契約 Claude の認証、およびそれらの実行器での実タスク実行。
2. 実 jev API の呼び出し、jev-verify による問いと閾値の検証。
3. ミニ PC への配置とメモリ測定。
4. ブランチの push、main へのマージ。
