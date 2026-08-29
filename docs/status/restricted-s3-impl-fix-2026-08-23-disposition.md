# S3-M1 実装 反証レビュー 確証欠陥の処置台帳（2026-08-23）

- Status: closed（第1ラウンドの確証欠陥 37 件＝1〜6 節、司令塔判断 4 項目＝7 節、D-S3-7 実装の反証レビュー 14 件＝9〜10 節、V ラウンド 3 件＝11 節、V2 ラウンド 2 件＝12 節、V3 ラウンド 2 件＝13 節、W ラウンド 13 件＝14 節、w-verify ラウンド 4 件＝15 節、いずれも処置完了。exit 条件 3 件はすべて closed＝10 節 3、J-FID-01 は 11 節 6 で再判定・13 節 6 で維持。残余は 8 節の 1 項目、14 節 14 の批准・確認 4 項目、15 節 5 の 2 項目）
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
  - **解決済み（2026-08-23、司令塔決定 Judgment A）: (b) を採る。** 台帳へ書く値を申告値からゲート導出値へ差し替え、承認 metadata スキーマから当該 2 欄を外してスキーマ版を上げる（申告されていれば拒否）。digest は 2 欄を除いた実行主体作成オブジェクトに対して取り、ゲート側 augment は採らない。残余（承認 digest が worktree 同一性を覆わなくなる）と却下理由は設計文書「S3-M1 worker 配線」5 に記載。第一層の admission は無変更であり、当該取得形は引き続き拒否・非計上のままである。
- **本クラスの読み取り系ツールがパス境界の検査を受けない。** 基準点から不変の既存残余。第一層の主張が「読み取りもロック済み root 内」を含むかは未決定。
  - **解決済み（2026-08-23、司令塔決定 Judgment B）: 含まない。** 第一層の主張は write 境界（状態変更の側）に限ると主張文へ明記し、読み取り境界は第二層の M2 必須要件 1（隔離実行）へ併合した。併せて本残余を confidentiality の残余として write 境界の残余から分離して記載した（露出範囲はロック済み worktree 外の資産・他タスクの作業領域・セッション記録面）。M1 では引数水準の境界を新設しない（理由 4 点は設計文書「第二層」M2 必須要件 1 に記載）。M1 exit 時点では seed フラグ既定 off により当該露出は運用上発生しない。

## 11. final-verify の確証欠陥 3 件の処置（2026-08-23、10 節の続き）

- 入力: `docs/status/restricted-s3-impl-review-2026-08-23-final-verify.md`（`6d49aa0..d4e0030` の独立検証。確証欠陥 3 件 / 誤検知 0 件、J-FID-01 を not-closed と判定）。
- 対象: 分類・計上のみ。admission は不変（判定関数の戻り値は全分岐 `GateDecision(False, ...)` のまま）。closeout 共有実装は無改訂。
- 実装: `integrations/hermes-scope-gate/scope_gate.py`。テスト: `tests/test_artifact_change_scope.py`。
- 全数: **459 passed**（本節前 427。新規 32 パラメタ）。
- 再現確認: `tmp/fix-v01v03/probe.py`（git 管理外）で修正前に 18 形の誤分類を実測し、修正後に 0 とした。

### 1. V-01（major）実行境界を名指すオプションの宣言漏れ

- 症状: 免除集合 member `ls-remote` に `--upload-pack=<exec>` の宣言が無く、PATH 解決に委ねる相対プログラム名（および短縮綴り・束ね綴り）が `git-read-unadmitted` / `tool_count` へ落ちた。実行境界への逸脱試行が拒否上限（6）ではなく tool 予算（96）でのみ有界。
- 処置: `ARTIFACT_GIT_WRITE_FORM_MARKERS` に `ls-remote: {--upload-pack, --exec, -u}` を宣言。`--exec` はインストール済み Git が受理し、名指したプログラムを実際に transport へ渡すことを実測で確認（当該プログラムの出力に対する protocol error に到達する）。`-u` は当該 Git の parser が拒否するため実測不能で、受理する parser が経路を再開できないよう防御的に宣言した（マーカーの過剰宣言は既に拒否済みの呼び出しを上限側へ移すだけであり保守的側）。
- 汎化（本欠陥の教訓）: **宣言義務を認識集合の全 member へ課した。** マーカー表とパスオプション表を認識集合（許可集合 ∪ 免除集合、12 member）上の**全域写像**とし、空 frozenset を「監査済み・宣言すべきものなし」の明示とした。従来の不変条件は宣言義務を diff 系の列挙に対してのみ課しており、監査されていない族は緑のまま原理的に検出されなかった。`test_the_read_only_git_subset_is_a_closed_set` を両表の**集合等価**（`<=` ではない）＋非空虚性 assert へ拡張し、認識集合へ member を加えて宣言を欠くと落ちる形にした。フェンス実効性は宣言エントリを空へ戻して実測（実行境界形 6/7 パラメタ＋不変条件が落ちる）。
- 検討して採らなかった選択: 検証所見 (c) の「`ls-remote` を免除集合から外して認識外扱いへ戻す」。純粋な読み取り形も計上側へ移るため false deny 側の変化を伴い、かつ本タスクが求める宣言義務の汎化は別途必要なため、宣言による処置を採った。

### 2. V-02（minor）束ねたフラグ末尾の値取り形

- 症状: 単一ダッシュのトークンについて値候補を `token[2:]` に固定していたため、値のない短縮フラグを前置した形（値の開始が 3 文字目以降）が境界外判定を素通りした。read 境界の反復探索が tool 予算でのみ有界。
- 処置: 値の抽出を `_git_token_invokes_option` に集約し、bare / `--opt=<v>` / `-X<v>` / 束ね末尾 `-abX<v>` の 4 綴りを同一規則で扱う。束ねの走査は「フラグ文字でない最初の文字」で打ち切り、他オプションの値に含まれる文字を束ねオプションと誤認しない（false deny 方向の抑制）。同じ helper をマーカー照合にも用いたため、V-01 の短縮・束ね綴りも同時に覆う。

### 3. V-03（major）値がパスに見える純粋な読み取りの誤計上（`d4e0030` が導入した回帰）

- 症状: 結合値・束ね形の値部分を**オプション名を見ずに一律**パス候補化したため、検索パターン・pickaxe・書式文字列・表示接頭辞・行帰属の行範囲（正規表現形）が `git-read-unsafe` / `denied_count` へ落ち、6 形で `denied_count == 6` に達して直後の write scope 内書込と admit 範囲内読み取りが `deny-budget` になった（I-DC-02 の終状態と同一）。
- 処置: 値部分をパス候補とするのは**パスを取ると宣言したオプションに限る**（`ARTIFACT_GIT_PATH_OPTIONS`、subcommand 単位の明示列挙）。宣言した綴りはすべて、絶対値を与えた invocation がオプション解析ではなくファイル open に到達すること（当該パスを名指す read failure）をインストール済み Git で確認した。書込側の出力先指定は表に含めない（マーカーで先に分類されるため）。
- **表を綴り単位ではなく subcommand 単位にした理由（実装上の必然）**: 同一綴りが member によって意味を変える。行帰属系ではリビジョン **file** を取るが、履歴系では pickaxe **文字列**であり、パスに見える値を履歴から探す通常形である。綴り単位の単一表は必ずどちらかの方向を誤る（履歴系の通常検索を再度計上側へ戻すか、行帰属系のファイル読みを免除側に残すか）。`test_a_path_option_is_declared_per_subcommand_not_by_spelling` で両方向を固定。
- 汎化（本欠陥の教訓）: false deny 側のガードに**値にパス区切りを含む正当な形**を追加した。従来の `test_a_joined_value_without_a_path_stays_exempt` の 6 パラメタはいずれも値にパス区切りを含まない形であり、回帰が住む区画を通っていなかった。新設 `test_a_value_that_only_looks_like_a_path_stays_exempt`（14 パラメタ）は検索パターン・pickaxe・書式文字列・表示接頭辞・行範囲正規表現を含む。
- **10 節 2 の自己評価の訂正**: 同節は本副作用を「パスを含まない装飾的な結合値（出力接頭辞指定・相対表示指定など）が計上側へ移る」「未分類は計上側の方針と同方向の保守的な変化」と記述したが、実測は 2 点で異なる。(a) 計上側へ移ったのは**値がパスに見える**形であり、パスを含まない装飾的結合値は移っていない（記述が逆）。(b) 境界内の純粋な読み取りを計上するのは保守的側ではなく **false deny 側（ターン座礁側）** である。「未分類は計上側」は*認識できない拒否理由*についての規則であり、境界内の純粋な読み取りには適用されない。受入項目 18 が両方向を義務化したのはこの非対称性のためである。本訂正を以て 10 節 2 の当該記述は無効とする。

### 4. 回帰テスト（新規 32 パラメタ、既存 1 件を拡張）

- `test_an_execution_form_under_a_recognized_read_name_is_never_exempt`（7。長形・synonym・結合短縮・分離・束ね綴り・絶対プログラムパス）
- `test_a_path_packed_onto_a_flag_bundle_is_not_exempt`(7。許可集合・免除集合の双方、行帰属系と索引列挙系を含む)
- `test_a_value_that_only_looks_like_a_path_stays_exempt`（14。V-03 の false deny 区画）
- `test_a_path_option_is_declared_per_subcommand_not_by_spelling`（1。綴り衝突の両方向）
- `test_a_read_whose_value_looks_like_a_path_does_not_strand_the_turn`（1。end-to-end。上限+2 反復で `denied_count == 0`、直後の write scope 内書込と admit 範囲内読み取りが成立）
- `test_probing_a_newly_classified_boundary_exhausts_the_ceiling`（2。end-to-end。実行境界形・束ね形パスの反復が `deny-budget` に到達）
- `test_the_read_only_git_subset_is_a_closed_set`（拡張。両表の全域性・非空虚性・diff 系と `ls-remote` の非空宣言）

フェンス実効性は修正前ロジック（`_git_token_path_candidates` / `_git_token_matches_marker` を `d4e0030` 相当へ戻す）に対して新規テストを実行し、25 失敗を確認した。

### 5. 併せて更新した文書

- `docs/design/task-scope-admission-gate.md`（正本）: §11 三分類の項 1 に「トークン内部の値をパス候補とするのはパスを取ると宣言したオプションに限る」「束ね末尾の値取り形を含む」を追記し、V-03 をそのまま散文で述べていた「オプション名が何であれ」の一文を削除。同 §11 の「集合への所属それ自体は免除ではない」項に、書込境界以外の境界（実行境界）を引数で名指す形と、**宣言義務を認識集合の全 member へ課す全域写像**の要求を追記。§10 受入項目 18 に束ね形と「値にパス区切りを含む正当な形での免除側固定」「宣言表の全域性自体を固定する」を追記。決定文の変更は無い。
- `docs/operations/adversarial-suite.md`: 新規迂回 3 類型（束ね末尾の値取り形 / 値の意味を見ない一律パス候補化による座礁 / 認識集合における宣言義務の欠落）を抽象名＋テスト所在で追記。

### 6. exit 条件の判定

- **J-FID-01 — closed（再判定）。** final-verify が挙げた両方向の反例がいずれも反転した。計上側であるべきもの（実行境界を名指すオプション＝V-01、束ね末尾の値取り形＝V-02）は `denied_count`、免除側であるべきもの（値がパスに見える純粋な読み取り＝V-03）は `tool_count`。分類の**網羅**の担保手段として、宣言表の全域性を不変条件に格上げした（宣言漏れが原理的に検出されない構造を除去）。end-to-end で両方向の予算挙動を固定済み。
- I-COM-01 残余 / I-COM-06: 10 節 3 の判定を変更しない（本節は分類の網羅のみを変更し、必須手順の到達性は不変）。

### 7. 本ラウンド後の残余（司令塔判断）

10 節 4 の 2 項目をそのまま引き継ぐ。本節で新たに増えた判断事項は無い。V-01〜V-03 はいずれも実装の網羅の問題であり、設計判断を要さなかった（処置はすべて既存の明示列挙機構の内側に収まり、admission を広げていない）。

残余として記録する既知の限界（設計判断は要さない）: 束ね走査の打ち切り規則は「フラグ文字でない最初の文字」までの走査であり、宣言済み短縮綴りの文字が他オプションの**英数字のみで構成される値**の内部に現れ、かつその後続がパス形である場合には計上側へ落ちうる。既に拒否済みの呼び出しの計数先が変わるだけで、方向は計上側（保守的側）である。

## 12. V2 ラウンドの確証欠陥 2 件の処置と D-S3-7 補則の実装（2026-08-23、11 節の続き）

- 入力: `docs/status/restricted-s3-impl-review-2026-08-23-final-verify.md` の V2 ラウンド節（`240d859` の独立検証。確証欠陥 2 件 / 誤検知 0 件）。
- 処置の分類: **設計改訂による解消**。V2-01 / V2-02 は誤検知ではなく、検査時点で有効な確証欠陥である。個別の網羅漏れを塞ぐ 4 巡目の修正は行わず、司令塔決定（D-S3-7 補則）により計上規則そのものを改訂して欠陥の成立条件を除去した。
- 対象: 計上規則と理由コードの帰属。**admission は無変更**（許可集合・判定関数・closeout 共有実装のいずれも変更なし）。
- 実装: `integrations/hermes-scope-gate/scope_gate.py`。テスト: `tests/test_artifact_change_scope.py`。
- 全数: **502 passed**（本節前 459。新規 43 パラメタ、既存 20 件を改訂基準へ更新、旧基準と矛盾する 2 件を置換）。

### 1. 改訂に至った判断

