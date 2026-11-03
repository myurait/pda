# 入口・会社のコネクタの経路・スマホへの通知の部品

- 更新: 2026-11-03 JST
- 種別: 調査記録。[部品の調査の計画](research-plan.md) の 4.1 節 (入口)、4.6 節 (会社のコネクタの経路)、4.7 節 (スマホへの通知) の結果。設計の結論は書かず、候補と隙間までにする。
- 物差し: [Claude 一本化の要件](requirements.md) の 3.1-1、3.1-2、3.1-6、3.2-5、3.2-6、C1、C9、C10、C11。
- 前提: Remote Control の server mode、Projects、セッションの間のメッセージの基本の振る舞いは [入口と spawn の調査](research-entry-and-spawn.md) の V1・V4・V6 にあり、ここでは繰り返さない。
- 出典: とくに書かないかぎり、2026-11-03 に取得した Claude Code の公式資料 (`https://code.claude.com/docs/en/<ページ>`)。GitHub のリポジトリのライセンス、アーカイブの有無、最後のコミットの日付は、同じ日に GitHub の API で取得した値。引用は取得した本文と照合した文だけを載せる。
- 手元の環境: 開発 PC の `claude` は 2.1.308、ミニ PC の `claude` は 2.1.293。開発 PC の `claude -p` の試験は、オーナーの hook を動かさない形 (`--setting-sources ""` か `--settings '{"disableAllHooks": true}'`) で、`--model haiku` で行った。ミニ PC は読むだけにした。

## 1. 入口 (4.1。3.1-1、3.1-2、C1)

### 1.1 Desktop とアプリから届き続けるもの

使える部品は、公式の Remote Control の 2 つの形である。

