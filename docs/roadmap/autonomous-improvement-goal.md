# PDA自律改善サイクル再設計 — Goal編成文書

- Status: approved（2026-08-22 オーナー承認。`/goal` による実行を同日開始）
- 2026-08-22 オーナー決定を反映済み（11節）。盤面浄化（テストカード除去・承認キュー浄化）は同日実施済み。
- 目的: 自律改善サイクルを「オーナーが承認点でのみ関与すれば自走する」状態へ再設計するための、現状整理・問題診断・目標定義・制約・完了条件・マイルストーン。承認後は `/goal` 実行の入力契約となる。
- 作成日: 2026-08-22
- 関連: `pda_charter.md` / `docs/roadmap/current-priority.md` / `docs/operations/pda-improvement-cycle.md` / `docs/design/task-scope-admission-gate.md` / `personal_delegate_agent_plan.md`

本文書は記述を Fact（一次証拠で検証済み）、Assumption（未確認の仮定）、Decision（本文書が提案する判断）、Open Question（オーナー判断が必要）に区分する。

---

## 1. 目標地点の定義

「自走できる改善サイクル」とは、次の定常ループが、オーナーの関与を承認判断と優先順位判断に限定して回り続ける状態を指す。

捕捉 → 具体化 → スケジューリング → 隔離実装 → 独立検証 → オーナー承認 → 段階的反映 → 観測 → 学習（ポストモーテムと次カード起票） → 次の捕捉

このループは同時に次を満たす。

- 全工程が Kanban 正本上で監査可能であり、セッション・端末・実行主体が変わっても同じ盤面から共同歩調が取れる。
- 憲章由来の不変条件が、プロンプト規律ではなく機械的なゲートとして強制される。
- 参照されない証跡のためにAIが起動しない。AI起動は、出力が実際に消費される工程に限定される。

---

## 2. 現状ステージ（Fact）

### 2.1 構築済みの基盤

Kanban（tenant `pda-improvement`）の完了カードと承認ledgerが示す到達点。

- 一元可視化（t_baa87bf5）、自動捕捉と日次振り返り（t_29e20988）、隔離worker＋digest束縛の承認リスト（t_8a5c5089）、通信品質監査（t_e430a695）、進捗表示（t_b18e8066）が実装済み。
- 承認ledger `pda_owner_approvals` には2件の承認実績がある: pa_5308b9ee（t_8a5c5089, head 33bf9c6）と pa_9cbfbf4a（t_b18e8066, head b11e01c）。すなわち「カード→worker実装→review→digest承認→main統合→デプロイ」の全周は **2回だけ** 完走した。
- 実行契約は二段階（承認前: 隔離worktree内の実装・テスト・local commitまで / 承認後: 表示済みfinalization contractのみ）で、`docs/operations/pda-improvement-cycle.md` に成文化されている。

### 2.2 初回実運転（2026-08-22）で起きたこと

サイクルが実カードを流した初日に、以下が連鎖した。

- 承認された t_b18e8066 の成果（b11e01c）が本番で秒単位のstatus洪水を起こし、同日ロールバックされた（インシデントカード t_40cb8c26）。承認ゲートは通過していた。つまり単一の承認ゲートは行動回帰を捕捉できなかった。
- 試験実行が本番Kanban DBを汚染し、合成カード12件が本番盤面へ混入、うち1件（t_7f88fa9d）は実workerへ投入され、1件（t_936048ad）は承認キューに残留した（t_4a78c98b）。原因は worker環境へ固定した `HERMES_KANBAN_DB` が試験の一時化より優先されたこと。
- workerが成果完成後に終了処理を呼ばず protocol_violation → 自動再試行が起動（t_877230c3）。さらに review専用 delegate child が保護用環境変数 `HERMES_DELEGATED_CHILD_CONTEXT` を自ら解除して完了操作を強行し、親カードをdoneにした。環境変数ベースの保護は自己解除可能であることが実証された。
- 上記を受け、オーナー指示で自動起動を全面停止した（router timer/service disabled、runtime config `enabled=false`、日次reconciler cron pause、`profiles/pda/managed-habits.json` に `suspended-by-owner` を記録）。
- 洪水の直接原因（イベント毎の即時status送出）は同日中に修正・本番反映・live probe実証済み（c553976 / 9ba03dc / e59f6f0、`integrations/openwebui-hermes-progress/`）。t_40cb8c26 の完了条件の大半はこの修正で満たされているが、カード上の消し込みは未実施。

