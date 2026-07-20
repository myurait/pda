# PDAミニPC セットアップ検討・実行記録

- 更新日: 2026-07-19
- 対象プロジェクト: Personal Delegate Agent（PDA）
- 対象機器: GMKtec M8（AMD Ryzen 5 PRO 6650H / 16GB LPDDR5 / 512GB SSD）
- 現在地点: Hermes・Firecrawl・Web Dashboard・Gatewayをすべて常時稼働化し、スマホからWeb UIで管理可能な状態にした。加えて、開発用PC上のClaude CodeからHermesへMCP経由で片方向の接続を確立し、`conversations_list` の呼び出しまで動作確認済みの状態。
- 次工程: HermesからClaude Codeへの逆方向連携（双方向化）、PKB取り込み系の整備、メインモデルのClaude移行

---

## 1. この文書の目的

Personal Delegate Agent（PDA）の常時稼働基盤として購入したミニPCについて、これまでに検討した構成、決定した方針、実際に完了した作業、および未完了の作業を整理する。

実行済みとして記載するのは、会話上で完了が確認できた内容に限定する。検討したが実行確認が取れていない項目は、未実施または確認未了として区別する。

---

## 2. ミニPCの役割

このミニPCは、PDAの初期中核を常時稼働させるためのサーバーとして使用する。

当面の役割は以下のとおり。

- Hermesの常時稼働
- PDA関連サービスの実行
- MCPサーバーの実行
- 開発用PC上のClaude CodeやCodexとの連携
- PDAの記憶、ログ、設定、成果物の保存
- 将来的なPKB／コンテキストグラフ基盤の実行環境

---

## 3. 検討・決定した構成

### 3.1 ハードウェア

- 機種: GMKtec M8
- PDA用の常時稼働機として購入済み
- Windowsがプリインストールされていた
- Windows環境を退避するための追加部品は購入しない方針

### 3.2 OS

採用OSは以下とした。

- Ubuntu Server 24.04.4 LTS

選定理由として検討した事項は以下のとおり。

- GUIを常用しないサーバー用途に適している
- Hermes、Claude Code、Codex、MCPサーバーなどの実行環境を構築しやすい
- SSHを前提とした遠隔管理に適している
- 常時稼働環境として管理しやすい
- LTSであり、PDAの基盤として長期運用しやすい

### 3.3 Windowsの扱い

検討した案には、既存Windows環境の保存、デュアルブート、別ストレージへの退避などが含まれるが、新しい部品を購入しない前提では、Windows環境を保持するための作業と制約が増える。

そのため、PDA専用機としてUbuntu Serverを導入し、Windows環境を維持しない方向で進めた。

### 3.4 ネットワーク

当初、有線LANでの接続を想定したが、設置条件上、有線接続が難しい可能性があった。

そのため、以下の方針を検討した。

- Ubuntu Serverのインストール時からWi-Fiを設定する
- Wi-Fi接続のみでも初期構築を進める
- 有線LANを必須条件にはしない
- Wi-Fi経由でローカルネットワーク上の開発用PCからSSH接続する

現在SSH接続まで完了しているため、ネットワーク接続とローカルネットワーク内からの到達性は確保できている。

### 3.5 管理方法

ミニPCはモニターやキーボードを常時接続して操作するのではなく、開発用PCからSSHで管理する方針とした。

想定する基本操作は以下のとおり。

- OS更新
- パッケージ導入
- Hermesの導入・設定
- サービス状態の確認
- ログ確認
- 設定ファイル編集
- PDA関連リポジトリの操作

---

## 4. 検討したセットアップ手順

これまでに検討した初期セットアップの流れは以下のとおり。

