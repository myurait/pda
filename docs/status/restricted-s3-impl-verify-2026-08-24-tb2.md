# TB 修正の焦点再検証（レンズ: tb2、2026-08-24）

- 対象コミット: `9bbb831`（`bc32ca1..HEAD`）。TB-01〜TB-04 の処置差分。
- 検証範囲: (1) TB-01 の fail-open 組合せの反転（全数）、(2) 新解決順序が偽装面を開いていないこと、(3) TB-03 の処置の妥当性、(4) admission・closeout・計上集合の不変、(5) 全テスト green。
- 再現環境: `./tmp/verify-tb/`（`matrix.py` / `compare.py` / `closeout.py`、`before/` は `bc32ca1` 抽出ツリー、`after/` は HEAD 複製）。実行は `./tmp/venv-scope/bin/python`。git fixture は `tempfile.mkdtemp` 上の合成リポジトリ。
- **本書は取扱制限。到達条件と構成手順を含む。** 親セッションへの戻り値には ID と抽象名のみを返す。

---

## 判定

**pass**。TB-01 の処置は全数検査で反転が確認でき、方向は縮小のみ。新たな確証欠陥は **minor 2 件（TB2-01 / TB2-02）で、いずれも「主張の射程」クラス**（TB-02・TB-04 と同種）であり、機構の fail-open ではない。

---

## 1. TB-01 の反転（全数検査、基準 1・2 を同時に判定）

`resolve_task_binding` の入力空間を anchor 5 状態 × payload 6 状態 = **30 セル**で全数展開し、`before`（`bc32ca1`）と `after`（HEAD）を同一 driver で観測した（`matrix.py`）。

- anchor: 不在 / 記録なし / seed / 自己 lock / session フォールバック経由でのみ到達
- payload: 空 / anchor と同値 / 記録なし / seed / 自己 lock / 履歴のみ（seed を記録してターンを立てた後に seed 行のみ削除。purge 後の形）
- 観測ベクタ: 解決された binding、登録ターンの state / origin / class / allow_push、束縛不能時判定、および 4 つの正規化された書込候補（2 リポジトリ × scope 内外）のうち admit されたもの

結果（`compare.py`）:

```
cells: 30
differed: ['norecord|seed', 'norecord|selflock']
violations: []
post-fix fail-open cells (contract reachable but turn unenforced): []
```

- **差分は 2 セルのみ**で、いずれも「アンカーが契約記録へ到達せず payload 側が到達する」= 処置が変えることを許された唯一の組合せ。他 28 セルは before と完全一致。
- **差分の向きは縮小のみ**: admit 集合が `{A/secrets.txt, A/src/app.py, B/lib/mod.py, B/secrets.txt}`（未強制＝全許可）から `{B/lib/mod.py}`（payload 側契約の write scope 内のみ）へ。束縛不能時判定も `allowed=True (not-enforced)` → `allowed=False (contract-unbound)` へ反転。
- **`post-fix fail-open cells` が空**: 「いずれかの識別子で契約記録が引けるのに、ターンが `state=audit` / `origin=''` で開く」セルは処置後に存在しない。司令塔決定の実装原則が全数で成立している。
- 判定基準は `compare.py` 側に置いた（`UNLICENSED-DIFF` / `WIDENED` / `UNBOUND-WIDENED` / `LICENSED-BUT-UNCHANGED` の 4 種で違反を検出する形）。いずれも 0 件。

反証記録の再現 probe も独立に再実行した。`./tmp/probe-envbind/probe2.py` の P10 は 4 行全一致へ反転している（`after` / `anchor STALE` が `state=locked` / `origin='assignment'` / out-of-scope write `denied (write-scope)`）。修正報告の記載と一致。

## 2. 偽装面の非開放

全数検査の結果がそのまま根拠になる。アンカーが契約記録へ到達する 3 状態（seed / 自己 lock / session 経由）× payload 6 状態 = 18 セルはすべて before と一致し、before はアンカーを無条件に採る実装である。したがって **実行主体は payload を選んでも、契約が発効しているアンカーから逃れられない**。アンカーが何も引けない場合に payload を選べるが、選べる結果は「その識別子で引ける契約に束縛される」ことのみで、比較対象は未強制（全許可）であるため常に縮小方向である。