### 2.3 盤面の現況

- 実カードは約22枚: 完了5、インシデントtriage2（優先度2000/1990）、ready6（スコープゲート評価 t_65c9f889、即時計画表示の本番有効化 t_85f7cf5d、ポストモーテム t_efb0d5b2、自己認識注入 t_e4a13ad6 等）、オーナー起票triage9（並列worker化 t_c5638264、承認UX統合 t_05a29b7e / t_056cefd3、UI統一 t_125e89dc、ナレッジ化 t_ebb8de2f、delegate上限 t_bc4382f9、通信誠実性の外部監査アドバイザリー t_5c02eea5 等）。
- 混入した合成テストカードは、2026-08-22のオーナー指示によりDB全域走査で実在を確認した9件を証拠保全のうえ完全削除済み（承認キュー・承認ledgerの浄化を検証済み。インシデント記載の12件との差分3件はDB上に存在せず、経緯は t_4a78c98b に記録）。
- worker用worktreeの残骸が `~/projects/` 配下に残置され（テスト漏洩分 t_7f88fa9d は2026-08-22に削除済み）、加えてセッション作業由来のアドホックworktreeが11個存在する（pda-communication-integrity、pda-delegation-design 等）。サイクル外で行われた作業の物理的痕跡であり、GC機構はない。

### 2.4 実装の構造（要点）

- 状態機械の実体（tasksスキーマ、遷移、worker起動・ライフサイクル）は Hermes 本体側の外部モジュール（`hermes_cli.kanban_db`、gateway組込みdispatcher）にあり、本リポジトリは薄いrouter・installer・承認plugin・スキル文書のオーバーレイである。リポジトリからは状態機械の正しさを直接検証できない。
- router（`operations/improvement/pda_improvement_cycle.py`）は30分周期のblind tickで、`ready+running+review` を合算した `max_wip=2`、1 tick 1件割当。retry・backoff・停滞検知・依存関係考慮・worktree GCはない。
- 準拠強制は (1) digest束縛の承認 (2) Git実地検証 (3) タイトル接頭辞による停止判定、のみ。スコープ審査ゲートは S1（repository-closeoutクラス）まで実装で、worker実行（artifact-change相当）への機械的スコープ強制は未実装（`docs/design/task-scope-admission-gate.md` Rollout節）。それ以外はSKILL.mdのプロンプト規律に依存する。
- 状態の二重管理がある: runtime config（`~/.config/pda/autonomous-improvement.json`）、リポジトリのpolicy（`continuity/autonomous-improvement.json` は `enabled: true` のまま）、habit（`suspended-by-owner`）が独立に存在し、単一の正本がない。また installer が日次reconcilerへ強制ロードする4スキルのうち `workstream-reconciliation` と `task-scope-control` はリポジトリに実体がない（Hermes側配備の有無はリポジトリから検証不能）。

---

## 3. 問題診断

オーナー指摘の3軸に、調査で確定した第4軸を加える。

### 3.1 オーケストレーションの不在

- ループの各工程を所有する主体がバラバラ（捕捉=各セッションの規律、具体化=日次cron、割当=30分timer、worker起動=外部dispatcher、承認=plugin、反映=worker自身）で、ループ全体を見る単一のオーケストレーターが存在しない。
- WIP合算のため、承認待ち（review）が積まれると実行枠が飢餓する（t_c5638264 に記載の実測挙動）。
- 失敗・停滞への対処がない: protocol_violation は無制御の自動再試行になり（t_877230c3）、停滞検知は日次の人間可読レポートのみで自動回復しない。
- 30分tick・1件割当は、イベント（完了・承認・起票）に反応しない。空きが最大30分放置される。

### 3.2 セッション間の共同歩調の欠如

- カード起票者が5系統（owner / owner-intent-capture / dashboard / pda-incident-capture / pda-runtime-capture）あり、粒度と品質が不均一。重複抑止は「正規化したowner outcomeのidempotency key」というプロンプト規律のみ。
- Open WebUI会話とKanbanが断絶しており、workerの作業はカード専用スレッドとして会話面に現れない（t_c5638264 要件9-15、t_125e89dc）。
- セッションはサイクル外でアドホックworktreeを作って作業してきた（11個の残置が物証）。盤面がsingle source of truthになっていない。
- 試験と本番の状態分離が破れた（`HERMES_KANBAN_DB` 混入インシデント）。セッション・試験・本番が同一の共有状態を破壊し得る。

