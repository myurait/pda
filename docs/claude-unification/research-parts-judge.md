# 部品の調査: 判断を専門にする役と、オーナーの判断待ち

- 更新: 2026-11-03 JST
- 種別: 調査記録。[部品の調査の計画](research-plan.md) の 4.3 節の結果。設計の結論は書かず、候補と隙間までにする。
- 物差し: [Claude 一本化の要件](requirements.md) の 3.1-4 (ツリーと上申)、3.2-3 (判断待ちは非同期に積まれ、入口が整理する)、C3〜C5。あわせて 3.3-1 (定額のログイン)、3.3-3 (指示していない安全装置を足さない)、3.2-6 と C10 (承認待ちがスマホに届く)。
- 前提: 公式の機能のうち [入口と spawn の調査](research-entry-and-spawn.md) にある事実 (Remote Control の server mode、サブエージェント、`claude -p`、バックグラウンドのセッション) は調べ直さず、そのまま使う。[先行事例の調査](research-prior-art.md) の事例は、順位を使わずにこの要素の観点で読み直した (5 節)。

## 1. 答える問い

計画の 4.3 節の問いを、次の 5 つに分けて答える。

- 問い 1: 入口に返ったものに、判断を専門にする役がどう意見を出すか。
- 問い 2: 判断役で解決しなかったものだけを、どう選り分けて積むか。
- 問い 3: 積んだものをどこに置くか (ファイル、DB、セッションの中)。
- 問い 4: オーナーが後で答えたとき、元の作業へどう戻るか。
- 問い 5: 積まれたものを入口がどう整理するか。

## 2. 公式の機能で確かめた事実

出典は、とくに書かないかぎり 2026-11-03 に取得した Claude Code の公式資料である。手元の確認は、開発 PC の Claude Code 2.1.308 で、`claude -p --setting-sources ""` に `--model haiku` を付けて行った。

### 2.1 hook で判断を返す仕組み

