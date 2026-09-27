# 所見 (一次資料の引用付き)

- 種別: 調査記録の本文。[README.md](README.md) の方法で集めた一次資料の所見。引用は英語のまま。
- 読んだ日: 2026-09-27。URL は読んだ時点のもの。

## 1. A: Conductor の可視化層

実機 (ミニ PC の 5000 番、conductoross/conductor:3.32.4) と一次資料で確認した。

- 画面: ワークフロー実行の検索 (状態・期間・自由文)、実行詳細の Diagram / Task List / Timeline / Summary / Input・Output / JSON / Variables のタブ、Queue Monitor、定義の閲覧編集、Agent Executions。Diagram は増分 4 の実行を DO_WHILE の枠、判定器、switch、DYN. FORK、セル、JOIN の図として描いた。Timeline はキュー待ち・実行時間・エンジンの遅延をガントで見せる。実機のサイドバーに Human Tasks は無い (Executions 配下は Workflow、Scheduler、Queue Monitor)。
- Agents 機能: [v3.32.0 リリースノート](https://github.com/conductor-oss/conductor/releases/tag/v3.32.0) "Agent / A2A / LLM support graduates to stable — hosted agents, A2A v0.2 compatibility"。[定義](https://conductor-oss.github.io/conductor/devguide/concepts/agents.html) "The definition names the model to use" (例 `model="openai/gpt-4o-mini"`)、"Conductor compiles the agent into a workflow graph and executes it"。[PR #1515](https://github.com/conductor-oss/conductor/pull/1515) "lazy sub-agent expansion"。Claude Code や Codex のセッションを包む機構ではない。
- 会話 UI: 見つからなかった。Orkes の Assistant はワークフローを作る開発者向けで Orkes 限定。
- 介入: [Orkes の文書](https://orkes.io/content/developer-guides/debugging-workflows) "Restart with Current Definitions, Restart with Latest Definitions, Rerun from a specific task, Retry - From failed task"。[Human Tasks](https://orkes.io/content/developer-guides/orchestrating-human-tasks) は Orkes の文書にあり、OSS の実機の画面には無い。
- ソース ([conductor-oss/conductor の ui/](https://github.com/conductor-oss/conductor)) は Material-UI v4 と dagre-d3 で、ui/src 全 157 ファイルに `@media` や `useMediaQuery` の一致が無い。ただし配備版は「Orkes Platform Version」と表示され、読んだソースとメニュー構成が違うので、レスポンシブの所見は配備版には当てはめない。
- Temporal: Web UI はイベント履歴の可視化で、会話 UI やエージェント向けの可視化は無い。[AI cookbook](https://docs.temporal.io/ai-cookbook/openai-agents-sdk-python) は可視化に OpenAI の Traces を案内する。

## 2. B: ベンダー app の可視化と後付けの観測

- Claude Code: [subagent を入れ子の木で表示、(+N) で子数](https://code.claude.com/docs/en/sub-agents)。[/workflows はフェーズ単位の木にエージェント数・トークン・時間](https://code.claude.com/docs/en/workflows)、v2.1.280 で木の表示を更新 ([changelog](https://code.claude.com/docs/en/changelog))。[/tasks](https://code.claude.com/docs/en/commands)。[claude agents (Agent View、研究プレビュー)](https://code.claude.com/docs/en/agent-view) は状態別の一覧で CLI 限定。[デスクトップ](https://code.claude.com/docs/en/desktop) はサイドバー一覧と Tasks ペイン。[Web](https://code.claude.com/docs/en/claude-code-on-the-web) はセッション一覧と差分。[スマホ](https://code.claude.com/docs/en/mobile) は Code タブで cloud セッション・Remote Control・Dispatch。subagent の木はスマホに無い。
- Claude Code の外への出力: [OpenTelemetry](https://code.claude.com/docs/en/monitoring-usage) はメトリクス 8 種と user_prompt・tool_result・api_request などの出来事、OTLP。[hooks 33 種](https://code.claude.com/docs/en/hooks) (SubagentStart / SubagentStop / TaskCreated / TaskCompleted を含む)。"Direct edits to hooks in settings files are normally picked up automatically by the file watcher."。[stream-json](https://code.claude.com/docs/en/headless) の出来事に parent_tool_use_id。[起動時の旗](https://code.claude.com/docs/en/cli-reference) `--settings`、`--mcp-config`、`--agents`、`--append-system-prompt`、`--setting-sources`。[subagent の frontmatter](https://code.claude.com/docs/en/sub-agents) に tools、disallowedTools、model、permissionMode、maxTurns、skills、mcpServers、hooks、memory、background、omitClaudeMd、effort、isolation など 18 項目。[`claude mcp serve`](https://code.claude.com/docs/en/mcp) で自身を MCP サーバとして公開。
- Codex: [/agent でスレッド切替、Subagents パネル (Active / Done)](https://learn.chatgpt.com/docs/agent-configuration/subagents)。[cloud はチャット型のタスク一覧](https://learn.chatgpt.com/docs/cloud)。[remote](https://learn.chatgpt.com/codex/remote) "Start, guide, and review coding tasks from your phone"。[otel](https://learn.chatgpt.com/codex/config-reference) の exporter に otlp-http / otlp-grpc。[app-server](https://learn.chatgpt.com/codex/app-server) の thread/list、thread/read。ミニ PC の Codex 0.156.1 の副コマンドに `app-server`、`remote-control`、`agents`、`queue`、`resume`、`fork` がある。Codex を MCP サーバとして公開する副コマンドは無い。
- 後付けの観測: [Datadog Lapdog](https://docs.datadoghq.com/llm_observability/lapdog/) "captures every span, prompt, tool call, and cost from ... a coding agent like Claude Code, Codex, or Pi"。[Langfuse](https://langfuse.com/resources/engineering/coding-agent-tracing) (Claude Code は Stop hook、Codex は plugin hook)。[o11y-dev/opentelemetry-hooks](https://github.com/o11y-dev/opentelemetry-hooks) (8 種)。[SigNoz](https://signoz.io/docs/claude-code-monitoring/)、[claude-code-otel](https://github.com/ColeMurray/claude-code-otel)、[claude_telemetry](https://github.com/TechNickAI/claude_telemetry) (Claude Code のみ)。[Datadog AI Agents Console](https://docs.datadoghq.com/ai_agents_console/setup/) に Claude Code のタイル。

## 3. ACP の状況

- [エージェント一覧](https://agentclientprotocol.com/get-started/agents)、[クライアント一覧](https://agentclientprotocol.com/get-started/clients) (エディタ、CLI、Web、モバイル、メッセージング)。
- [claude-agent-acp](https://github.com/agentclientprotocol/claude-agent-acp) v0.81.2 (2026-09-24)、2026-08-05 から 20 件以上のリリース。[codex-acp](https://github.com/agentclientprotocol/codex-acp) v1.13.1 (2026-09-23)、20 件。どちらも ACP の組織が保守し、ベンダー公式ではない。Gemini CLI は本体の `--acp`。
- [仕様の更新](https://github.com/agentclientprotocol/agent-client-protocol/blob/main/CHANGELOG.md): v1.9.1 (2026-09-18)、v1.8.0 (09-17)、v1.7.0 (08-20)。[通知の種類](https://agentclientprotocol.com/protocol/overview): message chunks (agent, user, thought)、tool calls、plans、available commands、mode changes。[usage_update、session/cancel](https://agentclientprotocol.com/protocol/v1/prompt-turn)。session/load は任意。
- subagent、hooks、skills が ACP 越しにどう見えるかを書いた公式文書は見つからなかった。
- 採用例: [JetBrains](https://www.jetbrains.com/help/ai-assistant/acp.html)、[Copilot CLI](https://github.blog/changelog/2026-01-28-acp-support-in-copilot-cli-is-now-in-public-preview/)、[Cursor CLI](https://cursor.com/docs/cli/acp)、[Goose](https://goose-docs.ai/docs/guides/acp-providers/)、GitKraken Kepler。

## 4. トークンの実測と推定

Claude Code のセッション記録 (開発 PC) と Codex の走行記録 (ミニ PC) から取った。換算は、キャッシュ読み取り 0.1、キャッシュ書き込み 1.25、それ以外 1 の重み。

| 記録 | 呼び出し | 初回コンテキスト | キャッシュ読み取り | キャッシュ書き込み | 出力 | 換算入力 |
|---|---|---|---|---|---|---|
| 開発 PC の Claude Code セッション (2026-09-27) | 14 | 94.9k | 2.21M | 0.22M | 26k | 0.49M |
| 2026-09-23 の設計・評価セッション 2 本 | 55 / 130 | 89.2k | 13.95M / 45.67M | 0.35M / 0.83M | 105k / 176k | 1.83M / 5.60M |
| Codex を skill で 4 回起動した Claude セッション | 134 | 不明 | 51.88M | 1.93M | 260k | 7.60M |
| Claude のサブエージェント 33 本の典型値 | 4〜55 | 76〜80k | 中央値 1.7M | 0.1〜0.2M | 数十〜数千 | 0.15〜4.0M |
| Codex 走行 increment-4 | 出来事 73 件 | 不明 | 4.41M (命中) | 0.13M (非命中) | 31k | 0.57M |
| Codex 走行 ui-mock-2 | 出来事 75 件 | 不明 | 5.83M | 0.23M | 95k | 0.81M |
| 増分 4 の実セル (ラッパー経由の Claude) | 不明 | 不明 | 終了時の総コンテキスト 18.7k | | | |

推定 (Codex の走行 1 本ぶんの作業 + 割り振りと集約を 1 タスクとする): セルの形の上乗せは 0.05〜0.2M、最上位に開発 PC の Claude セッションを置く形の上乗せは 0.3〜1.2M (最上位の呼び出しのうち割り振りと集約に当たる分を 10〜30 回と置く)。差の出所は固定プロンプトの大きさ (開発 PC の Claude Code は 90〜95k、ラッパー起動のセルは 18.7k) で、最上位の Claude を軽く起動すれば差は誤差の範囲に入る。

## 5. C: 製品ごとの所見

各製品の (a) 対応と繋ぎ方、(b) 会話する相手、(c) 常駐と端末、(d) 協調とワークフローの定義、(e) 画面と介入、(f) プロトコル、(g) 運営。引用の出典は README (raw.githubusercontent.com の HEAD/README.md) と各 homepage。

### 5.1 一次候補

**omnigent** ([repo](https://github.com/omnigent-ai/omnigent)、[site](https://omnigent.ai))
- (a) "via the official claude / codex CLIs"、"a claude / codex CLI you're logged into"。tmux / PTY の包み "the native omnigent <harness> terminal wrappers (claude, codex, cursor...)"。"Both speak the Agent Client Protocol over stdio"。
- (b) "Mix Claude Code, Codex, Cursor...together in the same session"。
- (c) "Run Omnigent on a server with a stable URL"、"One docker compose up runs the server on any host"。iOS / Android app、macOS app、"The web UI is built for mobile"。
- (d) "An agent is a short YAML file...MCP servers, and sub-agents a supervisor can delegate to"。"Ask one agent to review another's work, or split a task across agents"。
- (e) "Messages, sub-agents, terminals, and files stay in sync"、"pause for your approval before risky actions"。
- (f) MCP、ACP。OpenTelemetry と hooks は見つからなかった。
- (g) "Built by the Databricks AI team, Neon and the Omnigent Contributors."。

**happier** ([repo](https://github.com/happier-dev/happier)、[site](https://happier.dev))
- (a) "Claude Code, Codex, OpenCode, Pi and more"、"Any agent that speaks ACP can be added from the settings."。"uses the login your CLI already has, so a Claude Pro or Max subscription, a ChatGPT subscription through the Codex CLI...keeps working exactly as it does now."。
- (b) "Keep running Claude Code, Codex or OpenCode in their own terminal UIs."、"Happier mirrors them to every device."。
- (c) "The Happier daemon starts and manages agent processes where your code lives."。Web は cloud.happier.dev、"Run your own relay with one command"、"Docker and Proxmox as alternatives"。iOS / Android。
- (d) "Any session can launch review, plan or delegate runs on another agent."、"MCP servers, configured once... use them with every agent on every machine"。
- (e) "sessions, diffs and terminal in one window"、受信箱に "Permission requests, agent questions and unread sessions"、"Queue messages while the agent works, reorder or edit them before they run, and steer a running turn without interrupting it."。
- (f) ACP、"Happier as an MCP server"。
- (g) 運営主体は見つからなかった。"Not affiliated with or endorsed by Anthropic, OpenAI, or Google."。

**OpenHands** ([repo](https://github.com/OpenHands/OpenHands)、[ACP エージェント](https://docs.openhands.dev/openhands/usage/agent-canvas/acp-agents)、[スマホ](https://docs.openhands.dev/openhands/usage/agent-canvas/mobile-access.md)、[会話](https://docs.openhands.dev/openhands/usage/agent-canvas/conversations.md)、[資金](https://openhands.dev/blog/press-release-all-hands-announces-5m-to-scale-ai-agent-for-software-development))
- (a) Claude Code、Codex、Gemini CLI。"the Agent Server spawns the agent's own CLI as a subprocess"、"the provider CLI finds that login automatically"。
- (b) "Agent Canvas can drive conversations with the built-in OpenHands agent or with an external ACP agent"。
- (c) "agents to continue running even when your laptop is shut"。"Open...in your phone or tablet browser"。
- (d) SDK の機能として "Define specialized sub-agents as simple Markdown files with YAML frontmatter"。
- (e) "Branch from here"、/goal 実行中の "status banner...judge score"、"Sending a normal message while a goal is running interrupts the goal"。
- (f) ACP (JSON-RPC on stdio)、MCP。
- (g) "$5 million in seed funding" (Menlo Ventures、Pillar VC、Betaworks、Rebellion)。

**multica** ([repo](https://github.com/multica-ai/multica)、[site](https://multica.ai)、[LICENSE](https://github.com/multica-ai/multica/blob/main/LICENSE))
- (a) "Claude Code, Codex, Cursor, Copilot, Kimi, OpenCode, and more"、"runs the agent CLIs you already have installed and authenticated"。
- (b) "Ask your workspace a question"、"Assign to an agent like you'd assign to a colleague"。
- (c) "Web, desktop, and mobile — on macOS, Windows, Linux, iPhone, and iPad"、"daemon on your laptop or cloud box"、"Docker Compose or Helm"。
- (d) "Squads — Put agents and people on one team; the leader routes the work"、"Skills are reusable capability definitions" (SKILL.md)。
- (e) "A Multica board where agents...are moving work across columns"、"Steer a running agent"、"Execution log...timestamped"。
- (f) ACP、MCP、OpenTelemetry、hooks は見つからなかった。
- (g) "Multica is built by a small team...since 2021"、"Before Multica, we built devv.ai"。ライセンスは Apache 2.0 に商用ホスティングの制限等を足した独自条項 ("Multica License")。

**paseo** ([repo](https://github.com/getpaseo/paseo)、[site](https://paseo.sh)、[LICENSE](https://raw.githubusercontent.com/getpaseo/paseo/HEAD/LICENSE))
- (a) "One interface for Claude Code, Codex, Copilot, OpenCode, and Pi agents."、"supports many more via ACP"。"at least one agent CLI installed and configured with your credentials"。
- (b) "Paseo runs a local server called the daemon that manages your coding agents."。
- (c) "You can run the daemon headless and use any client to connect"。Web は app.paseo.sh、Docker 例で localhost:6767。"iOS, Android, desktop, web, and CLI"。
- (d) skill "/paseo-handoff"、"/paseo-committee"。"Use MCP, the CLI, or the TypeScript SDK to automate Paseo"。
- (e) diff tree、タブ、PR。
- (f) MCP、ACP。
- (g) "Paseo is built by one person and funded by the people who use it."。LICENSE は Apache License 2.0 (同梱のサードパーティ部分を除く)。

**kandev** ([repo](https://github.com/kdlbs/kandev)、[site](https://kandev.ai))
- (a) "@agentclientprotocol/claude-agent-acp"、"codex-acp"、"All agents communicate via ACP"。
- (b) "Plan with the agent, comment on exact steps"。
- (c) "self-host it on your own infrastructure"、"Works on macOS, Linux, and Windows"、"mobile remote-access guide...Tailscale, Cloudflare Tunnel"。
- (d) "Workflow portability...export and import workflows as portable YAML"、"Task-agent MCP...message other tasks"。
- (e) "Drag-and-drop boards"、"Review dialog"、"Plan, review, and approval gates"。
- (f) ACP、"External MCP...over streamable HTTP or SSE"。
- (g) "© 2026 Kandev. Open source, multi-provider, no telemetry"。"Kandev does not pin the managed npm runtimes for Claude, Codex, OpenCode"。

### 5.2 二次候補

**5dive** ([repo](https://github.com/5dive-ai/5dive)、[site](https://5dive.ai)): "running an official coding CLI (claude, codex...) as a systemd service"、"Official CLIs on your own Pro/Max or keys. No middleman, no OAuth proxy."、"5dive acp — Connect from Zed, Buzz, and other ACP clients"。"your agent...keeps managing agents through chat"。"Agents stay alive when you close the terminal"、Docker。"shared SQLite task queue, talk to each other, hand work off"、"Declarative agents via 5dive.yaml"。"Org chart...Queue...Gates...Triggers"、"5dive wall --grid=CxR...every agent's live TUI on one screen"、"tap-to-answer buttons"。"We run our own company on this"。スマホの記述なし。

**OpenMausBot** ([repo](https://github.com/milind-soni/OpenMausBot)、[site](https://openmausbot.com)): "your existing logins and subscriptions, no new accounts, no proxy in the middle"、"One small harness server on 127.0.0.1 owns every agent process"。"Every bot in the sidebar is a real agent — Claude or Codex running locally"。macOS / Windows / Ubuntu、Docker、Android / iOS (TestFlight)。"Install a complete team from one Markdown file"。"Allow / Deny / answer in chat"。"ships a stdio MCP server for external clients such as Claude Desktop"、ACP。個人 2 名。

**amux (mixpeek)** ([repo](https://github.com/mixpeek/amux)、[site](https://amux.io)): "dozens of parallel workers (Claude Code, Codex, Gemini CLI, OpenCode, Ollama)"、"Your agents stay vanilla CLI tools running in real terminal sessions"。"type into any running session from the dashboard or phone; redirect mid-task"。"./install.sh automatically creates and enables three user-level services" (systemd)、"open https://localhost:8824"、"installable PWA"、iOS app。"origin-stamped inter-worker messaging"、"Swap the model or provider on a running worker"。"shared kanban board"、"peek into any peer's terminal"。独自の AgentProtocol。ライセンスは MIT + Commons Clause。Mixpeek 社。

**bb** ([repo](https://github.com/get-bb/bb)、[site](https://getbb.app)): "any agent that supports ACP, on your own subscriptions"、"bb uses the provider CLI you already have authenticated"。"desktop app, web app, CLI, and HTTP API"、macOS (Apple Silicon) / Linux x64 / WSL2。"have one agent spawn and manage another, each in its own thread"。"code review thread, dispatch panel, and task board"、"steer at any point, or hand off to another agent"。MCP Registry。個人 (@_ymichael)。スマホの記述なし。

**podium** ([repo](https://github.com/madeinorbit/podium)、[site](https://podium.do)): Claude Code、Codex、Grok、OpenCode、Cursor をまたぐ委譲と通信、既存の契約をそのまま。会話中のエージェントが統括役になれ、個々とも話せる。macOS 正式、Windows / Linux はプレビュー、Linux (x86_64 / ARM64) のヘッドレスサーバを VPS に置き、デスクトップ・ブラウザ・スマホのブラウザから接続。エージェントが Podium の CLI / MCP で自分でタスクを作る。ボード、チーム表示、会話への途中参加。Made in Orbit (2 名)。

**claw-orchestrator** ([repo](https://github.com/Enderfga/claw-orchestrator)): Claude Code、Codex、Antigravity、Grok Build、OpenCode を "persistent programmable sessions" として包む。`clawo serve` でダッシュボードと HTTP (18796)、Web 3 タブ (Autoloop / Council / Forge)。agent / fanout / council / verifier / human_gate / router / subflow のノード。セッションごとに context・tool・model・worktree。再試行・タイムアウト・中断・steer。`clawo acp`、`clawo-mcp`。対応 CLI の版は週次スイープで自動更新。個人。

**Archon** ([repo](https://github.com/coleam00/Archon)、[docs](https://archon.diy/docs)): "Works with Claude Code SDK, Codex SDK, and local models via Pi"、"Compiled binaries need a CLAUDE_BIN_PATH"。端末では Claude Code 自身、Web では "Project chat"。"archon serve"、"A binary downloads the matching Web UI on first run"、"The Docker image ships Claude Code pre-installed"、"Ship from your phone"。".archon/workflows/build-feature.yaml"、"5 parallel reviewers"、"fresh_context: true"、"interactive: true"。"Run detail - Event log, artifacts, workflow graph"。MCP、skills、hooks。個人 (coleam00)。

**Orca** ([repo](https://github.com/stablyai/orca)、[site](https://onorca.dev)): "Run Codex, ClaudeCode, OpenCode or Pi side-by-side"、"Works with any CLI agent — if it runs in a terminal, it runs in Orca."、"Plug in the subscriptions you already have"。"Running `orca serve` on a headless Linux server? See the headless Linux server guide."、iOS / Android。"Fan one prompt across five agents, each in its own isolated git worktree"。委譲・メッセージ・ワークフロー定義・ACP・MCP・hooks は見つからなかった。"Backed by Y Combinator"、Stably AI。

**t3code** ([repo](https://github.com/pingdotgg/t3code)、[site](https://t3.codes)): "Works with your subscriptions on Claude Code, Codex, Cursor, Grok Build, OpenCode, and Google Antigravity."。"t3 service install keeps it running in the background"、"open the local web app"、"Self-host it or distribute it as your own"、iOS / Android。"Every agent thread writes to its own branch"、diff review、PR。委譲・ワークフロー定義・プロトコルは見つからなかった。"© 2026 T3 Tools Inc"。

**jean** ([repo](https://github.com/coollabsio/jean)): "Claude CLI, Codex CLI, Cursor CLI, OpenCode, PI, Command Code, Grok, and Kimi Code"、"Everything runs locally on your machine with your own CLI installations"。"Headless server (jean-server) - Linux amd64 and arm64 only"、"ghcr.io/coollabsio/jean-server"。"MCP server support, multi-agent collaboration"、"custom system prompts, custom CLI profiles"、"per-mode overrides"。terminal、diff viewer、file browser、canvas、"execution modes (Plan, Build, Yolo) with plan approval flows"。"© 2026 coolLabs Solutions Kft"。スマホの記述なし。

**vicoa** ([repo](https://github.com/vicoa-ai/vicoa)、[site](https://vicoa.ai)): "Claude Code, Codex, Pi, Oh My Pi, and Antigravity have native integrations; the rest connect over the Agent Client Protocol (ACP)."、"Bring your own key: your existing subscription or API keys"。"vicoa daemon to just connect this machine"、"Run the whole stack yourself with Docker"、Web / iOS / Android。"Skills: view, install and remove the agent skills"、"Automations: cron schedules"。"Inline diffs"、"approve changes"、"redirect the agent"。2026-08-28 作成。

**omg.dev** ([repo](https://github.com/BennyKok/omg.dev)、[site](https://omg.dev)): "Supports Claude Code, Codex, Grok, Cursor, omg agent, OpenCode, fx, Muse, DeepSeek, Devin, Jcode, Copilot, and Pi."。README は "Debian, Ubuntu, or macOS" のローカルサーバと "http://localhost:8766"、サイトは "durable, isolated cloud computers" で前提が食い違う。iPhone app。"Board"、"Chat"、"diff view"、"Transcripts"。"Hosted MCP server"。個人。

**intentic** ([repo](https://github.com/intentic/intentic)、[site](https://intentic.dev)): "on your Claude plan"、"Codex on your ChatGPT plan"。"agents live on your machine, not in the tab"、"Docker if the machine needs it"、Windows / Linux app、"desktop and mobile shells"。"Every task runs in its own git worktree and branch"。"the fleet board"、"stoppable mid-thought"。"any ACP agent"、"any MCP server of your own"。個人 (Artur Kurowski)。

**opensession** ([repo](https://github.com/tellahq/opensession)): "Supports multiple Codex and Claude subscriptions and model APIs"、"driving...through the Pi engine"。"Linux, macOS, or inside WSL2" (per-user service)、"PWA on your phone's home screen"、"Native Swift app (iOS + macOS)"。".agents/ lifecycle scripts a repo commits"、"per-user MCP/GitHub scoping"。PR review、diffs、automations。Tella (YC S20) の内製から。

**herdr と collie** ([herdr](https://github.com/herdrdev/herdr)、[docs](https://herdr.dev/docs/)、[collie](https://github.com/AltanS/collie)): "herdr doesn't wrap or replace them; it owns their terminals"。"Herdr uses newline-delimited JSON over a local socket"、"Claude Code uses hooks/herdr-agent-state.sh"。"One binary for macOS, Linux, and Windows"、"a server running in the background"、"Each machine keeps its own Herdr server"。"They split panes, start each other, prompt each other"、"The skill is a Markdown instruction file for agents"。"every pane is marked working, blocked, or idle"。collie: "A mobile web interface for terminal-based AI agents, served over Tailscale"、"Status dashboard led by what needs your input"、"Tap to answer an AskUserQuestion prompt"、"Crews: several machines' Collies behind one URL"。Herdr, Inc. "We raised $6M"。docs に "No MCP or OpenTelemetry mentions"。

**agent-of-empires** ([repo](https://github.com/agent-of-empires/agent-of-empires)): "Works with Claude Code, Codex, OpenCode, Gemini CLI, Mistral Vibe and more"、"aoe add --cmd claude"。"A session manager for AI coding agents on Linux and macOS"、"aoe serve"、"PWA install on desktop and mobile"、"Docker, Podman, and Apple Containers sandboxing"。"TUI, web, CLI, and HTTP API surfaces"。ACP。"Maintained by the Agent of Empires community, with support from Mozilla.ai"。委譲は見つからなかった。

**mjolnir** ([repo](https://github.com/BrokkAi/mjolnir)、[site](https://mjolnir.brokk.ai)): "runs Claude Code, Codex, Kimi Code, Grok Build, and Muse Code sessions side by side"、"mj acp for stdio ACP clients"。Docker / Podman / EC2、Web viewer (Tailscale 経由)、"On Linux or macOS"。"built by the engineers at Brokk"。委譲・ワークフロー定義は見つからなかった。

**agentconnect** ([repo](https://github.com/agentconnect-md/agentconnect)、[site](https://agentconnect.md)): Claude Code、Codex、Grok Build、DeepSeek、Pi、他は ACP。契約か API キーのどちらでも。Docker Compose (console / Control Plane / Relay / PostgreSQL)、Helm。Agents / Sessions / Schedules / Tools & Skills / Knowledge / Daemons のコンソール。エージェントごとに runtime・model・workspace・tool・machine。.claude/skills と .agents/skills。ACP、MCP、OpenTelemetry (サイトの構成表)。運営主体は見つからなかった。

**Fusion** ([repo](https://github.com/Runfusion/Fusion)、[site](https://runfusion.ai)): "ACP + MCP agent interop (Gemini CLI, Claude, Cursor)"。Claude Code の名指しは無い。"Direct chat and per-task chat with any agent, on any model"。Electron (mac / Win / Linux)、Capacitor (iOS / Android)、`fn dashboard`、"Docker + headless deployment"。"Built-in mailbox between agents for delegation and hand-offs"、"Fusion speaks the same AGENTS.md format as Paperclip"。kanban / list / graph / terminal / diff、"nudge direction, tighten constraints, pause, or re-prompt"。OTLP。運営主体は見つからなかった。

**OpenClaw、Hermes Agent、Paperclip** は [docs/research/unified-ui-2026-09-18/](../unified-ui-2026-09-18/a-session-managers.md) と本調査で確認した。OpenClaw: [CLI バックエンド](https://docs.openclaw.ai/gateway/cli-backends) "Compatible agent turns share one warm Claude Code subprocess"、[ACP](https://docs.openclaw.ai/tools/acp-agents)、[Control UI](https://docs.openclaw.ai/web/control-ui) "each card shows the agent's identity, model, current work status, last activity"、"Subagent runs appear in inline transcript activity rows and the chat Tasks tab"。"Models and agent harnesses (Claude, Codex, local models) are plugins you can swap"。Hermes: [Claude Code](https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-claude-code) は claude -p か tmux、[Codex](https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-codex) は codex exec、[Kanban](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/kanban.md) "sub-grouping of the Running column by assignee"。Paperclip: "If it can receive a heartbeat, it's hired."、[ACP はコアにしない](https://github.com/paperclipai/paperclip/discussions/787)。

### 5.3 机上で棄却したものの根拠

- zeron: README "use the desktop release"、サイト "Available for macOS, Windows and Linux. iOS is on the way"。Web UI は見つからなかった。
- munder-difflin: Electron のデスクトップ app。統括エージェント "Michael" が CLI へ割り振る。常駐サーバ・スマホは見つからなかった。
- Orkas、Agent Teams、Superset、Emdash: 説明文と awesome list の分類でデスクトップ app。
- openswarm: README の構成図に claude-agent-sdk、Anthropic API キーを設定画面で入力。"現状 macOS 専用 (Windows / Linux は計画中)"。Codex の記述なし。
- Yao: README に claude / codex / CLI Agent の語が無い。docs の "Claude Code" は Yao の built-in agent の名前で "same sandbox capabilities, powered by Claude"。LICENSE は修正版 Apache 2.0 (Infinite Wisdom Software、50 名以上または年商 100 万ドル超は商用ライセンス)。
- takt: [configuration.md](https://raw.githubusercontent.com/nrslib/takt/main/docs/configuration.md) で claude は "headless CLI mode" と `TAKT_ANTHROPIC_API_KEY`、Codex は Codex SDK と `TAKT_OPENAI_API_KEY`。YAML の steps / persona / rules は v0.4 の部品として再考。
- open-multi-agent: "a library with no OMA backend"、ワークフローは TypeScript。Run Viewer は "task DAG, span waterfall, and per-task evidence"。YuanASI (深圳)。
- claudexor: "macOS for the desktop app; the CLI/daemon also run on Linux"、Web UI 無し。"quota-aware rotation across multiple Claude/Codex subscriptions"、"--delegate injects a SCOPED Claudexor MCP belt"。個人 (Anton)。
- qm: "Pi, OpenCode, Codex, and Claude Code all drive the same core"、"every harness tool call pauses for human approval"、Slack と Web。Y Combinator の組織。多人数向けで、全ツール呼び出しの承認が要件 R7 の縮小と合わない。
- Vibe Kanban: [会社の解散](https://www.vibekanban.com/blog/shutdown)、3 か月のリリース 1 回。Crystal: 2026-02 に終了し Nimbalyst へ。Conductor.build: 非公開ソース、Mac のみ、自前運用なし。
- n8n、LangGraph Studio、Open WebUI、Mastra Studio: いずれも汎用のコマンド実行・MCP・自作エージェントの道具で、Claude Code や Codex を起動・監視する専用機能は無い ([n8n Execute Command](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/)、[LangGraph Studio](https://docs.langchain.com/langgraph-platform/langgraph-studio)、[Open Terminal](https://docs.openwebui.com/features/open-terminal/)、[Mastra Studio](https://mastra.ai/docs/studio/overview))。
