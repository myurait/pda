# PDAミニPC セットアップ検討・実行記録

- 更新日: 2026-08-17
- 対象プロジェクト: Personal Delegate Agent（PDA）
- 対象機器: GMKtec M8（AMD Ryzen 5 PRO 6650H / 16GB LPDDR5 / 512GB SSD）
- 現在地点: Hermes・Firecrawl・Web Dashboard・Gatewayをすべて常時稼働化。主UIはOpen WebUI v0.11.0。Tailscale Serveによるtailnet限定HTTPS導線を追加し、Windows・開発PC・iPhoneからの利用を確認済み。Open WebUIユーザーチャットの最終応答完了だけを識別し、チャットタイトル・回答冒頭・対象チャット直リンクをiPhoneへ送るntfy push経路を構築・検証済み。Claude CodeとHermesの双方向連携まで完了し、Hermes中核推論エンジンはCodex据え置きの方針で確定。
- 次工程: PKB取り込み系の整備

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

### 5.17 Open WebUIによる主UIの差し替え

Hermes標準のWeb Dashboardはチャットタブがxterm.js（Canvas/WebGL描画）で実装されており、macOSブラウザからのコピーペーストとiOS Safariでのテキスト選択が構造的に不可であることが判明した。Markdownレンダリングも十分でなく、長文の応答や設計書レベルの出力を扱う用途には向かない。この課題を解消するため、Hermesが標準で持つOpenAI互換HTTP APIサーバーの前段にOpen WebUIを立て、これを主UIとする構成に変更した。

**Hermes APIサーバーの有効化**:

- `~/.hermes/.env` に以下を追記した:
  - `API_SERVER_ENABLED=true`
  - `API_SERVER_HOST=0.0.0.0`
  - `API_SERVER_PORT=8642`
  - `API_SERVER_KEY=<openssl rand -hex 32 で生成した値>`
- `systemctl --user restart hermes-gateway.service` で反映
- 動作確認: `curl -H "Authorization: Bearer <KEY>" http://localhost:8642/v1/models` が `hermes-agent` を返すことを確認した
- 公開されるエンドポイント: `/v1/chat/completions`（SSEストリーミング対応）、`/v1/responses`、`/v1/runs`、`/v1/models` 等のOpenAI互換API

**Open WebUIのDocker Compose設置**:

- `~/openwebui/` にDocker Compose構成を配置（現在のimage: `ghcr.io/open-webui/open-webui:v0.11.0`）
- ホスト側ポート: `127.0.0.1:9120`。Tailscale Serveのバックエンドと同一ホスト上の保守アクセスだけに使用し、LANには直接公開しない
- APIキー等の秘密情報は `~/openwebui/.env`（`chmod 600`）に分離し、`docker-compose.yml` からは `${HERMES_API_KEY}` として参照
- 設定内容:
  - `WEBUI_AUTH=true`（Open WebUI内蔵の認証を使用）
  - `ENABLE_SIGNUP=false`（初回admin作成後は追加サインアップを禁止）
  - `DEFAULT_LOCALE=ja`
  - `OPENAI_API_BASE_URLS=http://host.docker.internal:8642/v1`
  - `OPENAI_API_KEYS=<Hermes API server key>`
  - `ENABLE_OLLAMA_API=false`
  - `extra_hosts: - "host.docker.internal:host-gateway"`（Linux上でコンテナからホストへ到達させるため）
- 初回起動時にsentence-transformersの埋め込みモデル（all-MiniLM-L6-v2、約90MB）をHugging Faceからダウンロードするためhealthcheck通過まで2〜3分かかる

**Open WebUIの常駐化**:

- Docker Composeの `restart: unless-stopped` と、system Dockerサービスの自動起動を正規の常駐経路とする
- 旧 `~/.config/systemd/user/openwebui.service` は、一般ユーザーがDockerソケットへ接続できず、存在しないuser-level `docker.service` に依存する無効な二重管理だったため、2026-08-17に無効化・削除した

**動作確認**:

- LAN経由でスマホから `http://192.168.0.59:9120` へアクセスし、日本語UIが表示されること・初回admin作成が完了すること・Hermesモデルが選択できることをユーザー側で確認した
- Markdownレンダリング・コードブロック・テキスト選択・コピーペーストがiOSとmacOSブラウザ双方で正常に動作することを確認

**役割の再定義**:

- **Open WebUI（主UI・新規）**: 会話・タスク委任・長文レスポンス閲覧。iOS/macOSブラウザから利用
- **Hermes Web Dashboard（副UI・既存維持）**: Gateway稼働状況・セッション一覧の監視用途に限定
- **CLI over SSH（macOS）**: 詳細設定・デバッグ・ログ確認
- **Claude Code MCP（開発PC）**: コードタスクとHermes会話履歴の読み取り

### 5.18 HermesからClaude Codeへの逆方向連携（双方向化の完了）

Claude Code → HermesのMCP経路（片方向）は5.16で確立済みだが、逆方向（Hermes → Claude Code）については別途Hermesの `claude-code` バンドルスキルを経由する必要がある。個人契約のClaude Pro/Maxプランで認証したCLIをミニPC側に導入し、逆方向連携を成立させた。

**アカウント分離の設計**:

- 開発用PC上のClaude Code: 会社発行Team plan。会社の開発業務・会社発行MCP（Datadog等）用
- ミニPC上のClaude Code: 個人契約Pro or Maxプラン。プライベート開発・私生活情報処理用
- 認証情報の境界を維持することを設計原則とし、Team planのOAuthトークンをミニPC側に置く選択肢は棄却した

**Node.jsランタイム**:

- Hermes自体がNode 22（`~/.hermes/node/bin/node`、`~/.local/bin/node` にsymlink）を既に含んでいたためこれを流用
- 将来の切り替え余地として `nvm` も導入済み（Node 24 LTSがインストール済み・未アクティブ）

**Claude Code CLIの導入**:

- ネイティブインストーラで `~/.local/share/claude/versions/2.1.205` に導入、`~/.local/bin/claude` にsymlink
- `claude --version` で `2.1.205 (Claude Code)` を確認

**OAuthトークンによる認証**:

- ユーザーがミニPC上で `claude setup-token` を実行し、個人アカウントでログイン済みブラウザから認可を行うことで1年有効な長期OAuthトークンを発行
- トークンは `~/.hermes/.env` の `CLAUDE_CODE_OAUTH_TOKEN` に格納（ファイル権限 `chmod 600`）
- 会社アカウントのブラウザセッションで誤って認可しないよう、個人アカウント専用のブラウザ・プライベートウィンドウ・スマホブラウザ等を使い分ける運用とする

**Hermes側スキルの状態確認**:

- `hermes skills list` で `claude-code` が `enabled` かつ `builtin` であることを確認
- 追加のopt-in操作は不要（バンドルスキルとしてデフォルト有効）
- スキルは `skills-sh/nousresearch/hermes-agent/claude-code` v2.2.0 を使用

**hermes-gateway再起動と動作確認**:

- `systemctl --user restart hermes-gateway.service` で環境変数を反映
- 動作確認: OpenAI互換エンドポイント `/v1/chat/completions` に対して、Hermesに `claude-code` スキル経由で `/tmp/pda_reverse_test.txt` にテキスト書き込みを依頼
- 結果: ファイルが指定通り27バイトで作成され、Hermesからは「Claude Code CLI経由で確認済み」の応答が返った
- これにより Hermes → claude CLI（個人プラン認証）→ ローカル実行 → Hermesへの結果返却 のパスが動作していることを確認

**制約・注意事項**:

- OAuthトークンは1年後に失効するため、再発行運用が必要
- claude CLIが実行するタスクはミニPCのユーザー権限で動作するため、Hermesが誤った指示を出した場合の影響範囲を意識する必要がある
- `claude -p` の非対話モードで動くため、対話が必要なプロンプト（Workspace Trust承認等）はスキルの実装側で処理されている前提

### 5.19 Tailscale Serveによる外出先アクセス

Open WebUIをインターネットへ直接公開せず、個人tailnetへ参加している端末からだけHTTPSで利用できる導線を追加した。Tailscale Personalプランの無料範囲で運用する。

