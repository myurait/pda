# S3-M1 実装 反証レビュー 確証欠陥の処置台帳（2026-08-23）

- Status: closed（第1ラウンドの確証欠陥 37 件＝1〜6 節、司令塔判断 4 項目＝7 節、D-S3-7 実装の反証レビュー 14 件＝9〜10 節、いずれも処置完了。exit 条件 3 件はすべて closed＝10 節 3。残余は 8 節の 1 項目と 10 節 4 の司令塔判断 2 項目）
- 読み取り方針: **`restricted-` 接頭辞の対象。個別の再現条件に触れるため Fable モデルのセッションでは直接読まない**。抽象名のみの一覧は `docs/operations/adversarial-suite.md` にある。
- 対象レビュー: `restricted-s3-impl-review-2026-08-23-{correctness,bypass,compat,fidelity}.md`（確証欠陥 37 件 + 判断 1 件）
- 正本設計: `docs/design/task-scope-admission-gate.md`「S3-M1」節（本処置に伴う改訂を含む）
- ローカルテスト: `./tmp/venv-scope/bin/python -m pytest integrations/hermes-scope-gate/tests -q --ignore=integrations/hermes-scope-gate/tests/test_hermes_integration.py -p no:cacheprovider` → 237 passed（処置前 199）。新規 38 件。
- レビュー時の再現プローブ（`tmp/` 配下、git 管理外）を再実行し、脆弱側の観測がすべて拒否側へ反転したことを確認した。反転しなかったものは下記の「司令塔判断」「明示済み残余」に対応する。

## 処置の分類

- **修正**: 実装を変更し、回帰テストで固定した。
- **部分修正**: 事実の不整合や計上誤りは直したが、許可集合そのものの変更を含む部分は設計判断として保留した。
- **文書対応**: 実装は設計どおりで、設計本文・README・台帳側の整合が処置。
- **判断へ回付**: 許可集合または既定値の変更を伴うため実装を変えていない。

## 1. 修正した欠陥

### パス基盤（照合入力の統一）

| ID | 処置 | 回帰テスト |
| --- | --- | --- |
| I-BYP-01 [blocker] | 正規化関数を作り直し、生引数に対する上位参照検査を折り畳みの前に置き、照合入力を実体解決後のパスへ統一した。root 側も実体解決する。監査記録の資源名も解決後の相対パスになる。 | `test_an_upward_reference_after_a_link_element_cannot_relocate_the_target`（1段/2段のパラメタ）、`test_a_name_resolving_outside_the_worktree_is_denied_on_every_layer` |
| I-COR-02 [blocker] | 同上。glob 照合が解決後の相対パスに対して行われるため、ロック済み root 内部でも閉集合になる。第一層の書込カタログ経路・ステージ経路・第二層の検証対象経路の3箇所が同一関数を通る。 | `test_the_scope_match_uses_the_resolved_destination_not_the_notation`、`test_an_in_scope_name_resolving_out_of_scope_is_denied_on_every_layer`（write / stage / verify の3経路） |
| I-COR-11 [minor] | 帰属判定を表記依存から場所依存へ変更（安全側の誤りの解消）。 | `test_equivalent_spellings_of_the_locked_root_resolve_alike` |
| I-COM-02 [major] | 同上。terminal の workdir 判定も独自の文字列比較を撤去し、実体解決の比較へ寄せた。 | `test_an_equivalent_spelling_of_the_locked_worktree_is_not_falsely_denied` |

補足: 単独で呼ばれていた祖先解決関数は削除し、正規化関数へ統合した（設計「パス正規化は単一の決定論関数へ集約する」）。既存テスト `test_write_target_entity_resolution_stays_inside_the_locked_root` は新しい呼び出し形へ更新した。

### 契約バインドと強制の持続

| ID | 処置 | 回帰テスト |
| --- | --- | --- |
| I-COR-01 [blocker] / I-BYP-02 [blocker] | `start_turn` の契約記録照会を分類結果から切り離した。記録があるタスクは分類に関わらず `artifact-change` として登録し、closeout 由来のフラグ（commit/push 許可）を持ち込まない。分類器の出力は `turns.classified_class` へ監査保存する。 | `test_a_seeded_task_is_enforced_whatever_the_message_classifies_as`（audit-only / bounded-operation / 疑問形 / closeout の5パラメタ。closeout パラメタで `allow_push == 0` と push 拒否を固定） |
| I-COR-03 [major] | ターンキーのフォールバックにメッセージ由来の識別子を必ず含めるようにした（task_id 単独をキーにしない）。 | `test_every_message_of_a_task_gets_its_own_turn` |
| I-COR-04 [major] / I-BYP-04 [major] | 未バインド判定を「task_id の seed のみ」から「task_id または session_id の契約記録、または当該 task/session の強制ターン履歴」へ拡張。未知の turn_id も同じ判定へ委譲した。 | `test_an_unbindable_call_is_fail_closed_without_a_task_id` |
| I-COR-05 [major] | ターン束縛の優先順位を「未完了の強制ターン → 直近のターン（完了済み含む）」に変更。より古い未完了ターンへ遡らない。 | `test_the_latest_turn_binds_a_call_even_after_it_closed`、`test_a_closed_turn_keeps_denying_mutation_without_an_explicit_turn_id` |
| I-COR-06 [major] / I-COM-05 [major] | session 正常終了でも強制ターンを閉じる。閉じたターンは per-turn policy 注入の対象外にした。 | `test_a_clean_session_end_closes_an_enforced_turn` |
| I-COM-03 [major] / I-FID-02 [major] | 上記の束縛順位と未バインド判定の両方で解消。閉鎖後に未強制へ戻る経路が無くなった。 | 同上 + `test_a_closed_turn_keeps_denying_mutation_without_an_explicit_turn_id` |
| I-COM-04 [major] / I-FID-03 [major] | 自己 lock を `self_scope_locks` へタスク単位（task_id、無い場合は session）で永続化し、後続ターンを `locked` として作る。未完了の強制ターンが後続の未強制ターンに遮蔽されない束縛順位も併せて入れた。 | `test_a_self_lock_keeps_enforcing_the_next_turn_of_the_same_task`、`test_an_open_enforced_turn_is_not_shadowed_by_a_later_unenforced_turn` |
| I-FID-04 [major] | 自己 lock の入口で契約 seed を照会し、seed があるタスクでの宣言 lock を拒否する（ターン state に依存しない）。 | `test_a_self_lock_is_refused_while_the_task_carries_a_seed` |

