# S3-M1 実装 反証レビュー（レンズ: bypass）2026-08-23

対象コミット: `4f3d22f` "feat: artifact-changeの二層契約と契約ライフサイクルをスコープゲートへ実装"

正本設計: `docs/design/task-scope-admission-gate.md` の S3-M1 節（377-520行）

レンズ: 迂回可能性（write境界・実行opt-in・lockライフサイクル・seed機構を迂回する経路。パス照合、glob、実体解決、引数検査、ツールカタログ網羅の抜け）

このファイルは迂回手法の具体形を含む。Fable セッションでは直接読まない扱いとし、対応は Opus のサブエージェントへ委譲する。

処置: `docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md`（2026-08-23。全確証欠陥の処置と、司令塔判断へ回付した項目の対応表）

確証欠陥 9 件（blocker 2 / major 2 / minor 5）。すべて再現スクリプトで確認済み（推測のみの項目は「未確証」として末尾に分離した）。

再現環境: 開発PC上の `./tmp/venv-scope`（pytest / jsonschema / pyyaml、git 管理外）。プローブスクリプトは `./tmp/work/byp/probe*.py`。

---

## I-BYP-01 [blocker] 生引数の上位参照がレキシカル畳み込みで消えるため、ロック済み worktree 外への書込が「スコープ内」として許可される

### 該当箇所

`integrations/hermes-scope-gate/scope_gate.py`

- `normalize_repo_relative_path`（320-362行）
- `resolve_existing_ancestor`（365-396行）
- 呼出元: `_admit_artifact_change_locked` の書込カタログ経路（2576-2601行）、`_scan_template_tokens` の検証対象経路（2422-2439行）、`_artifact_stage_targets`（2257-2258行）

### 根拠

`normalize_repo_relative_path` は次の順で処理する。

1. `lexical = Path(os.path.normpath(str(candidate)))`
2. `if ".." in lexical.parts: raise PathRejected("target-traversal", ...)`
3. `lexical.relative_to(locked_root)`
4. 呼出元が `resolve_existing_ancestor(absolute, root=root)` を呼ぶ。ここで `absolute` は **手順1で畳み込まれた `lexical`** である。

`os.path.normpath` はシンボリックリンクを考慮せず `a/link/../b` を `a/b` へ純レキシカルに畳み込む。したがって

- 手順2の `..` 検査は、生引数に `..` が含まれていても常に空振りする（畳み込み後に `..` が残るのは、絶対パスでは root の外へ抜けた場合だけ）。
- 手順4の実体解決は、生引数ではなく畳み込み後の別パスに対して行われる。生引数の実際の解決先は一度も検査されない。

結果として、リポジトリ内にワークツリー外を指すディレクトリ・シンボリックリンクが1つ存在すれば、そのリンクを経由して `..` を1段以上たどる生引数は「ロック済み root 配下の別ファイル」として照合され、glob に一致すれば allow になる。ツールに渡される引数はゲートが書き換えないため（`plugin_runtime.tool_execution_middleware` は `next_call(args)` に原引数をそのまま渡す）、OS が解決する実際の書込先はワークツリー外になる。

設計が明文で禁じた実装形そのものである。

- 「パス正規化は単一の決定論関数へ集約する。検査は『パス要素を完全に解決し、上位参照要素の不在と制御文字の不在を確認する』形で行い、文字列前処理の積み増しで実装しない」
- 「実体解決を含める。書込先の直近の既存祖先ディレクトリを実体解決し、解決後の絶対パスがロック済み worktree root 配下であることを検査する。レキシカルな文字列照合のみで書込を許可しない」

`resolve_existing_ancestor` 自体は、パス要素が**そのまま**シンボリックリンクである形（`linked/new.py`）は正しく捕まえる。既存テスト `test_artifact_change_scope.py` 192-195行・451-466行はその形のみを固定しており、リンクの後段に上位参照が続く形は未テストである。

