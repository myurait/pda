# Open WebUI → Hermes Progress Pipe

PDAのOpen WebUIユーザーチャットをHermes Runs APIへ接続し、最終応答完了時だけiPhoneへntfy pushを送るローカル統合。

## 実行元の分類

- Open WebUIの対話ターンは、このPipeが生成する `owui_[0-9a-f]{32}` のHermes session IDを持つ。
- 直接のRuns API、cron、CLI、バックグラウンド実行、live probeはこのID形状を持たない。
- delegated subagentはHermes上で `platform=subagent` として動き、Open WebUIのPipeを通らない。
- pushはPipeのストリーミング応答が成功した場合にだけ送る。このため、非同期エージェントの完了は同じpushを発生させない。

## 完了タイミング

Open WebUIへ最終content chunkと `data: [DONE]` を渡した後、async generatorのclose/finalize経路からntfy送信タスクを起動する。Open WebUIが `[DONE]` で内側のstreamを閉じても通知が失われないよう、送信タスクはPipe instanceが完了まで強参照する。

通知本文は固定の `Open WebUIでPDAの応答が完了しました。` であり、ユーザー入力、応答本文、session ID、run ID、ツール名を含めない。通知タップ先はtailnet限定のOpen WebUI URL。

## デプロイ先と秘密情報

実稼働コピー:

- `~/openwebui/functions/hermes_progress_pipe.py`
- `~/openwebui/install_hermes_progress_pipe.py`
- `~/openwebui/tests/`

秘密値はGitへ入れず、mode 0600の `~/openwebui/.env` に置く。

```dotenv
PDA_NTFY_SERVER_URL=https://ntfy.sh
PDA_NTFY_TOPIC=<192-bit random capability topic>
PDA_OPENWEBUI_PUBLIC_URL=https://pda-web.tailaff53a.ts.net
```

ntfy.shの未認証topicはtopic名自体がpasswordに相当する。本構成では192-bit乱数topicを使い、漏えい時の情報量を抑えるため通知本文を固定・content-freeにする。topicをローテーションする場合は `.env` を更新してinstallerを再実行し、iPhone側も新topicへ登録し直す。

## 更新手順

リポジトリ側のファイルを実稼働ディレクトリへ反映してからinstallerを実行する。installerは既存の同一ローカルFunctionだけを更新し、無関係なFunctionを上書きしない。

```bash
install -m 0644 functions/hermes_progress_pipe.py \
  "$HOME/openwebui/functions/hermes_progress_pipe.py"
install -m 0644 install_hermes_progress_pipe.py \
  "$HOME/openwebui/install_hermes_progress_pipe.py"
install -m 0644 tests/*.py "$HOME/openwebui/tests/"
cd "$HOME/openwebui"
python install_hermes_progress_pipe.py
```

pushだけ一時停止する場合は、Open WebUI管理画面のFunction Valvesで `NTFY_TOPIC` を空にする。Hermes本体、Open WebUIチャット、非同期エージェントの実行には影響しない。

## テスト

単体・統合テスト:

```bash
cd "$HOME/openwebui"
uv run --with pytest --with pytest-asyncio --with aiohttp --with fastapi \
  python -m pytest tests/test_hermes_progress_pipe.py -q
```

実Open WebUI経路（成功応答後にcontent-free pushが1件）:

```bash
uv run --with aiohttp python tests/live_openwebui_notification_probe.py
```

実Runs API非同期経路（runは完了するがpushは0件）:

```bash
uv run --with aiohttp python tests/live_async_notification_exclusion_probe.py
```

## iPhone登録

1. App Storeの公式 `ntfy` アプリをインストールする。
2. 通知を許可する。
3. serverを `https://ntfy.sh` とし、PDA管理者から受け取ったprivate topicを購読する。
4. setup test通知を受信できることを確認する。
5. 通知をタップし、Tailscale接続中に `https://pda-web.tailaff53a.ts.net` が開くことを確認する。

private topicは公開リポジトリ、スクリーンショット、一般チャットへ転載しない。
