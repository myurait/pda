# S3-M1 実装 反証レビュー記録（2026-08-23、レンズ: correctness）

- Status: open（確証欠陥 11 件。対応は goal M1 の残作業）
- 処置: `docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md`（2026-08-23。全確証欠陥の処置と、司令塔判断へ回付した項目の対応表）
- 読み取り方針: **本ファイルは `restricted-` 接頭辞の対象。迂回の具体形を含むため Fable モデルのセッションでは直接読まない**。対応は Opus のサブエージェントへ委譲し、本体へは欠陥ID・抽象名・判断項目のみを返す。
- レビュー対象: コミット `4f3d22f`「artifact-changeの二層契約と契約ライフサイクルをスコープゲートへ実装」
- 正本設計: `docs/design/task-scope-admission-gate.md`「S3-M1: 決定論コアの具体設計」および「S3-M1 契約ライフサイクル」
- レンズ: correctness（ロジック欠陥、fail-open 経路、原子性・並行性、エラー処理、状態遷移の穴）
- 確証欠陥: 11 件（blocker 2 / major 5 / minor 4）、推測のみで確証に至らなかった項目は「棄却・保留」節に分離
- 再現ハーネス: `tmp/repro_correctness.py`（git 管理外、この開発PCのローカル実行専用）。`./tmp/venv-scope/bin/python tmp/repro_correctness.py` で 7 件が決定論的に再現する。fixture の git リポジトリは `tempfile.mkdtemp()` 配下に作る（リポジトリ内へ入れ子の `.git` を作れないサンドボックス制約のため）。
- 既存テストの状態: 199 pass / 0 fail。**下記 7 件はいずれも 199 pass と同時に成立する**（テストが緑であることは以下の反証にならない）。

## 総括

第一層（write 境界）の**パターン照合そのもの**、第二層の全トークン検査、git 引数の allowlist、glob のセグメント境界扱い、lock 時の root 外シンボリックリンク検査は、いずれも設計どおりに実装されている。確証した欠陥は、その周囲の**契約が発効する条件**に集中している。

1. 契約の発効条件が分類器に従属している（I-COR-01）。
2. write 境界がロック済み root の**内部**で閉じていない（I-COR-02）。
3. ターン⇄タスクの同一視、バインド失敗、明示完了後、ターン終了、並行競合という 5 つの周辺経路が、いずれも「強制されないまま許可」または「例外」へ落ちる（I-COR-03〜07）。

つまり「locked 状態に到達したターンの admission」は堅い。問題は locked へ到達するか否かと、locked から外れた経路である。

---

## 確証された欠陥

### I-COR-01 [blocker] 割当 seed の強制が分類器の出力に従属する

**根拠**

`integrations/hermes-scope-gate/scope_gate.py:939-943`:

```python
seed = (
    self.get_contract_seed(task_id)
    if intent.task_class == "artifact-change"
    else None
)
```

seed の参照が `classify_task()` の戻り値に条件付けられている。`classify_task` → `_classify_non_closeout`（同 101-119）は次のとき `artifact-change` を返さない。

- `_BROAD_MISSION_RE`（同 67-73）に当たる語（全面・全体・大規模・包括・徹底・作り直・再設計・移行・監査・redesign・migrate・audit）が本文にあれば `audit-only`。
- `_ARTIFACT_CHANGE_RE`（同 90-98）の変更動詞が無ければ `audit-only`（例: 「調査」「分析」「設計」のみの指示、対象パスの列挙だけの指示）。
- `_BOUNDED_OP_RE` × `_BOUNDED_TARGET_RE` に当たれば `bounded-operation`。
- `?`／`？` を含み `_EXPLICIT_ACTION_RE` に当たらなければ closeout 判定を抜けて `_classify_non_closeout` 送り。

このいずれでも seed は読まれず、ターンは `state='audit'`・`contract_json=NULL` で作られる。`admit_tool`（同 1787-1796）は `task_class == "artifact-change" and state in ARTIFACT_ENFORCED_STATES` でしか強制経路へ入らないため、以降の全変異が `not-enforced` で許可される。`admit_without_turn` は**ターンがバインドできた**この経路では発火しない。`tool_execution_middleware` も同じ `admit_tool` を呼ぶため二重化にならない。

