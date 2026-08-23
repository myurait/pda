# S3-M1 実装 反証レビュー記録 — compat レンズ（2026-08-23）

- Status: open（確証欠陥 10 件。対応は goal M1 の残作業および D-S3-6 オーナー判断）
- 処置: `docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md`（2026-08-23。全確証欠陥の処置と、司令塔判断へ回付した項目の対応表）
- 読み取り方針: **本ファイルは `restricted-` 接頭辞の対象。再現手順の具体形を含むため、Fable モデルのセッションでは直接読まない**（安全性分類器の誤検知で会話が停止した実績がある）。対応作業は Opus のサブエージェントへ委譲し、本体へは欠陥ID・抽象名・判断項目のみを返す。
- レビュー対象コミット: `4f3d22f` "feat: artifact-changeの二層契約と契約ライフサイクルをスコープゲートへ実装"
- レンズ: 互換性（既存 closeout / S1 挙動の回帰、Hermes 統合面（hook / plugin / tool 語彙）との適合、既存テスト・incident replay との整合、スキーマ後方互換）
- 正本設計: `docs/design/task-scope-admission-gate.md` の「S3-M1: 決定論コアの具体設計」（377-520 行）
- 確証欠陥: 10 件（blocker 1 / major 5 / minor 4）、棄却 2 件
- 欠陥ID: `I-COM-01` 〜 `I-COM-10`

## 実施内容

- `git show 4f3d22f` による全差分精査、および変更前実装（`b9089b5`）との関数単位比較。
- ローカルテスト実行: `integrations/hermes-scope-gate/tests/`（`test_hermes_integration.py` を除外、`./tmp/venv-scope`）→ **199 passed / 0 failed**。実装サマリの主張と一致。既存テストの改変は 0 件であることを差分で確認。
- 再現スクリプト（git 管理外、`./tmp/work/` 配下）:
  - `tmp/work/probe_compat.py` — 閉じたターンの束縛経路、セッション終了時の closure、Hermes 実ツール語彙、turn_id ローテーション、破損 seed、replay 13、seed 保持、root 表記。
  - `tmp/work/probe_compat2.py` — root 正規化の表記差、replay 13 の正規表記、拒否予算の相互作用。
  - 追加の inline probe — worker 必須ツール（`kanban_show` / `delegate_task` / 読み取り専用 git / 承認前チェックコマンド）。
- Hermes 実ツール語彙の突き合わせ: `integrations/openwebui-hermes-progress/functions/hermes_progress_pipe.py:79-140`（`_PROGRESS_TOOL_ACTIVITY_GROUPS`）および `integrations/hermes-scope-gate/tests/test_hermes_integration.py`。
- 自律 worker レーンの必須手順: `profiles/pda/skills/pda-autonomous-improvement/SKILL.md:22-56`。
- incident replay: `docs/design/task-scope-admission-gate.md` の §10 受入項目一覧と、既存 fixture（`tests/test_scope_gate.py:46-54, 119-140, 540-556`）を突き合わせた。artifact-change 専用の replay fixture ディレクトリは存在せず、既存 fixture は「未強制であること」のみを固定している。

## 確証された欠陥

### I-COM-01 [blocker] 強制 artifact-change ターンで自律 worker 運用の必須ツール群が一律拒否され、拒否予算の枯渇でターン自体が無効化される

**根拠**

`_admit_artifact_change_locked`（`integrations/hermes-scope-gate/scope_gate.py:2537-2606`）の許可集合は `ARTIFACT_READ_TOOLS`（同 438-450）、`terminal`、`ARTIFACT_WRITE_TOOL_CATALOG`（同 475-491）の三つのみで、それ以外は `expansion-required` で拒否される。`ARTIFACT_READ_TOOLS` に列挙された 9 名のうち Hermes 実ランタイムに存在するのは `read_file` と `search_files` の 2 つだけであり（`hermes_progress_pipe.py:79-140` のツール群と `test_hermes_integration.py` の実呼び出しで確認）、`read_files` / `search` / `grep_files` / `glob_files` / `list_files` / `list_directory` / `file_info` は実カタログに現れない。逆に実カタログ側の `session_search` は読み取り系だが許可集合に無い。