**構成**:

- Tailscale v1.102.2の公式static buildを `~/.local/opt/tailscale-1.102.2/` に配置
- root権限を要求しないuserspace networkingモードで `tailscaled` を起動し、`~/.config/systemd/user/tailscale-pda.service` で常駐化
- ノード名: `pda-web`
- HTTPS URL: `https://pda-web.tailaff53a.ts.net`
- Tailscale Serve: `/` を `http://127.0.0.1:9120` へリバースプロキシ
- 公開範囲は `tailnet only`。Tailscale Funnelは無効で、ルーターのポート開放も行わない
- Tailscale SSH、Web管理UI、Exit Node、subnet routeは有効化しない
- Open WebUI内蔵認証 (`WEBUI_AUTH=true`) と新規登録禁止 (`ENABLE_SIGNUP=false`) は維持する
- userspace networkingのためホストに `tailscale0` を作らず、tailnet側へ明示的に公開される入口はServeのTCP 443だけとする

**永続化・確認**:

- `tailscale-pda.service` はenabled、user lingerもenabled
- Tailscaleの状態・証明書・Serve設定は `~/.local/share/tailscale-pda/` に永続化
- `tailscale-pda.service` を実際に再起動し、ノードが再接続すること、Serve設定が保持されること、Open WebUI `/health` が正常なことを2026-08-17に確認
- Windowsマシン、開発PC、iPhoneからHTTPS URLへの疎通とOpen WebUI表示をユーザー側で確認
- ホスト自身からは `http://127.0.0.1:9120` を保守導線として利用可能。旧LAN導線 `http://192.168.0.59:9120` は意図的に遮断

**運用確認コマンド**:

```bash
systemctl --user status tailscale-pda.service
"$HOME/.local/opt/tailscale-1.102.2/tailscale" \
  --socket="$HOME/.local/share/tailscale-pda/tailscaled.sock" status
"$HOME/.local/opt/tailscale-1.102.2/tailscale" \
  --socket="$HOME/.local/share/tailscale-pda/tailscaled.sock" serve status
curl -fsS http://127.0.0.1:9120/health
```

導入試行中に作成した旧Docker版TailscaleのCompose・state（旧ノード `pda-node`）と、未適用のpolicy案は、現行構成への誤切替と旧machine key残置を防ぐため削除した。

### 5.20 Open WebUIユーザーチャット完了時のiPhone push

長時間のHermes実行中にOpen WebUIを閉じても完了を把握できるよう、無料のホスト版ntfy (`https://ntfy.sh`) と公式iOSアプリを用いるpush経路を追加した。汎用的なHermes hookではなくOpen WebUIのHermes Progress Pipeに実装し、対話ターンと非同期エージェントを入口で分離する。

**実行元の識別**:

- Open WebUIの対話ターンはPipeが `owui_[0-9a-f]{32}` 形式のHermes session IDを生成する
- 直接のRuns API、cron、CLI、バックグラウンド実行、live probeはこのsession ID形式を持たない
- delegated subagentはHermes上で `platform=subagent` として動き、Open WebUIのPipe自体を通らない
- push条件を「Pipe経由」「正規の `owui_` session ID」「Open WebUIで保存済みassistant応答が `done=true`」の積にした。したがって親チャット内で非同期subagentが完了しても重複pushせず、ユーザーに返す親応答の完了時だけ1件送る

**完了タイミングと通知内容**:

- 実装バージョン: `hermes_progress_pipe` v2.1.0-local.12
- Open WebUIへ最終content chunkと `data: [DONE]` を渡した後、async generatorのclose/finalize経路からntfy送信をscheduleし、通知タスクをPipe instanceが完了まで強参照する
- Pipe開始時のOpen WebUI host taskの終了を待ってからDBを読み、host taskのsuccess・failure・cancelではなく、所有者本人の保存済みassistant messageが `done=true` かつ本文が非空かを通知条件にする。outlet filterによるredactionを前提にする場合は、filter失敗時の保存内容も通知され得るため外部pushを無効化する
- 通知前にOpen WebUI DB上の所有者スコープ付きassistant messageをpollし、`done=true` を確認する。通知タイトル・本文は保存済みchat/messageから取得し、Hermes terminal outputやユーザー入力で代用しない
- 通知タイトルはOpen WebUIの保存済みチャットタイトル（最大100文字）。自動タイトルを最大約20秒待ち、未確定なら実際の `New Chat` を使う
- 通知本文はOpen WebUIに保存された最終回答の冒頭（最大240文字）。reasoning/tool traceを除外し、制御文字と連続空白を正規化し、超過時は `…` で省略する。保存済み回答が空なら固定文へ差し替えず通知しない
- 旧 `✅ PDA` 固定表示の原因だったntfy emoji tagは削除した
- 通知タップ先は対象チャット直リンク `https://pda-web.tailaff53a.ts.net/c/<chat_id>`。Funnelやインターネット公開は追加していない
- success、failure、cancel、timeoutを通知種別として区別せず、Open WebUIに保存されたユーザー向け完了応答が空でない場合はその表示内容を通知する
- ストリーミングと非ストリーミングの両経路を対象とする
- Open WebUI内部呼び出しと `title_generation`、`tags_generation`、`follow_up_generation` taskは通知対象外
- 保存済みchat IDの所有者を認証user IDで照合し、installer実行管理者のuser IDに通知権限を限定する。chat未保存、所有者不一致、認証user ID欠落時は通知しない
- Open WebUI frontend由来のsession ID・assistant message ID・event emitterを必須にし、既存chat IDだけを付けた直接API呼び出しを除外する。同一assistant message IDへの送信試行はFunction process内で最大1回に抑止する。これはadvisoryなat-most-once attemptであり、プロセス停止をまたぐdurable exactly-once配送ではない

**設定と秘密管理**:

- `PDA_NTFY_SERVER_URL`、`PDA_NTFY_TOPIC`、`PDA_OPENWEBUI_PUBLIC_URL` をmode 0600の `~/openwebui/.env` に保存
- ntfy topicはtopic名自体がpasswordとなるため、192-bit乱数の52文字topicを生成した。実値はGitと本記録へ保存しない
- installerは更新前のsource・metadata・active state・Valvesを退避し、失敗時は全項目を復元する。新規作成rollbackではinstall transaction固有nonceとsourceが一致するFunctionだけを削除し、競合処理が作成・更新したFunctionを巻き込まない。成功時はFunction source v2.1.0-local.12・active・全ValvesをAPIから再読込して一致を確認する。rollback時も復元後のsource・metadata・active state・全Valvesを再読込し、不一致を成功扱いにしない
- ユーザー要望により、ホスト版ntfy.shへチャットタイトルと回答冒頭を送る。これらはntfy.sh側のmessage cacheとiPhone通知履歴へ残り得る。機密会話で使わないこと。外部保持を避ける場合は `NTFY_TOPIC` を空にするか、将来ntfyをtailnet内へself-hostする

**検証結果（2026-08-17）**:

- 単体・ローカル統合テスト: 71件すべて成功
- 長時間runでは `PROGRESS_HEARTBEAT_SECONDS=900` を既定とし、15分ごとに経過時間・安全な実行中ツール名・完了件数・一般化した直近活動をOpen WebUI `statusHistory`へ保存する。`0`で無効化できる
- heartbeatはrun単位で状態と送信lockを分離し、内部taskでは無効化する。terminal・例外・取消・stream close時に同期停止し、推論本文、tool引数・preview・結果、ユーザー入力、未知tool名を保存しない
- 実Open WebUI API → Progress Pipe → Hermes Runs API: 最終応答 `OWUI_PUSH_PREVIEW_OK` 後、チャットタイトル、回答冒頭、対象チャット直リンクを持ちemoji tagを持たないpushが1件だけ発生。期待通知の検出後も2秒間pollし、余分な通知0件を確認
- 上記E2Eで詳細progressを3件保存し、開始statusと完了statusの双方を確認
- 通知先のテストチャットがOpen WebUI上に存在し、タイトルと回答本文を保持していること、ローカルの `/c/<chat_id>` がHTTP 200を返すことを確認
- 実Hermes直接Runs API: `ASYNC_NO_PUSH_OK` で正常完了し、新規pushは0件
- 実稼働Function source、デプロイファイル、Git保存版のSHA-256が一致
- 再現可能なFunction、installer、単体テスト、live probeを `integrations/openwebui-hermes-progress/` に保存した

