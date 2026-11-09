# Claude 一本化の検討

- 更新: 2026-11-03 JST
- 種別: 検討の作業場所。オーナーが求めているものと、それに対する決定をこのディレクトリに置く。
- 位置付け: v0.3 の決定 ([docs/reports/v0.3-decision.md](../reports/v0.3-decision.md)) では、フロントドアに OpenClaw を選び、Claude Code と Codex を実行器にした。本件は、OpenClaw と Codex をやめて Claude Code に一本化できるかを検討する。結論が出るまで、v0.3 の決定と運用は変えない。

## 目的

Claude Code Desktop をフロントドアにし、PDA で実現したかったこと (役ごとに指示・メモリ・hook を分けて確実に効かせること) を、Claude Code CLI を包むスクリプトなどで満たせるかを確かめる。満たせるなら OpenClaw と Codex をやめる。

## 進め方

PDA の既存の書き方で、オーナーが求めているもの、それに対する決定の順に整理する。[AI-DLC Workflows](https://github.com/awslabs/aidlc-workflows) は同じ順序の先行例で、道具は入れない。

- オーナーが求めているもの: [requirements.md](requirements.md) に置く。調査と設計は、この要件を物差しにする。
- 決定: 本文書の「オーナーの判断の記録」に日付ごとに書く。

## 決まっていないこと

入口の要件を読み直している (2026-11-10)。オーナーが、リモートのセッションを入口にする形は使いづらいと述べたため、[requirements.md](requirements.md) の 3.1 の 1 と 2 をオーナーの回答で改める。部品の調査 ([research-plan.md](research-plan.md) と research-parts-*.md) は、入口の要件が決まってから読み直して使う。

## オーナーの判断の記録

### 2026-11-10

- リモートのセッションを入口にする形は、PC とスマホの両方で使いづらい。入口の要件を言語化し直す (発言は requirements.md の 2 節)。

### 2026-11-03

- AI-DLC は道具を入れず、PDA の既存の書き方で進める。
- 作業場所は `docs/claude-unification/` にする。
- 入口は 1 つにする。OpenAI の [Dots](https://techcrunch.com/2026/09/29/openai-launches-dots-its-bubbly-agentic-avatar/) のように、リモートに常駐するフロントドアのエージェントに複数の端末から話しかけ、そのエージェントが別のセッションを立ち上げて作業を移す形をとる。
- Claude Code での一本化もこの形にする。ミニ PC 上で長く動き続ける 1 つのセッションを、リモートのセッションか Claude Desktop から使い、そのセッションがセッションを spawn する道具で、作業と役を割り当てた別のセッションを起こす。spawn を `claude -p` のセッションの起動で行い、作業をうまく移せれば、役ごとの文脈を個別に注入できる。
- 発想は「Claude Code をどう有効に使うか」ではなく、「Claude の上に Dots のようなパーソナルエージェントを作り、1 つの入口として使い、そこにセッションを spawn する機能を持たせる」である。先行事例を含めて幅広く調べる。
- 先行事例は、公式の機能や OSS の製品ではなく、Claude でパーソナルエージェントやセカンドブレインを作った実践者の記事と実装を指す ([research-prior-art.md](research-prior-art.md))。
- 入口の画面は Claude Desktop と Claude アプリのリモートのセッションとする。
- 調査と設計の前に要件を固める。要件の正本は [requirements.md](requirements.md) とする。
