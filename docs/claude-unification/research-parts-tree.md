# 部品の調査: セッションのツリー

- 更新: 2026-11-03 JST
- 種別: 調査記録。[部品の調査の計画](research-plan.md) の 4.2 節の結果。設計の結論 (どの部品で作るか) は書かず、候補と隙間までを書く。
- 物差し: [Claude 一本化の要件](requirements.md) の 3 節と 4 節。各部品に、満たす要件の番号を付ける。
- 前提: 公式の機能の事実は、断りがないかぎり [入口と spawn の調査](research-entry-and-spawn.md) のとおりとし、4.2 節の「確かめ直す事実」だけを取り直した。公式の資料は 2026-11-03 に `https://code.claude.com/docs/en/<ページ>.md` から取得した。手元の確認は開発 PC (macOS) の Claude Code 2.1.308 で行い、ミニ PC (Ubuntu) では確かめていない。

## 1. 答える問い

計画の 4.2 節の問いを、次の 5 つに分けて答える。

- Q1 入口が、役と作業を割り当てたセッションを起こせるか (3.1-3、3.2-1、C2)
- Q2 起こされたセッションが、さらに子を起こせるか (3.1-4)
- Q3 子の結果が、チャットではなく起こした側に返るか。子が親にメッセージを送れるか。判断がつかないものを一段上へ上げられるか (3.1-4、C3、C4)
- Q4 起こした先の途中経過が、入口に届くか (3.2-4、C8)
- Q5 起こしたセッションが Claude のセッションとして記録に残るか。Claude アプリで見えるか (3.1-3、C2)

## 2. 手元で確かめた事実 (2026-11-03、開発 PC、Claude Code 2.1.308)

オーナーの hook を発火させないよう、試験の `claude -p` にはすべて `--setting-sources ""` を付けた。

- 3 段の起動と結果の戻り: このセッション (Claude Desktop) の Bash から `claude -p` (親) を起こし、親の Bash から `claude -p` (孫) を起こさせた。孫の出力 `GRANDCHILD-OK-7731` を親が受け取り、親の最終出力 `PARENT-SAW: GRANDCHILD-OK-7731` がこのセッションに返った。入れ子の起動を止める仕組みは働かなかった。
- 記録: Bash から起こした `claude -p` に `--session-id` を付けると、その ID の会話の記録 (`~/.claude/projects/<フォルダ>/<ID>.jsonl`) ができた。孫の記録が残るかは確かめていない (孫の起動がこの PC のサンドボックスの通信の制限で失敗し、制限を外した再試験は自動判定に止められた)。
- 環境の引き継ぎ: 起こした `-p` の記録の `entrypoint` は `claude-desktop` だった。起こした側の環境変数 (`CLAUDE_CODE_ENTRYPOINT` など) が子に引き継がれる。
- 子から親へのメッセージ: Bash から起こした `claude -p` の子が、`ListAgents` でこのセッションを見つけ、`SendMessage` で `CHILD-TO-PARENT-3391` を送った。このセッションに、送り手の名前と返信の宛先 (`uds:` で始まるソケットのパス) が付いて届いた。
- 子から親へのメッセージの条件: 同じ子をこのセッションの Bash のサンドボックスの中で起こすと、`ListAgents` は「No reachable agents.」を返し、送れなかった。サンドボックスの外で起こすと、このセッションを含む同じ PC のセッションが一覧に出た。

## 3. 問いごとの部品

### Q1 役と作業を割り当てたセッションを起こす

使える部品

