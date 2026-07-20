# PDA 全体設計文書

- 作成日: 2026-07-20
- 対象: Personal Delegate Agent（PDA）プロジェクト
- 作成方法: 開発PC上のClaude Code（Fable）による設計セッション。対象ミニPCへのライブ接続は行っていない

## 1. この文書群の位置付け

本ディレクトリは、PDAの現状から最終到達状態までの全体設計を記録する。構想書
[personal_delegate_agent_plan.md](../../personal_delegate_agent_plan.md) と
セットアップ記録 [pda_minipc_setup_record.md](../../pda_minipc_setup_record.md) は
**史料（historical record）** として保持し、本設計文書はそれらを批判的に統合した
**現行の設計正本（design authority）** である。

[.hermes/plans/2026-07-20_202237-pda-current-state-and-next-roadmap.md](../../.hermes/plans/2026-07-20_202237-pda-current-state-and-next-roadmap.md)
は承認済み仕様ではなく設計仮説であり、本設計で独立に評価した（採否は
[10-open-questions-and-decisions.md](10-open-questions-and-decisions.md) と各ADRに記録）。

## 2. 読む順序

| # | 文書 | 内容 |
|---|------|------|
| 1 | [01-requirements-and-invariants.md](01-requirements-and-invariants.md) | 目的、non-goals、システム境界、用語、不変条件、要求一覧、traceability matrix |
| 2 | [02-current-state-and-gaps.md](02-current-state-and-gaps.md) | 検証済み現状、資料間矛盾、現在フェーズ判定、ギャップとリスク |
| 3 | [03-target-architecture.md](03-target-architecture.md) | 論理／配備アーキテクチャ、責務、正本と権限、主要シーケンス、コア交換境界 |
| 4 | [04-context-spine-and-data-contracts.md](04-context-spine-and-data-contracts.md) | データライフサイクル、全canonical contract定義、状態機械、検索、削除、再構築 |
| 5 | [05-orchestration-and-runtime-contracts.md](05-orchestration-and-runtime-contracts.md) | task/run lifecycle、runtime adapter、MCP契約、ルーティング、handoff、障害処理 |
| 6 | [06-security-privacy-and-governance.md](06-security-privacy-and-governance.md) | 機密区分、信頼境界、脅威モデル、承認、監査、自己改変統治 |
| 7 | [07-deployment-operations-and-recovery.md](07-deployment-operations-and-recovery.md) | サービストポロジ、ネットワーク、secret、観測、バックアップ／復元、劣化運転 |
| 8 | [08-evaluation-and-phase-gates.md](08-evaluation-and-phase-gates.md) | 評価harness、gold set、metric仮説、フェーズゲート |
| 9 | [09-transition-roadmap.md](09-transition-roadmap.md) | マイルストーン、依存関係、critical path、最初のvertical slice、stop/go |
| 10 | [10-open-questions-and-decisions.md](10-open-questions-and-decisions.md) | 決定一覧とユーザー判断が必要な未決事項 |
| 11 | [../adr/](../adr/) | 主要判断のArchitecture Decision Record |

初見の読者は 01 → 02 → 03 の順で全体像を得たあと、関心領域の文書へ進むこと。
実装着手者は 09（最初のslice）→ 04／05（contract）→ 08（合格条件）の順を推奨する。

## 3. 文書のauthority（優先順位）

記述が矛盾した場合の優先順位は次のとおり。

1. `docs/adr/` の **Accepted** なADR
2. `docs/design/01`〜`10`（本設計文書）
3. `.hermes/plans/` 配下の提案文書（仮説。採用された部分は本設計に取り込み済み）
4. `personal_delegate_agent_plan.md` / `pda_minipc_setup_record.md`（史料。意図と経緯の一次資料だが、設計判断としては本設計が上書きする）

史料への修正が必要な場合、史料を直接書き換えず、まず
[02-current-state-and-gaps.md](02-current-state-and-gaps.md) の矛盾一覧に差分提案として記録する。

## 4. 記述区分の凡例

全文書で次の区分を用いる（[../../.hermes/prompts/claude-fable-full-system-design.md](../../.hermes/prompts/claude-fable-full-system-design.md) 第2節に準拠）。

- **Fact**: 文書、実機確認、公式仕様で検証できた事実。確認日と確認方法を伴う
- **Requirement**: ユーザーの目的または構想から導かれる要求（`R-xx`）
- **Assumption**: 未確認だが設計上いったん置く仮定（`A-xx`）
- **Proposal**: 採否未確定の設計案
- **Decision**: 比較検討後に本設計で採用する判断（`D-xx`、主要なものはADR化）
- **Open Question**: ユーザー判断または追加検証が必要な事項（`OQ-xx`）

ミニPCの状態に関するFactはすべて **2026-07-20時点の文書記録スナップショット** であり、
本設計セッションからはライブ再確認していない。それ以降に変化し得る事項は
`Unverified/Stale Candidate` と明示する。

## 5. 更新規則

1. 設計変更はまず該当文書を更新し、主要判断の変更はADRの追加（旧ADRのSuperseded化）で行う
2. 不変条件（`INV-xx`）の変更は必ず人間（本人）の明示承認を要する。PDA自身による自動変更の対象外（[06](06-security-privacy-and-governance.md) 参照）
3. requirement ID・invariant ID・decision ID・contract名は文書間で共有する。改番せず追記する
4. Mermaid図中のcomponent名・interface名・data object名は本文およびcontract定義と一致させる。図だけの先行変更を禁止する
5. secret、個人データ本文、会社情報を本文書群へ記載しない
6. 各文書冒頭に最終更新日を記す

## 6. 用語の正本

用語定義は [01-requirements-and-invariants.md](01-requirements-and-invariants.md) 第4節を正本とする。
他文書では再定義しない。
