# Claude 一本化の検討

- 更新: 2026-11-03 JST
- 種別: 検討の作業場所。オーナーが求めているものと、それに対する決定をこのディレクトリに置く。
- 位置付け: v0.3 の決定 ([docs/reports/v0.3-decision.md](../reports/v0.3-decision.md)) では、フロントドアに OpenClaw を選び、Claude Code と Codex を実行器にした。本件は、OpenClaw と Codex をやめて Claude Code に一本化できるかを検討する。結論が出るまで、v0.3 の決定と運用は変えない。

## 目的

Claude Code Desktop をフロントドアにし、PDA で実現したかったこと (役ごとに指示・メモリ・hook を分けて確実に効かせること) を、Claude Code CLI を包むスクリプトなどで満たせるかを確かめる。満たせるなら OpenClaw と Codex をやめる。

## 進め方

PDA の既存の書き方で、オーナーが求めているもの、それに対する決定の順に整理する。[AI-DLC Workflows](https://github.com/awslabs/aidlc-workflows) は同じ順序の先行例で、道具は入れない。

- オーナーが求めているもの: このディレクトリの `requirements.md` に置く。
- 決定: 本文書の「オーナーの判断の記録」に日付ごとに書く。

## 決まっていないこと

- 入口になる常駐のセッションと、そこからのセッションの spawn を、どの部品で作るか (ベンダーの機能、先行事例、自作)。スマホと PC から届くこと、spawn した先の見渡しを含む ([docs/plan-v0.3.md](../plan-v0.3.md) の 2.1 節、R4、R5)。
- 入口のセッションと、spawn したセッションで、規約をどこに効かせるか。

## オーナーの判断の記録

### 2026-11-03

- AI-DLC は道具を入れず、PDA の既存の書き方で進める。
- 作業場所は `docs/claude-unification/` にする。
- 入口は 1 つにする。OpenAI の [Dots](https://techcrunch.com/2026/09/29/openai-launches-dots-its-bubbly-agentic-avatar/) のように、リモートに常駐するフロントドアのエージェントに複数の端末から話しかけ、そのエージェントが別のセッションを立ち上げて作業を移す形をとる。
- Claude Code での一本化もこの形にする。ミニ PC 上で長く動き続ける 1 つのセッションを、リモートのセッションか Claude Desktop から使い、そのセッションがセッションを spawn する道具で、作業と役を割り当てた別のセッションを起こす。spawn を `claude -p` のセッションの起動で行い、作業をうまく移せれば、役ごとの文脈を個別に注入できる。
- 発想は「Claude Code をどう有効に使うか」ではなく、「Claude の上に Dots のようなパーソナルエージェントを作り、1 つの入口として使い、そこにセッションを spawn する機能を持たせる」である。先行事例を含めて幅広く調べる。
