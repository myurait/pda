# S3-M1 worker 配線の反証レビュー（レンズ: 正しさ・互換性、2026-08-23）

- 対象コミット: `f7cfe0f`（基準点 `913214a`、16 ファイル）。
- 照合対象: `docs/design/task-scope-admission-gate.md`「S3-M1 worker 配線」節、司令塔決定（Judgment A / Judgment B / 配線 / 有効化）。
- レンズ: seed → 割当 CAS → 通知の順序と失敗モード、導出の決定論性、承認 metadata スキーマ版上げの両 validator 整合と後方互換、既存テストおよび S1 挙動への回帰、設計文書と実装の一致、停止状態の不変。
- 開発 PC で実行可能な範囲（`integrations/hermes-scope-gate/tests`、および `hermes_cli` を最小スタブへ差し替えた再現）で確証を取り、実行不能な範囲（`operations/improvement/tests`、`integrations/hermes-pda-approvals/tests`）は静的読解と等価な再現で確認した。推測に留まるものは各項の「未確定」に分けて記す。

確証欠陥は 6 件（major 3、minor 3、blocker 0）。blocker が無いのは、`scope_seed.enabled` の既定が false であり、かつ委任方針自体が停止中であるため M1 exit 時点の live 面が変化しないことによる。ただし major 3 件はいずれも次段（ミニPC でのスイート実行と本番有効化）を阻害する。

---

## W-C-01（major）: 割当経路水準の正常系テストが fixture 不足で確定的に失敗する

**事実。** `scope_seed.record_seed` は `load_scope_gate(repo_root)` を経由し、`repo_root/integrations/hermes-scope-gate/scope_gate.py` を明示パスで読み込む。存在しなければ `ScopeSeedError("scope-gate-missing")` を送出する。

`operations/improvement/tests/test_pda_improvement_cycle.py` の `_repo()` fixture が作るリポジトリは `README.md` と `continuity/autonomous-improvement.json` のみを持ち、`integrations/` を持たない。cycle 設定の `repo_root` はこの fixture リポジトリを指す。

したがって本コミットで追加された `test_an_enabled_seed_policy_seeds_a_declared_card` は、seed 記録に到達した時点で `scope-gate-missing` となり、`_record_scope_seed` が汎用文面のカードコメントを残して `CycleError("scope-gate-missing")` を送出する。`run_cycle` は `ok: False` を返すため、当該テストの `assert result["assigned"] == [task_id]` は必ず失敗する。

**再現（開発 PC で確認済み）。** fixture と同形（`integrations/` を持たない Git リポジトリ）を作り、宣言済みカード本文を渡して `record_seed(repo_root=<fixture>, ...)` を呼ぶと `kind="scope-gate-missing"`。同じ fixture へ `integrations/hermes-scope-gate/scope_gate.py` と `operations/improvement/scope_seed.py` を配置すると seed 記録は成功し、`write_paths` / `git_write` / `execution` / `test_paths` は設計どおりの既定値になる。

**影響。**

1. 未実行と申告されたスイートは green ではない。ミニPC 実行で確定的に 1 件失敗する。
2. より重いのは、この失敗により**割当経路水準の正常系が未検証のまま残る**ことである。`integrations/hermes-scope-gate/tests/test_scope_seed_wiring.py` は `_route_task` を直接呼ぶ経路で正常系を押さえているが、`run_cycle` が委任方針から seed フラグを読み、`repo` を `_route_task` へ渡し、seed store の既定解決（`HERMES_HOME` 由来）で記録するまでの一連は、この 1 件だけが覆っていた。
3. 同ファイルの `test_an_enabled_seed_policy_refuses_a_card_without_a_scope_declaration` は通るが、それは宣言欠落の判定が `derive_seed_payload` で行われ、ゲート読み込みより前に返るためである。したがって「拒否側は通る／正常系だけ落ちる」という、原因を見誤りやすい失敗の形になる。

**判断が必要な点。** 修正の方向は 2 つある。(a) fixture に `integrations/hermes-scope-gate/scope_gate.py`（と必要なら `operations/improvement/scope_seed.py`）を配置して実リポジトリ相当にする。(b) `record_seed` のゲート解決を `repo_root` 依存から外す。(b) は「割当プロセスが参照するゲート実装の出所」を変える設計変更であり、現行の出所選択（下記「確認して問題の無かった点」4）には別の妥当性があるため、本レビューは (a) を推す。ただし fixture 側でゲート実装を持たせると、そのテストは実装本体のコピーに依存する点を明示すべきである。

---

## W-C-02（major）: 宣言の無いカード 1 枚が割当 queue 全体を停止させる