### 既定拒否段・予算・境界

| ID | 処置 | 回帰テスト |
| --- | --- | --- |
| I-FID-01 [major] | lock 前段と契約検証失敗段に、locked 段と同じ順序（wall → tool → deny）でクラス予算を適用した。予算値は locked 契約があればその契約から、無ければクラス既定から引く。 | `test_the_unlocked_stages_are_bounded_by_the_class_budget` |
| I-BYP-03 [major] | ステージ対象の実体解決後にディレクトリ指定を拒否する（`stage-directory`）。削除ステージ（存在しない in-scope パス）は許可のまま。 | `test_staging_a_directory_is_denied_even_when_a_pattern_matches_its_name`、false deny 側の対照 `test_staging_a_deletion_of_an_in_scope_file_is_not_falsely_denied` |
| I-FID-05 [major] | 宣言済み入れ子コンテナを listed 分岐と同じ規則へ揃えた（形状違い・要素型違い・書込先ゼロを拒否）。 | `test_a_declared_nested_container_is_never_skipped` |
| I-BYP-07 [minor] | terminal の引数キーを明示 allowlist にし、未列挙キーを `terminal-argument-unlisted` で拒否。 | `test_unlisted_terminal_argument_fields_are_denied` |
| I-BYP-09 [minor] | 拡張審査の第二段（契約が既に許可している判定）は permit 行を作らず予算を消費しない。 | `test_expansion_review_of_an_already_permitted_action_costs_no_budget` |
| I-COR-07 [major] | admission を呼ぶ全経路に fail-closed の例外境界を置いた（pre フック、制御ハンドラ、記録専用フックは飲むが外へ出さない）。書込競合については、admission が保持しうる時間（外部プロセス検証の timeout 合計）を上回る待ち時間へ変更し、競合が例外ではなく判定になるようにした。 | `test_the_admission_boundary_blocks_when_the_gate_itself_fails`、`test_admission_under_write_contention_returns_a_decision` |
| I-COM-10 [minor] | 検証の「不一致」と「実行失敗」を別扱いにした。実行失敗ではターンを登録せず、呼び出しは未バインド経路で fail-closed のまま次のフックで再試行できる。契約スキーマの読込と検証器のコンパイルはプロセス内で1回に変更。 | `test_a_transient_repository_probe_failure_stays_retryable` |
| I-COR-08 [minor] / I-COM-07 [minor] | 保持期間 purge の対象に拡張 permit・契約 seed・自己 lock・使用履歴を追加。 | `test_expired_contract_records_and_permits_are_purged` |

### 契約が運ぶ権限と監査面

| ID | 処置 | 回帰テスト |
| --- | --- | --- |
| I-BYP-06 [minor] | 契約に `actions.git_write`（`stage` / `commit`）を追加し、スキーマ側で artifact-change の必須項目にした。admission はこの欄を引き、欄が無い契約は git 書込を拒否する。seed API から縮小できる。 | `test_the_contract_carries_git_write_permission`、`test_a_contract_without_the_git_write_field_denies_git_writes` |
| I-COR-09 [minor] | artifact-change の対象欄は検証済み worktree から導出し、自由入力を受けない。スキーマに件数上限を追加。 | `test_the_self_lock_target_list_is_derived_not_declared` |
| I-FID-06 [minor] | admission 本体の class 分岐を dispatch テーブル参照へ置き換え、G3 第二段と同じ表を引く。 | `test_the_admission_dispatch_is_the_only_class_branch` |
| I-FID-07 [minor] | 契約スキーマの closeout 条件節に必須キー宣言を追加し、3分岐の記述形を揃えた。 | 既存 `test_generated_contract_validates_against_draft_2020_12_schema` + `tmp/verify_fidelity.py::probe_schema_gaps` で3分岐の宣言状態を確認 |
| I-BYP-08 [minor] | lock 前段の有効化を環境変数 `PDA_SCOPE_GATE_ARTIFACT_PRELOCK` から読む経路を追加（既定は変更せず無効）。 | `test_the_prelock_stage_has_a_configuration_path` |
| I-COM-08 [minor] | 制御ツールスキーマの `targets` 必須指定をクラス別（closeout 3キー / artifact-change は worktrees + write_paths）の選択形に戻した。 | 既存 `test_plugin_registers_one_control_tool_and_enforcement_hooks` と `test_the_seed_api_is_not_part_of_the_agent_facing_control_tool` が同スキーマを読む |

## 2. 部分修正（残りは司令塔判断）

### I-COM-01 [blocker] 強制ターンでの必須ツール群の拒否と拒否予算の枯渇

修正した部分:

- `ARTIFACT_READ_TOOLS` を実行中のツール語彙へ合わせた。実在しない名前（見かけの網羅）を削除し、実在する読み取り系ツールを追加した。語彙の一致は自動テストで固定した（`test_the_read_tool_allowlist_matches_the_running_tool_vocabulary`。語彙の正本は progress pipe の活動グループを解析して読む）。
- 予算値の参照元を、モジュール定数の直読みから locked 契約の `budget`（無ければクラス既定）へ揃えた。

保留した部分（D-S3-7）: リポジトリ境界の外側にしか作用しないツール群を第一層の判定対象外カテゴリにするか、読み取り専用 git を第一層へ加えるか、拒否上限を write 境界の逸脱試行に限定するか。いずれも許可集合または計上規則の変更であり、設計判断として実装を変えていない。処置後の実測では、当該ツール群の拒否は依然として拒否上限を消費する（上限直前までは write scope 内の作業が続行でき、`scope_gate` の lock / complete は上限後も到達可能）。

**→ 解決済み（2026-08-23 の司令塔決定、コミット `e98b219`）。下記 7 節を参照。上記「保留した部分」の記述は起票時点の状態である。**

## 3. 文書対応のみ

| ID | 処置 |
| --- | --- |
| I-COR-10 [minor] / I-BYP-05 [minor] | commit の admission は引数構文を検査し index の内容を照合しない。設計 §11 に第9項「第一層で明文化する残余」を新設し、脅威モデルとして明記した。実装で閉じる場合は admission に別の外部プロセス検査が増えるため、帰属を D-S3-7 に含めた。README の限界節にも記載。**D-S3-7 の決定 4 点には含まれなかったため残余のまま open（8 節）。** |
| I-COM-09 [minor] | README の「seed は turn 開始時に消費される」表現を持続的上限の実装に合わせて書き換えた。契約記録の使用履歴をターン単位で記録するテーブルを追加し、どのターンが記録を使ったかが残るようにした（`contract_scope_uses`、`test_every_message_of_a_task_gets_its_own_turn` で件数を固定）。常時注入の system prompt section に artifact-change の二層契約と lock 手順の要約を追加した。 |
| I-FID 判断1 相当（lock 前段の既定値の適用範囲） | 設計へ D-S3-8 として起票。実装は既定値を変更せず、設定経路のみ追加。 |

## 4. 判断へ回付（起票時点では実装を変えていない）

**この節の 4 項目はすべて 2026-08-23 の司令塔決定で解決し、コミット `e98b219` で実装・文書化した。下記 7 節を参照。**

| ID | 理由 | 決定後の状態 |
| --- | --- | --- |
| I-COM-06 [major] | 読み取り専用 git を第一層へ加えることは許可集合の拡大であり設計判断。§10 の受入項目一覧は closeout 事例を前提としているため、artifact-change 版の受入項目（強制状態を通す replay fixture）の新設も同じ判断に含める。D-S3-7 として起票した。 | 解決（7 節 1・4） |
| J-FID-01 [judgment] | I-COM-06 と同一の判断（読み取り専用 git の deny と拒否上限の相互作用）。D-S3-7 に統合した。 | 解決（7 節 3） |
| I-COM-01 の残余 | 上記 2 節のとおり。 | 解決（7 節 1・2・3） |
| I-BYP-08 の既定値 | 有効化経路は入れたが、どのレーンで既定 on にするかは D-S3-8。 | 決定（7 節 5。既定 off を批准） |

## 5. 誤検知（0 件）

再検証の結果、確証欠陥として計上されていた 37 件すべてについて、記載された性質が処置前のコードで成立することを確認した。誤検知として棄却したものは無い。

処置後に残る「反転しなかった観測」は次の2つで、いずれも誤検知ではなく残余である。

1. lock 前段の既定拒否が既定 off であること（D-S3-8）。
2. task_id も session_id も伴わないターンに対して、後から記録された seed の上限が効かないこと。契約記録の照会には識別子が必要で、両方が欠けたターンには照会対象が存在しない。運用条件として「強制クラスでは task_id か session_id のいずれかが必ず配線されていること」を設計 §11 第9項に明記し、第7項の synthetic payload 確認に含めた。

## 6. 設計文書への改訂（本処置と同一変更に含む）

- 契約の拡張: `actions.git_write` を追記。
- 契約ライフサイクル 第1項: seed を持続的上限として記述。自己 lock のタスク単位持続、分類器出力を admission 入力にしないこと、ターン識別子がメッセージ単位であることを追記。
- 第2項: クラス予算を lock 前段と契約検証失敗段にも適用すること、有効化が設定から到達できることを追記。
- 第4項規範要件: session 終了を閉鎖契機として明記、閉じたターンの到達可能性とターン束縛の優先順位、検証の「不一致」と「実行失敗」の区別を追記。
- 第9項（新設）: 第一層で明文化する残余（index 内容、terminal 引数フィールドの閉鎖、host 識別子の配線前提、ゲート自身の失敗の fail-closed、保持期間）。
- 未解決の設計判断: D-S3-7 / D-S3-8 を起票。

## 7. D-S3-7 / D-S3-8 の決定による解決（2026-08-23、コミット `e98b219`）

- ローカルテスト: 237 passed（本節の処置前）→ **293 passed**。新規 57 パラメタ、既存パラメタ 1 件削除（下記 6 参照）。
- Status 更新: 本台帳の 2 節「保留した部分」と 4 節「判断へ回付」は解決済み。**未解決のまま残るのは 8 節の 1 項目のみ**。

### 1. 読み取り専用 git を第一層へ（I-COM-06 / I-COM-01 の一部）

