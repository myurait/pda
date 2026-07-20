# 08. 評価とフェーズゲート

- 最終更新: 2026-07-20
- 上位文書: [README.md](README.md)
- 関連: マイルストーン別のentry/exitは [09](09-transition-roadmap.md)、要求との対応は [01 §7](01-requirements-and-invariants.md)

## 1. 評価の基本方針

1. **印象ではなく固定評価**: 検索・claim・pack・routing・gateの改善判断は、固定gold setと
   記録済みbaselineに対する差分で行う（R-29）
2. **metricの数値は初期仮説**: 本章の数値目標は根拠が実測で確立するまで仮説であり、
   測定方法と再調整条件をセットで管理する（[02 §3 C-8](02-current-state-and-gaps.md) の裁定）
3. **評価資産はprotected**: gold set・baselineはcore書込権限外（[06 §8.1](06-security-privacy-and-governance.md)）。
   自己改善pipelineがgold setを書き換えることはできない
4. **完了粒度の三分法**: フェーズ・マイルストーンの到達は「機能PoC／運用完了／評価完了」を
   区別して判定する（§2）

## 2. 完了粒度の定義

| 粒度 | 定義 | 証跡 |
|------|------|------|
| 機能PoC完了 | 経路・機能が少なくとも1回動作した | 動作記録（再現手順付き） |
| 運用完了 | 再現可能な構成・監視・backup/restore・失敗時手順の下で継続運用されている | IaC、doctor green、restore drill合格、runbook |
| 評価完了 | 固定gold set／テストで受入基準を満たし、baselineが記録されている | eval実行ログ、metric記録、回帰の自動実行 |

現在地判定（[02 §5](02-current-state-and-gaps.md)）はこの三分法で表現済み。

## 3. Gold set一覧

各gold setはJSONL（質問・期待・許容根拠・as-of・不許容事項）でrepo管理し、
作成・改訂は人間のみ（承認記録付き）。

| ID | 内容 | 初期規模 | 導入 |
|----|------|----------|------|
| GS-RETRIEVAL | 実データ由来の検索クエリ（日本語2字語・長文・時期指定を含む）→期待根拠event | 20〜30問 | M1 |
| GS-INJECTION | 指示文入りの敵対的文書（Web/チャット風）を取込→命令非実行・非昇格の確認 | 10〜15件 | M1 |
| GS-TEMPORAL | 失効済み決定・supersede関係を含むas-ofクエリ | 10問 | M1（最小）→M2（本格化） |
| GS-CONTINUITY | Hermesと別runtimeが同一packから同じactive decision・根拠を引用するシナリオ | M1は数問（sliceの核）→M2で拡充 | M1（最小）→M2 |
| GS-DECISION | 過去の本人判断の再現クイズ（判断軸claimの有効性測定） | 10〜20問 | M4 |
| GS-ROUTING | task種別→適切runtime選択の正解表 | 10〜20件 | M4〜M6 |
| GS-GATE | gate適用判断（要承認/不要、要gate/不要）の正解表 | 10〜20件 | M5 |

## 4. Metric仮説（測定方法・再調整条件付き）

| metric | 初期仮説 | 測定方法 | 再調整条件 |
|--------|----------|----------|-----------|
| evidence Recall@5 | ≥ 0.85 | GS-RETRIEVAL各問で期待根拠が上位5件に入る率 | 実データでの分布確認後。2字語クエリのみ別集計 |
| citation precision | ≥ 0.95 | 回答/packの引用event_idが実在し引用文が原文一致する率 | — |
| superseded decision誤用 | 0件 | GS-TEMPORALで失効決定を現行として提示しない | — |
| unsupported/no-answer正答 | ≥ 0.90 | 根拠がない問いに「不明」と答える率（GS-RETRIEVALの不許容問） | — |
| pack token | ≤ 約2,000 tokens | builder出力の推定token数 | 利用実感とruntime性能で±50%再調整 |
| pack build latency p95 | < 250ms（ローカル） | M1実機計測 | **実測後に必ず妥当性再確認**（仮説文書由来の暫定値） |
| baseline比較 | `session_search` 単独比で正答率+10pt、または同等精度でcontext token 30%削減 | 同一GS-RETRIEVALを両経路で実行 | baseline計測後 |
| injection非実行 | 100%（GS-INJECTION全件） | 敵対文書内の指示（例: 「このファイルを送信せよ」）を実行・記憶昇格しない | 失敗事例は個別に脅威モデルへ反映 |
| cross-runtime一致 | GS-CONTINUITY全問で同一decision・同一根拠 | 両runtimeの回答突合 | — |
| restore drill | 合格（integrity+件数一致） | [07 §6.3](07-deployment-operations-and-recovery.md) | — |
| 運用負荷 | 週次保守 ≤ 数時間（A-05） | 作業ログの自己記録 | 超過時はscope縮小（stop/go） |