追加確認: seed の `git_write` 省略時はクラス既定が入り、`allow_push=0`（push は恒久拒否）。すなわち seed へ束縛して push 権を得る経路は無い（`closeout.py` の 2 セルで確証）。

## 3. TB-03（宣言済み残余）の妥当性

台帳が根拠として挙げた 2 つの事実前提をコードで確認した。

- `resolve_turn_id` の fallback は `(("task_id", task_id), ("session_id", session_id))` の順で、`_FALLBACK_TURN_ORDER` は「開いている強制 artifact-change ターン優先 → `started_at DESC`」。したがって「安価な変種（session 一致で先に試す）は、後続 worker が自ターンを持たないという露出条件下で空振りし同じ task 照会へ落ちる」は成立する。
- `expansion_permits` は `turn_id` 列を鍵に持ち、参照も `WHERE turn_id = ?`。カード横断の permit 消費は起きない。

閉じる変種が「プロセス境界を跨ぐ task fallback の除去」＝ターン解決の共有意味論（closeout も同経路）の変更かつ admission 変更になる、という評価も上記コード形から妥当。**宣言済み残余としての処置を承認**。再実装は要求しない。

## 4. admission・計上集合の不変

- `scope_gate.py` の変更は 4 箇所に限られる: `Callable` の import、`resolve_task_binding`、`has_contract_record`（新規）、`admit_without_turn` の enforced 式の書き換え、`validate_shell_payload` の解決。予算・拒否計上のコードには触れていない。
- `admit_without_turn` の書き換えは恒等: 旧 `seed is not None or self_lock is not None or history` → 新 `has_contract_record(...) or history`、かつ `has_contract_record` = `seed is not None or self_lock is not None`。
- 例外境界: diff 外の `_binding` 呼び出し 3 箇所を確認した。`_close_at_audit_hook`（呼び出し元 `post_llm_call` が包む）と `on_session_end`（`try` の内側）は境界内。`post_tool_call` は境界を持たないが、**変更前から `_binding` の直後に無防備な `resolve_turn_id`（同種の store 読取）があった**ため、照会の追加は新しいクラッシュ・クラスを作っていない。台帳 §6 の当該主張は正しい。

## 5. テスト・空回り検出

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **622 passed**。
- ambient に `HERMES_KANBAN_TASK` を置いた同スイート: **622 passed**。
- 空回り検出（自前の変種）: `resolve_task_binding` の本体を `return anchor or payload` へ戻す（照会呼び出しごと除去）と **5 failed / 617 passed**。修正報告・台帳の「4 件」より 1 件多い。差は変種の形に由来する: 照会の**呼び出しごと**外すと例外境界テストの monkeypatch した述語が発火しなくなりターンが登録されてしまうため、当該テストも落ちる。報告側の変種は照会呼び出しを残して結果のみ無効化した形と推定される。**いずれの形でも新規テストは load-bearing**であり、報告より検出力が高い方向のずれなので欠陥として起票しない。検証後 `git checkout` で復元し、worktree clean と HEAD 一致を確認した。

---

## 新規の確証欠陥

### TB2-01（minor）TB-04 の訂正後の closeout 主張が、TB-01 処置で新設された再束縛セルを反映していない

**確証部分。** `closeout.py` で closeout 分類メッセージを 4 セルで観測した。

```
anchor_absent_payload_unseeded      before/after 一致: class=repository-closeout state=discovering allow_push=1 commit=block push=block
anchor_unseeded_payload_unseeded    before/after 一致: class=repository-closeout state=discovering allow_push=1 commit=block push=block
anchor_seeded                       before/after 一致: class=artifact-change     state=locked      allow_push=0 commit=allow push=block
anchor_unseeded_payload_seeded      before: class=repository-closeout state=discovering allow_push=1 commit=block
                                    after : class=artifact-change     state=locked      allow_push=0 commit=allow
```

