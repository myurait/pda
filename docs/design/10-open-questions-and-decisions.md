# 10. 決定事項と未決事項

- 最終更新: 2026-07-20
- 上位文書: [README.md](README.md)

## 1. 主要決定の一覧（Decision Register）

比較検討の詳細・棄却案・採用条件の変化はリンク先を正本とする。

| ID | 決定 | 正本 | 見直し条件（要約） |
|----|------|------|--------------------|
| D-1 | canonical storeはSQLite/WAL（domain別ファイル）＋content-addressed blob store | [ADR-0001](../adr/0001-canonical-store-sqlite-append-only-ledger.md) | 複数ホスト書込・DB約50GB超・書込競合の常態化・レプリケーション必要時 |
| D-2 | data modelはledger-first（追記event＋同一Tx運用テーブル＋再生成projection） | [ADR-0001](../adr/0001-canonical-store-sqlite-append-only-ledger.md) | replay検証の維持コストが便益を超えたとき |
| D-3 | retrievalはFTS5 trigram baseline→gold set不足の実証時のみvector/graph追加 | [04 §5](04-context-spine-and-data-contracts.md) | GS-RETRIEVAL未達（特に日本語2字語） |
| D-4 | runtime接続はMCP stdio主経路＋SSH stdio（ホスト間）。HTTP保留・MQ不採用 | [ADR-0003](../adr/0003-runtime-neutral-contracts-over-mcp-stdio.md) | 複数リモートclient常時接続・複数ホスト分散実行の必要時 |
| D-5 | near-termのorchestratorはHermes継続。ただしtask/run/pack契約はPDA側に置き、M6で交換実証 | [ADR-0003](../adr/0003-runtime-neutral-contracts-over-mcp-stdio.md)、[05](05-orchestration-and-runtime-contracts.md) | Hermes保守停止・破壊的変更、または契約実装をHermesが阻害する場合（前倒し） |
| D-6 | サービス管理single-owner（ネイティブ=systemd user unit、コンテナ=Docker restart policy）。docker group追加せず、digest固定 | [ADR-0006](../adr/0006-service-management-single-owner.md) | ホスト再構築時（rootless再評価）、コンテナ数増加 |
| D-7 | security domain 4区分。workはDB非作成のdefault deny、解禁時も別DB・別鍵・別backup | [ADR-0004](../adr/0004-security-domain-separation.md) | OQ-4の解決（書面許可＋分離構成） |
| D-8 | claimはmanual/deterministic first。LLM抽出はM4からproposer限定 | [04 §4.2](04-context-spine-and-data-contracts.md)、[06 §7](06-security-privacy-and-governance.md) | claim審査の運用負荷過大（自動化範囲を承認付きで拡大） |
| D-9 | memory providerはすべて再生成可能なprojection。正本にしない | [ADR-0002](../adr/0002-memory-providers-are-rebuildable-projections.md) | なし（INV-1に直結。緩和にはADR改訂＋本人承認） |
| D-10 | 自己改変はproposal→sandbox→固定eval→人間承認→canary→rollbackの経路のみ。protected assetsは恒久対象外 | [ADR-0005](../adr/0005-self-modification-authority.md) | なし（INV-13に直結） |

## 2. 仮説文書（HYP）の主要提案に対する採否