強制ターンで拒否されることを実測したツール（すべて `expansion-required`）: `session_search`、`todo`、`kanban_show`、`kanban_heartbeat`、`kanban_comment`、`kanban_request_review`、`web_search`、`delegate_task`。

`profiles/pda/skills/pda-autonomous-improvement/SKILL.md` は Phase 1 の必須手順としてこれらを要求している: 手順 1 が `kanban_show`、手順 3 がカードへの受入基準記録（`kanban_comment`）、手順 4 が任意の `delegate_task`、手順 7 が `kanban_request_review`、Phase 2 手順 4 が `kanban_complete`。手順 6 の `pda_approval` metadata は base SHA / head SHA / changed files / ブランチ / worktree 同一性を要求するが、読み取り専用 git（`git status --short`、`git diff`、`git rev-parse HEAD`、`git log --oneline -1`、`git branch --show-current`）はすべて `git-subcommand` で拒否される（`_admit_artifact_change_git` は `{"add", "commit"}` 以外を拒否、同 2330-2335）。Phase 2 の `python operations/improvement/install.py --check-approval …` は `execution-template` で拒否される。

**さらに拒否が予算を食い潰す**。`ARTIFACT_CHANGE_CLASS_BUDGET["max_denied_calls"] = 6`（同 2154-2161）で、`_admit_artifact_change_locked` は他の判定より前に拒否予算を検査する（同 2554-2557）。実測: 上記の必須ツール 6 件が拒否された時点で予算が枯渇し、その後の

- write scope 内の正当な `write_file` / `patch` → `deny-budget`
- opt-in 済みテンプレートの `python -m py_compile src/app.py` → `deny-budget`

となり、`tool_count = 0`、`denied_count = 8` のまま作業が一切できないターンが残る。到達可能なのは `scope_gate action=lock/complete` のみ。

**再現**（`./tmp/work/probe_compat.py::probe_real_tool_vocabulary`、`probe_compat2.py::probe_deny_budget_interaction`、および inline probe）

1. git worktree を作り、`record_contract_seed(worktree=<realpath>, branch="main", write_paths=["src/*.py"])`。
2. `start_turn` → state `locked`。
3. 予算が新しい状態で write scope 内 `write_file` → `allowed=True action=write-in-scope-change`（正常）。
4. `todo` / `kanban_heartbeat` / `kanban_comment` / `session_search` / `kanban_heartbeat` / `todo` を順に投入 → 6 件すべて `expansion-required`。
5. 直後に手順 3 と同じ write scope 内 `write_file` → `allowed=False action=deny-budget reason='too many denied out-of-scope attempts'`。

**設計・正本との衝突**

- 設計「S3: artifact changes」の Exit「必要 action の false deny 0」を満たせない。
- §10 incident replay 受入項目 5 は「`pytest`、全 branch review、別 cutover wait、`delegate_task` は拒否される」と限定列挙しており、作業記録系ツールの拒否は含まれていない。
- 設計は第一層で「読み取り系ツール（read/search/list 系）: 許可（audit 記録のみ）」と定めているが、実 Hermes の読み取り系ツール名の網羅が取れていない。

**対応方針**

1. `ARTIFACT_READ_TOOLS` を Hermes 実カタログから導出する（少なくとも `session_search` を追加し、実在しない名前は削除するか「将来名の予備」であることをコメントで明示）。ツール名の正本は 1 箇所に置き、`hermes_progress_pipe.py` のツール群との一致テストを追加する。
2. リポジトリ境界の外側にしか作用しないツール群（`kanban_*` / `todo` / `session_search`）を第一層の判定対象から外し、「audit 記録のみで許可」または「リポジトリ write 境界の対象外カテゴリ」として明示的に分類する。契約の `actions` に載せるか、クラス共通の運用ツール集合として扱うかは設計判断。
3. 拒否予算を「write 境界の逸脱試行」に限定し、境界外ツールの拒否や制御ツールの誤用で予算を消費しない。`_artifact_change_decision` が `ARTIFACT_CHANGE_CLASS_BUDGET` の定数を直読みしている点（同 1892）も、ロック済み契約の `budget` を参照する形へ揃える。
4. 読み取り専用 git は I-COM-06 と一体で解決する。

