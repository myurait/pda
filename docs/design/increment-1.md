# 最初の増分の設計

- 更新: 2026-09-22 JST
- 種別: 設計。`basic-design-proposal.md` の 10.1 で決まった範囲を、動かせる形まで具体化する。
- 物差し: `docs/requirements.md`（commit `a92a4ab`）。
- 範囲: 個人契約の Codex、会社契約の Claude、jev、決定論的な検証ツールの 4 実行器。すべてミニ PC 上。移行とペルソナ選定は含めない。
- 一次資料で確かめていない事項は「未確認」と書く。

## 1. 構成

ミニ PC 上に docker compose で次を立てる。実行器のコンテナは compose の内部ネットワークだけに置き、ホストへポートを公開するのは Conductor の API と UI、ログストアの UI に限る。実行器同士がホストのポートを取り合う事態はこれで避ける。

| 役割 | コンテナ | 実体 |
|---|---|---|
| コア | conductor-server | Conductor OSS のサーバ |
| コアの保存先 | conductor-redis、conductor-elasticsearch | 同梱の構成どおり。Elasticsearch のヒープは 512 MB〜1 GB |
| コアの画面 | conductor-ui | 同梱の UI |
| ログの受け口 | otel-collector | OpenTelemetry Collector。受けたものを OpenObserve と JSON Lines のファイルの両方へ出す |
| ログストア | openobserve | 単一バイナリ。ログとトレースを OTLP で受け、SQL で検索できる画面を持つ |
| 実行器 | exec-codex-personal | Codex の ACP アダプタとラッパー。個人契約の認証情報をマウント |
| 実行器 | exec-claude-company | Claude Code の ACP アダプタとラッパー。会社契約の認証情報をマウント |
| 実行器 | exec-jev | jev の HTTP API を呼ぶラッパー。TypeSafe の API キーをマウント |
| 実行器 | exec-tools | スクリプト実行ホスト。テスト、リンタなどの検証ツールとラッパー |
| 写し | conductor-mirror | Conductor の実行記録を読んで、エンジン側の状態変化を event stream へ写す小さなプロセス |

ラッパーと写しは Python で書く。理由は 3 つ。Conductor の Python SDK にワーカーの定義、ドメイン付きのポーリング、タスク定義の登録と入出力スキーマの指定が揃っていること。ACP の Python SDK（PyPI の `agent-client-protocol`）がクライアント側の標準入出力接続を提供すること。jev のスクリプトが Python であること。TypeScript でも同じ構成が組めるが、増分 1 では言語を 1 つに揃える。

## 2. ログストアの選定

候補 4 つを、OTLP でログとトレースの両方を受けるか、常駐の重さ、検索の手段、ライセンスで比べた。

| 候補 | ログとトレース | 常駐の構成 | 検索 | ライセンス |
|---|---|---|---|---|
| OpenObserve | 両方。HTTP と gRPC | 単一バイナリ。メタデータは SQLite、データはローカルディスク | SQL と画面 | AGPL-3.0 |
| SigNoz | 両方 | ClickHouse、ClickHouse Keeper、Postgres、Collector、本体。メモリ 4 GB 以上 | 画面のクエリビルダーと ClickHouse SQL | MIT（一部別ライセンス） |
| Langfuse | トレースのみ。ログの受け口は無し | Postgres、ClickHouse、Redis、オブジェクトストレージ。推奨メモリ 8 GB | 生成 AI 向けの画面 | MIT（一部別ライセンス） |
| Jaeger v2 | トレースのみ | 単一バイナリ。Badger で永続化 | トレース検索の画面 | Apache-2.0 |

OpenObserve を選ぶ。ログとトレースを両方受け、単一バイナリでミニ PC に収まり、SQL で監査の問いを書ける。AGPL-3.0 は個人利用では制約にならない。Langfuse は生成 AI のトレースの見え方が良いが、ログを受けず構成が重い。後で載せ替える場合も、Collector を挟んであるので受け口の設定だけで済む。

Collector にはファイル出力も並べる。OTLP の JSON Lines を日付で回転させて保存し、これを event stream の正本にする。OpenObserve は検索と画面のための複製とし、監査の実行器はどちらを読んでもよいが、食い違いがあればファイルを正とする。

## 3. メッセージの形

Conductor のタスクの入力と出力を、要件のプロトコルのメッセージとして使う。

### 3.1 セルへの入力

```json
{
  "job_id": "…",
  "cell_id": "…",
  "type": "implement",
  "prompt_ref": {"id": "implement", "version": 3},
  "input": "前のセルの出力の payload、または初期入力",
  "context": {"files": ["…"], "notes": "…"}
}
```