- [hooks](https://code.claude.com/docs/en/hooks) の `type: "prompt"` の hook は、モデルに 1 回問い合わせて `{"ok": true|false, "reason": "...", "impossible": true|false}` を受け取る。`type: "agent"` の hook は、Read などの道具を使う検証役のサブエージェントを起こし、同じ形を返す。両方が使える出来事に `Stop`、`SubagentStop`、`PreToolUse`、`PostToolUse`、`TaskCompleted`、`TeammateIdle` などがある。`Stop` と `SubagentStop` で `ok: false` を返すと、`reason` が次の指示として渡り、作業が続く。`impossible: true` を添えると、そのまま止まる。既定の待ち時間は `prompt` が 30 秒、`agent` が 60 秒。
- 同じ資料の `PermissionRequest` の hook は、権限の確認を出す前に動き、`decision.behavior` に `allow` か `deny` を返す。資料は、確認を出せないセッションでも動くとし、"In sessions that can't show a prompt, such as background subagents in non-interactive mode, Claude Code still runs these hooks, and if no hook returns a decision, it denies the tool call." と書く。`--permission-prompt-tool` と並んで動き、先に決めた方が採られる。
- command の hook に `async: true` を付けると裏で動く。その結果は次の会話のターンに届く。例外として、`asyncRewake` の hook が終了コード 2 で終わると、待機中のセッションでもすぐに起こす。原文は "Exception: an `asyncRewake` hook that exits with code 2 wakes Claude immediately even when the session is idle."

### 2.2 `-p` の作業を止めて、後で戻す仕組み (`defer`)

- 同じ資料の「Defer a tool call for later」の節。`PreToolUse` の hook が `permissionDecision: "defer"` を返すと、道具は動かず、結果に `stop_reason: "tool_deferred"` と `deferred_tool_use` (道具の `id`・`name`・`input`) が載ってターンが終わる。呼び出し側は答えを集め、`claude -p --resume <session-id>` で再開する。同じ道具の呼び出しで `PreToolUse` がもう一度動き、hook が `allow` を返すと道具が動いて作業が続く。答えは `updatedInput` で渡せる。
- 待てる時間の上限は無い。原文は "There is no timeout or retry limit. The session remains on disk until you resume it, subject to the `cleanupPeriodDays` retention sweep, which deletes session files after 30 days by default"。
- 制約: `-p` のときだけ効き、対話のセッションでは無視される ("In interactive sessions it logs a warning and ignores the hook result.")。1 つのターンで道具を 1 つだけ呼んだときだけ効く。答えがまだ無いときは、プロンプトを付けずに再開し、hook がもう一度 `defer` を返せばよい。プロンプトを付けて再開すると、止めていた呼び出しは捨てられる。`-p` の再開は前の権限のモードを戻さないので、付け直す。
- `AskUserQuestion` は典型の使い道とされている。ただし `-p` で `AskUserQuestion` が使えるのは、`--permission-prompt-tool` などの permission host があるときだけである。
- 手元で確かめた (2026-11-03): 回答のファイルが無ければ `defer`、あれば `allow` を返す command の hook を `--settings` で入れ、`claude -p` に Bash で `echo` を 1 回させた。1 回目は `stop_reason` が `tool_deferred`、`deferred_tool_use` に止めた Bash の呼び出しが載って終わった。回答のファイルを置いてから、同じ `--settings` を付けてプロンプト無しで `--resume` すると、同じ呼び出しが動き、作業が終わった (`stop_reason` は `end_turn`)。

### 2.3 権限の確認を外へ渡す仕組みと、問いを封じる仕組み

- [CLI reference](https://code.claude.com/docs/en/cli-reference) の `--permission-prompt-tool` は、`-p` の権限の確認を MCP の道具に渡す。例は `claude -p --mcp-config ./mcp.json --permission-prompt-tool mcp__permissions__approve "query"`。
- [Run Claude Code programmatically](https://code.claude.com/docs/en/headless): `-p` の既定は Manual のモードで、確認が要る呼び出しは、hook か `--permission-prompt-tool` が許さないかぎり断られる。`--permission-prompts none` を付けると、誰にも確認を回さずに断り、`AskUserQuestion` のような人の答えが要る道具も外す。原文は "With `--permission-prompts none`, Claude Code removes the tools that need an answer from a person, such as `AskUserQuestion`, so Claude can't call them."

### 2.4 セッションの間のメッセージで起こす仕組み

- [cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging): 待機中のセッションにメッセージが届くと、新しいターンが始まる。原文は "When the receiving session is idle, Claude Code starts a new turn with the message."
- `-p` のセッションも受け取り口 (inbox socket) を持つ。人のいない `-p` に受け取らせるには、`--settings` で `crossSessionInbound` を `accept` にする。`--bare` で起動したセッションは受け取れない。
- 受け取り口のパスは、hook と Bash に `CLAUDE_CODE_MESSAGING_SOCKET` として渡る。自分の子のプロセスからの投稿は、設定が無くても届く。
- 受け取り側に設定が無いとき、届けるか保留するかは両方の権限のモードで決まる。受け取り側が確認を出すモードなら、メッセージは届く。ただし送り手が権限の確認を飛ばすモードだと、保留される。
- 次に待機に入ったら 1 回知らせてもらう `notify_when_idle` がある。使えるのは主の会話からだけで、相手は同じ機械のセッションに限る。12 時間で切れる。受け取り側は、受け付けたメッセージを 50 件まで、保留を 100 件まで持つ。
- 他のセッションからのメッセージは、承認の代わりにならない。原文は "It can't approve anything: a message from another session never counts as your consent, so it can't answer a pending permission prompt on your behalf."

### 2.5 バックグラウンドのセッションと agent teams

- [agent-view](https://code.claude.com/docs/en/agent-view): `claude agents --json` の `waitingFor` が、承認待ちと入力待ちを分けて示す。権限の確認で止まったセッションのプロセスは動き続ける。答えを待つ状態で約 1 時間誰もつながないと、プロセスは止まり、会話は残る。`claude --resume <id> --bg` で続きを裏で動かせる。
- [agent-teams](https://code.claude.com/docs/en/agent-teams) は試験的な機能で、既定で無効。対話のセッションでだけ teammate を起こし、`-p` では起こさない。teammate はさらに teammate を起こせない。teammate の権限の確認は lead のセッションに出る。`TaskCompleted` と `TeammateIdle` の hook で、完了の点検を置ける。

### 2.6 入口 (対話のセッション) で積まれ方が変わる点

- 入口は Remote Control の対話のセッションである ([入口と spawn の調査](research-entry-and-spawn.md) の V1)。対話のセッションでは `defer` が無視されるので、2.2 節の仕組みは入口の下で動く `-p` の作業にだけ使える。
- Remote Control では、権限の確認と質問は、答えるまで端末に出たまま待つ (同じ調査の V1)。入口が自分のターンの中で問いを出すと、そのターンは答えまで止まる。
- [channels](https://code.claude.com/docs/en/channels) は、動いているセッションに外から出来事を押し込む MCP サーバーで、研究プレビューである。権限の確認をチャットへ回す permission relay を持てる。自作のチャネルを試すには `--dangerously-load-development-channels` が要る。

## 3. 候補の台帳

各候補の仕組み、`claude` との接続、最後のコミット (既定のブランチ、UTC)、ライセンス。リポジトリの情報は 2026-11-03 に GitHub の API で取った。

### 3.1 区分 2 から 4: Claude Code の上で判断役や判断待ちを持つもの

**goalkeeper** ([bonfire-systems/goalkeeper](https://github.com/bonfire-systems/goalkeeper))

- 仕組み: Claude Code の plugin。`goal-judge` の skill が判断役で、既定では Agent の道具で新しいサブエージェントを起こす。原文は "spawn a fresh **general-purpose** subagent via the Agent tool with the brief as its entire prompt"。判定は VERDICT / REASONS / FIX_LIST / NOTES の形で `gk verdict <slug> approve|reject` に渡す。差し戻しが上限に達すると `NEEDS_HUMAN` になる。原文は "`NEEDS_HUMAN` — max rejections; surface the fix-list verbatim and instruct: fix manually, then `/goal-resume`"。重い関門では 2〜3 体の判断役を並べ、全員の承認で通す。
- 置き場所: `.claude/goals/<slug>/` の状態とログ (副調査の読み取り。状態のファイルの中身は確かめていない)。
- `claude` との接続: plugin として入れ、同じセッションの中で判断役を起こす。`claude -p` の行は確かめていない。
- 最後のコミット 2026-08-31、MIT。

**subagent-loop** ([MustafaMese/subagent-loop](https://github.com/MustafaMese/subagent-loop))

- 仕組み: `agents/loop-judge.md` が判断役のサブエージェントの定義 (`model: opus`、Edit の道具を持たない)。判定はファイルに `VERDICT: ACCEPT | FIX | ESCALATE` の形で書く。ESCALATE は、既にある歯止めにかかったときか、決定が欠けているときだけに使う。原文は "`ESCALATE` — only for an existing loop brake or a missing decision"。
- 置き場所: 判定のファイル。人に回す論点を ledger に積む記述があるが、副調査の読み取りで、本文は照合していない。
- `claude` との接続: 同じセッションの中のサブエージェント。
- 最後のコミット 2026-11-02、MIT。

**Agent 007** ([bill10/agent-007](https://github.com/bill10/agent-007))

- 仕組み: 管理役のエージェント Billion がオーナーの唯一の窓口になり、作業者のカードを出し、権限の確認に答え、差分を読んで取り込むかを決める。オーナーへの問いは `notify_owner` で積み、1 日 2 回のブリーフィングでまとめて出す。原文は "So Billion comes to the owner twice a day, not whenever a question occurs to it." と "`notify_owner` no longer shows a question: it queues it under its `project`, which is the department."。ブリーフィングでは、プロジェクトごとに優先度の高い 2 件を出す (blocking、normal、low の順)。前回出して答えの無い問いは `consolidated` として閉じ、Billion が要るものだけ積み直す。スマホには Telegram で、ブリーフィングごとに 1 通だけ送る。blocking の問いはブリーフィングを待たずにスマホへ届く。
- 置き場所: ファイル。問いの一覧は `~/.agent-007/waiting.json`、ブリーフィングの記録は `rounds.json`。
- 戻り方: オーナーの答えは `[Owner via app] Q3: <answer> ...` の形で Billion の端末に入り、Billion が続ける。
- `claude` との接続: Billion は PTY で `claude --dangerously-skip-permissions` を起動し、再起動のときは `--continue` を付ける (docs/BILLION.md の Step 1)。
- 最後のコミット 2026-10-31、MIT。

**Gas Town** ([gastownhall/gastown](https://github.com/gastownhall/gastown)。旧名 steveyegge/gastown)

- 仕組み: 役のあいだを段で上げるエスカレーション。作業者が `gt escalate -s <SEVERITY>` で上げ、Deacon、Mayor、Overseer (人) の順に、解決するか次へ渡す。原文は "Each tier can resolve OR forward. The chain is tracked via bead comments." ([docs/design/escalation.md](https://github.com/gastownhall/gastown/blob/main/docs/design/escalation.md))。重さに応じて、記録だけ・Mayor へのメール・人へのメールや SMS に分けて送る。人が `gt escalate ack` で受けないまま `stale_threshold` (既定 4 時間) を過ぎると、重さを上げて送り直す。Mayor は起動のたびに積まれたものを重さごとに並べる。原文は "On `gt prime`, Mayor displays pending escalations grouped by severity."。
- 置き場所: `type: escalation` の bead (作業の記録の単位) と、`gt mail`。
- 戻り方: 段で解決すると、作業を割り当て直す ("resolves --> updates issue, re-slings work")。人が答えたあとの再開の手順は、資料に書かれていない。
- `claude` との接続: 役ごとに `claude --dangerously-skip-permissions` を対話で起動する (`internal/config/agents.go` の `AgentClaude` の定義)。
- 最後のコミット 2026-10-28、MIT。

**ccmanager** ([kbwo/ccmanager](https://github.com/kbwo/ccmanager))

- 仕組み: 確認待ちで止まったセッションについて、Enter を押してよいかを、別のプロセスの `claude -p` に判定させる。資料は既定の呼び出しを "By default CCManager runs `claude --model haiku -p --output-format json --json-schema …`" と書く ([docs/auto-approval.md](https://github.com/kbwo/ccmanager/blob/main/docs/auto-approval.md))。判定の形は `{"needsPermission": true|false, "reason"?: "..."}`。判定に失敗したら人の確認に回す。
- 置き場所: ccmanager の画面のセッションの状態。積む仕組みは無い。
- 判定の対象は「確認に Enter を押してよいか」で、成果物の合否ではない。
- 最後のコミット 2026-10-27、MIT。

**claude-workflow** ([alex-robert-fr/claude-workflow](https://github.com/alex-robert-fr/claude-workflow))

- 仕組み: Stop の hook から `claude -p --json-schema` で判断役を呼び、`{"ok":boolean,"raison":string}` を受け取る。`ok` が false なら終了コード 2 で作業者に差し戻す。人へ上げる仕組みは無い。定額のログインでは `--bare` がキーチェーンを読まないため、`--bare` を使わない旨を書いている (副調査の読み取り。本文は照合していない)。
- 最後のコミット 2026-09-13、ライセンスは API では未設定。

**HumanLayer** ([humanlayer/humanlayer](https://github.com/humanlayer/humanlayer))

- 今の状態: 以前の SDK (`require_approval` など) と、`--permission-prompt-tool` に渡す MCP サーバー (`humanlayer mcp claude_approvals`) は、今の main には無い (副調査の読み取り。旧版は `legacy` ブランチと v0.7.9 のタグ)。今の製品は、Claude Code の plugin がセッションを HumanLayer の Web に写し、Web から返事・停止・権限の確認への回答ができるもの。原文は "From the web app you can reply, stop a turn, answer permission prompts and comment on task files." ([apps/riptide-claude-code-plugin/README.md](https://github.com/humanlayer/humanlayer/blob/main/apps/riptide-claude-code-plugin/README.md))。Claude Code 2.1.287 以上と HumanLayer のアカウントが要る。
- 置き場所: HumanLayer のサーバー。待つ間、同じ Claude Code のプロセスが答えを待つ形 (副調査がコードで読んだ範囲)。
- 最後のコミット 2026-11-02、Apache-2.0。

**claude-remote-approver** ([yuuichieguchi/claude-remote-approver](https://github.com/yuuichieguchi/claude-remote-approver))

- 仕組み: `PermissionRequest` の hook が ntfy でスマホに確認を送り、ボタンの答えを待つ。`AskUserQuestion` の選択肢もボタンにする。時間切れは既定 120 秒で、過ぎると端末の確認に戻す。原文は "If no response is received within the configured timeout (default: 120 seconds), the hook falls back to the **CLI prompt** (`ask`), so you can still respond at your terminal."
- 置き場所: 無い (hook のプロセスの中で待つ)。
- 最後のコミット 2026-03-02、MIT。
- 同じ型のもの (副調査の読み取り。本文は照合していない): [coa00/claude-push](https://github.com/coa00/claude-push) (bash の hook、既定 90 秒)、[FilipCondac/claude-pager](https://github.com/FilipCondac/claude-pager) (Notification の hook と常駐の daemon。答えを tmux のキー入力で返す)、[onegrep/cco-mcp](https://github.com/onegrep/cco-mcp) (`--permission-prompt-tool` に渡す MCP サーバー。待ちはメモリの上で、既定 5 分で自動的に断る。最後のコミット 2025-07-08、MIT)。

**gotoHuman の MCP サーバー** ([gotohuman/gotohuman-mcp-server](https://github.com/gotohuman/gotohuman-mcp-server))

- 仕組み: Claude が MCP の道具でレビューを依頼すると、依頼の ID とリンクをすぐ返す。人が答えると、指定した URL に webhook が届く。続きを起こす側は自前で書く (副調査の読み取り。本文は照合していない)。gotoHuman のアカウントと API キーが要る。
- 最後のコミット 2026-10-01、MIT。

**codeArbiter** ([arbiterForge/codeArbiter](https://github.com/arbiterForge/codeArbiter))

- 人にしか答えられない未決を `[CONFIRM-NN]` として `.codearbiter/open-questions.md` に番号付きで置く、と副調査が読んだ。本文は照合しておらず、`claude` の起動のしかたも確かめていない。
- 最後のコミット 2026-11-02、AGPL-3.0。

**ruflo** ([ruvnet/ruflo](https://github.com/ruvnet/ruflo)。旧名 claude-flow) と **superpowers** ([obra/superpowers](https://github.com/obra/superpowers))

- ruflo には、検証役を複数起こして合意で決め、決まらなければ呼び出し元へ上げる定義がある。superpowers の subagent-driven-development は、作業ごとにレビュー役のサブエージェントを起こし、人を待たずに決めて記録に残す。どちらも副調査の読み取りで、本文は照合していない。人の判断待ちを積む場所は、どちらにも見つかっていない。
- 最後のコミット: ruflo 2026-11-01、superpowers 2026-10-21。どちらも MIT。

**Jev** (TypeSafe)

- 仕組み: [TypeSafe](https://typesafe.ai) の判定のモデル。サイトは "Send Jev structured questions and get typed decisions with probabilities and confidence that your software can act on." と書き、Jev は early access とする。オーナーの今の運用では skill から呼び、答えを bool・ラベル・数値のどれか 1 つの値と終了コードにして返す。問いは英語で書く必要がある。
- `claude` との接続: Claude ではなく、TypeSafe の API を自分の API キーで呼ぶ。hook の command から呼べる。
- 出せるのは分類と確率で、意見の文は出さない。

### 3.2 区分 1: 設計の参考 (`claude` を部品にしないもの)

- LangChain の Agent Inbox ([langchain-ai/agent-inbox](https://github.com/langchain-ai/agent-inbox)): アーカイブ済み (最後のコミット 2026-09-18、MIT)。LangGraph の interrupt で止まったスレッドを一覧し、人の答えで再開させる画面。入力は LangGraph の interrupt に限られ、Claude Code への言及は README に無い (副調査の読み取り)。
- LangGraph ([interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)): 止めた時点の状態を永続化の層に保存し、同じスレッドの ID で再開する。原文は "When an interrupt is triggered, LangGraph saves the graph state using its persistence layer and waits indefinitely until you resume execution." と "The `thread_id` you choose is effectively your persistent cursor."
- OpenAI Agents SDK ([human_in_the_loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)): 承認待ちで止めた実行の状態 (`RunState`) を、呼び出し側が保存して後で戻す。原文は "`RunState` is designed to be durable."。保存先は SDK が決めない。
- CrewAI、Microsoft Agent Framework、Google ADK も、人の待ちで実行を止め、状態を保存し、識別子を付けて再開する形を持つ (副調査の読み取り。本文は照合していない)。判断役の判定のあと人に上げることを専用の概念として持つ枠組みは、読んだ範囲では見つかっていない。どの枠組みも、判定する役と人の待ちの仕組みを組み合わせて作る。

## 4. 問いごとの答え

### 問い 1: 判断役がどう意見を出すか

使える部品

- 入口のセッションの中で、判断役のサブエージェントを起こす (3.1-4、C4)。定義に判断役の指示と記憶を書ける (サブエージェントの定義の `memory`。[入口と spawn の調査](research-entry-and-spawn.md) の V2)。例: goalkeeper の goal-judge、subagent-loop の loop-judge。
- 別のプロセスの `claude -p --json-schema` で判断役を起こし、決まった形の判定を受け取る (3.1-4、3.3-1、C4)。例: ccmanager、claude-workflow。
- `Stop` か `SubagentStop` の hook に `type: "prompt"` か `type: "agent"` を置き、`{ok, reason}` を受け取る (3.1-4、C4)。
- Jev を、意見を出したあとの選り分け (問い 2) に使う。

証拠

- 2026-11-03 に手元で、判断役の指示と、`resolved` と `escalate` の 2 値を持つ `--json-schema` を `claude -p` に渡した。性能に差が無くオーナーの好みで決まる、という作業者の結果を与えると、`structured_output` に `{"verdict":"escalate","question":"…"}` が返った。
- 3 節の各候補の出典。

埋めるべき隙間

- prompt と agent の hook は、続けるか止めるかの 2 値と理由の文を返す仕組みである。判断役の意見を「オーナーへの問い」の形で取り出して積むには、command の hook か、別のプロセスで呼ぶ形にする。
- 判断役に何を判断させ、何をオーナーに残すかの基準は、どの部品にも無い。判断役の指示として書く。

### 問い 2: 解決しなかったものだけをどう選り分けるか

使える部品

- 判断役の出力に「上げる」の値を持たせ、決まった形で受け取る (3.2-3、C4)。手元の `--json-schema` の確認、subagent-loop の `ESCALATE`、goalkeeper の `NEEDS_HUMAN`、Gas Town の段ごとの「解決するか、次へ渡すか」。
- 担い手がオーナーに直接問えないようにする: `-p` の担い手に `--permission-prompts none` を付けると、`AskUserQuestion` が外れ、確認が要る呼び出しは断られる (C5)。`--permission-prompts host` で permission host を持たせると、担い手の問いと確認は、そのホストへ回る。

証拠

- 2.3 節、2.2 節、3 節。

埋めるべき隙間

- 担い手の問いを判断役に回す経路は、公式には無い。permission host (MCP の道具) か `PreToolUse` の hook が担い手の問いを受け、判断役に渡すつなぎが要る。
- `PermissionRequest` を外へ渡す既製の部品 (claude-remote-approver、claude-push、claude-pager、cco-mcp、HumanLayer) は、どれも確認を 1 件ずつそのまま人に送る。判断役で選り分けたあとに置かないと、担い手が作業のたびにオーナーへ確認を求める形になり、C5 に反する。また、どれも同じプロセスの中で待つか、数分で時間切れにして端末の確認に戻す。非同期に積む形ではない。

### 問い 3: 積んだものをどこに置くか

使える部品

- セッションの記録 (3.2-3): `defer` で止めた `-p` の作業は、止めた道具の呼び出しごとセッションの記録に残る。上限の時間は無く、既定 30 日の掃除まで残る。担い手の作業の「続きの状態」はここに置ける。
- ファイル (3.2-3): Agent 007 (`waiting.json`)、Gas Town (bead と mail)、goalkeeper (`.claude/goals/<slug>/`)、codeArbiter (`open-questions.md`)。どれも 1 件 1 項目で、識別子・状態・優先度を持つ。
- DB: 区分 1 の LangGraph の checkpointer、CrewAI の SQLite。先行事例では van Deth が Supabase の表をタスクの待ち行列にしている。

証拠

- 2.2 節、3 節。

埋めるべき隙間

- セッションの記録は止めた作業の続きを持つが、「オーナーへの問い」の一覧は持たない。入口が整理するための一覧 (問いの文、起こしたセッション、止めたセッションの ID、優先度、状態) は別に置く必要がある。置き場の形を定めた既製の部品で、`claude` の `defer` と組んだものは見つかっていない。
- 入口は対話のセッションなので、入口自身が出す問いは `defer` で止められない (2.6 節)。入口の問いも一覧に書く形にしないと、入口のターンが答えまで止まる。

### 問い 4: オーナーが後で答えたとき、元の作業へどう戻るか

使える部品

- `defer` と `--resume` (3.2-3、C5): 答えが置かれたら、止めたセッションをプロンプト無しで `claude -p --resume <session-id>` し、hook が `allow` と答えを返す。2026-11-03 に手元で往復を確かめた (2.2 節)。
- 判断の結果を文で渡して続ける (3.2-3): 作業者のセッションが止まらずに終わっていれば、`claude -p --resume <session-id> "<オーナーの答え>"` で同じ会話に答えを足せる。2026-11-03 に手元で、判断役の会話を別のフォルダから `--resume` し、前の会話の中身を引き継いで答えたことを確かめた。
- 動いているセッションへメッセージを送る (3.2-3): 待機中のセッションは、届いたメッセージで新しいターンを始める (2.4 節)。動き続けるバックグラウンドのセッションや、`crossSessionInbound` を `accept` にした `-p` の作業者に使える。
- 参考: tmux のキー入力で返す (claude-pager)、Telegram の返事を管理役の端末に入れる (Agent 007)、webhook で続きを起こす (gotoHuman)。

証拠

- 2.2 節、2.4 節、3 節。

埋めるべき隙間

- 答えを受けて `--resume` を起こすのは、呼び出し側のプロセスの役目である。答えの置き場を見て再開を起こす部品は無い。
- `defer` の制約: 1 ターンに道具を 1 つだけ呼んだときしか効かない。`-p` の再開では、権限のモードと `--settings` などを付け直す必要がある。
- 他のセッションからのメッセージは承認として扱われない (2.4 節)。オーナーの答えを担い手に渡す経路は、権限の確認への回答ではなく、作業への指示か hook の答えとして渡す形になる。

### 問い 5: 積まれたものを入口がどう整理するか

使える部品

- Agent 007 のブリーフィング (3.2-3、C4、C10 の参考): 問いを部門ごとに積み、決まった時刻に優先度の高い 2 件ずつ出し、前回の答えの無い問いを閉じ、要るものだけ積み直す。スマホにはブリーフィングごとに 1 通だけ送り、急ぐ問いだけすぐに送る。積まれた問いを、入口に当たる管理役が整理する例として見つかったのはこれだけである。
- Gas Town: 積まれたものを重さで並べて出し、受けないまま時間が過ぎたら重さを上げて送り直す。
- 入口を起こす経路: 担い手や判断役から `SendMessage` (待機中の入口で新しいターンが始まる)、入口の子のプロセスから受け取り口のソケットへの投稿、`asyncRewake` の hook の終了コード 2、Channels (研究プレビュー)、オーナーが次に話しかけたとき。

証拠

- 2.1 節、2.4 節、2.6 節、3 節。

埋めるべき隙間

- 入口に積まれたものの一覧を読ませ、整理の結果をオーナーに見せる手順は、入口の指示 (と skill) として書く。Agent 007 の整理の規則は製品の中にあり、部品として取り出せる形ではない。
- 判断待ちが積まれたことをスマホに知らせる経路 (C10) は、4.7 節の調査の範囲である。この要素からは、知らせる時点 (1 件ごとか、まとめてか) を決める入力を渡す。

## 5. 先行事例をこの要素で読み直す

[先行事例の調査](research-prior-art.md) の事例のうち、判断役か判断待ちに関わる記述があるもの。順位は使わない。

- CommandMate の窓口・管理・ワーカー (kewton): 合否は LLM の判断役ではなく、`.commandmate/verify.yaml` に定めたゲートの結果で決める。相手が確認待ちで止まると、依頼した側は代わりに答えず、そのまま人に返る。判断待ちを積む場所は書かれていない。
- BridgeBoard の秘書と部門エージェント (yuto): 秘書が CEO の好みと過去の判断を `memory.yaml` に持つ。危ない作業は、秘書が CEO に確認してからタスクにする。判断役に過去の判断を持たせる記憶の置き方の参考になる。
- Neutron (Ryan Junee): コードを見る役と、コード以外を見る役のレビュー役がいる。結果は元の話題に投稿される。判断待ちを積む場所と、人の答えのあとの戻り方は書かれていない。記事のレビュー役の文は照合していない。
- Channels と作業者のデーモン (Vincent van Deth): 長い仕事を Supabase のタスクの表に積み、デーモンが `claude -p` で処理する。判断待ちではなく作業の待ち行列だが、DB に積んで `claude -p` を起こす形の参考になる。
- @ryu-ki: スレッドの目的と状態の台帳を、返信の前に読ませる。入口が積まれたものを整理する前に一覧を読む形の参考になる。
- Kai、mager、コキエほか: 判断役と判断待ちについての記述は無い。

## 6. この要素でつなぎのスクリプトが要る所

- 判断待ちの一覧の置き場と、その読み書き。1 件ごとに、問いの文、起こしたセッション、止めたセッションの ID、判断役の意見、優先度、状態を持つ。既製の部品の形 (Agent 007 の `waiting.json`、Gas Town の bead) は参考にできるが、`claude` の `defer` と組んだものは見つかっていない。
- 担い手の問いと確認を判断役へ回す口。`-p` の担い手の permission host (MCP の道具) か `PreToolUse` の hook が受けて、判断役を呼び、解決すれば答えを返し、しなければ `defer` を返して一覧に書く。
- 判断役の呼び出し。`claude -p --json-schema` で、解決したか、上げるか、オーナーへの問いの文を受け取る。
- 再開の駆動。オーナーの答えが一覧に入ったら、止めたセッションを `claude -p --resume` で起こす。起こすときに `--settings` と権限のモードを付け直す。
- 入口を起こす経路。一覧が増えたとき、または答えが入ったときに、待機中の入口へメッセージを送る (`SendMessage`、受け取り口のソケット、`asyncRewake` のどれか)。
- 入口自身の問いを一覧に書く手順。入口は対話のセッションで `defer` が効かないので、入口の指示か skill で書く。

## 7. 確かめていないこと

- `PermissionRequest` の hook が、`-p` の主の会話の確認で動くか。資料は、確認を出せないセッションでも動くと書くが、手元では試していない。
- 入口 (Remote Control の server mode のセッション) で agent teams が使えるか。
- `defer` で止めたセッションを、別の機械 (開発 PC とミニ PC) をまたいで `--resume` できるか。セッションの記録はその機械のディスクにある。
- `defer` の既知の不具合の報告 (止めた道具の入力が大きいと再開が止まる、とされる [anthropics/claude-code#41794](https://github.com/anthropics/claude-code/issues/41794))。報告の本文は読んでいない。
- 副調査の読み取りと書いた箇所の原文 (goalkeeper の状態のファイル、subagent-loop の ledger、HumanLayer の旧版と待ち方、claude-push、claude-pager、cco-mcp、gotoHuman、codeArbiter、ruflo、superpowers、CrewAI、Microsoft Agent Framework、Google ADK)。
