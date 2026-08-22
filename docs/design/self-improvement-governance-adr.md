# ADR: 自律改善の統治 (self-improvement governance)

- Status: draft-for-owner-review（オーナーのレビュー承認まで効力を持たない。承認により goal M1 の統治正本となる）
- 日付: 2026-08-22
- 位置付け: `docs/roadmap/autonomous-improvement-goal.md` M1(a) の成果物。全体設計発注書（`.hermes/prompts/claude-fable-full-system-design.md:145,168,178`）が要求する self-improvement governance の ADR。
- 根拠となる規範: `pda_charter.md`（特に第五条・第六条）、`personal_delegate_agent_plan.md:168-183`（提案と受入判断の分離、ゲートをコアの上位に置く）、goal文書6節の不変条件 C1-C9。
- 根拠となる実証: 2026-08-22 の M0 で確定した2つの事実。(1) プロンプト規律は強制力ではない（workerが保護環境変数を自己解除した）。(2) 意味的レビューは行動回帰を捕捉できない（b11e01c は digest 束縛のオーナー承認を通過して本番不具合を起こした）。

---

## D1. 自動化範囲とオーナー固定範囲の二分

改善サイクルの各工程を「自動化してよいもの」と「オーナーにのみ許されるもの」に二分し、この境界の変更自体を本 ADR の改訂（＝オーナー承認）に固定する。

自動化してよい工程:

- 依頼・欠陥・違反の捕捉と起票（未割当 triage、出典・idempotency key 必須）
- カードの具体化と ready 化（停止・判断ゲートがない場合のみ）
- 割当・隔離worktreeでの実装・focused test・local commit
- 独立検証と review handoff の作成
- 反映後の観測、異常時の承認済みrollback契約の実行
- ポストモーテムの自動起票、worktree GC（`docs/operations/worktree-lifecycle.md` の範囲内）、stale claim の回収

オーナーにのみ許される判断（自動化禁止・self-improvement の対象外）:

- 最終反映の承認（digest 束縛。main統合・push・デプロイ・restart・外部送信の解錠）
- 統治の変更: 本 ADR、ゲート policy、承認境界、不変条件 C1-C9、憲章
- 自律改善の再有効化、並列度・資源上限の変更
- 秘密・認証・課金・不可逆削除・外部公開範囲に触れる一切
- 優先順位の最終決定と、停止指示・停止解除

## D2. 二層検証の契約（決定論的ゲート層 × AI検証者層）

goal文書4節の確定（独立検証者は「AI/決定論混成」）を、層ごとの契約として定義する。どちらか一方を選ぶ議論はしない。

強制層（決定論的ゲート）:

- 性質: fail-closed、全カード必須、worker の書込権限外で動作、出力は監査イベント。
- 構成: スコープ審査（`docs/design/task-scope-admission-gate.md` の S2/S3 を worker 実行へ適用）、Git 実地検証（既存の digest/worktree/branch/diff 一致）、不変条件チェック（D4 の機械検査項目）、検証コマンド実在確認（handoff が主張するテスト実行をログ・exit code で照合）、terminal 遷移の claim 束縛（M0 で Hermes 本体へ実装済み・本番適用済み）。
- 根拠: 実証(1)(2)。プロンプトにも意味的レビューにも代替させない。

判断層（AI検証者）:

- 性質: 実装workerと別主体のAIが、受入条件の意味的充足・回帰リスク・スコープ妥当性を判定する。
- 消費契約（C6 充足）: 検証者の出力は review handoff の必須添付であり、承認画面に表示される。参照されない検証レポートを生成するための起動はしない。
- 限界の明文化: AI検証者の「合格」は強制層の通過にも digest 承認にも代替しない。検証者は lifecycle 変更権限を持たない（terminal claim guard により機械的に保証される）。
- 実装プリミティブの選定（Hermes の reviewer 引数 / `claim_review_task` / swarm verifier 段のいずれを使うか）は M2 のオーケストレーター設計で行い、本 ADR は契約のみを固定する。

## D3. ゲートの所有権と配置

- ゲート policy・不変条件定義・敵対テストは Git 正本（本リポジトリ）で管理し、変更はオーナー承認のコミットのみとする。worker の finalization contract に統治ファイルへの変更が含まれる場合、強制層は無条件で拒否する。
- 承認 ledger（`pda_owner_approvals`）は現在 Kanban DB 内にあり、DB に書ける主体からは物理的に隔離されていない。M0 の terminal claim guard と installer の検証は関数・契約レベルの保護であり、「worker の書込権限外への物理配置」（root 所有 broker 等、identity 計画の control-owned binding と同系）は未達である。これは本 ADR の残余であり、物理分離の時期と方式は Open Question 4 とする。
- 強制層のコードは Hermes 本体への管理パッチ（`integrations/hermes-kanban-governance/`）と本リポジトリの決定論的ツールに置き、worker のスキル・プロンプトには置かない。