1. Ubuntu Server 24.04.4 LTSのインストールメディアを作成する
2. ミニPCをインストールメディアから起動する
3. Ubuntu Serverを内部ストレージへインストールする
4. インストール中にネットワークを設定する
5. Wi-Fiしか利用できない場合はWi-Fiへ接続する
6. OpenSSH Serverを有効にする
7. インストール完了後に再起動する
8. ローカルコンソールでIPアドレスを確認する
9. 開発用PCからSSH接続する
10. OSとパッケージを更新する
11. 必要に応じて日本語ロケールや日本語入力環境を設定する
12. Hermesを導入する
13. Hermesの診断と初期設定を行う
14. Codex認証を設定する
15. Hermesからローカルのワークスペースを操作できることを確認する

---

## 5. 実行済みの内容

会話上で完了が確認できている内容は以下のとおり。

### 5.1 ミニPCの準備

- GMKtec M8を購入した
- PDA用の常時稼働機として使用する方針を決定した

### 5.2 OSの導入

- Ubuntu Server 24.04.4 LTSを採用した
- ミニPCへUbuntu Serverを導入した
- Ubuntu Serverを起動できる状態にした
- タイムゾーンと日本語localeは設定済み

### 5.3 ネットワーク接続

- ミニPCをネットワークへ接続した
- 有線LANを前提とせず、Wi-Fi利用を含む構成で進めた
- 開発用PCから到達可能な状態にした

### 5.4 SSH接続

- 開発用PCからミニPCへSSH接続した
- リモートで以後のセットアップを継続できる状態にした

### 5.5 OS更新と基本パッケージの導入

- `apt update` および `apt upgrade` によりOSとパッケージを最新化した
- `git`、`curl`、`ca-certificates`、`vim` を導入した

### 5.6 Hermesの導入

- 採用したエージェントランタイム: NousResearch/hermes-agent
- 公式インストーラー（`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`）を実行して導入した
- インストーラーはPython 3.11以上、Node.js、ripgrep、ffmpeg、uv（Pythonパッケージマネージャー）を自動導入した

### 5.7 Hermesの初期設定

導入直後に対話式ウィザードで以下を確定した。

- モデルプロバイダー: OpenAI Codex を選択（ブラウザ経由のデバイスコード認証。APIキーは使用しない）
- 認証情報の格納先: `~/.hermes/auth.json`
- 実行環境（terminal backend）: Local を選択（このミニPC上で直接コマンドを実行する構成）

モデル選定の背景として、当初はClaudeを利用予定であったが、Anthropic側のアカウント準備中のため、暫定的にCodexを採用した。将来的にClaudeへ切り替える場合も、Hermes側では `hermes model` で再選択するだけで済む構造となっている。

### 5.8 Web検索・本文取得基盤（Firecrawl Self-Hosted）の導入

Hermesのツール群のうち、Web Search & Extract機能を有効化するためにFirecrawlをセルフホストで導入した。

#### 選定理由

無料で利用できる候補としてSearXNGとFirecrawl Self-Hostedを比較検討した結果、Firecrawl Self-Hostedを採用した。

- 検索と本文取得の両方をひとつのスタックで完結できる
- 外部APIのクエリ上限に依存しない
- ミニPCのメモリ容量（16GB）で運用可能

なお、Brave Search API無料枠（月2,000クエリ、既存ユーザー向け）は、非同期エージェントによる情報収集用途では消費量に対して不足する見込みのため、主軸には採用しない判断とした。

#### 導入手順の要点

- Docker Engine および Compose Plugin をUbuntu公式リポジトリから導入した
- `firecrawl/firecrawl` を `~/firecrawl` にクローンした
- `~/firecrawl/.env` を新規作成した（`.env.example` はリポジトリルート直下には存在しないため、SELF_HOST.md記載のテンプレートから書き起こした）
- `.env` の必須項目: `PORT=3002`, `HOST=0.0.0.0`, `USE_DB_AUTHENTICATION=false`, `BULL_AUTH_KEY`（openssl rand で生成した値に置換）
- PostgreSQL関連の環境変数（`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`）はdocker-compose.yamlのデフォルト値（すべて `postgres`）に任せる方針とした
- `docker compose up -d --build` により5系統以上のコンテナ（api / playwright-service / redis / rabbitmq / nuq-postgres / foundationdb / foundationdb-init）を起動した