**事実。** `_route_task` は宣言欠落・宣言不受理のいずれでも `CycleError` を送出する。`run_cycle` の割当ループはこの例外を捕まえず、関数外側の `except CycleError` まで伝播して打ち切る。`_eligible_tasks` は優先度順であるため、**優先度が最も高い Ready カードが宣言を持たない場合、以降のカードは 1 枚も割当されない**。次周期も同じカードが先頭に来るため、状態は自己回復しない。

**再現（開発 PC で確認済み）。** `hermes_cli.kanban_db` を最小スタブへ差し替え、宣言なしカードと宣言済みカードを Ready で並べ、宣言なし側を高優先度にして `run_cycle` を回した結果:

- 戻り値 `{"ok": false, "assigned": [], "error_kind": "missing-scope-declaration", ...}`
- ボード上の両カードとも `assignee` は未設定のまま
- 記録された副作用は宣言なしカードへのコメント 1 件のみ

順序を入れ替え（宣言済みを高優先度）た場合は、宣言済みカードのみが割当・通知され、後続の宣言なしカードで打ち切られる。

**本番設定での形。** 委任方針の `max_assignments_per_tick` は 1 である。したがって毎周期 1 枚しか見ないため、**先頭カードが宣言を持たない限り queue は完全に止まる**。有効化初日は既存 Ready カードのいずれも宣言欄を持たない（欄自体が本コミットで新設されたもの）ため、停止は確実に起こる。さらに `_comment_once` により同一文面のコメントは 1 回しか残らないので、2 周期目以降はカード上に新しい痕跡が出ない。運用者に見えるのは cycle の戻り値だけである。

加えて `_ensure_worktree` は seed 検査より前に走るため、**割当されないカードにも worktree と branch が作られる**（作成自体は冪等なので増殖はしない）。

**設計との関係。** 司令塔決定の文面は「宣言なしは割当せず CycleError＋カードコメント」であり、設計文書も「宣言の無いカードは割当しない（エラーとし、カードへ一度だけ理由をコメントする）」と書く。**当該カードを飛ばして後続を処理する形も、この文面を同じだけ満たす。** 周期全体を打ち切るのは実装側の選択であり、決定事項ではない。

**判断が必要な点。** (a) 当該カードのみ skip して次の候補へ進む（queue は流れるが、宣言欠落が静かに残り続ける）。(b) 現行どおり打ち切る（fail-closed だが先頭 1 枚で全停止）。(c) 打ち切りは維持し、有効化前提として「全 Ready カードへ宣言を入れる移行手順」を運用手順へ明記する。有効化が次 gate の承認事項であることを踏まえると (c) は最小変更で成立するが、その場合は「先頭カードが queue を止める」性質そのものを設計文書の配線節へ明記し、批准対象に含めるべきである。

---

## W-C-03（major）: 承認 metadata のスキーマ版上げが既存 v1 承認を消費不能にする（移行経路なし）

**事実。** Judgment A の実装で、両 validator は次の 2 規則を持つ。

- `schema_version` が 2 以外ならエラー
- `git_common_dir` / `git_dir` が**存在すれば**エラー（値の妥当性ではなく存在自体を拒否）

v1 の worker 作成オブジェクト（`schema_version: 1` かつ当該 2 欄を持つ）は、この 2 規則で 3 件のエラーになる。開発 PC で installer 側 validator を直接呼んで確認済み。plugin 側は同一挙動であることを両実装の突き合わせで確認済み（下記「確認して問題の無かった点」1）。

**帰結を経路別に分けると:**

1. **消費済み（`consumed_at` が入っている）行**: `verify_owner_approval` と `_existing_approval` はいずれも `consumed_at IS NULL` で絞るため、再検証されない。影響なし。
2. **未消費行の再承認（冪等 replay）**: `approve_task` の replay 経路は `validate_approval(task_id, prior_approval)` を通るため 409 になる。
3. **未消費行の消費**: `install.py::_verify_approved_artifact` は `task_runs.metadata.pda_approval`（= worker 作成オブジェクト）に対して `_validate_approval_contract` を呼ぶため、`approved approval contract is invalid: ...` で `ValueError` になる。
4. **移行・grandfathering は存在しない。** 台帳のカラムは無変更だが、v1 オブジェクトを受理する分岐や、`schema_version` を見て 2 欄の扱いを切り替える分岐は無い。

**復旧経路（確認済み）。** 台帳は `UNIQUE(task_id, review_run_id, digest)` であり、`_existing_approval` は digest 鍵である。したがって新しい review handoff（v2 オブジェクト）を出し直して再承認すれば、新しい `review_run_id` と digest で新規行が入る。旧 v1 行は未消費の孤児として残るが、digest が違うため新経路と衝突しない。**データ経路は失われないが、レビュー差戻し相当のやり直しとオーナー再承認が必要になる。**