### 再現（`./tmp/work/byp/probe5.py`）

1. 一時ディレクトリに git worktree `repo/`（branch `main`）を作り、`repo/pkg/a.py` をコミットする。
2. `repo/pkg/link` を、worktree 外のディレクトリ（`<base>/outside/d`）を指すシンボリックリンクとして作る。
3. `write_paths=["pkg/**/*.py"]` の割当 seed を記録し、ターンを locked にする。
4. `write_file` を `path = "<root>/pkg/link/../pwned.py"` で admission に通す。

観測結果:

```
gate verdict : True | write-in-scope-change | audited as: pkg/pwned.py
actual write : /private/tmp/claude-501/byp5-_zxkdl7z/outside/pwned.py
inside root? : False
git sees it? : ?? pkg/link
```

- ゲートは allow を返し、監査記録（`decisions.resource` と `candidates.path`）に `pkg/pwned.py` を残す。
- 実際の書込は worktree 外の `<base>/outside/pwned.py` に着地する。git はこのファイルを一切認識しない。
- すなわち「機械的遮断」の主張だけでなく、監査記録の証拠性も同時に失われる（記録上はスコープ内書込に見える）。

第二層でも同じ経路が通る（`./tmp/work/byp/probe3.py` の P2）。

```
pytest -q <root>/pkg/link/../../pkg/a.py
  -> ALLOW / run-focused-test / resource "pkg/a.py"
```

`_scan_template_tokens` は `absolute.is_dir()` も畳み込み後のパスに対して評価するため、生引数が実際にはディレクトリを指す場合でもこの検査を通過する。第二層は「対象はファイル単位で `write_paths` ∪ `test_paths` へ照合する」を満たしていない。ワークツリー外の Python ファイルを pytest に収集させられるため、実行を伴う迂回にも直結する。

`_artifact_stage_targets` も同じ関数を使うが、git 自身が pathspec をワークツリー外へ出さないため、こちらの実害は限定的である。

### 修正方針

`normalize_repo_relative_path` を、設計文言どおり「生引数の完全な実体解決」を行う単一関数へ作り直す。

1. `normpath` の前に、**生引数の全パス要素**を検査し、`..`（および `.`）要素が1つでもあれば `target-traversal` で拒否する。呼出側が上位参照を必要とする正当な用途は artifact-change には存在しない。
2. root 相対化に用いる絶対パスは、`normpath` ではなく「既存部分を `os.path.realpath` で解決し、非存在部分を後段に連結した」パスとする。相対化・glob 照合・`is_dir` 判定はすべてこの解決済みパスに対して行う。
3. `resolve_existing_ancestor` には**生引数**を渡す（現在は畳み込み後を渡している）。祖先探索の起点が生引数になるだけで、既存のリンク検査ロジックは流用できる。
4. 受入テストを追加する: (a) `link/..` 1段、(b) `link/../..` 2段で root 外へ出る形、(c) 第二層の検証対象での同形、(d) `git add` での同形。いずれも `target-traversal` または `target-escape` で拒否されること、および allow 時の `resource` が常に実体解決後の相対パスであることを固定する。
5. あわせて、ゲートが admission に用いた解決済みパスと、ツールへ渡る引数の同一性を担保する設計上の選択（引数を正規化形へ書き換えるか、生引数に上位参照・シンボリックリンクを一切許さないか）を明記する。本修正方針は後者を採る。

---

## I-BYP-02 [blocker] 割当 seed の上限がターンの分類結果に従属しており、同一タスクの後続ターンが別クラスに分類されると第一層が完全に無効化される（クラス跨ぎの権限昇格を含む）

### 該当箇所

