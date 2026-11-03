# 先行事例の調査 (Claude の上のパーソナルエージェント)

- 更新: 2026-11-03 JST
- 種別: 調査記録。[README](README.md) の「決まっていないこと」の 1 つ目 (入口になる常駐のセッションと、そこからのセッションの spawn を、どの部品で作るか) の材料。
- 前提: Claude の公式の機能と、v0.3 の OSS の母集団から拾った製品は [入口と spawn の調査](research-entry-and-spawn.md) にある。本調査は、実践者が自分のために組んだ構成を、記事・投稿・発表と、そこから辿れるリポジトリから集める。同じ調査の V5 (先行事例) を広げるもの。

## 1. 調べたこと

オーナーの目指す形 (README の 2026-11-03 の判断) は、常駐する 1 つの入口に複数の端末から話しかけ、そのエージェントが役を割り当てた別のセッションを起こして作業を移すこと。これに近い構成を Claude (主に Claude Code、ほかに Claude Agent SDK) の上で組んだ事例を集め、次の 3 つの性質で順位を付けた。

1. 常駐する 1 つの入口に、複数の端末から同じ会話として届く
2. 役ごとの指示・設定を持つ別のセッションや作業者を起こし、仕事を渡す
3. 入口から、起こした先の様子が見え、止められる

## 2. 集め方と判定の仕方

- 情報源: Hacker News の投稿とコメント、英語の個人ブログ・Substack・Dev.to、Zenn・Qiita・note。各事例は人が書いた記事か投稿から入り、リポジトリはそこからのリンクで辿った。GitHub の topic と awesome 系の一覧は使っていない。
- 除いたもの: [入口と spawn の調査](research-entry-and-spawn.md) の V5 にある製品 (OpenClaw、Hermes Agent、Paperclip、NanoClaw ほか) の紹介そのもの。それらを使って自分の構成を書いた記事は入れた。
- 引用: 原文のページを取得して照合した文だけを載せた。
- 性質の判定: 出典に書かれているときだけ満たすとした。様子は見えるが止め方の記載が無い、のように一部だけ書かれているものは満たさないとし、その旨を添えた。公式の機能 (Remote Control、Channels) の振る舞いは公式の資料で補い、その場合は項目にそう書いた。
- 順位: 満たす性質の数が多い順、同じ数なら新しい順 (日付は記事の公開日。HN はその投稿の日時)。記述の厚さは順位に入れていないため、短いコメントが長い記事より上に来ることがある。
- 【SDK】: Claude Agent SDK で作った事例。定額ログインで Agent SDK を使う形を候補に戻すかはオーナーが決めていないため、外さずに印を付けた。

## 3. 順位

### 1. Kai (dcellison)