`prompt_ref` は識別子だけで、プロンプトの文は含めない。ラッパーが正本から引く。`input` と `context` はワークフロー定義の参照（前のタスクの出力、ワークフローの初期入力）から Conductor が組み立てる。定義にはこの 5 つの欄以外を書かない。これで A16 は定義を読めば確かめられる。

### 3.2 セルの出力

```json
{
  "kind": "flow | input | result",
  "payload": {},
  "meta": {
    "executor_id": "codex-personal",
    "declaration_version": 2,
    "trace_id": "…",
    "stop_reason": "end_turn"
  }
}
```

`kind` は要件の 3 種別に対応する。`flow` はフローへの指示、`input` は次のセルへの入力、`result` は仕事全体の成果。ラッパーはランタイムの出力を次の順で分類する。出力が `flow` の形（3.3）に合えば `flow`。次に走るセルが定義上あり、出力がそのセルの入力スキーマに合えば `input`。どちらにも合わなければ `result`。分類は形の照合だけで、中身の意味は見ない。

### 3.3 フローへの指示

判定器のセルだけが出す。

```json
{
  "kind": "flow",
  "payload": {
    "then": "continue | finish",
    "cells": [
      {"type": "break-down", "executor": "claude-company", "input_from": "previous"}
    ],
    "dynamicTasks": [ {"name": "break-down.claude-company", "taskReferenceName": "c1", "type": "SIMPLE"} ],
    "dynamicTasksInput": { "c1": {"type": "break-down", "prompt_ref": {"id": "break-down", "version": 1}, "input": "…", "context": {}} }
  }
}
```

`cells` が人向けの表現、`dynamicTasks` と `dynamicTasksInput` が Conductor の動的フォークに渡す形で、後者は前者から機械的に生成する。生成はラッパーの中の決定論的な変換で、判定器（jev）は `cells` の中身を選択肢から選ぶだけである。

## 4. 実行器の指定

判定器が選んだ実行器へタスクを届ける方法は 2 つある。Conductor の task domain（ワークフロー開始時に、タスクの種類ごとにどのドメインのワーカーへ向けるかを指定する）と、タスク定義の名前に実行器を含める方法である。増分 1 では後者を取り、タスク定義の名前を `{type}.{executor_id}` とする。判定器がフローの途中で実行器を選ぶため、開始時に固定する domain の形と合わないからである。タスク定義は type と実行器の組み合わせの数だけ生成するが、正本から自動生成するので手で書く量は増えない。各ラッパーは、自分の実行器 ID と宣言した type の組み合わせ分だけをポーリングする。

## 5. 雛形ワークフロー

```json
{
  "name": "pda_job",
  "version": 1,
  "inputParameters": ["initial_input", "context"],
  "tasks": [
    {
      "name": "pda_loop",
      "taskReferenceName": "loop",
      "type": "DO_WHILE",
      "loopCondition": "$.judge['output']['payload']['then'] == 'continue'",
      "loopOver": [
        {
          "name": "judge.jev",
          "taskReferenceName": "judge",
          "type": "SIMPLE",
          "inputParameters": {
            "type": "judge",
            "prompt_ref": {"id": "judge", "version": 1},
            "input": "${join.output}",
            "context": "${workflow.input.context}",
            "initial_input": "${workflow.input.initial_input}"
          }
        },
        {
          "name": "branch",
          "taskReferenceName": "branch",
          "type": "SWITCH",
          "evaluatorType": "value-param",
          "expression": "then",
          "inputParameters": {"then": "${judge.output.payload.then}"},
          "decisionCases": {
            "continue": [
              {
                "name": "fork",
                "taskReferenceName": "fork",
                "type": "FORK_JOIN_DYNAMIC",
                "dynamicForkTasksParam": "dynamicTasks",
                "dynamicForkTasksInputParamName": "dynamicTasksInput",
                "inputParameters": {
                  "dynamicTasks": "${judge.output.payload.dynamicTasks}",
                  "dynamicTasksInput": "${judge.output.payload.dynamicTasksInput}"
                }
              },
              {"name": "join", "taskReferenceName": "join", "type": "JOIN"}
            ]
          },
          "defaultCase": []
        }
      ]
    }
  ]
}
```

読み方。判定器のセルが先頭にあり、その出力の `then` で分岐する。続けるなら動的フォークが判定器の出したセル一覧を展開し、合流の出力が次の判定器の入力になる。終えるなら何もせず、繰り返し条件が偽になって終わる。最初の回は合流の出力が無いので、判定器は `initial_input` を使う。入れ子が要る type（大きなタスク分解の下位）は、セルとして `pda_job` 自身を SUB_WORKFLOW で呼ぶ。