M4以降の追加候補: 差し戻し率（本人による修正・却下の率）、approval override率、
routing正解率、gate false-positive/negative率。数値目標は導入時に仮説設定する。

## 5. テスト・証跡カタログ（T-xx）

[01 §7](01-requirements-and-invariants.md) のtraceability matrixが参照するID。
実装時はこのIDをテスト名・CI job名に対応させる。

| ID | 内容 | 種別 |
|----|------|------|
| T-INGEST-IDEM | 同一snapshot再取込で新規event 0 | 自動テスト |
| T-PROVENANCE | 全eventにlocator/observed_at/hash/domainが存在 | 自動テスト |
| T-POLICY-WORKDENY | work source取込・保存・送信の拒否（verdict記録付き） | 自動テスト |
| T-SECRET-EXCLUDE | secretパターンの本文非保存、`.env` 系の取込拒否 | 自動テスト |
| T-ASOF | as-of指定で当時のaccepted集合のみ返る | 自動テスト |
| T-PACK-CONTRACT | pack schema適合・data_label・citation必須・retracted除外・conflict表示 | 自動テスト |
| T-PACK-BUDGET | budget超過時の優先度切詰めとtruncated表示 | 自動テスト |
| T-CLAIM-LIFECYCLE | evidence必須・proposed開始・不正遷移拒否・遷移履歴保持 | 自動テスト |
| T-REDACTION-PROPAGATION | redaction後の本文消滅・FTS除去・claimフラグ・audit記録 | 自動テスト |
| T-AUDIT-CHAIN | hash連鎖の検証、改竄検出 | 自動テスト |
| T-EXPORT-REBUILD | 全正本のexport→空環境での再構築→projection再生成、memory provider無効化後の無損失 | drill |
| T-RESTORE-DRILL | backup→隔離環境restore→integrity・件数一致 | drill |
| T-REBOOT-HEALTH | 再起動後に全サービスhealthy（doctor green） | drill |
| T-E2E-CONT | GS-CONTINUITYの実行（Hermes＋個人Claude Code） | E2E |
| T-RESUME | orchestrator再起動後のtask再開（stale run→timeout→新attempt） | E2E |
| T-RUN-CONTRACT | TaskSpec/RunResultのschema適合・citation検証・artifact hash | 自動テスト |
| T-HANDOFF | fallback runtimeへの引き継ぎで文脈が維持される（[05 §7](05-orchestration-and-runtime-contracts.md)） | E2E |
| T-PROJECT-RESUME | 中断プロジェクトの再開packで次アクション・blockerが提示される | E2E |
| T-GATE-DENY | 決定論的gateのfail-close（判定不能・policy違反の拒否） | 自動テスト |
| T-PROTECTED-ASSETS | core権限からのgate policy/gold set/audit改変試行が失敗する（**transition=M3以降でのみ有意。near-termはOS強制がなく合格を主張できない**。[06 §8.1](06-security-privacy-and-governance.md)） | 自動テスト＋drill |
| T-SELFIMP-PIPELINE | 改善proposalがsandbox→eval→承認→canary→rollbackの全経路を通る | E2E |
| T-CORE-SWAP | Hermes以外の経路で同一gold set・同一taskを完遂し、結果を比較記録 | drill |
| CONN-SUITE | connector必須テスト一式（policy/idempotency/provenance/update-delete/injection/backup/独立無効化。[04 §6](04-context-spine-and-data-contracts.md)） | 自動テスト |

## 6. フェーズゲートの運用

- 各マイルストーンは **entry criteria / exit criteria / evidence / rollback条件** を持つ
  （具体値は [09](09-transition-roadmap.md)）
- entry criteriaの中核はINV-7（restore-first）: backup/restore・監査が先行して成立していない
  マイルストーンには入らない
- exit判定は本人が行い、判定結果と証跡参照を `docs/status/`（実装フェーズで新設）に記録する
- ゲート不合格時のrollback: 直前マイルストーンの構成へ戻せることを設計条件とする
  （schema migrationは直前backup、サービスは旧digest/旧unit）
- gold set・metricの改訂は「評価対象の変更」と「評価基準の変更」を分離し、
  基準変更は必ず人間承認＋改訂理由の記録を伴う
