# S3-M1 実装 反証レビュー記録（fidelity レンズ、2026-08-23）

- Status: open（確証欠陥 7 件。うち 5 件は M1 exit 判断前の処置が要る）
- 処置: `docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md`（2026-08-23。全確証欠陥の処置と、司令塔判断へ回付した項目の対応表）
- 読み取り方針: **本ファイルは `restricted-` 接頭辞の対象。迂回手法の具体形を含むため、Fable モデルのセッションでは直接読まない。** 対応は Opus のサブエージェントへ委譲し、本体へは欠陥ID・抽象名・判断項目のみを返す。
- レビュー対象コミット: `4f3d22f`（feat: artifact-changeの二層契約と契約ライフサイクルをスコープゲートへ実装）
- 正本設計: `docs/design/task-scope-admission-gate.md` の「S3-M1: 決定論コアの具体設計」（契約の拡張／lock／第一層／第二層／G3と予算／契約ライフサイクル 1〜8項／M2への残余）
- レンズ: 設計適合（無断のスコープ縮小・拡大、必須項目の実装漏れ、チェックリスト項目の消化漏れ）
- 確証欠陥: 7 件（blocker 0 / major 5 / minor 2）、棄却 3 件（末尾「棄却した疑い」）
- 再現スクリプト: `tmp/verify_fidelity.py`, `tmp/verify_fidelity2.py`（git 管理外。`./tmp/venv-scope/bin/python` で実行）
- テスト再実行: `./tmp/venv-scope/bin/python -m pytest integrations/hermes-scope-gate/tests -q --ignore=integrations/hermes-scope-gate/tests/test_hermes_integration.py` → 199 passed（実装サマリの申告と一致）

## blocker が 0 である根拠

第一層の硬い境界そのものは、割当 seed レーン（`origin: assignment`）では実測で保持されている。

- seeded ターンで、同一セッションに 2 通目のユーザーメッセージが来た後も新ターンが seed から再 lock され、ロック済み worktree 外への書込は `target-closed` で拒否される（`tmp/verify_fidelity2.py::probe_seeded_lane_second_message`）。
- seeded タスクでターンへバインドできない呼び出しは、読み取り以外が `contract-unbound` で拒否される（実装テスト `test_an_unbindable_call_on_a_seeded_task_denies_mutation`）。
- ロック済みターン内の write / stage / commit / 第二層実行は、いずれも write scope 照合・実体解決・全トークン走査を通る（実装テスト群および `tmp/verify_fidelity.py` の probe で確認）。

したがって M1 exit gate が主張する範囲（第一層・seeded レーン）に境界の敗北はない。以下の major は「自己 lock レーンでの強制の消失」「強制段の予算未適用」「担保層の置き場所の誤り」であり、seeded レーンの write 境界を直接破るものではない。

## 確証された欠陥

### I-FID-01 [major] lock 前段および契約検証失敗段にクラス予算が適用されていない

**根拠**

設計「契約ライフサイクル」第2項は、artifact-change 専用の discovery 予算を新設しない代わりに「上限はクラス予算（wall time / tool calls）とする」と明記する。D-S3-4 の決定は lock 前の無制限許可を **bounded な** 既定拒否段へ置き換えることであり、bounded 性の供給源はクラス予算だと設計が指定している。

実装では `GateStore._artifact_change_decision`（`integrations/hermes-scope-gate/scope_gate.py:1927-1947`）の `pre-lock` 分岐が `denied_count >= max_denied_calls` のみを検査し、`state == "mutation-denied"` 分岐（同:1939-1947）は予算検査を一切持たない。wall time と tool calls の検査は `_admit_artifact_change_locked`（同:2546-2557）にしかなく、`locked` 状態にしか効かない。

重要なのは、`mutation-denied` は既定 off のフラグに依存せず **今日 seeded レーンで到達可能**な状態である点（`start_turn` は seed 実体検証に失敗したターンを `mutation-denied` にする。同:960-964）。したがって本欠陥は `ARTIFACT_CHANGE_PRELOCK_ENFORCED` の既定値とは独立に露出している。

**再現**（`tmp/verify_fidelity2.py::probe_prelock_bounds` / `probe_wall_budget_in_prelock`）

- `enforce_artifact_change_pre_lock=True` の `pre-lock` ターンで `read_file` を 200 回連続 admit → 200 回とも allow、`turns.tool_count` が 200（クラス予算 `max_tool_calls = 96` を超過）。
- 同ターンの `started_at` を 0 に書き換え（wall budget 完全経過相当）→ `read_file` はなお `inspect-before-lock` で allow。
- branch 不一致 seed で `mutation-denied` に落としたターンでも `read_file` 200 回 allow。