- `GateStore.start_turn`（925-1009行）: `seed = self.get_contract_seed(task_id) if intent.task_class == "artifact-change" else None`
- `GateStore.resolve_turn_id`（1018-1054行）: `completion_status IS NULL` の最新ターンへフォールバックする
- `GateStore.admit_tool`（1787-1796行）: `task_class == "artifact-change"` かつ `state ∈ ARTIFACT_ENFORCED_STATES` 以外は `not-enforced`
- `GateStore.record_contract_seed` の docstring（820-826行）: 「The seed is the authoritative ceiling for **every turn of the task**」

### 根拠

seed はタスク単位（`contract_seeds.task_id` が主キー）で記録されるが、参照されるのは `classify_task` が当該ターンの `user_message` を `artifact-change` と分類したときだけである。分類が他クラス（`audit-only` / `bounded-operation` / `repository-closeout`）になったターンは、seed の存在に関わらず次の状態で作られる。

- `audit-only` / `bounded-operation`: `state = "audit"`。`admit_tool` は `not-enforced` を返す（1794-1796行）。
- `repository-closeout`: `state = "discovering"`。closeout の契約体系に入る。

さらに `resolve_turn_id` は task_id / session_id 経路で「未完了の最新ターン」を返すため、seed で locked になった先行ターンが**開いたまま**でも、後続の未強制ターンが tool call のバインド先になる。`_artifact_change_decision` は enforced な artifact-change ターンを中間フックで閉じない（`post_llm_call` 267-276行）ので、先行ターンは開き続け、しかし何も支配しない。

分類器の入力は当該ターンの `user_message` である。自律レーンでは後続ターンの入力を実行主体が完全に制御できるとは限らないが、`_ARTIFACT_CHANGE_RE` は「調査」「設計」「分析」「テスト」を含まない（`_CHANGE_RE` にのみ含まれる）ため、`artifact-change` から外れる文面は極めて容易に成立する。

closeout へ落ちた場合は単なる無効化ではなく**権限昇格**になる。artifact-change 契約は `push-to-remote` を `actions.forbidden` に置き、`_admit_artifact_change_git` は `add` / `commit` 以外の subcommand を拒否する。一方 `_admit_closeout_locked` は `allow_push` が立った closeout ターンで `git push` を許可する（2117-2141行）。すなわち seed が push を禁じているタスクで、ターン1つの文面によって push 権限が取得できる。

設計の次の規定を満たしていない。

- 「割当 seed（正規経路）: … 実行主体側の操作を必要とせず、実行主体は seed を広げられない」
- 「バインディング不能時は fail-closed: 当該タスクに seed が存在する場合、契約へバインドできない tool call の変異系を拒否する。ターン未登録を『未強制』として扱わない」

`admit_without_turn`（1954-1980行）は「ターンが1つも解決できない」場合のみを fail-closed にしている。「別クラスの未強制ターンへバインドできてしまう」場合は覆っていない。

### 再現（`./tmp/work/byp/probe2.py` の P4、`./tmp/work/byp/probe4.py` の C）

無効化:

```
turn-1  artifact-change / locked      (seed 消費、write_paths=["pkg/**/*.py"])
turn-9  audit-only      / audit       (同一 task_id、文面 "現状を調査して報告して")
resolve_turn_id(task_id="T1") -> turn-9
write_file(path="<base>/anywhere.txt") -> ALLOW / not-enforced
```

seed のワークツリーの外、リポジトリの外にあるパスへの書込が許可される。

権限昇格:

```
tc1  artifact-change    / locked      (seed: write_paths=["pkg/**"], push は契約上 forbidden)
tc2  repository-closeout / discovering, allow_push = 1   (文面 "この差分をcommitしてpushしてください")
resolve_turn_id(task_id="TC") -> tc2
```

以降 tc2 の closeout 経路で bounded discovery → lock → `git push origin main` が到達可能になる。

### 修正方針

