# 設計ドラフト: 改善サイクル・オーケストレーター (M2)

- Status: draft（M2 実装の設計入力。効力は M1 exit gate 通過後のオーナー承認で生じる。ADR レビュー結果に依存する箇所は「ADR 依存」と明記した）
- 日付: 2026-08-22
- 要求の正本: `docs/roadmap/autonomous-improvement-goal.md` M2、Kanban カード t_c5638264（オーナー要件 1-15）、2026-08-22 オーナー決定3（日次正常化プロセス）、`docs/operations/worktree-lifecycle.md`
- 前提の実測: 30 分周期の blind tick・WIP 合算・自動回復なしという現行ルーターの限界（goal 文書 3.1 節）

## 設計原則

- P1. **二つ目の dispatcher を作らない。** Hermes gateway には 60 秒周期の Kanban dispatcher（global / per-profile 同時実行上限つき）と通知購読（kanban notify）が既にある。オーケストレーターは「何を ready にし、何を割り当ててよいか」を決める薄いポリシー層とし、worker の起動・生存管理は既存 dispatcher に委ねる。
- P2. **オーケストレーターは AI を呼ばない。** 全遷移は決定論。AI 起動（具体化・検証・judge）は出力が消費される工程に限定し、呼び出しの発生自体を監査イベントにする（C6）。
- P3. **状態の正本は Kanban DB と Git のみ。** オーケストレーター固有の永続状態を増やさない。増やす場合は再構築可能なキャッシュに限る。
- P4. **停止が常に勝つ。** committed policy（M0 で一本化）、停止接頭辞、オーナー停止指示は、どのイベントよりも優先して評価する。

## 駆動方式（現行 30 分 tick の置換）

- イベント駆動 + 低頻度リコンサイルの二層にする。
  - イベント: カードの ready 化、run の終端（done / review / blocked / failed）、承認・差戻しの記録、finalization 完了。これらを既存の kanban 通知と task_events から購読し、発生の都度「割当てポリシー評価」を 1 回走らせる。空き枠は数秒〜数十秒で補充され、30 分の空白は消える（要件 5 の「完了イベントで枠補充」）。
  - リコンサイル: 毎時 1 回、イベント欠落に備えて盤面全体を照合する（要件 5）。生存していない claim、期限切れ permit、残置 worktree、review 滞留を検出し、回復は「安全に自動化できる種別」だけ実行して残りは審査リストへ記す。
- 割当てポリシー評価は 1 回の実行で 1 トランザクション。原子的 claim（既存 CAS）を用い、同一カードの重複割当てと worktree 共有を構造的に排除する（要件 3, 4）。

## 二値判断プロセスの形骸化監視

`docs/design/process-degeneration-monitor.md`の共通契約を、オーケストレーターの決定論的な観測・起票経路として実装する。オーケストレーター自身は判定内容を再解釈せず、登録済みeventの完全性、72時間窓の件数、episode状態、起票冪等性だけを扱う。

- 判定eventが永続化された直後に、その`monitor_id`だけを再評価する。
- 毎時reconcileで全登録を再評価し、event欠落、遅着、処理失敗、時間経過だけで閾値を横断する場合を回収する。
- 期待eventだけがある間はprocess固有の期限までpendingとし、期限または必須ライフサイクル境界を越えた場合だけmissingとして起票する。
- 各processの有効な直近72時間で、`N >= 10`かつ`max(true_count, false_count) / N >= 0.95`なら未割当Triageへ「判定プロセス失敗疑い」を冪等起票する。`N < 10`では比率を記録しても偏向episodeを開始しない。
- 同じepisodeではカードへ最新集計を追記し、回復後の再発は新episodeとして関連付ける。
- 欠損、不正、未実施、評価不能、同一施行の同値または相反duplicate、母集団取得不能、monitor自身の失敗は、偏向比率から黙って落とさず別のtelemetry failureとして起票する。
- sinkはdefault board、tenant `pda-improvement`、未割当Triageである。起票によってworkerを割り当てず、元の判定、作業、承認、finalizationを変更しない。
- sink失敗時はcontrol側のdurable outboxへ同じidempotency keyを保持し、task IDのread-backまで再送する。起票失敗をepisode成功として記録しない。
- monitor状態のfalse→true遷移、episode generation採番、outbox行作成は同じcontrol transactionでCASし、event直後評価と毎時reconcileの競合で二重episodeを作らない。
- Kanban delivery障害はprimary sinkへ再帰的にだけ通知せず、control storeの`process_monitor_health`とKanban非依存の`owner_alert_outbox`へ記録する。control store自体の失敗は構造化journal eventとservice non-zeroで表面化し、次の正常reconcileが冪等に取り込む。
- monitor IDが欠落・未知なraw eventは予約ID`process-monitor.ingress-integrity`へ帰属させ、control envelopeのingress IDで冪等化する。未知IDをregistryへ自動追加しない。
- 集計・reconcile・起票にAIは使わない。新しい監視対象はregistryへ追加し、個別if分岐を増やさない。