| 提案 | 採否 | 修正点 |
|------|------|--------|
| 「Phase 3.5」現在地判定 | 採用 | 実行管理はM0〜M6へ再編（[09 §1](09-transition-roadmap.md)） |
| append-only Event Ledger | 採用（修正付き） | redaction手続きの契約化（INV-3とINV-12の両立、[04 §7](04-context-spine-and-data-contracts.md)）、blob分離、純イベントソーシングでなくledger-first |
| SQLite/WAL/FTS5 trigram | 採用（制約明示） | 日本語2字語の限界と緩和策・見直し条件を明記（[04 §5.1](04-context-spine-and-data-contracts.md)） |
| claim/evidence分離 | 採用 | 遷移authorityからLLMを恒久除外、conflict/stale伝播を契約化 |
| Context Pack | 採用（強化） | builderの決定性を契約化（LLM要約は隔離セクションへ）、data_label必須、unknowns追加 |
| 共通stdio MCP | 採用 | 書込系toolの範囲を限定し導入時期を分離（[05 §5](05-orchestration-and-runtime-contracts.md)） |
| memory provider=projection | 採用 | 同期方向・selectの契約化（[04 §9](04-context-spine-and-data-contracts.md)） |
| metric数値（Recall等） | 修正採用 | 確定値→初期仮説へ格下げ（[08 §4](08-evaluation-and-phase-gates.md)） |
| Task 1での史料（REC）修正 | 棄却 | 史料は上書きせず、矛盾一覧（[02 §3](02-current-state-and-gaps.md)）で差分管理 |
| E2E相手=Claude Code（無限定） | 修正採用 | 会社アカウントruntimeを除外し、ミニPC個人Claude Codeに限定（OQ-5） |
| task/run/gate/approval契約の欠落 | 補完 | [04](04-context-spine-and-data-contracts.md)・[05](05-orchestration-and-runtime-contracts.md) で新規設計 |

## 3. Open Questions（ユーザー判断が必要な事項）

各項目は「決定点」までに未決の場合、記載のsafe defaultで進める（作業を止めない。brief作業制約7）。

### OQ-1: バックアップ先の選定 【blocking: M0】

- 選択肢: (a) 外付けSSD/HDDのみ (b) クラウド（B2/S3等）のみ (c) **両方（推奨）**
- 推奨: (c)。restic 2系統（ローカル即時復元＋オフサイト災害耐性）。クラウドは暗号化済みのため
  機密面の追加リスクは鍵管理に集約される
- 影響: RPO/RTOの実効値、月額コスト（数百円〜規模）、T-11（backup漏洩）の面
- 決定点: M0 backupタスク着手時。safe default: まずローカル外付けで開始し、クラウドを追補

### OQ-2: Tailscale導入 【blocking: 外出先要件のみ】

- 選択肢: (a) **導入（推奨）** (b) LAN限定継続＋UFW (c) 他VPN（WireGuard手動等）
- 推奨: (a)。ポート開放なし方針と整合し、ACLで端末・ポート単位に絞れる（確認 2026-07-20）。
  外部アカウント依存が増える点は、失っても到達性のみの影響（データ非依存）で許容
- 決定点: M0ネットワークタスク時。safe default: (b)で進め、外出先要件が発生したら(a)

### OQ-3: 個人データのLLM egress許容範囲 【blocking: M2】

- 事実: 現構成ではHermes中核推論（Codex）を通じ、Hermes上の全会話・tool結果がOpenAIへ送信される。
  Claude委任分はAnthropicへ送信される
- 決めること: (1) この現状を追認するか (2) 送信不可のデータクラス（例: 健康・金融・特定人物）を
  定義するか (3) 各ベンダーの学習利用オプトアウト設定の確認
- 推奨: 現状追認＋除外クラスの少数定義＋オプトアウト確認。除外クラスはconnector除外規則と
  pack組成フィルタで実装
- 決定点: M2 entry（会話export・ブラウザ等の高機微sourceの取込前）。safe default: 新規取込は
  低機微sourceに限定し続ける

### OQ-4: 会社データの取り込みを目指すか 【non-blocking（恒久default deny可）】

- 選択肢: (a) 目指さない（PDAは私的活動専用） (b) 目指す（会社の書面許可・別DB・別鍵・別backup・
  場合により別ホストをentry conditionに）
- 推奨: 当面(a)。(b)は費用対効果と規約リスクの評価をOQ-4再訪時に実施
- 決定点: なし（default denyのまま無期限保留可能）