1. `start_turn` の seed 参照を分類結果から切り離す。`task_id` に seed が存在する場合は、分類結果に関わらず当該ターンを artifact-change の seed 契約として作る（分類結果は監査フィールドとして残す）。seed のあるタスクで分類器が別クラスを返したことは、分類の誤りかタスク境界の誤りであり、権限の変更根拠にしてはならない。
2. seed のあるタスクで、seed より広い権限を持つクラス（closeout の push を含む）へ遷移する要求は拒否し、拒否理由コードを「seed 契約外のクラス遷移」として計上する。真に別タスクなら別 task_id を割り当てるのがオーケストレーター側の責務であることを README と設計に明記する。
3. `resolve_turn_id` のフォールバックを、同一 task_id 内で「enforced な未完了ターンがあればそれを優先する」順序に変える。未強制ターンが enforced ターンを覆い隠せないようにする。
4. 受入テスト: (a) seed 有り × 分類 audit-only のターンで変異系が拒否されること、(b) seed 有り × 分類 repository-closeout で push が拒否されること、(c) enforced ターンが開いている間、同一タスクの後続ターンが `not-enforced` を返さないこと。
5. `record_contract_seed` の docstring が主張する「every turn of the task」が実装と一致するまで、docstring 側を実態に合わせるか実装を合わせるかを明示する（本方針は実装を合わせる）。

---

## I-BYP-03 [major] `git add` がディレクトリ pathspec を受け付けるため、同一ゲートが書込を拒否するファイルがステージされる

### 該当箇所

`_artifact_stage_targets`（2237-2264行）

### 根拠

`_artifact_stage_targets` はトークンから option（`-` 始まり）、pathspec magic（`:` 始まり）、`.` / `./`、ワイルドカード（`*?[`）を排除するが、**ディレクトリ指定を排除しない**。`is_dir()` 検査がない。同じコミットの第二層 `_scan_template_tokens` には `absolute.is_dir()` 検査があり（2427-2432行）、非対称である。

glob は「パス文字列 vs パターン」の照合なので、ディレクトリ自身に一致するパターンが存在する場合がある。特に `**/<name>` 形と `<dir>/**` 形。`**/tests` はパス `tests` に一致するが、`tests/test_a.py` には一致しない（`**` の後段 `tests` が最終セグメントを消費するため）。

`git add <dir>` は当該ディレクトリの部分木全体をステージする。したがって write scope に一切一致しないファイルがインデックスへ入る。設計の次の規定に反する。

- 「ステージ対象は `write_paths` ∪ `test_paths` へ照合済みのパス指定経由のみとし、対象を列挙しない一括ステージ系の指定は許可しない」
- 「closeout は『既存差分を保存する』意味論のため一括指定を許容できるが、artifact-change では許容しない。『closeout 同水準』は検査の厳密さの下限であり、許可範囲の上限ではない」

監査記録も壊れる: `decisions.resource` にはディレクトリ名1件（例 `tests`）しか残らず、実際にステージされたファイル集合は記録されない。

### 再現（`./tmp/work/byp/probe4.py` の A）

seed: `write_paths=["**/tests"]`。worktree に `tests/test_a.py` と `tests/fixtures/big.bin` が存在する。

```
pattern **/tests matches path 'tests'      : True
pattern **/tests matches 'tests/test_a.py' : False

git add tests            -> True  / stage-in-scope-change / audit resource: "tests"
write tests/test_a.py    -> False / write-scope ("tests/test_a.py is outside the locked write scope")
```

同一ターン・同一契約で、書込が拒否されるファイルがステージ経由でインデックスへ入る。I-BYP-05（commit がインデックス内容を検査しない）と組み合わせると、そのままローカルコミットに載る。

`<dir>/**` 形（例 `pkg/**` と `git add pkg`）でもディレクトリ指定は通るが、この場合は部分木全体がパターンに一致するため内容としてはスコープ内に収まる。ただし「対象を列挙しない一括指定」であること自体は同じで、ターンが書いていない既存の dirty 差分を巻き込む点は残る。

### 修正方針

