# goal M1 完了記録（2026-08-29）

- Status: complete
- 対象: `docs/roadmap/autonomous-improvement-goal.md` M1「統治核 — 思想準拠の強制力」
- exit gate（同文書153-161行）: (1) workerの自己完了・保護解除・スコープ逸脱の敵対的テストが全て遮断される、(2) 全finalizationが決定論的な不変条件チェックを通る、(3) ADRがオーナー承認済み。

## 1. exit gate 1: 敵対テストの遮断

- 統治ファイル変更の拒否ゲートと独立検証(`independent_verification`)の全カード必須化を承認ゲート両系（plugin/installer）へ実装。実装前後の4レンズ並列反証レビューでblocker 2件（強制層自身の保護漏れ=自己永続化経路、git renameによる統治パスのdiff隠蔽）とmajor 2件（検証者自己申告の限界明示・assignee照合、activate時のdashboard未再起動）を修正しテスト固定（計69件）。
- ルーター側にコミット済みpolicyの二重確認を追加し、runtime config改竄では起動できないことを敵対テストで固定（30件pass）。
- 統治正本 `GOVERNANCE_PATHS` は installer・plugin両実装が同一列挙を持ち、相互一致をテスト固定（`test_governance_path_lists_match_between_installer_and_plugin`、`integrations/hermes-pda-approvals/tests/test_plugin_api.py`）。
- terminal遷移claim束縛パッチ（`integrations/hermes-kanban-governance/`）を本番Hermesへ適用済み（084cdbf1、graceful restart、実DBでの拒否・監査・force動作をsmoke検証済み、フルスイート比較でpatched固有failure 0件）。

## 2. exit gate 2: 決定論的finalizationチェック

- スコープ審査ゲートG0を`bounded-operation`/`artifact-change`の決定論分類へ拡張（gold set 17ケース、クラス別budget上限、67件pass）。
- G3(expansion review)を実装: クラス別審査予算、決定論deny/allow、fingerprint束縛・one-use・TTL付きpermit。審査者(LLM judge)はプラグ可能でfail-closed既定。
- S3-M1（artifact-change write scope）のworker配線を実装し、`integrations/hermes-scope-gate/`にテスト固定（`test_artifact_change_scope.py` 136件のtest関数）。
- C6起動監査の契約（schema+validator）と検証者handoff契約スキーマを制定。

## 3. exit gate 3: ADR承認

- `docs/design/self-improvement-governance-adr.md` はStatus: approved（2026-08-22オーナー承認、Open Questions全決定済み）。2026-08-29オーナー批准（`docs/design/auto-integration-gate.md` 16節）によりD1第1項を改訂済み。

## 4. 実運転による実証（t_e2364a83、2026-08-29）

- 本番初のscope_seed活性化（`scope_seed.enabled=true`）でwrite scope強制走行を実施（詳細: `docs/status/m1-supervised-run-2026-08-29.md`）。
- ゲート判定: scope外への書込試行は0件、誤許可はレビューで検出0件。誤拒否（budget系のturn座礁）は実作業を妨げるには至らず、既知課題としてK10（M2、t_9174eb5d）へ引き継いだのみで座礁はしていない。
- 第2ターンで発生した非計上deny（`git-read-unbounded`、読取2ツールskill_view/tool_describeの誤分類）は、カタログ追加によりオーナー承認済みで処置済み（`docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md` 897/940/944行）。
- live資産（本番repo main、他カード、承認ledger、gateway設定）への書込は走行を通じて0件。

## 5. M2への移行

M1 exit gateの3条件は全て充足した。M2「オーケストレーション再設計」（`docs/design/improvement-orchestrator.md`、実装カード t_5dbb92ca）の停止ゲートを開放する。実運転で確認された残課題（tool budget座礁時の完了合図欠落、無統制の自動再試行、独立検証者ステージ未配線、todoの自動ready昇格）はK10（M2, t_9174eb5d）への入力として引き継ぐ。