**司令塔判断が要る点**: 作業記録系ツールを artifact-change 契約の許可 action に含めるか、それらが契約に載るまで worker レーンを強制しないか。D-S3-6 の「M1 で worker 適用」分岐はこの解決なしには成立しない。

---

### I-COM-02 [major] ロック済み root の正規化がロック時のみ実体解決で、以後の照合が字句のみのため等価な別表記の絶対パスで全書込・全 terminal が拒否される

**根拠**

ロック済み root は `_validated_worktree_branches`（同 2635-2660）が `Path(worktree).resolve()` で作るため実体解決済み（symlink 解決後）である。一方、以後の照合は字句のみ:

- `normalize_repo_relative_path`（同 320-363）: `locked_root = Path(os.path.normpath(str(root)))` に対する `lexical.relative_to(locked_root)`。`os.path.normpath` は symlink を解決しない。
- `_admit_artifact_change_terminal`（同 2502-2505）: `str(Path(os.path.normpath(workdir))) != str(Path(os.path.normpath(root)))` の文字列比較。

`resolve_existing_ancestor`（同 365-397）は実体解決を行うが、上記の字句ゲートを通過した後にしか呼ばれないため、等価な別表記を救済できない。

**回帰**: closeout 側 `_admit_closeout_locked`（同 2026-2045）は読み取りパスも workdir も `Path(...).resolve()` で正規化しており、両表記を受け付ける。artifact-change だけが表記依存になっている。

**再現**（`./tmp/work/probe_compat2.py::probe_root_spelling`）

1. `<base>/spell/repo` に git worktree を作る。`<base>/spell-link` を `<base>/spell` への symlink にする。
2. `record_contract_seed(worktree="<base>/spell/repo")`（`<base>` は symlink を含む表記）。契約の locked root は realpath 表記 `/private/tmp/.../spell/repo` になる。
3. `git -C <base>/spell-link/repo rev-parse --show-toplevel` は同一の realpath を返す（同じリポジトリであることの確認）。
4. `write_file` に `<base>/spell/repo/src/app.py`（symlink を含む等価表記）→ `allowed=False action=target-closed reason='the target path is outside the locked worktree'`。
5. `terminal` に `git add src/app.py` / `workdir=<base>/spell/repo` → `allowed=False action=target-closed reason='the terminal workdir is outside the locked worktree'`。
6. 同一リポジトリを realpath 表記で指定した対照実行（`probe_replay13_canonical`）では `git add` / `git commit` / focused test がすべて許可される。

**設計との衝突**

設計 第一層は「パス正規化は単一の決定論関数へ集約する。検査は『パス要素を完全に解決し、上位参照要素の不在と制御文字の不在を確認する』形で行い、文字列前処理の積み増しで実装しない」「『絶対パス即 deny』は引数の表記形式ではなく『ロック済み repository / worktree root のいずれにも属さないパス』を意味する」と明記している。現実装は表記形式で拒否しており、terminal workdir が normalizer を通らない第二の判定経路になっている。`README.md` の「resolve to absolute, relativize to the single locked worktree root」という記述も実装と一致しない。

**影響**: fail-closed 方向なので境界の敗北ではない。ただし seed を書く側（オーケストレーター）や Hermes が報告する workdir に symlink 成分が 1 つ含まれるだけで、強制ターンは何もできなくなる（書込・staging・commit・検証実行の全滅）。macOS の `/tmp`・`/var`、symlink 経由のチェックアウト、bind mount 配下で成立する。

**対応方針**