**修正方針**

`pre-lock` と `mutation-denied` の両分岐で、`locked` 分岐と同じ順序（wall → tool → deny）でクラス予算（`ARTIFACT_CHANGE_CLASS_BUDGET`）を検査する。`locked` は契約 budget、未 lock 段はクラス既定値を引く形でよい。受入テストは「予算超過後の読み取りが `wall-budget` / `tool-budget` で拒否される」を pre-lock と mutation-denied の双方に置く。

### I-FID-02 [major] 明示的に閉じたターンで、ターン束縛の喪失により変異が許可される

**根拠**

設計「契約ライフサイクル」第4項の規範要件は「閉じたターンでは変異系を拒否したままにする」。実装は `turn_id` を直接与えた場合はこれを満たす（`admit_tool` → `turn-closed`）。しかし runtime のツールフックは `turn_id` を host から受け取れないことを前提に `resolve_turn_id`（同:1018-1054）へ委ねており、この関数は `completion_status IS NULL` の行しか返さない。閉じたターンは解決対象から外れ、`ScopeGatePluginRuntime.pre_tool_call`（`plugin_runtime.py:79-96`）は `admit_without_turn` へ落ちる。`admit_without_turn`（`scope_gate.py:1954-1980`）は seed が無ければ `not-enforced` を返す。

結果、自己 lock レーン（seed 無し・`origin: self`）では、明示的な `complete` の後にロック済み worktree 外への書込が許可される。

`pre_llm_call` が `turn_id` 未指定時に `f"{session_id}:{sha256(user_message)[:16]}"` という合成キーでターンを作る（`plugin_runtime.py:292-303`）ため、ツールフック側がこのキーを持たない構成は実装自身が前提としている。よって本経路は理論上のものではない。

**再現**（`tmp/verify_fidelity.py::probe_closure_after_complete`）

自己 lock（`write_paths=["src/*.py"]`）→ `finalize_turn(status="success")` → `state == "completed"`。
- `turn_id` 直指定の `admit_tool`: deny（`turn-closed`）。
- `resolve_turn_id(session_id="s1")`: 空文字列。
- `runtime.pre_tool_call(session_id="s1", tool_name="write_file", args={"path": "/etc/anything"})`: `None`（= 許可）。

**設計テキスト側の緊張**

実装テスト `test_an_unbindable_call_on_a_seeded_task_denies_mutation` は `unseeded.allowed is True` を明示的に固定している。これは第4項の「バインディング不能時は fail-closed」が「当該タスクに seed が存在する場合」と条件付きで書かれていることの字面どおりの実装であり、実装者の見落としではない。第4項は同時に「閉じたターンでは変異系を拒否したままにする」を無条件で要求しており、seed の無いターンでは両者が衝突する。処置には設計本文の整合（どちらの条件が優先か）が必要。

**修正方針**

`resolve_turn_id` を「解決可能な最新ターン」へ広げ（`completion_status` の有無で除外しない）、閉じたターンに束縛された変異は `turn-closed` で拒否する。あるいは `admit_without_turn` の fail-closed 条件を「seed が存在する場合」から「当該 session / task に強制対象クラスのターンが存在した場合」へ広げる。いずれを採るかは設計本文の第4項を先に確定させる（司令塔判断 2）。受入テストは runtime 経路（`pre_tool_call` に `turn_id` を渡さない形）で書く。既存の `test_a_closed_turn_keeps_denying_mutation` は `turn_id` 直指定であり、この経路を覆っていない。

### I-FID-03 [major] 開いたままの locked 契約が、同一セッションの後続ターンに影を落とされて強制が消える

**根拠**

I-FID-02 と根本原因（「最新の未完了ターン」に基づく契約非対応のターン束縛）を共有するが、違反する規範が別である。設計第4項は「強制クラスのターンを中間の監査フックで閉じない」＝ closure は明示のみ、と定める。実装は `post_llm_call`（`plugin_runtime.py:266-276`）で強制状態の artifact-change ターンを閉じずに返す（設計どおり）。その結果、当該ターンは明示 `complete` まで `completion_status IS NULL` のまま残る。

ここで同一セッションに次のユーザーメッセージが来ると `pre_llm_call` が新しいターン行を作る。`resolve_turn_id` は `started_at DESC LIMIT 1` で最新の未完了ターンを返すため、以後のツール呼び出しは **新しい（多くは `audit-only` の）ターン**へ束縛され、まだ locked のままの artifact-change 契約は参照されない。閉じてもいないのに強制が消える。