#### 運用上の注意事項

- `POSTGRES_DB` を `postgres` 以外に変更すると、初期化SQL（`010-nuq.sql`）内の `pg_cron` 拡張作成が失敗し、`nuq-postgres` コンテナが起動しなくなる。`pg_cron` は `cron.database_name` で指定されたDBでのみ拡張作成が許可される仕様のため、デフォルト値を変更しない
- `nuq-postgres` は永続ボリュームを持たない構成のため、コンテナ削除時にデータも消える。長期運用でデータ保全が必要になった時点で `docker-compose.yaml` にボリューム設定を追加する検討が必要
- Firecrawlの `/search` API はデフォルトでGoogle検索を利用する。SearXNGを併用する場合は `SEARXNG_ENDPOINT` を追加設定する（現時点では併用しない）

#### Hermes側の接続設定

- `~/.hermes/.env` に `FIRECRAWL_API_URL=http://localhost:3002` を追記した
- Hermesを再起動し、`hermes tools` でWeb Search & Extractプロバイダーとして「Firecrawl Self-Hosted」を選択・有効化した
- APIキーは未設定（`USE_DB_AUTHENTICATION=false` のため不要）

### 5.9 Hermesツールセットの構成確定

`hermes tools` で確認できる現時点の有効化状況は以下のとおり。

有効化されているコアツールセット:

- browser
- clarify
- code_execution
- computer_use
- context_engine
- cronjob
- delegation
- file
- image_gen
- kanban
- memory
- session_search
- skills
- terminal
- todo
- tts
- vision
- web

上記の組み合わせは、Hermesのplatform toolset `hermes-cli`（インタラクティブCLIセッションのデフォルトフル装備）とほぼ一致する。CLIから使う限り、追加でONにすべきツールセットは現時点で存在しない。

未有効化のうち、将来的に有効化する可能性のあるもの:

- `x_search`: X（旧Twitter）の投稿・スレッド検索。xAI APIキー（新規登録で$25クレジット、データ共有プログラム経由で月$175まで無料枠）を取得次第、有効化を検討する
- `hermes-telegram` などの platform toolset: `hermes gateway setup` でメッセージングプラットフォームを追加した際に自動的に選択される。手動で有効化するものではない

未有効化で当面不要と判断したもの:

- 他プラットフォーム系（discord, spotify, feishu_*, yuanbao, homeassistant 等）: PDA計画上の利用予定なし
- video, video_gen: 現時点で用途なし
- project: GUI専用のため、サーバー用途では利用不能

composite toolset（`coding`, `debugging`, `safe`）については、構成メンバーがすべて既に個別で有効化されているため、追加でONにする実益はない。

### 5.10 未セットアップの外部連携ツール

`hermes tools` の一覧上、以下は認証情報未設定のためチェックが外れた状態のまま残している。優先度に応じて後から埋める。

- Vision（画像解析）: `hermes setup` の実行が必要
- Image Generation: FAL.ai APIキー（`FAL_KEY`）が必要。PDA用途で頻繁に画像生成する予定がなければ後回し
- Skills Hub（GitHub）: GitHub API のレート制限緩和用の `GITHUB_TOKEN`（Fine-grained token、public read のみで十分）

### 5.11 拡張パッケージの導入（Web拡張・音声認識準備・Firecrawlクライアント等）

Hermesの標準インストールにはWeb Dashboardや各種プラグイン用の追加パッケージが含まれない。以下を実行してまとめて導入した。