`normalize_repo_relative_path` の内部で root と候補の双方を実体解決してから相対化する（`os.path.realpath` を単一関数の内側に入れる）。`_admit_artifact_change_terminal` の workdir 判定を同じ関数経由にし、独自の文字列比較を撤去する。受入テストに「同一ディレクトリの等価な別表記が許可される」ケースを追加する（現行テストは realpath 表記のみを使っており、この差を検出できない）。

---

### I-COM-03 [major] 閉じたターンの変異拒否が turn_id 束縛時のみ成立し、task/session 束縛の自己 lock レーンでは完了後に変異が再許可される

**失敗方向: fail-open**（本記録で fail-open は I-COM-03 と I-COM-04 のみ。他はすべて fail-closed の false deny）

**根拠**

`resolve_turn_id`（同 1018-1054）の直接 turn_id 参照には `completion_status` の条件が無いが、task_id / session_id のフォールバックには `completion_status IS NULL` が付いている。したがって turn_id が渡らない経路では完了済みターンが解決されず、`admit_without_turn`（同 1954-1980）へ落ちる。`admit_without_turn` は seed の有無だけで判定するため、seed の無い自己 lock レーンでは `not-enforced` で許可になる。

**再現**（`./tmp/work/probe_compat.py::probe_closed_turn_binding`）

1. seed 無しで artifact-change ターンを開始し、`handle_scope_gate(action="lock", worktrees=[repo], write_paths=["src/*.py"])` で自己 lock → state `locked`。
2. `complete_turn(status="success")` → state `completed`。
3. `pre_tool_call(turn_id="t1", …, write_file, path=<repo>/src/app.py)` → `{'action': 'block', … [turn-closed]}`（期待どおり）。
4. `pre_tool_call(task_id=…, session_id=…, turn_id 無し, write_file, path=<repo>/secrets.txt)` → `None`（＝許可）。write scope 外の書込が閉じたターンの後に通る。
5. 対照: seed 有りの同手順は `[contract-unbound]` で block される。

**テストが検出できない理由**: 新規テスト `test_a_closed_turn_keeps_denying_mutation`（`tests/test_artifact_change_scope.py:470-481`）は `store.admit_tool` を明示 turn_id で直接呼んでおり、`resolve_turn_id` を経由しない。また同ファイルの `test_the_shell_hook_path_is_fail_closed_for_a_seeded_task`（同 595-624）は `extra` に `turn_id` を入れずに `validate_shell_payload` を呼んでおり、shell hook 経路が turn_id を運ばない可能性を示している。

**設計との衝突**: 契約ライフサイクル 第4項 規範要件「closure は明示のみ … 閉じたターンでは変異系を拒否したままにする」。`README.md` の「a closed turn keeps denying mutation」も過大主張。

**対応方針**

`admit_without_turn` を「task / session の最新ターンを completion_status に関わらず引き、存在すれば task class の admission へ回す」形にする（閉じたターンは `turn-closed` を返せる）。加えて自己 lock を task 単位の記録として残し（I-COM-04 と共通の修正）、seed 無しレーンでも閉じた後に fail-closed とする。受入テストは `pre_tool_call` / `validate_shell_payload` を turn_id 無しで呼ぶ経路で固定する。

**司令塔判断が要る点**: Hermes の各 hook / shell hook が turn_id を必ず運ぶかどうかはミニPC側の事実確認が必要。運ぶことが確認できれば影響範囲は shell hook 経路に限定される。

---

### I-COM-04 [major] 自己 lock の強制が単一 turn_id に束縛され、ターン粒度が LLM 呼び出し単位だと次ターンで無強制へ戻る

**失敗方向: fail-open**（seed 経路は両 probe で fail-closed を維持。影響は自己 lock レーンに限る）

**根拠**

自己 lock の結果は `turns` 行の `state='locked'` と `contract_json` にしか残らない（`_lock_artifact_change`、同 1290-1297）。`start_turn` は artifact-change について seed のみを参照し（同 939-971）、自己 lock 済みの task であることを知らない。したがって新しい turn_id のターンは `audit` から始まり、`admit_tool` は `not-enforced` を返す。