`status` / `diff` / `rev-parse` / `branch` を locked 段の terminal admission へ追加した。引数検査は closeout の既存実装（トークナイザ、境界付き pathspec 検査、検証用引数 allowlist）をそのまま経由し、本クラス用の第二のパーサーを作っていない。当該共有関数を artifact-change のために拡張することもしていない（拡張は closeout の受入集合も広げるため）。

closeout の読み取り集合より狭い 2 点（いずれも意図した縮小、設計本文へ明記）:

- ネットワーク越しの読み取り（remote ref 照会系）は push に奉仕するものであり、push を持たない本クラスでは対象外。
- `log` は closeout 側に境界付き引数検査の実装が無く、追加すれば「新しいパーサー」に当たるため除外。commit id は `rev-parse HEAD` が供給する。

読み取りは `actions.git_write` の検査より前に判定する（書込権限を持たない契約でも状態は見られる必要がある）。drift 再検査は読み取りには適用しない。

回帰テスト: `test_read_only_git_is_admitted_inside_the_locked_worktree`（9 パラメタ）、`test_read_only_git_arguments_outside_the_admitted_form_are_denied`（6 パラメタ）、`test_read_only_git_reads_outside_the_locked_worktree_are_denied`、`test_read_only_git_needs_no_git_write_permission`、`test_push_stays_outside_the_first_layer`、`test_the_read_only_git_subset_is_a_closed_set`。

### 2. 作業記録系カテゴリの新設（I-COM-01 の残余）

`ARTIFACT_WORK_RECORD_TOOLS` を**閉じた明示カタログ**（13 名: `todo` と kanban 系 12 名）として追加し、locked 段・lock 前段・契約検証失敗段で許可（audit 記録のみ）した。capability 推論やツール引数の形状ヒューリスティックは用いていない（R-11 と同型の欠陥を新設しないため）。未列挙ツールの default deny for mutation は不変。

明示的な除外と理由: 別エージェント起動系（クラス予算 `subagents` は 0、設計 §10 項目 5 でも拒否）、外部情報取得系（依頼外の調査＝expansion）、スキル定義を書き得るもの（リポジトリのファイル書込に当たる）、ターン契約外の永続状態を書くもの。

lock 前段・契約検証失敗段でも許可した点は「第一層で許可」の拡張である。作業管理平面には逸脱しうるスコープが無く、また座礁したターンに対して INV-S6 が求める行動（blocked として記録する）がこのカテゴリで行われるため、記録手段を閉じると規範自体が実行不能になる。設計本文に明記した。

> **【9 節で改訂】** 「作業管理平面には逸脱しうるスコープが無い」はリポジトリ書込境界については成り立つが、審査ゲート自身の入力面については成り立たない。カードの run 終端はオーケストレーターが次の割当てを判断する購読対象である。また許可理由（INV-S6 の blocked 記録）は 13 名全体を覆っていない。9 節 1 でカタログを段階別に二分し、宛先を引数に運ぶツールと統治権限に属するツールをカタログ外へ出した。

回帰テスト: `test_work_record_tools_are_admitted_in_a_locked_turn`（5 パラメタ）、`test_work_record_tools_are_admitted_before_lock_and_after_a_failed_seed`、`test_the_work_record_catalogue_is_a_closed_explicit_set`、`test_tools_outside_the_work_record_catalogue_stay_denied`（3 パラメタ）。

### 3. 拒否上限の計上限定（J-FID-01 / I-COM-01 の残余）

`artifact_deny_counter(action)` を追加し、計上先を拒否理由コードごとに決める閉じた表にした。上限値（6）は維持。

- 逸脱試行（write 境界・実行境界）→ `denied_count`。**未分類の理由コードもここに落ちる**（免除は明示列挙によってのみ与える）。
- 読み取り境界の拒否 → `tool_count`。計上されない拒否が無償にならないようにした結果、計上されない経路もクラス予算で有界である。
- 予算枯渇そのものの拒否（wall / tool / deny）→ いずれの計数も消費しない。

計上規則は artifact-change に限定し、closeout の計上は変更していない。

**解釈を要した点**: 決定文の「読み取り系の拒否は計上しない」と「計上を逸脱試行に限定する」は、許可された読み取り subcommand が admit 範囲外の引数を伴う場合に衝突する。免除を「逸脱しえない subcommand」に限り、「逸脱を試みる引数」は計上する側へ寄せた（当該拒否はロック済み worktree 外への読み取りか、読み取り形だけが許可された subcommand の書込形のいずれかであり、後者は write 境界への試行そのものである）。設計本文へ明記した。

> **【9 節で撤回】** この二分は網羅ではない。第三の類型（ロック済み worktree 内の純粋な読み取りで、引数形が allowlist に載っていないもの）が落ちており、免除の粒度が subcommand 名であったことと併せて両方向の誤分類を生んでいた。実測で確証（I-DB-02 / I-DB-03 / I-DC-01 / I-DC-02）。9 節 2 の三分類が正本である。

回帰テスト: `test_the_deny_ceiling_counts_only_boundary_deviations`（11 パラメタ）、`test_read_refusals_do_not_strand_a_turn_that_keeps_working`、`test_boundary_deviations_still_exhaust_the_deny_ceiling`、`test_uncounted_denials_stay_bounded_by_the_class_budget`、`test_recognized_read_only_git_subcommands_are_refused_without_counting`（9 パラメタ）、`test_unrecognized_git_subcommands_still_count_as_deviations`、`test_closeout_deny_counting_is_unchanged`。

### 4. §10 受入項目の新設（I-COM-06 の一部）

