# 入口と spawn の調査

- 更新: 2026-11-03 JST
- 種別: 調査記録。[README](README.md) の「決まっていないこと」の 1 つ目 (入口になる常駐のセッションと、そこからのセッションの spawn を、どの部品で作るか) の材料。
- 前提: 同じ形 (常駐する入口、どの端末からも届く、役を分けたセッションを spawn する) は、v0.3 で OpenClaw によって動いている ([v0.3 の決定](../reports/v0.3-decision.md) の R2、R3、R4)。本調査は、OpenClaw の各機能を Claude の機能と先行事例のどれで置き換えられるか、置き換えると何が失われるかを調べる。v0.3 の母集団 ([front-door-oss-2026-09-27](../research/front-door-oss-2026-09-27/README.md)) は調べ直さず、Claude で動くもの・常駐するもの・spawn するものに絞って読み直す。

## 1. 決めること

入口のセッションと spawn を、どの部品で作るか。

## 2. 決めることを左右する変数

- V0 規約: 定額ログインの Claude を、オーナーが自分のためだけに作って動かすエージェント (Claude Agent SDK を含む) から使うことが、Anthropic の規約で認められるか。v0.3 では、第三者の製品が Agent SDK で定額ログインを使う形を外した ([findings.md](../research/front-door-oss-2026-09-27/findings.md) の 6 節)。認められるなら、Agent SDK と、v0.3 で H7 として外した製品が候補に戻る。
- V1 入口への到達: ミニ PC に常駐する 1 つのセッションに、PC とスマホから同じ会話として届くか。送る、途中の出力を見る、止める、権限の確認に答える (v0.3 の R4、R7、R13、R14)。
- V2 spawn と文脈の注入: 入口のセッションから、役ごとに指示・メモリ・hook・MCP を分けたセッションを起動し、作業を渡せるか。
- V3 spawn した先の見渡し: spawn したセッションの進行が入口から見え、止める・追加の指示を送ることができるか (v0.3 の R5)。
- V4 常駐の持続: 入口のセッションが、文脈の圧縮、プロセスの再起動、ログインの期限 (約 29 日) を越えて続くか。記憶をどう持ち越すか。
- V5 先行事例: 同じ形を Claude で作った製品・OSS と、Dots 自体の仕組み。
- V6 アカウントの置き場所: 入口のセッションを会社と個人のどちらのアカウントで動かすか。v0.3 では入口を個人の側 (ミニ PC) に置き、会社のコネクタは開発 PC の Claude だけが使う形にした。

## 3. 手元で確かめた事実 (2026-11-03)

- 開発 PC の Claude Code は 2.1.308。CLI に、セッションをバックグラウンドで起動する `--bg` と、バックグラウンドのセッションを一覧・起動・停止する `claude agents`・`attach`・`logs`・`stop`・`respawn` がある。`claude agents` は、起動するセッションに `--settings`、`--setting-sources`、`--plugin-dir`、`--mcp-config`、`--agent`、`--model` を指定できる (`claude --help`、`claude agents --help`)。
- CLI の `--environment <environment_id>` は「self-hosted environment で動く新しいクラウドのセッションを作る」(`claude --help`)。
- ミニ PC では `claude remote-control --name mini-pc` を systemd で常駐させ、claude.ai/code、モバイルアプリ、デスクトップアプリから環境 `mini-pc` を選んでセッションを始められる。ログインは個人の claude.ai の契約で、期限は約 29 日 ([deploy/claude-remote-control/README.md](../../deploy/claude-remote-control/README.md))。
- 開発 PC の Claude Desktop から新しいセッションを起こせる先は、この PC のフォルダと、クラウドの環境 3 つ (「カンリー標準設定」「Default」「mbp」) で、SSH の接続は登録が無い。クラウドの環境に `mini-pc` は出てこない。開発 PC の Desktop は会社のアカウントで動いている。
- 開発 PC の Claude Code のセッションの中から、Bash で `claude -p` を起動すると応答が返った (`--setting-sources ""`、`--model haiku`。入れ子の起動を止める仕組みは働かなかった)。

## 4. 変数ごとの事実

出典は、とくに書かないかぎり 2026-11-03 に取得した Claude Code の公式資料 (`https://code.claude.com/docs/en/<ページ>`) である。

### V0 規約