- 出典: [Show HN: Kai – A Telegram bot that turns Claude Code into a personal dev asst](https://news.ycombinator.com/item?id=47034875) (2026-02-16)。リポジトリ [dcellison/kai](https://github.com/dcellison/kai) の README (2026-11-03 に取得。投稿のときより機能が増えている)。
- 仕組み: 手を加えていない Claude Code の CLI を子プロセスとして動かす自作の常駐サービス。投稿では「logged-in Claude Code session」を包むので API キーが要らないとする。
- 常駐と入口: Mac mini で LaunchDaemon (Linux では systemd) として動く。入口はブラウザの Workshop とスマホの Telegram で、両方をつないでも履歴は続く。
- 記憶: 規則 (毎回注入する identity のファイル)、事実、会話の履歴を分ける。事実は手元のベクトルストアに入れ、人とプロジェクトごとに引く。
- spawn と役: エージェントごとに handle、目的、指示、能力を定義する。委譲の能力を持つエージェントは、別のエージェントに範囲を区切った仕事を渡す。エージェントはチャンネルのエージェントごとに stream-json で話す子プロセスとして起こし、使われないと落とす。
- 見え方と止め方: 実行中のエージェントはツールの呼び出しごとに見え、Stop で止まる。委譲した実行も同じように見える。
- 満たす性質: 1、2、3
- 裏付け: "the run inspector shows every tool call as it happens, and Stop actually stops it." / "An agent with the delegation capability can hand bounded sub-tasks to other agents"

### 2. Remote Control でサーバーの Claude Code を動かす (blfr)

- 出典: [Hacker News のコメント](https://news.ycombinator.com/item?id=50151287) (2026-10-19)
- 仕組み: 公式の Remote Control。サーバーに Claude Code を入れ、プロジェクトごとに systemd のサービスを足す。
- 常駐と入口: サーバーで動き、Claude Desktop・モバイル・Web から同じセッションに届く。機械とリポジトリがアプリの一覧に出る。
- 記憶: 記載なし。
- spawn と役: サブエージェントを使う。役ごとの定義は記載なし。
- 見え方と止め方: サブエージェントはアプリの標準の表示で見える。Remote Control でつないだ端末からサブエージェントを止めると機械の上でも止まる ([入口と spawn の調査](research-entry-and-spawn.md) の V3)。
- 満たす性質: 1、3 (2 はサブエージェントを使うが役の定義の記載なし)
- 裏付け: "you can control Claude Code on mutiple servers straight from your Claude Desktop, Mobile or Web" / "you get the native view of subagents"

### 3. ShowTalk Taishi の Agent Switchboard (surugawan-ebi)【SDK】

- 出典: [CodexとClaude CodeをSlackから動かす——安全なAgent Switchboardの設計](https://zenn.dev/surugawannoebi/articles/codex-claude-slack-agent-switchboard) (2026-10-16)。リポジトリ [surugawan-ebi/showtalk-taishi](https://github.com/surugawan-ebi/showtalk-taishi)。
- 仕組み: 自作の Gateway。Claude Code の担当は `@anthropic-ai/claude-agent-sdk` で動かし、Codex の担当は Codex App Server で動かす。
- 常駐と入口: 信頼できる自分の作業機で動かす前提。Slack のチャンネルごとに担当 (Koe) がいる。Mac の前に戻ると、各エージェントが持つ会話をそのまま続けられる。入口はチャンネルごとの担当で、1 つではない。
- 記憶: 推論・ツールの実行・会話の履歴は各エージェントと手元の workspace に残す。thread ID を保存し、Gateway を再起動しても続きから話せる。
- spawn と役: Koe ごとに workspace、Slack のチャンネル、role、persona、相談先、Adapter を設定する。Koe は設定した相談先にだけ依頼でき、Koe 同士のやり取りは Gateway の中を通し、Slack には活動ログとして出す。
- 見え方と止め方: stream、進捗の表示、Status、Interrupt に対応する。
- 満たす性質: 2、3
- 裏付け: "Koeが持つのは、担当workspace、Slack channel、role、persona、相談可能な相手、そして利用するAdapterへの参照です。"

### 4. Neutron (Ryan Junee)

- 出典: [How I orchestrate twenty Claude Code sessions from my phone](https://ryanjunee.com/posts/build-your-own-neutron) (2026-06-09)
- 仕組み: 手を加えていない対話型の `claude` を tmux の窓で長く動かし、自作のチャンネル (MCP サーバー) と Bun の Gateway でつなぐ。`--dangerously-load-development-channels` を使う。
- 常駐と入口: Mac で 20 余りのセッションが動き、1 つのプロジェクトが Telegram の 1 つの話題 (forum topic) と 1 つのセッションに対応する。スマホとデスクトップの Telegram から同じ話題に届く。入口は 1 つの Telegram のグループで、話題ごとに別の常駐セッションがいる。
- 記憶: 人・会社ごとの Markdown のファイルを置いたディレクトリ。セッションは `--resume` で再起動を越える。
- spawn と役: 話題のセッションは時間のかかる仕事を `scripts/spawn-agent.sh` に、役・作業名・戻し先の話題・指示を付けて渡す。役は 5 つで、それぞれ `prompts/` の別のシステムプロンプトのファイル。重い 4 役は同じ tmux の中に対話型のセッションとして起こし、記憶の抽出役だけ `claude -p`。セッションの起動には `--settings` と `--append-system-prompt-file` を付け、返信を必ず送らせる Stop hook を `--settings` で入れる。話題をまたいで頼む `/dispatch` もある。
- 見え方と止め方: 作業者は終わると結果を元の話題に投稿し、Gateway はそれを元のセッションにも流す。起動の記録 (`running-agents.jsonl`) を watchdog が 15 秒ごとに読み、落ちた作業者を話題に知らせる。入口から止める手段は記載なし。
- 満たす性質: 1、2 (3 は結果と異常が届くが止め方の記載なし)
- 裏付け: "A topic session calls one script, scripts/spawn-agent.sh , with an agent role, a task slug, the target chat and thread, and a task prompt" / "Telegram on the desktop: the sidebar is the multi-project list, one forum topic per Claude Code session" (画像の説明)

### 5. claude-hub (貼り絵職人)

- 出典: [【導入編】: claude-hub — iPhoneからClaude Codeを操作するDiscord Supervisorシステム](https://zenn.dev/harieshokunin/articles/c6ba085ed070e3) と [運用編](https://zenn.dev/harieshokunin/articles/9828126cc12e6e) (ともに 2026-04-13)。リポジトリ [miyashita337/claude-hub](https://github.com/miyashita337/claude-hub)。
- 仕組み: Discord の Supervisor Bot が、tmux の中に手を加えていない Claude Code のセッションを起こす。
- 常駐と入口: 自宅の Mac に常駐。iPhone の Discord から使う。PC からの利用は記載なし。
- 記憶: 記載なし。
- spawn と役: `/session start` のたびにスレッドができ、独立したセッションが立つ (1 セッション = 1 tmux session)。`CHANNEL_MAP` でチャンネルとプロジェクトのディレクトリを結び、チャンネルごとに別のプロジェクトでセッションを起こす。役はプロジェクトの単位で、起こすのは人のコマンド。
- 見え方と止め方: `/session list` で稼働中のセッションを一覧し、`/session stop` で止める。`PostToolUse` hook が呼ぶ `progress-relay.sh` が進捗を Supervisor に送り、スレッドに転記する。サイドバーに稼働中と停止済みが出る。
- 満たす性質: 2、3 (1 は iPhone だけ記載)
- 裏付け: "/session stop → セッション終了（スレッド内で実行）" / "仕組みは PostToolUse hook だ。Claude Code がツールを実行するたびに progress-relay.sh が呼ばれ、HTTP経由でSupervisorに通知する。"

### 6. CCBot (sixddc)

- 出典: [Show HN: CCBot – Control Claude Code from Telegram via tmux](https://news.ycombinator.com/item?id=46923706) (2026-02-07)。リポジトリ [six-ddc/ccbot](https://github.com/six-ddc/ccbot) の README。
- 仕組み: tmux の中の手を加えていない Claude Code の出力を読み、キー入力を送る薄い層。SDK で別のセッションを作る形をとらないことを設計の要点にしている。
- 常駐と入口: 自分の機械の tmux。Telegram の 1 つの話題が 1 つの tmux の窓と Claude のセッションに対応し、端末とスマホで同じセッションを続けられる。
- 記憶: Claude Code のセッションの記録をそのまま使う。
- spawn と役: Telegram からディレクトリを選んでセッションを作る。役ごとの指示・設定は記載なし。`SessionStart` hook で窓とセッションを結ぶ。
- 見え方と止め方: 応答・思考・ツールの使用と結果を話題に通知する。話題を閉じると tmux の窓が止まる。
- 満たす性質: 1、3 (2 はセッションを起こすが役の分け方の記載なし)
- 裏付け: "Switch from desktop to phone mid-conversation" / "Close (or delete) the topic in Telegram. The associated tmux window is automatically killed and the binding is removed."

### 7. 常時動く家の機械で tmux と Remote Control (Mustafa)

- 出典: [How I run Claude Code 24/7 on an always-on home box with tmux](https://mustafa.net/2026/09/27/how-i-run-claude-code-24-7-on-an-always-on-home-box-with-tmux/) (2026-09-27)
- 仕組み: 手を加えていない `claude` を tmux で動かし、`/remote-control` でアプリにつなぐ。
- 常駐と入口: 家の常時動く機械で、プロジェクトごとに 1 つの長いセッション。ノート PC・デスクトップ・スマホから同じセッションにつなぐ。
- 記憶: Claude Code の会話の記録 (`~/.claude/projects/` の `.jsonl`)。
- spawn と役: 記載なし。
- 見え方と止め方: スマホから進み具合を見て質問に答える。止めるのは端末から `kill -TERM`。
- 満たす性質: 1
- 裏付け: "Attach from any machine — laptop, desktop, or phone — and pick up exactly where I left off."

### 8. CommandMate の窓口・管理・ワーカー (kewton)

- 出典: [窓口は Claude Code、実装は安いモデルに任せる — 個人開発の並列エージェント運用と 2 つのハーネス](https://qiita.com/kewton/items/9a5f09a666bdfa7b83c8) (2026-09-18)
- 仕組み: 自作の CommandMate が tmux の上で Claude Code・Codex・Command Code などを worktree ごとに動かす。窓口は Claude Code (Opus)、管理とワーカーは Command Code。
- 常駐と入口: 手元の機械。人が話すのは窓口の 1 体だけ。スマホからの利用は記載なし。
- 記憶: 手順はリポジトリの `CLAUDE.md` と文書、ワーカーへの指示は `.commandmate/tasks/` のファイル、合否の定義は `.commandmate/verify.yaml`。
- spawn と役: 窓口は `cmate-delegate` で隣のセッションに頼み、返答を受け取る。管理は `cmate-orchestrate` で Issue をワーカーに配る。ワーカーは `cmate-worker-development` の Skill に従う。
- 見え方と止め方: ワーカーの画面は止まったときだけ見る。相手が確認待ちで止まると、そのまま人に返る。途中で止める手段は記載なし。
- 満たす性質: 2
- 裏付け: "どちらの型でも、 人が話す相手は窓口の 1 体だけ です。ワーカーの画面は、止まったときにしか見ません。"
- その他: Claude Code の Projects について「この記事の体制と、形はほとんど同じ」と比べている。

### 9. Orchestrator (mhaaseth)

- 出典: [Show HN: Orchestrator, spawn and manage Claude Code instances remotely](https://news.ycombinator.com/item?id=49643645) (2026-09-10)。リポジトリ [markusbug/Orchestrator](https://github.com/markusbug/Orchestrator)。
- 仕組み: 自作のスマホアプリ (Android と iOS) から、複数の機械の Claude Code を起こし、指示し、止める。
- 常駐と入口: ノート PC と API サーバーの両方の Claude Code を外から扱う。アプリを閉じてもセッションは動き続ける。
- 記憶: 記載なし。
- spawn と役: ディレクトリを選んで起こす。役ごとの設定は記載なし。
- 見え方と止め方: 後から進み具合を見られ、止められる。
- 満たす性質: 3
- 裏付け: "This is a simple app that lets you spawn, prompt, kill and manage Claude Code instances remotely, on many remotes."

### 10. Remote Control の device mode と server mode (Tom)

- 出典: [Remote Control でスマホから Claude Code を起動できるようになり、自前のリモート運用はどこが置き換わったか](https://zenn.dev/marvelousu/articles/claude-code-rc-device-mode) (2026-08-28)
- 仕組み: 公式の Remote Control の server mode (`claude rc`) と、セッション間のメッセージ (`ListAgents`、`SendMessage`)。`claude rc` は tmux の中で維持する。
- 常駐と入口: 4 台の機械をそれぞれデバイスとして登録し、セッションの一覧はスマホアプリと claude.ai の両方で 1 本にまとまる。スマホからデバイスとディレクトリを選んで新しいセッションを起こせる。
- 記憶: 記載なし。
- spawn と役: セッション同士は名前宛てにテキストを送れ、機械をまたぐ配送は Remote Control を通る。役ごとの設定は記載なし。
- 見え方と止め方: デバイスをまたいだ一覧に出る。止まった server は約 4 時間以内なら戻せるが、自動では戻らない。
- 満たす性質: 1 (2 はセッション間で頼めるが役の分け方の記載なし)
- 裏付け: "セッション一覧はデバイスをまたいで1本に統合され、デバイス配下のセッションは各行にどのマシンのものかが表示されます。"

### 11. Channels でアバター付きの自宅アシスタント (hamasato0000)

- 出典: [Claude Code Channelsで遊び始めたらいつ間にかアバターAIアシスタントになった](https://zenn.dev/hamasato0000/articles/e323c365cbe2b2) (2026-06-12)
- 仕組み: 公式の Channels (Telegram) と、自作のチャネル (ブラウザのアバターアプリ用の MCP サーバー)。外からは Cloudflare Tunnel と Cloudflare Access を通す。
- 常駐と入口: 自宅の MacBook。Telegram とブラウザの 2 つの経路が同じ 1 つの会話に届く。
- 記憶: 記載なし。人物像は `CLAUDE.md`。
- spawn と役: 記載なし。
- 見え方と止め方: 記載なし。
- 満たす性質: 1
- 裏付け: "Telegram経由でもアバターアプリ経由でも、同じ1つの会話セッションを共有しているので"

### 12. OpenClaw をやめて Channels と CLAUDE.md にした (mager)

- 出典: [Killing OpenClaw for a native Claude Code setup](https://mager.co/blog/2026-06-02-killing-openclaw/) (2026-06-02)
- 仕組み: 手を加えていない `claude --channels plugin:telegram@claude-plugins-official` を tmux で動かす。Pro の契約でログインする。
- 常駐と入口: シカゴの Mac mini。東京からスマホの Telegram で話す。再起動のあとは SSH で tmux を立て直す。
- 記憶: 初めは `~/Code/brain/` の Markdown を `@` で読み込み、のちに MCP サーバーとして動く gbrain (手元の PGLite) に移した。
- spawn と役: 常駐のセッションを principal とし、狭い仕事は Agent の道具でサブエージェントに渡す。定義は `~/.claude/agents/`。共通の指示は `~/.claude/CLAUDE.md`。
- 見え方と止め方: 記載なし。
- 満たす性質: 2
- 裏付け: "The always-on session is the principal, and I can dispatch a "draft a post about X" or "check the scraper" subagent when I want"
- その他: Agent SDK で自作した plexus は Anthropic の API の課金になり、定額の契約から外れたため消した、と書いている ("plexus routed everything through the Anthropic API, not the Pro subscription.")。

### 13. スマホから Remote Control で使う (HAMY)

- 出典: [How I use Claude Code as my personal assistant from my phone](https://hamy.xyz/blog/2026-05_claude-code-from-phone) (2026-05-27)
- 仕組み: 公式の Remote Control。すべてのセッションで有効にし、auto mode で動かす。
- 常駐と入口: ノート PC とデスクトップで動き、Claude の Web・デスクトップ・モバイルのアプリから届く。
- 記憶: Obsidian をセカンドブレインにする。
- spawn と役: 記載なし。
- 見え方と止め方: スマホで動いているセッションの出力を読み、新しい指示を送る。止め方は記載なし。
- 満たす性質: 1
- 裏付け: "This allows access to these sessions from the various Claude apps (web, desktop, mobile)."

### 14. NanoClaw の個人の運用 (Vivian Balakrishnan)【SDK】

- 出典: [NanoClaw — Personal Claude Assistant](https://gist.github.com/VivianBalakrishnan/a7d4eec3833baee4971a0ee54b08f322) (gist、2026-04-24 作成)
- 仕組み: NanoClaw を自分用に組んだもの。グループごとの Docker のコンテナの中で Claude Agent SDK を動かす。
- 常駐と入口: Raspberry Pi 5 で日常的に動く。WhatsApp・Gmail・Web が有効で、Web の portal で複数の会話を扱う。
- 記憶: SQLite の知識のグラフ。全体の記憶は main 以外から読み取りだけ、グループの記憶はそのグループだけが書く。まとめたページは iCloud と rsync で Obsidian に同期する。
- spawn と役: 登録したグループごとに、コンテナ・ファイル・記憶・Claude のセッションを分ける。main のグループは権限が高い。エージェントは試験的な agent teams で子のエージェントを起こす。
- 見え方と止め方: コンテナは会話が止むと落ちる。入口から見る・止める手段は記載なし。
- 満たす性質: 2
- 裏付け: "Each registered group gets an isolated Docker container, filesystem, local mnemon store, and Claude session."

### 15. Slack から話しかける AI チーム (ロジ)

- 出典: [Socket Mode + Claude CLIでSlack Botを作る](https://note.com/roji_/n/n0f7d94adaaae) (2026-04-11)
- 仕組み: 約 370 行の Python が Slack から受けたメッセージを `claude -p` に渡す。launchd で起動する。
- 常駐と入口: 自分の Mac。スマホの Slack から話しかける。Dispatch、tmux、スマホの SSH は比べた上で使わなかった。
- 記憶: Slack の直近 6 件の会話を毎回プロンプトに付ける。
- spawn と役: Slack 専用のセッション (`slack_session/CLAUDE.md`) が、時間のかかる仕事を別の CLI のプロセスとしてバックグラウンドで起こす。メンバーごとの設定ファイルに完了の報告の仕方を書く。
- 見え方と止め方: バックグラウンドのプロセスが終わると自分で Slack に報告する。止めるのはブリッジ全体 (`launchctl unload`)。
- 満たす性質: 2
- 裏付け: "メンバーの設定ファイルに「タスク完了時は ` slack.py send` で報告する」というルールを書いておくと、誰がいつ何を完了したかがSlackに集まります。"

### 16. Channels と作業者のデーモンと 8 つのエージェントのディレクトリ (Vincent van Deth)

- 出典: [I Replaced OpenClaw With Claude Code Channels, a Worker Daemon, and 8 Agent Directories](https://vincentvandeth.nl/blog/replaced-openclaw-claude-code-channels-worker-architecture) (2026-04-07)
- 仕組み: 入口は公式の Channels (Telegram)。作業は systemd の Python のデーモンが `claude -p` で起こす。
- 常駐と入口: GCP の VM。スマホの Telegram から音声・文字・写真を送る。
- 記憶: 部品の間の状態は Supabase。会話は `--resume <session_id>` で続ける。
- spawn と役: 長い仕事は入口が Supabase のタスクの表に入れ、「Queued. You can keep talking.」と返す。デーモンは 10 秒ごとに表を見て、エージェントのディレクトリで `claude -p` を起こす (同時に 2 つまで)。エージェントは `CLAUDE.md` を持つディレクトリで、MCP もエージェントごとに分ける。
- 見え方と止め方: 進み具合は別のダッシュボードに流す (つなぎ込みは作業中)。Telegram から見る・止める手段は記載なし。
- 満たす性質: 2
- 裏付け: "an agent is a directory with a CLAUDE.md file." / "MCP servers are per-agent (research gets Perplexity, images gets Excalidraw)"

### 17. VPS で Channels とカスタムエージェント (Okapi 2.0)

- 出典: [OpenClawみたいなAI自動化、Claude Codeで実際につくってみた](https://note.com/okapi5746/n/n664244bdbafa) (2026-03-31)
- 仕組み: 公式の Channels (Telegram) を VPS の tmux で動かす。
- 常駐と入口: VPS。スマホの Telegram から送る。
- 記憶: 記載なし。`CLAUDE.md` を OpenClaw の SOUL.md に当たるものとして書く。
- spawn と役: `.claude/agents/` に役ごとのサブエージェントを定義し、内容に応じて Claude が渡す。
- 見え方と止め方: 記載なし。
- 満たす性質: 2
- 裏付け: ".claude/agents/ にMarkdownファイルを置くことで、特定の役割に特化したサブエージェントを定義できる機能です。"

### 18. 1 タスク 1 `claude -p` のアンビエントエージェント (コキエ)

- 出典: [アンビエントエージェントを育てている — Slack の依頼を claude -p が勝手にさばく仕組みを作っている話](https://zenn.dev/kok1eeeee/articles/ambient-task-agent-harness-design) (2026-03-25)
- 仕組み: Rust と SQLite と Slack の Socket Mode で作った自作の常駐。社内チーム向けで、コードは公開していない。
- 常駐と入口: 動く場所は記載なし。入口は Slack と Asana。
- 記憶: 状態は SQLite。タスクが終わるたびに `context.md` (完了の記録) と `memory.md` (学んだこと) に足す。
- spawn と役: 1 つのタスクを 1 つの `claude -p` で動かす。役と制約は `--append-system-prompt` で渡し、`ops_skills` で指定した手順書と同じフォルダの `gotchas.md`・`references/` も結合して注入する。
- 見え方と止め方: 結果は Slack のスレッドに返す。stop を受けても動いている `claude -p` は最後まで走る。
- 満たす性質: 2
- 裏付け: "ops_skills で指定したマークダウンファイルが作業手順書。Rust がこれを読み込んで、同フォルダの gotchas.md と references/ も自動結合し、 claude -p の --append-system-prompt に注入する。"

### 19. Cowork と Dispatch の Chief of Staff (Constantin Gonzalez)

- 出典: [Welcome Claude, my Chief of Staff](https://constantin.glez.de/posts/2026-03-22-welcome-claude-my-chief-of-staff/) (2026-03-22)。後半は Claude が答える形で書かれている。
- 仕組み: 公式の Claude Cowork と Dispatch、予定の作業、MCP のコネクタ。
- 常駐と入口: ノート PC の Cowork のセッションに、スマホから Dispatch で同じ会話として話しかける。メールの転送も受ける。
- 記憶: `CLAUDE.md`・`TASKS.md`・`SOP.md` と PARA の構成のフォルダ、Trello、Dropbox。
- spawn と役: サブエージェントに仕事を配る形は、これからの案として書いているだけ。
- 見え方と止め方: 記載なし。
- 満たす性質: 1
- 裏付け: "I'm not starting from zero on the phone; I'm continuing the same conversation."

### 20. BridgeBoard の秘書と部門エージェント (yuto)

- 出典: [Claude Codeで「AI会社」を動かす — 89タスクを自律処理したオーケストレーター全設計](https://zenn.dev/seeda_yuto/articles/bridgeboard-ai-company-orchestrator) (2026-03-17)
- 仕組み: 手を加えていない Claude Code を tmux のペインで動かし、YAML のキューと inotify のディスパッチャーでつなぐ。ディスパッチャーが動いていないときは `claude -p` で応答する。
- 常駐と入口: 手元の機械で、入口はブラウザ (`localhost:3939`) と CLI の `bb`。スマホは記載なし。
- 記憶: YAML のファイル。秘書は `memory.yaml` に CEO の好みと過去の判断を持つ。
- spawn と役: 秘書から PM、PM から部門へ YAML で渡す。エージェントの性格と能力はそれぞれの `CLAUDE.md` に書き、作業者は要るときだけ tmux のペインで起こして終わったら閉じる。
- 見え方と止め方: `tmux attach` で動きを見られ、ダッシュボードに全エージェントの動きが流れる。止め方は記載なし。
- 満たす性質: 2
- 裏付け: "各エージェントの「性格」と「能力」は CLAUDE.md で定義される"

## 4. 繰り返し出てくる設計のパターン

### 4.1 入口の作り方は 4 通りに分かれる

- 公式の Channels で、動いているセッションにチャットを流し込む: mager、Okapi 2.0、van Deth の入口、hamasato0000、Monica (5 節)、@ryu-ki (5 節)、broomva (5 節)。公式の資料では、Channels は「動いているセッションに外からイベントを押し込む MCP サーバー」で、Telegram・Discord・iMessage が研究プレビューに入る。常駐させるにはセッションを動かし続ける必要がある ([Channels](https://code.claude.com/docs/en/channels): "Events only arrive while the session is open, so for an always-on setup you run Claude in a background process or persistent terminal.")。Pro・Max・Ultra の個人の契約では `--channels` を付けるだけで使え、Team と Enterprise では Owner が有効にする。Neutron と hamasato0000 は自作のチャネルを足している。
- 公式の Remote Control で、公式のアプリから同じセッションに入る: HAMY、Mustafa、Tom、blfr。届く先は Claude のアプリで、Telegram などは使わない。
- 自作のボットが `claude` を子プロセスとして起こす: Kai、ロジ、コキエ、Okhlopkov (5 節)、correlate design (5 節)。メッセージごと・タスクごとに `claude -p` を起こし、`--resume` で会話を続ける形が多い。
- 自作のボットが tmux の中の対話型の `claude` を操作する: CCBot、claude-hub、Neutron の作業者、AgentWire (5 節)。CCBot は「端末が正本のまま」を理由に挙げる。

### 4.2 常駐は tmux とサービスの管理で支える

- 対話型のセッションを tmux に置き、launchd か systemd で起動・再起動する形がほとんどである (mager、Mustafa、Tom、Okapi 2.0、Neutron、Kai、ロジ)。
- 機械の再起動のあとに手で立て直している例が多い (mager は SSH で 2 行、Tom は 4 台ぶん)。Neutron は Gateway の中に十余りの watchdog を持つ。
- 会話は `--resume` や `--session-id` で戻す (Neutron、broomva、van Deth)。

### 4.3 1 つの話題・チャンネル・スレッドを 1 つのセッションにする

- Telegram の話題 (Neutron、CCBot)、Discord のチャンネルとスレッド (claude-hub、broomva)、Slack のチャンネルとスレッド (Agent Switchboard、岩谷 (5 節)) を 1 つのセッションに結ぶ。端末をまたいでも話題が同じなら同じ会話に届く。
- この形では、入口は「1 つのチャットのアプリ」で、話し相手のセッションは話題の数だけある。1 つのエージェントが受けて振り分ける形 (mager の principal、kewton の窓口、BridgeBoard の秘書、ロジの Slack 専用セッション) とは分かれる。

### 4.4 仕事の渡し方は 4 通りに分かれる

- 同じセッションの中のサブエージェント: mager、Okapi 2.0、computerex (5 節)。結果は呼んだ会話に文で返る ("Subagents return text, not control.")。
- 入口のセッションがスクリプトやキューで別のプロセスを起こす: Neutron (`spawn-agent.sh`)、van Deth (Supabase のタスクの表とデーモン)、ロジ (バックグラウンドの CLI)、コキエ (1 タスク 1 `claude -p`)、BridgeBoard (YAML のキュー)。
- 人が入口のコマンドで起こす: claude-hub (`/session start`)、CCBot (話題を作る)、Tom (アプリの New session)、Orchestrator。
- セッション同士のメッセージで頼む: Neutron (`/dispatch`)、Agent Switchboard (`agent.send`)、kewton (`cmate-delegate`)、Tom (`SendMessage`)。

### 4.5 役ごとの文脈は、ディレクトリと起動の引数で分ける

- ディレクトリごとの `CLAUDE.md`: van Deth ("an agent is a directory with a CLAUDE.md file")、broomva (`--workdir` で読む `CLAUDE.md` を変える)、claude-hub (`CHANNEL_MAP`)、BridgeBoard。MCP もディレクトリごとに分ける例がある (van Deth)。
- 起動の引数: `--append-system-prompt-file` (Neutron)、`--append-system-prompt` (コキエ)、`--settings` で hook を入れる (Neutron の話題のセッションの Stop hook)。
- サブエージェントの定義 (`~/.claude/agents/`、`.claude/agents/`): mager、Okapi 2.0。
- 人格・規則・事実を別のファイルに分ける: Monica (`Claude.md`・`Identity.md`・`Soul.md`・`Tools.md`・`Agents.md`)、Kai (規則・事実・会話の履歴)。OpenClaw の SOUL.md などの分け方を写した例が多い。

### 4.6 結果と進み具合は、チャットに投稿して戻す

- 作業者が終わると元の話題に投稿する (Neutron、ロジ)。Neutron は同じ結果を元のセッションの文脈にも入れる。
- 進み具合は hook や記録のファイルから拾ってチャットに出す (claude-hub の `PostToolUse` hook、CCBot のセッションの記録の監視、Neutron の `running-agents.jsonl`)。別のダッシュボードに出す例もある (van Deth、BridgeBoard)。
- 入口から止める手段を書いているのは、Kai (Stop)、claude-hub (`/session stop`)、CCBot (話題を閉じる)、Agent Switchboard (Interrupt)、Orchestrator (kill) である。`claude -p` で起こした作業は、止める指示を受けても最後まで走る、と書く例がある (コキエ)。

### 4.7 記憶は Markdown のファイルが中心で、検索の層を足す例がある

- Markdown のファイル (Obsidian の vault や git のリポジトリを含む) が最も多い (HAMY、Okhlopkov (5 節)、Neutron、Teresa Torres (5 節)、Monica (5 節))。
- 検索の層を足す例: mager (MCP サーバーの gbrain)、Kai (手元のベクトルストア)、Vivian Balakrishnan (SQLite の知識のグラフ)。
- 会話ごと・スレッドごとの台帳を持たせる例: @ryu-ki (スレッドの目的と状態の台帳を、返信の前に読ませる)。

### 4.8 定額の契約で動かすことを、構成を選ぶ理由に挙げる例が多い

- 手を加えていない `claude` を使う理由として、定額の契約のまま動くことを挙げる例が多い (mager、Kai、Neutron の作業者、Instar (5 節))。
- mager は Agent SDK で作った plexus が API の課金になったため消した。Agent SDK で作った事例のうち、課金の扱いを書いているのは 5 節の cha0tikdino (定額の契約で動くと書く) だけで、Agent Switchboard と Vivian Balakrishnan は書いていない。課金と規約の公式の記述は [入口と spawn の調査](research-entry-and-spawn.md) の V0 にある。

## 5. 順位に入れなかった事例

満たす性質が 0 か、性質の記述が順位の 20 件より薄いもの。構成の参考になる点だけ書く。

- [Always-On AI Agent: Running Claude Code 24/7 on a Server](https://okhlopkov.com/always-on-ai-agent-server-setup/) (@danokhlopkov、2026-03-31): Hetzner の VPS の Docker で、Telethon のデーモンがメッセージごとに `claude -p` を起こす。文脈はメッセージの中身ではなく chat_id で決める。記憶は Docker の volume の `memory.md` と、git の Obsidian の vault。
- [An assistant named Monica](https://readwhitespace.substack.com/p/an-assistant-named-monica) (Mateusz Tatara、2026-05-15): 古い MacBook Pro で公式の Telegram のプラグイン。専用の Google のアカウントを持たせ、人格と規則を 5 つのファイルに分ける。
- [My Team of Agents: How I Get Claude to Do Tasks While I'm Away from the Computer](https://www.producttalk.org/my-team-of-agents/) (Teresa Torres、2026-05-20): 常時動く Mac mini の LaunchAgents で、役ごとのエージェント (ポッドキャストの管理役、営業の事務役、開発の管理役) を予定どおりに動かす。identity・タスク・スクリプトは Claude Code の skill ではなく Obsidian に置く。入口は記載なし。
- [How I Replaced OpenClaw with Claude Code Channels and a Discord Watchdog](https://broomva.tech/writing/replacing-openclaw-with-claude-code-channels) (broomva、2026-03-23): Discord のチャンネルごとに tmux のペインで Channels のセッションを動かし、watchdog がスマホで作ったチャンネルを 60 秒以内に見つけてセッションを起こす。30 分使わないと止め、`wake` で戻す。起こすのは watchdog で、入口のセッションではない。
- [【雑記】自分のClaude Code運用の全体像](https://qiita.com/ryu-ki/items/1668e67b8d3cf43c4e0a) (@ryu-ki、2026-08-17): 公式の Channels。記憶をタスクの台帳・個人のメモ・技術の知見の 3 つに分け、git のファイルを開発用の機械との共有の記憶にする。
- [SlackからClaude Code CLIをリモート操作するブリッジを作った](https://qiita.com/nariakiiwatani/items/e79186237cce6cf7462d) (岩谷成晃、2026-02-26): チャンネルがプロジェクト、スレッドがセッションに対応し、返信すると `--resume` が付く。端末で動く `claude` の文脈を取り込む `fork` がある。
- [Discord BotでMac miniをどこからでもClaude Code遠隔操作する](https://zenn.dev/correlate_dev/articles/discord-bot-remote-mac-mini) (correlate design、2026-02-12): スラッシュコマンドのたびにスレッドを作り、`claude` をサブプロセスで動かす。
- [Claude Agent SDKでOpenClawのような常駐型AIエージェントを自作する](https://zenn.dev/is0383kk/articles/7f33a2eca6733d) (ヨシダ ヨシヲ、2026-03-19)【SDK】: Python の Agent SDK で Unix ソケットのデーモンを常駐させ、CLI・REST・Discord・Slack から受ける。`setting_sources=["user", "project"]` で手元の Claude Code の設定を流用する。
- [Show HN: I built a personal AI agent that runs 24/7 on my home server](https://news.ycombinator.com/item?id=47132125) (cha0tikdino、2026-02-24)【SDK】: Beelink のミニ PC の systemd で 6 か月動かす。記憶は SQLite の FTS5 の会話の記録と、システムプロンプトに常に入れる小さな事実。
- [Show HN: Instar – Persistent Server for Claude Code with Telegram and Evolution](https://news.ycombinator.com/item?id=47414744) (JKHeadley、2026-03-17): Telegram の話題ごとに Claude Code のセッションを結び、`AGENT.md` と hook で identity を保つ。バックグラウンドのセッションを起こす skill を持つ (README)。
- [Show HN: AgentWire – Talk to your AI coding agents by voice, across machines](https://news.ycombinator.com/item?id=46974968) (prradox、2026-02-11): tmux の上のブラウザの portal に、スマホやタブレットから音声で話しかける。1 つのセッションを leader にして作業者のペインを起こし、要約を集める。
- [Hacker News のコメント](https://news.ycombinator.com/item?id=48960288) (theptip、2026-07-18): 親の Remote Control のセッションが、新しい作業ごとに tmux の窓と Remote Control のセッションを作る。
- [Hacker News のコメント](https://news.ycombinator.com/item?id=48624111) (computerex、2026-06-22): 1 つの Claude Code を Chief of Staff にしてすべての仕事をサブエージェントに渡させ、hook でそれを強める。
- [atlas](https://georgemasto.substack.com/p/atlas) (George Mastorakos、2026-05-18): 古い MacBook で常駐し、Telegram と音声のメモで話す。Claude Code に仕事を起こさせるとあるが、起こし方は記載なし。テンプレートのリポジトリ [atlas-template](https://github.com/george-masto/atlas-template) を公開している。
- [boop-agent](https://github.com/raroque/boop-agent) (raroque)【SDK】: 作者が自分のパーソナルエージェントの構成として公開した iMessage のエージェント。README は Claude の動作を Agent SDK と手元の Claude Code のログインで動かすとする。人が書いた記事は見つからず (作者の動画は読んでいない)、中身は確かめていない。

## 6. 見つからなかったこと

- Reddit の投稿: 検索 (`allowed_domains` に reddit.com) と取得 (www.reddit.com、old.reddit.com) がどちらも道具で断られ、読めなかった。
- X の投稿: 取得が HTTP 402 で断られた。記事に引用された投稿だけを読んだ。LinkedIn (HTTP 999)、medium.com の一部 (HTTP 403) も読めなかった。
- Anthropic の社員が自分のパーソナルエージェントの構成を書いた記事: 見つからなかった。検索語: Anthropic employees "how I use Claude" chief of staff、"how I use Claude" Boris / Cat Wu / Thariq personal assistant。
- カンファレンスの発表: Agent SDK のワークショップと講座だけで、パーソナルエージェントの構成の発表は見つからなかった。検索語: talk personal agent built on Claude Code Agent SDK conference AI Engineer 2026。
- Dots を名指しして Claude で同じ形を作った実践者の記事: 見つからなかった。出てきたのは比較の記事と、Claude Code の作業を Telegram と Web から動かす OSS の [Open Dots](https://github.com/Anil-matcha/open-dots) (README だけで、記事は無い)。検索語: OpenAI Dots alternative built on Claude Code personal agent。
- LINE から複数のセッションを指揮する事例: 見つからなかった。LINE を Claude Code のチャネルにするプラグインはある。検索語: Claude Code LINE Bot 常駐 秘書 複数セッション、Claude Code セカンドブレイン Obsidian 常駐 LINE スマホ 指示 ワーカー。
- 複数の端末から 1 つの入口に届き、その入口が役を分けたセッションを起こし、入口から見えて止められる、の 3 つをそろえて書いた事例: Kai (README による) のほかは見つからなかった。検索語: claude code personal agent always-on subagents、Claude Code chief of staff sub-agents、Claude Code 司令塔 常駐 セッション 他のセッションを起動 claude -p 子セッション 役割別 CLAUDE.md、Claude Code tmux 複数エージェント オーケストレーター 部下 スマホ Telegram LINE 常駐。
- `claude --bg` と `claude agents` をパーソナルエージェントに使った事例: 開発の例だけで見つからなかった。検索語: "claude --bg" / "claude agents" personal assistant、"claude --bg" / "claude agents" second brain。
- Agent SDK で個人が常駐のエージェントを作り、課金の扱いまで書いた記事: cha0tikdino (5 節) のほかは見つからなかった。検索語: "Claude Agent SDK" personal assistant Telegram bot、Claude Agent SDK personal assistant Telegram VPS spawns sub-agents blog "I built"。
