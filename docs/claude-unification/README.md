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

- スマホから届く入口と作業の見渡しを、Claude Code Desktop の形でどう用意するか ([docs/plan-v0.3.md](../plan-v0.3.md) の 2.1 節、R4、R5)。
- オーナーが話すセッションと、スクリプトから起動するセッションで、規約をどこに効かせるか。

## オーナーの判断の記録

### 2026-11-03

- AI-DLC は道具を入れず、PDA の既存の書き方で進める。
- 作業場所は `docs/claude-unification/` にする。