- [法令と規約](https://code.claude.com/docs/en/legal-and-compliance): 定額のログイン (OAuth) は「Claude Code と Anthropic のネイティブのアプリの通常の利用」のためのもの ("designed to support ordinary use of Claude Code and other native Anthropic applications")。Pro・Max・Ultra の上限は「Claude Code と Agent SDK の通常の、個人の利用」を前提にする ("assume ordinary, individual usage of Claude Code and the Agent SDK")。禁じているのは、第三者の開発者が自分のアプリで claude.ai のログインを提供すること、利用者に代わって定額の資格情報で要求を通すこと。手を加えていない Claude Code に、利用者が自分の契約でログインすることは妨げない。
- Agent SDK をオーナーが自分のためだけに定額のログインで動かす形を、名指しで認める文も禁じる文も、上のページには無い。サポートの記事 ([Use the Claude Agent SDK with your Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)) は、Agent SDK と `claude -p` の利用を定額の上限の扱いとして書いている ("when you’re signed in with your Claude plan, the Claude Agent SDK and claude -p still draw from your subscription limits")。
- 手を加えていない `claude` を自分の契約で `-p` や Remote Control で動かす形について、上のページが明記しているのは「通常の利用」のためのログインであること、手を加えていない Claude Code に自分の契約でログインすることを妨げないことまでである。`-p` で動かす使い方がこれに含まれるというのは、この 2 つの文と上のサポートの記事からの推論である。

### V1 入口への到達

- Remote Control ([remote-control](https://code.claude.com/docs/en/remote-control)): 会話と、サブエージェントと dynamic workflow の進み具合が、つないだすべての端末でそろい、端末・ブラウザ・スマホから交互に送れる。権限の確認と質問は、答えるまで端末に出たまま待つ。server mode (`claude remote-control`) は 1 つのプロセスで既定 32 までのセッションを持ち、アプリや claude.ai/code から始めたセッションも受ける。Pro・Max・Ultra・Team・Enterprise で使え、Team と Enterprise は Owner が有効にする。ネットワークが約 10 分切れるとプロセスが終わり、止まったセッションは約 4 時間以内なら戻せる。server mode は起動時に、そのフォルダで 1 つのセッションを作っておく (`--create-session-in-dir`、既定で有効)。`--continue` を付けて起動すると、新しく作らず、前の server が最初に作ったセッションを戻す。`--settings` などの起動オプションは server が作るセッションに引き継がれず、付けて起動すると断られる (`--verbose`、`--model` など、引き継がなくても動きが変わらないものだけ通る)。server が作るセッションの設定は、設定ファイルと定義のファイルから読まれる。
- Projects ([claude-projects](https://code.claude.com/docs/en/claude-projects)): 「1 つの続く会話で、Claude が関連する作業の流れを取りまとめる。頼んだ作業ごとにスレッドを始める」。claude.ai/code、Desktop の Code タブ、モバイルアプリで使え、CLI では使えない。Pro・Max・Ultra の公開ベータで順に提供中、Team と Enterprise には無い。スレッドは既定でクラウドのセッションで、頼めば Remote Control を通して自分の機械のフォルダで動かせる (Work locally。その機械に 2.1.280 以上が要り、起きている間だけ動く)。クラウドのスレッドは、機械にだけ入れた skill・MCP・plugin を持たない。機械で動かすスレッドは、その機械に入れたものを使う。
- Dispatch ([desktop](https://code.claude.com/docs/en/desktop)): スマホから頼んだ仕事を Desktop のセッションにする機能。限定ベータで新しい利用者は使えず、Team と Enterprise には無い。
- 開発 PC の Desktop は会社のアカウントで動いている (3 節)。ミニ PC の Remote Control は個人のアカウントで動いている。

### V2 spawn と文脈の注入

- サブエージェント ([sub-agents](https://code.claude.com/docs/en/sub-agents)): 定義のファイルに、`hooks` (そのサブエージェントが動いている間だけ働く)、`memory` (役ごとの記憶のディレクトリ。`~/.claude/agent-memory/<名前>/` など)、`skills` (起動時に中身ごと読み込む)、`mcpServers`、`model`、`tools` を書ける。plugin に入れたサブエージェントでは `hooks`、`mcpServers`、`permissionMode` が無視される。プロジェクトの `.claude/agents/` に置いたサブエージェントの `hooks` は、そのフォルダを信頼するまで働かず、`-p` のセッションは信頼した扱いにならない。ユーザーの `~/.claude/agents/` に置いたものと、`--agents` で渡したものの `hooks` は、この手順なしで働く。設定ファイルの hook もサブエージェントの中で働き、入力にエージェントの種類が付く。サブエージェントはさらに 3 段までサブエージェントを起こせ、結果は起こした会話に返る。
- `claude -p`: 入口のセッションから Bash で起動できる (3 節)。役ごとに `--append-system-prompt`、`--settings`、`--plugin-dir`、`--mcp-config`、`--agents` で文脈を分けられ、記憶の置き場は `--settings` の `autoMemoryDirectory` で分けられる ([memory](https://code.claude.com/docs/en/memory))。起動した `-p` のセッションは、`crossSessionInbound` を `accept` にしておけば、入口から `SendMessage` で追加の指示を受けられる ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging))。`--bare` で起動すると受けられない。
- バックグラウンドのセッション (`claude --bg`、`claude agents`。[agent-view](https://code.claude.com/docs/en/agent-view)): 起動は人の操作 (agent view の入力、`--bg`、`/bg`、`/fork`) で、結果は人にだけ報告され、起こしたセッションには返らない。
- モデルが道具として別のセッションを丸ごと起動する仕組みは、公式資料に見当たらない ([tools-reference](https://code.claude.com/docs/en/tools-reference) の道具の一覧に無い)。

### V3 spawn した先の見渡し

- Remote Control でつないだ端末には、そのセッションが動かしているサブエージェントと workflow が出て、端末から止めると機械の上でも止まる。
- Projects は、Overview の画面にスレッドを状態ごと (確認待ち、返事待ち、作業中) に並べ、スマホから様子を見て指示を足せる。
- Bash で起動した `claude -p` と、バックグラウンドのセッションが、スマホや claude.ai/code に出るとする記述は見当たらない。agent view は、そのセッションを動かしている機械の上の画面である。別のセッションが待ちに入ったときの通知 (`notify_when_idle`) は、同じ機械の中だけで使える。

### V4 常駐の持続

- 文脈が埋まりそうになると自動で圧縮し、会話は続く。圧縮のあと、システムプロンプト、プロジェクトの `CLAUDE.md`、自動の記憶はディスクから入れ直され、hook が足した文脈は要約に含まれる ([context-window](https://code.claude.com/docs/en/context-window))。
- `--resume` と `--continue` で会話を戻すとき、`--mcp-config`、`--settings`、`--plugin-dir` は付け直す必要がある ([sessions](https://code.claude.com/docs/en/sessions))。会話の記録は既定で 30 日残る。
- ログインの期限を過ぎると、バックグラウンドのセッションと Remote Control のセッションは、ログインし直すまで進まない ([authentication](https://code.claude.com/docs/en/authentication))。ミニ PC の期限は約 29 日 (3 節)。
- 記憶を整理し直す dreaming は、Claude Code の資料には見当たらず、API で使う Claude Managed Agents にある ([dreams](https://platform.claude.com/docs/en/managed-agents/dreams))。Managed Agents は API キーでの利用で、定額の契約では動かない。

### V5 先行事例

- Dots ([Meet dots](https://learn.chatgpt.com/docs/dots)): クラウドに自分のコンピューターとブラウザーを持って常駐し、ChatGPT のモバイルアプリ・デスクトップアプリ・ブラウザー、Slack、Teams、通話から同じ dot に届く。バックグラウンドのエージェントを使い、新しいクラウドのスレッドを始め、つないだコンピューターに Codex の作業を作り、その結果を確かめて追加の指示を送る。メモは会話と連絡手段をまたいで続く。
- Anthropic の機能で同じ形に最も近いのは Projects (1 つの会話からスレッドを始め、Overview で見渡す) である。
- OSS で、手を加えていない `claude` を動かすもの: OpenClaw (今の PDA)、Hermes Agent、Paperclip、OpenMausBot、amux、claw-orchestrator、Trinity、happier、claudeclaw (moazbuilds)、multi-agent-shogun、5dive、podium。Agent SDK で動かすもの: NanoClaw (チャットから、`CLAUDE.md`・記憶・コンテナを持つ仲間を起こす)、claude-code-telegram、cyrus。スマホと PC で同じ会話に届き、役ごとの設定を持つ作業者を起こし、入口から止められることを、手を加えていない `claude` でそろえていると資料で読めるのは OpenClaw だけだった (各製品の README と v0.3 の [findings.md](../research/front-door-oss-2026-09-27/findings.md) による)。

### V6 アカウントの置き場所

- Projects と Dispatch は個人のプラン (Pro・Max・Ultra) だけで使える。Remote Control はどのプランでも使え、会社のプランでは Owner が有効にする必要がある。
- 別の機械のセッションへの `SendMessage` が届くのは、自分の Remote Control のセッションとクラウドのセッションである。資料には、別のアカウントのセッションへ届くとする記述は無い。

## 5. OpenClaw の機能と、置き換えに使える Claude の部品

- 常駐の入口 (Gateway、Control UI、iOS アプリ) → ミニ PC の Remote Control の server mode に、claude.ai/code・モバイルアプリ・Desktop からつなぐ。または Projects の会話。
- `sessions_spawn` → サブエージェント (端末から見えて止められる)、Bash で起動する `claude -p` (役ごとに設定を丸ごと分けられるが、端末からは見えない)、Projects のスレッド。
- 役ごとの `AGENTS.md` と共通の指示の plugin (pda-common) → サブエージェントの定義 (指示・hook・記憶・skill・MCP)、`CLAUDE.md`、`--append-system-prompt`。
- 開発 PC を node としてつなぎ、会社のコネクタを借りる経路 → 置き換えの部品は見つかっていない (V6)。