- Bash から起こす `claude -p` (3.1-3、3.2-1、3.3-1)。役の設定は起動の引数で渡す。`claude --help` にある引数: `--append-system-prompt`、`--system-prompt`、`--settings` (hook と設定)、`--setting-sources`、`--agents` (JSON で役の定義)、`--agent` (主の役)、`--plugin-dir`、`--mcp-config` と `--strict-mcp-config`、`--model`、`--effort`、`--permission-mode`、`--tools`・`--allowedTools`、`--session-id`、`-n`/`--name`、`--add-dir`。作業の場所は起動するフォルダで分け、そのフォルダの `CLAUDE.md` が読まれる。
- バックグラウンドのセッション `claude --bg` (3.1-3、3.2-1)。[agent view](https://code.claude.com/docs/en/agent-view) の資料は `claude --agent code-reviewer --bg "..."` の形で、定義済みの役を主にして起こす例を示す。`--settings`、`--setting-sources`、`--plugin-dir`、`--mcp-config`、`--add-dir` は背景のセッションに引き継がれる。手元では起こしていない。
- 対話の `claude --remote-control [name]` を tmux の窓で起こす (3.1-3)。`claude --help` は「Remote Control を有効にした対話のセッションを始める」とする。実践者の theptip は、Remote Control の親のセッションが作業ごとに tmux の窓と Remote Control のセッションを作る形を [Hacker News のコメント](https://news.ycombinator.com/item?id=48960288) に書いている ("master RC session that creates new tmux windows and Claude RC sessions for each new code trajectory")。スクリプトは公開されていない。手元では起こしていない。
- サブエージェント (3.2-1)。定義のファイルか `--agents` で役を渡せるが、入口のセッションの中で動く担い手で、別のセッションではない ([sub-agents](https://code.claude.com/docs/en/sub-agents))。3.1-3 の「別のセッション」には当たらない。

証拠

- `--bg` の制約 ([agent view](https://code.claude.com/docs/en/agent-view)): `--bg` と `-p` を併用すると、セッションを作る前に断られる。信頼していないフォルダでスクリプトから `--bg` を起こすと、確認の画面が出せないため `Workspace not trusted` で終わる。
- agent teams ([agent-teams](https://code.claude.com/docs/en/agent-teams)) は実験的で既定は無効。`-p` のセッションでは仲間を起こさない ("In non-interactive mode with the `-p` flag, including Agent SDK sessions, Claude doesn't spawn teammates")。
- [Projects](https://code.claude.com/docs/en/claude-projects) は、取りまとめの会話が claude.ai の上にあり、スレッドを機械で動かすには Remote Control と、フォルダごとの「Allow once」の操作が要る。取りまとめ役がミニ PC のセッションではないので、3.1-2 に合わない。

埋めるべき隙間

- 役ごとの引数の組み立て: 役の名前から、指示のファイル・`--settings`・`--plugin-dir`・`--mcp-config`・作業のフォルダ・`--session-id`・環境変数を組み立てて起動の行にする部品は、公式には無い。起こした側の環境変数が子に引き継がれるので、子に渡す環境は明示して組み立てる必要がある。

### Q2 起こされたセッションが、さらに子を起こす

使える部品

- `claude -p` の入れ子 (3.1-4)。3 段まで手元で動いた (2 節)。公式の資料に入れ子の `-p` の深さの上限の記述は見当たらない。
- サブエージェントの入れ子 (3.1-4 の参考)。既定で主の会話から 3 層まで起こせ、`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` で変えられる ([sub-agents](https://code.claude.com/docs/en/sub-agents): "By default, a subagent can spawn subagents of its own, up to three layers below the main conversation.")。

証拠

- agent teams は 1 段まで ([agent-teams](https://code.claude.com/docs/en/agent-teams): "No nested teams: teammates cannot spawn their own teammates. Only the lead can manage the team.")。リーダーは起動したセッションに固定される。
- `--bg` のセッションが Bash から別の `--bg` を起こせるかは、資料に記述が無く、確かめていない。

埋めるべき隙間

- 入れ子の `-p` で、各段が自分の起こした子を覚えておく台帳。公式の機能は `-p` の親子の関係を記録しない (agent view は背景のセッションを並べるだけで、起こした側を表示しない。サブエージェントと仲間は行に出ない)。

### Q3 子の結果が起こした側に返る

使える部品

- `claude -p` の標準出力 (3.1-4、C3)。最終出力が起こした側の Bash に返る (2 節)。`--output-format json` にすると `result` と `session_id` が返る ([headless](https://code.claude.com/docs/en/headless))。この経路では、結果はチャット (オーナー) ではなく起こした側にだけ返る。
- セッションの間のメッセージ `SendMessage` (3.1-4、C3)。子から親へ送れた (2 節)。資料の要点 ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging)):
  - 受け手は、作業中ならツールの呼び出しの合間に読み、待機中なら新しいターンを始める。
  - 受け手は返信の宛先を受け取り、`SendMessage` で送り手に返せる。
  - `claude -p` も受け口のソケットを持ち、一覧に出る。無人の `-p` に受けさせるには、`--settings` で `crossSessionInbound` を `accept` にする ("To let a `-p` worker take messages unattended, start it with `crossSessionInbound` set to `accept` in its `--settings` value.")。`--bare` で起こすと受け口を持たない。
  - 既定では、受け手が権限の確認を求めるモードなら届き、送り手が確認を飛ばすモード (bypassPermissions) だと保留される。
  - Bash のサンドボックスからソケットに届くかは `sandbox.network.allowAllUnixSockets` と `sandbox.network.allowUnixSockets` で決まる。
  - メッセージは文だけで、1 通の上限は同じ機械で約 100 万文字。
  - 別の機械のセッションへは Remote Control を通して届く。
- 待機の知らせ `notify_when_idle` (3.1-4)。別のセッションが次に待機に入るか終わったときに 1 回知らせる。主の会話の Claude だけが、同じ機械のセッションにだけ頼める。12 時間で切れる。
- `claude agents --json --all` (3.1-4)。資料は「背景の仕事を監督する別の Claude のセッション」がこれを読む使い方を挙げる ("another Claude session that supervises background work")。`state` (`working`・`blocked`・`done`・`failed`・`stopped`) と `waitingFor` が読める。`--bg` のセッションの結果は人にだけ報告されるので ([agents](https://code.claude.com/docs/en/agents): "agent view sessions report results only to you")、起こした側に返すにはこれか `SendMessage` を使う。
- サブエージェントの結果は、起こした会話に返る ([agents](https://code.claude.com/docs/en/agents))。仲間 (agent teams) は、終わるとリーダーに最終の答えを付けて知らせる。

証拠

- 2 節の 3 段の起動と、子から親へのメッセージ。
- 他のセッションからのメッセージは、承認の代わりにならず、設定を変えさせられず、`/compact` などのコマンドとしても実行されない ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging))。

埋めるべき隙間

- 長い作業の結果の受け取り: `-p` を Bash で前に起こすと、子が終わるまで起こした側のターンが止まる。Bash を背景で動かして出力のファイルを後で読むか、子に `SendMessage` で返させるかを、起こす側の手順に書く必要がある。
- 一段上へ上げる仕組み: 「判断がつかないものを、起こした側のさらに上へ」上げる公式の機能は無い。各段が自分を起こした側の宛先 (セッションの名前か ID) を知っている必要があり、Q2 の台帳と、役の指示に書く上げ方の規則が要る。判断待ちの置き場所は [計画](research-plan.md) の 4.3 節で扱う。

### Q4 途中経過が入口に届く

使える部品

- 子が `SendMessage` で途中経過を送る (3.2-4、C8)。Q3 と同じ経路。
- `claude agents --json --all` を入口が読む (3.2-4、C8)。`--bg` で起こした場合に使える。資料は、セッションが自分の言葉で進み具合を出すなら `$CLAUDE_JOB_DIR/tmp` に自分のファイルを書かせる形を勧める。
- 受け口のソケットへのスクリプトからの投稿 (3.2-4)。セッションは受け口のパスを `CLAUDE_CODE_MESSAGING_SOCKET` で hook と Bash に渡し、自分の子のプロセスからの投稿は、受け入れの設定が無いときも届ける ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging) の「Own-child messages」)。孫や曾孫の hook が入口のソケットに投稿したとき、自分の子として扱われるかは確かめていない。
- Remote Control でつないだ端末には、そのセッションのサブエージェントと dynamic workflow の進み具合が出る ([remote-control](https://code.claude.com/docs/en/remote-control))。別のセッションとして起こした担い手には当たらない。

証拠

- 2 節の、子から親へのメッセージ。
- 先行事例では、`PostToolUse` の hook が進み具合を送る形 (claude-hub、[先行事例の調査](research-prior-art.md) の 5)、起動の記録を見張る形 (Neutron の `running-agents.jsonl`) がある。

埋めるべき隙間

- 途中経過をいつ・何を送るかの規則 (役の指示か hook)。孫の途中経過を入口まで届けるには、各段が中継するか、孫が入口の宛先を知る必要がある。どちらにするかは設計で決める。

### Q5 記録に残るか、Claude アプリで見えるか

使える部品

- `claude -p` の会話は既定で記録に残り、`--resume` で戻せる (C2)。`--no-session-persistence` を付けたときだけ残らない (`claude --help`)。2 節で、子の記録ができたことを確かめた。
- `--bg` のセッションは、止めたあと `claude attach <id>` や `claude --resume` で開き直せる (`claude --help`)。
- `claude --remote-control` で起こした対話のセッションは、Remote Control のセッションとして Claude アプリと claude.ai/code の一覧に出る ([remote-control](https://code.claude.com/docs/en/remote-control))。

証拠

- Remote Control は、明示して起動したとき (`claude remote-control`、`claude --remote-control`、`/remote-control`) か、`remoteControlAtStartup` を `true` にして「対話のセッションが始まるとき」にだけつながる ([remote-control](https://code.claude.com/docs/en/remote-control): "connect automatically when an interactive session starts")。`-p` は対話のセッションではないので、資料の上では Claude アプリに出ない。
- `--bg` のセッションが `remoteControlAtStartup` でアプリに出るかは、資料に記述が無く、確かめていない。この PC の CLI と Desktop は会社のアカウントで動いているため、個人のアカウントでのアプリの表示は試していない。

埋めるべき隙間

- 3.2-4 は、起こした先をオーナーが直接見ることを求めていない。アプリで見えることは要件ではないので、記録に残ること (C2) を満たせば足りる。アプリで見せたい場合だけ、起こす先を対話の `--remote-control` にする必要がある。

## 4. 公開されているスクリプトと OSS

計画の 3 節の条件を当てた結果を各項目に書く。順位は付けない。最後のコミットの日付は 2026-11-03 に `gh api` で取ったもの。

### 4.1 ツリーとエスカレーションを持つもの

- Gas Town ([gastownhall/gastown](https://github.com/gastownhall/gastown)、旧 steveyegge/gastown)
  - MIT。最後のコミット 2026-10-28。
  - 起動: 役の既定のコマンドは `claude --dangerously-skip-permissions` ([internal/config/agents.go:235-236](https://github.com/gastownhall/gastown/blob/466aa41c83ee73b1fa0eb79eb9d172fb1eca9476/internal/config/agents.go#L235))。tmux のセッションに起こす。
  - 役の設定: 役ごとの settings を `--settings` で渡し ([internal/config/loader.go:1537](https://github.com/gastownhall/gastown/blob/466aa41c83ee73b1fa0eb79eb9d172fb1eca9476/internal/config/loader.go#L1537))、役の本文は `SessionStart` の hook (`gt prime --hook`) で入れる。
  - 結果の戻り: 作業者は `gt done` でブランチを push し、マージの依頼を台帳 (Beads、git で管理する) に作る。連絡は `gt mail`。
  - エスカレーション: README は "Agents that hit blockers escalate via `gt escalate`, which creates tracked beads routed through the Deacon, Mayor, and (if needed) Overseer." と書く ([README](https://github.com/gastownhall/gastown/blob/466aa41c83ee73b1fa0eb79eb9d172fb1eca9476/README.md))。
  - 深さ: Mayor → Rig → Polecat などの固定の役の階層。深さの上限は記載なし。
  - 条件: 手を加えていない `claude` を起こす (条件 1)。tmux 3.0 以上で動き、操作の中心は `gt` の CLI (条件 2・3)。ミニ PC での動作は確かめていない。

- multi-agent-shogun ([yohey-w/multi-agent-shogun](https://github.com/yohey-w/multi-agent-shogun))
  - MIT。最後のコミット 2026-08-06。
  - 起動: 将軍・家老・足軽を tmux の窓に `claude --model ... $PERMISSION_FLAG` の send-keys で起こす ([shutsujin_departure.sh:704](https://github.com/yohey-w/multi-agent-shogun/blob/aff8dc8495da26a2aad582257457655fa953b57e/shutsujin_departure.sh#L704))。
  - 役の設定: 起動の引数では渡さず、各セッションが tmux の窓の変数で自分の役を判別し、`instructions/<役>.md` を読む (`CLAUDE.md` の Session Start の手順)。
  - 結果の戻り: 報告は YAML のファイルと受け箱への書き込み。家老から将軍へは受け箱を使わず `dashboard.md` を更新するだけ ([CLAUDE.md](https://github.com/yohey-w/multi-agent-shogun/blob/aff8dc8495da26a2aad582257457655fa953b57e/CLAUDE.md) の Report Flow)。
  - 人の判断待ち: "ALL items needing Lord's decision → dashboard.md 🚨要対応 section." (同じ CLAUDE.md の Action Required Rule)。家老の指示には、要対応が増えたら ntfy で知らせる記載がある。
  - 深さ: 固定の 3〜4 層。足軽は子を起こさない。
  - 条件: README は定額のプランで動かす理由を書く (条件 1)。tmux だけで動く (条件 2・3)。

- overstory ([jayminwest/overstory](https://github.com/jayminwest/overstory))
  - MIT。最後のコミット 2026-05-28。
  - 起動: 既定は `claude -p --output-format stream-json --input-format stream-json` ([src/runtimes/claude.ts:252-264](https://github.com/jayminwest/overstory/blob/ff38f3f76f084abcc34f519bcaa69580f6e53cf1/src/runtimes/claude.ts#L252))。tmux の対話の形も選べる。
  - 役の設定: 作業者ごとの worktree に `.claude/CLAUDE.md` を生成し、`claude` に読ませる。役の定義は `agents/*.md`。
  - 結果の戻り: 自前の SQLite のメール。メールが届くと `claude --resume <session-id>` で次のターンを起こして渡す ([src/agents/headless-mail-injector.ts](https://github.com/jayminwest/overstory/blob/ff38f3f76f084abcc34f519bcaa69580f6e53cf1/src/agents/headless-mail-injector.ts) の冒頭のコメント)。
  - エスカレーション: メールの種別に `escalation` があり、lead が blocker を coordinator に上げる。人へ非同期に知らせる仕組みは記載なし。
  - 深さ: `agents.maxDepth` の既定は 2 ([src/config.ts:59](https://github.com/jayminwest/overstory/blob/ff38f3f76f084abcc34f519bcaa69580f6e53cf1/src/config.ts#L59))。
  - 条件: 手を加えていない `claude` を起こす (条件 1)。CLI が中心 (条件 2)。Linux での動作の記載は見つけていない。

- CLI Agent Orchestrator ([awslabs/cli-agent-orchestrator](https://github.com/awslabs/cli-agent-orchestrator))
  - Apache-2.0。最後のコミット 2026-11-03。
  - 起動: tmux の中の対話の `claude` ([src/cli_agent_orchestrator/providers/claude_code.py:563](https://github.com/awslabs/cli-agent-orchestrator/blob/3dd21d5b698612ce6dab25041724627fd308061b/src/cli_agent_orchestrator/providers/claude_code.py#L563))。
  - 役の設定: 役のプロファイルから `--append-system-prompt-file` (同じファイルの 646 行)、`--agent`、`--model`、`--mcp-config` を組み立てる。
  - 結果の戻り: 割り当ての道具の説明に "The worker can send results back by calling send_message without receiver_id — it routes to this terminal automatically." とある ([mcp_server/server.py:570](https://github.com/awslabs/cli-agent-orchestrator/blob/3dd21d5b698612ce6dab25041724627fd308061b/src/cli_agent_orchestrator/mcp_server/server.py#L570))。結果は割り当てた側の受け箱に届く。
  - 深さ: 作業者も MCP サーバーを持てば割り当てられる。2 層の例がある。上限は記載なし。人へ上げる経路は記載なし。
  - 条件: 手を加えていない `claude` を起こす (条件 1)。CLI・MCP・HTTP が中心 (条件 2)。Codespaces と Kubernetes の例があるが、ミニ PC での動作は確かめていない。

- Kai ([dcellison/kai](https://github.com/dcellison/kai))
  - Apache-2.0。最後のコミット 2026-10-15。
  - 起動: `claude --bare --input-format stream-json --output-format stream-json ... --permission-mode bypassPermissions` を常駐の子プロセスとして起こす ([src/kai/claude.py:270-303](https://github.com/dcellison/kai/blob/aef6407ba3649ccee89468ae526811c430594599/src/kai/claude.py#L270))。
  - 役の設定: コードのコメントは "Kai supplies every canonical instruction source explicitly." とし、`--bare` で `CLAUDE.md`・skill・hook・plugin・MCP・自動の記憶を読ませない。
  - 結果の戻り: 子の stream-json の `result` を読み、委譲の結果を共有の会話に残す。
  - 深さ: 委譲の方針に `max_depth: int = 3`、`max_fan_out: int = 3` などを持つ ([src/kai/workshop/agent_delegation.py:79-83](https://github.com/dcellison/kai/blob/aef6407ba3649ccee89468ae526811c430594599/src/kai/workshop/agent_delegation.py#L79))。
  - 条件: 条件 1 に疑いがある。手元の `claude --help` は `--bare` について "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)." とする。一方、Kai の HN の投稿は定額のログインで動くとし、コードのコメントは `~/.claude/.credentials.json` の OAuth の資格情報に触れている。今のバージョンが定額のログインで動くかは確かめていない。

- Neutron ([rjunee/neutron](https://github.com/rjunee/neutron))
  - Apache-2.0。最後のコミット 2026-10-10。
  - ブログの `scripts/spawn-agent.sh` はリポジトリに無く、TypeScript の実装 (`agent-dispatch/service.ts`) に置き換わっている。
  - 起動: 対話の `claude` に `--settings`、`--agents`、`--append-system-prompt-file`、`--mcp-config`、`--dangerously-load-development-channels` を付ける ([runtime/adapters/claude-code/persistent/build-repl-argv.ts:138-186](https://github.com/rjunee/neutron/blob/095fd44a1761e1429de44dbe7822ab3683cae7a1/runtime/adapters/claude-code/persistent/build-repl-argv.ts#L138))。
  - 結果の戻り: 作業者の結果を元のチャットの話題に投稿し、元のセッションにも流す。
  - 深さ: `MAX_SPAWN_DEPTH = 1`、`MAX_CHILDREN_PER_AGENT = 5` ([runtime/subagent/registry.ts:14-15](https://github.com/rjunee/neutron/blob/095fd44a1761e1429de44dbe7822ab3683cae7a1/runtime/subagent/registry.ts#L14))。
  - 条件: README は `claude setup-token` か API キーで `claude` を起こすとする (条件 1)。入口が Telegram の話題ごとに分かれる形で、3.1-1 の画面とは違う。中の仕組みだけを参考にする。

- Tmux-Orchestrator ([Jedward23/Tmux-Orchestrator](https://github.com/Jedward23/Tmux-Orchestrator))
  - ライセンスの記載なし (コードの再利用はできない)。最後のコミット 2025-07-14。
  - 起動と役の設定: 手順書 (`CLAUDE.md`) が、tmux に `claude` を send-keys で起こし、役の説明の文を send-keys で入れる手順を書く。
  - 結果の戻り: `tmux capture-pane` で読む。Orchestrator → Project Manager → 開発者の 3 層の図と、詰まったら上へ上げる規則がある。
  - 条件: パスが作者の Mac に固定されており、手順書と小さなスクリプトの集まり。形の参考にとどまる。

### 4.2 1 段の親子で結果を返すもの

- claude-code-mcp ([steipete/claude-code-mcp](https://github.com/steipete/claude-code-mcp))
  - MIT。保管済み (archived)。最後のコミット 2026-05-15。
  - `claude -p` を MCP の道具として包み、標準出力を道具の戻り値として返す ([src/server.ts:564](https://github.com/steipete/claude-code-mcp/blob/2e401f3ed81d32435ca6cfe85a3ac1404d318c84/src/server.ts#L564))。セッションの ID を渡すと `--resume` で同じ会話を続ける。役を渡す引数は無い。

- cli-delegate ([isCopyman/cli-delegate](https://github.com/isCopyman/cli-delegate))
  - MIT。最後のコミット 2026-08-21。
  - Claude Code の skill から `claude -p ... --output-format json --bare` を子として起こし、JSON の `result` と `sessionId` を返す ([skills/cli-delegate/scripts/lib/backends.mjs:163-176](https://github.com/isCopyman/cli-delegate/blob/ba09a8d967f1974ebd623326898034637ab59534/skills/cli-delegate/scripts/lib/backends.mjs#L163))。`--settings` を渡せる。
  - Claude の中から Claude を起こすことを、`--settings` が無いかぎり既定で断る (同じファイルの 110 行)。
  - 条件: `--bare` を付けるので、Kai と同じく条件 1 に疑いがある。

- Instar ([JKHeadley/instar](https://github.com/JKHeadley/instar))
  - MIT。最後のコミット 2026-11-03。
  - 自前のサーバーの `POST /sessions/spawn` を skill から呼び、tmux の対話か `claude --dangerously-skip-permissions ... -p` で起こす ([src/core/frameworkSessionLaunch.ts:1011-1024](https://github.com/JKHeadley/instar/blob/f540bfcb727ce47c2f914a002a4ca79083c1bae8/src/core/frameworkSessionLaunch.ts#L1011))。
  - 結果は tmux の画面を `capture-pane` で読んで返す。親子の深さの制限は記載なし。README は API キーか定額の契約で動くとする。

- AgentWire ([dotdevdotdev/agentwire-dev](https://github.com/dotdevdotdev/agentwire-dev))
  - Apache-2.0。最後のコミット 2026-11-03。
  - リーダーのセッションが tmux の窓に作業者を起こす。役の指示をファイルに書き出し `--append-system-prompt "$(<file)"` で渡し、`--tools`・`--disallowedTools`・`--model` も役から組み立てる ([agentwire/core.py:668-704](https://github.com/dotdevdotdev/agentwire-dev/blob/399f6c18d58c97671dd7286b3a15e1aea114a58d/agentwire/core.py#L668))。
  - 結果: 作業者は待機に入ると要約を `.agentwire/worker-*.md` に書いて終わる。親を持つ作業者は `agentwire msg send --to <parent>` で返す。README に Ubuntu の手順がある。

- CommandMate ([Kewton/CommandMate](https://github.com/Kewton/CommandMate)) と skill 集 ([Kewton/commandmate-skills](https://github.com/Kewton/commandmate-skills))
  - ともに MIT。最後のコミットは 2026-11-02 と 2026-10-27。
  - tmux の対話の `claude` を worktree ごとに起こす ([src/lib/session/claude-session.ts:813](https://github.com/Kewton/CommandMate/blob/6752d53dd941e63ef3a25104e504e99a8fb24def/src/lib/session/claude-session.ts#L813))。
  - 窓口は `commandmate ask <worktree-id> --instance <id> "<依頼文>" --json` で頼み、相手のターンが終わるまで待って、会話の記録の末尾を受け取る (`cmate-delegate` の skill)。

- Ruflo ([ruvnet/ruflo](https://github.com/ruvnet/ruflo)、旧 Claude Flow)
  - MIT。最後のコミット 2026-11-01。
  - 作業を 1 件ずつ `claude -p --output-format json` に流し、標準出力の `result` と `session_id` を取り込む ([v3/@claude-flow/cli/src/commands/hive-mind-worker.ts:133-160](https://github.com/ruvnet/ruflo/blob/5f3dacc54b7279e39b172d6027d7989791448e2e/v3/@claude-flow/cli/src/commands/hive-mind-worker.ts#L133))。ファイルの冒頭のコメントは "Workers are records, not processes" とし、作業者は常駐するセッションの木ではない。

- claude-swarm (parruda)
  - GitHub のリポジトリ (parruda/claude-swarm と parruda/swarm) は 2026-11-03 に取得できなかった (HTTP 404)。最後のコミットの日付は確かめていない。RubyGems の claude_swarm 1.0.11 (MIT) の中身による。
  - 主のインスタンスを `claude --append-system-prompt ... --mcp-config ... --settings` で起こし、子のインスタンスを MCP サーバーとしてつなぐ。親が子の `task` の道具を呼ぶと、子の結果が道具の戻り値として返る。後継の SwarmSDK は Claude Code を使わない。

- claude-hub ([miyashita337/claude-hub](https://github.com/miyashita337/claude-hub))
  - ライセンスの設定なし。最後のコミット 2026-11-01。
  - tmux の対話の `claude --session-id ...` と、`claude -p ... --output-format json` の両方で起こす ([supervisor/src/session/manager.ts:1152](https://github.com/miyashita337/claude-hub/blob/12b65fe7d3babf96b8f640bd0aa70436a9b1d925/supervisor/src/session/manager.ts#L1152))。Stop の hook を `--settings` で入れる。`-p` の結果は GitHub の Issue にコメントする。launchd 前提で、Linux の記載は見つけていない。

- agent-deck ([asheshgoplani/agent-deck](https://github.com/asheshgoplani/agent-deck))
  - MIT。最後のコミット 2026-11-02。
  - tmux の対話のセッションを管理する TUI。親子は 1 段だけで、子から起こしたセッションは 1 つ上の親に付く。
  - 監督役の conductor のセッションがほかのセッションを見張り、README は "answers routine questions, escalates the interesting ones to your phone" と書く。
  - 条件: 自前の TUI に価値があるので、conductor の仕組みだけを参考にする。

- そのほか (中身は確かめていない、または参考): [mvschwarz/openrig](https://github.com/mvschwarz/openrig) (Apache-2.0、役を持つ席の間で `rig send` とキューで渡す)、[nrslib/takt](https://github.com/nrslib/takt) (MIT、YAML の工程で `claude -p` を部品として動かし、人の確認点を書ける)、[frapercan/agent-farm](https://github.com/frapercan/agent-farm) (ライセンスの記載なし、YAML の役の定義から `claude -p` を tmux の窓に起こす)。

### 4.3 部品にしないもの

- 自前の画面が本体のもの (条件 2): [smtg-ai/claude-squad](https://github.com/smtg-ai/claude-squad) (AGPL-3.0)、[kbwo/ccmanager](https://github.com/kbwo/ccmanager) (MIT)、[markusbug/Orchestrator](https://github.com/markusbug/Orchestrator) (MIT)。どれも親子の関係と結果の戻しを持たない平らな管理。ccmanager は agent teams と自前の端末の管理がぶつからないよう `--teammate-mode in-process` を付けている。
- Agent SDK で動かすもの (条件 1、参考): adapt-toolkit/ours-fleet (FSL-1.1-Apache-2.0)、[anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks) の `claude_agent_sdk/`、[anthropics/claude-agent-sdk-demos](https://github.com/anthropics/claude-agent-sdk-demos)。
- Anthropic のリポジトリ: 組織の一覧から拾った [anthropics/claude-code](https://github.com/anthropics/claude-code)、[anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks)、[anthropics/claude-agent-sdk-demos](https://github.com/anthropics/claude-agent-sdk-demos)、[anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents) は、どれも親のセッションが `claude` の CLI で役を付けた子のセッションを起こして結果を受け取る実装ではなかった。一覧のすべてのリポジトリの中身までは確かめていない。公式に該当するものは 3 節の製品の機能 (サブエージェント、agent teams、背景のセッション、セッションの間のメッセージ) である。

## 5. つなぎのスクリプトが要る所

公式の機能と 4 節の OSS で埋まらないもの。

1. 役から起動の行を組み立てる部品 (Q1)。役の名前を受け取り、指示のファイル (`--append-system-prompt-file`)、`--settings` (役の hook と、子が受けるための `crossSessionInbound`)、`--plugin-dir`、`--mcp-config`、作業のフォルダ、`--session-id`、`--name`、子に渡す環境変数を組み立てて、`claude -p`・`claude --bg`・対話の `claude --remote-control` のいずれかで起こす。同じ形の公開の実装は、Neutron の `build-repl-argv.ts`、AgentWire の `core.py`、CAO の `claude_code.py`、Gas Town の役ごとの `--settings`。
2. 親子の台帳 (Q2、Q3)。誰が誰を起こしたか (起こした側のセッションの ID と名前、作業、状態) を記録する。結果を返す先と、一段上へ上げる先をここから引く。公式の機能は `-p` と `--bg` の親子の関係を記録しない。同じ役の公開の実装は、Kai の `runs` の表 (`parent_run_id`)、overstory の SQLite、Neutron の起動の記録、Gas Town の Beads。
3. 結果を起こした側へ返す手順 (Q3)。短い作業は `-p` の標準出力で受ける。長い作業は、子に `SendMessage` で返させるか、背景で動かした出力を後で読む。`SendMessage` を使うには、子をサンドボックスの外で動かすか、Bash のサンドボックスで受け口のソケットを許す (`sandbox.network.allowUnixSockets`)。`--bare` の子は受け口を持たない。
4. 一段上へ上げる規則 (Q3)。各段の役の指示に、判断がつかないものを起こした側へ送る書き方を入れ、2 の台帳から宛先を引く。入口に届いたものの扱いは 4.3 節 (判断を専門にする役と、オーナーの判断待ち) で扱う。公開の例は Gas Town の `gt escalate`、overstory のメールの `escalation`、multi-agent-shogun の `dashboard.md` の要対応の欄。
5. 途中経過を入口へ届ける手順 (Q4)。子が `SendMessage` で送るか、hook が入口の受け口に投稿するか、入口が `claude agents --json --all` か台帳を読む。孫の途中経過を、中継させるか入口へ直接送らせるかを設計で決める。