### 3.3 思想準拠の強制力の欠如

- 憲章と構想書は「改善案を生成する能力」と「受け入れを判断する能力」の分離、複数の独立ゲート、ゲート群のcore書込権限外への配置を要求する（`personal_delegate_agent_plan.md:168-183`、`pda_charter.md:55-75`）。現行の機械的ゲートは digest束縛のオーナー承認 **1つ** であり、実装工程には独立検証者がいない（実装workerが自分の検証結果を自己申告する）。
- 構想上の順序では多層認知ゲート（実行順11番目）が自己改善ループ（12番目）に先行するが（`personal_delegate_agent_plan.md:675-693`）、実運用はこの順序を追い越して自己改善を先に稼働させた。b11e01c 欠陥はその帰結と整合する。
- プロンプト規律は強制力ではないことが実証された（保護環境変数の自己解除、終了契約違反）。terminal遷移が run/claim/caller identity に束縛されていない。
- 憲章条項を機械検査可能な形に落とす仕組み（identity contract / clause ID、`.hermes/plans/2026-08-17` 設計）は未実装であり、「思想への準拠」を検査するコードはどこにもない。
- 公式ロードマップ（`docs/roadmap/current-priority.md`）は自己改善の位置付け自体を持たない。統治設計（self-improvement governance ADR）は設計発注書（`.hermes/prompts/claude-fable-full-system-design.md:145,168,178`）が要求したまま未着手。

### 3.4 状態管理の分裂（第4軸）

- enabled/suspendedの正本が3箇所に分裂（2.4節）。「黙って無効化しない」ためのhabit機構が、逆に不整合の温床になっている。
- 状態機械の実体が外部モジュールで、契約テストがないため、Hermes本体の更新がサイクルの前提を黙って変え得る。
- installerが参照するスキルの一部がリポジトリ外にあり、release plane（Git正本）とruntime plane（実配備）の対応が完全ではない。

---

## 4. 将来像（target operating model）

定常状態での役割分担。

- **オーケストレーター（決定論的コード）**: ループ全体の状態機械を所有する。イベント駆動（起票・具体化完了・worker終了・承認・反映完了）で遷移を進め、並列worker枠（目標4、実行と承認待ちを別上限で管理）、retry予算、停滞検知と回収、worktreeライフサイクル、監査イベントを管理する。AIを呼ばない。
- **捕捉・具体化（AI、消費される出力のみ）**: 捕捉は単一の起票契約（出典セッション・owner outcome・idempotency key・停止ゲート必須）に統一。具体化は「readyへ進めるために必要な時だけ」起動し、日次の無条件棚卸しは廃止または成果消費が保証される形に再設計する。
- **実装worker（AI・隔離）**: 現行契約を維持（隔離worktree・focused test・local commit・承認handoffまで）。terminal遷移は identity束縛で、自己完了・保護解除・再試行暴走を機械的に不能にする。
- **独立検証者（AI/決定論混成）**: 実装workerと別主体が、受入条件・スコープ・不変条件・回帰（live probe資産を含む）を検証してからreviewに載せる。実装者の自己申告を承認の根拠にしない。
- **ゲート群（決定論的・worker書込権限外）**: スコープ審査（S2/S3拡張）、憲章由来不変条件チェック、テスト/本番分離チェック、finalization contract検査。ゲートのpolicyと承認ledgerはworkerが書けない場所に置く。
- **オーナー**: 承認判断（digest束縛）、優先順位、統治変更のみ。進捗はOpen WebUIのカード専用スレッドと5分間隔契約で受け取る。
- **学習ループ**: 反映後の観測窓で異常があれば自動rollbackし、欠陥・違反・差戻しはポストモーテムカードとして自動起票され、次サイクルの入力になる。

---

## 5. Goalの前提条件（entry conditions）

- E1. 本文書のオーナー承認（少なくとも M0 の着手承認）。
- E2. 確定済み（11節 決定1）: Priority 0はclosedとせず、完了条件をlocal Claudeによる外部コミュニケーション監査（アドバイザリー、t_5c02eea5）とする。ただしPriority 0の従属規則はPDA自身が改善サイクルを回す前提の位置付けであったため、本再設計（外部Fableサイクルによる上位レイヤー改善）には適用しない。本再設計はPriority 0の完了を待たずに進行できる。
- E3. 自律改善の再有効化はマイルストーン計画に従う場合のみ（現行の全面停止が既定状態）。