**未確定（ミニPC の実機事実）。** 台帳に未消費の v1 行が実在するか、実在するなら何件か。開発 PC からは確認できない。実在する場合は上記 2・3 が現実に発生する。

**判断が必要な点。** (a) 現行どおり（実在するなら再ハンドオフでやり直す）。(b) `schema_version == 1` かつ当該 2 欄が実地導出値と一致する場合に限り受理する互換分岐を消費経路へ置く。(b) は「検査主体がいなくなった欄を digest の中で通さない」という Judgment A の狙いと衝突するため、実在件数が 0 か少数なら (a) が整合する。いずれにせよ**有効化手順書へ「本コミット以前の未消費承認は再ハンドオフが必要」を明記する必要がある**。現状どの文書にも書かれていない。

---

## W-C-04（minor）: 宣言例が必須の情報文字列を欠いており、そのまま写すと認識されない

**事実。** `parse_scope_declaration` は情報文字列を厳密一致で照合する。`docs/operations/pda-improvement-cycle.md` の当該節は、直前の散文で情報文字列が必要だと述べた上で、唯一の例を**情報文字列の無い素のフェンス**として示している（54 行目が要件を述べ、56 行目のフェンスがそれを満たしていない）。例を写したカード本文は認識ブロック 0 件となり、`missing-scope-declaration` になる。

`operations/improvement/daily_reconciler_prompt.txt` の例はさらに弱く、フェンスすら無い素の JSON 一行として示されている。直前の箇条書きが情報文字列とフェンスを要求しているため辛うじて成立するが、例が要件を満たしていない点は同じである。

**影響。** 単独では文書不備だが、W-C-02 と組むと「例のとおり書いたカードが queue 全体を止める」という形になる。specifier（`daily_reconciler_prompt.txt` を読む主体）が生成するカードにも同じ risk がある。

**併記。** `parse_scope_declaration` は未知キーを拒否する。この挙動はどの文書にも書かれていない。宣言可能なキーが 4 つだけであることは書かれているが、それ以外を書いたら拒否されるとは読み取れない。

---

## W-C-05（minor）: クラス既定の定数が二重定義で、突き合わせテストが無い

**事実。** `scope_seed.CLASS_DEFAULT_GIT_WRITE` と `scope_gate.ARTIFACT_GIT_WRITE_ACTIONS` は現時点でどちらも同じ 2 要素だが、両者を等しいと固定するテストが無い。`scope_seed` はこの定数だけで「縮小のみ」判定を行うため、片側が動いたときの帰結は次のとおりである。

- ゲート側が増えた場合: カードは新しい action を宣言できない（`scope_seed` が widen と誤判定して拒否）。実質は false deny。
- ゲート側が減った場合: `scope_seed` は通すがゲートが拒否する。fail-closed だが、拒否理由が割当時に出るためカードコメントは汎用文面になる。

**同コミット内の不整合。** 同じ「独立実装を突き合わせで固定する」規律は承認側では実施されている（`plugin.APPROVAL_METADATA_SCHEMA_VERSION == install_module.APPROVAL_METADATA_SCHEMA_VERSION` と `GATE_DERIVED_IDENTITY_KEYS` の等値アサート、および両 validator の挙動 parity ケース）。seed 側に同じ固定が無いのは同一コミット内の規律の非一貫である。

---

## W-C-06（minor、基準点から存在。本コミットで常態化）: 周期内で一部割当が成功した後の失敗が「割当ゼロ」として報告される

**事実。** `run_cycle` の `except CycleError` は `assigned: []` を固定で返す。割当ループは成功ごとに `assigned.append` するが、途中で `CycleError` が出ると蓄積分は捨てられる。

**再現（開発 PC、`max_assignments_per_tick: 2`）。** 宣言済みカードを先頭、宣言なしカードを次に置くと、宣言済みカードは seed 記録・CAS・通知まで完了し、ボード上も `assignee` が入る。にもかかわらず戻り値は `{"ok": false, "assigned": [], ...}` である。`wip` も欠落する。

**評価。** 基準点でも `_ensure_worktree` の `workspace-collision` / `dirty-worktree` や `claim-race` で同じ形になり得たため、本コミットの回帰ではない。ただし基準点では周期中断は例外的事象だったのに対し、本コミット後は「宣言の無いカードが 1 枚ある」という日常的な盤面が中断要因になる。本番設定は `max_assignments_per_tick: 1` なので現状の live 形では発生しないが、per-tick を増やした時点で常態化する。

---

## 確認して問題の無かった点（レンズ被覆の記録）