1. `_artifact_stage_targets` に「トークンは既存のファイルでなければならない」検査を入れる。実体解決後に `is_dir()` なら `stage-directory` で拒否する。存在しないパスの削除ステージが必要な場合の扱いは別途決める（M1 では拒否で足りる）。
2. 拒否理由コードを新設し（`stage-directory`）、既存の `stage-unbounded` と区別して計上する。
3. glob 側の規律として、`write_paths` / `test_paths` のパターンは「ファイルに一致することを意図する」ものであることを README と設計例に明記する。`**/<name>` 形が中間ディレクトリにも一致する挙動を承認レビュー時に読み取れるようにする。
4. 受入テスト: (a) `**/tests` 契約下で `git add tests` が拒否されること、(b) `pkg/**` 契約下でも `git add pkg` が拒否され、`git add pkg/a.py` は許可されること、(c) allow 時の `resource` がステージされる実ファイル集合と一致すること。

---

## I-BYP-04 [major] 閉じたターン／バインド不能ターンが `not-enforced` へ落ちるため、「閉じたターンでは変異系を拒否したままにする」が成立しない

### 該当箇所

- `GateStore.resolve_turn_id`（1032-1053行）: task_id / session_id 経路の条件が `completion_status IS NULL`
- `GateStore.admit_without_turn`（1954-1980行）: seed が無ければ `not-enforced`
- `GateStore.admit_tool`（1779-1781行）: `turn is None` なら無条件で `not-enforced`
- `ScopeGatePluginRuntime._turn_key`（292-303行）: turn_id / task_id が無いホスト形態では `session_id:sha256(user_message)[:16]` を合成する

### 根拠

`finalize_turn` / `complete_turn` は enforced な artifact-change ターンの `state` を `completed`、`completion_status` を設定する。`state = "completed"` は `ARTIFACT_ENFORCED_STATES` に含まれるため、**そのターン行に到達できる限り** `_artifact_change_decision` は `turn-closed` で変異系を拒否する（1948-1952行）。

問題は到達可否である。`resolve_turn_id` は `turn_id` 引数が行に一致する場合のみ完了済みターンを返す。task_id / session_id 経路は `completion_status IS NULL` で絞るため、完了後は空文字を返す。ホストが tool call ごとに `turn_id` を渡さない形態（`_turn_key` がわざわざ `session:digest` を合成しているのは、まさにその形態を想定しているため）では、完了直後から解決が失敗し、`admit_without_turn` に落ちる。

`admit_without_turn` は seed が無ければ `not-enforced` を返す。自己 lock レーン（seed 無し）では、`scope_gate action=complete` を呼ぶこと自体が「以降すべて未強制」への遷移になる。さらに seed 有りのタスクでも、ホストが `task_id` を渡さなければ seed 参照が空振りして `not-enforced` になる。

`admit_tool` 側にも同じ穴がある。`turn_id` が渡されたが行が存在しない場合、seed の有無を一切見ずに `not-enforced` を返す（1779-1781行）。

設計の次の規定に反する。

- 「closure は明示のみ: 強制クラスのターンを中間の監査フックで閉じない。**閉じたターンでは変異系を拒否したままにする**」
- 「バインディング不能時は fail-closed」

### 再現（`./tmp/work/byp/probe2.py` の P5）

```
turn-3  artifact-change, 自己 lock (write_paths=["pkg/**/*.py"])
  locked 中の scope 外書込                 -> deny
finalize_turn(status="success")
  state                                   -> "completed"
resolve_turn_id(task_id="T3", session_id="S3") -> ""
admit_without_turn(tool_name="write_file")     -> True / not-enforced
```

完了後、ワークツリー外を含む任意の書込が許可される。

### 修正方針