**モデル経路**:

- Open WebUIのglobal `DEFAULT_MODELS` と管理者の `ui.models` を `hermes_progress_pipe` に統一した。新規チャットは詳細status対応の `Hermes Agent (Progress)` を既定で使う
- 既存33チャットもtop-level `models` を `hermes_progress_pipe` へ統一した。旧 `hermes-agent` 直結経路では詳細statusが保存されず、汎用の `progress` 表示だけになるため。変更前の全chat exportはmode 0600でローカルバックアップ済み

iPhone側では公式ntfyアプリをインストールし、通知を許可してprivate topicを購読する。topicは秘密値であるため、本記録や公開Gitには記載しない。

---

## 6. Hermes運用上の設計判断

### 6.1 スマホ・macOS CLI・Claude Code MCPの3経路について

PDAへのアクセス経路として、以下を併用する。それぞれ利用する仕組みが異なる。

- スマホ・ブラウザからのアクセス: Tailscale接続後、`https://pda-web.tailaff53a.ts.net` のOpen WebUIを主UIとして利用する。Funnelとポート開放は使わない
- ntfy: Open WebUIユーザーチャットの保存済み応答完了を、チャットタイトル・回答冒頭・直リンク付きでiPhoneへ送る専用pushチャネル。非同期エージェントは対象外
- Telegram: 将来の汎用通知・双方向メッセージングチャネル候補。現時点のチャット完了通知には使用しない
- macOS CLI: 現行のSSH経由でミニPC上の `hermes chat` を叩く経路を継続利用する
- Claude Code MCP: 直接HTTP接続はできない（`hermes mcp serve` はstdio専用）ため、`claude mcp add --scope user hermes -- ssh agent-node <hermes絶対パス> mcp serve` の形でSSHをstdioラッパーとして用いる構成を採用した。認証はSSH鍵で、暗号化もSSHが担う

現時点で動作している経路: macOS CLI（SSH越しの `hermes` 直接実行）、Open WebUI（Tailscale Serve経由でWindows・開発PC・iPhoneから利用）、ntfy（Open WebUI保存済み応答完了時のタイトル・回答冒頭・直リンク付きpush）、Hermes Dashboard（監視用途）、Claude Code MCP（双方向：Claude Code → Hermes はSSH stdio、Hermes → Claude Code はミニPC上のclaude CLIをバンドルスキルで呼び出し）。

### 6.2 コンテキスト圧縮エンジンについて

`context_engine` は `hermes tools` 上でチェックを入れることで有効化した。デフォルトの組み込みエンジン `compressor` が使われる。将来的に別方式（LCM等のプラグイン）を試したくなった時点で `config.yaml` の `context.engine` を書き換える。

### 6.3 Hermes中核推論エンジンの選定（Codex据え置き）

Hermes自体がタスクを判断・分解する際に用いる推論エンジンについて、以下の理由でCodex据え置きとする方針を確定した。

**背景**:

計画初期には「個人契約のClaude Pro/Maxプランを用いて、HermesのメインモデルをClaudeに切り替える」という案があった。しかし詳細調査の結果、以下の制約が判明した。

- Hermesの `anthropic` プロバイダ（alias: `claude` / `claude-code`）は3経路のいずれかで認証する必要がある: (1) `ANTHROPIC_API_KEY` による従量課金、(2) Anthropic OAuth（Max plan + 追加extra credits必須、Pro plan不可）、(3) `~/.claude/.credentials.json` からのauto-detect（実装バグ既知）
- **個人契約のPro/Maxサブスクリプション代金だけでは、Hermesの中核推論として常用することはできない**。いずれの経路でも別途API課金が必須
- サードパーティ経由でClaude Code OAuthトークン（`CLAUDE_CODE_OAUTH_TOKEN`）を推論APIとして流用する経路は、2026-04-04にAnthropic側で遮断済み。仮に動作してもMax割当ではなくextra_usageプールに課金される
- Sonnet 4.5の従量単価はどの経路でも同水準（1M input $3 / output $15）

