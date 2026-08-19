# Open WebUI → Hermes Progress Pipe

PDAのOpen WebUIユーザーチャットをHermes Runs APIへ接続し、最終応答完了時だけiPhoneへntfy pushを送るローカル統合。

## PDA Kanbanの可視化導線

PDA改善タスクの正本はHermes標準の`~/.hermes/kanban.db`とし、初期移行タスクにはtenant `pda-improvement`を付ける。独自のタスクDBやOpen WebUI内の複製台帳は作らない。

オーナー向けURLは`https://pda-web.tailaff53a.ts.net/hermes/kanban`。同一tailnet限定ホストで、次の経路を使う。

```text
/           -> Open WebUI                    127.0.0.1:9120
/hermes/*   -> dashboard_prefix_proxy.py     127.0.0.1:9121
             -> Hermes Dashboard             127.0.0.1:9119
             -> Kanban                       ~/.hermes/kanban.db
```

安全境界:

- Hermes Dashboardは`infra/systemd/hermes-dashboard.service.d/10-pda-loopback.conf`で`127.0.0.1:9119`へ限定する。Kanban APIをLANへ直接公開しない。
- prefix proxyも`127.0.0.1:9121`限定で、上流にはcredentialを含まないloopback HTTPだけを許可する。上流`Host`はloopback originへ固定し、公開host名は`X-Forwarded-Host`だけで伝える。
- 外部導線はTailscale Serveのみとし、Funnelは使わない。Hermes Dashboard自身のusername/password認証も維持する。
- Hermes v0.20.2には2つの既存prefix不整合がある。password login HTMLの`/auth/password-login`とログイン後遷移は`/login`レスポンスに限って補正し、配布済みSPA bundleのlogout先`window.location.assign("/login")`は未圧縮の直下`/assets/*.js`内の完全一致だけを`/hermes/login`へ補正する。それ以外のSPA、API、WebSocket本文は書き換えない。
- upstreamの`Set-Cookie`は、単一のwell-formed cookieかつ`Path=/hermes`のときだけraw値を転送する。Pathなし・root scope・malformed cookieはfail-closedで破棄し、Hermes sessionをOpen WebUI rootへ送らない。
- upstreamの圧縮responseはaiohttpで自動展開せず、encoded bodyと`Content-Encoding`を対でそのまま転送する。圧縮済みassetには本文補正を適用しない。
- 初期移行時は`kanban.auto_decompose=false`、全カード未割当とする。ボードを可視化しただけでworkerを自動起動しない。
- Open WebUI v0.11.0の標準banner `pda-kanban-link`へMarkdown相対リンク`/hermes/kanban`を置く。既存bannerは保持し、このIDだけをidempotentに更新する。独自Actionやfrontend forkは使わない。

管理対象:

- `dashboard_prefix_proxy.py`
- `infra/systemd/pda-kanban-dashboard-proxy.service`
- `infra/systemd/hermes-dashboard.service.d/10-pda-loopback.conf`
- `tests/test_dashboard_prefix_proxy.py`

導入手順:

```bash
install -D -m 0644 \
  integrations/openwebui-hermes-progress/dashboard_prefix_proxy.py \
  "$HOME/.local/libexec/pda/dashboard_prefix_proxy.py"
cmp -s \
  integrations/openwebui-hermes-progress/dashboard_prefix_proxy.py \
  "$HOME/.local/libexec/pda/dashboard_prefix_proxy.py"

install -D -m 0644 infra/systemd/pda-kanban-dashboard-proxy.service \
  "$HOME/.config/systemd/user/pda-kanban-dashboard-proxy.service"
install -D -m 0644 infra/systemd/hermes-dashboard.service.d/10-pda-loopback.conf \
  "$HOME/.config/systemd/user/hermes-dashboard.service.d/10-pda-loopback.conf"
systemctl --user daemon-reload
systemctl --user restart hermes-dashboard.service
systemctl --user enable --now pda-kanban-dashboard-proxy.service

TAILSCALE_BIN="$HOME/.local/opt/tailscale-1.102.2/tailscale"
"$TAILSCALE_BIN" --socket="$HOME/.local/share/tailscale-pda/tailscaled.sock" \
  serve --bg --yes --set-path /hermes http://127.0.0.1:9121
```

検証条件:

- tracked `dashboard_prefix_proxy.py`と`~/.local/libexec/pda/dashboard_prefix_proxy.py`がbyte一致する。
- `ss`で9119、9120、9121がすべて`127.0.0.1`にだけlistenする。
- Tailscale Serve statusが`/ -> 127.0.0.1:9120`と`/hermes -> 127.0.0.1:9121`を同時に保持する。
- `/hermes/kanban`が`/hermes/login`へ遷移し、認証CookieのPathが`/hermes`、認証後Kanban APIが200を返す。
- Open WebUIの`/api/v1/configs/banners`に`pda-kanban-link`が1件だけあり、本文リンク先が`/hermes/kanban`である。
- `pda-improvement`の初期未完了カードが9件あり、依存関係が6本ある。Kanban化カード完了後は、その子カードだけがTodoからReadyへ昇格する。
- 再起動後も両systemd serviceとTailscale Serve導線が維持される。

