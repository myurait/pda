# PDAのパイプライン (案C)

T3 Codeの画面から受けた依頼を、Claudeのセッションで作業し、終端のゲートを通った返信だけを画面と通知に出す。設計は [design-stage1.md](../../docs/claude-unification/design-stage1.md) と [design-stage2.md](../../docs/claude-unification/design-stage2.md)、確認した結果は [check-stage1.md](../../docs/claude-unification/check-stage1.md) と [check-stage2.md](../../docs/claude-unification/check-stage2.md) にある。

| ファイル | 役目 |
| --- | --- |
| `pda-pipelined` | 常駐プロセスの入口。本体は `pda_pipeline/` |
| `pda-shim` | 常駐プロセスへの薄い窓口。`acp` (T3 Codeが起動する)、`mcp` (返信のツール)、`hook` (Stopのhook) の3つ |
| `pda-ledger` | 台帳を参照するコマンド |
| `roles/` | 役の指示。`common.md` と、役ごとの `main.md`・`worker.md`、報告係の `reporter.md` |
| `rules.json` | 伝え方の規約のゲートに載せる規則と問い (段階1。`norms.enabled` を切にしたときに使う) |
| `norms/` | オーナーの規約の正本。`rules.json` (規則ごとの、載せるか・判定器・問い・外れを差し戻すか)、`mcp.json` (すべてのセッションに配るMCP)、`plugin/` (すべてのセッションに配るskill) |
| `pda-pipeline.service` | 常駐プロセスの定義 |
| `pda-t3code.service` | T3 Codeのサーバーの定義 |
| `tests/` | 単体の試験と、T3 Codeの代わりにACPの窓口を起動する確認用のクライアント |
| `dev-pc/` | 開発PCに置くブリッジの常駐プロセスのスクリプトと定義 |

## 決まり

- 直すときは、ここを直してコミットし、ミニPCの `~/pda` を pull する。役の指示と規則は次のターンから効く。コードを直したときは `systemctl --user restart pda-pipeline.service` を実行する。
- 常駐プロセスは `~/pda/deploy/pda-pipeline/` から直接動く。ミニPCにコピーを置かない。
- 設定の上書き `~/.config/pda-pipeline/config.json` と、通知先 `~/.config/claude-login-notify/ntfy.env` はコミットしない。
- オーナーの規約は `norms/rules.json` を直す。規則の `load` が載せるか、`judge` が判定器、`enforce` が外れを差し戻すか (`false` は判定を台帳に残すだけ) である。直すと、常駐プロセスを再起動せずに次のターンから効く。
- `norms/` には、開発PCの会社のアカウントの規則と、開発PCのメモリの本文を置かない。

## 置き場

| もの | 場所 (ミニPC) |
| --- | --- |
| 台帳と、セッションごとの生成ファイル | `~/.local/share/pda-pipeline/` |
| 常駐プロセスのソケット | `$XDG_RUNTIME_DIR/pda-pipeline.sock` |
| 設定の上書き | `~/.config/pda-pipeline/config.json` (無ければ既定) |
| セッションが足し引きした規則 | `~/.local/share/pda-pipeline/norms/overlay.json` (正本の `norms/rules.json` に重ねる) |
| T3 Codeの本体とデータ | `~/spike-t3code/` (`127.0.0.1:18900` で接続を受け付け、Tailscale Serveの19114で公開) |
| Claudeのログイン | `~/pda/secrets/claude` (`claude-remote-control.service` と同じ) |
| Codexのログイン | `~/.codex` |
| Jevの認証 | `~/pda/secrets/typesafe_credentials` |

## 新しい環境に入れる

ミニPCの `~/pda` で行う。T3 Codeは `~/spike-t3code` に入っている前提である。

```sh
cp deploy/pda-pipeline/pda-pipeline.service deploy/pda-pipeline/pda-t3code.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pda-pipeline.service pda-t3code.service
```

T3 Codeの設定 `~/spike-t3code/home/userdata/settings.json` の `providerInstances` を次のようにする。

