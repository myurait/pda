# ADR: 自律改善の統治 (self-improvement governance)

- Status: approved（2026-08-22 オーナー承認。Open Questions は全て決定済み — 末尾「確定済みオーナー決定」参照。goal M1 の統治正本）
- 日付: 2026-08-22
- 改訂: 2026-08-29 オーナー批准（`docs/design/auto-integration-gate.md` 16節 決定1-4）により D1 第1項を改訂。同批准が本 ADR 13行目の「境界の変更は本 ADR の改訂に固定する」を満たす承認記録である。
- 改訂: 2026-09-01 オーナー指示により、自然言語のスコープ・リスク判定を決定論分類から分離し、Terra事前評価、実作用監査、二値判断プロセスの形骸化監視をD2/D6へ追加した。同日、実装正本を`integrations/hermes-scope-gate/`へ置く統治変更とmain・稼働環境への反映が承認された。
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

- 最終反映の承認（digest 束縛）。ただし main統合・push は、`docs/design/auto-integration-gate.md` のゲート群 G1-G8（同5節）を全通過した変更に限り自動執行を許す（同1節 C5'。2026-08-29 オーナー批准）。デプロイ・restart は同12節 Phase C 以降かつ非干渉検査 G8 通過時のみ自動可。外部送信および以下の固定判断は従来どおりカード単位の承認を要する。
- 統治の変更: 本 ADR、ゲート policy、承認境界、不変条件 C1-C9、憲章
- auto-integration-gate 設計・統合記録・方針（`continuity/autonomous-improvement.json` の `auto_integration` 節）・Tier マニフェストの変更
- 自律改善の再有効化、並列度・資源上限の変更
- 秘密・認証・課金・不可逆削除・外部公開範囲に触れる一切
- 優先順位の最終決定と、停止指示・停止解除

## D2. 意味判断・作用監査・強制境界の分離

自然言語の指示が要求するスコープと作業リスクは、regex、キーワード、task class、決定木その他の決定論分類では定義しない。現在の認証済みオーナー指示を最上位とし、`docs/design/task-scope-admission-gate.md` 0節の三段階を適用する。

スコープ制御の判断層:

- 主作業前: 実行主体が現在指示からScopeFrameと計画を作り、別sessionのTerra-class modelが過不足、リスク、`additional_assurance_required`、追加監査事項を評価する。実行主体はフラグを下げたり迂回したりできない。
- 作業後: 実行主体自身が全runの実作用と未達成果をScopeFrameへ照合し、`final_scope_conformant`と詳細状態を出す。計画どおりだったという自己申告だけでは足りない。
- 追加保証: Terraが必要とした場合だけ、作業前に予約した別主体が最終作用監査を行う。経路が無ければ作業前にblockする。存在しない検証者待ちを進捗にしない。

強制層（決定論的ゲート）:

- 性質: fail-closed、workerの書込権限外、出力は監査event。
- 担当: 指示元/provenance、event/schema、対象containment、Gitのdigest/worktree/branch/diff一致、不変条件、検証実行の証拠、承認、予算、stale-plan、terminal遷移のclaim束縛、評価済み計画と観測作用の機械照合。
- 非担当: 自然言語の意味、必要成果、リスク、追加保証要否を決定論的に推論しない。安全境界は作用を止められるが、現在指示の意味を別taskへ書き換えない。

自己改善成果の独立実装検証:

- 実装workerとは別主体のAIが、受入条件の意味的充足、回帰、成果差分を検証し、review handoffへ添付する従来契約は**全ての自己改善変更で維持する**（2026-08-22 オーナー決定）。
- これは成果物の独立検証であり、上記のTerra事前評価、実行主体の最終作用監査、条件付きの追加スコープ監査とは別契約である。一つの出力で複数の主体分離を満たしたことにしない。
- AI検証者の合格は強制層やdigest承認に代替せず、検証者はlifecycle変更権限を持たない。

各AI出力は実際の計画修正、監査gate、review handoffのいずれかに消費されるためC6に適合する。実装プリミティブとstage配置はM2で具体化する。