これは設計「S3-M1 契約ライフサイクル」第5項「git 書込その他の副作用を許すかどうかは **locked 契約のフィールド**で表す。分類器が推定したフラグの既定値に依存させない」と第4項の fail-closed 規範（「seed 検証失敗も fail-closed」「バインディング不能時は fail-closed」「ターン未登録を『未強制』として扱わない」）に正面から反する。設計は「自律 worker レーンは常に seed 経路とする」としており、seed が存在するタスクで強制が消える経路は許容されていない。

なお設計第1項は「オーケストレーターがタスク割当時に…契約 seed をゲート状態へ記録する。ゲートはターン開始時にこの seed を消費し」と書いており、seed の存在自体が権威である。分類は seed の**有無を判定する材料ではない**。

**再現**

`tmp/repro_correctness.py::case_seed_bypass`。`record_contract_seed(task_id="TASK-1", worktree=<repo>, branch="main", write_paths=["src/*.py"])` を入れた上で、

- 対照（「src/a.py を修正して」）: `class=artifact-change state=locked`。scope 外書込は拒否される。
- 「現状を調査してレポートして」: `class=audit-only state=audit` → `write_file` で `docs/secret/keys.txt`（write_paths 外）が `allowed=True action=not-enforced`。
- 「全面的に見直して」「この設計はどうなっていますか？」「gateway サービスを再起動して」でも同じ結果。

4/4 の探索文で scope 外書込が許可された。

**修正方針**

`start_turn` の seed 参照を分類から切り離す。`task_id` があれば無条件に `get_contract_seed` を引き、seed が存在する場合は分類結果を上書きして `task_class='artifact-change'` として登録する（seed の `task_class` を権威とする）。分類器の出力は監査記録・gold set 用のフィールドとして別に保持し、admission の入力にしない。seed があるのに契約構築へ失敗した場合は既存の `mutation-denied` へ落とす（この分岐自体は正しく実装されている）。受入テストは「seed があるタスクでは、どの分類結果でも scope 外変異が拒否される」形で、分類クラスを直接パラメタ化して固定する。

---

### I-COR-02 [blocker] 第一層の write 境界がロック済み root の内部で閉じていない

**根拠**

`_admit_artifact_change_locked`（`scope_gate.py:2576-2601`）と `_artifact_stage_targets`（同 2237-2264）は、いずれも

1. `normalize_repo_relative_path()` で**レキシカルな**相対パスを得て、
2. `resolve_existing_ancestor()` で実体解決し、
3. **手順1のレキシカルな相対パス**を `scope_patterns_match()` へ渡す。

`resolve_existing_ancestor`（同 365-396）が検査するのは「解決後の実体がロック済み **root 配下**であること」だけで、解決後のパスを `write_paths` / `test_paths` へ再照合しない。したがって、scope 内ディレクトリに置かれた**root 内の scope 外ファイルを指すシンボリックリンク**は、両方の検査を通過し、書込はリンク先（scope 外）に着地する。

lock 時の検査 `verify_scope_prefixes_are_inside_root`（同 408-425）はこれを覆わない。走査するのはパターンの**静的プレフィックス**のみ（`_static_pattern_prefix`、同 399-405。`src/*.py` なら `("src",)` まで）で、判定も「root 外へ解決するか」に限られる。root 内で scope 外へ向くリンクは検査対象外である。リンクが lock 後に作られる場合はそもそも lock 時検査の射程外になる。

設計「第一層: write 境界（硬い決定論保証）」は次の 2 つを同時に要求している。

- 「**実体解決を含める。** 書込先の直近の既存祖先ディレクトリを実体解決し、解決後の絶対パスがロック済み worktree root 配下であることを検査する。レキシカルな文字列照合のみで書込を許可しない。」
- 「`targets.write_paths`: …ターンの書込許可範囲の**閉集合**（INV-S2 の write 版）。」

実装は前者の文言（root 配下であること）は満たすが、後者の閉集合性を満たしていない。root 配下であることと write_paths の閉集合であることは別の性質であり、S3-M1 が exit gate で主張する「スコープ逸脱の機械的遮断」は後者についての主張である。

**再現**

`tmp/repro_correctness.py::case_symlink_write_through`。`write_paths=["src/*.py"]` で lock 済みのターンに対し、`src/b.py` → `docs/secret/keys.txt`（root 内・scope 外）のリンクを置く。