## D4. 不変条件 C1-C9 の検査化分類

「思想準拠の機械検査」を過大に謳わない。identity contract / clause ID（`.hermes/plans/2026-08-17` 設計）は未実装であり、M1 で検査化するのは部分集合である。分類は次のとおり。

機械検査が実装済み（M0 時点）:

- C5（二段階実行契約）: digest 束縛承認、Git 実地再検証、activation nonce（既存 installer / plugin）。
- C7（試験の本番非接触）: repo 直下 conftest の ambient 除去と本番 DB fail-closed ガード、installer の ambient 無効化、回帰テスト。
- C8 の一部（停止の尊重）: 停止接頭辞カードの router 除外（既存）、policy 停止中の activation 拒否（M0）。
- terminal 遷移の所有権（C2/C4 の実行時の一角）: live foreign claim guard（M0、本番適用済み）。

M1-M2 で検査化する:

- C3（ゲート・ledger の権限外配置）: M1 では統治ファイル変更の拒否ゲートと敵対テスト、物理分離は Open Question 4。
- C6（クレジット規律）: AI 起動と出力消費先の対応を監査イベント化し、消費先のない定期起動を検出する。
- C9（通知契約）: 表示側は実装・実証済み（Open WebUI v2.1.0-local.18）。cycle 側のカード専用スレッド通知は M2（t_c5638264）で実装し、終端通知の欠落を検査する。
- C8 の残り（再有効化の禁止）: 有効化経路が policy コミット＋承認以外に存在しないことの敵対テスト。

構造でのみ担保する（機械検査で置換できない）:

- C1（憲章至上・改定権限）: authority map と本 ADR の効力規定そのもの。検査は「統治ファイルの無承認変更の拒否」という代理指標に限られる。
- C2（提案能力と受入判断の分離）: 役割分割（worker / 検証者 / ゲート / オーナー）という構造。実行時の代理指標は terminal guard と承認境界。

監査でのみ担保する:

- C4（自己正当化による無効化の禁止）: 統治変更の全履歴が Git とカード監査イベントに残ること。事前検査は C3 の拒否ゲートが代理する。

## D5. 敵対的迂回テストの要件

統治の変更を伴うリリースは、次の迂回試行がすべて遮断されることを回帰スイートで証明してから review に載せる。

- 保護環境変数（delegate child 文脈等）の自己解除後の terminal 遷移試行（M0 で実装済み）
- 本番 Kanban DB パスの ambient 注入（M0 で実装済み）
- worker による統治ファイル（ゲート policy・ADR・承認 ledger スキーマ）への変更を含む finalization contract
- スコープ外パスへの書込（S2/S3 適用後）
- 検証者・review 専用主体による lifecycle 変更試行

新しい迂回が実運用で観測された場合、ポストモーテム起票と同時にこのスイートへ再現テストを追加する（学習ループ、M3）。

## Open Questions（オーナー判断事項）

1. 全体設計発注書（`.hermes/prompts/claude-fable-full-system-design.md`）との関係。本再設計を全体設計の一部として進めるか、独立トラックとするか。（goal文書 Open Question 2 の再掲。本 ADR レビューが判断の場）
2. 多層認知ゲート（構想フェーズ8）との順序。本 ADR は「自己改善に必要な最小ゲート群」の先行実装であり、フェーズ8全体の代替ではない。この先行を許容するか。（goal文書 Open Question 3 の再掲）
3. AI検証者の深度を risk_class（`pda-autonomous-improvement` SKILL.md の local-reversible / service-restart / external-visible / security-sensitive）に連動させるか。全カード一律の AI 検証は C6（クレジット規律）と緊張するため、例えば local-reversible は強制層のみ、external-visible 以上で AI 検証必須、という傾斜を提案する。
4. 承認 ledger・ゲート policy の worker 書込権限外への物理分離（root 所有 broker 等）の時期。M2 で実施するか、identity 計画（control-owned session binding）と統合して後続にするか。

## 承認後に M1 実装として動くもの

- スコープ審査ゲート S2/S3 の worker 実行への適用（artifact-change クラス）
- D4「M1-M2 で検査化する」のうち M1 分: 統治ファイル変更の拒否ゲート、C6 起動監査の最小実装、再有効化経路の敵対テスト
- D5 敵対テストスイートの整備（M0 実装分の統合を含む）
- 検証者ステージは契約スキーマ（handoff への必須添付形式）の定義まで。ステージの実装・配置は M2 のオーケストレーター再設計で行う