### OQ-5: 会社アカウントruntimeへの個人context提供 【blocking: M1のE2E範囲】

- 事実: 開発PCのClaude Code（会社Team plan）からHermes MCPへ接続済み（[02 §3 C-9](02-current-state-and-gaps.md)）。
  この経路で個人domainのpackを提供すると、個人データが会社契約のAnthropic組織へ送信される
- 選択肢: (a) **deny（推奨）**: pda-mcpは個人アカウントruntimeのみに提供。既存のHermes MCP接続も
  用途を再確認 (b) public domainのみ許可 (c) 全面許可
- 決定点: M1のpda-mcp登録時。safe default: (a)

### OQ-6: retention・削除の既定値 【blocking: M2】

- 決めること: source別の本文保持期間（例: ブラウザ履歴1年、会話原文無期限等）、
  backup世代数（実効削除期限を規定する。[04 §7](04-context-spine-and-data-contracts.md)）、
  redaction定期レビューの頻度
- 推奨初期値: 会話・決定系は無期限、ブラウザ/Web本文は2年、backup世代90日、レビュー四半期
- 決定点: M2 entry。safe default: 推奨初期値

### OQ-7: claim承認のUX 【non-blocking】

- 選択肢: (a) CLI批評（`pda claims review`、週次バッチ）（M1既定） (b) Open WebUI統合 (c) messaging通知
- 決定点: M1運用開始後の使用感で。safe default: (a)

### OQ-8: ディスク暗号化（LUKS） 【non-blocking】

- 事実: 現ミニPCのFDE有無は記録がなく、おそらく未使用（GAP-9）
- 推奨: 次回ホスト再構築時にLUKS採用。現行は backup暗号化＋物理管理で緩和
- 決定点: ホスト再構築イベント時

### OQ-9: 通知チャネル（Telegram等） 【non-blocking、M2で有用】

- 用途: ingest失敗・backup失敗・承認要求のプッシュ通知（Hermes gatewayの既存機能を利用）
- 決定点: M2のguard付き自動取込開始時。safe default: 通知なし（doctor手動確認）

### OQ-10: ローカル推論fallbackとハードウェア投資 【non-blocking】

- 事実: WAN断・vendor停止時にクラウド推論が全停止する（[07 §7](07-deployment-operations-and-recovery.md)）。
  現16GB RAM機ではローカルLLMは小型に限られる
- 選択肢: (a) 受容（縮退運転のみ） (b) 緊急要約・検索補助用の小型ローカルモデル (c) 別ホスト増設
- 決定点: [07 §8.2](07-deployment-operations-and-recovery.md) の分離閾値に達したとき。safe default: (a)

### OQ-11: 過去履歴（ChatGPT/Claude export）の取込範囲 【blocking: M2該当connector】

- 決めること: 全量か直近か、機微会話の除外方法（手動選別 or 除外パターン）
- 推奨: 小標本（数十会話）でCONN-SUITEとGS回帰を通してから拡大
- 決定点: M2該当connector着手時。safe default: 小標本

### OQ-12: Hermes中核モデルの再検討トリガ 【non-blocking】

- 現状: Codex据え置き（REC§6.3の決定を踏襲）。切替はHermes側 `hermes model` で可能
- 再検討トリガ案: OpenAI障害の頻発、Codex OAuth条件の変化、Claude API課金の許容決定、
  routing評価（M6）でHermes中核の品質劣位が計測されたとき
- 決定点: トリガ発生時

## 4. blocking整理（直近で本人回答が必要な順）

1. **OQ-1**（backup先）— M0の途中で必要
2. **OQ-2**（Tailscale）— M0の途中で必要（safe defaultで先送り可）
3. **OQ-5**（会社アカウントruntimeへの提供可否）— M1のMCP登録時
4. **OQ-3**（egress許容）・**OQ-6**（retention）・**OQ-11**（過去履歴範囲）— M2 entry