1. `resolve_turn_id` の task_id / session_id 経路から `completion_status IS NULL` を外し、「未完了ターンを優先し、無ければ直近の完了ターンを返す」順序に変える。完了ターンへ到達できれば既存の `turn-closed` 判定が働く。
2. `admit_without_turn` の既定を、タスク／セッションに **enforced クラスのターン履歴があるかどうか**でも判定する。seed の有無だけを条件にしない。
3. `admit_tool` の `turn is None` 分岐を、`admit_without_turn` と同じ fail-closed 判定へ委譲する。
4. ホストから渡される識別子（turn_id / task_id / session_id）のどれが必須かを README に明記し、必須フィールドが欠けたまま enforced クラスを運用しない条件を実装側でも検査する。
5. 受入テスト: (a) 完了後の変異系が `turn-closed` で拒否されること（turn_id を渡さない形態を含む）、(b) `task_id` を渡さない形態で seed 有りタスクの変異系が拒否されること、(c) 存在しない turn_id で `admit_tool` を呼んだ場合に fail-closed になること。

---

## I-BYP-05 [minor] `git commit` がインデックス内容を一切検査しないため、スコープ外の staged 差分がそのままコミットされる

### 該当箇所

`_admit_artifact_change_git`（2362-2367行）、`_artifact_commit_verdict`（2267-2315行）

### 根拠

`_artifact_commit_verdict` は引数構文のみを検査する（`-m` / `--message=` 必須、履歴書換・検証フック迂回・一括ステージ系オプションの拒否）。インデックスに何が載っているかは見ない。ゲート経由で `git add` されたパスの記録（`candidates` テーブル）は存在するが、commit 判定はそれを参照しない。

したがって、ターン開始前から staged だった変更、I-BYP-03 経由で入った変更、あるいはゲートを通らない経路（別ターン、別プロセス）で staged された変更が、`commit-in-scope-change` という action 名でコミットされる。`push` は禁止されているため影響はローカル履歴に留まるが、監査 action 名と実内容が乖離する。

### 再現（`./tmp/work/byp/probe4.py` の B）

seed: `write_paths=["pkg/**"]`。ゲート外で `secrets/keys.txt` を変更・staged した状態で:

```
git commit -m wip -> True / commit-in-scope-change
```

### 修正方針

1. commit の admission 前に `git diff --cached --name-only` 相当を実行し、staged パス集合が `write_paths` ∪ `test_paths` に収まることを検査する。収まらない場合は `commit-scope` で拒否し、理由に外れているパスを含める。
2. 検査コマンドの実行はゲート内部の副作用であり、第二層の opt-in とは独立であることを設計に明記する（`_validated_worktree_branches` と同じ位置付け）。
3. 受入テスト: スコープ外の staged 差分があるとき commit が拒否され、`git restore --staged` 後は許可されること。

---

## I-BYP-06 [minor] artifact-change 契約が git 書込権限を運ぶフィールドを持たず、権限の出所が task class になっている

### 該当箇所

`_build_artifact_change_contract`（1300-1381行）、`_admit_artifact_change_git`（2318-2367行）

### 根拠

closeout は `turn["allow_commit"]` / `turn["allow_push"]` で stage / commit / push を出し入れするが、artifact-change の `add` / `commit` は契約の内容に関わらず class 固定で許可される。契約の `actions.required` は `["change-artifacts-in-scope"]` のみで、stage / commit を表すフィールドはない。`execution` は第二層の opt-in を持つのに、第一層の git 書込には対応する opt-in が存在しない。

設計 §5 は次のように定める。

- 「git 書込その他の副作用を許すかどうかは **locked 契約のフィールド**で表す。分類器が推定したフラグの既定値に依存させない」

実装は分類器フラグに依存していないので後段は満たすが、前段（契約のフィールドで表す）を満たしていない。結果としてオーケストレーターは「書込は許すがコミットはさせない」タスクを seed できない。D-S3-3 が「ローカルコミットを決定論 allowlist へ含める」と決めたことは、契約がそれを表現できないことまでは含意しない。

### 修正方針