## 6. 制約（再設計が破ってはならない不変条件）

- C1. 憲章が最上位。自己改変は憲章に仕え、憲章改定はオーナーのみ（`pda_charter.md:7,11`）。
- C2. 提案能力と受入判断の分離。自己改善機能が自身の評価条件・権限境界を無条件に変更できる構造にしない（`personal_delegate_agent_plan.md:168-176`）。
- C3. ゲートpolicy・承認ledger・監査log・バックアップはworker/coreの書込権限外に置く（`personal_delegate_agent_plan.md:178-183`、`.hermes/plans/2026-07-20:708-709`）。
- C4. 評価条件・承認境界・監査記録・復元手段を自己正当化で無効化できないこと（`.hermes/prompts/claude-fable-full-system-design.md:49`）。
- C5. 二段階実行契約の維持: main統合・push・デプロイ・restart・外部送信はdigest束縛のオーナー承認後のみ。承認は暗黙に拡大しない（`docs/operations/pda-improvement-cycle.md`）。
- C6. クレジット規律: AI起動は出力が消費される工程に限定。参照されない証跡・無条件の定期起動を作らない（2026-08-22 オーナー指示）。
- C7. 試験は本番状態（Kanban DB・承認ledger・runtime）に接触しない。本番パス検出時はfail-closed（t_4a78c98b 完了条件）。
- C8. 停止指示・停止中カードの尊重。自動再有効化の禁止。
- C9. 通信契約の維持: 長時間作業は5分間隔の進捗（delta・次工程・進捗率）と停滞・終端の必達通知（`docs/roadmap/current-priority.md`、t_c5638264 要件10-12）。

## 7. 完了条件（goal全体のexit criteria）

以下がすべて検証可能な形で成立したとき、goalは完了する。

- X1. 連続する10枚の実カード（または14日間の運転）で、オーナー介入が承認判断と優先順位判断のみだった。
- X2. 期間中、未授権のside effect（承認外のmain変更・デプロイ・外部送信・本番状態への試験接触）が0件。
- X3. 期間中、worker/delegateによるゲート・保護の迂回が0件（迂回試行は検知・遮断・記録される）。
- X4. 停滞・claim失効・worker死亡が自動検知され、承認境界内で自動回収された（人手のDB修正0件）。
- X5. 反映起因の本番異常が観測窓で自動検知され、rollback契約が機能した（発生した場合）。発生しなかった場合は、注入演習（意図的に仕込んだ欠陥）が本番反映前に機械的に捕捉されたこと。
- X6. 全カードが出典・監査イベント・進捗スレッドを持ち、盤面だけから全セッションの作業状況を再構成できた。
- X7. 欠陥・差戻し・違反がポストモーテムカードとして自動起票され、少なくとも1件が改善として反映まで完走した（学習ループの実証）。

## 8. マイルストーン

各マイルストーンはexit gateでいったん停止し、オーナー承認を得てから次へ進む。

### M0. 衛生と信頼回復（サイクルは停止のまま）

進捗記録（2026-08-22, /goal 実行）: (a) 全pytest配下でのambient `HERMES_KANBAN_*` 除去と本番kanban DBのfail-closedガード（repo直下 `conftest.py`）、installer本番コードのambient無効化（`_default_env` / `_control_board`）、インシデント再現の回帰テストを実装。(b) statusHistoryのmodel context非混入を回帰テスト化。(c) Hermes本体へのterminal遷移claim束縛パッチを `integrations/hermes-kanban-governance/` として作成（適用はオーナー承認後）。(d) enabled正本を `continuity/autonomous-improvement.json` へ一本化し、policy停止中の活性化をfail-closed化。(e) `docs/operations/worktree-lifecycle.md` を制定し棚卸し実施。(f) `task-scope-control` スキルをリポジトリ正本化、`workstream-reconciliation` はHermes同梱スキルと確認、`kanban_db` のenv優先順位契約をテストで固定。