- `write_file {"path": "<root>/src/b.py"}` → `allowed=True action=write-in-scope-change`。実際の書込先 `docs/secret/keys.txt` は `scope_patterns_match(("src/*.py",), "docs/secret/keys.txt") == False`。
- 同じリンクを対象にした `terminal {"command": "git add src/b.py"}` → `allowed=True action=stage-in-scope-change`。

第二層のファイル対象（`_scan_template_tokens`、同 2422-2439）も同じ順序でレキシカルな相対パスを照合しているため、同じ形が成立する。

**修正方針**

照合の入力を実体解決後のパスに統一する。`resolve_existing_ancestor` を「root 配下判定」から「解決後の絶対パスを返す関数」へ変え、`scope_patterns_match` には**解決後のパスを root から相対化したもの**を渡す。書込先自体が既存のシンボリックリンクである場合は、リンク先の相対パスで照合する（あるいは write 対象がシンボリックリンクであること自体を deny する。設計は前者の粒度を要求していないため、どちらを採るかを受入テストで固定する）。`_admit_artifact_change_locked` / `_artifact_stage_targets` / `_scan_template_tokens` の 3 箇所が同じ関数を通ることを、パス正規化の単一化規律（設計「パス正規化は単一の決定論関数へ集約する」）に合わせて確認する。受入テストは「scope 内に置かれた root 内 scope 外リンクへの書込・ステージ・検証対象指定がいずれも拒否される」で固定する。

---

### I-COR-03 [major] ターン行がタスク単位に退化し、初回分類と予算がタスク全体を固定する

**根拠**

`plugin_runtime.py:292-303`:

```python
@staticmethod
def _turn_key(kwargs: dict[str, Any]) -> str:
    direct = str(kwargs.get("turn_id") or kwargs.get("task_id") or "")
    if direct:
        return direct
    ...
```

Hermes が `turn_id` を渡さず `task_id` を渡す構成では、タスクの全ユーザーメッセージが同一 `turn_id`（= `task_id`）になる。`start_turn` の INSERT は `ON CONFLICT(turn_id) DO NOTHING`（`scope_gate.py:981`）なので、2 通目以降のメッセージは**ターン行を作らず、分類もやり直されない**。結果:

- 初回メッセージの分類が以降のタスク全体を固定する。I-COR-01 と組み合わさると、1 通の非 artifact-change 表現でタスク寿命ぶんの未強制状態が確定する（回復経路が無い）。
- `started_at` が初回のままなので `max_wall_seconds=3600` はタスク全体の壁時計になる。`tool_count` / `denied_count` も累積し、`max_tool_calls=96` / `max_denied_calls=6` がターン予算ではなくタスク予算になる。
- `origin_message_sha256` が初回メッセージのものに固定される（契約と原文の対応が崩れる）。

設計「S3-M1 契約ライフサイクル」第4項は状態遷移をターン単位で規定し（「seed 消費に成功したターン: 直ちに locked」「完了: 明示的な完了制御アクション、または session 終了」）、実装サマリも「seed 自体はタスク全体の上限として有効なままにした。文字どおりの一回消費にすると同一タスクの後続ターンが未強制へ落ちる窓が生まれる」と後続ターンの存在を前提にしている。ターン行がタスク単位に退化していると、その「後続ターン」が状態機械上に現れない。

`_turn_key` 自体は本コミットで変更されていない（S1 由来）。ただし S3-M1 の契約ライフサイクルはターン粒度を前提に設計されているため、この前提のずれは S3 で初めて実害を持つ。

**再現**

`tmp/repro_correctness.py::case_turn_task_conflation`。seed 済み `TASK-2` に対し `pre_llm_call` を 2 回（1 通目「状況を調査して」、2 通目「src/a.py を修正して」）呼ぶと、2 通目のあとも `class=audit-only state=audit` のままで、`pre_tool_call` は scope 外書込に `None`（＝ブロックせず通過）を返す。

**判断が必要な点**

Hermes が pre_llm_call / pre_tool_call / post_llm_call へ `turn_id` を実際に渡すかは、この開発PCでは検証できない。設計の実装チェックリスト第7項が「監査フックの発火粒度が『ユーザーターン単位』か『LLM 呼び出し単位』かを、有効化前に synthetic payload で確認する」を既に挙げており、同じ検証で `turn_id` / `task_id` の実配線も確認する必要がある。