未確認: DO_WHILE の中でのタスク参照の書き方（繰り返しごとの接尾辞の扱い）、最初の回に `join.output` が未定義でも判定器のタスクが起動するか、SWITCH の評価方式と式の書き方。いずれも動かして確かめ、必要なら判定器を繰り返しの外に 1 つ置く形へ変える。

## 6. ラッパー

1 つの Python パッケージで、実行器の種類ごとに「操作役」だけを差し替える。

```
wrapper/
  worker.py        Conductor のワーカー。ポーリング、入力の組み立て、出力の分類と検査、タスクの完了
  prompts.py       prompt_ref から正本のプロンプトを引く
  classify.py      出力を flow / input / result に分類し、スキーマで検査する
  events.py        出来事を閉じた種別に写し、OpenTelemetry で送る
  drivers/
    acp.py         ACP クライアント。標準入出力でアダプタを起動し、session/new → session/prompt → 通知の受信 → 完了
    jev.py         jev の HTTP API。問いの集合と state を送り、答えをセル一覧へ写す
    tools.py       スクリプト実行。コマンドを走らせ、終了コードと出力を成果にする
```

### 6.1 1 タスクの処理

1. Conductor からタスクを取る。`job.received` を記録する。
2. `prompt_ref` から事前プロンプトを引き、`input` と `context` と合わせてランタイムへの入力を作る。`input.assembled` として、プロンプトの識別子と版、入力のハッシュを記録する。文そのものは記録しない。
3. 操作役でランタイムを動かす。実行中の通知を出来事に写して送る（7 節）。
4. 出力を分類し、種別に応じたスキーマで検査する。`output.classified` を記録する。検査に落ちたら `output.rejected` を記録し、Conductor には終端失敗（再試行しない失敗）で返す。
5. Conductor にタスクの完了を返す。出力の要約 1 行をタスクログに追記する。
6. 応答時間切れ（心拍）は Conductor 側の設定に任せる。長いタスクでは Python SDK のリース延長を有効にする。

### 6.2 ACP の操作役

Claude Code と Codex はどちらも npm で配布される ACP アダプタで包む。Claude Code のアダプタは、作業ディレクトリと設定ディレクトリの `settings.json` を読み、権限モードも CLI と同じ規則で扱う。Codex のアダプタは環境変数で Codex の設定と権限モードを受ける。Gemini CLI は `--acp` で同じ規約を話すが、増分 1 の範囲外。

操作役は次をする。アダプタを子プロセスとして起動し、`session/new` でセッションを作り、`session/prompt` で入力を渡す。返ってくる通知（`sessionUpdate`）を受けるたびに出来事に写す。権限要求（`session/request_permission`）には、宣言ファイルに書いた方針（常に許可、常に拒否、種類ごと）で機械的に答え、その事実を記録する。未確認: Codex のアダプタは起動時の環境変数で権限モードを固定する作りで、権限要求を都度出すかどうかを確かめていない。都度出さないなら Codex では `permission.request` と `permission.response` の出来事は現れず、起動時のモードを `job.received` の属性に残す。応答の `stopReason` を `meta.stop_reason` に入れる。Conductor 側から中断が来たら `session/cancel` を送る。

認証はコンテナにマウントした設定ディレクトリに置く。Claude Code は `CLAUDE_CONFIG_DIR`、Codex は Codex の設定ディレクトリ。初回のログインはコンテナの外で済ませてからマウントする。未確認: Codex の個人契約のログイン情報がコンテナ内のアダプタからそのまま使えるか。

### 6.3 jev の操作役

判定器の問いは英語で書き、state は日本語のままでよい。判定は選択肢から選ぶ形（Choice）と真偽（Noul）で組む。

| 問い | 型 | 選択肢の出所 |
|---|---|---|
| この仕事は完了しているか | Noul | しきい値は検証で決める |
| 次に必要な type は何か | Choice | type の正本の一覧 |
| その type をどの実行器で走らせるか | Choice | 宣言ファイルの一覧（費用と到達資源を criteria に書く） |
| いくつのセルに分けるか | Choice | 1、2、3 以上 |

答えから `cells` を組み、`dynamicTasks` と `dynamicTasksInput` を生成する。問いの集合は正本に置き、閾値は `jev-verify` で実データを流して決める。jev の API へは `api.typesafe.ai` に出る必要があるので、exec-jev だけは外向きの通信を許す。