seeded レーンではこの経路が塞がっている。seed が消費後も上限として有効なまま（実装サマリで宣言された逸脱）であるため、新ターンも seed から再 lock され `locked` になる（`tmp/verify_fidelity2.py` で実測）。露出は自己 lock レーンに限られる。

**再現**（`tmp/verify_fidelity.py::probe_newer_turn_shadow`）

自己 lock 済みターン（`write_paths=["src/*.py"]`、`completion_status` は NULL）を保持したまま、同一 session で 2 通目のメッセージを `pre_llm_call` へ渡す → `resolve_turn_id` は新ターン（`audit-only`）を返し、`pre_tool_call(tool_name="write_file", args={"path": "/etc/anything"})` は `None`（許可）。

**付随して確認した状態残留**

`on_session_end`（`plugin_runtime.py:280-290`）は「completed かつ failed/interrupted でない」セッションで早期 return するため、正常終了したセッションの artifact-change ターンも開いたまま DB に残る。同一 `task_id` を再利用する後続セッションでは、この古い locked 契約が `resolve_turn_id(task_id=...)` で解決されうる（seeded レーンでは新ターンが作られるため実害は小さいが、自己 lock レーンでは古い契約での強制になる）。処置は I-FID-02/03 の束縛規則の見直しと同一箇所で行う。

**修正方針**

ターン束縛を「最新」ではなく「強制対象クラスの未完了ターンを優先し、無ければ最新」へ変更する。より根本的には、artifact-change の強制単位を「ユーザーターン」ではなく「タスク（seed / 自己 lock 契約）」に置き、`resolve_turn_id` が契約の有無を見るようにする。I-FID-02 と同一の修正で両方が閉じるため、工数は二重に数えない。

### I-FID-04 [major] 自己 lock が既存の割当 seed を照会しない

**根拠**

設計「契約ライフサイクル」第1項は「seed があるターンで lock が要求された場合は、seed 契約をそのまま冪等に返す。seed を超える宣言は拒否する」と定め、INV-S8（書込境界を実行主体の自発的宣言に依存させない）をその根拠に置く。

実装の `_lock_artifact_change`（`scope_gate.py:1220-1298`）は「seed があるターン」を **ターンの state が `locked` であること**で判定する。`get_contract_seed` は一度も呼ばれない。seed 上限の担保は「`start_turn` が seed を見つけて先に lock していたこと」に完全に依存しており、その前提は host が `task_id` を正しく渡し、かつ seed の記録がターン開始より前であることに依存する。担保層が INV-S8 が排除しようとしたもの（実行主体側の経路と host 配線）に置かれている。

**再現**（`tmp/verify_fidelity.py::probe_seed_not_consulted_on_self_lock`）

- ケース1: `task_id` を伴わずターン開始（対話ターン相当）→ 後から `record_contract_seed(task_id="TASK-1", write_paths=["src/a.py"])` → 自己 lock で `write_paths=["**"], test_paths=["tests/**"], execution=["focused-test"]` が **成立**（`origin: self`）。seed の上限は一切効かない。
- ケース2: `task_id` を渡してターン開始（seed 先行）→ 自己 lock による widen は `the declared scope exceeds the assigned contract seed` で拒否。

つまり設計が要求する不変条件は、ターン開始時の順序と `task_id` の有無という外部条件が揃った場合にのみ成り立つ。

**修正方針**

`_lock_artifact_change` の入口で、ターンの `task_id` に対する `get_contract_seed` を引く。seed が存在すれば（ターン state が `locked` でなくとも）seed を天井として `write_paths` / `test_paths` / `execution` / worktree の包含検査を行い、超過は拒否する。seed があるのにターンが `locked` でない場合（記録順序の逆転、`task_id` の欠落）は fail-closed とし、seed から契約を再構築するか lock を拒否する。受入テストは上記ケース1をそのまま拒否側に固定する。

### I-FID-05 [major] 書込先収集で、宣言済みの入れ子コンテナが想定外形状のとき黙って検査対象外になる

**根拠**

設計「第一層」は「書込先の識別はツールカタログで行う」「単一パス、パス配列、変更元と変更先の対を持つツールを区別して、**書込先になりうる全フィールドを検査する**」と定める。実装のモジュール冒頭コメント（`scope_gate.py:428-436`）も「a listed tool that carries none of its declared destination fields is denied rather than silently admitted」と宣言している。