3 巡（D7 ラウンド → V ラウンド → V2 ラウンド）で確証された欠陥は、いずれも「terminal 引数の綴りを並行列挙して逸脱か否かを両方向に分類する」機構の網羅漏れであった。11 節 6 は網羅の担保手段として宣言表の全域性を不変条件へ格上げしたが、V2 ラウンドの独立検証はその担保の限界を明示した。全域性は「どの member が宣言するか」を閉じるが、「宣言が対象コマンドの受け付ける全綴りに効くか」は閉じない。検証者の指摘は「開放的な引数空間の双方向分類は列挙では原理的に閉じない」であり、これは実装の努力量ではなく機構の構造に対する指摘である。

したがって 4 巡目として個別の綴りを追加するのではなく、**分類の正しさが安全性・可用性のいずれにも影響しない構造へ移す**ことを選んだ。詳細は正本設計の D-S3-7 補則。

### 2. V2-01（major）宣言済み境界オプションの照合における綴り正規化の不足

- 検査時点の症状: 宣言済みの境界オプションについて、対象コマンドが受理する一部の綴り形が照合を素通りし、計上側であるべき invocation が免除側へ落ちた。実行境界・読み取り境界の双方に成立し、うち一部は前差分が捕捉していた区画を失った退行であった。
- 処置: **設計改訂による解消。** 補則により、当該分類段の拒否は計上対象から外れた。綴り正規化の網羅は計上先を変えないため、この欠陥の成立条件（計上先の誤り）が消滅した。
- **admission 側の確認（検証者確認済み）**: 本欠陥の逸脱形はすべて admission では拒否のまま（`allowed is False`）である。誤っていたのは予算の帰属のみで、許可は広がっていない。したがって改訂後も、これらの invocation が通るようになることはない。
- 残る性質: 綴り正規化の網羅漏れは audit ラベルの精度の問題として残る。監査記録上、境界形の refusal が読み取り refusal として記録されうる。admission の判定と予算の帰属には影響しない。

### 3. V2-02（minor）境界に届かないオプションの過剰宣言による純粋読み取りの誤計上と座礁

- 検査時点の症状: パスを開かないオプションをパスオプションとして宣言したため、純粋な読み取りが計上側へ落ち、上限回数の反復でターンが座礁した。
- 処置: **設計改訂による解消。** 補則により既定が非計上となったため、過剰宣言によって純粋な読み取りが計上側へ落ちる経路が消滅した。座礁は原理的に成立しなくなった（当該段の拒否は計上ゼロ）。
- 固定: `test_no_classification_label_can_strand_the_required_flow`（4 パラメタ）。分類器が 4 ラベルのいずれを付けた場合でも、上限+2 反復の後に write scope 内書込とステージが成立し `denied_count == 0` であることを固定する。ラベルの正しさに依存しない形で座礁不成立を固定した点が、従来の固定との違いである。

### 4. 実装の変更点

1. **計上規則の反転**: 免除集合（既定は計上）を廃し、計上集合 `ARTIFACT_DEVIATION_DENY_ACTIONS`（有限の文字列リテラル集合、**24 メンバー**）を新設した。（当初「25 メンバー」と記載していたが実測 24 の誤記であった。V3-01 として 13 節で処置。同節で 22 メンバーへ縮小している。）`artifact_deny_counter` の既定を `tool_count` へ反転した。集合の帰属規則は「その理由コードを受け取りうる invocation が、admission が自ら決める事実だけで write / 実行境界への試行と断定できること」＝「実際には scope 内の純粋な読み取りである呼び出しが到達しえないこと」。
2. **分類表の降格**: 分類表・分類関数（`ARTIFACT_GIT_WRITE_FORM_MARKERS` / `ARTIFACT_GIT_PATH_OPTIONS` / `ARTIFACT_GIT_READ_FORM_FLAGS` / `_artifact_git_deviation_action` 等）は削除せず audit 帰属専用へ降格した。削除すると監査粒度を失い、ラベルの回帰テストを書き換える必要が生じるだけで得が無い。各表のヘッダコメントに「audit attribution only」および「計上先を変えない」を明記し、旧根拠（計上先に関する記述）を除去した。`ARTIFACT_GIT_READ_FORM_FLAGS` のみは admission に対して load-bearing のままである（`branch` の書込形を読み取りとして admit させない allowlist）ことを明記した。
3. **理由コードの一意化**: terminal の workdir 検査 3 件を `target-missing` / `target-traversal` / `target-closed` から `workdir-missing` / `workdir-traversal` / `workdir-outside` へ改めた。理由: workdir 検査はコマンドの字句解析より前に行われ、純粋な読み取りも到達する（例: 読み取り subcommand を worktree 外の workdir で呼ぶ形）。write 対象のパス検査と綴りを共有したままでは、コードから計数先への写像が健全にならず、write 対象が root 外へ出る確定判定を計上側に置けない。分離により当該 3 コードは非計上、write 対象のパス検査由来のコードは計上側となった。
4. 計上判定は分類表を参照しない。静的に固定した（下記 5 の 3 層）。

補則の例示のうち計上集合に対応コードを持たないものと、写像を経由しない計上箇所を、監査の便のため明記する。

- **「lock 超過宣言」に対応する計上コードは無い。** 宣言 scope が seed を超える場合と scope パターンがロック済み root 外へ解決する場合の拒否は、`lock_turn`（ストア API）が例外として送出する。per-call の admission 経路を通らないため `GateDecision` を生成せず、`artifact_deny_counter` にも到達しない。計上規則の対象外であり、集合の欠落ではない。
- **`hook-argument-drift` は写像を経由せず直接 `denied_count` を加算する。** 同一の tool-call id が異なる引数で再到達した場合の拒否で、冪等性ガードの位置（admission 判定の前）にある。クラス非依存で、本補則より前から存在する。ゲート自身が記録した fingerprint の比較という確定判定であり補則の原理と整合するが、写像された集合のメンバーではない。純粋な読み取りの呼び出し id を引数を変えて再送する形も到達しうるため、帰属規則の litmus に厳密には合わない。既存挙動を変えないことを選んだ（下記 7 の 4 項目目）。

### 5. 回帰テスト（新規 43 パラメタ、既存 20 件を改訂基準へ更新）

新規:
- `test_the_counting_set_is_exactly_the_ratified_enumeration`（1。計上集合の同値性。実装から導出せずテスト側に正本列挙を持ち、集合の増減を意図的な二箇所編集に限定する）
- `test_every_definitive_determination_charges_the_deny_ceiling`（**24**。計上集合の**全数**。13 節の縮小後は 22）
- `test_a_budget_denial_consumes_no_counter`（3。予算枯渇由来はいずれの計数も消費しない）
- `test_a_denial_that_is_not_a_definitive_determination_spends_tool_budget`（18。非計上側。分類ラベル 4 件と、純粋な読み取りが到達する経路 14 件）
- `test_an_unclassified_denial_does_not_charge_the_deny_ceiling`（1。既定の極性反転）
- `test_the_counting_rule_does_not_consume_the_argument_classification`（1。静的独立性 第1層。計上関数の `co_names` が分類表・分類関数の識別子を含まない）
- `test_no_classification_label_can_reach_the_deny_ceiling`（1。静的独立性 第2層。分類器の値域を理由文表から導出し、計上集合と交わらないことを固定。第1層のみでは「表から構築した集合を参照する」形を捕捉できない）
- `test_an_uncounted_denial_lane_is_closed_by_the_tool_budget`（5。end-to-end。非計上の 5 レーンについて tool 予算まで反復し、`denied_count == 0`・tool 予算で閉鎖・閉鎖が拒否であって fail-open でないことを固定）
- `test_no_classification_label_can_strand_the_required_flow`（4。上記 3 節）
- `test_the_idempotence_guard_charges_the_ceiling_outside_the_mapping`（1。写像を経由しない唯一の計上箇所を両方向に固定。上記 4 節の 2 点目）

更新（旧項目18 前提から改訂基準へ）:
- 分類の両方向を計上先で固定していた 8 件（`test_no_write_form_of_an_admitted_read_reaches_the_exempt_lane` 他）は、**audit ラベルの固定**へ改めた。ラベル assert は維持し、計上 assert を `tool_count` へ統一した。テスト名の "exempt" 語彙を "labelled" 系へ改めた（免除／計上の対比が計上規則の記述ではなくなったため）。
- `test_a_refused_read_is_classified_by_the_whole_invocation`（11 パラメタ）: ラベルは維持、計上分岐を削除し `denied_count == 0` へ統一。
- `test_git_families_with_a_write_form_are_never_exempt` → `..._are_not_recognized_as_reads`: 認識外 subcommand コードが非計上であることへ更新。
- `test_unrecognized_git_subcommands_still_count_as_deviations` → `..._are_denied_and_bounded_by_tool_budget`: 同上。admission は不変（拒否のまま）。
- `test_probing_a_newly_classified_boundary_exhausts_the_ceiling` / `test_probing_a_write_form_under_a_recognized_read_name_exhausts_the_ceiling`: 削除し、上記 `test_an_uncounted_denial_lane_is_closed_by_the_tool_budget` へ置換した。旧テストは分類段の拒否が拒否上限を枯渇させることを固定していたため、改訂基準と直接矛盾する。
- workdir コード改称に伴う 2 件（`test_terminal_work_outside_the_locked_worktree_is_denied` / `test_read_only_git_reads_outside_the_locked_worktree_are_denied`）を新コードへ更新。

新規テストは 43 パラメタ。更新理由は本節に記録し、テスト内コメントには改訂の経緯を書いていない（コメントは当該テストが何を固定するかのみを述べる）。

### 6. 併せて更新した文書

- `docs/design/task-scope-admission-gate.md`（正本）: Status 行に補則を追記。§11「第一層」の計上規則を確定判定由来へ書き換え（確定判定の定義、有限明示集合と既定非計上、分類表非参照、理由コード一意性の要求）。D-S3-7 の決定項へ「補則」を経緯・3 要点・安全目的の担保付きで追記。§10 受入項目 18 を「改訂（2026-08-23、D-S3-7 補則）」として出所を残して書き換え（固定対象 4 点＋改訂理由 3 点）。契約ライフサイクル節の「lock 未了」の計上に関する記述を補則と整合させた。
- `docs/operations/adversarial-suite.md`: 分類機構の位置付け変更を反映（下記）。

### 7. 本ラウンド後の残余（司令塔判断）

10 節 4 の 2 項目をそのまま引き継ぐ。本節で新たに増えた判断事項として次の 3 点を挙げる（いずれも admission を広げず、非計上側＝クラス予算で有界な側への帰属である）。

1. **認識外 subcommand / 認識外ツールの拒否が非計上になった。** 理由コード（`git-subcommand` / `expansion-required`）は、純粋な読み取りである呼び出しも到達しうるため確定判定に当たらない。結果として、これらの反復探索は tool 予算（96）で有界となり拒否上限（6）では有界でない。押し出し系（`push` 等）は本クラスでは認識外 subcommand としてこの経路に入る。admission は全て拒否のままである。
2. **terminal workdir がロック済み worktree 外である拒否が非計上になった。** workdir 検査が字句解析より前に位置するため、同一コードに純粋な読み取りと書込試行の双方が到達する。admission の順序は変更していない（補則は admission 無変更を要求する）。順序を変えずに計上へ戻すには、字句解析後に workdir を再判定する構造変更が必要である。
3. **ステージ・コミットの引数形拒否を計上側に置いた。** `stage-option` / `stage-unbounded` / `stage-magic` / `stage-directory` / `commit-unsafe` / `commit-rewrite` は、解決済みの境界越えを証明するコードではないが、当該レーンへ到達するのは `git add` / `git commit` のみであり、純粋な読み取りは到達しえない。同じ理由で実行テンプレート不一致系（`execution-template` / `execution-option` / `execution-stdin` / `execution-target`）も計上側に置いた。保守的側の選択が逆（非計上）である解釈も成立するため、批准時に確認を要する。
4. **`hook-argument-drift` の計上を写像の外に残した。** 上記 4 節のとおり、冪等性ガードの位置で直接 `denied_count` を加算する既存経路であり、クラス非依存である。帰属規則の litmus に厳密には合わない（純粋な読み取りの呼び出し id を引数を変えて再送する形も到達しうる）が、これはフック protocol の整合性ガードであり、非計上へ移すと改竄側の反復が拒否上限で有界でなくなる。既存挙動の保持を選んだ。写像へ取り込むか、litmus に合わせて非計上とするかは批准時の判断とする。

---

## 13. V3 ラウンドの確証欠陥 2 件の処置と計上帰属の司令塔決定（2026-08-23、12 節の続き）

- 入力: `docs/status/restricted-s3-impl-review-2026-08-23-final-verify.md` の V3 ラウンド節（`240d859..17b236b` の独立検証。確証欠陥 2 件 / 誤検知 0 件、いずれも minor）。
- 前提: 同検証は J-FID-01 を closed と判定し、I-COM-01 / I-COM-06 の退行なしを確認している。本節の処置対象は残る 2 件である。
- 全数: **506 passed**（本節前 502。新規 4 パラメタ、既存 2 件を改訂）。
- 検証者記録（final-verify）は本節で書き換えていない。検証者の推奨（V3-02 の修正形 (a)）と司令塔決定（部分的に (b) を採用）の差は本節で明示する。

### 1. 司令塔決定（2026-08-23、D-S3-7 補則の帰属確定）

補則の初版は計上帰属規則を二通りに書いており（レーン別の確定事実の列挙と、読み取りが到達しうるかを問う litmus）、両者は「同値な言い方」とされていたが実行レーンで乖離していた。決定は次のとおり。

