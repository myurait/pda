# 日次状態報告の配信

- Status: active

## 目的

毎朝の状態報告をオーナーへ届ける。報告そのものはHermesの定期実行ジョブ `4d9f09797922`（`PDA日次自己改善・状態報告`、07:45 JST）が作る。ジョブは実行結果をファイルへ書いたうえで、ジョブを作った会話へ返そうとする。その会話はOpen WebUIの要求・応答経路で提供されており、オーナーが求めていないメッセージを送り込む経路を持たない。そのため報告は書かれるが誰にも届かない。本運用はその隙間だけを埋める。

## 構成

- 配信方針: `continuity/daily-report.json`（起動時に `~/.config/pda/daily-report.json` へ複製される）
- 管理習慣の宣言: `profiles/pda/managed-habits.json` の `daily-owner-state-report-delivery`
- 実装: `src/pda/report/`、実行入口は `operations/report/pda_daily_report.py`
- systemd unit: `infra/systemd/pda-daily-report-delivery.service` / `.timer`（07:50 JST）
- 送信先: Open WebUIの完了通知が使っているpush topic。サーバURLとトピックは `~/openwebui/.env` の `PDA_NTFY_SERVER_URL` と `PDA_NTFY_TOPIC` から実行時に読む。リポジトリには秘密値を置かない

## 動作

07:50に起動し、ジョブの出力ディレクトリから最新の実行ファイルを読む。そのファイルが当日の 07:45 以降に書かれていれば `## Response` 以降を本文として送る。まだ無ければ30秒間隔で最大20分待つ。

二重送信は時刻ではなく状態ファイル（`~/.local/state/pda/daily-report-delivery.json`）で防ぐ。送信済みの実行ファイル名が記録されるため、再試行、ホスト再起動後の追いかけ実行、手動実行のいずれでも同じ報告が二度送られることはない。

本文が方針の上限文字数を超える場合は、送らずに落とすのではなく末尾を切って送る。

## 導入

```bash
~/.hermes/hermes-agent/venv/bin/python operations/report/install.py
```

インストーラはpush設定が読めることを先に確かめ、読めなければタイマーを張らずに失敗する。07:50になって初めて失敗が分かる状態を作らないため。

## 確認

```bash
~/.hermes/hermes-agent/venv/bin/python operations/report/pda_daily_report.py status --config ~/.config/pda/daily-report.json
```

`latest_run` が最新の報告、`last_delivered_run` が最後に送った報告を示す。両者が一致していれば届いている。詳細な実行記録は `journalctl --user -u pda-daily-report-delivery.service` にある。

## 制約

- 配信先はオーナーのpush topicであり、Open WebUIの会話ではない。Open WebUIの会話履歴はOpen WebUI自身が保持しており、Hermes側から書き込む経路が無い
- 報告の生成には関与しない。ジョブが動かなければ配信は `no-run-in-window` を返して終わる