`collect_write_targets`（同:517-550）の 3 分岐のうち、`listed` 分岐は配列でない値に対して `PathRejected("target-shape")` を上げる（同:534-535）。しかし `nested` 分岐（同:538-544）は、宣言済みコンテナが存在するのに配列でない場合 `continue` で **黙って読み飛ばす**。他の宣言フィールド（`path` 等）がスコープ内であれば `found` は非空になり、呼び出し全体が allow される。非対称であり、境界コード内の既定 open 分岐である。

**再現**（`tmp/verify_fidelity.py::probe_nested_container_shape`）

- `collect_write_targets("multi_edit", {"path": "src/a.py", "edits": [{"path": "src/b.py"}]})` → `('src/a.py', 'src/b.py')`（両方が検査対象）。
- `collect_write_targets("multi_edit", {"path": "src/a.py", "edits": {"0": {"path": "/etc/passwd"}}})` → `('src/a.py',)`。`edits` 内の書込先は検査されず、`src/a.py` がスコープ内であれば admission は allow になる。
- 対照: `collect_write_targets("write_files", {"files": {"0": "/etc/passwd"}})` → `target-shape` で拒否（`listed` 分岐は正しく閉じている）。

**露出の限定（正直に付す）**

現行カタログで `nested` を持つのは `multi_edit` のみであり、Hermes 実ランタイムがこの名前・この引数形状のツールを提供している証跡は本レビューでは得ていない。したがって現時点では潜在欠陥である。ただしカタログは将来拡張される前提の表であり、既定 open のまま拡張されると露出が生じる。

**修正方針**

`nested` 分岐を `listed` 分岐と同じ規則に揃える。コンテナが存在して配列でなければ `PathRejected("target-shape")`、配列要素が dict でなければ同様に拒否、`item_field` が dict にあれば収集。加えて「宣言済みコンテナが present なのに 1 件も書込先を出さなかった場合」も拒否する。受入テストは上記 3 形状（正常配列 / dict コンテナ / 非 dict 要素）をパラメタ化して固定する。

### I-FID-06 [minor] admission の dispatch テーブルが admission 本体では load-bearing でない

**根拠**

設計「契約ライフサイクル」第7項のチェックリスト第2項は「admission を task class の dispatch テーブルへ一般化し、G3 の『既に契約が許可している』判定も同じ dispatch を用いる」。

実装は `_LOCKED_ADMISSION_DISPATCH`（`scope_gate.py:2612-2615`）を追加し、G3 の第二段はこれを `locked_admission_for` 経由で引いている（同:1521-1523）。しかし admission 本体は依然ハードコード分岐である。

- `admit_tool`（同:1783-1796）が task class で if/elif し、`_closeout_decision` / `_artifact_change_decision` を直接呼ぶ。
- `_artifact_change_decision`（同:1916）が `_admit_artifact_change_locked` を直接呼ぶ。
- `lock_turn`（同:1083-1106）も task class の if/elif。

同じ関数オブジェクトを指しているため今日の挙動は一致しており、動作上の差異はない。ただしテーブル項目を編集しても admission は変わらないため、設計が意図した「新しく強制されるクラスがどちらの場所にもハードコード分岐を必要としない」状態には到達していない。チェックリスト項目の消化漏れ。

**修正方針**

`admit_tool` の class 分岐と `_artifact_change_decision` の locked 呼び出しをテーブル参照へ置き換える（`locked_admission_for(task_class)`）。`lock_turn` は per-class の契約構築テーブル（`_LOCK_DISPATCH`）を別に持つ形でよい。テーブルと実挙動の一致を検査するテスト（既存の `test_the_catalogue_and_the_admission_dispatch_are_wired` の拡張）を置く。

### I-FID-07 [minor] スキーマの closeout 条件節に必須キー宣言が伴っていない

**根拠**

設計「契約の拡張」の「スキーマ記述規律」は「新設フィールドの class 別必須化は、条件節の下に必須キー宣言を伴わせる。プロパティ形状の宣言だけでは欠落を検査できず、上記の既存バグと同種の空振りが再発する」と定める。

`schemas/scope-contract-v1.schema.json` の `allOf` 3 分岐のうち、`bounded-operation` と `artifact-change` は `then.required` と `budget.required` を伴う（既存の実在しないキーへの制約バグもここで修正済み。`minutes`/`tool_calls` → `max_wall_seconds`/`max_tool_calls`）。`repository-closeout` 分岐のみ `then.required` も `budget.required` も無く、`budget` の上限制約だけを宣言している。