設計 §10 へ artifact-change 版の受入項目 15〜17 を別立てで新設した。既存項目 1〜14 は改訂していない。`push` が S3 第一層の対象外である旨を明記した。

回帰テスト: `test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling`（13 手順の通常フロー、拒否 0 件で完走）、`test_replay_the_worker_flow_survives_one_unadmitted_read_attempt`、`test_replay_the_enforced_flow_still_refuses_the_incident_expansions`。

### 5. D-S3-8（lock 前段の既定値）

既定 off を批准。既定値・設定経路は変更していない（文書対応のみ）。設計本文へ「既定 off は INV-S8 の恒久緩和ではなく S1 と同じ段階的 rollout 方針の適用であり、自己 lock レーンの有効化は S3 rollout の実運用評価、自律 worker レーンの有効化は seed 配線と同時（D-S3-6 に従属）」を明記した。

### 6. 既存テストの変更（1 件）

`test_commit_arguments_and_other_git_writes_are_bounded` のパラメタから読み取り形の拒否を固定していた 1 件を削除した。D-S3-7 が当該挙動を反転させたためであり、読み取り形は上記 1 の新規テスト群へ移した。他の既存テストは無改変。

### 7. 併せて更新した文書

- `docs/design/task-scope-admission-gate.md`: Status 行、§10 の新設節、第一層（読み取り系・作業記録系・読み取り専用 git・計上規則・コードパス共有の範囲）、契約ライフサイクル第2項、D-S3-7 / D-S3-8 の項（起票 → 司令塔決定 → M1 exit gate で批准対象という出所が読める形へ改訂）。
- `docs/operations/adversarial-suite.md`: 新カテゴリ 4 件を「カバー済み」へ追加。「未カバー」から artifact-change の強制状態 replay を削除。
- `integrations/hermes-scope-gate/README.md`: 第一層の記述と限界節。
- `integrations/hermes-scope-gate/plugin_runtime.py`: per-turn の artifact-change policy 文面（許可される読み取り手段を明示。`log` が非許可であることと commit id の取得手段を含む）。

## 8. 本決定後も未解決の残余

- **commit 時点の index 内容と write scope の照合**（I-COR-10 / I-BYP-05。設計 §11 第9項の明示済み残余）。D-S3-7 の決定 4 点に含まれなかったため、帰属先を失ったまま残余として open。閉じる場合は admission 内で staged パス集合の照合が必要になる。`docs/operations/adversarial-suite.md` の「未カバー」に同じ扱いで記載している。

## 9. D-S3-7 実装の反証レビュー欠陥への処置（2026-08-23）

- 入力: `restricted-s3-impl-review-2026-08-23-d7-bypass.md`（I-DB-01〜08）、`restricted-s3-impl-review-2026-08-23-d7-correctness.md`（I-DC-01〜06）。
- ローカルテスト: 293 passed → **393 passed**（新規 100 パラメタ）。誤検知 0 件。
- いずれの処置も**決定文への適合化**である（両レビューが「決定文 3 への不適合」と判定）。設計判断の変更は含まない。ただし 1 の二分は I-DC-04 が「判断要」としたため、批准対象として設計本文へ出所を書いた。

### 1. 作業記録系カタログの段階別二分と縮小（I-DB-01 / I-DC-04 / I-DB-07 / I-DB-08）

13 名の一括許可を、注記系 6 名（全段）と run 終端シグナル系 2 名（locked 段のみ）に二分し、5 名をカタログ外へ出した。

- 注記系（`record-work-state`、全段で許可）: ボード参照、添付一覧、注記、心拍、blocked 記録、作業段階リスト。
- run 終端シグナル系（`signal-run-outcome`、locked 段のみ）: 完了記録、レビュー要求。契約が検証できていないターンは対象を確立していない。
- カタログ外（default deny for mutation → G3）: カード新規作成（INV-S6: blocker が新タスクになる経路）、レビュー差戻し記録（INV-S7: レビュアー側の権限）、リンク・パス添付・URL 添付（いずれも第一層が境界付けていない宛先を引数に運ぶ）。

**引数検査の新設は不要になった。** 宛先を運ぶツールをカタログ外へ出したため、残る許可対象は「引数によらず安全である」と言える形に閉じている。

ターン束縛を失った経路（`admit_without_turn`）は fail-closed のまま維持し、根拠の適用範囲を実装 docstring と設計本文へ明記した（未 lock 段で許可する根拠は「座礁したターンが自らの状態を記録できること」であり、記録対象のターンが無い経路へは届かない）。

回帰テスト: `test_work_record_tools_are_admitted_in_a_locked_turn`（カタログ全体を parametrize）、`test_run_signal_tools_are_admitted_in_a_locked_turn`、`test_run_signal_tools_are_denied_outside_a_locked_turn`（lock 前段・契約検証失敗段の双方。blocked 記録が同段で残ることも固定）、`test_the_work_record_catalogue_is_a_closed_explicit_set`（二分の非重複、除外 5 名が実ツール語彙に存在しかつカタログ外であること）、`test_tools_outside_the_work_record_catalogue_stay_denied`（**架空名を廃し、実在する近傍ツール 6 名で構成**）、`test_an_unbindable_call_cannot_record_work_state`。

### 2. 拒否計上の三分類（I-DB-02 / I-DB-03 / I-DB-05 / I-DC-01 / I-DC-02）

免除の粒度を subcommand 名から invocation 単位へ改めた。`artifact_git_read_refusal_action(subcommand, tail)` を追加し、許可された読み取り subcommand の拒否を三分類する。