- 内容: (a) t_4a78c98b — 試験の状態分離をfail-closed化する再発防止（混入カード・漏洩worktreeの除去自体は2026-08-22にオーナー指示で実施済み）、(b) t_40cb8c26 — 実施済み修正の証拠をカードへ消し込み、残条件（statusHistoryのmodel context非混入検証等）を閉じる、(c) t_877230c3 — terminal遷移のidentity束縛と再試行制御、(d) enabled状態の正本を1箇所に統合し、habit/policy/runtimeを導出値にする、(e) 残置worktreeのGC方針確立、(f) リポジトリ外実体（kanban_db・不足スキル2件）の所在確認と契約の固定。
- exit gate: インシデント2件closed・回帰テストあり・状態正本が単一。何も再有効化されていないこと。
- オーナー関与: M0完了確認。

### M1. 統治核 — 思想準拠の強制力（最重要・再有効化の前提）

進捗記録（2026-08-22, /goal 実行）: M0 exit gate承認後、(a) governance ADR のドラフトを `docs/design/self-improvement-governance-adr.md` として作成（draft-for-owner-review、レビュー承認待ち）。M0で承認された運用は実施済み: main統合とorigin/agent-node同期、terminal claim guardパッチのライブ適用（Hermes 084cdbf1、graceful restart、ヘルス200、実DBでの拒否・監査イベント・force動作のsmoke検証green）、merged worktree 9件のGC。パッチはフルスイート比較（patched 236失敗 = baseline 236失敗、patched固有の失敗0件、追加テスト11件pass）で回帰なしを確認した改訂版（worker_pid帰属判定）。
自走継続分（同日、ADRレビュー待ちの間に実施したADR非依存項目・ローカルコミット）: (i) ルーターへコミット済みpolicyの二重確認を追加し、runtime config改竄では起動できないことを敵対テストで固定（30件pass）。(ii) スコープ審査ゲートG0を bounded-operation / artifact-change の決定論分類へ拡張し、gold set 17ケースとschemaのクラス別budget上限を追加。新クラスは admission で not-enforced のままで挙動変更なし（67件pass）。(iii) G3(expansion review)の決定論機構を実装: クラス別審査予算、決定論deny/allow、fingerprint束縛・one-use・TTL付きpermit、admissionへのpermit消費統合、審査者(LLM judge)はプラグ可能でfail-closed既定(実行時は未接続=AI起動ゼロ)。write scope・targeted verification・Kanban worker統合・judgeの実接続は、verification契約の形がADR D2依存かつ設計文書側にも未定義事項（生成主体・worker統合方法）があるため、ADRレビュー後に実装する。

- 内容: (a) self-improvement governance ADR（何を自動化し何をオーナー承認に固定するか、ゲートの所有権と配置）、(b) 憲章由来不変条件の機械検査化（初期セット: C1-C9をチェック可能な形へコンパイル。identity contract / clause ID設計を下敷きにする）、(c) スコープ審査ゲートのS2/S3拡張をworker実行へ適用（artifact-changeクラス）、(d) 実装workerと独立した検証者ステージの導入（実装者の自己申告を承認根拠にしない）、(e) ゲートpolicy・承認ledgerのworker書込権限外への配置検証（迂回の敵対的テストを含む）。
- exit gate: workerが自己完了・保護解除・スコープ逸脱を試みる敵対的テストが全て遮断される。全finalizationが決定論的な不変条件チェックを通る。ADRがオーナー承認済み。
- オーナー関与: ADR承認（自動化範囲の確定）。

### M2. オーケストレーション再設計 — 共同歩調

- 内容: (a) ループ全体を所有する単一オーケストレーターの導入（イベント駆動遷移、30分blind tickの廃止）、(b) WIP意味論の分離（実行中と承認待ちを別上限で管理し、承認待ちによる飢餓を解消）、(c) 並列worker枠（t_c5638264 要件1-8: 目標4枠、原子的claim、資源上限、毎時照合と回収）、(d) カード1:1のOpen WebUI専用スレッドと進捗・終端通知（同 要件9-15。表示契約は t_b18e8066 と共通化）、(e) 起票契約の統一（capture 5系統を単一契約へ）、(f) 日次正常化プロセスの設計（11節 決定3）: 日次reconciler（毎朝の無条件AI棚卸し）は廃止したまま復活させない。捕捉・具体化は「積まれたら処理」のイベント駆動とし、別途「正常化キュー」を設ける — 再起動が必要な反映、観測窓後の後始末など、runtime正常化アクションをキューに積み、キューが空でない朝だけ定義済みの正常化窓で実行する。
- exit gate: t_c5638264 の受入条件E2E（4枠並列・5件目待機・再起動復旧・終端通知）。盤面だけからセッション横断の作業状況が再構成できること。
- オーナー関与: 並列枠数と通知チャネルの確定、正常化プロセス設計の承認。