現状はトップレベル `required` が `budget` を含み、`budget` オブジェクト自身が 6 キー全てを `required` にしているため空振りは起きない（`tmp/verify_fidelity.py::probe_schema_gaps` で 3 分岐の宣言状態を確認）。よって実害はなく minor。ただし設計が明示した記述規律への不適合であり、`budget` のトップレベル必須が将来緩んだ瞬間に closeout 分岐だけが空振りへ戻る。

**修正方針**

`repository-closeout` 分岐に `then.required: ["budget"]` と `budget.required: ["max_wall_seconds", "max_tool_calls", "max_expansions"]` を追加し、3 分岐の記述形を揃える。

## 司令塔判断が要る項目

1. **lock 前段の有効化単位**: `ARTIFACT_CHANGE_PRELOCK_ENFORCED = False`（`scope_gate.py:2171`）は lock 前段を **全レーン**で無効化する。設計第8項の M2 分岐が免除しているのは「自律 worker レーンでの強制」だけであり、seed 配線に依存しない自己 lock レーン（対話ターン）まで既定 off にするのは設計より広い。実装サマリで宣言済みだが、設計本文への反映または明示的批准が必要。現状、seed の無い artifact-change ターンは分類直後から `audit` であり、第一層は lock されるまで一切効かない（`tmp/verify_fidelity.py::probe_prelock_default` で確認）。

2. **I-FID-02 / I-FID-03 を M1 exit の阻害とみるか**: 両者は自己 lock レーン限定であり、seeded レーンは実測で安全。設計第4項の「閉じたターンでは変異系を拒否したままにする」（無条件）と「バインディング不能時は fail-closed」（seed 条件付き）が衝突しているため、どちらを優先するか設計本文を確定させる必要がある。`origin: self` の弱保証残余として受容するか、束縛規則を修正して M1 に含めるかの判断。

3. **seed の恒久有効化の設計反映**: 実装は seed を「初回消費で記録を残すがタスク全体の上限として有効なまま」にした（実装サマリで宣言済みの逸脱）。この逸脱は単なる利便ではなく、seeded レーンが複数ターンにわたって強制を保つための **必須条件**であることが実測で確認された（`tmp/verify_fidelity2.py::probe_seeded_lane_second_message`）。設計本文の「ゲートはターン開始時にこの seed を消費し」を、恒久上限として書き直す判断。

4. **terminal 経由の読み取り専用 git の deny と拒否上限 6 の相互作用**: 実装は artifact-change の terminal で `git add` とメッセージ付き `git commit` のみを許可し、`git status` / `git diff` 等を deny する（設計記載外の拡張を避ける厳密読み。実装サマリで宣言済み）。ここで宣言されていないのは費用側で、コミット前に状態確認を行う通常の運用では拒否が `denied_count` を消費し、`max_denied_calls = 6`（実装側で確定した値。設計に記載なし）に到達するとターンが座礁しうる。`scope_gate` の `lock` / `complete` は上限後も到達可能に保たれているが、作業自体は続行できない。読み取り専用 git を第一層へ加えるか、拒否上限を引き上げるか、運用手順で禁止を明示するかの判断。

## 棄却した疑い（確証に至らなかった、または設計どおりと判定）

- **lock 時のシンボリックリンク検査が glob の静的接頭辞までしか降りない**（`verify_scope_prefixes_are_inside_root`）: 設計は「`write_paths` / `test_paths` が指す範囲の祖先ディレクトリ」の検査を求めており、ワイルドカード以降の実体は書込時の `resolve_existing_ancestor` が必ず実体解決する。安全性は書込時検査に包含されるため欠陥としない。
- **自己 lock で `write_paths: ["**"]`（リポジトリ全域）が通る**: 設計は自己 lock の検査を「クラス上限（単一 worktree、相対指定、件数上限）」に明示限定しており、`**` は 3 条件すべてを満たす。設計は自己 lock 由来契約を「監査上は弱い保証」と明記しているため、設計どおりの挙動。運用上の含意は司令塔判断 2 に含めた。
- **パス正規化が 2 関数（レキシカル正規化と実体解決）に分かれている**: 設計は「単一の決定論関数へ集約する」と書くが、実装は 3 つの呼び出し箇所すべてで両者を対で呼んでおり、検査内容（要素の完全解決、上位参照の不在、制御文字の不在）は設計の指定どおり揃っている。現時点で抜けのある呼び出し箇所は無いため欠陥としない。
- **第二層の標準入力起動形態の固定**: 設計は「deny する（または標準入力を空へ固定する）。いずれを採るかを M1 の受入テストで固定する」と要求しており、`test_verification_arguments_are_scanned_in_full_and_default_to_deny` のパラメタに標準入力起動形態が含まれ deny 側で固定されている。消化済み。