1. 書込形の明示マーカー該当（`diff` の出力先指定・外部差分駆動、および読み取り形 allowlist 外のブランチ操作） → `git-write-form`（計上）。
2. ロック済み root の外を指す引数 → `git-read-unsafe`（計上）。判定はパス要素単位（`Path.parts`）。リビジョン範囲が `..` を演算子として運ぶため、文字列包含での判定は純粋な読み取りを逸脱と誤判定する。
3. それ以外（ロック済み root 内の純粋な読み取りで、引数形が allowlist 外） → `git-read-unbounded`（**免除、tool 予算へ**）。

分類は「既に拒否された呼び出しがどちらの予算を消費するか」だけを決める。いずれの分岐も何も許可しない。判定順は最も具体的な分類を先に置く（監査記録の意味が試行内容と一致するため。I-DB-05 の処置がこれに当たる）。

免除される subcommand 集合から、書込形を併せ持つ 2 族（リモート設定系、reflog 系）を除去した。認識外扱い（`git-subcommand`、計上）へ戻る。純粋な読み取りである `merge-base` を追加した（承認 metadata の base/head ancestry が用いる形）。

回帰テスト: `test_a_refused_read_is_classified_by_the_whole_invocation`（22 パラメタ。三分類それぞれの計数先を実測で固定）、`test_git_families_with_a_write_form_are_never_exempt`（5 パラメタ）、`test_no_write_form_of_an_admitted_read_reaches_the_exempt_lane`（25 パラメタ。**引数水準での閉集合検査**。短縮指定の束ね形・結合値形・両表記の境界外参照を含む）、`test_a_pure_read_inside_the_locked_root_stays_off_the_ceiling`（18 パラメタ。同じ閉鎖の反対側。リビジョン範囲 `..` / `...`、および書込マーカーの安全な類似指定を含む）、`test_the_read_only_git_subset_is_a_closed_set`（書込形を持つ subcommand が免除集合に不在であること、および admit 済みで書込形を持つ subcommand が読み取り形 allowlist を必ず持つことへ拡張）、`test_the_deny_ceiling_counts_only_boundary_deviations`（新理由コード 2 件を追加）、`test_uncounted_denials_stay_bounded_by_the_class_budget`（**免除される理由コードごとに有界性を固定**）。

### 3. §10 受入項目の整合（I-DB-04）

- 項目 15 の列に承認 metadata 収集手順を追加（base commit id、変更ファイル一覧、ステージ内容確認、head commit id、ブランチ同一性）。19 手順で拒否 0 件を固定。
- 項目 16 を「admit 済み subcommand の allowlist 外引数形」まで拡張し、さらに「必須手順が到達する拒否件数が拒否上限を超えても座礁しない」を明記。
- 項目 18 を新設: invocation から理由コードへの分類が両方向で正しいことを固定する義務。写像のみを固定すると分類の誤りが検出されずに残る。

回帰テスト: `test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling`（19 手順へ拡張）、`test_replay_the_worker_flow_survives_one_refused_read`（8 パラメタ。両類型を含む）、`test_repeated_refused_reads_do_not_strand_the_required_flow`（**上限を超える件数の必須読み取り拒否の後に、admit 範囲内の読み取り・write scope 内の書込・ステージ・コミットが成立することを固定**）。

### 4. 文書対応のみ（I-DB-06 / I-DC-03 / I-DC-05 / I-DC-06）

- 読み取りをロック済み worktree 内に留めている機構を「seed 検証が root を worktree top-level に固定していること＋git 自身のリポジトリ探索」と書き直した。workdir 束縛は単独では引数を境界付けない。本クラスの読み取り系ツールはパス検査を受けない（基準点から不変の既存残余）ことも明記した。
- `status` の引数境界が git 自身の pathspec 解決に依存する点を明記した。独自 allowlist の新設は共有実装の変更となり closeout の受入集合に影響するため行わない。
- per-turn policy 文面から "throughout" を外し、読み取り専用 git が lock 後のみであることと、拒否された読み取りが拒否上限を消費しないことを明示した。カタログ二分も文面へ反映した。
- 読み取り admission へのブランチ束縛引数を削除した（`_verification_action` の共有シグネチャは無変更）。admit 集合のいずれの subcommand も判定が束縛に依存しないことを `test_read_admission_does_not_consult_the_branch_binding`（12 パラメタ）で固定した。

### 5. 本ラウンド後の残余（司令塔判断）

- **承認 metadata の `git_dir` / `git_common_dir`（canonical Git 同一性）を契約内で取得する手段が無い。** 座礁は 2 の免除で解消した（試行は拒否されるが上限を消費しない）が、値そのものは取得できない。選択肢: (a) 割当 seed が値を供給する、(b) 承認ゲート側が worktree root から導出する、(c) 共有 allowlist を拡張して `rev-parse --git-dir` / `--git-common-dir` を admit する。(c) は D-S3-7 決定 1 の「共有実装を artifact-change のために拡張しない」に触れる。
- **本クラスの読み取り系ツール（`read_file` / `search_files`）がパス境界の検査を受けない。** 基準点から不変の既存残余であり本ラウンドの差分外。第一層の主張が「読み取りもロック済み root 内」を含むかは決定されていない。

## 10. 14 件の実地再判定と取り残しの処置（2026-08-23、9 節の続き）

9 節の処置は前任セッションがコミット `6d49aa0` で投入した直後にクレジット上限で中断したため、台帳の記載を鵜呑みにせず、14 件すべてをコードとテストで実地に再判定した。判定手段は (a) 該当コードの読解、(b) store 水準の end-to-end プローブ（`tmp/probe-d8/`、`tmp/probe-d9/`。git 管理外）、(c) 回帰テストの実行である。