**再現**（`./tmp/work/probe_compat.py::probe_turn_rotation`）

1. seed 有りレーン: `start_turn(turn_id="t6", task_id="task-f")` → `locked`。同 task_id で `start_turn(turn_id="t7")` → `locked`（強制が持続する。seed の権威が持続する実装判断どおり）。
2. 自己 lock レーン: `pre_llm_call(turn_id="t8", task_id="task-g")` → 自己 lock → `locked`。同 task_id で `pre_llm_call(turn_id="t9")` → state `audit`。
3. `pre_tool_call(turn_id="t9", …, write_file, path=<repo>/secrets.txt)` → `None`（write scope 外の書込が許可される）。

**設計との関係**: 実装チェックリスト第7項は「LLM 呼び出し後の監査フックの発火粒度が『ユーザーターン単位』か『LLM 呼び出し単位』かを、有効化前に synthetic payload で確認する」を要求している。post_llm_call 側の closure は対処済み（`test_a_locked_turn_survives_an_intermediate_audit_hook`）だが、`pre_llm_call` 側で turn_id がローテーションする場合の自己 lock 消失は未対処・未検査。

**対応方針**

自己 lock を task スコープの記録として永続化する（`contract_seeds` と同型のテーブル、`origin='self'` で区別）。`start_turn` は seed と同じ経路でこれを参照し、自己 lock 済み task の後続ターンを `locked` として作る。少なくとも「一度自己 lock した task を未強制へ戻さない」ことを不変条件として受入テストに固定する。

**司令塔判断が要る点**: hook 発火粒度はミニPC側の事実。自己 lock は対話ターン専用（自律レーンは常に seed 経路）であるため、宣言済み残余として受容する選択もあり得る。

---

### I-COM-05 [major] 強制 artifact-change ターンが正常なセッション終了で閉じられず、完了制御を呼ばない限り開いたまま残る

**根拠**

`post_llm_call`（`plugin_runtime.py:257-278`）は強制状態の artifact-change ターンに対して早期 return するようになった（意図どおり）。しかし `on_session_end`（同 280-290）は `completed and not failed and not interrupted` のとき早期 return する。結果として、正常終了したセッションでは強制 artifact-change ターンを閉じる経路が存在しない。

**再現**（`./tmp/work/probe_compat.py::probe_session_end_closure`）

1. seed 有りで `pre_llm_call` → state `locked`。
2. `post_llm_call(...)` → 変化なし。
3. `on_session_end(completed=True, failed=False, interrupted=False)` → `{'state': 'locked', 'completion_status': None}`。
4. 同一 store で closeout ターンを作り `post_llm_call` → `{'state': 'completed', 'completion_status': 'partial'}`（従来挙動は保持されている）。

**影響**

- `resolve_turn_id` の task_id / session_id フォールバックは `completion_status IS NULL` を条件にするため、この滞留ターンが後続呼び出しに解決され続ける。wall budget（3600 秒）が過ぎた後は同 task の呼び出しが `wall-budget` で拒否される。
- 回収は `purge_expired` の 30 日保持のみ。
- 付随: `ARTIFACT_ENFORCED_STATES` に `"completed"` が含まれるため、閉じたターンに対しても `pre_llm_call` が artifact-change の policy 文脈を注入する（`plugin_runtime.py:61-66`）。

**設計との衝突**: 契約ライフサイクル 第4項「完了: 明示的な完了制御アクション、または session 終了」。session 終了側が正常経路で実装されていない。

**対応方針**

`on_session_end` で強制 artifact-change ターンを常に閉じる（正常終了は `success`、失敗・中断は従来のステータス）。あるいは wall budget 超過ターンを次回 `start_turn` の `purge_expired` と同じ入口で `interrupted` として掃く。`pre_llm_call` の policy 注入条件を `completed` を除いた集合に変える。

---

