# 増分 4 実装報告

実施日: 2026-09-23。作業場所: `/home/user/pda`。ブランチ: `increment-4`（main から分岐）。

## 1. 変えたもの

- 2.1: ACP の `available_commands_update` と `session_info_update` を無視し、他の未知の通知は `unknown` のままにした。
- 2.2: judge 以外の事前プロンプト 6 ファイルに JSON だけを返す指示を追記した。分類規則は変更していない。
- 2.3: compose のプロジェクト名を `pda`、自作イメージのタグを `local` に変更し、旧プロジェクトのコンテナとボリュームを削除した。
- 2.4: 可用性、実行器の置き換え、`PDA_MAX_ROUNDS`、共通 state 組み立て関数、`tools/judge_probe.py` を追加した。
- 2.5: 読み取り専用の `pda_view`、3 つの API、日本語の画面、compose の `pda-view` を追加した。
- 2.6: 単体試験と e2e 13・14、名指しした実行器のポーリング待機を追加した。手順書を `docs/runbook/increment-4.md` に置き換えた。

## 2. 使ったイメージと版、依存パッケージと版

自作イメージを `pda-executor:increment-3` → `pda-executor:local`、`pda-executor-real:increment-3` → `pda-executor-real:local` に変更し、今回のコードで再ビルドした。`pda-view` は前者を使い UID 1000 で動く。

基底イメージと既存サービスの版は変更していない。アプリケーションの依存追加・版変更はなく、`uv.lock` は変更していない。`pyproject.toml` の wheel 対象に `src/pda_view` を追加し、`uv sync --frozen` で同期した。

画面の検証だけに `uv run --no-project --with playwright` の一時環境と Chromium 153.0.8010.12 を使用した。アプリケーション、イメージ、プロジェクトの依存には追加していない。画面にフレームワーク、npm、ビルド工程、CDN、外部フォントはない。

## 3. 部品ごとの受け入れ条件の合否と確かめ方

`ruff check` は合格、`pytest tests/unit` は **93 passed**。証拠は [quality.txt](evidence/increment-4/quality.txt)。

| 条件 | 合否 | 確かめ方 |
|---|---|---|
| ACP の通知の整理 | 合格 | 単体試験で 2 通知が無出力、別の通知が `unknown` になることを確認した。 |
| 事前プロンプト | 合格 | 単体試験で 6 ファイルの追記を確認した。実 jev の仕事で Claude の成果は JSON として読めた（5 節）。 |
| compose | 合格 | 正本を単体試験で確認した。旧プロジェクトのコンテナ・ボリュームはどちらも 0。[environment-checks.json](evidence/increment-4/environment-checks.json)。 |
| 可用性 | 合格 | モックで 60 秒ちょうど、60 秒超、未来の時刻、宣言順、API 代替経路を検証した。最終 fixture e2e の state は `fake-a, fake-b, jev, tools` の 4 実行器。[02-events.jsonl](evidence/increment-4/02-events.jsonl) の `input.assembled`。 |
| 置き換え | 合格 | 単体試験で不在・type 非対応・候補なしを確認した。実 jev でも `substituted:tools->claude-personal` が記録された。 |
| 上限の上書き | 合格 | `PDA_MAX_ROUNDS=1` の単体試験で、1 回のセル実行履歴に対して `finish:round_limit` を確認した。 |
| 判定器の道具 | 合格 | 両入力経路は httpx モックによる単体試験で実 API と同じ送信先・本文への送信と JSON 出力を確認した。実 API は費用枠に従い `--job-id` だけ 1 回実行。[13-probe.json](evidence/increment-4/13-probe.json)。 |
| 可視化の API | 合格 | httpx モックと HTTP サーバの試験で 3 API の欄、障害時の 502 と理由の JSON、復旧後の応答を確認した。e2e 14 で実機のセルと出来事を照合した。 |
| 可視化の画面 | 合格 | HTML・JS・CSS は HTTP 200。HTML の一覧・詳細・時間軸を単体試験で確認した。Chromium の幅 375px で scrollWidth=375、最小文字サイズ 14px、絞り込みと解除、JavaScript エラー 0 を確認した。[14-browser.json](evidence/increment-4/14-browser.json)。 |
| 増分 3 の全部品 | 合格 | 今回指定された e2e 1〜9 が通過した。10〜12 は実行していない。 |
| 手順書 | 合格 | 配置、旧プロジェクト削除、定義登録、個人認証、実 jev と fixture の切り替え、道具、5081、Tailscale Serve、会社契約の範囲外を記載した。実機の Serve の help で構文を確認し、設定コマンドは実行していない。 |