- ローカルテスト: 393 passed（9 節時点）→ **427 passed**。新規 34 パラメタ。
- 結果: **12 件は `6d49aa0` で処置済みと確認**。**2 件（I-DC-01 / I-DB-03）は同一欠陥類型の取り残しが実測で残っており、本節で追加処置した**。誤検知 0 件。

### 1. 欠陥ID → 処置 → 回帰テスト（14 件全件）

`6d49aa0` で処置済みと確認したもの（実地判定の根拠を併記）:

- **I-DB-01 [blocker]** 作業記録系カテゴリの引数無検査書込 — 宛先を引数に運ぶツール（カード新規作成、リンク、パス添付、URL 添付、レビュー差戻し）をカタログ外へ出し、残余を段階別に二分。実測でカタログ外の 5 名がすべて `expansion-required` へ落ちることを確認。回帰テスト: `test_the_work_record_catalogue_is_a_closed_explicit_set` / `test_tools_outside_the_work_record_catalogue_stay_denied` / `test_work_record_tools_are_admitted_in_a_locked_turn`
- **I-DB-02 [blocker]** 承認 metadata の必須読み取りが拒否上限を枯渇させ座礁 — 免除粒度を invocation 単位へ。実測で必須手順 17 件の読み取り列が `denied_count == 0` で完走し、直後の write / stage / commit がすべて許可されることを確認（レビュー時の 6 件目座礁が反転）。回帰テスト: `test_repeated_refused_reads_do_not_strand_the_required_flow` / `test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling` / `test_a_pure_read_inside_the_locked_root_stays_off_the_ceiling`
- **I-DB-04 [major]** §10 受入項目が必須手順より狭い — 項目 15 の列に承認 metadata 収集を追加（19 手順）、項目 16 を admit 済み subcommand の allowlist 外引数形まで拡張、項目 18 を新設。回帰テスト: `test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling` / `test_replay_the_worker_flow_survives_one_refused_read` / `test_repeated_refused_reads_do_not_strand_the_required_flow`
- **I-DB-05 [minor]** ブランチ生成・削除形が読み取り系の理由コードで記録される — 判定順を最も具体的な分類から置き、当該形は書込形の理由コードへ。実測で確認。回帰テスト: `test_a_refused_read_is_classified_by_the_whole_invocation` / `test_no_write_form_of_an_admitted_read_reaches_the_exempt_lane`
- **I-DB-06 [minor]** 読み取りの確定根拠の記述誤り — 設計本文を「seed 検証が root を worktree top-level に固定していること＋git 自身のリポジトリ探索」へ書き直し、読み取り系ツールがパス検査を受けない点を既存残余として明記（設計 §11 の該当行を確認）。文書対応のみ。
- **I-DB-07 [minor]** 否定側の閉集合テストが架空のツール名で構成 — 実在する近傍ツール 6 名へ置換したことをテスト本文で確認。回帰テスト: `test_tools_outside_the_work_record_catalogue_stay_denied`
- **I-DB-08 [minor]** 座礁時記録の許可根拠がターン束縛喪失経路へ適用されていない — fail-closed を維持し、根拠の適用範囲を実装 docstring と設計本文へ明記。回帰テスト: `test_an_unbindable_call_cannot_record_work_state`
- **I-DC-02 [major]** 逸脱しえない読み取り拒否が上限を消費し座礁 — I-DB-02 と同一処置。実測で反転を確認。回帰テスト: I-DB-02 に同じ
- **I-DC-03 [minor]** admit 済み読み取り集合内の引数検査の非対称 — 実装は変更せず、引数境界が git 自身の pathspec 解決に依存する点を設計本文へ明記（該当行を確認）。共有実装への allowlist 新設は D-S3-7 決定 1 に触れるため行わない。文書対応のみ。
- **I-DC-04 [major, 判断要]** 契約検証失敗段で run 終端シグナルが許可される — run 終端シグナル系 2 名を locked 段限定とし、blocked 記録は同段に残した。実測で当該段が `seed-verification-failed` へ落ち、blocked 記録・注記が残ることを確認。回帰テスト: `test_run_signal_tools_are_denied_outside_a_locked_turn` / `test_run_signal_tools_are_admitted_in_a_locked_turn`
- **I-DC-05 [minor]** per-turn policy 文面が lock 前段の読み取りを誤解させる — 文面から当該語を除去し、読み取り専用 git が lock 後のみであることを明示（該当語の不在を確認）。文書対応のみ。
- **I-DC-06 [minor]** 読み取り admission への無効なブランチ束縛引数 — 引数を削除。回帰テスト: `test_read_admission_does_not_consult_the_branch_binding`

本節で追加処置したもの:

- **I-DC-01 [major] / I-DB-03 [major]** 計上免除カタログに書込形を持つ subcommand 族が含まれる — `6d49aa0` はリモート設定系と reflog 系の 2 族を免除集合から除去したが、**免除集合そのものの分類が subcommand 名のみで行われる経路が残っていた**（許可集合側だけが invocation 単位に改まっていた）。実測により、免除集合の member のうち diff 系オプションを受け取る 4 名が出力先指定で実際にファイルを作成し、うち 2 名は外部プログラム駆動の指定も受け取ることを確認した。当該形はいずれも拒否されるが免除側に落ち、write 境界の反復探索が拒否上限ではなく tool 予算でのみ有界になっていた。処置は 2 を参照。

### 2. 追加処置の内容

