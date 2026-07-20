# ADR-0005: 自己改変の受入権限は人間に固定し、protected assetsを改変対象から恒久除外する

- Status: Accepted
- Date: 2026-07-20
- 対応Decision: D-10
- 関連: [design/06 §7-8](../design/06-security-privacy-and-governance.md)、INV-8、INV-10、INV-13

## Context

PDAの最終構想は自己改善（Phase 9）とコアを含む自己改変（Phase 11）に及ぶ。
このとき「改善案を生成する能力」と「変更を受け入れる権限」を分離しなければ、
自己正当化によって評価条件・承認境界・監査・復元手段が無効化される
（PLAN §5.5、brief命題7、脅威T-10）。

## Decision

1. **権限の四分離**: proposer（提案）／executor（実行）／evaluator（評価）／approver（承認）を
   分離する。approverは **本人のみ** であり、この権限をPDA・runtime・自動ruleへ委譲しない
2. **自己改変の唯一経路**: proposal（根拠citation必須）→ sandbox適用（本番資格情報なし）→
   固定gold set＋回帰テスト → GateVerdict → 人間承認 → canary（git管理・旧版保持）→
   監視 → 採用確定 or rollback＋quarantine（[design/06 §8](../design/06-security-privacy-and-governance.md) 図6）
3. **protected assets（恒久的に自己改変対象外）**: gate policy、data/egress/approval policy、
   gold set・評価baseline、approval資格情報、audit chain、backup repoと鍵、
   本設計文書・ADR・INV定義。これらの変更は人間の直接操作のみ
4. **評価の独立**: evaluatorは実行runtimeと別のmodel/プロセスを用い、自己採点を禁止する。
   認知gateは決定論的denyを覆せない
5. **security差分レビュー**: prompt/skill/connector/gate構成を変えるproposalは、gold set metricの
   合格だけでは承認しない。新規egress先・network能力・tool権限・承認要否の変化を列挙する
   security差分チェックリストを人間レビューの必須項目とする（gold set外の悪性挙動の密輸を防ぐ。
   [design/06 §8](../design/06-security-privacy-and-governance.md) 規約7）
6. **無承認で許す自動操作**は可逆的operationalジョブ（projection再構築・索引再生成・
   キャッシュ無効化）に限定し、この許可リスト自体の拡大は人間承認による
7. **強制手段の段階**: near-term=規約＋監査（OS強制なし。protected assets保護もこの間は
   実効性が限定的で、T-PROTECTED-ASSETSはtransition以降でのみ意味を持つ）、
   transition=OS権限（`pda`/`pda-admin` ユーザー分離・socket仲介・ファイル所有権）、
   M5=sandbox実行。移行計画は [design/09](../design/09-transition-roadmap.md)

## Alternatives considered

### 高信頼evaluator（LLM多数決等）による自動承認 — 棄却

- 「AIが評価するから安全」はbrief品質基準で明示的に禁止。evaluator自体が改変・汚染対象に
  なり得るため、最終権限は決定論的統制と人間に置く

### 全変更を人間手動（自己改善機構なし） — 棄却

- Phase 9-11の要求（R-14, R-17）を放棄することになる。統制付きpipelineであれば
  提案生成・検証の自動化は安全に価値を出せる

### protected assetsも「多重承認があれば」改変可 — 棄却

- 承認フロー自体がPDA経由である限り自己正当化リスクが残る。人間の直接操作（PDAの
  書込経路の外）に固定する方が検証可能性が高い

## Consequences

- (+) 自己改善の失敗が本番・統治条件へ波及しない（sandbox・canary・rollback・quarantine）
- (+) 「PDAが自身の監査条件を書き換える」攻撃・事故（T-10）が構造的に成立しない
- (−) 改善のスループットは人間承認律速になる（設計上の意図。承認UXはOQ-7で改善）
- (−) protected assetsの人間管理は運用規律を要する（編集手順のrunbook化で補う）

## Revisit conditions

- approver権限の委譲・protected assetsの縮小: 恒久的に不可（INV-13）。
  本ADRのSuperseded化には本人の明示承認と新ADRを要する
- 自動許可リストの拡大: M5以降、対象操作の可逆性・失敗実績を証跡としてpolicy claim改訂で個別判断