## 4. e2e 1〜14 の結果

| 番号 | 結果 | 確認内容・証拠 |
|---|---|---|
| 1 | 合格 | fixture の 2 回のセル実行、3 回の判定、前段入力、仕事別ディレクトリ。`01-workflow.json`、`01-workdir.json`。 |
| 2 | 合格 | 出来事の種別、同一 trace、動的セルの出所、終了時フラッシュ、ログとトレースの分離。`02-events.jsonl`、`02-traces.jsonl`。 |
| 3 | 合格 | OpenObserve の SQL 検索。`03-openobserve.json`。 |
| 4 | 合格 | 不正出力の終端失敗と `output.rejected`。`04-invalid-*`。 |
| 5 | 合格 | ワーカー消失後の応答時間切れと同一入力での再試行。`05-retry-*`。 |
| 6 | 合格 | ランタイムを期限前に中断して失敗を返した。`06-deadline-*`。 |
| 7 | 合格 | 初期入力なしの仕事がラッパーのスキーマ検査で失敗した。`07-schema-*`。 |
| 8 | 合格 | UID 1000、ネットワーク分離、Conductor UI、コンテナ使用量。`08-*`。 |
| 9 | 合格 | fake-c の宣言追加だけで定義を追加し実行、後で削除・復元した。`09-*`。 |
| 10 | 未実施 | 指示に従い、実 Codex を名指しする有料試験は実行していない。 |
| 11 | 未実施 | 指示に従い、実 Claude を名指しする有料試験は実行していない。 |
| 12 | 未実施 | 指示に従い、10・11 の比較は実行していない。 |
| 13 | 合格 | 実 jev 2 回、道具 1 回、実行器セル 1 個、再試行 0。flow のスキーマ、4 問、置き換え、仕事の完了を確認した。`13-*`。 |
| 14 | 合格 | e2e 1 の仕事が一覧に存在。セルの参照名順・状態が一致。出来事 64 件は e2e 2 の 64 件以上。judge__1 に絞ると 9 件すべて同セル。ホスト 5081 と静的ファイルの応答を確認した。`14-*`。 |

最初の一括実行は 10 合格・14 のみ失敗。OpenObserve の時刻条件修正と pda-view の再作成後に 14 単独が合格した。最終イメージで 1・2・14 を再実行して 3 合格。1・2・14 の証拠は最終実行、3〜9・13 は最初の実行の抜粋である。証拠はすべて [evidence/increment-4/](evidence/increment-4/) に置き、1 ファイル 300 行以内、出来事は対象 job_id だけを保存した。

## 5. 実 jev の判定

job_id: `8dfb2223-508c-49a3-b00c-ccf418248235`。初期入力は指示の hello.py 作成依頼。判定時の可用実行器は両回とも `claude-personal, codex-personal, fake-a, fake-b, jev, tools`。前の回の出力数は 1 回目が 0、2 回目が 1。

| 問い | judge__1 の答え | confidence | judge__2 の答え | confidence |
|---|---|---|---|---|
| is_complete | noul=0.08 | API に独立した confidence 欄なし | noul=0.91 | API に独立した confidence 欄なし |
| next_type | implement | 0.93 | none | 0.60 |
| executor | tools | 0.18 | claude-personal | 0.71 |
| cell_count | 1 | 0.88 | 1 | 0.92 |