1. 契約に `actions.git_write`（例: `[]` / `["stage"]` / `["stage","commit"]`）を追加し、スキーマ側で artifact-change の enum と既定を定義する。`record_contract_seed` と自己 lock の双方から渡す。既定値は D-S3-3 に合わせて `["stage","commit"]` とし、seed 側で縮小できるようにする。
2. `_admit_artifact_change_git` はこのフィールドを引いて subcommand を許可する。フィールドが無い契約（旧形）は fail-closed 扱いにする。
3. 受入テスト: `git_write` を空にした seed で `git add` / `git commit` が拒否され、既定 seed では許可されること。

---

## I-BYP-07 [minor] terminal ツールの未列挙引数フィールドが無検査で通る（書込ツールに適用した閉鎖規律が terminal に適用されていない）

### 該当箇所

`_admit_artifact_change_terminal`（2481-2534行）

### 根拠

この関数が読むのは `background` / `pty` / `command` / `workdir` の4フィールドのみで、`args` に他のキーがあっても検査せず通す。書込ツールについては設計どおり「ツール名 → 書込先を表す全フィールド名の明示 allowlist、未列挙のツールは default deny」という閉鎖を実装している（`ARTIFACT_WRITE_TOOL_CATALOG`、`collect_write_targets`）のに、terminal の引数側には同じ閉鎖がない。

設計の第二層 引数検査規範4は「設定の探索経路、収集経路、プラグイン読込経路、出力先および一時領域を差し替える指定は deny する」と定める。terminal ツールが `env` 相当のフィールドを持つ場合、`command` トークン列の allowlist を一切通らずに同種の差し替えが成立する。本レビューでは Hermes の terminal ツールの実引数スキーマがリポジトリ内に無く、当該フィールドの存在は確認できなかった。ただし「未列挙フィールドを無検査で通す」こと自体はコードから確証できる欠陥であり、フィールドの有無に依存しない。

### 修正方針

1. terminal に対して、artifact-change で許可する引数キーの明示 allowlist（`command` / `workdir` と、必要なら `timeout`）を定義し、それ以外のキーが1つでもあれば `terminal-argument-unlisted` で拒否する。
2. Hermes の terminal ツールの実引数スキーマを確認し、allowlist を実態へ合わせる。確認結果を README の「ツールカタログ」節に記録し、ツール側スキーマ変更時にゲート側 allowlist を更新する運用条件を書く。
3. 受入テスト: 未知の引数キーを1つ付けた合法コマンドが拒否されること。

---

## I-BYP-08 [minor] lock 前段の既定拒否を有効化する経路がモジュール定数の書き換えのみで、設定・環境変数からは到達できない

### 該当箇所

`ARTIFACT_CHANGE_PRELOCK_ENFORCED = False`（2171行）、`GateStore.__init__` の `enforce_artifact_change_pre_lock`（657-670行）、`ScopeGatePluginRuntime.__init__`（42-49行）

### 根拠

`GateStore` はコンストラクタ引数で上書きできるが、`ScopeGatePluginRuntime` は `GateStore(state_path)` しか呼ばず、環境変数も設定ファイルも読まない。したがって有効化にはソース編集とデプロイが必要である。

`./tmp/work/byp/probe4.py` の D で確認したとおり、現状 seed の無い artifact-change ターンは `state = "audit"` で作られ、`admit_tool` は `not-enforced` を返す（`/etc/hosts` への書込も許可される）。

これは D-S3-6 の M2 分岐（自律レーンでの強制は seed 配線まで有効化しない）と整合する意図的な選択であり、実装サマリでも明示されている。欠陥として記録するのは有効化経路の欠落のみである。付随して、seed が配線されていない現時点では第一層の硬い保証はどのレーンでも発効していないため、M1 exit gate の主張範囲は司令塔判断事項に載る（後述）。

### 修正方針