第 4 セル（アンカーが未 seed のカードを指し、payload が seed 済みカードを指す）が本コミットで変わった。設計本文へ書かれた TB-04 の訂正は

> 「closeout 挙動が不変なのは、**アンカー不在時、または当該カードが未 seed のとき**に限る」

であり、第 4 セルは「アンカーが未 seed」に該当するため、この主張のままでは closeout が保たれることになる。実測は保たれない（クラスが `artifact-change` へ上書きされ、`allow_push` が 0 になる）。**訂正文が本コミット自身の機構変更を反映していない。**

**評価。** 到達集合の比較では縮小である。変更前の `discovering` は commit がその場では拒否されるが、worker は自ら `scope_gate action=lock` を経て commit と push の両方へ到達できる（`allow_push=1`）。変更後は push が恒久拒否で commit のみ（seed の `git_write` クラス既定による契約側の付与であり、漏れではない）。したがって安全性の後退は無く、欠陥は**主張の射程**に限る。ただし「commit の即時判定が deny → allow へ動く」点は設計・台帳のいずれにも記載が無い。

**塞ぐ方向（抽象）。** TB-04 の訂正文へ「または payload 側の識別子が契約へ到達し、アンカー側が到達しないとき」を条件として追加する。機構変更は不要。

### TB2-02（minor）束縛照会から履歴を除く根拠の主張が、束縛不能時判定の強制根拠集合と食い違う

**確証部分。** `has_contract_record` の docstring と設計本文は履歴除外の根拠を次のように述べる。

- コード: "a turn opened under a task that has history but no record is unenforced whichever identifier bound it, so counting history here would move bindings without putting any contract back in force"
- 設計: 「ターン履歴は照会に含めない（記録ではないため、履歴だけを根拠に束縛を動かしても契約は発効しない）」

実測（`./tmp/verify-tb/` の履歴セル、`payload` は別セッションで強制ターンを持ち記録は削除済み、`anchor` は何も引けない）:

```
has_contract_record(payload)                     = False
_has_enforced_history(payload, call-session)     = True
resolved binding                                 = anchor
admit_without_turn as resolved (anchor)          -> allowed=True  reason=initial rollout audits this task class
admit_without_turn if it had bound the payload   -> allowed=False reason=contract-unbound
```

`admit_without_turn` は記録 2 種に加えて**強制ターン履歴も enforced として数える**（本コミットでも変更されていない）。したがって履歴を照会へ含めれば束縛は動き、束縛不能時判定は allow から deny へ変わる。「契約は発効しない」は文字どおり正しいが、根拠文は「履歴は強制に無関係」と読める形であり、除外が allow を残す帰結を持つことを述べていない。設計本文（正本）の読者はこの帰結に到達できない。

**評価。** 機構は本コミット前後で不変（全数検査の当該セルは差分に現れない）であり、**新しい露出ではない**。台帳 §6「隣接する未確証の角」は機構を正確に記述している。欠陥は、正本側の根拠文が取扱制限台帳側の記述より強い主張になっている点に限る。司令塔決定の文字どおりの範囲（契約＝seed または locked 契約）の外でもあるため、処置は文書側で足りる。

**塞ぐ方向（抽象）。** 設計本文の当該括弧書きへ、束縛不能時判定が履歴を強制根拠に数えること、および除外の帰結（当該組合せで未強制側に留まる）を明記する。機構で閉じるなら台帳 §6 が挙げる 2 形（照会へ履歴を加える／`admit_without_turn` を両識別子で照会する）。帰属は司令塔判断。

---

## 否定的結果（欠陥ではない、記録目的）

- 全数 30 セルで「契約が引けるのに未強制へ落ちる」組合せは処置後に 0 件。
- 全数 30 セルで admit 集合の拡大は 0 件（`WIDENED` 検出 0）。
- アンカーが契約へ到達する 18 セルは before と完全一致（アンカー優先の主目的は不変）。
- seed へ束縛して push 権を得る経路は無い（`allow_push=0`）。
- `post_tool_call` の境界欠如は本コミット由来ではない（変更前から同位置に無防備な store 読取があった）。
