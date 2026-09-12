# 送信直前の報告編集（opt-in / 本番未反映）

技術報告・判断依頼の最終原稿を、一回だけ tools 無し編集器へ渡します。
採用稿は主モデルへ戻して再編集せず、API / Open WebUI と利用者履歴へ同じ本文を送ります。
未設定・無効・対象外・編集失敗は既存の原稿へ戻します。新しい Gemini 接続や課金設定は含みません。

## 構成と責任

- `__init__.py`: Hermes plugin。信頼済み run context と主モデルの明示 prepare を合わせて対象判定。
- `report_editor/contracts.py`: 公開用の構造化入力、保護文・数字・文の出現回数を検査。独立した意味理解の保証ではありません。
- `report_editor/pipeline.py`: 一回性、総15秒（設定上限）、cancel、process group の終了、fail-open の原稿復帰、内容を含めない数値 metrics。
- `report_editor/worker.py`: 一回の adapter 実行。共通処理には provider/vendor/model 分岐なし。
- `report_editor/adapters/claude_cli.py`: 認証参照、モデル名、CLI 通信、SDK 出力形式をここだけに隔離。
- `integrations/openwebui-hermes-progress/functions/hermes_progress_pipe.py`: `ENABLE_REPORT_EDITOR` valve で opt-in。

Hermes の汎用変更も必要です: `agent/output_delivery.py`, `agent/conversation_loop.py`,
`agent/turn_finalizer.py`, `gateway/platforms/api_server.py`, `hermes_cli/plugins.py`。
既存の最終 hook だけでは、先行 stream と既に保存した履歴を同時に止められません。
本パッチは valid prepare が成功した後だけリクエスト単位で本文を buffer し、最終 hook を永続化前に通します。
有効化だけでは通常会話の逐次表示を止めません。正当な途中経過はmessage境界で閉じ、技術toolを
経た最終報告をターン全体のvisibleフラグで除外しません。送信済み本文の内容は保持せずhashで照合し、
最終原稿そのものをすでに送った場合は編集稿へ差し替えて「原稿先出し無し」と装いません。
途中経過がある場合、最終run eventの汎用replace指定をOpen WebUIのResponses state eventへ変換し、
DOMだけでなく保存用accumulatorも最終本文へ揃えます。この経路の実証対象はOpen WebUI 0.11.1です。
通常の provider replay 用原稿は既存 `api_content` に残し、ユーザー履歴は `content` の採用稿です。
UI から再送された過去の表示稿は所有 session の保存済み履歴に一致する場合だけ元の provider 原稿へ戻します。
過去の利用者履歴を書き換えたり、主モデルへ編集済み過去文を再注入したりしません。

## 対象と除外

対象は完了・未完了・障害の技術報告、判断・承認依頼です。主モデルが
技術作業と必要な途中経過の後、最終報告本文を送る前に `report_editor_prepare` を一回呼び、同じ原稿を最終回答として返します。
全会話、内部推論、秘密、不要ログを渡さず、資料内命令は編集器の操作指示にしません。
`export_class=public` は主モデルの申告です。完全な秘密検知器ではないため非公開データへの導入は別判断です。

短い通常会話、JSON/code/raw成果物、title/tag/follow-up、internal/subagent/editor context、
urgent stop/status は除外します。API 呼出しは既存認証が必要で、frontend-only の由来保証は主張しません。
信頼された API entrypoint が作る context と prepare の両方が必要です。

## 編集設定だけで交換

次は導入例です。今回この設定を本番へ書いてはいません。
主モデル、汎用 delegation は変更しません。

```yaml
plugins:
  enabled: [pda-report-editor]  # 既存リストに統合し、置換しない
  entries:
    pda-report-editor:
      settings:
        enabled: false       # 導入は無効のまま。反映許可後のみ true
        timeout_seconds: 15 # 15を超える値も15へ制限
        metrics_path: /ABSOLUTE/PRIVATE/CONTENT-FREE-METRICS.jsonl
        adapter:
          factory: report_editor.adapters.claude_cli:ClaudeCliAdapter
          model: sonnet
          auth_env: CLAUDE_CODE_OAUTH_TOKEN  # 既存の認可済み参照名のみ
```

adapter は `Adapter(config).edit(request, monotonic_deadline)` を実装し、
`{text, finish_reason, calls?, usage?}` を返します。factory と adapter 内の設定だけで交換します。
共通 pipeline、主モデル、本体 vendor 分岐の変更は不要です。factory は運用者が選ぶ信頼済みコードであり sandbox ではありません。
worker の request/config envelope は4 MiB上限です。公開入力スキーマの最大UTF-8要求を収め、超過する設定/envelopeは実行せず原稿へ戻します。
子プロセスへの入出力はPOSIXの非ブロッキングpipe/selectorで処理し、部分書込み・遅い起動でもcancelと総期限を監視します。検証環境はLinux/CPython 3.11です。
CLI adapter は一時 HOME/CWD、空 tools・MCP、hook/plugin/context 読込無効、session persistence 無効、max-turns=1 で実行します。
未知の finish reason、非0終了、API error、空の実モデル利用、retry/tool 出現は不採用です。
モデル別の品質・速度はこの試験に限る結果で、Gemini の実証ではありません。