- server mode (`claude remote-control`): 今のミニ PC の常駐の形 ([deploy/claude-remote-control/claude-remote-control.service](../../deploy/claude-remote-control/claude-remote-control.service) の `ExecStart=/home/user/.local/bin/claude remote-control --name mini-pc`)。1 つのプロセスで複数のセッションを受け、起動時に 1 つのセッションを作っておく。server が作るセッションには `--settings` などの起動オプションを渡せず、設定ファイルと定義のファイルから設定を読む ([入口と spawn の調査](research-entry-and-spawn.md) の V1)。満たす要件: 3.1-1、3.1-2。
- 対話の形 (`claude --remote-control <名前>`、または `remoteControlAtStartup` を `true` にした対話のセッション): 1 つのプロセスが 1 つのリモートのセッションを持つ ([remote-control](https://code.claude.com/docs/en/remote-control): "each Claude Code instance supports one remote session at a time")。起動オプション (`--append-system-prompt`、`--settings`、`--agent` など) をそのまま付けられる。端末が要るので、ミニ PC では tmux などの中で動かす (同じページ: "start it inside `tmux` or `screen` to keep the session running after you disconnect from SSH")。満たす要件: 3.1-1、3.1-2。

届く先の画面について、資料で確かめたこと。

- 接続した端末は会話をそのまま見て、端末からも送れる。圧縮の進み具合と、どこで圧縮したかも端末に出る ([remote-control](https://code.claude.com/docs/en/remote-control) の "What connected devices see")。
- Remote Control のセッションは、claude.ai、モバイルアプリ、Claude Desktop から見て操作できる (同じページの Trusted Devices の節: "view or steer Remote Control sessions from claude.ai, the Claude mobile apps, or Claude Desktop")。
- 開発 PC の Claude Desktop は会社のアカウントで動いている ([入口と spawn の調査](research-entry-and-spawn.md) の 3 節)。個人のアカウントのミニ PC のセッションが、会社のアカウントの Desktop に出るとする記述は資料に無い。C1 の「PC の Claude Desktop」に、個人のアカウントでログインした Desktop が要るかは確かめていない (隙間 1.5-1)。

### 1.2 長く動かす間に文脈があふれたとき

公式の機能で続けられる。実践者の部品は hook の設定の例である。

- 自動の圧縮: 文脈が埋まりそうになると自動で圧縮し、会話は続く ([context-window](https://code.claude.com/docs/en/context-window): "Claude Code compacts automatically as you approach the limit, so a full context window doesn't end your session")。圧縮の後、システムプロンプトと出力のスタイルは効いたまま、プロジェクトの根の `CLAUDE.md` と自動の記憶はディスクから入れ直され、hook が足した文脈は会話と一緒に要約される。`SessionStart` の hook で `compact` に当てたものは、圧縮の後に動いて出力が文脈に足される (同じページの "What survives compaction" の表)。
- 圧縮の位置: `autoCompactWindow` (10 万〜100 万トークン) と `--autocompact` で、どこまで埋まったら圧縮するかを決められる ([settings-reference](https://code.claude.com/docs/en/settings-reference) の `autoCompactWindow`)。
- 放置中の圧縮: `idleCompaction` は既定で有効で、2.1.290 以上で効く。条件は、対話の端末・VS Code・Desktop のセッションであること、文脈が既定で 20 万トークンに達していること、最後の要求から約 1 時間たったことなど (同じページの `idleCompaction`)。server mode が作るセッションがこの条件に入るかは確かめていない。
- 手で圧縮する: `/compact <残す内容の指示>`。Remote Control の端末から `/compact` と `/autocompact` を送れる ([remote-control](https://code.claude.com/docs/en/remote-control) の Limitations)。
- 実践者の設定の例: [What survives compaction in Claude Code](https://dev.to/rulestack/what-survives-compaction-in-claude-code-and-how-to-keep-your-rules-alive-564p) (dev.to、rulestack) は、`SessionStart` の `matcher` を `compact` にして、ファイルの中身を出力する hook で規約を入れ直す形を示す。[Issue #43733](https://github.com/anthropics/claude-code/issues/43733) は、圧縮の後に読み直しを促す hook を置いても確実ではないという報告である。どちらも本文の引用は照合していない。

満たす要件: 3.1-2 (1 つのセッションを動かし続ける)。役ごとの規約を圧縮の後も効かせる仕組みは 4.4 節の調べる範囲である。

### 1.3 再起動の後に同じ会話を続ける手順

server mode と対話の形で、戻せる条件が違う。

server mode (今の形)

- 止めたあと同じフォルダで `claude remote-control` を起動すると、server が受けていたセッションをすべて戻す。`--continue` は最初に作ったセッションだけ、`--session-id <id>` は指定したセッションだけを戻す。どれも「about four hours after the server stopped」までで、過ぎたら新しいセッションになる ([remote-control](https://code.claude.com/docs/en/remote-control) の "Resume sessions after stopping the server")。
- 今の unit は `Restart=always`、`RestartSec=10`、`RestartMaxDelaySec=5min` で、プロセスが落ちても 4 時間の内に起動し直す。ミニ PC が 4 時間を超えて止まった場合 (停電、ログインの期限切れが 4 時間を超えて放置された場合) は、同じ会話に戻らない。
- [claude-rc-keep](https://github.com/Jwrede/claude-rc-keep) (MIT、最後のコミット 2026-10-25) の README は、server が作ったセッションを同じ形では戻せないと書く ("Sessions spawned by the `claude remote-control` server cannot be restored the same way")。`--session-id` で戻せるのは single-session mode だけで、ほかの `claude remote-control` がその機械で動いていないときだけ、とも書く。
- [systemd-claude-rc](https://github.com/DanielBaulig/systemd-claude-rc) (LICENSE のファイル無し、最後のコミット 2026-10-11): systemd が `claude remote-control` を直接起動する。`bin/claude-rc-serve` の 50 行目 `args=(remote-control --name "$name"` と 62 行目 `exec "$claude_bin" "${args[@]}"`。53 行目からのコメントで、`--no-create-session-in-dir` を付けない理由を書いている。今のミニ PC の unit と同じ形である。
- [claude-code-remote-control-unraid-plugin](https://github.com/Nebur692/claude-code-remote-control-unraid-plugin) (LICENSE のファイル無し、最後のコミット 2026-10-11): README の 117 行目に、設定したフォルダで同じセッションを `--continue` で戻し続ける ("always resumes the same ongoing session in its configured directory (`--continue`)") とある。

対話の形

- `claude --remote-control` で始めたセッションは、`claude --continue` か `claude --resume` で会話を戻すと、記録された Remote Control のセッションにつなぎ直す ([remote-control](https://code.claude.com/docs/en/remote-control): "To bring back a session you started with `claude --remote-control` or `/remote-control`, resume the conversation with `claude --continue` or `claude --resume`")。会話の記録は既定で 30 日残る (`cleanupPeriodDays`。[sessions](https://code.claude.com/docs/en/sessions))。4 時間の制約は資料に書かれていない。
- 戻すときに付け直すもの: `--mcp-config`、`--settings`、`--plugin-dir`、`--fallback-model`、`--add-dir`。`settings.json` の中身は起動のたびに読み直される。圧縮したセッションは、最後の圧縮の要約から続く ([sessions](https://code.claude.com/docs/en/sessions) の "What a resumed session restores")。
- [claude-tmux-service](https://github.com/ErcouldnT/claude-tmux-service) (MIT、最後のコミット 2026-09-29): watchdog が tmux のセッションを見張り、無ければ作り直す。README の 38〜39 行目で、初回は `claude --session-id <uuid>` で起動して ID を記録し、以後は `claude --resume <uuid>` でつなぎ直すと書く。42 行目で、`claude --continue` は最も新しい会話を拾うので使わないと書く。起動するのは `claude --remote-control` (16 行目)。
- [claude-rc-keep](https://github.com/Jwrede/claude-rc-keep): 1 分ごとに動いているセッションを記録し、止まったものを `claude --resume <id> --remote-control` で起動し直す (README の 13 行目)。対話の形のセッションは、再起動の後も同じ Web のセッションにつながる (83〜84 行目)。server が作ったセッションは `--fork-session` の写しとして一度だけ戻し、URL が変わる (95 行目)。

満たす要件: 3.1-2。

### 1.4 Remote Control のネットワーク断の後

- server mode: 機械は起きているのにネットワークに届かないと、約 10 分で諦めて `claude remote-control` のプロセスが終わる ([remote-control](https://code.claude.com/docs/en/remote-control): "Claude Code gives up after roughly 10 minutes and the `claude remote-control` process exits")。今の unit は落ちたら起動し直し、1.3 節の server mode の条件で戻る。
- 対話の形: ネットワークが戻るまで再試行し続け、自分でつなぎ直す (同じページ: "Claude Code retries for as long as the outage lasts and reconnects on its own when the network returns")。プロセスは終わらない。
- 対話の形で接続が切れた理由が出たときは、`/remote-control` でつなぎ直す。その間に圧縮で会話が書き換わっていた場合、使っていたリモートのセッションはアーカイブされる (同じページの "Reconnecting after a connection failure")。端末の無いところでこの操作をする方法は確かめていない。
- 30 分ほど届かないと、対話のセッションでも `could not reach the Remote Control server for about 30 minutes` で切れ、`/remote-control` でつなぎ直す (同じページの Limitations)。

### 1.5 埋めるべき隙間

1. 個人のアカウントの Desktop: 開発 PC の Desktop は会社のアカウントで動く。PC から入口に届く画面を何にするか (Desktop のアカウントを切り替えるか、別の PC か) は確かめていない。
2. server mode のまま 4 時間を超えて止まると同じ会話に戻らない。会話を ID で記録して戻す仕組みは、server mode の公式の機能には無い。対話の形に移す場合は、tmux とセッションの ID の記録と `--resume` を組む部品 (claude-tmux-service、claude-rc-keep) か、同じことをするつなぎのスクリプトが要る。
3. 対話の形で切断の理由が出たときの `/remote-control` を、端末無しで打つ手段。claude-rc-revive ([PyPI](https://pypi.org/project/claude-rc-revive/)、MIT、最後のコミット 2026-10-25) は tmux の窓に `/remote-control` を打ち込む部品として公開されているが、中身は確かめていない。
4. 圧縮の後に、入口の役の規約を確実に入れ直す方法 (4.4 節と重なる)。`SessionStart` の `compact` の hook は公式の機能で、確実さは実践者の報告が割れている。

## 2. 会社のコネクタの経路 (4.6。3.1-6、3.2-5、C9)

### 2.1 ミニ PC から開発 PC の Claude を呼ぶ部品

SSH で開発 PC の `claude -p` を起こす形 (公式の CLI)

- 呼び出しの行の形: `ssh <開発 PC> 'cd <作業フォルダ> && claude -p --output-format json "<依頼>"'`。結果は標準出力の JSON の `result` に入り、`session_id` を取れば `claude -p --resume <session_id>` で同じ会話に続きを頼める ([headless](https://code.claude.com/docs/en/headless) の "Continue conversations")。
- 定額のログイン: `--bare` を付けると定額のログインを読まない ("bare mode doesn't use your subscription login")。付けない形で使う。
- 承認の扱い: 2.1.302 以上の `-p` は、何も指定しないと Manual mode で始まり、承認が要る呼び出しは拒まれる (同じページの "Auto-approve tools")。`--allowedTools`、`--permission-mode`、`--permission-prompts none` で扱いを決める。
- 満たす要件: 3.1-6、3.2-5 (結果が標準出力で入口に返る)。C11 については、開発 PC の側は会社のアカウントの定額のログインで動く (v0.3 と同じ)。

`claude mcp serve` (公式の CLI)

- 公式の資料は、Claude Code の道具を MCP の相手に出すものと書く ("This MCP server only exposes Claude Code's tools to your MCP client"。[mcp](https://code.claude.com/docs/en/mcp) の "Use Claude Code as an MCP server")。通信は stdio。
- 手元の 2.1.308 で `tools/list` を送ると、返ったのは組み込みの道具 (`Agent`、`Bash`、`Read`、`Edit`、`Write`、`WebFetch`、`SendMessage` など 30 個) だけで、`mcp__` で始まる道具 (会社のコネクタ) は無かった。依頼の文を受けて開発 PC の Claude が答えを返す道具も無い。
- 開発 PC の `Bash` をミニ PC に出すことになり、開発 PC の画面やブラウザーを触れない形 (3.1-6 の前提) に合わない。`Agent` の道具を通して会社のコネクタを使えるかは確かめていない。

別のマシンの Claude Code を MCP の道具にする公開の部品

- [steipete/claude-code-mcp](https://github.com/steipete/claude-code-mcp) (MIT、アーカイブ済み、最後のコミット 2026-05-15): `claude_code` という 1 つの道具で依頼の文を受け、`claude -p` を起こす。`src/server.ts` の 564 行目 `claudeProcessArgs.push('-p', processedPrompt);`、通信は 626 行目 `const transport = new StdioServerTransport();` で stdio だけ。548〜549 行目で、既定は `--dangerously-skip-permissions`、`permissionMode` を渡すと `--permission-mode` を付ける。`--tools`、`--mcp-config`、`--allowedTools` を渡す口は無い。定額のログインは、手で一度ログインした `claude` をそのまま使う形 (README)。別のマシンへ届ける仕組みは持たない。ミニ PC から使うには、SSH の上で stdio を通す形を組む必要があり、その形は確かめていない。
- [KunihiroS/claude-code-mcp](https://github.com/KunihiroS/claude-code-mcp) (MIT、アーカイブ済み、最後のコミット 2026-08-25): 同じ種類の部品で、保守をやめている。
- [jthack/dm-other-claudes](https://github.com/jthack/dm-other-claudes) (GitHub のライセンス判定は無し、LICENSE のファイル無し、最後のコミット 2026-04-12): MCP ではなく、Bun のスクリプトを skill から呼ぶ形。`dm-claude.ts` の 141〜147 行目で `const remoteParts = ["claude"];`、`remoteParts.push("-p", "--output-format", "json");` を組み、`--resume`、`--max-turns`、`--model` を足し、170 行目と 195 行目で `ssh` を起こす。道具を絞るフラグを渡す口は無い。ミニ PC に Bun が要る。

セッションの間のメッセージ (公式の機能)

- 別の機械の自分のセッションに届くのは、相手がその機械の Remote Control で動いていて、送る側も Remote Control につないでいるときである ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging): "a session on another of your machines appears only when it runs with Remote Control and this session is connected as well")。届く先は「your sessions」と書かれ、別のアカウントのセッションに届くとする記述は無い。
- 返事: Remote Control につないでいない側から送ったものには返事の宛先が付かない ("the message still goes through, but without a reply address")。送れるのは文だけで、会話の履歴やファイルは渡らない。
- 入口は個人のアカウント、開発 PC は会社のアカウントなので、資料からはこの経路は使えない。会社の組織で Remote Control が有効かも確かめていない。

### 2.2 開発 PC 側で使える道具を会社のコネクタに限る方法

開発 PC の `claude -p` で、起動の形ごとに、読み込まれた MCP と道具を起動時の情報 (`--output-format stream-json` の `system/init`) で確かめた。

- `--setting-sources ""`: plugin の MCP だけが読み込まれ、claude.ai のコネクタは読み込まれなかった。v0.3 で、ユーザーの範囲を外すと claude.ai のコネクタが読み込まれないと確かめたこと ([v0.3 の決定](../reports/v0.3-decision.md) の「置き場所と橋渡し」) と同じである。
- `--settings '{"disableAllHooks": true}'`: hook は止まり、claude.ai のコネクタ 22 個、ユーザーの範囲の MCP 2 つ、plugin の MCP 2 つが読み込まれた。組み込みの道具は `Bash`、`Read`、`Edit`、`WebFetch` などを含む 33 個。
- 上に `--strict-mcp-config` を足す: MCP は 0 個。`--mcp-config` で渡したものだけを使う形で、claude.ai のコネクタも外れる (v0.3 の記録の「claude.ai のコネクタは `--mcp-config` では渡せない」と合わせると、この形では会社のコネクタを使えない)。
- 上に `--restricted` を足す: `Bash`、`WebFetch` などが外れ、ユーザーの設定ファイルも読まれず、MCP は plugin のものだけになり、claude.ai のコネクタは外れた。
- 上に `--tools ""` を足す: 組み込みの道具は 0 個になり、MCP の道具 154 個が残った。`--tools Read` では組み込みの道具は `Read` だけになり、MCP は同じく残った。CLI の説明は "Specify the list of available tools from the built-in set. Use "" to disable all tools" (`claude --help`)。

ここから、組み込みの道具を外してコネクタだけを残す口は `--tools` だと分かる。満たす要件: 3.1-6 (開発 PC の画面・ブラウザー・シェルをミニ PC に出さない)。残る点。

- 個々のコネクタに絞るには、`--allowedTools` に `mcp__claude_ai_<名前>__*` の形の規則を書いて自動で許し、ほかを `-p` の Manual mode で拒ませる形が考えられる。この形は確かめていない。claude.ai のコネクタを名前で外す `deniedMcpServers` (例 `"claude.ai Slack"`) は資料にある ([mcp](https://code.claude.com/docs/en/mcp) の "Disable claude.ai connectors")。
- 組織が connector の道具に付けた `ask` は、`-p` の `dontAsk` では許す規則があっても拒まれる ([headless](https://code.claude.com/docs/en/headless) の `dontAsk` の項)。
- `-p` では MCP の OAuth のサインインを行えないので、認証の要る MCP は開発 PC の対話のセッションで先にサインインしておく ([mcp](https://code.claude.com/docs/en/mcp): "A `claude -p` or Agent SDK run has no `/mcp` panel, so Claude Code can't run the OAuth flow there.")。claude.ai のコネクタの認証は claude.ai の側で行う (同じページの "Use MCP servers from claude.ai")。
- SSH の接続そのものを 1 つのコマンドに縛る部品として、OpenSSH の `authorized_keys` の `command="..."` と `restrict` がある ([sshd(8)](https://man.openbsd.org/sshd): "Specifies that the command is executed whenever this key is used for authentication." "The command supplied by the user (if any) is ignored.")。決めたコマンドを動かすだけの鍵にできる。

### 2.3 資料で確かめられることと、手元で確かめること

資料で確かめられたこと

- claude.ai のコネクタは、有効な認証が claude.ai の定額のログインのときだけ読み込まれる。`ANTHROPIC_API_KEY`、`apiKeyHelper`、`claude setup-token` のトークンでは読み込まれない ([mcp](https://code.claude.com/docs/en/mcp) の "Use MCP servers from claude.ai")。
- 端末で動かす `claude` (CLI) は、コネクタを自分で claude.ai から取ってくる。Desktop のセッションは、Desktop がコネクタを渡す。CLI の側には `disableClaudeAiConnectors`、`ENABLE_CLAUDEAI_MCP_SERVERS`、`deniedMcpServers` が効き、Desktop の側には効かない (同じページの "How connectors reach Claude Code")。
- 組織が connector の道具に付けた `blocked` は、CLI がその道具を Claude に見せない形で効く (同じページの "Organization controls on connector tools")。

手元で確かめたこと (2026-11-03)

- 2.2 節の起動の形ごとの読み込み。
- 開発 PC の macOS のリモートログイン (`com.openssh.sshd`) は、`launchctl print-disabled system` の表示で有効だった。ミニ PC から開発 PC への SSH の接続は、ミニ PC の `~/.ssh/config` に接続先の登録が無く、試していない。

手元で確かめていないこと

- SSH で入ったときに、開発 PC の `claude` が会社のアカウントのログイン (キーチェーンの項目 `Claude Code-credentials`) を読めるか。v0.3 の node の経路は開発 PC の GUI のログインの中で動くので、SSH とは条件が違う。
- 会社の組織の設定が、SSH 越しの `claude -p` やコネクタの読み込みを止めていないか。
- `--tools ""` と `--allowedTools` の組み合わせで、依頼した作業が会社のコネクタだけで最後まで進むか。

### 2.4 埋めるべき隙間

1. ミニ PC から開発 PC への SSH の経路 (鍵、接続先、開発 PC のログインの読み込み)。今は登録が無い。
2. 依頼の文と作業フォルダを受け、`claude -p` に道具を絞るフラグ (`--tools ""`、`--allowedTools`、hook を止める `--settings`) を付けて起こし、JSON の結果を返す包み。公開の部品 (steipete/claude-code-mcp、dm-other-claudes) はこのフラグを渡す口を持たず、steipete は保守を終えている。
3. 入口からこの包みを呼ぶ口を、Bash の 1 行にするか、MCP の道具にするか。MCP にする場合、SSH の上で stdio を通す形は確かめていない。

## 3. スマホへの通知 (4.7。3.2-6、C10)

### 3.1 Remote Control の push 通知

- 条件 ([remote-control](https://code.claude.com/docs/en/remote-control) の "Mobile push notifications"): Remote Control が有効であること ("When Remote Control is active, Claude can send push notifications to your phone")、スマホの Claude アプリに、端末の Claude Code と同じアカウントと組織でログインすること ("Use the same account and organization you use for Claude Code in the terminal")、OS の通知を許すこと、`/config` で 2 つの切り替えを有効にすること。
- 2 つの切り替え ([settings-reference](https://code.claude.com/docs/en/settings-reference)):
  - `inputNeededNotifEnabled` (`/config` の **Push when actions required**): 権限の確認や質問が答えを待つときに通知する。既定は `false`。
  - `agentPushNotifEnabled` (`/config` の **Push when Claude decides**): Claude が送るべきと判断したときに通知する。既定は `false`。`claude remote-control` の server のセッションは、設定ファイルではなくアカウントに保存された値に従う ("they follow the value saved to your account rather than this key")。値を変えるには、端末の Claude Code のセッションで `/config` を切り替える。
- 通知の対象: 承認待ちは `inputNeededNotifEnabled` で必ず送る対象になる。入口の返事は「Claude が判断して」送るもので、返事のたびに届くとは書かれていない ("Claude decides when to push. It typically sends one when a long-running task finishes or when it needs a decision from you to continue")。イベントごとの設定は無い ("Beyond the two on/off toggles below, there is no per-event configuration")。送る道具は `PushNotification` で、Remote Control につないでいればスマホに届く ([tools-reference](https://code.claude.com/docs/en/tools-reference))。
- 送られないとき: 接続した端末で入力しているか、端末にフォーカスがある間は送らない。
- 契約の条件: Remote Control は Pro、Max、Ultra、Team、Enterprise で使え、Team と Enterprise では Owner が有効にする。push 通知だけに付く契約の条件は資料に無い。
- ミニ PC の今の状態: `CLAUDE_CONFIG_DIR` の `settings.json` には、2 つの切り替えの鍵も hook も無い。server のセッションが従うアカウントに保存された値は確かめていない。個人のアカウントで実際に通知が届くかも確かめていない。
- 満たす要件: 3.2-6 の承認待ち。返事の通知は Claude の判断に任され、C10 の「返事をしたとき」を毎回満たすとは資料から言えない。

### 3.2 hook でスマホに通知する部品

使う hook の事象 ([hooks](https://code.claude.com/docs/en/hooks))

- `Stop`: "When Claude finishes responding"。`matcher` は無く、毎回動く ("no matcher support | always fires on every occurrence")。入口の返事の通知に当たる。
- `PermissionRequest`: "Runs when Claude Code is about to ask you for permission to use a tool."
- `Notification` の `permission_prompt`: 承認を求める確認が約 6 秒待ったときに動く ("the prompt has waited about six seconds")。`PermissionRequest` との違いを、資料は "Claude Code runs a Notification hook with the `permission_prompt` type only after the prompt has waited about six seconds." と書く。`idle_prompt` は "Claude finished responding about 60 seconds ago and you haven't typed since"。
- 承認待ちを 1 通にするには、`PermissionRequest` か `Notification` の `permission_prompt` の片方だけを使う。
- server mode が作るセッションで、ユーザーの設定ファイルの hook が動くかを明記した文は見つけていない。資料には、Remote Control につないでいる間の hook に `$CLAUDE_CODE_BRIDGE_SESSION_ID` が渡るとある ("sets `$CLAUDE_CODE_BRIDGE_SESSION_ID` to the Remote Control session ID while the local session has an active Remote Control connection")。server のセッションの設定は設定ファイルから読まれる ([入口と spawn の調査](research-entry-and-spawn.md) の V1)。server のセッションで実際に動くかは確かめていない。

部品

- 今の運用: 開発 PC の Claude Code は、`Stop` と `UserPromptSubmit` の hook で ntfy に通知している。ミニ PC には、ログインの期限の通知 ([deploy/claude-remote-control/](../../deploy/claude-remote-control/README.md) の `claude-login-expiry-notify`) があり、入口の返事の通知は無い。
- [zbiljic/ntfy-hooks](https://github.com/zbiljic/ntfy-hooks) (MIT、最後のコミット 2026-09-23): シェル 1 本と `install.sh`。`install.sh` の 300〜302 行目で `.hooks.Stop`、`.hooks.Notification`、`.hooks.PermissionRequest` に登録し、297 行目で `"async": true` を付ける。`ntfy.sh` は 197 行目で `permission*)`、201 行目で `idle*)` を分け、206 行目の `Finished responding` (返事) と 211 行目の `Needs permission` (承認待ち) で本文を変える。3 つすべてに登録するので、承認待ちは 2 通になり得る。満たす要件: 3.2-6 (返事と承認待ちの両方)。
- [shiqkuangsan/claude-code-notify](https://github.com/shiqkuangsan/claude-code-notify) (MIT、最後のコミット 2026-03-09): `Stop` と `Notification` の `idle_prompt|permission_prompt` で、ntfy・Telegram・Webhook に送る。README は Python の標準ライブラリだけで macOS と Linux で動くとする。中身は照合していない。
- [coa00/claude-push](https://github.com/coa00/claude-push) (MIT、最後のコミット 2026-02-24) と [yuuichieguchi/claude-remote-approver](https://github.com/yuuichieguchi/claude-remote-approver) (MIT、最後のコミット 2026-03-02): `PermissionRequest` の hook で ntfy に許可・拒否のボタン付きの通知を送り、スマホから答える。返事の通知は持たない。中身は照合していない。3.2-6 が求めるのは通知で、スマホの通知から承認に答えることは求めていない。

### 3.3 埋めるべき隙間

1. 返事のたびの通知: 公式の push は Claude の判断に任されるので、毎回の通知には `Stop` の hook (ntfy-hooks のような部品か、今の ntfy の hook を移したもの) が要る。
2. 公式の push を使う場合、server のセッションが従うアカウントの値を、ミニ PC の同じ `CLAUDE_CONFIG_DIR` の対話のセッションで `/config` を切り替えて保存する手順。オーナーが一度行う。
3. server mode のセッションで hook が動くかの確認。動かない場合は、入口を対話の形 (1.1 節) にするか、通知を別の経路で出す。
4. 公式の push と hook の両方を使うと、承認待ちが 2 通届く。どちらで送るかを分ける。

## 4. つなぎのスクリプトが要る所

- 入口の常駐の形に合わせた、同じ会話に戻す起動 (1.5-2): server mode のまま `--continue` で戻すか、対話の形でセッションの ID を記録して `claude --resume <id> --remote-control` で戻すか。後者には公開の部品 (claude-tmux-service、claude-rc-keep) がある。
- 開発 PC の `claude -p` を、道具を会社のコネクタに絞って SSH で呼び、JSON の結果を返す包み (2.4-2)。開発 PC 側は `authorized_keys` の `command=` でその包みだけを動かす鍵にできる。
- 入口の返事を毎回スマホに知らせる `Stop` の hook (3.3-1)。ntfy に送る部品は公開されている (ntfy-hooks)。承認待ちを公式の push と hook のどちらで送るかで、登録する事象が変わる。