1. **両 validator の挙動 parity。** plugin 側と installer 側の validator を同一プロセスへ読み込み、追加された 3 ケース（`git_dir` 宣言・`git_common_dir` 宣言・`schema_version: 1`）と既存 3 ケースでエラー配列を突き合わせた。順序を含めて完全一致。定数（スキーマ版・導出キー集合）も一致。`test_plugin_and_installer_validators_agree_on_behavior` に追加された parity ケースは、ミニPC で通る。
2. **seed → CAS → 通知の順序と失敗モード。** 割当イベント発火時点で seed が存在することを確認するテストが `integrations/hermes-scope-gate/tests` 側にあり、通知が最後であること、宣言欠落時に CAS・通知のいずれも起きないこと、宣言編集時に既存 seed が保たれること、繰り返し不成立でもコメントが 1 件に留まることを、いずれもローカル実行 green で確認した。孤児 seed が次周期の冪等経路を通ることも設計どおり。
3. **導出の決定論性。** `derive_seed_payload` は正規化・並べ替え・重複除去を一切行わずゲートの正規化関数へ委ねている。同一カードからの再導出が同一 payload になることをテストが固定している。`git_write` 省略時は `None` を渡してゲートのクラス既定に委ねるため、明示宣言（クラス既定と同一集合）との間でも payload が一致する。
4. **割当プロセスとゲートの実装同一性。** ゲートの installer はプラグインディレクトリを**リポジトリのソースへの symlink** として設置する（`plugin_path.is_symlink() and plugin_path.resolve() == source_path`）。したがって seed を書く側（`repo_root` 経由でリポジトリのゲートを読む）と強制する側（プラグイン経由）は同一ファイルであり、版ずれは起きない。当初懸念した「リポジトリが先行して installed が古い」構成は成立しない。
5. **`PathRejected` の捕捉。** `PathRejected` は `ValueError` の派生であるため、パターン構文誤り・絶対パス・上位参照・件数超過・未知 action・未知テンプレートはすべて `record_seed` の `except ValueError` で `ScopeSeedError("scope-seed-rejected")` へ変換される。カードコメント経路を素通りして traceback で落ちる形にはならない。
6. **S1（closeout）挙動への回帰。** 本コミットは `scope_gate.py` を一切変更していない。`integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` を除く）は 535 passed（基準点 506 + 新規 29）。
7. **停止状態の不変。** `continuity/autonomous-improvement.json` の `enabled` は false のまま、`suspension` ブロックは無変更。追加されたのは `scope_seed` ブロック（`enabled: false` と説明）のみ。既定 off をリポジトリの正本ファイルに対して固定するテストがある。
8. **新設モジュールの統治面被覆。** 新規 `operations/improvement/scope_seed.py` は `GOVERNANCE_PATHS` の `operations/improvement/` に含まれるため、worker の finalization が自分の上限導出コードを変更する経路は既に閉じている。
9. **Judgment A の drift 検査 2 点性。** 承認時は同一トランザクション内の導出値を台帳へ書き、消費時は実地再導出を台帳行（`marker`）と比較する。設計ノート §6 が記録した「消費時比較先が worker オブジェクトだった」という事実誤認の訂正は妥当であり、`marker` への変更は司令塔決定（消費時の実地再導出と台帳比較を維持）と整合する。replay 経路にも `_identity_drift_errors` が入り、移動した worktree に対する replay が通らないことを確認した。`verify_workspace` は導出失敗時に `identities` を `None` へ戻すため fail-closed。
10. **処置台帳の記述。** 引継ぎ記述の更新箇所は 13 節の「7. 本ラウンド後の残余」であり、実装サマリの「§13-7」は正しい参照である（節番号がリテラル文字列として現れないだけ）。10 節 4 の 2 残余が Judgment A / B で閉じた旨の追記も、設計文書側の追記と整合している。

---

## 未確定（ミニPC でのみ確定できる事実。本レビューでは判定しない）

- 台帳に未消費の v1 承認行が実在するか（W-C-03 の現実の影響範囲）。
- `operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` の実行結果。W-C-01 の 1 件は確定的に落ちる見込みだが、他に落ちるものが無いことは実行でしか確認できない。
- cycle プロセスと gateway プロセスが同一の seed store を解決すること、および割当プロセスの実行ユーザーが当該ファイルへ書けること（設計ノート §3.5B の 3）。`record_seed` は `state_path` 未指定時にゲートの既定解決（`HERMES_HOME` 由来）へ委ねるため、両プロセスの `HERMES_HOME` が異なると seed は記録されるが強制されない構成になり得る。この不一致は fail-open 方向であり、W-C-02 の停止とは違って表面化しない。