### I-COM-06 [major] 第一層に読み取り専用 git が無く、設計 §10 incident replay 受入項目と第一層の許可集合が未整合。強制経路の replay 検証も存在しない

**根拠**

`_admit_artifact_change_git`（同 2330-2335）は `{"add", "commit"}` 以外の全 subcommand を拒否する。実測（realpath 表記、opt-in 済み契約）:

- `pytest tests/test_app.py` → 許可（`run-focused-test`）
- `pytest -x -q --maxfail=1 tests/test_app.py` → 許可（false deny 無し。第二層の allowlist は意図どおり動作）
- `pytest tests` → 拒否（`execution-target`、ディレクトリ単位）
- `pytest` → 拒否（`execution-target`、対象なし）
- `git add src/app.py` → 許可、`git commit -m "fix"` → 許可
- `git push origin main` → 拒否（`git-subcommand`。設計どおり別 finalization 契約へ残す判断）
- **`git status --short` / `git diff` / `git rev-parse HEAD` / `git log --oneline -1` / `git branch --show-current` → すべて拒否（`git-subcommand`）**

設計 §10 の受入項目 4 は「`git status`、candidate diff 確認、secret check、stage、commit、push、remote ref 確認は許可される」、項目 13 は「`失敗testも修正し、全test後にcommit/push` と明示した別 fixture は `artifact-change` となり、対象修正と verification を誤って拒否しない」と定めている。項目 13 に対応する既存 fixture（`tests/test_scope_gate.py:46-54` と `540-556`）は `task_class == "artifact-change"` かつ `action == "not-enforced"` のみを固定しており、強制経路を一切通っていない。artifact-change 専用の incident replay fixture は存在しない。

`git add` が「write scope 内の明示パス列挙のみ」を要求する一方で、変更対象の列挙元になる `git status` / `git diff` が拒否されるため、staging に必要な情報を契約内の手段で得られない。I-COM-01 の SKILL.md 手順 6（base/head SHA、changed files、ブランチ、worktree 同一性）も読み取り専用 git を必要とする。

実装サマリはこれを明示的な逸脱として申告している（「terminal 経由の読み取り専用 git は artifact-change では許可していない（設計記載外の拡張を避ける厳密読み）」）。したがって欠陥の所在は「実装が設計に従っていない」ではなく「設計 §11 の第一層列挙と §10 の受入項目が未整合であり、厳密読みが運用フローを断絶させる」点にある。

**対応方針**

第一層に closeout が既に許可している読み取り専用 git 部分集合（`status` / `diff` / `rev-parse` / `branch` / `log`、いずれも closeout と同水準の引数検査つき）を加える。closeout 側の `_diff_args_are_bounded` / `_verification_action` と同じ厳密さの独立実装を artifact-change 用に置く（コードパス非共有の方針は維持）。あわせて artifact-change 用の incident replay 受入項目を §10 に別立てし、強制状態での fixture を追加する（現行 fixture は未強制状態しか固定していない）。

**司令塔判断が要る点**: §10 の受入項目一覧は closeout 事例を前提にしている。artifact-change 版の受入項目を新設するか、項目 13 を S3 第一層の許可範囲に合わせて改訂するか（`push` を artifact-change の対象外と明記するか）はオーナー判断。

---

### I-COM-07 [minor] `contract_seeds` が保持期間管理の対象外で、失効した seed が新しいセッションのターンをロックし続ける

**根拠**

`purge_expired`（同 772-806）は `decisions` / `candidates` / `turns` のみを削除し、`contract_seeds` に触れない。`record_contract_seed` に TTL は無く、`get_contract_seed`（同 902-923）は `session_id` を照合しない（seed 側は列を持つが未使用）。`start_turn` は task_id 一致のみで seed を消費するため、同一 task_id の後続ターンは無期限にその seed へロックされる。

**再現**（`./tmp/work/probe_compat.py::probe_seed_retention`）