- **litmus を唯一の規範とする**: 「純粋な読み取り目的の呼び出しが到達しうる理由コードは拒否上限に計上しない」。レーン別の確定事実は litmus の適用結果として位置づけ、食い違う場合は列挙側を誤りとする。
- 個別帰属の確定:
  1. 認識外 subcommand・認識外ツールの拒否 = **非計上**（批准。admission は拒否のままで tool 予算で有界）。
  2. terminal workdir がロック済み worktree 外の拒否 = **非計上**（批准）。字句解析後の workdir 再判定は M2 検討残余として設計へ記録した。
  3. ステージ・コミットの引数形拒否 = **計上維持**（純粋読み取りは到達しない）。**実行テンプレート不一致系 = 非計上へ変更**（V3-02 の実測による）。
  4. 冪等性ガードの直接計上 = **維持**。litmus の明示例外として設計へ記載した。

12 節 7 の司令塔判断 4 項目のうち、1 / 2 / 4 は上記のとおり批准され、3 は実行テンプレート不一致系についてのみ変更された。当該 4 項目は本決定により解決済みとして閉じる。

### 2. V3-01（minor）計上集合の要素数の誤記

- 指摘: 台帳 12 節 4 項目 1 と 12 節 5 が計上集合を「25 メンバー」、全数テストを「25」と記載していたが実測は 24 である。併せて 12 節 5 の見出し「新規 42 パラメタ」と同節末尾「新規テストは 43 パラメタ」が食い違っていた。
- 処置: 台帳のみの修正。12 節 4 項目 1 を 24 へ（誤記であった旨と本節での縮小への参照を併記）、12 節 5 の全数テストを 24 へ、見出しを 43 へ改めた。実装と正本列挙は当初から一致していたため実装変更は無い。
- 11 節 4 の「25 失敗」はフェンス実効性検査の失敗件数であり別の 25 である。混同を避けるため変更していない。

### 3. V3-02（minor）計上帰属規則の二重定式化と実行レーンでの乖離

- 指摘: §11 の列挙型は「コマンドが git 以外のプログラム起動であること」を確定事実に数えており、litmus 型の「純粋な読み取りが到達しうるコードは計上しない」と実行レーンで一致しない。実装は列挙型を採っていたため、ロック済み worktree 内・write scope 内のファイルを terminal 経由で読む呼び出しが上限を消費し、6 回で座礁して以後は無条件に許可される読み取りツールまで `deny-budget` となった（検証者の実測）。
- 処置: 司令塔決定に従い、設計を litmus の単一定式化へ統一し、実装側で実行テンプレート**不一致**系を計上集合から外した。
- **確定点の言い換え（実行レーン）**: 確定事実は「コマンドが git 以外のプログラム起動であること」ではなく「**コマンドが opt-in 済み実行テンプレートの起動形に一致すること**」である。一致した時点でその invocation は呼び出しの目的を問わず実行境界への行為として確定する（契約自身の opt-in がそのプログラムを名指しているため）。一致しない拒否はレーンを確定しない。
- 実装の変更: `ARTIFACT_DEVIATION_DENY_ACTIONS` から `execution-not-opted-in` / `execution-template` を除いた（**24 → 22 メンバー**）。一致後の引数形の拒否（`execution-option` / `execution-stdin` / `execution-target`）は計上のまま維持した。とくに `execution-target` は scope パターン照合に依存して値が決まるため、非計上へ移すと write scope 内容の探索が tool 予算（96）でのみ有界になる。ステージ・コミット系（`stage-*` / `commit-*`）も同じ理由で計上のまま維持した。
- **一方向性の確認**: 変更は計上 → 非計上の 2 件のみであり、非計上 → 計上はゼロである（変更前の集合が変更後の集合を真に包含する）。admission は無変更で、`_admit_artifact_change_execution` を含む admission 関数に手を入れていない。両コードを発行する既存の admission テスト（`test_execution_is_denied_entirely_without_an_opt_in` ほか）は無改訂で緑であり、これが admission 不変の証人である。

### 4. 設計文書の統一（V3-02 の処置に含む）

litmus を唯一の規範へ格上げした結果、指摘箇所（§11 の確定判定の定義）以外にも旧極性の記述が残っていたため同時に掃いた。いずれも文言のみで、admission・計上ともに挙動は変わらない（設計修正の前後でテストは 506 passed のまま）。

- §11 計上規則（指摘箇所）: litmus を規範として単独提示し、レーン別確定事実 5 点をその適用結果として従属させた。第 3 項を「opt-in 済み実行テンプレートの起動形への一致」へ改め、実行レーンの確定点・不一致の非計上・認識外の非計上・字句解析前の非計上を各々明文化した。集合の縮小と拡大の意味の違い（適用誤りの修正か、新たな確定事実の主張か）を追記した。
- §11 冪等性ガード: litmus の**唯一の**明示例外として位置づけ、他コードへ例外を広げない旨を追記した。
- §11 三分類（旧極性が残っていた第三の定式化。検証者の指摘外）: 本段が決めるのは audit 帰属ラベルと（許可読み取り subcommand の）引数形 admission であり予算は決めない旨を前置し、各分類の「→ 計上 / → 計上しない」を境界側ラベル / 読み取り側ラベルへ retag した。「未分類の拒否理由は計上する」の一文（補則の既定非計上と正面から矛盾）を削除した。分類の実質（パス候補の宣言義務、書込マーカー表、読み取り形 allowlist、ネットワーク読み取り系の除外、全域性の義務）は既存テストが固定しているため一切変更していない。`ARTIFACT_GIT_READ_FORM_FLAGS` が admission に load-bearing である旨は当該箇所へ明記した。
- §10 受入項目 18: 固定対象の第 2 点へ、レーン未確定の拒否（実行テンプレート不一致）についても座礁ゼロを固定する要求を追記した。
- D-S3-7 の決定項: 「補則の定式化統一と帰属確定」を司令塔決定として追記（経緯、litmus 単一化、個別帰属 1〜4、一方向性と admission 無変更）。
- 掃き出し後、`計上` / `免除` の全出現を litmus に照らして確認した。旧極性の記述は残っていない（残る `免除` は経緯記述、`test_paths` の非免除、M2 分岐の免除であり計上規則とは無関係）。

### 5. 回帰テスト（新規 4 パラメタ、既存 2 件を改訂）

新規:
- `test_a_terminal_read_that_matches_no_template_does_not_strand_the_turn`（2。V3-02 が実測した座礁の解消。opt-in の無い契約と opt-in 済みで不一致の契約の双方で、テンプレートに一致しない読み取り目的の terminal 呼び出しを上限超まで反復した後に、読み取りツール・許可読み取り subcommand・write scope 内の書込・ステージがすべて成立し `denied_count == 0` であることを固定する）
- `test_uncounted_denials_stay_bounded_by_the_class_budget`（既存 2 → 4。新たに非計上となった 2 レーンについて tool 予算での有界性と閉鎖が拒否であることを追加）

改訂:
- `test_every_definitive_determination_charges_the_deny_ceiling`（24 → 22。正本列挙 `_EXPECTED_DEVIATION_DENY_ACTIONS` の縮小に追従）
- `test_a_denial_that_is_not_a_definitive_determination_spends_tool_budget`（18 → 20。除いた 2 コードを非計上側の列挙へ移した）

フェンス実効性は、計上集合へ当該 2 コードを一時的に戻して新規・改訂テストを実行し、7 失敗を確認した。うち座礁テストは 2 変種とも 7 回目の呼び出しで `deny-budget` に落ちて失敗し、検証者が報告した終状態を再現した。

### 6. exit 条件の判定

- **J-FID-01**: 検証者の判定（closed）を維持する。本節の処置は計上機構ではなく計上集合の要素選択とその記述であり、機構側の不変条件（既定非計上、分類表非参照、値域との非交差、計上箇所 2 か所）はいずれも変更していない。
- **I-COM-01 / I-COM-06**: closed 維持。必須手順は実行テンプレート不一致系に到達しないため座礁の解消は必須手順の判定を変えないが、読み取り目的の terminal 呼び出しを含むターンの可用性は改善する。
- 境界（admission）の無変更は 3 節のとおり。

### 7. 本ラウンド後の残余（司令塔判断）

10 節 4 の 2 項目は、いずれも 2026-08-23 の司令塔決定（Judgment A / Judgment B）で閉じた（10 節 4 に解決内容を追記済み）。12 節 7 の 4 項目は本節 1 の決定により閉じた。本節で新たに増えた判断事項は次の 1 点である。

1. **実行テンプレート不一致系の非計上により、実行境界への反復試行のうち「起動形に一致しない形」が tool 予算（96）でのみ有界となった。** 一致後の引数形は拒否上限（6）で有界のまま、admission は全形で拒否のままである。認識外 subcommand・認識外ツールの非計上（本節 1 の帰属 1）と同じ性質の緩和であり、litmus の適用として一貫している。M1 exit gate では、この緩和の受容が帰属 1 の批准と同一の判断であることを確認事項とする。

## 14. W ラウンド（worker 配線 `f7cfe0f`）の確証欠陥の処置（2026-08-23、13 節の続き）

対象レビュー: `restricted-s3-impl-review-2026-08-23-w-bypass.md`（W-B-01〜07）、`restricted-s3-impl-review-2026-08-23-w-correctness.md`（W-C-01〜06）。**本節は取扱制限。迂回の具体形へ言及する。**

### 1. W-B-02（blocker）許可済み書込からのリポジトリ解決の乗っ取り

再現を再確認した。第一層が許可する worktree 内のファイル書込のみで、ロック済み root からの Git リポジトリ探索を agent 作成物へ向け替えられ、契約が admit する Git 書込動作がフック経路で任意実行に至る。破られる性質はレビュー記載どおり 5 点（第二層の既定閉鎖、契約の禁止項、第一層の書込上限、`--no-verify` 拒否によりフック実行が「強制」であること、README の探索前提）。

処置は 2 系統の独立した検査である。

1. **書込形の carve-out（クラス局所）**: ロック済み root への相対パスに `.git` セグメントを含む書込先・ステージ対象を、`write_paths` の幅によらず拒否する。`_admit_artifact_change_locked` の write カタログ分岐と `_artifact_stage_targets` に置き、共有のパス正規化・pathspec 実装は変更していない（D-S3-7 決定 1）。パターン照合より**前**に判定するため、宣言の幅が結論を変えない。
2. **解決先の封じ込め（書込形と独立）**: `add` / `commit` の admission 直前に、ロック済み root から解決した git-dir / git-common-dir が root 配下に入らないことを検査する（root 直下の `.git` 自身は通常リポジトリ形として名指しで許容）。linked worktree は両者が primary repository へ解決するため本番形に false deny を追加しない。1 の carve-out だけでは「別経路で解決先が変わった場合」を覆えないため独立に持つ。

Judgment A 側（承認ゲート）へも同じ封じ込めを課した。`verify_workspace` は解決先が workspace 配下に入る構成をエラーとし、`identities` を `None` のまま返す（台帳へ値を提供しない fail closed）。消費側（`install.py::_verify_approved_artifact`）にも同じ検査を局所に置いた。台帳行との比較は承認後の向け替えを捕らえるが承認時点で既に存在した向け替えは捕らえず、かつ消費側は共有状態へ変更を適用する経路であるため、性質を各実装で述べる（独立実装の突き合わせ規律に合わせる）。予測どおり `rev-parse --show-toplevel` は向け替え後も不変であり、既存検査では捕らえられないことを確認した（`./tmp/fix-w/installer_containment.py`）。レビューの指摘（導出主体の移動だけでは信頼の根が移らない）はそのとおりであり、導出の入力を worker の上限外へ置くことで初めて Judgment A の狙いが成立する。

新設した理由コードは `write-git-metadata` / `stage-git-metadata` / `git-discovery-redirected` / `git-discovery-unverified` の 4 件で、いずれも litmus（読み取り目的の呼び出しが到達しうるか）に照らして計上対象である。前 2 者は write カタログ／`git add` からのみ到達し、後 2 者は `add` / `commit` からのみ到達する。`git-discovery-unverified` は環境起因だが、既に計上対象である `target-drift` が同じ性質（worktree probe 由来）を持つため、扱いを一致させた。

フェンス実効性: 両検査を無効化した負の対照（`./tmp/fix-w/negctl.py`）で、メタデータ書込と向け替え後の `add` / `commit` がいずれも admit されることを確認した。有効時は 3 者とも拒否される。

### 2. W-B-01（major）宣言由来の書込上限に機械的な上限が無い

確証部分（上限に機械的上限が無い、全域パターンがそのまま契約になる）を再確認した。最悪形（メタデータ面）は 1 節の carve-out が宣言の幅と無関係に閉じる。breadth 自体には**ルータ側**で機械的上限を課した: パターンの先頭セグメントが `*` または `**` である宣言を拒否する（`write_paths` / `test_paths` の双方）。レビューが挙げた二択のうちゲート側案は共有実装に当たるため採らなかった。

制限は 1 形のみに留めた。再帰形（`src/**`）・前方一致（`src*/**`）・単一セグメント glob（`*.py`）はいずれもパターン自身の字面で有界であり、false deny ゼロ要求クラスで通常形を狭めないことを非拒否側のテストで固定した。

推測部分（コメント経由で specifier に広い宣言を写させる経路）は本ラウンドでも検証しておらず、確証として扱っていない。ただし `parse_scope_declaration` が読むのは body のみという事実は変わらず、先頭ワイルドカード拒否は body へ写された後の形にも効く。

### 3. W-B-04（minor）Markdown 上の不活性領域の未区別

正規表現を行走査へ置き換えた。fence は行頭〜インデント 3 桁のみを fence として扱い（4 桁以上は逐語テキスト）、別の fence が開いている間に現れた fence 行は外側ブロックの内容として扱う。fence 文字は バッククォートとチルダの双方を認識する。これで双方向が閉じる: 図解が実効宣言になる方向と、実宣言と図解の併記が「2 ブロック」として拒否される方向。実宣言 2 件の曖昧拒否は維持されることを別テストで固定した。