## D3. ゲートの所有権と配置

- ゲート policy・不変条件定義・敵対テスト・形骸化monitor registry/閾値/起票先は Git 正本（本リポジトリ）で管理し、変更はオーナー承認のコミットのみとする。worker の finalization contract に統治ファイルへの変更が含まれる場合、強制層は無条件で拒否する。
- 承認 ledger（`pda_owner_approvals`）は現在 Kanban DB 内にあり、DB に書ける主体からは物理的に隔離されていない。M0 の terminal claim guard と installer の検証は関数・契約レベルの保護であり、「worker の書込権限外への物理配置」（root 所有 broker 等、identity 計画の control-owned binding と同系）は未達である。これは本 ADR の残余であり、物理分離は identity 計画（control-owned session binding）と統合して後続実施とする（確定済みオーナー決定 4）。
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
- C6（クレジット規律）: AI 起動と出力消費先の対応を監査イベント化し、消費先のない起動（参照されない証跡・ログ・オーナーに届かない建前文書の作成・校正）を検出する。検証・レビューのような消費されるAI起動は制限対象ではない（2026-08-22 オーナー明確化）。
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

## D6. 二値判断プロセスの形骸化検知

意味判断を別主体へ分離しても、その主体または最終gateが常に同じbooleanを返すなら機構は形骸化し得る。この失敗は判断内容ではなく施行分布から決定論的に監視する。共通契約の正本は`docs/design/process-degeneration-monitor.md`とする。

- 任意の二値判断processをregistryへ登録でき、個別実装のif分岐にしない。
- 各processの有効な直近72時間について、`N >= 10`かつ`max(true_count, false_count) / N >= 0.95`なら「判定プロセス失敗疑い」をdefault boardのtenant `pda-improvement`へ未割当Triageとして冪等起票する。
- 件数下限は10件とし、`N < 10`では比率を記録しても偏向episodeを開始しない。
- 欠損、不正、未実施、評価不能、同値または相反duplicate、期待母集団取得不能、monitor自身の失敗は、比率から黙って除外せず別のtelemetry failureとして起票する。
- alertは元の判定を反転、補正、再解釈せず、作業・承認・finalizationを自動で許可または拒否しない。
- 最初の登録はTerra事前評価の`additional_assurance_required`と、全終端runの最終監査gateが出す`final_scope_conformant`である。

この監視のregistry、閾値、起票先を通常workerが変更することはD3により禁止する。実装は`integrations/hermes-scope-gate/process_monitor.py`へ置き、event契約、期待母集団、Triage delivery、reconcileを同integrationのfocused testとruntime read-backで検証する。

## 確定済みオーナー決定（2026-08-22）

1. 本再設計は全体設計と一本化せず、**独立トラックで先行**する。
2. 最小ゲート群の先行実装を**許容**する（フェーズ8全体の代替ではないという位置付けのまま）。
3. **AI検証は全ての変更に適用**する（推奨の傾斜案を棄却）。C6 の禁止対象は「参照されない証跡・ログ・オーナーに届かない建前文書のための文書作成・校正」であり、消費される検証はこれに当たらない。
4. 承認 ledger・ゲート policy の物理分離は**後回し**とし、identity 計画（control-owned session binding）と統合して実施する。それまでの改竄検知・拒否は現行の機械検査で担保する。

## 承認後に M1 実装として動くもの

- スコープ審査ゲートの worker 実行への適用（当初は v1 の artifact-change クラスとして計画。2026-09-01 の D2 改訂により、現行は `task-scope-admission-gate.md` 0節の v2 scope 制御が担う）
- D4「M1-M2 で検査化する」のうち M1 分: 統治ファイル変更の拒否ゲート、C6 起動監査の最小実装、再有効化経路の敵対テスト
- D5 敵対テストスイートの整備（M0 実装分の統合を含む）
- 検証者ステージは契約スキーマ（handoff への必須添付形式）の定義まで。ステージの実装・配置は M2 のオーケストレーター再設計で行う