**修正方針**

`turn_id` が渡されない場合のフォールバックを `task_id` そのものにしない。`f"{task_id}:{message_digest}"` のように**メッセージ由来の識別子を必ず含める**（既に session_id 側のフォールバックがこの形になっている）。あわせて、seed を「タスク単位の上限」、契約を「ターン単位のインスタンス」として明確に分ける（seed 参照は I-COR-01 の修正で分類から切り離す）。ミニPC側で synthetic payload により実フィールドを確認したうえで有効化する。

---

### I-COR-04 [major] 未バインド時の fail-closed が task_id 依存で、session 由来の契約を参照しない

**根拠**

`admit_without_turn`（`scope_gate.py:1954-1980`）は `session_id` を引数に取るが本体で一度も使わない。seed の照会は `get_contract_seed(task_id)`（同 902-923）で `task_id` 完全一致のみ。`contract_seeds` テーブルは `session_id` 列を持ち（同 721）、`record_contract_seed` はそれを保存する（同 887-897）が、**どの照会経路も session_id を引かない**。

結果、`task_id` が空のまま未バインドの tool call が来ると、seed が存在しても `GateDecision(True, "not-enforced", ...)` になる。設計第4項「バインディング不能時は fail-closed: 当該タスクに seed が存在する場合、契約へバインドできない tool call の変異系を拒否する。ターン未登録を『未強制』として扱わない」の実装が、`task_id` が配線されている場合にのみ効く条件付きのものになっている。

既存テスト `test_an_unbindable_call_on_a_seeded_task_denies_mutation`（`tests/test_artifact_change_scope.py:483-506`）は 3 ケースすべてで `task_id` を渡しており、空 `task_id` の経路を踏んでいない。

**再現**

`tmp/repro_correctness.py::case_unbound_session`。同一 seed に対し
`admit_without_turn(task_id="TASK-4", session_id="S4", tool_name="write_file")` → `allowed=False (contract-unbound)`、
`admit_without_turn(task_id="", session_id="S4", tool_name="write_file")` → `allowed=True (not-enforced)`。

**判断が必要な点**

I-COR-03 と同じ配線確認。Hermes が tool フックへ `task_id` を渡すなら実害は無く、渡さないなら fail-closed 規範がこの経路で機能しない。

**修正方針**

`get_contract_seed` に session_id 経由の照会を追加し、`admit_without_turn` は `task_id` と `session_id` の**どちらか**で seed を引けたら fail-closed 側に倒す。`session_id` を使わないなら引数から外す（黙って無視される引数は、規範が効いているという誤った読みを招く）。受入テストは `task_id=""` を明示的に含める。

---

### I-COR-05 [major] 明示完了後の再バインドが未強制ターンへ落ちる

**根拠**

`resolve_turn_id`（`scope_gate.py:1018-1054`）の 3 経路のうち、`turn_id` 完全一致の経路には完了フィルタが無い（完了済みターンにそのままバインドされ、`admit_tool` が `turn-closed` で拒否する。これは正しい）。一方 `task_id` / `session_id` フォールバックは `completion_status IS NULL` で絞るため、**最新ターンが完了済みなら、より古い未完了ターンを拾う**。同一 session に未強制（`audit`）のターンが残っていれば、そこへバインドされて `not-enforced` で許可される。

これは設計第4項「**closure は明示のみ**: 強制クラスのターンを中間の監査フックで閉じない。閉じたターンでは変異系を拒否したままにする」の後半を破る。閉じたターンで変異が拒否されるのは、呼び出し側が完了したターンの `turn_id` を渡し続ける場合に限られる。

既存テスト `test_a_closed_turn_keeps_denying_mutation`（`tests/test_artifact_change_scope.py:470-480`）は完了したターンの `turn_id` を直接渡しており、フォールバック経路を踏んでいない。

**再現**

`tmp/repro_correctness.py::case_post_closure_rebinding`。同一 session に未強制ターン `T5-old`（「現状を調査して」）と artifact-change ターン `T5-new` を作り、`T5-new` を lock → `finalize_turn(status="success")`。