tools は implement 非対応のため、宣言順で最初の対応する可用実行器 claude-personal へ置き換えた。`judge.answer` に `substituted:tools->claude-personal` がある。選ばれたセルは `c1__1: implement.claude-personal` の 1 個で `COMPLETED`。出力は `kind: result`、payload に `files: ["hello.py"]` と summary がある JSON。保存された hello.py を別途実行して `hello` を確認した。Codex は可用だったがセルに選ばれなかった。

2 回目は noul が既定閾値 0.7 を超え、next_type も none で finish。仕事は **COMPLETED**。動的セルの実行は 1 回、判定は 2 回、すべて再試行 0。両判定の flow 出力がスキーマ検査を通った。

道具を同じ job_id で 1 回実行した。所要時間 304 ms。答えは noul=0.90、next_type=none（0.56）、executor=claude-personal（0.69）、cell_count=1（0.92）。閾値を適用せず、API の answers をそのまま保存した。合計の実 jev 呼び出しは **3 回**。再実行していない。

終了後は `JEV_MODE=fixture`、`PDA_MAX_ROUNDS` の値を空に戻し、全タスク定義の retryCount を正本どおりに復元し、real の 2 実行器を停止した。

## 6. ポーリング記録の API のどちらの経路で動いたか

`GET /api/tasks/queue/polldata/all` が HTTP 200 で `queueName`、`workerId`、`lastPollTime` の配列を返した。実機ではタスク名ごとの経路への切り替えは不要だった。404 と形の相違による代替経路は単体試験で確認した。

仕事検索も `workflowType='pda_job'` が HTTP 200 で動いた。`workflowType IN (pda_job)` は実機では使わず、モックで切り替えを確認した。

## 7. 指示に無かった判断と、指示どおりにできなかったこと

- state の証拠を残す場所として、最終実装は既存の `input.assembled` に `pda.input_kind: judge_state` と回数・出力数・可用実行器を載せた。実 jev を実行した時点では `judge.state` を送っており、閉じた種別一覧にないため `unknown` の raw に保存された。実 jev の state 要約はこの保存済み raw から抽出した。最終形式は単体試験と fixture e2e で確認し、有料試験は再実行していない。
- OpenObserve は検索の start_time=0 を `invalid time range` で拒否したため、1 マイクロ秒にした。実機で HTTP 200 と対象の出来事を確認した。最初の e2e 14 の最終エラーは修正のためのコンテナ再作成中の接続拒否で、再作成後の再試験は通過した。
- 終了直後の Collector の反映待ちが不足していたため、実 jev の証拠は記録の配送後に同じ job_id で取り直した。試験にも最終 workflow 出来事の待機を追加した。
- probe の `--workflow-file` と `--job-id` の両方を実 API で実行すると指定された道具 1 回の費用枠を超えるため、両入力経路はモックで検証し、実 API は指定の `--job-id` 1 回だけにした。
- job の一覧は実行中 ID と検索結果を重複排除し、開始時刻の降順にした。上流障害時には例外の型を含む理由を JSON で返す。
- Git の author が未設定だったため、このリポジトリだけ `Codex <codex@localhost>` に設定した。コミットメッセージは日本語 1 文で、Co-Authored-By は付けていない。

認証ファイルと deploy/.env の内容は表示・複写・編集していない。認証は既存の実行器および probe が通常の実行時に使用した。main、要件、設計、研究、プロセス、環境、既存報告書、作業指示は変更していない。

## 8. 未実施のこと

- e2e 10〜12、会社契約の Claude、実 Codex のセル実行。
- Tailscale Serve の設定実行と、実スマートフォンからの tailnet 接続。375px 幅は Chromium で確認した。
- `--workflow-file` からの追加の実 jev 呼び出し、問いや閾値の品質評価。
- main へのマージ。