- uvパッケージマネージャーの導入（`curl -LsSf https://astral.sh/uv/install.sh | sh`。標準インストーラーでは`~/.local/bin/uv`に配置され、PATHは自動追加される）
- Hermes同梱venvを利用: `source ~/.hermes/hermes-agent/venv/bin/activate` （venvは`.venv`ではなく`venv`という名前で `~/.hermes/hermes-agent/venv/` に配置されている）
- 拡張インストール: `uv pip install -e ".[all,firecrawl]"`

`all` にはWeb Dashboardに必要な`web`（FastAPI/Uvicorn）、`pty`、`mcp`、`google`（Google Workspace）、`youtube`、`cron`、`cli`、`acp`、`homeassistant`、`sms` が含まれる。`firecrawl` は明示的に追加した。音声入力（`voice`）はスマホの音声認識をワークフロー的に用いる方針のため、この段階では入れていない。

### 5.12 Web Dashboardの認証設定とLAN公開

Web Dashboardをスマホから利用するため、Basic認証を設定した上でLAN内公開に切り替えた。

- 認証情報の生成: `openssl rand -base64 24`（パスワード）と `openssl rand -base64 32`（セッション署名シークレット）
- `~/.hermes/.env` に追記:
  - `HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin`
  - `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<生成値>`
  - `HERMES_DASHBOARD_BASIC_AUTH_SECRET=<生成値>`
- 手動起動テスト: `hermes dashboard --host 0.0.0.0 --port 9119 --no-open`
- スマホからのアクセス確認: 同一Wi-Fi上のスマホブラウザから `http://<ミニPCのLAN IP>:9119` に接続し、Basic認証を通過してDashboardが表示されることを確認

重要な設計上の注意事項:

- Web Dashboardは認証プロバイダー未設定の状態でnon-loopbackアドレスにバインドしようとすると起動時にfail closeする（公式仕様）。したがってBasic認証の環境変数設定は「あった方がよい」ではなく起動要件
- Basic認証はブルートフォース保護を持たないため、LAN内またはVPN内での利用に限定する。インターネットへの直接公開は禁忌

### 5.13 Web Dashboardの常駐化（systemd user service）

Web Dashboardを手動起動から常駐化に切り替えた。

- systemd user unit 作成: `~/.config/systemd/user/hermes-dashboard.service`
  - `ExecStart=<hermes絶対パス> dashboard --host 0.0.0.0 --port 9119 --no-open`
  - `EnvironmentFile=%h/.hermes/.env`
  - `Restart=on-failure`, `RestartSec=10`
  - `WantedBy=default.target`
- 有効化: `systemctl --user daemon-reload && systemctl --user enable hermes-dashboard && systemctl --user start hermes-dashboard`
- linger有効化: `sudo loginctl enable-linger $USER`（SSHログアウト後もサービスが動き続け、かつミニPC再起動後も自動起動する要件を満たす）

SSHセッションを切断してもDashboardがスマホから閲覧可能であることを確認した。

### 5.14 Hermes Gatewayの常駐化

`hermes gateway install` を実行し、対話プロンプトで「auto-start on boot with systemd」に `Y` と回答した。

- `~/.config/systemd/user/hermes-gateway.service` が自動生成される
- lingerは既に5.13で有効化済みのため、ここでは既存の設定が引き継がれる
- Web Dashboard の Status ページで Gateway が `running` として表示されることを確認した

Gatewayの担当範囲はメッセージング系（Telegram/Slack/Discord等）に限らず、cronジョブスケジューラ・Webhook受信・セッション管理・音声メッセージ配信も含む。メッセージングプラットフォームを未接続でも、cronやWebhookを利用する将来のフェーズ4作業のためにGateway自体は常駐化しておく判断とした。

### 5.15 開発用PCからミニPCへのSSH鍵認証

Claude CodeからHermes MCPへ非対話接続するため、開発用PC（macOS）からミニPCへのSSHをパスフレーズ不要な状態にした。

