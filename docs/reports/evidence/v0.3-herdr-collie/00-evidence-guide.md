# 証拠の読み方

- 走行日: 2026-10-04。角括弧の採取時刻は UTC。端末の画面に表示される時刻は JST。
- `*-stream.txt` と `09-handoff.txt` は Collie の `GET /api/pane/<id>` を約 0.5 秒ごとに読み、変化した snapshot を保存した記録。Collie の画面自体も HTTP polling を使用する。SSE/WS として採取したものではない。
- 端末表示から ANSI SGR と行末の空白 padding を除いた。文字・コマンド・API の応答・タイムスタンプは保持した。PNG は画面をそのまま保存した。
- PNG の `000s`、`010s` 等は約 10 秒ごとの採取順。実時刻は同名の `*-screenshots.txt` に記録。T2 の PNG は初回案内が重なっており、文字全文の証拠は `02-claude-stream.txt`。
- `03-claude-stop.txt` と `05-codex-stop.txt` には、当時の要約と、その誤りを訂正する末尾の `CORRECTION` がある。`Esc` の生の API 応答は `ok:false / not a key: Esc / keys.send_failed`。受理されたという途中の要約は誤りで、正しいキー名 `Escape` での停止試行は行っていない。
- T3 は `Ctrl+C`、その後 `Esc` の 2 操作。T5 は `/new` 直後の入力欠落を伴う試行と、待機後に本文を再送して `Esc` を送った試行の 2 回。pane close と最後の unit stop は後片付けであり、T3/T5 の中断成功とは数えない。
- T6 の ps は指定コマンドで取得し、試用 unit の cgroup と祖先だけを残した。環境変数の証拠も `HOME`、`CLAUDE_CONFIG_DIR`、`CODEX_HOME`、`PATH` に限定した。
- `06-source.txt` は固定版ソースの参照行。Herdr は Apache-2.0、Collie は MIT の公開ソース。出典と固定コミットは報告書第 4 節に記載した。
- 認証ファイルの内容・トークン・パスワードは採取していない。バックアップの削除証拠はパス、ls のメタデータ、削除後の存在確認だけ。
