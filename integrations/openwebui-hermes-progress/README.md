# Open WebUI → Hermes Progress Pipe

PDAのOpen WebUIユーザーチャットをHermes Runs APIへ接続し、最終応答完了時だけiPhoneへntfy pushを送るローカル統合。

## 長時間runの定期進捗

- ユーザー向けHermes runが継続している間、Open WebUIの `status` イベントとして既定900秒（15分）ごとにheartbeatを送る。通常のassistant本文へ追記しないため、会話本文や次ターンのモデル入力を汚染しない。
- `PROGRESS_HEARTBEAT_SECONDS` Valveで間隔を秒単位に設定する。既定値は `900`、`0`で無効化する。
- heartbeatには経過時間、allowlistで検証した実行中ツール名、完了済みツール件数、一般化した直近活動だけを含める。推論本文、回答途中の本文、ユーザー入力、tool引数・preview・結果、未知のtool名は含めない。
- heartbeatのtask、進捗状態、status送信lockはrun単位で分離する。terminal event、例外、取消、streamの `aclose()` ではheartbeatを同期的に停止し、その後の遅延通知を残さない。
- title/tag/follow-up生成、automation、timer、subagent継続などOpen WebUI内部taskではprogress statusを送らない。本回答の「完了」後に内部taskのheartbeatが混入しない。
- statusはOpen WebUIのassistant messageの `statusHistory` に保存されるため、run中の画面だけでなくチャット再読込後にも確認できる。

## 実行元の分類

- Open WebUIの対話ターンは、このPipeが生成する `owui_[0-9a-f]{32}` のHermes session IDを持つ。
- 直接のRuns API、cron、CLI、バックグラウンド実行、live probeはこのID形状を持たない。
- delegated subagentはHermes上で `platform=subagent` として動き、Open WebUIのPipeを通らない。
- pushは、installerを実行した管理者本人が所有する保存済みchat ID、Open WebUIフロントエンド由来のsession ID・assistant message ID・event emitter、DB上の完了済み応答、専用Hermes session IDのすべてを満たす場合だけ送る。既存chat IDだけを付けた直接API呼び出しは対象外。
- Open WebUI内部呼び出しと `title_generation`、`tags_generation`、`follow_up_generation` などのtask呼び出しは除外する。このため、内部taskや非同期エージェントの完了は同じpushを発生させない。

## 完了タイミングと表示内容

実装バージョンは `hermes_progress_pipe` v2.1.0-local.12。

ストリーミング時は、Open WebUIへ最終content chunkと `data: [DONE]` を渡した後、async generatorのclose/finalize経路からntfy送信タスクを起動する。Pipe開始時のOpen WebUI host taskの終了を待ってから、Open WebUI DB上の対象assistant messageを読む。success、failure、cancel、timeoutやhost taskの終了状態は通知種別として区別せず、所有者本人のmessageが `done=true` かつ本文が非空なら保存済み内容を通知する。通知タイトルと本文は保存済みレコードだけから読み、Hermesのterminal outputやユーザー入力を代用しない。outlet filterによるredactionを前提にする環境では、filter失敗時にも保存済み本文が通知され得るため、`NTFY_TOPIC`を空にして外部pushを無効化する。

同一assistant message IDへの送信試行は、Function processの存続中は最大1回に抑止する。これは外部キューを持たないadvisoryなat-most-once attemptであり、プロセス停止をまたぐdurable exactly-once配送ではない。通知失敗はチャット応答を失敗扱いにしない。

通知は次の形式になる。

- タイトル: Open WebUI DBのチャットタイトル（最大100文字）。自動タイトル生成を最大約20秒待ち、未確定なら実際の `New Chat` 表示を使う。ユーザー入力にはフォールバックしない。
- 本文: Open WebUI DBへ保存された最終回答の冒頭（最大240文字）。reasoningとtool traceは除外し、制御文字と連続空白を正規化し、超過時は末尾を `…` にする。保存済み回答が空なら固定文で代用せず、通知を送らない。
- 絵文字tag: 付与しない。iOS上で `✅ PDA` が先頭に固定表示される旧形式は廃止。
- タップ先: `https://pda-web.tailaff53a.ts.net/c/<chat_id>`。対象チャットを直接開く。