初期登録は`scope.prework.additional-assurance-required`と`scope.final.final-scope-conformant`の二件である。前者はScopeFrame/計画のTerra提出を期待母集団とし、作業開始前の`additional_assurance_required`を一件要求する。後者は全ての終端runを期待母集団とし、実作用監査の`final_scope_conformant`を一件要求する。Terraが追加保証を要求したrunでは、予約済みの別主体監査が欠けた最終eventを有効としない。

この節は共通monitorの実装契約である。実装正本は`integrations/hermes-scope-gate/process_monitor.py`と同integrationのruntime/installerに置き、オーケストレーターは登録eventを供給する側として接続する。稼働状態はserviceとstate storeのread-backで確認する。

## WIP 意味論の分離（承認待ち飢餓の解消）

- 現行の `max_wip`（ready+running+review 合算）を廃止し、次の独立上限へ分離する（要件 1, 2）。
  - `running_cap`: 実行中 worker 数の上限。既定 4、オーナーが 1-8 で設定可能。
  - `review_cap`: 未統合成果（review 滞留）の上限。承認待ちを無制限に積まない歯止めで、実行枠とは独立に数える。
  - `host_guard`: ホスト実測に基づく fail-closed 上限。メモリ 12GiB の実測（2026-08-22 の OOM）を踏まえ、空きメモリ・load・provider 利用枠のしきい値を下回ったら新規割当てを止める（要件 6）。
- 割当て可否 = 停止判定 → host_guard → running_cap → review_cap → 依存関係充足 → 優先度順、の順で決定論的に評価する。

## worker ライフサイクルと回復

- 生存判定は claim（claim_lock / worker_pid / 期限）を正本とし、terminal 遷移の claim 束縛（M0 で本番適用済み）を前提に置く。
- protocol_violation の再試行は「進捗判定つき」へ変更する: 違反 run の worktree に検証可能な成果（新規コミット）が存在する場合、自動再試行せず審査リストへ回す（t_877230c3 の残スコープ。判定は Git の事実のみで行い、AI を使わない）。
- stale claim・死亡 worker の回収は既存の crash 検知 CAS を使い、回収イベントを必ずカードへ記録する。
- worktree GC は `docs/operations/worktree-lifecycle.md` の規則をリコンサイルに組み込み、削除・審査リスト送りを自動化する。

## カード専用スレッドと進捗配信（要件 9-15）

- worker が原子的 claim で着手を確定した時点で、Open WebUI にカードと 1:1 の専用スレッドを作成する。run 再試行・gateway 再起動では同一スレッド内に run を区切って継続し、重複スレッドを作らない（要件 9）。
- 投稿契機は「着手・実進展・状態遷移・停滞判定・阻害発生・終端」で、内容は既存の進捗表示契約（現在・直近結果・次の一手・阻害・最終実進展と delta）と共通化し、二重実装しない（要件 10, 15。表示契約の正本は t_b18e8066 の成果）。
- 投稿は task_events / run / heartbeat を根拠に順序保証・冪等化し、再送や crash で欠落・二重投稿しない（要件 11）。終端状態は必ず投稿し、承認待ちは承認リストへの導線を含める（要件 12）。
- どの端末からも同じ所有者セッションで一覧から発見でき、Kanban と相互に遷移できる（要件 13）。承認前の外部送信禁止の例外は、この所有者向け進捗テレメトリだけに限定し、許可フィールドを型で定義する（要件 14）。

## 日次正常化プロセス（オーナー決定3）

- 毎朝の無条件 AI 棚卸しは復活させない。代わりに決定論の「正常化キュー」を設ける。
  - 積まれるもの: 承認済み finalization のうち再起動を要するもの（finalization kind が restart 系）、観測窓明けの後始末、リコンサイルが検出した安全に自動化できる回復操作。
  - 実行: キューが空でない朝だけ、定義済みの正常化窓（バックアップ 05:00 と重ねない時刻）で順次実行する。各実行は対象カードへ監査イベントを残す。
  - 空の朝は何も起動しない（C6）。

## ADR 依存（レビュー結果で確定する箇所）

- ScopeFrame/計画のTerra事前評価、全runの実行主体による作用監査、`additional_assurance_required=true`時の別主体監査を別stageとして扱う（ADR D2、`task-scope-admission-gate.md` 0節）。
- 自己改善成果に対する従来の独立実装検証は全変更で維持し、上記の条件付き追加スコープ監査と同一視しない（ADR D2）。
- 統治ファイル変更の拒否ゲートの強制点（ADR D3）。
- 承認記録簿の物理分離（ADR Open Question 4）。

## 移行

1. 現行ルーターのポリシー判定（優先度・停止接頭辞・policy 二重確認・worktree 整合）を関数として抽出し、イベント駆動の評価器から呼ぶ。30 分 timer は移行完了までフォールバックとして残し、二重割当ては原子的 claim が防ぐ。
2. スレッド配信は表示契約の共通化から着手し、既存 run にも遡って適用しない（新規割当てから有効化）。
3. ScopeFrame/Terra/final auditのevent契約と期待母集団を先に実装し、共通形骸化monitorをshadow modeで照合してからTriage sinkを有効化する。
4. 各段の有効化は staged config + オーナー承認（既存の activation 契約）を踏む。
