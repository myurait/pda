# 部品の調査: 役ごとの規約・記憶・hook と、正本の配布

- 更新: 2026-11-03 JST
- 種別: 調査記録。[部品の調査の計画](research-plan.md) の 4.4 節「役ごとの規約・記憶・hook と、出力の点検と直し」と 4.5 節「正本 1 か所から配る」の結果。設計の結論は書かず、使える部品と埋めるべき隙間までを書く。
- 物差し: [Claude 一本化の要件](requirements.md) の 3.1-5、3.2-2、3.3-1、3.3-2 と、受け入れ条件 C6、C7、C11、C12。
- 出典: とくに書かないかぎり、2026-11-03 に取得した Claude Code の公式資料 (`https://code.claude.com/docs/en/<ページ>`)。公開のリポジトリの最後のコミットの日付は、2026-11-03 に GitHub の API で取った既定のブランチの値。

## 1. 答える問い

- 問い 1 (3.1-5、3.2-2、C6): 役ごとの指示・メモリ・hook・skill・MCP は、どの起こし方で、その役のセッションに効くか。どの起こし方で効かないか。
- 問い 2 (3.2-2、C7): 出来上がった出力を規約で点検し、外れていれば差し戻して直させる仕組みは、どの起こし方で効くか。直したことは記録に残るか。
- 問い 3 (3.3-2、C12): 指示・skill・hook・MCP の正本を 1 か所に置き、1 か所を直すとすべての役のセッションに届くようにするには、何を使うか。

## 2. 手元で確かめた事実

開発 PC の Claude Code 2.1.308 で、一時ディレクトリに試験用の hook・設定・役の定義を置いて試した。`claude -p` には `--setting-sources ""` (`project` と書いたものを除く) と `--model haiku` を付けた。試験用の hook は、入力の JSON を記録し、Stop と SubagentStop では最後の応答に「【点検済み】」が無ければ `{"decision":"block","reason":"規約: 応答の最後の行に【点検済み】と書いてから終えてください。"}` を返し、`stop_hook_active` が `true` のときは返さない command 型のスクリプトである。