タイトル・回答取得はOpen WebUIの所有者スコープ付きDB lookupを使用する。別ユーザーのchat ID、保存されていないchat/message ID、認証ユーザーIDがない呼び出しでは通知自体を送らない。ntfy送信を許可するOpen WebUI user IDはinstallerが管理者APIキーのidentityから取得し、`NTFY_ALLOWED_USER_ID` Valveへ固定する。ntfy serverとOpen WebUI click URLはinstallerとruntimeの同じ条件で検証し、外部宛ての平文HTTP、credential入りURL、query/fragment、不正URLを拒否する。ntfy serverに限り、ローカル試験・self-host用途のloopback HTTPを許可する。

Hermes runの成功・failure・cancel・timeoutは通知種別として区別しない。Open WebUIがユーザー向けassistant応答を保存して `done=true` にし、その回答本文が空でなければ、保存された表示内容の冒頭を同じ形式で通知する。

## プライバシーと秘密情報

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

ntfy.shの未認証topicはtopic名自体がpasswordに相当する。192-bit乱数topicを使用し、漏えい時はtopicをローテーションする。

旧版と異なり、現在はユーザーの要望によりチャットタイトルと回答冒頭をホスト版ntfy.shへ送る。通知内容はntfy.sh側のmessage cacheとiPhoneの通知履歴へ残り得るため、機密会話ではこの経路を使わないこと。会話内容を外部ホストへ残したくない場合は、Function Valvesの `NTFY_TOPIC` を空にして停止するか、将来tailnet内へntfyをself-hostする。

## 更新手順

リポジトリ側のファイルを実稼働ディレクトリへ反映してからinstallerを実行する。installerは既存の同一ローカルFunctionだけを更新し、無関係なFunctionを上書きしない。更新前のsource・metadata・active state・Valvesを退避し、失敗時はすべて復元する。新規作成時のrollbackはinstall transaction固有nonceとsourceが一致する場合だけ削除し、競合処理が作成・更新したFunctionを削除しない。成功時はsource、active state、全ValvesをAPIから再読込して一致を確認する。rollback時もsource・metadata・active state・全Valvesを再読込し、復元不一致を成功扱いにしない。

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

単体・ローカル統合テスト（現在71件）:

```bash
cd "$HOME/openwebui"
uv run --with pytest --with pytest-asyncio --with aiohttp --with fastapi \
  python -m pytest tests/test_hermes_progress_pipe.py \
  tests/test_install_hermes_progress_pipe.py -q
```

実Open WebUIフロントエンド相当のasync経路（DB保存済みタイトル・回答、詳細progress、チャット直リンクを持つpushが1件）:

```bash
uv run --with aiohttp python tests/live_openwebui_notification_probe.py
```

このlive probeは、通知タップ先も検証できるようテストチャットを1件残す。assistant messageの `done=true`、`Hermesが処理を開始しました…` と `完了` のstatus履歴、pushが厳密に1件であることも確認する。失敗時は作成したチャットを削除する。

実Open WebUI + 短縮heartbeat間隔（完了後にValveを元の900秒へ復元し、合成E2Eのntfy pushは抑止）:

```bash
cd "$HOME/openwebui"
uv run --with aiohttp python tests/live_openwebui_heartbeat_probe.py
```

このheartbeat probeは2秒間隔で実toolを含む長時間runを行い、複数heartbeatの `statusHistory` 永続化、入力・prompt非混入、terminal後3秒間の追加heartbeatなしを確認する。成功時は確認用チャットを1件残し、失敗時は削除する。

実Runs API非同期経路（runは完了するが新規pushは0件）:

```bash
uv run --with aiohttp python tests/live_async_notification_exclusion_probe.py
```

## iPhone登録

1. App Storeの公式 `ntfy` アプリをインストールする。
2. 通知を許可する。
3. serverを `https://ntfy.sh` とし、PDA管理者から受け取ったprivate topicを購読する。
4. 通知タイトルがOpen WebUIのチャットタイトル、本文が回答冒頭になっていることを確認する。
5. 通知をタップし、Tailscale接続中に対象のOpen WebUIチャットが直接開くことを確認する。

private topicは公開リポジトリ、スクリーンショット、一般チャットへ転載しない。