**決定**:

- Hermesの中核推論エンジンは引き続き `openai-codex`（ChatGPT Plus/Pro subscription経由OAuth）を使用する
- 個人契約のClaude Pro/Maxサブスクリプションは、Hermes → Claude Code逆方向連携（5.18）を通じてコード関連の重い委任タスク実行に利用することで、subscription代金分の価値を回収する
- Hermes中核をClaudeに切り替えるオプションは、明確な必要性と追加課金の許容が揃った時点で再検討する

**教訓（プロジェクト固有の記録として）**:

有料プランの契約前に、想定用途全体をそのプランでカバーできるかを一次情報（公式pricing・providers doc・ToS）で検証すべきだった。目の前のサブタスク（今回はClaude Code CLI認証）だけで判断せず、セッション全体・計画書レベルの目的（Hermes中核化）にも接続して検証すべきだった。

---

## 7. 次工程

### 7.1 情報取り込み基盤の整備（フェーズ4開始）

PDA計画書のフェーズ4に相当する作業。以下の情報源からHermesへの取り込み経路を順次確立する。

- ChatGPT / Claude / Codex / Hermes 自身の会話・実行履歴
- ブラウザ履歴とWeb閲覧情報
- Slack（業務コミュニケーション）
- Backlog（プロジェクト管理）
- Git（開発履歴）

### 7.2 PKB／コンテキストグラフの成立（フェーズ5準備）

情報取り込みが一定量進んだ段階で、PKB／グラフネットワークの設計に着手する。Firecrawlによる本文取得はこの段階で本格利用される。

---

## 8. 初期構築完了の定義

以下をもって「PDAミニPC初期構築完了」とみなす。この時点までがフェーズ1「常時稼働基盤の構築」の到達内容であり、加えてフェーズ2（Hermesを中核とした最小PDA）およびフェーズ3（複数エージェントランタイム統合）の双方向連携までを達成した状態。

**フェーズ1 相当の到達内容**:

- Ubuntu Serverが常時稼働可能な状態にある
- 開発用PCからSSH経由で管理できる（鍵認証、パスフレーズ不要）
- Hermesが導入されており、モデルプロバイダー（Codex）で対話・ツール実行ができる
- Hermesが実行可能なツールとして、ファイル操作、ターミナル、ブラウザ、Web検索・本文取得（Firecrawl経由）、記憶、スキル管理、視覚解析等を持つ
- 外部Web情報を自前スタック（Firecrawl Self-Hosted）で取得可能な状態にある
- Hermes本体・Web Dashboard・Gateway・Open WebUIがすべてsystemd/Docker restart policyによりミニPC再起動後も自動起動する

**フェーズ2 相当の到達内容**:

- Open WebUIがTailscale Serve経由でWindows・開発PC・iPhoneから利用可能（tailnet限定HTTPS、Markdownレンダリング・コピペ・テキスト選択すべて正常動作）
- Hermes Web DashboardがGatewayステータス・セッション・cron・ログ・設定の監視用途で利用可能
- Hermesが対話、タスク受付、ツール実行を単独で完結できる

**フェーズ3 相当の到達内容（双方向）**:

- 開発用PC上のClaude Code（会社Team plan）→ Hermes: MCP経由（SSH越しのstdio wrapper構成）で `conversations_list`, `messages_send` 等の10ツールが利用可能
- Hermes → ミニPC上のClaude Code（個人プラン）: バンドルスキル `claude-code` 経由で `claude -p` を呼び出し、コードタスクをローカル実行して結果を返す
- 認証情報の境界を維持（会社と個人のAnthropicアカウントを別マシンに分離）

以降は「7. 次工程」の項目実装と、PDA計画書のフェーズ4（情報取り込み）・フェーズ5（PKB）への移行となる。