### 4. W-B-05 / W-C-04（minor）運用手順の宣言例が受理形と一致しない

`docs/operations/pda-improvement-cycle.md` の例を情報文字列付きの実形へ改めた。3 節の入れ子扱いにより、外側 4 バッククォートで囲めば文書内に実形を素朴に書ける（囲みの中は不活性）。手順書の当該例を実際に `derive_seed_payload` へ通すテストを追加し、正本手順と実装の乖離が再発したら落ちるようにした。`daily_reconciler_prompt.txt` 側も行単位の実形と、先頭ワイルドカード禁止・未知キー拒否・インデント制約を明記した。

### 5. W-B-06 / W-C-02（minor / major）宣言不備 1 枚による割当 queue の停止

処置は per-card 回復である。割当ループを try/except で囲み、拒否したカードを飛ばして次の候補へ進む。可視性はカードコメント（従来どおり 1 件）と戻り値の `refused`（カード ID と理由種別）の 2 経路で確保した。加えて宣言検査を `_ensure_worktree` より**前**に移し、**宣言解析段および幅検査段で拒否されるカード**に branch と worktree を残さないようにした（レビューが併記した副作用の解消と、拒否を飛ばす際の費用の有界化）。**seed 記録段の拒否（宣言は解析できるがゲートが契約 seed を受理しない形）では worktree は残る。**記録は worktree の同一性を入力とするため事前検査へ移せない。残った worktree は次周期の `_ensure_worktree` が同一 branch の worktree として再利用する（WV-04 の訂正、2026-08-23。起票時点の記述は「割当されないカードに branch と worktree を残さない」であり、後段拒否を含む主張になっていた）。1 周期で飛ばす拒否件数にも上限（50）を置いた。拒否 1 件あたりの作業がカードコメントであるため、走査を盤面サイズに比例させない。上限値は本レーンの実際の盤面規模より十分大きく、病的な盤面で 1 周期が無界にならないことのみを担う。

**司令塔判断に回す点（実装裁量で先に入れた形）**: 決定文面「宣言なしは割当せず CycleError＋カードコメント」は当該カードの扱いを定めるもので、周期全体を打ち切るかは定めていない（レビューも同旨）。したがって per-card 回復は決定の変更ではないと判断した。ただし周期の戻り値の `ok` が、宣言不備のみのときに `false` から `true` へ変わる（不備カードは盤面の状態であって周期の失敗ではないという解釈）。exit gate で批准対象とする。

### 6. W-C-06（minor）一部割当成功後の失敗が「割当ゼロ」として報告される

5 節の per-card 回復により、成立済みの割当は戻り値の `assigned` に残る。ローカル等価再現で、宣言済みカードが割当・seed 記録・通知まで完了した周期が `assigned: ['t_good']` を返すことを確認した（基準点および修正前は `[]`）。

### 7. W-C-01（major）割当経路水準の正常系テストの fixture 不足

`_repo()` fixture が `integrations/hermes-scope-gate/scope_gate.py`・`schemas/`・`operations/improvement/scope_seed.py` をこのリポジトリから複製するようにした。スタブではなく複製である（スタブは、存在しないゲートと cycle 側テストが合意する状態を作る）。開発 PC では当該スイートが実行不能なため、fixture と同形のリポジトリを組んで `record_seed` と `start_turn` まで通す等価再現（`./tmp/fix-w/fixture_equiv.py`）で確認した。当該テストの assert 対象（`write_paths` / `git_write` / `execution` / `test_paths`）はいずれも成立する。

### 8. W-C-03（major）承認 metadata のスキーマ版上げに移行経路が無い

互換分岐は置かない。v1 オブジェクトを受理する分岐は「検査主体がいなくなった欄を digest の中で通さない」という Judgment A の趣旨と衝突する。処置は文書化である: 有効化手順書へ「本変更以前の未消費承認は再ハンドオフとオーナー再承認が必要」「有効化前に未消費行の有無を確認する」を明記し、設計文書の Judgment A 節にも移行方針として記載した。

**司令塔判断に回す点**: 台帳に未消費 v1 行が実在するか（実在件数）は開発 PC から確認できない。実在が判明した場合に (a) 再ハンドオフで処理するか (b) 消費経路へ限定的な互換分岐を置くかは、件数を見た上でのオーナー判断とする。本処置は (a) を前提に文書化した。

### 9. W-B-03（minor）強制スイッチの既定値による fail-open

`_route_task` の `scope_seed_enabled` から既定値を外し、キーワード必須にした。省略は呼び出し時エラーとなる。既定 false はコミット済み方針ファイル側の既定として残る（`run_cycle` が読む）。既存テストの 1 呼び出しを明示指定へ更新した。

### 10. W-C-05（minor）クラス既定の定数の二重定義

`scope_seed.CLASS_DEFAULT_GIT_WRITE` と `scope_gate.ARTIFACT_GIT_WRITE_ACTIONS` の等値を固定するテストを追加した。承認側で既に実施されている「独立実装を突き合わせで固定する」規律に揃えた。

### 11. W-B-07（minor）誤検知として処置しない

**判定: 誤検知（前提が事実と異なる）。** W-B-07 は「seed を書く実装と強制する実装が別コピーであり、正規化の意味論がずれうる」と述べるが、ゲートの installer はプラグインディレクトリを**リポジトリのソースへの symlink** として設置する（`install.py`: `plugin_path.is_symlink() and plugin_path.resolve() == source_path`、`--source` の既定は当該ディレクトリ自身）。したがって強制側が読むファイルとルータが `repo_root` 経由で読むファイルは同一ファイルであり、「別コピー」も「版ずれ」も成立しない。W-C レビューの被覆記録 4 が同じ事実を独立に確認しており、両レビューの記述が衝突している側のうち W-B-07 が誤りである。

残るのは「cycle 設定の `repo_root` が installer の `--source` と別チェックアウトを指す場合」だが、これは W-B-07 の主張内容ではなく、worker から到達できる経路でもない（プライマリリポジトリは全 worker の上限外）。証拠として、installer のソース既定とルータが解決するゲートのパスが同一であることを固定するテストを追加した。

### 12. 回帰テスト（新規 19 件 + 25 パラメタ、既存 4 件を改訂）

新規（`integrations/hermes-scope-gate/tests/test_artifact_change_scope.py`）:
- `test_the_widest_write_scope_still_refuses_gits_own_metadata`（4 パラメタ）/ `test_the_widest_write_scope_still_admits_ordinary_files` / `test_no_write_catalogue_tool_reaches_git_metadata`（7 パラメタ、対フィールドの source 側・destination 側を分けて固定）/ `test_staging_refuses_gits_own_metadata` / `test_a_linked_worktree_is_admitted_by_the_discovery_check` / `test_a_git_write_is_refused_when_discovery_resolves_inside_the_locked_root`

新規（`integrations/hermes-scope-gate/tests/test_scope_seed_wiring.py`）:
- `test_a_declaration_cannot_stand_in_for_the_whole_tree`（7 パラメタ）/ `test_the_same_limit_applies_to_declared_test_assets` / `test_an_anchored_pattern_of_any_depth_is_still_accepted`（6 パラメタ）/ `test_an_indented_example_is_not_a_live_declaration` / `test_a_declaration_shown_inside_an_example_block_is_inert`（2 パラメタ）/ `test_a_real_declaration_beside_a_worked_example_is_not_ambiguous` / `test_two_live_declarations_are_still_refused` / `test_the_documented_declaration_example_is_the_accepted_form` / `test_the_class_default_matches_the_gate_that_enforces_it` / `test_the_router_reads_the_gate_the_installer_deploys`

新規（`operations/improvement/tests/test_pda_improvement_cycle.py`、ミニPC 実行）:
- `test_an_undeclared_card_does_not_block_the_cards_behind_it` / `test_a_refusal_after_an_assignment_still_reports_the_assignment`

新規（`integrations/hermes-pda-approvals/tests/test_plugin_api.py`、ミニPC 実行）:
- `test_gate_derived_identity_refuses_a_workspace_that_carries_its_own_repository`

拡張（`operations/improvement/tests/test_install.py`、ミニPC 実行）:
- `test_activation_rechecks_latest_review_head_and_clean_workspace`（消費側の封じ込め拒否を既存の drift 検査群と同じ形で追加。向け替えを組んで拒否を確認し、元の状態へ戻す）

改訂:
- `test_the_counting_set_is_exactly_the_ratified_enumeration` の正本列挙 `_EXPECTED_DEVIATION_DENY_ACTIONS`（22 → 26。計上集合の**拡大**であり、litmus に照らした新たな確定事実の主張である。11 節 4 の一方向性規律に従い縮小とは混ぜていない）
- `test_the_flag_defaults_off_and_records_nothing`（既定値依存を廃し明示指定へ）
- `test_atomic_route_never_overwrites_a_concurrent_assignment`（同）
- `test_an_enabled_seed_policy_refuses_a_card_without_a_scope_declaration`（`ok: true` + `refused` + worktree 非作成へ）
- `_repo()` fixture / `_config()` helper（7 節、および per-tick の可変化）

ローカル実行結果: `integrations/hermes-scope-gate/tests` は 576 passed（基準点 535 + 41）。`operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` は開発 PC で実行不能（`hermes_cli` / `fastapi` 不在）のため、等価再現（`./tmp/fix-w/test_loop_after.py`、`./tmp/fix-w/verify_ws_probe.py`、`./tmp/fix-w/fixture_equiv.py`）で確認した。ミニPC での実行は親セッションが一括で行う。

### 13. 併せて更新した文書

- `docs/design/task-scope-admission-gate.md`: 第一層へ照合順序の改訂と「Git メタデータは宣言の対象外」項を新設。worker 配線 2 項へ per-card 拒否・worktree 作成前検査・breadth の機械的上限・宣言ブロックの不活性領域の 4 点を追記。4 項へ強制スイッチの既定値廃止を追記。Judgment A へ導出入力の上限外化とスキーマ移行を追記。
- `integrations/hermes-scope-gate/README.md`: 探索前提の残余記述へ carve-out と封じ込めを追記。
- `docs/operations/pda-improvement-cycle.md`: 宣言例を受理形へ、制約 4 点を追記、per-card 拒否と `refused` を明記、承認スキーマ移行の手順を追記。
- `operations/improvement/daily_reconciler_prompt.txt`: 宣言の実形と制約を追記。
- `profiles/pda/skills/pda-autonomous-improvement/SKILL.md`: `.git` への書込・ステージ禁止（計上対象である旨を含む）を追記。
- `docs/operations/adversarial-suite.md`: 迂回 7 類型を抽象名とテスト所在で追記。

### 14. 本ラウンド後の残余（司令塔判断）

1. **周期戻り値の `ok` 意味論の変更**（5 節）。**批准対象は「割当ループの失敗報告全体」である**（WV-03 の訂正、2026-08-23。起票時点は「宣言不備のみのとき」と書いていたが、per-card 回復は割当ループ内の `CycleError` を種別で選別せず捕らえる）。宣言不備に加えて `workspace-collision` / `dirty-worktree` / `claim-race` でも `ok` が false から true へ変わる。`scope_seed.enabled: false`（M1 exit 時点の live 構成）でも同様であり、seed 経路の有効化と独立に発効している。現行 live 構成への影響がこの点である。拒否は `refused` に必ず出るため不可視ではないが、周期の `ok` のみを見る監視から見える形は変わる。割当ループの外側の失敗（設定不正・方針ファイル読取不能など）は従来どおり `ok: false`。exit gate で批准対象。
2. **未消費 v1 承認行の実在確認と処置方針**（8 節）。ミニPC の実機事実に依存する。
3. **commit 時点の index 内容と write scope の照合**（既存残余、設計 §11 第 9 項）。本ラウンドの封じ込めは解決先の乗っ取りを閉じるが、ゲート外でステージされた内容がローカル commit に入る残余は変わらない。
4. **`git-discovery-*` の計上**（1 節）。環境起因の拒否を拒否上限へ計上する点は `target-drift` と同じ扱いだが、レビューを経ていない新規判断である。

## 15. w-verify ラウンドの確証欠陥 4 件の処置（2026-08-23、14 節の続き）

- 入力: `docs/status/restricted-s3-impl-review-2026-08-23-w-verify.md`（`f7cfe0f..312b1f4` の独立検証。修正 12 件の反転を実測で確認、W-B-07 棄却は妥当、確証欠陥 4 件 / 誤検知 0 件）。
- 対象: WV-01 は第一層の carve-out の照合方法、WV-02 はルータ側の宣言幅検査の機構、WV-03 / WV-04 は本台帳と設計本文の記述。
- **admission は広げていない。** WV-01 は拒否の到達範囲を広げる変更（同一実体を指す別綴りを拒否側へ）であり、WV-02 はルータ側の受理条件を狭める変更である。closeout 共有実装は無改訂、計上規則（litmus・計上集合）も無改訂。
- 全数: **598 passed**（本節前 576。新規 22 パラメタ、既存 1 パラメタを差し替え）。加えてミニPC 実行のルータテストを 2 パラメタ追加。
- 再現確認: 検証者のプローブを実行して修正前の状態を再確認したうえで処置し、反転を実測した（下記各項）。
- フェンス実効性: WV-01 の実体同一性判定と WV-02 の実効幅測定をそれぞれ無効化した負の対照で新規テストを実行し、**19 失敗**を確認した（残る 3 件は false deny 側の対照とクロス実装の突き合わせであり、フェンス無効化では落ちないことが正しい）。

### 1. WV-01（case を畳む FS では blocker、本番の ext4 では不成立）メタデータ carve-out が綴りの完全一致のみで判定