### 6.4 スクリプト実行ホスト

`tools` の操作役は、type ごとに正本に書いたコマンド（例: `verify.test` は `pytest`、`verify.lint` は `ruff`）を、`input` に含まれる作業ディレクトリで走らせる。終了コードと標準出力を `result` の成果にし、終了コードが 0 かどうかを `payload.passed` に入れる。これは種別の分類ではなく成果の中身なので、次の判定器が読む。

## 7. event stream

### 7.1 出来事の種別

閉じた一覧。増分 1 ではこれ以外を作らない。写せないものは `unknown` に入れ、元の通知をそのまま添える。

| 種別 | 出所 | 主な属性 |
|---|---|---|
| job.received | ラッパー | job_id、cell_id、type、executor_id |
| input.assembled | ラッパー | prompt_ref、input_hash、context_keys |
| message.output | ACP の agent_message_chunk | 文字数（本文は別属性で任意） |
| reasoning | ACP の agent_thought_chunk | 文字数 |
| tool.call | ACP の tool_call | tool_call_id、kind、title、raw_input |
| tool.result | ACP の tool_call_update | tool_call_id、status、raw_output |
| plan | ACP の plan | 項目数 |
| permission.request | ACP の session/request_permission | tool_call_id、選択肢 |
| permission.response | ラッパー | 選んだ選択肢、根拠にした宣言の欄 |
| usage | ACP の usage_update | トークン数 |
| turn.end | ACP の stopReason | stop_reason |
| output.classified | ラッパー | kind、schema_id |
| output.rejected | ラッパー | 理由 |
| command.run | tools の操作役 | コマンド、終了コード |
| judge.answer | jev の操作役 | 問いの識別子、選んだ選択肢、確度 |
| engine.workflow | 写し | 状態遷移、理由 |
| engine.task | 写し | 状態遷移、再試行回数、時間切れの種類、規則 |
| unknown | ラッパー | 元の通知 |

### 7.2 OpenTelemetry への写し

仕事 1 つをトレース 1 つ、セル 1 つをスパン 1 つにする。トレース ID は Conductor のワークフロー ID から決定論的に作り、スパンの親子はフローの親子に合わせる。出来事はログレコードとして送り、属性に `pda.event.kind`、`pda.job_id`、`pda.cell_id`、`pda.executor_id`、`pda.type` を必ず付ける。モデル名やトークン数は、生成 AI の意味規約の属性名（`gen_ai.*`）に合わせて入れる。

### 7.3 エンジン側の写し

Conductor のワークフローとタスクの状態遷移は、本来はサーバ内のリスナー（Java）で拾うのが正しい。増分 1 では Java を書かず、Conductor の REST API で実行記録を定期的に読み、前回との差分を `engine.workflow` と `engine.task` の出来事として送る小さな Python プロセスで代える。再試行回数はタスクの記録に欄がある。時間切れの種類と終端失敗の理由がタスクの記録のどの欄にどう入るかは未確認で、作る順序の 1 で確かめる。A18（どの規則に該当したか）は、その欄とタスク定義の規則を対応づけて出す。遅延は数秒で、可視化には足りる。監査の厳密さが要る段階で Java のリスナーに置き換える。

## 8. 宣言ファイル

実行器ごとに 1 ファイル。A2A の AgentCard の欄を土台に、要件の能力の宣言を足す。

```yaml
executor_id: codex-personal
name: Codex (個人契約)
version: 2
agent: codex
runtime: acp
account: personal
environment: minipc
types: [break-down, implement, review]
capabilities:
  streaming: true
  cancel: true
cost:
  currency: JPY
  per_run_estimate: 50
  per_run_seconds_estimate: 300
  rate_limit: {requests: 50, per: hour}
resources:
  filesystem: [/work]
  network: [api.openai.com]
  connectors: []
state:
  interruptible: true
  resume: reinject
permissions:
  default: allow_once
  deny_kinds: [delete]
```

`resources` はコンテナの設定と同じ内容にし、生成元を一つにする。`state.resume` は `resume`（中断位置から再開）か `reinject`（再投入）で、増分 1 の 4 実行器はすべて `reinject`。判定器はこのファイルの一覧を state として受け取り、実行器の選択肢とする。

## 9. type の初期一覧