```json
{
  "pda": {
    "driver": "acpRegistry",
    "displayName": "PDA",
    "enabled": true,
    "config": {
      "source": "local",
      "commandPath": "/usr/bin/python3",
      "commandArgs": ["/home/user/pda/deploy/pda-pipeline/pda-shim", "acp"]
    }
  },
  "claudeAgent": { "driver": "claudeAgent", "enabled": false },
  "codex": { "driver": "codex", "enabled": false }
}
```

## 端末から接続する

1. ミニPCでペアリングのURLを作る。出た `Pairing URL` の `http://127.0.0.1:18900` を `https://pda-web.tailaff53a.ts.net:19114` に置き換える (`#token=` からあとは残す)。URLは1台につき1回使える。

   ```sh
   ~/spike-t3code/bin/t3 pair --base-dir ~/spike-t3code/home --ttl 10m --label <端末の名前>
   ```

   `t3 pair --tailscale` は、Tailscale Serveの443の割り当てを書き換えるので使わない。
2. スマホのT3 Codeのアプリでは、Settings → Environments → Add environment にURLを貼る。PCのブラウザでは、URLを開く。
3. 新しいスレッドは、providerの `PDA` で始まる。オーナーが作ったスレッドがメインセッションになる。

## 開発PCのブリッジ

PDAのセッションが、ツール `ask_dev_pc` で、開発PCのClaude (会社のアカウント) に作業を依頼するための経路である。開発PCの常駐プロセスが、ミニPCの22番にSSHで接続し、届いた依頼ごとに開発PCの `claude -p` を起動して、返信を返す。

| もの | 入れる場所 (開発PC) | 役目 |
| --- | --- | --- |
| `dev-pc/pda-bridge` | `~/.local/bin/` | ブリッジの常駐プロセスの本体。`claude -p` に付ける引数は、このファイルに固定してある |
| `dev-pc/com.pda.dev-pc-bridge.plist` | `~/Library/LaunchAgents/` | 上のスクリプトを、ログインのあいだ動かし続ける |
| (リポジトリに置かない) | `~/.config/pda-bridge/allowed-tools.txt` | 承認なしで実行してよいMCPのツールの名前。1行に1つ。無ければ、どのツールの呼び出しも拒否される |
| (リポジトリに置かない) | `~/.config/pda-bridge/config.json` | 既定を変えるときだけ置く (SSHの接続先、ミニPCで起動するコマンド、待つ上限) |

- `claude -p` は、`--restricted` と `--tools ""` で起動する。組み込みツールと、ユーザーの設定 (hook、許可の規則、ユーザーの設定に登録したMCP) は使わない。使えるのは、ログインに付いている会社のコネクタと、管理設定とpluginのMCPのうち、`allowed-tools.txt` に書いたツールだけである。
- `allowed-tools.txt` に入れるツールは、オーナーが決める。ブリッジは、依頼のたびに、このファイルの内容を取得する。直すか消すと、ブリッジの常駐プロセスを再起動せずに、次の依頼から効く。
- `claude -p` には、環境変数 `MCP_CONNECTION_NONBLOCKING=0` と `MCP_CONNECT_TIMEOUT_MS=20000` を渡す。コネクタの接続を20秒まで待ってから、最初の要求を出す。渡さないと、接続の前に最初の要求が出て、コネクタのツールが載らないことがある。
- ブリッジの常駐プロセスが開発PCで行うのは、ミニPCへのSSHの接続と、`claude -p` の起動だけである。開発PCは外部からの接続を受け付けない。
- 送った依頼文と、開発PCのClaudeの返信は、ミニPCの常駐プロセスを通り、PDAのセッションの返信の材料になる。返信の材料は、ミニPCの台帳に残り、返信の前の判定 (Jev、Codex) に渡り、返信に入った分は通知 (ntfy) にも出る。
- 動作のログは `~/Library/Logs/pda-bridge.log` に残る。依頼番号と文字数だけで、依頼と返信の内容は残さない。