## 失敗時・計測・限界

認証不足、起動失敗、timeout、空文、途中切れ、形式違反、必須情報の欠落・変更、
追加文、原稿にない文の重複、cleanup 失敗は原稿復帰します。cancel は返信せず遅延稿も追加送信しません。
締切は SDK 内 retry/queue、worker、cleanup を含む総経過時間から判定します。既定15秒は仮値です。
OS全体の停止やスケジューラの遅延に対する hard real-time の保証ではありません。

metrics は reason、invocation id、一回性、経過秒、数値の usage/cost/retry の allowlist のみです。
取得不能な token・費用は unknown/null で、0 と捏造しません。CLI の `total_cost_usd` は provider 報告値で、請求確定額ではありません。
棄却稿でも取得済みの数値 usage は残します。本文、秘密、モデルが返した任意のキー/文字列は記録しません。

文の抽出・順序変更を基本に、許可見出しと段落分けだけを追加します。
検査は保護値・数字・原文の文・その出現回数の不変条件です。
主モデルの事実整理漏れ、重要な非保護文の削除、順序による含意、読みやすさの好みまで自動証明しません。
Open WebUI の既存「完了」status は応答処理の終了で、案件の達成認定ではありません。本文の未完了・判断待ちを保持します。

## 再現・回帰（本番を使わない）

```sh
python integrations/hermes-report-editor/run_tests.py \
  --hermes-source /ABSOLUTE/TASK/HERMES-WORKTREE -- tests -q
```

全47件には実 API/AIAgent/SQLite を通す成功・無効・未設定・対象外・fallback・timeout・cancel・
再入/二重表示・セッション混線・過去 replay/cache・tool/log/input canary・process cleanup・大きい有効UTF-8入力・通常会話のstream保持・送信済み原稿の拒否・実技術tool/途中経過後の編集・Pipeの最終本文置換を含みます。
fake adapter は境界の再現用です。実編集器/実UI/実主モデルの実証は別 evidence に保存します。

`tests/live_runtime.py` は明示 opt-in の隔離 HTTP fixture です。主 transport は scripted と明記し、
実 Hermes API と実 Claude editor と実 Open WebUI の区別を保ちます。
`--public-capture` は `public_examples.json` と完全一致する公開例だけの診断用で、通常導入には使いません。
`tests/real_primary_probe.py` は実設定の主モデルを変更せず五つの有限リクエストで、実技術tool/進捗後の対象判定と有効/無効の通常会話を調べます。
pytest はこの live probe を自動実行しません。既存認証を読むだけで更新・コピー・ログインしません。
小さい入力で reasoning=max を使うと既定の Codex idle 12秒が短すぎる場合があります。
試験プロセスだけ `HERMES_CODEX_EVENT_STALE_TIMEOUT_SECONDS=60` とし、各要求145秒・全試験570秒の上限を残します。
これは主モデル通信の試験設定で、編集の15秒制限を変えません。

## 導入手順（後続の明示反映許可が必要）

1. 現行リポジトリの HEAD/dirty state、Hermes 起動元、plugin path、設定、実 Pipe source/valves を保存する。
   今回の task commits を現在の変更と照合する。他スレッドの main / 未commit を reset・stash・上書きしない。
2. レビュー済み Hermes の汎用差分、PDA plugin、Pipe の三者を同じ検証済み組合せとして隔離環境へ配置する。
   plugin root を対象環境の `plugins/pda-report-editor` とし、`enabled: false` と Pipe valve false で起動確認する。
3. 認証参照とモデルは既存の認可済みものだけを指定。新 provider 接続・契約・課金・秘密設定は別途承認。
4. 隔離環境で無効時の外注0、通常chat、3例×両mode、両履歴一致、cancel/timeout、停止後quietを再確認する。
5. 本番反映・対象サービスの再起動・有効化は明示許可された時だけ行い、変更対象と正常復元点を限定する。
   今回の成果は local task-branch commit までで、main merge / push / 本番配置 / restart はしていない。

## 切戻し手順

- まず当該 plugin の settings.enabled と Pipe の ENABLE_REPORT_EDITOR を false にし、新規の編集を止める。
- 対象の編集中 run があれば、その run id だけを既存 stop API で停止する。全 run 一括停止はしない。
- 通常会話が返り、editor metrics の増分が0で、既存履歴の本文が変わらないことを実測する。
- コードを戻す場合は許可済みの正常組合せと起動元へ戻す。現在の設定/metadata が自分の反映値と一致しない場合は
  他者の変更を上書きせず conflict として停止する。DBやユーザー履歴を古い backup で丸ごと上書きしない。
- この機能は DB migration を追加しない。過去に採用した利用者本文はそのまま保存する。
- 切戻し後の health と通常chat、外注0、履歴不変を確認してから切戻し完了とする。

試験証拠索引・前後比較・残存リスク・各 local commit は今回の実装 report/evidence index を参照してください。