- 既存のSSH公開鍵をミニPCの `~/.ssh/authorized_keys` に登録した
- 開発用PCの `~/.ssh/config` にホストエイリアス `agent-node` を定義した（`HostName`, `User`, `IdentityFile`, `ServerAliveInterval` 等）
- 疎通確認: `ssh agent-node echo ok` がパスフレーズ入力なしで即座に応答することを確認した

### 5.16 Claude CodeとHermesのMCP接続（片方向）

Hermesの `hermes mcp serve` は現行実装ではstdio専用（HTTPリスナー無し・認証機構無し）のため、直接ネットワーク越しの接続ができない。SSHをstdioラッパーとして用いる構成で片方向の接続を確立した。

- 開発用PC側で以下を実行: `claude mcp add --scope user hermes -- ssh agent-node <hermes絶対パス> mcp serve`
- SSH経由の非対話シェルでは `.bashrc` のPATHが解決されないため、hermesは絶対パスで指定する必要がある（`~/.hermes/hermes-agent/venv/bin/hermes`）
- Claude Codeを再起動して `/mcp` で確認し、`hermes` サーバーが `connected` 状態になっていることを確認した
- 動作確認として `mcp__hermes__conversations_list` を呼び出し、正常なJSONレスポンス（`count: 0, conversations: []`）を取得した

接続されたHermes MCPが公開するツール（10個）:

- `conversations_list`, `conversation_get`, `messages_read`, `attachments_fetch`
- `events_poll`, `events_wait`
- `messages_send`
- `channels_list`
- `permissions_list_open`, `permissions_respond`

これらはHermesのmessaging bridgeとして動作する構成で公開されている。会話が0件なのは、Telegram等のmessaging platformをまだHermes gatewayに接続していないため。

**制約と設計上の注意事項**:

- `hermes mcp serve` のstdio専用実装のため、SSHセッションが切れると MCP セッションも切れる。Claude Code側で再接続処理が必要になる可能性がある
- 逆方向（Hermes → Claude Code）はこの経路では動かない。Hermes側の `claude-code` スキルを別途セットアップして `claude -p '指示' --max-turns N` でCLIラップする必要がある
- Team plan であっても、user scope（`~/.claude.json`）に登録したMCPサーバーは組織管理者ポリシーの明示的なブロックがない限り動作する

---

## 6. Hermes運用上の設計判断

### 6.1 スマホ・macOS CLI・Claude Code MCPの3経路について

PDAへのアクセス経路として、以下の3つが計画されている。それぞれ利用する仕組みが異なる。

- スマホからのアクセス: Web Dashboard（`hermes dashboard --host 0.0.0.0`）を主軸とする方針。LAN内はそのまま到達可能。外出先からのアクセスは、ポート開放ではなくTailscale等のオーバーレイVPNを後段で追加する
- Telegram: 通知チャネル（PDA側から能動的にプッシュ可能）として位置付ける。Web Dashboardのpull型を補完する
- macOS CLI: 現行のSSH経由でミニPC上の `hermes chat` を叩く経路を継続利用する
- Claude Code MCP: 直接HTTP接続はできない（`hermes mcp serve` はstdio専用）ため、`claude mcp add --scope user hermes -- ssh agent-node <hermes絶対パス> mcp serve` の形でSSHをstdioラッパーとして用いる構成を採用した。認証はSSH鍵で、暗号化もSSHが担う

現時点で動作している経路: macOS CLI（SSH越しの `hermes` 直接実行）、Web Dashboard（LAN経由、スマホ含む）、Claude Code MCP（片方向：Claude Code → Hermes）。逆方向（Hermes → Claude Code）は未実装。

### 6.2 コンテキスト圧縮エンジンについて

`context_engine` は `hermes tools` 上でチェックを入れることで有効化した。デフォルトの組み込みエンジン `compressor` が使われる。将来的に別方式（LCM等のプラグイン）を試したくなった時点で `config.yaml` の `context.engine` を書き換える。

---

## 7. 未実施・次工程

### 7.1 HermesからClaude Codeへの逆方向連携（双方向化）