開発PCに入れるときは、開発PCのリポジトリのフォルダ (`~/dev/pda`) で次を実行する。取り出しているブランチに関わらず、mainの内容から入れる。

```sh
git fetch origin main:main
git show main:deploy/pda-pipeline/dev-pc/pda-bridge > ~/.local/bin/pda-bridge
chmod 755 ~/.local/bin/pda-bridge
git show main:deploy/pda-pipeline/dev-pc/com.pda.dev-pc-bridge.plist > ~/Library/LaunchAgents/com.pda.dev-pc-bridge.plist
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.pda.dev-pc-bridge.plist
tail ~/Library/Logs/pda-bridge.log    # connected の行が出る
```

登録を取り消すときは、次を実行する。

```sh
launchctl bootout gui/501/com.pda.dev-pc-bridge
trash ~/Library/LaunchAgents/com.pda.dev-pc-bridge.plist ~/.local/bin/pda-bridge
```

`~/.local/bin/pda-bridge --check` で、設定と、`claude -p` に付ける引数を確認できる。

## 設定

既定の値は `pda_pipeline/config.py` の `DEFAULTS` にある。`~/.config/pda-pipeline/config.json` に書いたキーだけが上書きされる。

```json
{
  "roles": { "worker": { "model": "claude-opus-5-5", "effort": "medium" } },
  "stages": { "reporter": true, "jev": true, "codex": true },
  "judge": { "codex_model": "gpt-6.2-sol", "codex_effort": "medium", "timeout_sec": 600 },
  "limits": { "completion_rejections": 5, "stop_hook_blocks": 5 }
}
```

- 既定で、`norms/` の正本から、役の指示・報告係の指示・ゲートの問いを組み、依頼を受けた時点のゲートを動かす。`norms.enabled` を `false` にすると、段階1の役の指示と `rules.json` だけを使う。`norms.pre_gate` を `false` にすると、依頼を受けた時点のゲートだけを無効にする。
- `judge.fixed` は試験用の固定の判定で、Codexを呼ばずに決まった結果を返す。`{"mode": "reject_until", "n": 12}` は12回目の送信まで差し戻す。`"delay"` は判定が返るまでの秒数である。
- 設定を変えたら常駐プロセスを再起動する。

## 確認方法

```sh
systemctl --user status pda-pipeline.service pda-t3code.service   # active (running) か
journalctl --user -u pda-pipeline.service -n 30                   # 常駐の記録
deploy/pda-pipeline/pda-ledger sessions                           # セッションの一覧
deploy/pda-pipeline/pda-ledger turns                              # ターンの一覧 (新しい順)
deploy/pda-pipeline/pda-ledger show <ターンの番号>                 # 送信ごとの下書きと判定、出来事
deploy/pda-pipeline/pda-ledger knowledge                          # 案件ごとに残した、決まったこと・分かったこと
deploy/pda-pipeline/pda-ledger forget <番号>                       # 残した1件を消す
python3 -m unittest discover -s deploy/pda-pipeline/tests         # 単体の試験
```

- セッションごとの `claude -p` のエラー出力は `~/.local/share/pda-pipeline/sessions/<セッション>/claude.stderr` に残る。
- T3 Codeを通さずに常駐プロセスだけを確認するときは、`tests/acp_client.py <スレッドの名前> <依頼>` を使う。
- 台帳に残っている出した返信を、正本の問いに通し直すときは、`tests/replay_norms.py <台帳のSQLite>` を使う。規則ごとに、出した返信を外れにした数が出る。
- T3 CodeのCLIから依頼を送るときは、次のようにする。`<プロジェクトのID>` には、プロジェクトに属さないスレッドの入れ物のIDを渡す。

```sh
~/spike-t3code/bin/t3 thread start --base-dir ~/spike-t3code/home --provider pda --model default --wait --json <プロジェクトのID> "依頼の文"
~/spike-t3code/bin/t3 thread send --base-dir ~/spike-t3code/home <スレッドのID> "続きの依頼" --wait --json
```