1. seed を記録し、ターンを開始。
2. `turns.started_at` と `contract_seeds.created_at` を保持期間外の値へ更新。
3. `purge_expired()` → turns 1 件削除、seed は残存。
4. 別 session_id・新しい turn_id で同一 task_id の `start_turn` → state `locked`（古い seed の worktree と write scope でロックされる）。

fail-closed 方向（worktree が消えていれば `mutation-denied`）だが、状態が無限に増え、セッション境界を越えて権威が持続する。

**対応方針**

`purge_expired` に `contract_seeds` を `created_at` 基準で含める。`session_id` が記録されている seed は session 一致を必須にする（または seed に明示 TTV を持たせる）。「seed をタスク全体の上限として持続させる」実装判断（サマリで申告済み）は保つが、持続範囲の上限を state 側で切る。

---

### I-COM-08 [minor] 制御ツールのスキーマ緩和で closeout lock の必須指定検査が実行時例外へ後退した

**根拠**

`__init__.py` の `_SCOPE_GATE_SCHEMA` で `parameters.properties.targets.required` が `["repositories", "worktrees", "branches"]` から `["worktrees"]` へ緩和された（`__init__.py:57`）。`plugin_runtime.handle_scope_gate` は `repositories` / `branches` を `_optional_string_list` で受けるため（`plugin_runtime.py:174-176`）、これらを欠いた closeout lock はツール境界で弾かれず `_lock_closeout` まで到達し、`ValueError("repository-closeout requires non-empty repositories, worktrees, and branches")` が `{"ok": false, "error": …}` として返る。

このとき `admit_tool` は `scope_gate` 制御アクションを既に許可済みで `tool_count` を加算している（`_closeout_decision`、同 1837-1855）。closeout の discovery 段の tool 予算は 3（`_admit_closeout_discovery`、同 1990-1991）なので、スキーマ不正な lock の再試行が discovery 予算を消費する。

契約スキーマ側（`schemas/scope-contract-v1.schema.json`）は `targets.required` に 4 キーを保持しているため、生成される契約の妥当性は落ちていない。影響は S1 のツール境界検査とターン予算に限られる。

**対応方針**

ツールスキーマで class 条件付きの必須指定にする（closeout は 3 キー必須、artifact-change は `worktrees` + `write_paths` 必須）。少なくともスキーマ不正な制御呼び出しでターン予算を消費しないようにする。

---

### I-COM-09 [minor] README・監査記録の「seed 消費」表現が持続的 seed の実装と不一致で、system prompt section も closeout のみを記述している

**根拠**

- `README.md` は「an assignment seed … is consumed at turn start」と書くが、実装は seed をタスク全体の上限として持続させる（サマリで申告済みの実装判断）。
- `start_turn` の消費記録は `consumed_at = COALESCE(consumed_at, ?)` / `consumed_turn_id = COALESCE(...)`（同 999-1007）なので初回ターンのみが記録される。実測（`probe_turn_rotation`）で、2 つ目のターンが同じ seed でロックされても `consumed_turn_id` は 1 つ目のまま。どのターンが seed を使ったかの監査痕が残らない。
- `_SCOPE_GATE_SCHEMA` と同居する `_SYSTEM_POLICY`（`__init__.py:15-19`、常時注入される system prompt section）は closeout のみを記述しており、artifact-change の二層契約は `pre_llm_call` の per-turn 注入のみに依存する。強制状態に入らないターンでは実行主体が lock 手順を知る手段が無い（現状はどのレーンも強制 off なので実害は無いが、有効化時に効いてくる）。

**対応方針**

`contract_seeds` の消費記録を「初回」ではなく「使用ターン一覧」にする（別テーブルまたは decisions への記録）。README の文言を持続的上限の実装に合わせる。`_SYSTEM_POLICY` に artifact-change の二層契約と lock 手順の要約を加えるか、クラス別 policy は `pre_llm_call` が供給する旨を明記する。

---

### I-COM-10 [minor] 強制ターンの起動ごとに git 2 プロセスとスキーマメタ検証が走り、初回の一過性失敗が回復不能な `mutation-denied` を作る

**根拠**