- `turn_id="T5-new"` で scope 外書込 → `allowed=False (turn-closed)`。
- `resolve_turn_id(turn_id="", task_id="", session_id="S5")` → `'T5-old'` を返し、同じ scope 外書込が `allowed=True (not-enforced)`。

**判断が必要な点**

I-COR-03 / I-COR-04 と同じ配線確認。seed 経路では未バインドが `contract-unbound` で拒否されるため（I-COR-04 の修正が入れば）影響は自己 lock レーンに限定される。

**修正方針**

フォールバックの候補集合を「同 session の未完了ターン」から「同 session の最新ターン（完了済みを含む）」に変える。最新ターンが完了済みなら、それにバインドして `turn-closed` を返すのが規範に沿う。過去の未完了ターンへ遡ってバインドしてはならない。あわせて I-COR-06 の修正（強制ターンを閉じる）を入れないと未完了ターンが溜まり続け、この経路の露出が増える。

---

### I-COR-06 [major] 強制ターンが明示完了以外で閉じられない

**根拠**

`post_llm_call`（`plugin_runtime.py:267-276`）は、強制状態の artifact-change ターンでは意図的に閉じずに return する（closure 規範に沿った正しい実装）。ところが `on_session_end`（同 280-290）は

```python
if kwargs.get("completed") and not kwargs.get("failed") and not kwargs.get("interrupted"):
    return
```

で、**正常終了した session では何もしない**。したがって強制 artifact-change ターンは、エージェントが `scope_gate action=complete` を明示的に呼ばない限り、`state='locked'` / `completion_status=NULL` のまま永久に残る。

設計第4項は「完了: 明示的な完了制御アクション、**または session 終了**」と両方を閉鎖契機に挙げている。実装は前者のみが機能する。

実害は 2 つ。(a) 未完了ターンが蓄積し、I-COR-05 のフォールバック経路が古い未強制ターンを拾う確率が上がる。(b) `task_id` / `session_id` フォールバックが古い locked ターンを拾った場合、`started_at` が古いため `max_wall_seconds` 超過で正当な作業が `wall-budget` で拒否される（こちらは fail-closed 側だが、原因が状態機械の穴なので診断困難な false deny になる）。

**再現**

`tmp/repro_correctness.py::case_never_closed`。lock 済みターンに対し `post_llm_call` → `state=locked status=None`、続いて `on_session_end(completed=True, failed=False, interrupted=False)` → `state=locked status=None`。

**修正方針**

`on_session_end` の早期 return を外し、正常終了時も `complete_turn(status="success")` を呼ぶ。session 終了は「明示的な完了制御アクション」とは別の正規の閉鎖契機であり、これを閉じることは closure 規範（「中間の監査フックで閉じない」）と矛盾しない — session 終了は中間フックではない。受入テストは「clean な session 終了後、同 session の変異が `turn-closed` で拒否される」で固定する。

---

### I-COR-07 [major] admission が競合時に例外を投げ、pre_tool_call に fail-closed 境界がない

**根拠**

`admit_tool`（`scope_gate.py:1751-1826`）は `BEGIN IMMEDIATE` で書込ロックを取ったまま decision を計算する。artifact-change / closeout の git 書込経路はその中で `_validated_worktree_branches`（同 2635-2660）を呼び、`git rev-parse --show-toplevel` と `git branch --show-current` の 2 つの subprocess を **それぞれ timeout=3 秒**で実行する。`_connect` の設定は `timeout=3.0` / `busy_timeout=3000`（同 672-678）なので、書込ロックの保持時間が busy_timeout を超えうる。この間に別の admission が来ると `sqlite3.OperationalError: database is locked` が送出される。

`tool_execution_middleware`（`plugin_runtime.py:145-151`）は明示的に `except Exception` で fail-closed に倒す（正しい）。しかし `pre_tool_call`（同 79-110）、`pre_llm_call`（同 51-67）、`post_tool_call`（同 210-255）、`handle_scope_gate` の `lock`（同 167-181。`sqlite3.OperationalError` は `TypeError`/`ValueError` に含まれないため except を抜ける）には同等の境界が無い。pre フックで例外が出たとき Hermes が block 側に倒すか通過させるかは、この開発PCでは検証できない。

`validate_shell_payload`（`scope_gate.py:2880-2928`）も例外を捕まえないが、`pda-scope-gate` 側の `_validate_tool` が `except Exception` で stderr へ書き exit 1 を返す（`integrations/hermes-scope-gate/pda-scope-gate`）。シェル hook 経路は呼び出し側が非零終了を block と扱う限り fail-closed。