| type | 目的 | 想定する実行器 | 出力の種別 |
|---|---|---|---|
| judge | 完了判定、次の type と実行器の選択 | jev | flow |
| break-down | 仕事を下位の仕事に分ける | Claude、Codex | input |
| implement | コードを書く、直す | Codex、Claude | input |
| review | 変更を読んで指摘する | Claude、Codex | input |
| verify.test | テストを走らせる | tools | result |
| verify.lint | リンタを走らせる | tools | result |
| summarize | 複数の出力を一つにまとめる | Claude、Codex | result |

type ごとに事前プロンプト（`prompts/{type}.md`）、入力スキーマ、出力スキーマを正本に置く。タスク定義（再試行 3 回、応答時間切れ 600 秒、入力スキーマの強制あり）は正本から生成して Conductor に登録する。

## 10. 正本の置き場所

このリポジトリに次を置き、変更は git の履歴で追う。

```
registry/
  types/{type}.yaml          入力スキーマ、出力スキーマ、再試行と時間切れ
  prompts/{type}.md          事前プロンプト
  executors/{executor}.yaml  宣言ファイル
  judge/questions.json       判定器の問いの集合と閾値
  workflows/pda_job.json     雛形
tools/
  generate_defs.py           正本からタスク定義とワークフロー定義を生成し、Conductor に登録する
```

## 11. 作る順序

1. compose で Conductor、UI、Collector、OpenObserve を立て、雛形を登録して、ダミーのワーカーで 1 周回す。DO_WHILE と動的フォークの参照の書き方をここで確かめる。
2. ラッパーの骨格と `tools` の操作役。`verify.test` を 1 つ動かし、出来事が OpenObserve とファイルに届くことを見る。
3. jev の操作役。問いの集合を `jev-decompose` と `jev-verify` で作り、判定器のセルがフローへの指示を出すところまで。
4. Codex の操作役。個人契約の認証をコンテナへ持ち込み、`implement` を 1 つ通す。
5. Claude Code の操作役。会社契約で `review` を 1 つ通す。
6. 写し。エンジン側の状態遷移が event stream に出ることを見る。
7. 受け入れ条件の確認（12 節）。

## 12. 受け入れ条件の確かめ方

| 条件 | 確かめ方 |
|---|---|
| A1 | 同じ `implement` を Codex と Claude で走らせ、Conductor の記録と event stream の形が同じであることを比べる |
| A2 | 宣言ファイルを 1 つ足して定義を生成し直すだけで、既存のコンテナと定義を変えずに新しい実行器がセルに現れる |
| A3 | 増分 1 では対象外。同一ベンダーの会社契約と個人契約の組が範囲に無い |
| A4 | jev を止めて、別の判定器（例: 固定の規則を返すダミー）に差し替えても Conductor と他の実行器が動く |
| A5 | 4 実行器の出来事が同じ属性の組で OpenObserve に並ぶ |
| A12 | 出力の `kind` が 3 つのどれかで、`input` が次のセルにそのまま渡る |
| A13 | スキーマに合わない出力を返すダミーで、終端失敗と `output.rejected` が残る |
| A14 | Conductor の API だけで、仕事の現在のセルと状態が答えられる |
| A15 | 時間切れで再試行が起き、2 回目の入力が 1 回目と同じ形で、`engine.task` に規則が残る |
| A16 | 雛形の定義に文が無いこと、`input.assembled` の prompt_ref とハッシュが記録されること |
| A17 | 動的フォークで生まれたセルが、直前の判定器の出力と Conductor の記録で結び付く |
| A18 | 終端失敗、時間切れ、再試行のそれぞれで、`engine.task` の理由がタスク定義のどの規則かを示す |

## 13. 未確認とリスク

- DO_WHILE の中の参照の書き方、最初の回の未定義参照の扱い、SWITCH の書き方（5 節）。
- Codex のアダプタが権限要求を都度出すか（6.2 節）。
- タスクの記録に時間切れの種類と終端失敗の理由がどう入るか（7.3 節）。
- 動的フォークに空の一覧を渡したときの挙動。雛形では分岐で避けている。
- Conductor がワーカータスクの出力スキーマを検査するか。増分 1 ではラッパーが検査するので、どちらでも動く。
- Codex の個人契約の認証情報をコンテナ内のアダプタから使えるか。
- ACP のアダプタが知らない通知を無視する点。ラッパーの `unknown` で拾えるのは、アダプタが通知として出したものだけ。
- ミニ PC のメモリ。Conductor 一式（Java、Redis、Elasticsearch 1 GB）に OpenObserve と 4 コンテナが乗る。1 で計測してから 2 に進む。
- 写しの遅延と、Conductor の記録を二か所（Conductor と event stream）に持つこと。食い違いは event stream を正とし、Conductor はエンジンの状態として扱う。