1. 有効化を環境変数（例 `PDA_SCOPE_GATE_ARTIFACT_PRELOCK`）または Hermes プラグイン設定から読む経路を `ScopeGatePluginRuntime` に追加する。既定は現状どおり無効。
2. 有効／無効の実効値を `pre_llm_call` の policy 注入と README に露出させ、どのレーンで発効しているかを運用側から確認できるようにする。

---

## I-BYP-09 [minor] G3 第二段（契約が既に許可している判定）が拡張審査予算を消費する

### 該当箇所

`GateStore.request_expansion`（1501-1530行、1577-1601行）

### 根拠

コメントは「a class whose contract already permits an action never burns review budget on it」と述べるが、実装は判定結果に関わらず `expansion_permits` へ行を挿入し、`reviews_used` はその行数を数える。したがって第二段の deterministic-allow も予算を1消費する。artifact-change の予算は2しかないため、契約が許す action を2回 review に掛けると、以降の正当な拡張審査経路が予算切れで塞がる。

迂回ではなく可用性側の欠陥だが、拒否上限（`max_denied_calls = 6`）との併用でターンが座礁しやすくなる。

### 修正方針

`already_allowed` の場合は permit 行を挿入せず（または `verdict` とは別の非予算カラムで記録し）、`reviews_used` の集計から除外する。受入テスト: 契約が許す action を予算回数超えて review に掛けても、その後の未許可 action の review 経路が予算切れにならないこと。

---

## 未確証（推測。確証欠陥として計上していない）

- **相対パス引数の解決基準の一致**: `normalize_repo_relative_path` は `workdir` を受け取れるが、すべての呼出元が省略しており相対パスは常にロック済み root へ相対化される。実際の書込ツールがプロセス cwd に対して相対解決する場合、ゲートとツールの解決先が食い違う。Hermes の書込ツールの相対パス扱いがリポジトリ内から確認できないため未確証。確認方法: ツール実装または schema で相対パス許容の有無を確認し、許容する場合はゲート側で相対指定を拒否するか、ツール側 cwd を root に固定する。
- **ツールカタログの実ツール名網羅**: `ARTIFACT_WRITE_TOOL_CATALOG` / `ARTIFACT_READ_TOOLS` の名前が Hermes の実ツール名と一致しているかを確認できていない。書込側は未列挙で default deny のため fail-closed だが、読み取り側 allowlist に実在しない名前が並んでいると偽の安心になる。また `ARTIFACT_READ_TOOLS` に載ったツールが書込可能フィールドを持つ場合は無検査で通る（locked 状態でパス検査を一切していない。設計は読み取り系の無条件許可を認めているため、これ自体は設計内）。
- **TOCTOU**: admission とツール実行の間にシンボリックリンクを差し替える経路。M2 の隔離実行で覆う残余であり、本レンズでは計上しない。

---

## 司令塔の判断が必要な項目

1. **I-BYP-01 と I-BYP-02 は M1 exit gate の主張そのものに関わる**。修正前の状態では、第一層の「スコープ逸脱の機械的遮断」は seed レーンでも成立していない（I-BYP-01 はパス層、I-BYP-02 は契約バインド層）。修正を M1 に含めるか、exit gate の主張範囲を再定義するかの判断が必要。
2. **I-BYP-02 の修正方針は「seed があるタスクでは分類結果より seed を優先する」ことを含む**。これは「同一タスク内で closeout（push を含む）へ遷移する」運用を禁じることになる。オーケストレーター側でタスク境界を切り直す前提を置いてよいかの判断が必要。
3. **I-BYP-06 の契約フィールド追加はスキーマ変更を伴う**。D-S3-3 の決定（ローカルコミットを allowlist へ含める）を変えるものではないが、契約スキーマの改訂が M1 の範囲かどうかの判断が必要。
4. **I-BYP-08 は D-S3-6 の未決に直結する**。有効化経路を M1 で入れるか（オーナー判断が出るまで既定無効のまま）を確認したい。