- 再現（処置前）: 検証者のプローブ `./tmp/verify-w/p1g_casefold.py` を実行し、綴り変種が carve-out を通過して実体側の内容が書き換わることを再確認した。
- 処置: 判定を 2 段にした。(a) 相対パスが `.git` セグメントを含むこと（従来の判定。ツリーに依存せず成立し、未作成の書込先と入れ子リポジトリを覆う）、(b) 解決後パスの各前置部が、その親ディレクトリの `.git` と**同一のファイルシステム実体**であること（`os.path.samefile`）。`root` は必須引数とし、省略時に綴り照合へ静かに退行する形を作らない。理由コードは `write-git-metadata` / `stage-git-metadata` のまま（計上集合と litmus は無改訂）。
- 司令塔決定どおり、フェンス 2（解決先の封じ込め）の通常リポジトリ許容を狭める案は採っていない。carve-out 側で連鎖が閉じるため。
- 反転の実測: `./tmp/verify-w/p3b_purewrite.py`（end-to-end のプローブ）が 1 手目で `allowed=False action=write-git-metadata` となり、以降の連鎖に到達しない。**`p1g_casefold.py` は処置後は再実行できない**（carve-out 関数を直接呼ぶプローブであり、`root` を必須引数にしたため呼び出し形が変わった）。同関数の両方向は下記の回帰テストで固定してある。
- 併せて `scope_gate.py` のコメントと拒否理由文から無条件の主張（「which no contract admits」）を外し、実体同一性による照合であることを明示した。検証者が指摘した 3 点のうち残る 2 点（本番形が Linux に限る保証が無い、新設テストに当該事例が無い）は下記テストで閉じた。
- 回帰テスト: `test_a_metadata_name_the_filesystem_folds_is_still_refused`（FS の実挙動を検出し、畳む環境では拒否、畳まない環境では別ディレクトリとして許可＝false deny 側を固定）、`test_an_alias_of_the_metadata_pointer_is_refused`（**FS 非依存**。linked worktree の `.git` は pointer file であり、その hard link は同一実体で別名になる。書込とステージの双方を固定）、`test_an_ordinary_file_beside_the_metadata_pointer_is_not_refused`（false deny 側の対照）。

### 2. WV-02（major）宣言由来上限の「機械的上限」が綴りの列挙

- 再現: `./tmp/verify-w/p4_anchor.py` を実行し、綴りを変えた全域相当の宣言が受理され、ロック済み契約で全域の書込が admit されることを再確認した。
- 処置（司令塔決定どおり、綴りの列挙をやめ実効照合で測る）:
  1. **綴りの規則は床として残した。** 先頭セグメント `*` / `**` の拒否は、ツリーを要さずに成立する点で価値があるため撤去しない。ただし**保証を負うのは測定側**であることを実装 docstring と設計本文へ明記した。撤去して測定のみにすると、判定が対象ツリーの規模に依存し、小さなツリーでは最も素朴な形が通ってしまう（W-B-01 の確証済み反転を退行させる）。
  2. **実効幅の測定を追加した。** 宣言（`write_paths` と `test_paths` の**和**。ゲートは書込 admission で両者を合わせて照合するため実効上限は和である）を実ツリーへ照合し、被覆する最上位エントリ数を測る。上限は既定 3 で、所有者コミットの方針ファイル `scope_seed.max_top_level_entries` から変更できる。測定は導出の 2 箇所（割当前検査＝プライマリリポジトリのツリー、seed 記録＝対象 worktree のツリー）で行う。ツリーが測定できない場合は拒否する（未測定の上限を狭いと仮定しない）。照合はゲートの `scope_pattern_matches` を**読み取りで利用**し、共有実装を拡張していない（D-S3-7 決定 1）。
  3. **統治面の被覆は常に拒否する。** 判定は字面（未作成のファイル名を名指す形を含む）と実照合の 2 経路。`install.py` の `GOVERNANCE_PATHS` と同一集合をルータ側に持ち、突き合わせテストで固定した（承認側の複製に既に適用している規律に合わせた）。
- 反転の実測: `./tmp/fix-wv/p4_breadth_after.py`（本リポジトリのツリーに対して）で、検証者が ACCEPTED と記録した 8 形すべてと組み合わせ形が拒否側へ移り、通常形（`src/**` / `src/pda/backup/*.py` / `src*/**` / `docs/status/*.md` / `src/**/*.py` / 和の形）は受理のまま。ルータ経由は `./tmp/verify-w/p10_router.py` P10e（当該カードが `refused` へ移り worktree を残さない）と `./tmp/fix-wv/router_equiv.py`（ミニPC テストの等価再現）で確認した。
- **測定は割当時のみで、進行中のタスクを座礁させない。** 導出が走るのは `_eligible_tasks`（`status == ready` かつ未割当）に載るカードだけであり、割当済みのタスクは再導出の対象にならない。claim race の残留 worktree に対して再導出が起こる場合も、`_ensure_worktree` が `record_seed` より前に `git status --porcelain` の clean を要求する（dirty なら `dirty-worktree` で拒否。基準点から不変の挙動）ため、測定が worker の書込後のツリーを見ることはない。payload は測定に依存しないため、ゲートの seed 冪等経路（異 payload の二度目を拒否する）にも影響しない。
- **解釈を要した点（判断へ回付済み。下記 5）**: 司令塔決定の 2 条件が現行の文書上で衝突していた。「統治パスへの被覆は常に拒否」と「運用手順の宣言例が通ることをテストで固定」の両方を満たすには、手順書の例（`operations/improvement/*.py`）が統治面を名指していることを解消する必要がある。当該例は `install.py` が最終承認の段で無条件に拒否する面を対象にしており、写したカードは最終化できない作業を買う。したがって**例を非統治面へ改める**方向で解消した（`docs/operations/pda-improvement-cycle.md`、`operations/improvement/daily_reconciler_prompt.txt`）。`test_the_documented_declaration_example_is_the_accepted_form` は手順書を読む形のまま維持しており、例と実装の乖離は引き続き自動検出される。
- **既存テストの差し替え（1 パラメタ）**: `test_an_anchored_pattern_of_any_depth_is_still_accepted` の `operations/improvement/*.py` を `src/sub/*.py` へ替え、当該形は `test_a_declaration_covering_a_governance_surface_is_refused` の側へ移した。
- 回帰テスト: `test_a_spelling_that_evades_the_floor_is_still_measured`（7 パラメタ。検証者が挙げた綴り族）、`test_the_measured_breadth_is_the_union_of_both_declared_fields`、`test_the_limit_is_configurable_without_changing_the_measurement`、`test_a_declaration_covering_a_governance_surface_is_refused`（7 パラメタ。字面判定側。未作成ファイル名を含む）、`test_a_governance_file_reached_by_a_wide_pattern_is_refused`（実照合側）、`test_the_governance_surfaces_match_the_activation_gate`（承認側実装との集合一致）、`test_an_unmeasurable_tree_refuses_rather_than_assuming_narrowness`（fail closed）。ミニPC 側に `test_an_overbroad_declaration_is_refused_before_a_workspace_exists`（2 パラメタ。ルータ経由で `refused` と worktree 非作成、後続カードの割当を固定）。

### 3. WV-03（minor）周期戻り値 `ok` の意味論変更が批准項目より広い

- 挙動は変えていない。記述を実測どおりの範囲へ広げた。14 節 14 項 1 を「割当ループの失敗報告全体」へ改め、該当理由種別（`workspace-collision` / `dirty-worktree` / `claim-race`）と、`scope_seed.enabled: false` の現行 live 構成でも発効している点を明記した。設計本文（第一層 worker 配線 2 項）と運用手順にも同じ範囲を書き、監視は `ok` だけでなく `refused` を読むことを明記した。

### 4. WV-04（minor）「割当されないカードに worktree を残さない」の主張範囲

- 司令塔決定の「安い方」に従い、主張を実態へ縮小した（後段拒否時のクリーンアップは追加していない。既存の衝突 worktree を消す経路になり得るため、費用も危険も高い）。14 節 5 と設計本文へ「宣言解析段・幅検査段の拒否では残さない、seed 記録段の拒否では残る」と、残った worktree が次周期に同一 branch の worktree として再利用されることを明記した。

### 5. 本ラウンド後の残余（司令塔判断）

14 節 14 の 4 項目のうち 1（`ok` 意味論）と 4（`git-discovery-*` の計上）は引き続き exit gate の批准対象、2（未消費 v1 承認行）と 3（index 内容の照合）は不変。本節で新たに増えた判断事項は次の 2 点である。

1. **統治面の被覆を宣言段で拒否する範囲の批准。** 最終承認の段で無条件に拒否される面であるため実質的な縮小は無いが、自律レーンが宣言できる面が明示的に狭まる（`operations/improvement/`・`integrations/hermes-*/`・`infra/systemd/`・`conftest.py` ほか）。手順書・reconciler prompt の宣言例を非統治面へ改めた点も同じ判断に属する。
2. **既存 Ready カードの宣言に対する false deny の実地確認。** 実効幅の測定と統治面拒否は既存カードの宣言を拒否しうる。live 盤面のカード本文は開発 PC から確認できないため、有効化前に既存 Ready カードの宣言を本測定へ通す確認が必要である（ミニPC 側の事実）。`scope_seed.enabled` が false の現構成では影響は発生しない。

### 6. 実行結果

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **598 passed**。
- `operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` は開発 PC で実行不能（`hermes_cli` / `fastapi` 不在）。ルータ経由の新規テストは等価再現（`./tmp/fix-wv/router_equiv.py`）で確認した。ミニPC でのスイート実行は親セッションが行う。

## 16. agent-node 限定スイートの失敗 4 件の処置（2026-08-24、15 節の続き）