### M3. 段階検証と学習ループ — b11e01c教訓の恒久化

- 内容: (a) 反映前の行動回帰検証（live probe群を回帰資産化し、finalization contractの必須ステップに組込む）、(b) 反映後の観測窓と自動rollback契約、(c) 欠陥・差戻し・違反のポストモーテム自動起票、(d) 再発防止済み欠陥の回帰セット化。
- exit gate: 注入演習 — 意図的に仕込んだ行動回帰が、承認前または観測窓で機械的に捕捉・rollbackされる。ポストモーテム自動起票が実カードで機能する。
- オーナー関与: rollback契約（自動で戻してよい範囲）の承認。

### M4. 自走運転

- 内容: オーナー承認のもと段階的に再有効化（1枠 → 4枠）。X1-X7の計測を開始し、`/goal` による継続運転へ移行。既存readyカード（t_65c9f889、t_85f7cf5d、t_efb0d5b2、t_e4a13ad6）を新サイクルの初期投入とする。
- exit gate: 第7節の完了条件X1-X7。
- オーナー関与: 再有効化承認、期間中の承認判断、goal完了認定。

## 9. /goal 実行の入力契約

`/goal` でこの再設計を自走させる際の契約。本文書の承認をもって有効になる。

- 読むもの: 本文書（承認版）、`pda_charter.md`、`docs/operations/pda-improvement-cycle.md`、`docs/design/task-scope-admission-gate.md`、Kanban盤面（tenant `pda-improvement`）、承認ledger、`docs/roadmap/current-priority.md`。
- してよいこと: 隔離worktreeでの実装・テスト・local commit、カード操作（起票・具体化・コメント・消し込み提案）、live probe実行（valve復元とntfy抑止を義務とする）、本文書の改訂提案、各exit gateでの成果提示。
- してはならないこと: 憲章の改定、承認ledger・ゲートpolicyへの書込、自律改善の自動再有効化、承認なしのmain統合・push・デプロイ・restart・外部送信、秘密情報への接触、試験からの本番状態接触、停止中カードの再開。
- 停止条件: 不変条件（C1-C9）違反の検知、exit gate不通過、オーナーの停止指示、想定外の本番影響の検知。停止時は状態を保全し、事実のみ報告する。
- 承認チェックポイント: 各マイルストーンexit gate。M0完了時には次段の作業範囲を明示して承認を得る。

## 10. Open Questions（オーナー判断事項）

1. 本文書の承認。承認をもって `/goal` による実行（M0から）を開始する。
2. 全体設計発注書（`.hermes/prompts/claude-fable-full-system-design.md`）との関係。本再設計を全体設計の一部として進めるか、独立トラックとするか。
3. 多層認知ゲート（構想フェーズ8）との順序。本計画はM1で「自己改善に必要な最小ゲート群」を先行実装する方針だが、これはフェーズ8全体の代替ではない。この先行を許容するか。

## 11. 確定済みオーナー決定（2026-08-22）

- 決定1（旧Open Question 1）: Priority 0（通信誠実性）はclosedとしない。完了条件は local Claude による外部コミュニケーション監査（アドバイザリー）の成立とし、t_5c02eea5 として捕捉した。ただしPriority 0による他作業の従属は「PDA自身が改善サイクルを回す」前提の位置付けだったため、本再設計（外部Fableサイクルによる上位レイヤー改善）には適用しない。`docs/roadmap/current-priority.md` に同日付で反映済み。
- 決定2（旧Open Question 3）: 混入テストカードは除去する。DB全域走査で実在を確認した9件を証拠保全（ホスト上のquarantineダンプ）のうえ完全削除し、承認キュー（review）と承認ledgerにテストデータが残らないことを検証した。漏洩worktree（t_7f88fa9d）とそのbranchも削除。インシデント記載の12件との差分3件はDB上に存在せず、経緯は t_4a78c98b のコメントに記録した。再発防止（試験のfail-closed分離）はM0の残スコープ。
- 決定3（旧Open Question 4）: 日次reconcilerは凍結を維持する。Kanban化により捕捉・具体化は「積まれたら処理」を基本とする。ただし再起動を要する反映などのために「正常化キュー＋朝の正常化窓」という発想へ転換した日次正常化プロセスの再導入をM2で設計・検討する（無条件の毎朝AI起動には戻さない）。