**再現**

`tmp/repro_correctness.py::case_lock_contention`。別コネクションで `BEGIN IMMEDIATE` を 5 秒保持した状態で `admit_tool` を呼ぶと `OperationalError: database is locked` が送出される（deny ではなく例外）。git subprocess を実際に遅延させる代わりに保持時間を直接作っているが、`_validated_worktree_branches` が同じ書込トランザクション内で最大 6 秒ぶんの subprocess timeout を持つことはコード上明白である。

**判断が必要な点**

Hermes が pre フックの例外を block 扱いにするか。`tool_execution_middleware` が `register()` で無条件に登録されている（`__init__.py`）ため、実効的な最終防衛線は存在する。それでも二重化のうち片側だけが fail-closed であるのは、設計が要求する fail-closed 規範の実装として不完全である。

**修正方針**

2 点を分けて直す。(a) `pre_llm_call` / `pre_tool_call` / `post_tool_call` / `handle_scope_gate` に `tool_execution_middleware` と同じ `except Exception` の fail-closed 境界を置く（`post_tool_call` は記録のみなので失敗を飲んでよいが、黙って落とさずログに出す）。(b) 書込トランザクションの中で subprocess を呼ばない。ブランチ drift 再検査は `BEGIN IMMEDIATE` の**前**に実施し、結果を decision 計算へ渡す（drift 検査と decision 記録の間に競合窓ができるが、drift 判定は git 側の状態を読むだけで、判定後に変わった場合は次の呼び出しで捕まる。現状のように admission 全体が例外で落ちるより安全）。あわせて `busy_timeout` を subprocess timeout の合計より大きく取る。

---

### I-COR-08 [minor] purge が expansion_permits と contract_seeds を残す

`purge_expired`（`scope_gate.py:772-806`）は `decisions` / `candidates` / `turns` を削除するが、`expansion_permits` と `contract_seeds` を触らない。permit は `(turn_id, action_fingerprint)` 主キーで残り続けるため、同一 `turn_id` が再生成された場合（I-COR-03 のとおり `turn_id` は `task_id` になりうるので、決定論的に再生成される）に、30 日前の allow permit が `_consume_permit_locked` で消費されうる。`expires_at` によるフィルタがあるため実際の allow には至らないが、TTL 判定のみが最後の砦になっている。seed も無期限に残る（実装サマリの「seed の権威の持続」は意図的な判断だが、GC 対象から外れていることは別問題）。

修正方針: `purge_expired` の削除対象に `expansion_permits`（turn_id 一致）と、完了済みかつ retention を超えた `contract_seeds` を加える。

---

### I-COR-09 [minor] 自己 lock の repositories が未検証・件数無制限で契約へ入る

`_lock_artifact_change`（`scope_gate.py:1239-1241`）は `repositories` を `_canonical_targets` に通すだけで、worktree との関係も件数も検査しない。`_canonical_targets` は「絶対パスであること」しか見ない（同 1383-1392）。スキーマ側の `nonEmptyUniqueStrings` にも `maxItems` が無い。admission は `worktrees` / `write_paths` / `worktree_branches` だけを読むため強制への影響は無いが、契約は承認レビューと監査の読み物であり、実行主体が任意の絶対パスを任意個数書き込める欄が残る。closeout 側は候補集合との包含を要求している（同 1141-1143）のに対し非対称でもある。

修正方針: artifact-change の `repositories` は lock 済み worktree から導出した値に固定する（自由入力を受け取らない）。または worktree の親リポジトリと一致することを検証し、スキーマに `maxItems` を入れる。

---

### I-COR-10 [minor] commit の admission が既存 index を write scope へ照合しない

`_artifact_commit_verdict`（`scope_gate.py:2267-2315`）は `-a` / `-p` / 履歴書換・hook 迂回トークンを拒否し、メッセージ必須を強制する（設計どおり）。ただし commit の内容は「その時点の index」であり、admission はそれを見ない。ステージ経路（`_artifact_stage_targets`）が scope 内に限定されているため、ゲート配下でステージされた内容は scope 内に収まる。一方、未強制の窓（I-COR-01 / I-COR-03 / I-COR-05 の経路、または lock 前に外部プロセスがステージした場合）で index に入った scope 外の内容は、そのまま commit に載る。