seed 有り artifact-change タスクの `pre_llm_call` は毎回 `start_turn` → `_build_artifact_change_contract` を通り、`_validated_worktree_branches` が `subprocess.run(..., timeout=3)` を 2 回（`rev-parse --show-toplevel` と `branch --show-current`）実行し、`_validate_contract_against_schema`（同 2624-2632）がスキーマファイルを読み直して `check_schema` とインスタンス検証を毎回行う。LLM 呼び出しのホットパスに最大 6 秒の外部プロセス待ちが入る。

初回呼び出しで一過性の失敗（git のロック競合、タイムアウト、一時的な I/O エラー）が起きると、`except (ValueError, PathRejected)` が state を `mutation-denied` に固定して INSERT する（同 960-964）。以後 `ON CONFLICT(turn_id) DO NOTHING` で行は上書きされず、`_lock_artifact_change` は `mutation-denied` からの lock を拒否する（同 1265-1268）。同じ turn_id の間は回復手段が無い。

`OSError` / `subprocess.SubprocessError`（`TimeoutExpired` を含む）は `_validated_worktree_branches` 内で `ValueError` に包まれているため hook が例外で落ちることはない（**棄却済みの疑い**、下記参照）。問題は「一過性失敗と検証失敗が区別されない」点にある。

**再現**

`probe_broken_seed`（worktree を seed 後に削除）で state が `mutation-denied` になることを確認。一過性失敗の注入は未実施（同じ except 経路を通るため経路上は同一）。

**対応方針**

seed の実体検証結果をターン行にキャッシュし、`pre_llm_call` ごとの再実行をやめる。検証失敗を「検証結果としての不一致（fail-closed、回復不可）」と「検証の実行失敗（ターン内でリトライ可能）」に分け、後者はターンを `mutation-denied` に固定しない。`_validate_contract_against_schema` のスキーマ読込と `check_schema` はプロセス内でキャッシュする。

---

## 棄却した疑い

- **seed 検証失敗で hook が例外を投げる**: `_validated_worktree_branches` は `OSError` と `subprocess.SubprocessError`（`TimeoutExpired` を含む）を `ValueError` に包んでおり（同 2653-2654）、`start_turn` の `except (ValueError, PathRejected)` が受ける。worktree を削除した状態で `pre_llm_call` を呼び、例外ではなく state `mutation-denied` になることを実測（`probe_broken_seed`）。fail-closed で設計どおり。
- **既存の永続化済み契約がスキーマ必須項目追加で無効化される**: 契約スキーマの再検証は `_validate_contract_against_schema` が lock 時にのみ行い、`contract_json` の読み出し側（`_admit_closeout_locked` / `_admit_artifact_change_locked` / `_lock_closeout` の冪等再 lock）は `json.loads` のみで再検証しない。既存 state DB の closeout 契約は無効化されない。closeout 分岐の budget 制約は変更前から実キー（`max_wall_seconds` / `max_tool_calls`）を使っており、今回の修正対象は bounded-operation と artifact-change の分岐のみ。DB マイグレーションも `PRAGMA table_info` ベースの列追加（`contract_origin`）が入っており、既存 DB で欠落しない。

## 参考: 変更前後の比較で確認した非回帰

- `_lock_closeout` は引数検査・候補集合検査・ブランチ一致検査・budget 算出・contract 構造のすべてが変更前と同一で、順序も保たれている（`write_paths` / `test_paths` / `execution` が渡された場合の明示拒否のみ追加）。
- `_closeout_decision` は変更前の `admit_tool` 内インライン分岐と同一の判定・同一の理由コードを持つ。
- `request_expansion` の stage 2 は `task_class == "repository-closeout"` のハードコード分岐から `locked_admission_for(task_class)` の dispatch へ一般化されたが、closeout の expansion 予算は 0 のため stage 2 は closeout では到達不能であり、挙動は不変。
- `post_llm_call` の closeout 側 closure（`partial`）は保持されており、実測で確認（`probe_session_end_closure`）。