現状はClaude Code → Hermesの片方向のみ確立している。逆方向を追加して双方向連携を成立させる。

- Hermes側の `claude-code` スキル（バンドル済み）を有効化する
- `claude` CLI（Claude Code）を開発用PC側ではなくミニPC側にも導入する、あるいは開発用PC上のClaude Codeを何らかの経路でHermesから叩けるようにする
- 実行モードとしては非対話印刷モード（`claude -p 'タスク説明' --max-turns N`）が推奨される（tmux経由の対話モードよりオーケストレーションが単純）
- 動作確認: Hermesにコード変更タスクを依頼し、それがClaude Code経由で実行され、結果がHermesに戻ることを確認する

### 7.2 スマホアクセスの外出先対応

現状はLAN内限定。外出先からもWeb Dashboardを利用できるようにする。

- Tailscale等のオーバーレイVPNをミニPCと利用端末（スマホ・開発用PC）に導入する
- ポート開放は行わない方針を継続する

### 7.3 メインモデルのClaude移行

- Anthropicアカウント準備完了後、`hermes model` で `anthropic-claude` に切り替える
- Codexは補助モデルとして残すか、切り替え動作の検証用途に留めるかを判断する

### 7.4 情報取り込み基盤の整備（フェーズ4開始）

PDA計画書のフェーズ4に相当する作業。以下の情報源からHermesへの取り込み経路を順次確立する。

- ChatGPT / Claude / Codex / Hermes 自身の会話・実行履歴
- ブラウザ履歴とWeb閲覧情報
- Slack（業務コミュニケーション）
- Backlog（プロジェクト管理）
- Git（開発履歴）

### 7.5 PKB／コンテキストグラフの成立（フェーズ5準備）

情報取り込みが一定量進んだ段階で、PKB／グラフネットワークの設計に着手する。Firecrawlによる本文取得はこの段階で本格利用される。

---

## 8. 初期構築完了の定義

以下をもって「PDAミニPC初期構築完了」とみなす。この時点までがフェーズ1「常時稼働基盤の構築」の到達内容であり、加えてフェーズ2（Hermesを中核とした最小PDA）およびフェーズ3（複数エージェントランタイム統合）の片方向連携までを達成した状態。

**フェーズ1 相当の到達内容**:

- Ubuntu Serverが常時稼働可能な状態にある
- 開発用PCからSSH経由で管理できる（鍵認証、パスフレーズ不要）
- Hermesが導入されており、モデルプロバイダー（Codex）で対話・ツール実行ができる
- Hermesが実行可能なツールとして、ファイル操作、ターミナル、ブラウザ、Web検索・本文取得（Firecrawl経由）、記憶、スキル管理、視覚解析等を持つ
- 外部Web情報を自前スタック（Firecrawl Self-Hosted）で取得可能な状態にある
- Hermes本体・Web Dashboard・GatewayがすべてsystemdによりミニPC再起動後も自動起動する

**フェーズ2 相当の到達内容**:

- Web Dashboardがスマホブラウザから閲覧可能（LAN内、Basic認証）
- Web Dashboard上でGatewayステータス、セッション、cron、ログ、設定を管理できる
- Hermesが対話、タスク受付、ツール実行を単独で完結できる

**フェーズ3 相当の到達内容（片方向）**:

- 開発用PC上のClaude CodeがMCP経由でHermesを呼び出せる（SSH越しのstdio wrapper構成）
- Hermes MCPが公開する10ツール（`conversations_list`, `messages_send` 等）を Claude Code側から利用可能
- 逆方向（Hermes → Claude Code）は未実装で、7.1で対応する

以降は「7. 未実施・次工程」の項目実装と、PDA計画書のフェーズ3完成（双方向化）・フェーズ4（情報取り込み）への移行となる。

上記はすべて満たされている。以降は「7. 未実施・次工程」に記載した項目の実装と、PDA計画書のフェーズ2以降への移行となる。