ロールバック時は、変更前statusを`~/.local/state/pda/rollback/tailscale-serve-before-kanban.json`で確認する。現行のlegacy Serve設定は`serve get-config --all`から完全復元できないため、`tailscale serve reset`後に`serve --bg --yes http://127.0.0.1:9120`でOpen WebUIのroot導線だけを再登録する。次にproxy serviceを停止・disableし、`~/.local/libexec/pda/dashboard_prefix_proxy.py`の配備コピーを削除する。loopback drop-inを外して`systemctl --user daemon-reload`後にHermes Dashboardを再起動する。Open WebUI bannerは`~/.local/state/pda/rollback/openwebui-banners-before-kanban.json`の一覧へ戻す。Kanban DBのカードは表示導線と独立しているため、ロールバックで削除しない。

## ツール実行前の即時中間メッセージ

- Hermes Runs APIの`message.interim`をOpenAI互換content chunkへ直ちに変換する。モデルが「短い計画」を出した時点でOpen WebUI本文へ表示し、同じrunを閉じずにtool実行と最終回答を続ける。
- 通常のtoken streamですでに表示された中間文はHermes側の`already_streamed`判定で重複送信しない。中間文と最終回答の間には空行を置く。
- Open WebUIの保存済みassistant本文には中間文と最終回答の両方を残す。一方、完了時ntfy pushは中間prefixを除き、従来どおり最終回答の冒頭を通知する。
- この経路には、Hermes core側で`interim_assistant_callback`をRuns SSEへ接続する管理パッチが必要。復元可能なpatch seriesは`hermes-core/`に保存する。

## 長時間runの定期進捗

- ユーザー向けHermes runが継続している間、Open WebUIの `status` イベントとして既定300秒（5分）ごとにheartbeatを送る。通常のassistant本文へ追記しないため、会話本文や次ターンのモデル入力を汚染しない。
- heartbeatはHermes Runs APIの `plan.updated` イベントを正本とし、`todo`計画の完了項目数をcancelled以外の全項目数で割った概算進捗率、直近の完了項目、現在のin-progress項目だけを表示する。例: `[5分経過] 処理中 (50%) - 完了: 設計の大枠を確定。現在: 外部システムとの疎通条件を追加調査中。`
- 前提となるHermes APIは `/v1/capabilities` の `features.plan_progress_events=true` を公開する。未対応APIでもrun自体は継続するが、heartbeatは率を捏造せず未算出になる。
- 計画が未登録なら率を捏造せず `進捗率未算出` と表示する。`PROGRESS_HEARTBEAT_SECONDS` Valveは既定 `300`、`0`で無効化できる。
- `実行中: terminal`、`完了: read_file`、tool件数、汎用reasoning表示のような低水準ログは既定で送らない。診断時だけ `SHOW_TOOL_ACTIVITY=true` でtool lifecycleを再表示できる。`SHOW_REASONING_STATUS`も既定false。
- 推論本文、回答途中の本文、生のユーザー入力、tool引数・preview・raw結果、未知のtool名はheartbeatへ直接含めない。表示するtodo項目はモデルが作成した作業要約であり、Hermes API側で件数・長さを制限して秘密情報とcredential付きURLのredactionを通す。Pipe側でもcredential付きURL、secret代入、Bearer値を再度redactする。これはntfy pushには送らず、Open WebUIのローカル`statusHistory`に保存する。
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

実装バージョンは `hermes_progress_pipe` v2.1.0-local.14。

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

単体・ローカル統合テスト（現在76件）:

```bash
cd "$HOME/openwebui"
uv run --with pytest --with pytest-asyncio --with aiohttp --with fastapi \
  python -m pytest tests/test_hermes_progress_pipe.py \
  tests/test_install_hermes_progress_pipe.py -q
```

実Open WebUIで、中間計画がtool待機中に保存・表示可能になり、人間の追加ターンなしで最終回答まで続くことを時刻付きで確認:

```bash
uv run --with aiohttp python tests/live_openwebui_interim_probe.py
```

成功条件は、中間計画が`done=false`の間に現れ、5秒toolの完了後に最終回答が同じassistant本文へ追記され、両者の観測時刻に4秒以上の差があること。この合成runのntfy pushは抑止し、確認用チャットを1件残す。

実Open WebUIフロントエンド相当のasync経路（DB保存済みタイトル・回答、詳細progress、チャット直リンクを持つpushが1件）:

```bash
uv run --with aiohttp python tests/live_openwebui_notification_probe.py
```

このlive probeは、通知タップ先も検証できるようテストチャットを1件残す。assistant messageの `done=true`、`Hermesが処理を開始しました…` と `完了` のstatus履歴、pushが厳密に1件であることも確認する。失敗時は作成したチャットを削除する。

実Open WebUI + 短縮heartbeat間隔（完了後にValveを元の300秒へ復元し、合成E2Eのntfy pushは抑止）:

```bash
cd "$HOME/openwebui"
uv run --with aiohttp python tests/live_openwebui_heartbeat_probe.py
```

このheartbeat probeは2項目の実todo計画と7秒の実toolを含む長時間runを行い、2秒間隔の複数heartbeatが50%・完了節目・現在工程を表示すること、tool lifecycleログ・tool名・入力・promptを表示しないこと、terminal後3秒間の追加heartbeatがないことを確認する。成功時は確認用チャットを1件残し、失敗時は削除する。

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
