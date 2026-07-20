# ADR-0002: memory providerはすべて再生成可能なprojectionであり正本にしない

- Status: Accepted
- Date: 2026-07-20
- 対応Decision: D-9
- 関連: [design/04 §9](../design/04-context-spine-and-data-contracts.md)、INV-1、INV-11

## Context

Hermesはbuilt-in memoryを持ち、外部memory provider（Holographic、Hindsight、OpenViking、
Supermemory等が仮説文書で言及）も接続できる。Open WebUIも独自のメモリ・会話ストアを持つ。
これらは便利だが、(1) 一度に有効化できるproviderの制約、(2) スキーマ・挙動がprovider更新に
追随する、(3) export・削除・再構築の保証がまちまち、という性質があり、PDAの正本に据えると
INV-1（runtime交換可能性）とINV-11（export可能性）を破る。

## Decision

1. すべてのmemory provider（Hermes built-in・外部provider・UI内蔵メモリ）は
   **Context Spineから再生成可能なprojection（cache）** として扱う
2. 同期は **Spine → provider の一方向** のみ。同期対象は `accepted` claimのうち
   provider向けに明示selectされた部分集合に限る
3. providerからPDAへの逆流入は、明示的なimport操作（`proposed` claimとして入り
   承認境界を通る）以外に存在しない
4. Hermes built-in memory（`MEMORY.md`/`USER.md`）の許容内容は「pda-mcpの存在と使い方、
   安定した少数の運用ヒント」に限定する。判断基準・プロジェクト状態・決定を書かない
5. provider無効化・交換後もcanonical stateが無損失であることをテスト（T-EXPORT-REBUILD）で
   継続検証する

## Alternatives considered

### Hermes built-in memoryを正本にする — 棄却

- Hermes更新にスキーマが追随し、Hermes交換（Phase 10/M6）で継続性が失われる。INV-1違反

### 外部専用provider（KG系/クラウド系）を正本にする — 棄却

- 交換・再生成・削除の保証がproduct依存になり、新しいロックインが生まれる（仮説文書リスク欄と同判断）。
  クラウドproviderは加えてegress・削除・export条件が未確認（INV-9/11）

### provider双方向同期 — 棄却

- providerの自動書き戻しは、承認境界を迂回するmemory poisoning経路（T-2）になる。
  一方向＋明示import以外を許さない

## Consequences

- (+) provider選定・交換・A/B比較が安全な実験になる（正本無風）
- (+) memory poisoningの侵入面が claim承認境界の1点に集約される
- (−) providerの「自動学習」的な便益は制限される（acceptされた知識しか流れない）
- (−) 同期selectの管理という運用作業が増える（M2以降、少数claimから開始して抑制）

## Revisit conditions

- なし（INV-1/11に直結するため恒久原則）。緩和には本ADRのSuperseded化と本人の明示承認を要する。
  providerのA/B評価はGS-RETRIEVAL/GS-CONTINUITYのbaseline超過を条件に個別判断する