**(a) 免除集合にも invocation 単位の分類を適用した。** 三分類の判定を共通関数へ切り出し、許可集合と免除集合の双方が同じ判定を通るようにした。純粋な読み取りの場合の理由コードのみ集合ごとに異なる（既存の計上規則と audit 記録の意味を保つため、免除集合側の理由コード文字列は変更していない）。diff 系オプションを受け取る免除集合 member には書込指定の明示マーカーを宣言し、宣言漏れが免除の穴になるため当該 member にマーカーが存在することをテストで固定した。

**(b) 境界外判定をトークン内部へ拡張した。** パスはトークン全体であるとは限らないため、結合値（`--opt=<value>`）と単一ダッシュのフラグに詰めた形（`-X<value>`）の値部分も同じパス要素単位の判定にかける。リビジョン範囲が `..` を演算子として運ぶ形は従来どおり免除側に残る（false deny 側の対照テストで固定）。

いずれも**分類のみの変更であり、admission を一切広げない**。判定は artifact-change 専用の分類関数の内部にあり、closeout と共有するトークナイザ・境界付き pathspec 検査・検証用引数 allowlist には触れていないため、D-S3-7 決定 1（共有実装を artifact-change のために拡張しない）に抵触しない。closeout の計上規則も無変更（`test_closeout_deny_counting_is_unchanged` と `test_closeout_guards.py` が緑）。

副作用として、パスを含まない装飾的な結合値（出力接頭辞指定・相対表示指定など）は計上側へ移る。いずれも拒否済みの呼び出しであり、必須手順が用いない形であるため、設計が明記する「未分類は計上側」の方針と同方向の保守的な変化である。

回帰テスト（新規 34 パラメタ）:

- `test_a_write_form_under_a_recognized_read_name_is_never_exempt`（10 パラメタ。免除集合 member の書込形・外部プログラム駆動形・境界外読み取りが計上側に落ちることを固定）
- `test_a_pure_read_of_a_recognized_read_name_stays_exempt`（11 パラメタ。同じ閉鎖の反対側。必須手順が到達する形とリビジョン範囲を含む）
- `test_a_path_inside_a_joined_option_value_is_not_exempt`（5 パラメタ。許可集合・免除集合の双方について固定）
- `test_a_joined_value_without_a_path_stays_exempt`（6 パラメタ。束ね形・`key=value` 形が誤って計上側へ落ちないことを固定）
- `test_probing_a_write_form_under_a_recognized_read_name_exhausts_the_ceiling`（end-to-end。免除集合 member の書込形の反復が tool 予算ではなく拒否上限を枯渇させる）
- `test_a_recognized_read_still_does_not_strand_the_required_flow`（end-to-end。同 member の読み取り形は上限を超えても免除され、直後の write scope 内書込が成立する）
- `test_the_read_only_git_subset_is_a_closed_set`（拡張。マーカー宣言の網羅と、宣言先が認識集合の内側であることを固定。従来の宣言先の包含 assert は許可集合のみを見ており、免除集合 member について空振りしていた）

### 3. exit 条件の判定（M1 gate 前提）

- **I-COM-01 残余 — closed。** 必須手順が契約内で完結しない状態と、その後段（必須手順の拒否が拒否上限を枯渇させ admit 範囲内の呼び出しと write scope 内の書込まで予算拒否になる）の双方が解消した。実測で必須手順 17 件の読み取り列が拒否計上 0 件で完走し、直後の write / stage / commit が成立する。根拠: `test_repeated_refused_reads_do_not_strand_the_required_flow` / `test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling`。値そのものを契約内で取得できない 2 項は 4 の司令塔判断へ残す（座礁は解消済み）。
- **I-COM-06 — closed。** 構造面（読み取り専用 git の第一層追加、§10 受入項目 15〜18 の別立て、強制状態 replay、`push` の対象外明記）に加え、受入項目が必須手順全体と整合した。項目 15 は承認 metadata 収集を列に含む 19 手順、項目 16 は admit 済み subcommand の allowlist 外引数形と「拒否件数が上限を超えても座礁しない」を含む、項目 18 は分類の両方向を義務化し、本節でさらに「認識のみの集合も両方向で固定する」を追記した。既存項目 1〜14 は無改訂。
- **J-FID-01 — closed。** 計上規則の機構、理由コードから計数先への写像、免除経路のクラス予算による有界性に加え、**invocation から理由コードへの分類が両方向で正しいことを許可集合と免除集合の双方について固定した**。両方向の誤りはいずれも実測で反転を確認している: 書込形の種別（免除集合 member の出力先指定・外部プログラム駆動形、許可集合 member のブランチ操作形、トークン内部に運ばれた境界外パス）はすべて計上側、境界内の純粋な読み取り（承認 metadata の同一性読み取り、リビジョン範囲、束ね形・装飾的な `key=value` 形）はすべて免除側。9 節 2 の三分類が正本であり、本節はその適用範囲を免除集合と引数内部へ広げたものである。

### 4. 本ラウンド後の残余（司令塔判断）

9 節 5 の 2 項目をそのまま引き継ぐ。本節の処置で新たに増えた判断事項は無い。

- **承認 metadata の canonical Git 同一性（`git_dir` / `git_common_dir`）を契約内で取得する手段が無い。** 座礁は解消済み（試行は拒否されるが上限を消費しない）で、値そのものが取得できない。選択肢: (a) 割当 seed が値を供給する、(b) 承認ゲート側が worktree root から導出する、(c) 共有 allowlist を拡張して当該取得形を admit する。(c) は D-S3-7 決定 1 に触れる。
- **本クラスの読み取り系ツールがパス境界の検査を受けない。** 基準点から不変の既存残余。第一層の主張が「読み取りもロック済み root 内」を含むかは未決定。
