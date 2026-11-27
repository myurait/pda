# PDAのパイプライン (案Cの段階1)

T3 Codeの画面から受けた依頼を、Claudeのセッションで作業し、終端のゲートを通った一通だけを画面と通知に出す。設計は [docs/claude-unification/design-stage1.md](../../docs/claude-unification/design-stage1.md)、確かめた結果は [docs/claude-unification/check-stage1.md](../../docs/claude-unification/check-stage1.md) にある。

| ファイル | 役目 |
| --- | --- |
| `pda-pipelined` | 常駐の入口。本体は `pda_pipeline/` |
| `pda-shim` | 常駐への薄い口。`acp` (T3 Codeが起こす)、`mcp` (返信の道具)、`hook` (Stopのhook) の3つ |
| `pda-ledger` | 台帳を参照するコマンド |
| `roles/` | 役の指示。`common.md` と、役ごとの `main.md`・`worker.md`、報告係の `reporter.md` |
| `rules.json` | 伝え方の規約のゲートに載せる規則と問い |
| `pda-pipeline.service` | 常駐の定義 |
| `pda-t3code.service` | T3 Codeのサーバーの定義 |
| `tests/` | 単体の試験と、T3 Codeの代わりにACPの口を起こす確かめ用のクライアント |

## 決まり

- 直すときは、ここを直してコミットし、ミニPCの `~/pda` を pull する。役の指示と規則は次のターンから効く。コードを直したときは `systemctl --user restart pda-pipeline.service` を実行する。
- 常駐は `~/pda/deploy/pda-pipeline/` から直接動く。ミニPCに写しを置かない。
- 設定の上書き `~/.config/pda-pipeline/config.json` と、通知先 `~/.config/claude-login-notify/ntfy.env` はコミットしない。

## 置き場

| もの | 場所 (ミニPC) |
| --- | --- |
| 台帳と、セッションごとの生成ファイル | `~/.local/share/pda-pipeline/` |
| 常駐のソケット | `$XDG_RUNTIME_DIR/pda-pipeline.sock` |
| 設定の上書き | `~/.config/pda-pipeline/config.json` (無ければ既定) |
| T3 Codeの本体とデータ | `~/spike-t3code/` (待ち受けは `127.0.0.1:18900`、Tailscale Serveの19114で公開) |
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

## 端末からつなぐ

1. ミニPCでペアリングのURLを作る。出た `Pairing URL` の `http://127.0.0.1:18900` を `https://pda-web.tailaff53a.ts.net:19114` に置き換える (`#token=` からあとは残す)。URLは1台につき1回使える。

   ```sh
   ~/spike-t3code/bin/t3 pair --base-dir ~/spike-t3code/home --ttl 10m --label <端末の名前>
   ```

   `t3 pair --tailscale` は、Tailscale Serveの443の割り当てを書き換えるので使わない。
2. スマホのT3 Codeのアプリでは、Settings → Environments → Add environment にURLを貼る。PCのブラウザでは、URLを開く。
3. 新しいスレッドは、providerの `PDA` で始まる。オーナーが作ったスレッドがメインセッションになる。

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

- `judge.fixed` は試験用の固定の判定で、Codexを呼ばずに決まった結果を返す。`{"mode": "reject_until", "n": 12}` は12回目の送信まで差し戻す。`"delay"` は判定が返るまでの秒数である。
- 設定を変えたら常駐を起こし直す。

## 確かめ方

```sh
systemctl --user status pda-pipeline.service pda-t3code.service   # active (running) か
journalctl --user -u pda-pipeline.service -n 30                   # 常駐の記録
deploy/pda-pipeline/pda-ledger sessions                           # セッションの一覧
deploy/pda-pipeline/pda-ledger turns                              # ターンの一覧 (新しい順)
deploy/pda-pipeline/pda-ledger show <ターンの番号>                 # 送信ごとの下書きと判定、出来事
python3 -m unittest discover -s deploy/pda-pipeline/tests         # 単体の試験
```

- セッションごとの `claude -p` のエラー出力は `~/.local/share/pda-pipeline/sessions/<セッション>/claude.stderr` に残る。
- T3 Codeを通さずに常駐だけを確かめるときは、`tests/acp_client.py <スレッドの名前> <依頼>` を使う。
- T3 CodeのCLIから依頼を送るときは、次のようにする。`<プロジェクトのID>` には、プロジェクトに属さないスレッドの入れ物のIDを渡す。

```sh
~/spike-t3code/bin/t3 thread start --base-dir ~/spike-t3code/home --provider pda --model default --wait --json <プロジェクトのID> "依頼の文"
~/spike-t3code/bin/t3 thread send --base-dir ~/spike-t3code/home <スレッドのID> "続きの依頼" --wait --json
```