- T1 `--settings` の Stop の hook (command 型): `claude -p "1 + 1 の答えを一言で。" --setting-sources "" --settings ./settings-stop.json`。hook が 1 回差し戻し、出力は「2」の後に「【点検済み】」を足したものになった。2 回目の呼び出しの入力は `stop_hook_active=true` だった。
- T2 `--settings` の Stop の hook (prompt 型): 同じ判定を `type: "prompt"` の文で書いた。`model` を書かない (既定のモデルを使う) と、差し戻して「【点検済み】」を足させた。`"model": "haiku"` と書くと、標準エラーに `[claude-code:unrecognized_model] {"model":"haiku","query_source":"hook_prompt"}` が出て、差し戻さずに「2」だけで終わった。
- T3 `--agents` で渡したサブエージェントの `hooks`: `claude -p "checker サブエージェントに 2 + 3 を計算させ、その返事をそのまま返してください。" --setting-sources "" --agents ./agents.json`。定義の `hooks` に書いた Stop の hook が SubagentStop として呼ばれ (入力の `agent_type` は `checker`)、サブエージェントの答えを差し戻して「【点検済み】」を足させた。
- T4 `--agent` で主のスレッドを役にした: `claude -p "2 + 3 は？" --setting-sources "" --agents ./agents.json --agent checker`。定義の Stop の hook が Stop として呼ばれ (入力の `agent_type` は `checker`)、差し戻しが効いた。
- T5 プロジェクトの `.claude/agents/checker.md` の `hooks`: `claude -p "checker サブエージェントに 2 + 3 を計算させ、その返事をそのまま返してください。" --setting-sources project --output-format stream-json --verbose`。記録の中に `subagent_type: "checker"` の Agent の呼び出しがあり、サブエージェントは動いたが、定義の hook は一度も呼ばれなかった。
- T6 `--plugin-dir` の plugin: plugin の `agents/checker.md` の `hooks` は呼ばれず、デバッグの記録に `Plugin agent file … sets hooks, which is ignored for plugin agents. Use .claude/agents/ for this level of control.` と出た。同じ plugin の `hooks/hooks.json` に書いた SubagentStop の hook は、入力の `agent_type` が `rolestest:checker` (plugin の名前で名前空間が付く) で呼ばれ、差し戻しが効いた。同じ `hooks.json` の Stop の hook も主のスレッドで呼ばれた。plugin の hook が初めて動くとき、plugin の置き場の下に `${CLAUDE_PLUGIN_DATA}` のディレクトリ (`data/rolestest-inline`) が作られた。
- T7 CLAUDE.md と `--setting-sources`: 作業ディレクトリに合言葉を書いた `CLAUDE.md` を置いた。`--setting-sources ""` では読まれず、`--setting-sources project` では読まれた (合言葉を答えた)。
- T8 記憶の置き場: 一時ディレクトリに合言葉を書いた `MEMORY.md` を置き、`--setting-sources "" --settings '{"autoMemoryDirectory":"<そのディレクトリ>"}'` で起こすと、ファイルを読む道具を使わずに合言葉を答えた。
- T9 `--setting-sources ""` は、この PC に入れてある plugin を外さなかった。T6 の起動の記録 (`system/init` の `plugins`) に、試験用の plugin のほかに、ユーザー設定の `enabledPlugins` に書かれていない marketplace の plugin が並び、そのうち 1 つの Stop の hook が試験の中で動いた。資料の `defaultEnabled` (「`enabledPlugins` で利用者が決めていないとき、plugin を有効で始めるか。既定は `true`」。[plugins-reference](https://code.claude.com/docs/en/plugins-reference)) で説明がつくが、組織の管理設定から有効にされた可能性は切り分けていない。外す手段として資料にあるのは、`--settings` の `enabledPlugins` で `false` にすること ([plugins/loading](https://code.claude.com/docs/en/plugins/loading)) と、`--bare` である。

確かめていないこと: `claude --bg`、Remote Control の server が作るセッション、`hooks.json` の `matcher` で `agent_type` を絞る書き方、agent 型の hook。以下ではこれらを資料だけで書く。

## 3. 問い 1: 起こし方ごとに効くもの・効かないもの

### 3.1 入口のセッションの中のサブエージェント

サブエージェントの定義 ([sub-agents](https://code.claude.com/docs/en/sub-agents)) には、`name`、`description`、`tools`、`disallowedTools`、`model`、`permissionMode`、`maxTurns`、`autoCompactWindow`、`skills`、`mcpServers`、`hooks`、`memory`、`background`、`omitClaudeMd`、`effort`、`isolation`、`color`、`initialPrompt`、`experimental` を書ける。本文はそのサブエージェントのシステムプロンプトになる ("Subagents receive only this system prompt plus basic environment details like the working directory, not the Claude Code system prompt.")。CLAUDE.md は、Explore と Plan と `omitClaudeMd` を付けたものを除いて読み込まれる。同じ名前の定義は、管理設定、`--agents`、`.claude/agents/`、`~/.claude/agents/`、plugin の順に優先される。

置き場ごとの違い。

- ユーザーの `~/.claude/agents/` (3.1-5、C6): 指示・`memory`・`hooks`・`skills`・`mcpServers` がすべて効く。`hooks` は信頼の手順なしで動く ("Hooks from user-level subagents in `~/.claude/agents/` and from definitions you pass with `--agents` run without this step.")。
- `--agents` で渡した定義 (3.1-5、C6): 同じくすべて効き、`hooks` は信頼の手順なしで動く (T3)。`-p` では JSON のファイルのパスも渡せる。入口の中のサブエージェントに使う場合、`--agents` は入口のセッションを起動するときの引数である。
- プロジェクトの `.claude/agents/` (3.1-5 は一部): 指示と `memory` は効くが、`hooks` と、定義の中に書いた MCP のサーバーは、そのフォルダを信頼するまで働かない。親のフォルダの信頼では足りず、`-p` は信頼した扱いにならない ("trusting a parent folder isn't enough, and a `-p` session doesn't count as trusted.")。T5 で、`-p` ではサブエージェントは動き、hook は動かないことを確かめた。
- plugin の `agents/` (3.1-5 は一部): `hooks`、`mcpServers`、`permissionMode` は無視される ("For security reasons, plugin subagents don't support the `hooks`, `mcpServers`, or `permissionMode` frontmatter fields.")。資料は、hook を plugin の `hooks/hooks.json` に、MCP を `.mcp.json` に置くよう勧める ("They apply whenever the plugin is enabled rather than only inside the subagent.")。`hooks.json` の SubagentStop の hook は、入力の `agent_type` (例: `rolestest:checker`) で役を区別でき、`matcher` は `agent_type` で絞る ([hooks](https://code.claude.com/docs/en/hooks) の SubagentStop input: "The `agent_type` field is the value used for matcher filtering.")。T6 で、`matcher` を書かない hook が plugin の役の出力を差し戻すことを確かめた。`matcher` を書かない hook はすべてのサブエージェント (Claude Code が内部で動かすものを含む) で動く。

役ごとの記憶。

- サブエージェントの `memory` は、`user` (`~/.claude/agent-memory/<名前>/`)、`project` (`.claude/agent-memory/<名前>/`)、`local` (`.claude/agent-memory-local/<名前>/`) の置き場を持つ。自動の記憶を切ると効かない ("if you turn auto memory off … the `memory` field has no effect")。
- サブエージェントの hook は、そのサブエージェントが動いている間だけ働き、終わると外れる。定義の Stop は SubagentStop に変わる ([hooks](https://code.claude.com/docs/en/hooks) の Hooks in skills and agents)。
- 設定ファイルの hook もサブエージェントの中で動き、入力に `agent_id` と `agent_type` が付く。

### 3.2 `claude -p`

- 既定では、対話のセッションと同じく、hook・skill・サブエージェント・入れてある plugin・MCP・自動の記憶・CLAUDE.md を探して読む ([headless](https://code.claude.com/docs/en/headless): "Without it, `claude -p` discovers and loads them as an interactive session would")。`-p` は信頼の確認を出さず、フォルダを信頼した扱いにする。そのため、プロジェクトの `.claude/settings.json` の hook は動く ([hooks](https://code.claude.com/docs/en/hooks) の Workspace trust)。プロジェクトのサブエージェントの定義の hook だけは、上のとおり動かない。
- `--settings` (C6): 設定の JSON (ファイルか文字列) を、ユーザー・プロジェクト・ローカルの設定より上に重ねる。hook (T1、T2)、`autoMemoryDirectory` (T8)、`enabledPlugins`、`agent` などを役ごとに渡せる。`--setting-sources ""` のときも効いた (T1)。
- `--setting-sources`: 読む設定の出所を `user`、`project`、`local` から選ぶ。プロジェクトを外すと、プロジェクトの CLAUDE.md (T7) と `.claude/rules/` も読まない ([memory](https://code.claude.com/docs/en/memory): "Project rules are skipped if you exclude `project` from `--setting-sources`")。選べる値は `user`、`project`、`local` だけで、管理設定は外せない ([cli-reference](https://code.claude.com/docs/en/cli-reference))。入れてある plugin も外れなかった (T9)。
- `--append-system-prompt`、`--append-system-prompt-file`: 既定のシステムプロンプトの後ろに役の指示を足す。`--system-prompt` は既定のシステムプロンプトを丸ごと置き換える。
- `--agents` と `--agent`: 役の定義を渡し、`--agent` でその役を主のスレッドにする (T4)。主のスレッドになった役の定義は、指示 (既定のシステムプロンプトを置き換える)・`tools`・`model` を持ち、定義の Stop の hook は Stop として動く。CLAUDE.md とプロジェクトの記憶は、`omitClaudeMd` を付けても読み込まれる ("`CLAUDE.md` files and project memory still load through the normal message flow, even when the agent's definition sets [`omitClaudeMd`]")。
- `--plugin-dir`: plugin をそのセッションだけ読み込む。複数を重ねられ、同じ名前の入れてある plugin より優先される。
- `--mcp-config` と `--strict-mcp-config`: 役ごとの MCP のサーバーを渡し、`--strict-mcp-config` でそれ以外の MCP の設定を読まない。
- `--bare`: hook・skill・サブエージェント・入れてある plugin・MCP・自動の記憶・CLAUDE.md の自動の読み込みをすべて止め、上の引数で渡したものだけを使う。ただし定額のログインを読まない ("In bare mode, Claude Code never reads OAuth credentials or the system keychain.")。資料は、`--bare` を `-p` の既定に変える予定と書く ("`--bare` is the recommended mode for scripted and SDK calls, and will become the default for `-p` in a future release.")。

### 3.3 `claude --bg` と `claude agents`

資料だけで、手元では試していない ([agent-view](https://code.claude.com/docs/en/agent-view)、[cli-reference](https://code.claude.com/docs/en/cli-reference))。

- `--bg` は `-p` と組み合わせられない。起動の前にフォルダの信頼を確かめ、確認を出せないところでは `Workspace not trusted` で終わる。`--agent` で役を指定できる。
- 起動の引数のうち、`--mcp-config`、`--strict-mcp-config`、`--settings`、`--setting-sources`、`--add-dir`、`--plugin-dir`、`--fallback-model` はバックグラウンドのセッションに引き継がれる。`claude agents` も `--settings`、`--add-dir`、`--plugin-dir`、`--mcp-config` を受け、`--agent` を起こすセッションの既定にできる。
- `--append-system-prompt` と `--agents` が引き継がれるかは、資料に書かれていない。
- 結果は起こしたセッションに返らない ([入口と spawn の調査](research-entry-and-spawn.md) の V2)。

### 3.4 Remote Control の server が作るセッション

資料だけで、手元では試していない ([remote-control](https://code.claude.com/docs/en/remote-control))。

- `claude remote-control` の前に付けた `claude` の全体の引数は、server が作るセッションに引き継がれない。動きを変えない `--verbose` や `--model` などだけが通り、`--settings` などを付けると起動を断られる ("For any other flag, such as `--settings`, Claude Code refuses to start and names the flag to remove.")。
- そのため、server が作るセッションの役の設定は、そのフォルダとユーザーの設定ファイル・定義のファイル (ユーザーとプロジェクトの `settings.json`、`CLAUDE.md`、`.claude/agents/`、入れてある plugin) から読まれる。設定の `agent` (どのファイルにも書ける。[settings-reference](https://code.claude.com/docs/en/settings-reference): "Start every session as a named subagent with its prompt, tools, and model") を使えば、フォルダの設定でそのフォルダのセッションを役にできる。
- 信頼していないフォルダでは、起動の前に `Trust <directory>? [y/N]` を尋ね、端末でないと `Workspace not trusted` で終わる。プロジェクトの `.claude/agents/` の hook が、ここで信頼したフォルダの server のセッションで動くかは確かめていない。
- `--spawn worktree` では、作るセッションごとに git の worktree を切る。

### 3.5 起こし方ごとの要約

- 入口の中のサブエージェント: `~/.claude/agents/` と `--agents` は指示・記憶・hook・skill・MCP がすべて効く。プロジェクトの `.claude/agents/` は `-p` と信頼していないフォルダで hook と定義の MCP が効かない。plugin のサブエージェントは hook・MCP・`permissionMode` が効かず、`hooks.json` と `.mcp.json` で補う。
- `claude -p`: 起動の引数で、指示 (`--append-system-prompt-file`、`--agents` と `--agent`)・記憶 (`--settings` の `autoMemoryDirectory`)・hook (`--settings`)・skill と hook (`--plugin-dir`)・MCP (`--mcp-config`) を役ごとに丸ごと分けられる。`--bare` を付けると定額のログインを読まない。
- `claude --bg`: `--settings`、`--plugin-dir`、`--mcp-config`、`--agent` は渡せる。`--append-system-prompt` と `--agents` は資料に記載なし。信頼したフォルダでしか起こせない。
- Remote Control の server のセッション: 起動の引数は使えず、フォルダとユーザーの設定ファイル・定義のファイルだけで役を決める。

## 4. 問い 2: 出力の点検と直し

### 4.1 使える部品

- Stop と SubagentStop の hook (3.2-2、C7)。どちらも `decision: "block"` と `reason` (または終了コード 2 と標準エラー) を返すと、`reason` が次の指示として渡り、主のスレッドかサブエージェントが作業を続ける ([hooks](https://code.claude.com/docs/en/hooks) の Stop decision control と SubagentStop input)。`hookSpecificOutput.additionalContext` を返すと、誤りの扱いでなく「Stop hook feedback」として続けさせる。入力の `last_assistant_message` に最後の応答の文が入るので、記録のファイルを読まずに点検できる。
- hook の種類: command 型、http 型、mcp_tool 型、prompt 型、agent 型のすべてが Stop と SubagentStop で使える。prompt 型は、入力と文を Claude のモデル (既定は Claude Code が裏の処理に使うモデル) に送り、`{"ok": false, "reason": …}` を返すと `reason` を次の指示にして続けさせる。`impossible: true` を添えると止めずに終える。既定の時間切れは 30 秒。agent 型は Read・Grep・Glob を使える検証役を最大 50 ターン動かす試験的な機能で、既定の時間切れは 60 秒。
- 置き場ごとの効き方 (問い 1 と同じ規則に従う): `--settings` と設定ファイル (T1、T2)、`--agents` と `~/.claude/agents/` の定義 (T3、T4)、plugin の `hooks.json` (T6) で効く。プロジェクトの `.claude/agents/` の定義に書いたものは `-p` で効かない (T5)。skill の定義に書いた hook は、skill を呼んだ後そのセッションの残りで動く。プロジェクトの skill の hook は、信頼していないフォルダの `-p` でも登録される。
- `/goal` は、セッションの間だけ効く prompt 型の Stop の hook の近道である ([hooks](https://code.claude.com/docs/en/hooks) の Stop: "The `/goal` command is a built-in shortcut for a session-scoped prompt-based Stop hook.")。
- 起こし方との対応: `-p` (T1〜T4、T6)、入口の中のサブエージェント (SubagentStop。T3、T6)、主のスレッドを役にしたセッション (T4)。`--bg` と Remote Control の server のセッションでは試していないが、どちらも設定ファイルと `--settings` (`--bg` のみ) の hook を読む。

### 4.2 直したことの記録 (C7)

- `reason` は Claude への次の指示として会話の記録に入る。`additionalContext` は会話の記録に「Stop hook feedback」として残る。hook のスクリプトは、点検の結果を自分で記録のファイルに書ける (T1〜T6 の試験用の記録)。
- 点検の結果を、入口やオーナーが後から読める場所に集める部品は見つかっていない。

### 4.3 点検が効かずに通る場合 (C7 の隙間)

- prompt 型の hook のモデルの名前を `haiku` と書くと、`unrecognized_model` の誤りになり、差し戻さずに終わった (T2)。点検する側の誤りは、出力を通す側に倒れた。
- 連続の差し戻しには上限がある。Stop の hook が 8 回続けて差し戻すと、次の差し戻しを無視してターンを終える (上限は `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` で変えられる)。道具を 1 回呼ぶと数え直す。
- 2 回目以降の呼び出しは `stop_hook_active` が `true` になる。試験用の hook はこのとき差し戻さないので、直した出力が規約に合っているかは 1 回しか確かめていない。
- Stop は、利用者が割り込んで止めたときと、API の誤りで終わったとき (StopFailure) は動かない。
- `--bare` は hook を自動で読まない。`--settings` か `--plugin-dir` で渡した hook は効く。

## 5. 問い 3: 正本 1 か所から配る

### 5.1 使える部品

- plugin (3.3-2、C12): skill、サブエージェント、hook (`hooks/hooks.json`)、MCP (`.mcp.json`)、LSP、出力のスタイル、workflow、monitor、実行ファイル (`bin/`)、既定の設定 (`settings.json` の `agent` と `subagentStatusLine` だけ) を 1 つのディレクトリにまとめる ([plugins-reference](https://code.claude.com/docs/en/plugins-reference))。`userConfig` で値を尋ね、hook には `CLAUDE_PLUGIN_OPTION_<KEY>` で渡せる。
- 手元のパスから足した marketplace (3.3-2、C12): marketplace の中の相対パスの plugin は、キャッシュに写さずにその場から読み込まれ、元のディレクトリを直すと、次のセッションの開始か `/reload-plugins` で効く。バージョンを上げる必要は無い ([plugins/loading](https://code.claude.com/docs/en/plugins/loading): "Your edits to the source directory take effect at the next session start or `/reload-plugins`, and you don't need to increase the version.")。
- `--plugin-dir` (3.3-2): plugin のディレクトリをその場から読み込む (写さない)。セッションごとに渡す必要がある。同じ名前の入れてある plugin より優先される。`CLAUDE_CODE_PLUGIN_DIRS` の環境変数でも渡せる。
- git の marketplace: GitHub などから足すと `~/.claude/plugins/marketplaces/<名前>/` に複製し、plugin はキャッシュに写す。バージョンを書かなければ、コミットの SHA がバージョンになる。auto-update は既定で切れており、`extraKnownMarketplaces` の `autoUpdate` で入れる。更新は走っているセッションには入らず、`/reload-plugins` か次の起動で入る。
- 設定の階層: 管理設定、`--settings`、プロジェクトのローカル、プロジェクト、ユーザーの順に優先され、配列 (`permissions.allow` や hook) は重ね合わされる。hook は階層をまたいで足される ([settings](https://code.claude.com/docs/en/settings))。ユーザーの `~/.claude/settings.json` に書いた hook と `enabledPlugins` は、`--setting-sources` で `user` を外さないかぎり、その機械のすべてのセッションに効く。
- claude.ai の個人のアカウントで有効にした plugin は、claude.ai のログインで動く端末のセッションに同期される (`<名前>@synced`)。`--setting-sources` で `user` を外したセッションと、`--bare` のセッションでは同期されない ([plugins/loading](https://code.claude.com/docs/en/plugins/loading) の Plugins synced from claude.ai)。
- 指示の共有: `@path` の取り込み、ユーザーの `~/.claude/rules/`、`CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` と `--add-dir` で別のディレクトリの CLAUDE.md を読む方法がある ([memory](https://code.claude.com/docs/en/memory))。

### 5.2 plugin で運べないものと、その代わり

- CLAUDE.md: plugin の根元に置いた `CLAUDE.md` は文脈に読み込まれない ("A `CLAUDE.md` at the plugin root isn't loaded as context")。資料は skill に入れるよう勧める。サブエージェントの定義の本文 (役のシステムプロンプト) も plugin で運べる。
- plugin のサブエージェントの `hooks`、`mcpServers`、`permissionMode`: 無視される。代わりに `hooks/hooks.json` で `agent_type` を見て役ごとに分け (T6)、MCP は `.mcp.json` に置く (plugin が有効な間すべての役に効く)。役だけに MCP を限るには、`-p` の `--mcp-config` か、`--agents` や `~/.claude/agents/` の定義の `mcpServers` を使う。
- 自動の記憶: plugin の部品に無い。役ごとの置き場は `--settings` の `autoMemoryDirectory` (T8) か、サブエージェントの `memory` で決める。
- plugin のパス: 部品のパスは plugin の根元から外に出られない。`../` や外を指すシンボリックリンクは断られる (同じ marketplace の中の plugin の間のリンクは除く)。

### 5.3 配り先ごとの届き方

- 入口の中のサブエージェント: 入口のセッションで有効な plugin がそのまま効く。
- `claude -p`: 入れてある plugin は既定で読み込まれる (T9)。`--plugin-dir` で正本のディレクトリを直接渡すこともできる。
- `claude --bg`: `--plugin-dir` を引き継ぐ。
- Remote Control の server のセッション: 起動の引数を使えないので、入れてある plugin (ユーザーかプロジェクトの `enabledPlugins`) で届ける。

## 6. 公開の部品

候補ごとに、出典、設定の書き方、最後のコミットの日付、ライセンスを書く。[部品の調査の計画](research-plan.md) の 3 節の絞る条件 (定額のログインで動く、画面に価値がある製品は中の仕組みだけ見る、ミニ PC で動く) を当てた結果を「条件」に書く。

いずれも手を加えていない `claude` に plugin・hook・定義のファイルを足す形で、自前の画面に価値がある製品ではない。ミニ PC (Ubuntu) で動かないとする記述は無い。

### 6.1 出力を LLM で点検して差し戻す hook

- ensemble-vnext ([FortiumPartners/ensemble-vnext](https://github.com/FortiumPartners/ensemble-vnext)、最後のコミット 2026-10-31、ライセンスは GitHub の判定が無く、`packages/full/.claude-plugin/plugin.json` は MIT、`package.json` は ISC と食い違う): 3.2-2、C7 の公開の例。プロジェクトの `.claude/settings.json` の雛形 (`packages/core/templates/claude-directory/settings.json`) に、Stop の `"type": "prompt"` の hook を置く。点検の文は `packages/core/hooks/prompts/discipline-stop.prompt.md` にあり、"The agent may stop unless its final message (`last_assistant_message` in the payload) commits one of the two violations below" で始まる。SubagentStop には置いていない。役ごとの出し分けは無い。配り方は marketplace (`claude plugin marketplace add FortiumPartners/ensemble-vnext`) と、hook をプロジェクトに写す雛形の併用。条件: 定額のログインについての記述は無い。
- claudetto ([xsyetopz/claudetto](https://github.com/xsyetopz/claudetto)、旧名 dotclaude、MIT、最後のコミット 2026-10-31): Stop の prompt 型の hook を 0.28.0 で出し、0.29.0 で外した。その評価の記録 `docs/evidence/stop-hook-eval.md` に、"The hook costs one model request per turn and fails open." 、"Timeout, API error, bad JSON, schema failure | No block, so the hook fails open"、1 ターンに約 6,914 入力トークンの要求が 1 回足されること、常に差し戻す SubagentStop の hook が 8 回で打ち切られたことが書かれている。部品としてではなく、prompt 型の点検の限界の記録として使える (4.3 節の T2 と同じ向き)。今のバージョンの Stop は LLM でなくスクリプトで判定する。
- 公式の plugin-dev の hook-development の skill ([anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)、Apache-2.0、最後のコミット 2026-10-30): prompt 型の hook を勧め、SubagentStop を「サブエージェントが仕事を終えたか確かめるのに使う」と説明する。SubagentStop の設定の例は無い。部品ではなく書き方の資料。

### 6.2 役ごとに hook を分ける実例

- claude-code-hooks-mastery ([disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)、ライセンスの表示なし、最後のコミット 2026-02-01): 3.1-5、C6 の実例。プロジェクトの `.claude/agents/team/builder.md` の定義に `hooks:` の `PostToolUse` (`matcher: "Write|Edit"`) を書き、書いたファイルを ruff と ty で検査して `{"decision": "block", "reason": …}` を返す。点検は LLM でなく道具の実行。プロジェクトの `.claude/agents/` に置くので、`-p` では効かない (T5)。配り方はリポジトリの `.claude/` を写す形。ライセンスが無いので、写して使う部品にはできない。
- claude-octopus ([nyldn/claude-octopus](https://github.com/nyldn/claude-octopus)、MIT、最後のコミット 2026-11-03): plugin の `hooks/hooks.json` の SubagentStop で `hooks/subagent-stop-gate.sh` を動かし、hook の中で `agent_type` を見て振り分ける。点検は長さと誤りの印による 0〜100 の点数で、`OCTOPUS_SUBAGENT_GATE_STRICT=true` のときだけ差し戻す。plugin の `hooks.json` で役を `agent_type` で分ける形 (T6) の公開の例。

### 6.3 規則のファイルから hook を作る plugin

- hookify (公式の [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) の `plugins/hookify`、Apache-2.0、このディレクトリの最後のコミット 2026-10-26): `.claude/hookify.<名前>.local.md` に正規表現の規則を書くと、plugin の PreToolUse・PostToolUse・Stop・UserPromptSubmit の hook がそれを読む。Stop の規則は会話の記録 (`transcript`) を正規表現で見て、`action: block` で止めずに続けさせる。規則はプロジェクトの `.claude/` に置くので、役ごとのフォルダで分けられる。判定は正規表現で、LLM ではない。SubagentStop は扱わない。

### 6.4 サブエージェントの定義集

- [wshobson/agents](https://github.com/wshobson/agents) (MIT、最後のコミット 2026-10-30) と [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) (MIT、最後のコミット 2026-11-02): どちらも marketplace で配る役の定義集。定義に `hooks:` と `memory:` は書いていない (前者の例 `plugins/agent-teams/agents/team-debugger.md`、後者の例 `categories/01-core-development/backend-developer.md`)。plugin のサブエージェントは hook を持てないので、役ごとの規約の点検には使えない。marketplace の作り方の例としてだけ使える。

### 6.5 hook を書くための道具

- [GowayLee/cchooks](https://github.com/GowayLee/cchooks) (MIT、最後のコミット 2026-04-08): hook の入力と出力を扱う Python のライブラリ (`SubagentStopContext` など)。点検の中身は持たない。
- [karanb192/claude-code-hooks](https://github.com/karanb192/claude-code-hooks) (MIT、最後のコミット 2026-10-17): 1 つの hook を 1 つの plugin にした marketplace。SubagentStop は記録の用途 (`async`) で、差し戻しはしない。

### 6.6 設定の配布

- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) (最後のコミット 2026-11-03) の一覧には、役ごとの hook を明示した項目は無かった。設定の配布に近いものとして、共通の設定を 1 つのディレクトリへのシンボリックリンクで複数のアカウントに配る [clausona](https://github.com/larcane97/clausona) と、規則・MCP・サブエージェントの設定を複数の AI の道具の形式に書き出す [Rulesync](https://github.com/dyoshikawa/rulesync) が載っている。どちらも中身は確かめていない。
- 1 か所の正本を複数の機械と役に配る仕組みとして資料と手元の試験で確かめられたのは、Claude Code の公式の機能 (5 節) だけだった。

## 7. 先行事例の読み直し

[先行事例の調査](research-prior-art.md) の事例を、この要素 (役ごとの規約・記憶・hook と出力の点検) の観点で読み直した。順位は使わない。

- Neutron ([rjunee/neutron](https://github.com/rjunee/neutron)、Apache-2.0、最後のコミット 2026-10-10): 起動のたびに `--settings` の JSON を作って渡し、Stop の hook を入れる。`runtime/adapters/claude-code/persistent/build-settings.ts` の冒頭に "generate the per-session `--settings` JSON that wires the enforce-reply Stop hook." とある。hook は、チャネルから来た依頼に返信の道具を呼ばずにターンを終えようとすると差し戻す (記事: "If not, the hook blocks the turn from ending")。役の指示は `prompts/` の役ごとのファイルを `--append-system-prompt-file` で渡す。役ごとに別の hook や記憶を渡す記述は無い。点検は規約の文ではなく、返信の道具を呼んだかという機械的な条件である。
- Kai ([dcellison/kai](https://github.com/dcellison/kai)、Apache-2.0、最後のコミット 2026-10-15): `src/kai/claude.py` は `claude` を `--bare` で起こし、指示・記憶・会話の履歴を最初のメッセージの前に足す ("On the first message of a new session, prepend identity, memory, conversation history")。hook は使わない。資料のとおり `--bare` が定額のログインを読まない (3.2 節) なら、今の公開のコードの起動の形は、定額のログインで動かす条件 (3.3-1) と合わない。HN の投稿 (2026-02-16) は、ログインした Claude Code を包むので API キーが要らないと書いている。
- computerex ([HN のコメント](https://news.ycombinator.com/item?id=48624111)): 「すべての仕事をサブエージェントに渡せ」と指示し、"I have hooks further enforcing this." と書く。どの hook で何をするかは書かれていない。
- mager ([Killing OpenClaw for a native Claude Code setup](https://mager.co/blog/2026-06-02-killing-openclaw/)) と Okapi 2.0: 役を `~/.claude/agents/` と `.claude/agents/` のサブエージェントで定義する。役ごとの hook の記述は無い。
- コキエ: 役と制約を `--append-system-prompt` で渡し、手順書を結合して注入する。hook の記述は無い。コードは公開していない。
- van Deth: 役をディレクトリごとの `CLAUDE.md` と MCP で分け、`claude -p` をそのディレクトリで起こす。hook の記述は無い。
- claude-hub: `PostToolUse` の hook で進捗を送る。点検には使っていない。

## 8. 埋めるべき隙間と、つなぎのスクリプトが要る所

### 8.1 隙間

- 役ごとの hook を確実に効かせる置き場が、起こし方ごとに違う。`-p` と入口の中のサブエージェントの両方に効くのは、`--agents`、`~/.claude/agents/`、plugin の `hooks.json` (役を `agent_type` で区別する)、`--settings`。プロジェクトの `.claude/agents/` は `-p` で hook が効かない (T5)。
- Remote Control の server のセッションには起動の引数を渡せず、役ごとの設定はフォルダの設定ファイルと定義のファイルに置くしかない。
- `--bare` は定額のログインを読まず、`-p` の既定になる予定がある (3.3-1、C11)。役の設定を自動の読み込み (ユーザーやプロジェクトの設定ファイル、入れてある plugin) に頼る起こし方は、既定が変わると届かなくなる。`--settings`、`--plugin-dir`、`--agents`、`--append-system-prompt-file`、`--mcp-config` で明示して渡したものは `--bare` でも届く。
- `--setting-sources ""` で起こしても、入れてある plugin は既定で有効になる (T9)。役のセッションに入れる plugin を正本のものに限るには、`--settings` の `enabledPlugins` で外す。
- 出力の点検は、点検する側の誤りで通る (T2)、連続の差し戻しに上限がある、の 2 つで「必ず」が崩れる (4.3 節)。
- 直したことを入口やオーナーが読める場所に集める部品が無い (C7 の「記録に残る」)。
- plugin は CLAUDE.md と役ごとの MCP と役ごとの記憶を運べない (5.2 節)。

### 8.2 つなぎのスクリプトが要る所

- 役の起動の行を組み立てるスクリプト: 役の名前を受け取り、正本から `--agents` (または `--agent`)、`--append-system-prompt-file`、`--settings` (役の Stop の hook、`autoMemoryDirectory`、`enabledPlugins`)、`--plugin-dir`、`--mcp-config` を組み立てて `claude -p` を起こす。Neutron の `build-settings.ts` が同じ形の公開の例である。
- 点検の hook の本体: 役ごとの規約の文を読み、`last_assistant_message` を点検して `decision: "block"` を返す。prompt 型の hook で足りる範囲と、規約の文をファイルから読む・結果を記録する・点検する側の誤りを差し戻しに倒す必要がある範囲を分ける。後者は command 型のスクリプトが要る。prompt 型の点検の文の公開の例は ensemble-vnext の `discipline-stop.prompt.md`、役を `agent_type` で振り分ける公開の例は claude-octopus の `subagent-stop-gate.sh` (6 節)。
- 点検と直しの記録を集める先: hook のスクリプトが書く記録を、入口が読める 1 か所にまとめる。
- 正本の置き場から各機械へ届ける手順: リポジトリの中の marketplace を、ミニ PC と開発 PC で手元のパスから足す (その場から読み込まれ、`git pull` の後の次の起動で効く)。