- 入力: ミニPC（agent-node）でのみ実行できる 2 スイートの失敗 4 件（`operations/improvement/tests` 3 件、`integrations/hermes-pda-approvals/tests` 1 件）。
- 分類: **ハーネス問題 2 件 / 意味論追従 1 件 / テスト fixture の版ずれ 1 件。実装欠陥 0 件。** 変更は test ファイル 3 本のみで、実装・設計本文・運用手順は無改訂。
- **admission は広げていない。** 安全性質を弱める変更は無く、2 項・3 項はいずれも主張を強めている。
- 全数: `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）**598 passed**（15 節から不変。本節の変更は当該スイートに触れない）。

### 1.（ハーネス問題）承認プラグインを exec で読み込む 2 件が dataclass の注釈解決で落ちる

対象: `test_governance_path_lists_match_between_installer_and_plugin`、`test_plugin_and_installer_validators_agree_on_behavior`

- 症状: `dataclasses._is_type` 内で `AttributeError: 'NoneType' object has no attribute '__dict__'`。
- 原因: 両テストのモジュール読込が `module_from_spec` の結果を `sys.modules` へ登録せずに `exec_module` している。`plugin_api.py` は `from __future__ import annotations` 下にあり注釈は文字列であるため、`dataclasses` は `ClassVar` / `InitVar` / `KW_ONLY` の判定で定義モジュールを `sys.modules` から引く。未登録のモジュール内では dataclass が生成できない。Judgment A で新設した `WorkspaceCheck` が当該モジュール唯一の dataclass であり、これが入って初めて潜在していたハーネス欠陥が表面化した。テストは assert 本体に到達せず、モジュール実行の段で落ちていた。
- 処置: 両読込に `exec_module` 前の `sys.modules[name] = module` を追加した。実装は無改訂。同じ登録は本リポジトリの既存 3 箇所（承認テスト自身のプラグイン読込、ルータの seed helper 読込、scope-gate の配線テスト）で既に行われており、それに合わせた形である。
- 再現と反転: 開発PC 上でスタブを当てて exec を再現し、処置前は同一トレースで失敗、処置後は成功することを確認した。
- **併せて閉じた点。** 当該 2 件の assert 本体は読込段の失敗に阻まれ、Judgment A 以後一度も実行されていない。読込修正が新たな assert 失敗へ化けないことを事前に閉じるため、処置後に本体（`GOVERNANCE_PATHS` の集合一致、両バリデータの 11 ケース挙動一致、`APPROVAL_METADATA_SCHEMA_VERSION` と `GATE_DERIVED_IDENTITY_KEYS` の一致）を開発PC 上で実行し、いずれも成立することを確認した。スキーマ v2 化に伴う二実装の乖離は無い。

### 2.（意味論追従）path collision テストが per-card 回復より前の契約を主張している

対象: `test_cycle_adopts_exact_existing_branch_but_rejects_path_collision`

- 症状: `assert result["ok"] is False` が True。
- 判定: 15 節 3（WV-03 の訂正）で批准対象としている範囲そのものである。per-card 回復は割当ループ内の `CycleError` を種別で選別せず捕らえるため、`workspace-collision` も `ok: true` + `refused` へ移る。設計本文（第一層 worker 配線、「拒否は当該カード単位に閉じる」の項）にも当該理由種別が名指しで書かれている。テストが改訂前の契約に留まっていたものであり、挙動側の退行ではない。
- 処置: 主張を批准後の契約へ改めた。`ok is True` / `assigned == []` / `refused == [{task_id, "workspace-collision"}]` / `reason == "no-routable-task"` に加え、**周期水準の失敗として報告されないこと**（`"error_kind" not in result`）を新たに固定した。安全側の主張（衝突ディレクトリを worktree として採用しない、カードを割当てない）は維持し、さらに **衝突ディレクトリの内容が不変であること・`.git` が作られないこと・当該 branch が作られないこと** を追加した。docstring に WV-03 と設計本文の該当項を記し、テストが批准根拠を自ら持つようにした。
- 反転の実測: 開発PC 上のスタブ盤面で実 `run_cycle` を当該シナリオへ通し、新しい 9 個の主張すべてが成立することを確認した。

### 3.（fixture の版ずれ）承認トランザクション内の再検証テストが drift を作れていない

対象: `test_workspace_is_revalidated_inside_approval_transaction`

- 症状: `assert response.status_code == 409` が 200。
- **実装は健全である。** 承認経路は `kanban_db.write_txn` の内側で `verify_workspace(fresh_task, fresh_approval)` を呼び直し、`errors` があれば 409、導出 identities が空でも 409 を返す。台帳へ書く identities はこの内側の導出値であって前段の値ではない。Judgment A はトランザクション内再検証を弱めていない。
- 原因: fixture が Judgment A 前の戻り値形に留まっている。`verify_workspace` は `WorkspaceCheck`（frozen dataclass）を返すようになったが、fixture は戻り値をそのまま `if not errors:` で空判定していた。dataclass のインスタンスは常に truthy であるため条件は決して成立せず、drift（タスクの `branch_name` 書換え）が一度も注入されない。drift が無ければ再検証は当然通り、承認が成立して 200 になる。**表面上の期待値ではなく、安全性質のテストが空回りしていたことが失敗の内容である。**
- 処置: 空判定を `check.errors` 側へ改め、`check` をそのまま返す形にした。併せて応答検査の直前へ **`assert drifted is True`** を追加した。fixture が再び空回りした場合、409 の主張が通ってしまう前にこの主張が落ちる（空回り検出の固定であり、主張を弱めない）。期待値 409 は変更していない。
- 反転の実測: 開発PC 上で実 linked worktree に対して実 `verify_workspace` を呼び、(a) 清浄な workspace では `errors == []` かつ identities が得られる、(b) 旧 fixture の条件は成立しない（drift 非注入）、(c) 新 fixture の条件は成立する（drift 注入）、(d) `branch_name` を drift させたタスクは `task branch_name no longer matches the approval request` で拒否される、の 4 点を確認した。(d) がトランザクション内で 409 を生む入力である。

### 4. 併せて記録する観測（本節では処置しない）

- `workspace-collision` の拒否は `_ensure_worktree` が投げるため `_route_task` に到達せず、**カードコメントは書かれない**。設計本文の「可視性はカードコメント（1 件）と `refused` の 2 経路で確保する」は宣言不備の拒否について成立し、`workspace-collision` / `dirty-worktree` / `claim-race` では `refused` の 1 経路のみである。15 節 3 で改めた WV-03 の記述は「拒否は `refused` に必ず出るため不可視ではない」としてこの 1 経路を前提にしており矛盾はしていないが、設計本文の 2 経路の記述は宣言不備に限る旨を補う余地がある。コメント経路の追加は批准範囲外の挙動変更であるため本節では行わず、exit gate の判断材料として記録する。

### 5. 実行結果

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **598 passed**。
- `operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` は開発PC で実行不能（`hermes_cli` / `fastapi` 不在）。本節の 4 件はいずれも開発PC 上のスタブ再現で処置前の失敗と処置後の反転を確認した。ミニPC でのスイート実行は親セッションが行う。

---

## 17. 実機検証（隔離 HERMES_HOME・実カード）で確定した束縛欠陥の処置（2026-08-24、16 節の続き）

ミニPC の dispatcher 起動 worker で実カードを 1 枚流し、フックへ実際に届く値を計測した。設計第 9 項が「運用条件として要求する」に留めていた host 識別子の配線について、実測が要求の成立形を変えたため本節で処置する。

### 1. 発見（計測事実）

- **フックへ届く task_id は Hermes セッション識別子であり、ボードカード ID ではない。** turn 行の実測値は `task_id == session_id ==` 同一のセッション識別子、`task_class=audit-only`、`contract_origin` 空であった。
- seed はカード ID を鍵として記録されるため、payload だけを見る解決では**照会が結合せず、ターンは監査のみとして開く**。設計が想定した「seed の存在が強制の発効セレクタである」という不変条件は、記録側が正しくてもこの一点で成立しなくなる。第 9 項の「task_id または session_id のどちらかが配線されていること」という条件は、**両方が非空でも満たされない**（非空性ではなく指す対象が問題であった）。
- **強制系そのものは健全であった。** worker は locked 契約なしの変異を自覚し、self-lock を「audit-only turns cannot lock a scope contract」で拒否され、カードを理由付きで block した。fail-closed は設計どおり成立しており、欠陥は「強制が漏れる」方向ではなく「seed 経路が発効しない」方向である。
- **dispatcher は spawn 時に worker プロセスの環境変数へカード ID を供給していた**（`HERMES_KANBAN_TASK`。ミニPC 実機で確認。開発PC に当該ソースは無い）。plugin/フックは worker の agent プロセス内で動くため、この値はホスト供給の束縛アンカーとして読める。
- 併せて確認: plugin のロードと shell hook 登録（`fail_closed=True`）は隔離環境で成功。カタログのツール名（`read_file`・`kanban_block` 等）は実レジストリに実在した（架空名による許可の空振りは無い）。

### 2. 処置（司令塔決定の実装）

決定は「プロセス環境変数 `HERMES_KANBAN_TASK` を最優先の正本とし、無ければ従来どおり payload の task_id → session_id」。

- 解決関数を `scope_gate.py` に置いた（`HOST_TASK_BINDING_ENV` / `host_task_binding()` / `resolve_task_binding()`）。shell hook は `scope_gate` のみを import するため、両サーフェスが共有できる置き場所はここだけである。
- 読取はフック処理時に行う（プロセス起動時に固定しない）。ただし**一つの呼び出しの中では一度だけ解決し、同じ値を全ての store 呼び出しへ渡す**。`plugin_runtime` に `_binding()` を置き、`pre_llm_call` / `pre_tool_call` / `tool_execution_middleware` / `handle_scope_gate` / `post_tool_call` / `_close_at_audit_hook` / `on_session_end` の全フックで先頭に解決を寄せた。`_turn_key()` は kwargs を読む形から解決済み値を受け取る形へ改め、キーワードを必須にした（既定値を残すと呼び出し漏れが空文字経路へ落ちる）。
- `validate_shell_payload` も同一順序で解決し、`resolve_turn_id` / `admit_without_turn` / `admit_tool` へ同じ値を渡す。改訂前は同じ式を各呼び出しで別々に書いていたため、片方だけ直すと束縛と admission が食い違う形が残る。
- **`session_id` は上書きしない。** 会話の識別子であり、task 識別子が全て無い場合の照会先として独立に必要である。
- **`record_contract_seed` には適用しない。** そこでの task_id は「配る相手のカード」を指す割当者の鍵であり、実行中 worker プロセスの同一性ではない。統一すると seed が誤ったタスクへ記録される。この非対称は意図であり、後続ラウンドが「揃える」方向で潰さないよう設計本文にも明記した。
- `operations/improvement/install.py` の `KANBAN_ENV_OVERRIDES` には**加えない**。あちらは board / DB パスの pin を無効化するための集合であり（インシデント t_4a78c98b）、`HERMES_KANBAN_TASK` はパス pin ではない。2 つの同名タプルは目的が別である。

### 3. テスト環境の露出（処置に含めた）

環境変数が payload より優先されるため、**worker 環境の中でスイートを走らせると明示した識別子が上書きされる**。実測: ambient に値を置くと 5 件が落ちる（うち 3 件は「アンカー不在時の挙動」を主張するテスト、2 件は 2 つの異なる task id を使うテスト）。残りが通るのは解決が seed・ターン・admission で一貫して上書きされるためであり、これは実装の一貫性の裏付けでもある。

- リポジトリ直下 `conftest.py` の `KANBAN_ENV_OVERRIDES` へ `HERMES_KANBAN_TASK` を追加した。同 conftest が既に扱っているインシデント類型（dispatcher 管理環境の env が `HERMES_HOME` ベースの隔離を上回る）と同一であり、ゲートを import するスイートは本ディレクトリの他に 2 つある（`operations/improvement/tests`・`integrations/hermes-pda-approvals/tests`）ためリポジトリ全体で除去するのが正しい範囲である。
- 加えて `integrations/hermes-scope-gate/tests/conftest.py` に autouse fixture を置いた。rootdir がリポジトリ直下でない起動（当該ディレクトリ内から `pytest tests` を実行する形）では直下 conftest が読まれないため、二重化する。両方の経路で ambient 値を置いた実測 green を確認した。

### 4. 回帰テスト（新規 16 件）

`integrations/hermes-scope-gate/tests/test_host_task_binding.py`。テスト名は欠陥台帳の抽象水準に留める。

- 解決規則そのもの: 呼び出し時読取であること、空白のみの値は「不在」であって task id ではないこと、アンカーが payload に優先すること、アンカー不在時に payload が束縛すること。
- in-process サーフェス: カード seed が初回ターンへ結合し `locked` / `contract_origin=assignment` になり seed の `consumed_turn_id` が埋まること、同ターンの tool 呼び出しが当該契約で統治されること（scope 内は admit・scope 外は block）、**バインド不能な呼び出しがカード契約に対して enforced になること**（`contract-unbound`）、実行 middleware が同じアンカーを解決すること、制御ツールが同じターンへ届くこと、アンカー不在時に payload 識別子で従来どおり `locked` になること。
- 優先順位の可観測化: payload 側 task にも実 seed を持たせ、**両者が実契約へ解決する状態で**アンカー側が勝つことを主張する（片方の照会が失敗するだけの構成では優先順位を実証できない）。payload 側 seed が未消費であることも併せて固定した。
- out-of-process サーフェス: shell hook が同じアンカーを解決すること（payload の session 欄が欠ける形を含む。この形ではアンカーだけが契約へ到達する唯一の識別子であり、改訂前は not-enforced として許可されていた）、および shell hook のバインド不能経路が enforced になること。
- 割当側の非適用: ambient にアンカーを置いた状態で `record_contract_seed` が引数のカードへ記録され、アンカー側のカードには記録されないこと。

**空回り検出**: 解決関数からアンカー優先を外した状態で当該ファイルを実行し、**16 件のうち 8 件が落ちる**ことを確認した（残る 8 件は解決の単体検査・アンカー不在時の挙動・割当側非適用であり、どちらでも通るのが正しい）。テスト環境の露出についても、直下 conftest を外して ambient 値を置くと 5 件が落ちることを確認済み（3 節）。

### 5. 設計文書の更新

- 契約ライフサイクル節 第 9 項の「host 識別子の配線が前提条件」を、実測に基づく解決順序へ書き換えた。要求の内容が「どちらかが非空であること」から「カードを名指す識別子が到達すること」へ変わっている点を明記した。一呼び出し一回の解決、割当側 seed への非適用、pytest ガードへの追加も同項に含めた。
- 「S3-M1 worker 配線」節へ第 3 項「記録した契約と実行中の worker を結ぶ識別子」を新設し、以降を繰り下げた（旧 3→4、旧 4→5、旧 5→6）。他節からの「第N項」参照は当該節を指すものが無いことを確認済み（415/581/659 行の参照はいずれも別節・S2 宛て）。ホスト供給値が INV-S8（上限の出所は実行主体の外）と同じ性質を持つこと、実行主体が書き換えても自分の上限は広がらないこと、供給が失われた場合も fail-closed であることを記した。
- 併せて `integrations/hermes-scope-gate/README.md` の束縛記述を解決順序へ改めた。

### 6. 本ラウンド後の残余（司令塔判断）

- 実機で確認できていない設計第 7 項の残り: `post_llm_call` の発火粒度、cycle と gateway が同一 store を解決すること、`PDA_SCOPE_GATE_ARTIFACT_PRELOCK` の実効値読み戻し、worktree path の canonical 一致。本ラウンドの実カード実行は audit-only ターンで終わったため、locked ターンでのこれらの確認は seed 結合後の再走行を要する。
- **本処置後の実機再走行は未実施である。** 開発PC には dispatcher のソースが無く、環境変数の供給は実機観測に依拠している。処置の実効確認（seed 結合済みの locked ターンでカードが完走すること）はミニPC 側の再走行事項として親セッションへ引き渡す。
- **アンカーは継承される環境変数であるという性質の残余（本節では処置しない）。** kanban-governance patch の同梱テスト（`test_delegate_child_env_scrub_bypass_is_closed`）が示すとおり、当該変数を持たない子プロセスは実在する事象として既に扱われている。アンカーを持たない呼び出しは payload 識別子へ落ち、親の seed とは結合しないため監査のみとして解決される。**この形は本処置の新設ではない**（改訂前も子の payload 識別子は親の seed と結合しない）。かつ artifact-change 契約は委任と background work を拒否するため、locked な worker からこの経路へ進むことはできない。したがって現時点で追加の機構は要らないと判断したが、「ホスト供給値の到達がクラスの運用条件である」という第 9 項の要求は、供給する側（dispatcher）と供給が途切れる境界（子プロセス生成）の両方に掛かる。境界側を機構で閉じるか運用条件に留めるかは司令塔判断であり、exit gate の判断材料として記録する。

### 7. 実行結果

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **614 passed**（16 節時点 598 + 新規 16。既存の失敗・skip 無し）。
- ambient に `HERMES_KANBAN_TASK` を置いた同スイート: **614 passed**（直下 conftest 経路・ディレクトリ内 rootdir 経路の両方）。
- `operations/improvement/tests`・`integrations/hermes-pda-approvals/tests`・`tests/`・`integrations/openwebui-hermes-progress/tests` は開発PC で実行不能（`fastapi` / `hermes_cli` 不在。16 節と同じ）。直下 conftest の変更は当該スイートへも影響するため、ミニPC でのスイート実行は親セッションが行う。`operations/improvement/install.py` 側の同名タプルは変更していないため、`test_kanban_isolation.py` が import する集合は不変である。

---

## 18. 束縛変更の反証レビュー（tb-bypass、2026-08-24）で確証された欠陥の処置

対象は 17 節の処置（アンカー優先化、`bc32ca1`）に対する反証レビュー。検証記録は `docs/status/restricted-s3-impl-review-2026-08-24-tb-bypass.md`（迂回手法の具体形を含むため取扱制限）。確証 4 件のうち挙動変更は TB-01 のみで、TB-02 / TB-04 は主張の射程訂正、TB-03 は宣言済み残余とした。

### 1. TB-01 [major]（アンカー優先解決の fail-open 分岐）— 機構修正

- **確証された形**: 解決がアンカーを無条件に優先していたため、payload 側の識別子が seed 済みカードを名指すターンで、アンカーに別値が入っているだけで払い出し済みの契約が無言で失効し、未強制（全許可）へ落ちた。設計本文の不変条件「監査のみへは落ちない」を反証する。再現は検証記録の probe P10。
- **処置（司令塔決定の実装）**: 実装原則を「**いずれかの識別子で契約記録（seed または自己 lock）が引ける場合、束縛はそれを失効させる方向へ解決してはならない**」とした。
  - `GateStore.has_contract_record(task_id=, session_id=)` を新設。seed と自己 lock の 2 記録種を、それぞれの session フォールバックを含めて照会する（「その識別子で束縛したターンは強制されるか」を答える述語であり、「その鍵が seed されているか」ではない）。
  - `resolve_task_binding` に任意引数 `has_contract` を追加。両識別子が食い違うときに限り照会し、**アンカー側が引けず payload 側が引ける場合のみ** payload を採る。両方引ける／アンカー側が引ける／どちらも引けないは従来どおりアンカー優先。引数省略時は従来の純粋な優先順位（store へ到達できない呼び出し元のため）。
  - 照会は解決の内部で一度だけ行う。`plugin_runtime._binding()` を静的メソッドから実例メソッドへ改め（`self.store` を要するため）、`validate_shell_payload` では `session_id` の読み取りを解決より前へ移した。両サーフェスが同一規則で解決する。
  - **ターン履歴は照会に含めない。** 記録ではないため、履歴のみを根拠に束縛を動かしても契約は発効せず、帰属だけが動く。`admit_without_turn` の 3 経路判定（記録 2 種＋履歴）は新述語を用いる純粋なリファクタとし、判定内容は無変更。
  - **照会の失敗は各フックの既存例外境界の内側に置いた。** 改訂前の解決は env 読取と文字列操作のみで例外を出し得なかったが、照会を伴う解決は store 読取を含むため store 障害（DB ロック・I/O 失敗）で失敗し得る。解決を境界の外に置いたままでは、設計の「ゲート自身の失敗は fail-closed。admission を呼ぶ全経路に例外境界を置く」に反し、呼び出し元へ例外が抜ける（実測で 3 経路の抜けを確認）。したがって `pre_llm_call` / `pre_tool_call` / `tool_execution_middleware` / `handle_scope_gate` の 4 経路で解決を `try` の内側へ移した。結果は各経路の既定の fail-closed 出口（admission 経路は block、ターン登録は未登録 → 後続呼び出しが unbound 経路で fail-closed、制御呼び出しは `ok: false`）である。**述語の側で例外を飲まない**: 失敗時に「契約なし」を返すとアンカーが採られ、本節が閉じた組合せの未強制側へ倒れる。shell hook は照会が `validate_shell_payload` の内側にあり、`fail_closed=True` の登録が既に境界である。
- **admission を広げていない。** 訂正が発火するのは「アンカー側の束縛が全く強制されない」場合に限られ、その場合の遷移は未強制 → locked である。すなわち向きは強制を*加える*方向のみで、逆向きの遷移を作る分岐が無い。**偽装面も開かない**: 実行主体が payload 側の識別子を選べたとしても、選べるのは「その識別子で引ける契約に束縛される」ことだけであり、上限は狭まる（検証記録の「偽装束縛は制限方向にしか働かない」と同じ性質）。
- **実測（処置後）**: 検証記録 probe P10 の 4 行が全一致（stale アンカー行が `state=audit` / 全許可 → `state=locked` / `origin=assignment` / scope 外書込 `write-scope` 拒否へ反転）。probe P1〜P9 は全 PASS 維持（アンカー不在時の後方互換、偽装面の閉鎖、子プロセス経路をいずれも変えていない）。

### 2. TB-02 [minor]（env 不在経路の後方互換主張の不正確性）— 主張の訂正

- 17 節の「env 不在経路は完全な後方互換」は正確でない。新しい解決関数が payload 側に識別子の正規化（前後空白の除去）を導入したため、**空白のみの task 識別子**で turn key の scope 半分が task 由来から session 由来へ移り、`turns.task_id` の保存値も変わる。
- **方向は改善であり挙動は戻さない。** 改訂前は `get_contract_seed` / `scope_key` が内部で正規化する一方 `start_turn` は未正規化の値を保存しており、同一識別子が照会と保存で別物になり得た。改訂後は一貫する。安全性への影響は無く、欠陥は主張の正確性のみであった。
- 正確な主張: **「env 不在経路の後方互換は、識別子が正規化の影響を受けない形（前後空白を持たない）である限り成立する」**。空白のみの識別子をホストが送る経路は観測していない。

### 3. TB-03 [minor]（カード単位 turn fallback のプロセス境界越え共有）— 宣言済み残余

司令塔決定は「最小の機構修正か、機構が重い場合は宣言済み残余のどちらか安い方。判断根拠を台帳へ」。**残余として設計本文へ明記**した（設計 §「第一層で明文化する残余」へ項目追加）。根拠:

- **安価な変種は当該露出を閉じない。** 露出条件は「先行ターンが開いたまま残り、後続 worker が自分のターンを持たない」ことである。ターン解決の task 列照会を session 一致で先に試す変種は、後続 worker に自ターンが無いため空振りし、同じ task 照会へ落ちる。結果は変わらない。
- **閉じる変種は処置範囲を超える。** 閉じるには「プロセス境界を跨ぐ task fallback を外す」必要がある。これはターン解決の共有意味論（closeout も同じ経路に乗る）の変更であり、かつ現在境界付きで許可されている呼び出しを拒否へ変える admission 変更である。TB-01 の処置範囲（契約を失効させない方向の解決）を超え、本ラウンドの「admission を広げない・closeout 共有実装に触れない」制約とも別方向の risk を持つ。
- **残余の実害は有界**: scope 面は fail-closed（同一カードの契約であるため admit されるパス集合は同じ）、拡張 permit は turn 単位鍵のためカード横断消費なし。残るのはターン単位予算の相互消費と監査帰属の混線のみ。

### 4. TB-04 [minor]（closeout 挙動不変の主張の射程不足）— 主張の訂正

- 17 節の「アンカー優先化は closeout 挙動を変えない」は射程が不足していた。アンカーが seed 済みカードを指すとき、closeout 分類のメッセージは契約側の上書きにより `locked` な artifact-change になる。
- **意図された挙動である**（「契約記録は分類器より優越する」の文字どおりの帰結）。ただし改訂前の dispatcher レーンでは seed が結合しなかったため closeout が保たれており、**そこは live 挙動が変わった箇所である**。
- 正確な主張: **「closeout 挙動が不変なのは、アンカー不在時、または当該カードが未 seed のときに限る」**。方向は fail-closed（push が使えなくなる）で安全性の後退は無い。運用上の含意は「closeout を要する作業を seed 済みカードへ割り当てると詰まる」ことのみ。設計 S3-M1 配線 第 3 項へ明記した。

### 5. 回帰テスト（新規 8 件）

`integrations/hermes-scope-gate/tests/test_host_task_binding.py` へ追記。テスト名は欠陥台帳の抽象水準に留める。

- 解決規則そのもの: 4 通りの到達組合せ（両方引ける／アンカーのみ／payload のみ／どちらも引けない）を偽の照会関数で固定し、アンカーが譲るのは 1 通りだけであることを主張。照会関数を省略した場合に従来の優先順位が残ることも併せて固定。
- 照会の省略: 識別子が一方しか無い場合と両者が同値の場合に照会を行わないこと（答が決まっている場面で store 読取を増やさない）。
- **fail-open 組合せそのもの**（in-process）: payload が seed 済みカードを名指し、アンカーが store に無いカードを名指す形で、ターンが `locked` / `origin=assignment` になり、scope 外書込が拒否・scope 内書込が許可されること。
- 同組合せの自己 lock 版: 記録種が自己 lock でも同じく失効しないこと（`origin=self` を維持）。
- 非反転の保証 2 件: アンカーの鍵自体は未 seed でも session 経由で強制が成立する場合はアンカーを維持し、session 側の契約が当たること（payload 側の seed は未消費のまま）。どちらの識別子も契約を引けない場合はアンカーが束縛し従来どおり未強制で開くこと。
- out-of-process サーフェス: shell hook で同組合せが強制されること（束縛不能形で `contract-unbound`、ターン生成後は `write-scope`）。
- 例外境界: 照会が store 障害で失敗する状態を作り、4 経路がいずれも例外を出さず既定の fail-closed 出口へ落ちること（admission は `admission-validator-error` の block、middleware は `execution-validator-error` で下流未実行、ターン登録は未登録のまま、制御呼び出しは `ok: false`）。

**空回り検出**（2 変種で確認）:

- 解決から契約照会を外した変種: **8 件のうち 4 件が落ちる**（fail-open 組合せの in-process / 自己 lock 版 / shell hook 版と、解決規則そのものの 4 通り固定）。通る 4 件のうち 3 件は照会省略の主張と非反転の保証 2 件であり、どちらでも通るのが正しい。
- 解決を例外境界の外に戻した変種: **例外境界のテスト 1 件が落ちる**（store 障害が呼び出し元へ抜ける）。上記変種では落ちないため別立てで確認した。

### 6. 本ラウンド後の残余（司令塔判断）

- **TB-03 の残余の批准**（上記 3 節）。閉じるなら「ターン解決を session 一致へ限定し、跨ぐ呼び出しは束縛不能として fail-closed 経路へ落とす」形で別ラウンドに置く。
- **隣接する未確証の角（本ラウンドで確証していない、処置していない）**: バインド不能経路（`admit_without_turn`）は記録 2 種に加えてターン履歴も enforced とみなす。TB-01 の処置は履歴を束縛の照会に含めないため、「アンカーが別値、payload 側は契約記録を持たないがターン履歴だけを持つ」組合せでは、束縛はアンカー側に留まり当該履歴に到達しない。確証された欠陥集合の外であり、司令塔決定の文字どおりの範囲（契約＝seed または locked 契約）の外でもあるため処置していない。閉じるなら束縛の照会に履歴を加えるか、`admit_without_turn` を両識別子で照会する形になる。帰属は司令塔判断。
- **TB-04 の運用含意**: closeout を要する作業が seed 済みカードへ割り当てられると詰まる。割当側にガードを置くか運用条件に留めるかは司令塔判断。
- **記録専用フック `post_tool_call` に例外境界が無い（既存、本ラウンドでは処置しない）**: 設計の「記録専用フックは失敗を飲むが例外を外へ出さない」に対し、当該フックは store 読取（ターン解決・結果記録）を境界無しで行う。本ラウンドの変更前から同じ形であり（解決の直後で同種の store 読取を行っていた）、照会の追加は新しい露出クラスを作っていないため、上記 1 節の境界処置の対象外とした。`post_llm_call` は呼び出し側が包んでおり、`on_session_end` は内側に入っている。帰属は司令塔判断。
- 17 節の残余（実機再走行の未実施、アンカー継承の境界）は未解消のまま引き継ぐ。

### 7. 実行結果

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **622 passed**（17 節時点 614 + 新規 8。既存の失敗・skip 無し）。
- ambient に `HERMES_KANBAN_TASK` を置いた同スイート: **622 passed**。
- `operations/improvement/tests`・`integrations/hermes-pda-approvals/tests`・`tests/`・`integrations/openwebui-hermes-progress/tests` は開発PC で実行不能（`fastapi` / `hermes_cli` 不在。16・17 節と同じ）。ミニPC でのスイート実行は親セッションが行う。

---

## 19. tb2 レンズ再検証（2026-08-24）で確証された欠陥の処置と司令塔決定

対象は 18 節の処置（`9bbb831`、TB-01〜TB-04）に対する再検証。検証記録は `docs/status/restricted-s3-impl-verify-2026-08-24-tb2.md`（到達条件・構成手順を含むため取扱制限）。判定は pass、確証 2 件はいずれも「主張の射程」クラス（機構の fail-open ではない）。全数検査（anchor 5 状態 × payload 6 状態、30 セル）で admit 集合の拡大は 0 件、未強制へ落ちる新規セルも 0 件を確認済み。

### 1. TB2-01 [minor]（TB-04 訂正後の closeout 主張が TB-01 処置の再束縛セルを反映していない）— 主張の訂正

- 18 節 4 項の正確な主張「closeout 挙動が不変なのは、アンカー不在時、または当該カードが未 seed のときに限る」は、TB-01 の処置自体が新設した再束縛セルを反映していなかった。全数検査の closeout 観測（4 セル）で、アンカーが未 seed のカードを指し payload が seed 済みカードを指すセルが処置前後で変わっている（`repository-closeout` / `discovering` / `allow_push=1` → `artifact-change` / `locked` / `allow_push=0`）。「当該カードが未 seed」はこのセルでも真であるため、訂正文の文字どおりの射程ではこのセルも不変側に含まれてしまい、実測と食い違う。
- **評価**: 到達集合の比較では縮小のみ（commit は deny→allow へ動くが push は恒久拒否のまま）であり、安全性の後退は無い。欠陥は主張の射程に限る。
- **処置**: 設計文書（`docs/design/task-scope-admission-gate.md`、S3-M1 worker 配線 第 3 項）の当該主張文へ、原文の 2 つの選言（アンカー不在／当該カード未 seed）はそのまま残し、例外節「ただし、payload 側の識別子が契約へ到達し、かつアンカー側がいずれの経路でも到達しない場合は、この限りではない」を追加した。機構変更は無い。

### 2. TB2-02 [minor]（束縛照会から履歴を除く根拠文と束縛不能時判定の強制根拠集合の食い違い）— 主張の訂正

- 設計文書の「ターン履歴は照会に含めない（記録ではないため、履歴だけを根拠に束縛を動かしても契約は発効しない）」は文字どおり正しいが、`admit_without_turn` の enforced 判定（本コミットでも変更されていない、記録 2 種＋強制ターン履歴）が履歴を強制根拠に数えることと、除外の帰結（識別子が食い違いアンカー側に記録も履歴も無いとき、payload 側にのみ強制履歴があっても判定には反映されず allow 側に留まる）を述べていなかった。実測（`anchor` は記録も履歴も無し、`payload` は記録なしだが強制履歴あり）で `admit_without_turn` は解決結果の `anchor` についてのみ判定し `allowed=True` となることを確認した。
- **評価**: 機構は本コミット前後で不変（全数検査の当該セルは差分に現れない）であり、新しい露出ではない。18 節 6 項「隣接する未確証の角」は機構を正確に記述しており、欠陥は正本（設計文書）側の根拠文が取扱制限台帳側の記述より強い主張になっていた点に限る。
- **処置**: 設計文書の当該括弧書きへ、束縛不能時判定は解決済みの一つの識別子についてのみ行われるため選ばれなかった側の履歴は反映されないこと、および除外の帰結が「契約が発効する」ではなく「この組合せが未強制側に留まる」ことを明記した。機構変更は無い。

### 3. 司令塔決定 3 件

- **(1) TB-03 は宣言済み残余として批准する。** tb2 再検証 3 節が `resolve_turn_id` の fallback 順序と `expansion_permits` の鍵構造をコードで再確認し、18 節 3 項の評価（安価な変種は露出を閉じない／閉じる変種はターン解決の共有意味論変更かつ admission 変更になる）が引き続き成立することを確証した。閉じる変種は admission 変更を伴うため M2 検討へ送り、本ラウンドでは再実装しない。
- **(2) TB-04 の運用含意は運用条件として明記する。** 18 節 6 項の残余「割当側にガードを置くか運用条件に留めるかは司令塔判断」に対し、**運用条件（ガードコードの新設ではなく明文の運用ルール）として設計文書へ記録する**と決定した。設計文書（S3-M1 worker 配線 第 3 項、TB2-01 の処置と同一段落）へ「運用条件（TB-04 の運用含意、司令塔決定 2026-08-24）: closeout を要する作業は seed 済みカードへ割り当てない。」を明記済み。真に別クラスの作業なら別カード（別 task_id、未 seed）を割り当てるのが割当側の責務である、という帰結は従来どおり維持する。
- **(3) 記録専用フック `post_tool_call` の既存例外境界欠如は据え置く。** 18 節 6 項および tb2 再検証「否定的結果」がいずれも独立に確認したとおり、当該フックの境界欠如は本コミット由来ではなく（変更前から解決直後に無防備な同種 store 読取があった）、TB-01〜TB2-02 のいずれの処置も新しい露出クラスを作っていない。新規の対応は不要とし、18 節 6 項の記述を維持する。

### 4. 実行結果

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **622 passed**（本ラウンドは文書修正のみで新規テスト追加は無く、18 節時点の件数を維持）。

---

## 20. 隔離実機検証（HERMES_HOME 分離・実カード）による束縛修正の確認と実機新知見の記録（2026-08-24、19 節の続き）

17 節で処置した束縛修正（アンカー優先解決からホスト供給のカード識別子優先への変更、`bc32ca1`。18・19 節の反証レビュー・再検証を経て確証済み）について、17 節が残した残余「本処置後の実機再走行は未実施である」を解消するため、live 資産から分離した隔離環境（`HERMES_HOME=/tmp/pda-iso-verify`）で実 LLM worker により実カード `t_dec48aee` を用いて 3 走行の検証を行った。

### 1. 走行の経過

- 走行1〜2: worker プロセスが解決に用いる task_id が（フックへ届く払い出し形と同様に）カード識別子ではなくセッション識別子であり、契約記録を引けない状態を観測した。17 節の処置が対象とした欠陥形と同一のパターンであり、dispatcher が `HERMES_KANBAN_TASK=<カード識別子>` を worker プロセスの環境変数へ供給し、ゲート側 `resolve_task_binding()` がこれを優先解決する束縛（17 節の実装、`bc32ca1`）が機能する条件を実機で再確認した。
- 途中の blocker: worker 側に git author identity が設定されておらずコミットが実行できない事象が発生した。これはゲート側の欠陥ではなく隔離ハーネス環境の不備（iso worktree に git config が未設定）であり、iso worktree 側へ git config を設定して解消した。worker は blocker を理由付きで正しく報告しており、fail-closed の挙動として正当である。
- respawn guard: `consecutive_failures` の蓄積により dispatcher の Spawned カウントが 0 となる挙動を観測した。カウントのリセットで復帰した。ゲートの束縛・admission とは無関係な dispatcher 側の既存仕様である。
- 束縛修正後の最終走行（成功走行）: task_id=`t_dec48aee` で seed 消費が結合し、ターンは `locked` / `artifact-change` / `contract_origin=assignment` として開始した。decisions は 22 allow / 4 deny、計上対象の denied_count は 0（座礁なし）。scope 外への git diff 系試行は `write-scope` として正しく遮断された。scope 内の write → stage → ローカルコミット（`a5610a5`）作成 → complete までを完走し、ターンは `completed` / `success`、カードは `done` となった。
- 全走行を通じ、live 資産（本番 kanban.db、gate store、オーナーの `~/projects/pda`）は不変であることを確認した。

### 2. 実機で新たに判明した事項（読み取りカタログの false deny 2 件は §21 で処置済み）

- 実在の読み取り専用ツール `skill_view`（スキル定義閲覧）を複数回、および `tool_describe`（ツール schema 閲覧）を、いずれも第一層カタログ（「第一層: write 境界」節の読み取り系ツール許可集合）に含まれないため拒否する事例を実機で確認した。拒否は非計上・座礁なしだが、純粋な読み取りに対する運用上の摩擦になる。
- カタログへの追加は許可集合を広げる方向の変更（allow-set 拡大）に当たるため、本セッションでは実装しない。有効化ゲートにおけるオーナー承認事項として提示する。
- git の `-c` 付き複合形に対する拒否は、既存の tokenizer 方針（未列挙形の default deny for mutation）どおりの挙動であり、対応は不要と判断した。

### 3. 設計文書への反映

上記の結果を `docs/design/task-scope-admission-gate.md` の「S3-M1 worker 配線」節末尾（第 7 項として新設）へ反映した。false deny 2 件のカタログ追加提案が未実装・オーナー判断待ちである旨も同項へ記載した（§21 の処置に伴い当該記載は更新済み）。

---

## 21. 隔離実機検証で判明した読み取り false deny 2 件の処置（2026-08-24、20 節 2 項の続き）

20 節 2 項が未処置として残した false deny 2 件を処置した。20 節が記録した隔離実機検証（`HERMES_HOME` を専用ディレクトリへ切替、実 LLM worker、実カード `t_dec48aee`、3 走行）の結果要約は次のとおりであり、本節の処置はその 3 走行で観測された事象のうち「読み取り拒否」のみを対象とする。

### 1. 隔離実機検証 3 走行の結果要約（20 節 1 項の再掲）

- 走行1〜2: worker が解決に用いる task_id がカード識別子ではなくセッション識別子であり契約記録を引けない状態を観測した。17 節の処置（dispatcher がカード識別子を worker プロセスの環境変数へ供給し、ゲートがこれを優先解決する束縛、`bc32ca1`）が機能する条件を実機で再確認した。
- 最終走行: task_id = カード識別子で seed 消費が結合し、ターンは `locked` / `artifact-change` / `contract_origin=assignment` として開始した。scope 内の write → stage → ローカルコミット作成 → complete までを完走し、ターンは `completed` / `success`、カードは `done` となった。scope 外への変異試行は `write-scope` として遮断された。
- 拒否の計上: 計上対象の denied_count は 0（座礁なし）。
- live 資産（本番 kanban.db、gate store、オーナーの作業ツリー）は全走行を通じて不変である。
- 途中で発生した「git author identity 未設定によりコミット不能」はゲート側の欠陥ではなく隔離ハーネス環境の不備であり、worker は blocker を理由付きで報告した（fail-closed として正当）。
- respawn guard（`consecutive_failures` の蓄積により dispatcher の Spawned カウントが 0 になる挙動）はゲートの束縛・admission と無関係な dispatcher 側の既存仕様であり、カウントのリセットで復帰した。

### 2. 処置: 第一層の読み取り系許可集合への 2 件追加

- 対象は実在の読み取り専用ツール 2 件である: スキル定義（エージェント自身のローカル設定）の閲覧と、ツール schema（エージェント内部メタデータ）の閲覧。
- **分類根拠**: いずれもリポジトリのパスも実行境界も名指さないため、第一層が境界付ける宛先が存在しない。したがって第一層の読み取り系ツール許可集合（`ARTIFACT_READ_TOOLS`、`integrations/hermes-scope-gate/scope_gate.py`）へ加えた。作業記録系カタログではない: 当該カタログは作業管理平面（ボード、作業段階リスト）に作用するツール群であり、それを未 lock 段で許可する根拠（座礁したターンが自らの状態を記録できること）は純粋読み取りには当たらない。
- **本追加の射程（許可方向の変更として正直に記す）**: 読み取り系許可集合に載る名前は全段で許可される。すなわち locked 段・lock 前段に加えて束縛不能経路（`admit_without_turn`）でも許可される。根拠が「境界付ける宛先が無い」ことであり、この根拠はターンの存在に依存しないためである。既に同経路で許可されているファイル読取・検索の露出は本 2 件より広いため、露出クラスは増えない（confidentiality の残余は従来どおり第二層の M2 必須要件 1 で閉じる）。
- **同一語彙群の隣接ツールは追加しない。** スキル定義を書き得るツールはリポジトリのファイルを書き得るためカタログ外を維持し、別ツールの呼び出しを引数に運ぶ形も第一層が境界付けないため含めない。追加は実機で false deny を確認した 2 件に限る。
- 計上規則（`max_denied_calls`）の変更は無い。本 2 件は拒否から許可へ移るのみであり、読み取りの理由コードは D-S3-7 補則の litmus により元から計上対象外である。
- git の `-c` 付き複合形に対する拒否は既存 tokenizer 方針（未列挙形の default deny for mutation）どおりであり、変更対象外とした（20 節 2 項の判断を維持）。

### 3. 根拠を残す形（テストと設計文書）

- 語彙一致テスト（読み取り許可集合が実行中のツール語彙の実在名のみで構成されることを固定する既存テスト）の正本列挙へ 2 件を加えた。
- 新規テスト `test_reads_of_the_agents_own_configuration_plane_touch_no_write_boundary` を追加した。テスト名と本文が分類根拠（エージェント自身の設定・メタデータ面の読み取りであり write 境界に作用しない）を保持し、locked 段・lock 前段・束縛不能経路の 3 段で許可されること（=本追加の射程の全体）と、スキル定義を書き得るツール・別ツール呼び出しを運ぶツールが許可集合外に留まることを固定する。
- 既存の「作業記録系カタログが閉じた明示集合であること」を固定するテストは無変更で通る（読み取り集合との非交差は維持されている）。
- 設計文書 `docs/design/task-scope-admission-gate.md` の「第一層: write 境界」節の読み取り系ツール項へ分類根拠と射程を追記し、「S3-M1 worker 配線」第 7 項の当該事項を実機確認済み・処置済みへ更新した。

### 4. 批准の扱い

**本変更は許可集合を広げる方向（allow-set 拡大）であるため、後段の反証レビューの対象とし、有効化承認シートの明示項目として批准を受ける。** 20 節 2 項が「オーナー判断待ち」としていた論点は「実装するか否か」から「有効化ゲートで批准するか否か」へ移る。批准前の段階で本変更が live に影響しないことは、seed フラグ既定 off（設計文書「有効化経路」第1項）により従来どおり成立する。

### 5. 実行結果

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **623 passed**（19・20 節時点 622 + 新規 1。既存の失敗・skip 無し）。

### §21 補記（レビュー主体の記録、2026-08-24）

本変更（skill_view / tool_describe のカタログ追加）の反証レビューは、Workflow の Opus xhigh レビュアーが機械側安全分類器に制止されたため、司令塔（Fable）による差分直接レビューで代替した。判定は確証欠陥なし: 隣接書込ツール（skill_manage）と呼出搬送ツール（tool_call）のカタログ外維持がテストで固定済み、露出は既存 read 系より狭く新規露出クラスなし、拒否計上規則に変更なし。オーナーは承認シート「ご確認①」および 2026-08-24 チャットで本追加とコミットを承認済み。

### 日付訂正（2026-08-29）

§20・§21 および同時期のコミット・カードコメントが「2026-08-24」と記す出来事（隔離実機検証3走行、installer配備、読取2ツールのカタログ追加と承認、盤面再編）の実施日は、セッション内の日付通知異常による誤記であり、実機時刻で **2026-08-29** が正しい（隔離検証走行は 2026-08-29 02-03時 JST、ゲート有効化と実運転キックは同日 17時 JST）。