設計は「ステージ範囲は write scope に従属させる」と書いており、commit 内容の再照合は要求していない。したがって設計逸脱ではないが、第一層の閉集合主張と index の状態が独立であることは脅威モデルに明記する価値がある。

修正方針: 設計上の残余として明記する。実装で閉じるなら、commit 前に `git diff --cached --name-only` 相当の照合を admission へ入れる（別の subprocess を admission に増やすため、I-COR-07 (b) の整理と同時に行う）。

---

### I-COR-11 [minor] シンボリックリンク経由の表記が false deny になる

`normalize_repo_relative_path`（`scope_gate.py:348-357`）は `os.path.normpath` の結果を、実体解決していない `root` に対して `relative_to` する。契約の `root` は `_validated_worktree_branches` が `Path(worktree).resolve()` した値なので、同じ worktree を**シンボリックリンクを含む表記**で指した引数（macOS の `/tmp` → `/private/tmp` など）は `target-closed` で拒否される。`_admit_artifact_change_terminal` の workdir 比較（同 2502-2505）も `normpath` のみで同じ性質を持つ。

安全側の誤りであり fail-open ではない。ただし設計「『絶対パス即 deny』は引数の表記形式ではなく『ロック済み repository / worktree root のいずれにも属さないパス』を意味するものとする」の趣旨からは、表記の違いで属否判定が変わるのは望ましくない。本レビューの再現ハーネスも当初これに当たり、fixture 側で `.resolve()` して回避している。

修正方針: 相対化の前に対象と root の双方を実体解決する（I-COR-02 の修正で照合入力を解決後パスへ統一するなら、同じ変更で解消する）。

---

## 棄却・保留（推測のみで確証に至らなかった項目）

- **`_admit_artifact_change_terminal` の workdir 比較がレキシカル**: fail-open にはならない（`root` が解決済みのため、レキシカルに一致するパスは同一の場所を指す）。false deny 側の性質として I-COR-11 に統合した。
- **pytest の node id（`tests/x.py::test_y`）が拒否される**: 設計が「対象は**ファイル単位**」と明記しているため仕様どおり。
- **`git add <dir>` によるディレクトリ一括ステージ**: `**` を含むパターンでのみディレクトリ自体が一致し、その場合ディレクトリ配下は定義上 scope 内。`*` のみのパターンではディレクトリが一致しないことをコード上確認した（`_match_segments`）。欠陥ではない。
- **`ARTIFACT_WRITE_TOOL_CATALOG` の網羅性**: 実 Hermes のツール名・引数スキーマとの突き合わせがこの開発PCではできない。未列挙ツールは `expansion-required` で default deny になるため fail-open ではないが、カタログのフィールド名が実スキーマと食い違えば「列挙済みだが書込先フィールドを取り違える」形はありうる。ミニPC側での実スキーマ突き合わせを判断項目に含める。
- **第二層のプロセス副作用**: 設計が脅威モデルとして明文化し M2 の必須要件に固定済み。本レビューの対象外。

---

## 司令塔判断が必要な項目

1. **I-COR-01 / I-COR-02 の位置づけ**: いずれも「locked 契約が発効すれば境界は堅い」が「発効条件・照合入力が閉じていない」型の欠陥である。M1 exit gate の主張（第一層でのスコープ逸脱の機械的遮断）を満たすには両方の修正が前提になる。D-S3-6 でどちらの分岐を採っても、seed 経路を有効化する前に必要。
2. **I-COR-03 / I-COR-04 / I-COR-05 / I-COR-07 の harness 依存**: Hermes が各フックへ `turn_id` / `task_id` をどう渡すか、pre フックの例外を block 扱いにするかで実害の範囲が変わる。設計の実装チェックリスト第7項（監査フック発火粒度の synthetic payload 確認）と同じ作業で、フィールド配線と例外時挙動をミニPC側で確定させる必要がある。
3. **ツールカタログの実スキーマ突き合わせ**: 実 Hermes のツール定義との照合をミニPC側の作業として立てるか。
4. **I-COR-10 の帰属**: commit 内容と index の関係を M1 で閉じるか、脅威モデルの明示済み残余として M2 へ送るか。
