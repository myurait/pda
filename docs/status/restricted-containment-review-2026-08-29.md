# 封じ込め実行器の反証レビュー（2026-08-29）

- Status: review complete / findings recorded（統合前の反証記録）
- 対象: 未コミットの `operations/integration/`（`contained_runner.py` 1196行、`probe/containment_probe.py`、`tests/test_contained_runner.py`、`README.md`、`__init__.py` × 2）
- レンズ: (1) マウント面の逸脱余地 (2) 環境変数・docker経由のホスト資格 (3) `--network=none` の徹底 (4) fail-open (5) 出力の信頼
- 照合した一次資料: `operations/integration/` 実装全体、`docs/design/auto-integration-gate.md`、`docs/status/restricted-auto-integration-review-2026-08-29.md`、`integrations/hermes-scope-gate/scope_gate.py`、`operations/improvement/{scope_seed.py,install.py}`
- 検査手法: 対象モジュールを直接 import し、各主張に対応する入力を与えて戻り値を実測した（下記の blocker/major は全て実測結果を伴う）

## 件数

- blocker 2 件 / major 4 件 / minor 4 件（計 10 件）

## 5軸に対する反証の到達点

- **(1) マウント面**: 個別の逸脱は閉じている。マウント元は常に `_resolve()` 済み実パス、target は宣言スペル、`..` を含む引数は拒否、worktree 内から外へ出る symlink は静的検査が検出、runtime mount と worktree の入れ子は拒否。破れは deny-set 自体の由来（B2）と `--volume` フィールド区切りの未検証（m2）。
- **(2) 環境**: コンテナ側は成立。ホスト環境は継承されず（`--env=` 明示列挙のみ）、`docker.sock` はどこにもマウントされず、`--privileged`/`--network=host` は argv に現れない。破れはホスト側の検査サブプロセスの env 継承（m1）。
- **(3) ネットワーク**: 徹底されている。`--network=none` は `build_argv` で無条件に付き、上書き経路が無い。`docker build` は存在せず、`docker pull` も実装せず（`verify_image_present` は `image inspect` のみ）、ローカル不在は拒否に倒れる。反証は成立しなかった。
- **(4) fail-open**: 「素で実行」経路は存在しない。docker を経由せず pytest を起動するコードパスは全ファイルに無い。ただし docker 不在時は構造化出力を返さず素の例外で終わる（M3）、および opt-out にフロアが無い（M4）。
- **(5) 出力の信頼**: 破れている（B1）。コンテナ内コードは判定に効く3値（収集件数・junit集計・終了コード）を全て偽造でき、`verdict: pass` を作れる。

---

## blocker

### B1. 判定出力は被験コードが偽造でき、`verdict: pass` が偽装可能

- 実装の主張: モジュール冒頭「The judgement output is the structured triple design §5 G2 requires as input: process exit code plus collected count *and* executed count, so that a collection error, an OOM kill or a missing dependency is distinguishable from "zero failures"」。実装報告は「判定は pytest 自身の出力のパースに依存する」を未成立事項2として挙げるが、影響を「保証の弱さ」ではなく「設計の帰結」として書いている。
- 検証事実: 3つの判定入力すべてが、被験コードが書き込めるのと同じ stdout / 同じプロセスの終了コードにある。
  - `_extract_junit`（`contained_runner.py:820-825`）は `stdout.find(_JUNIT_BEGIN)` / `find(_JUNIT_END)` で **最初の** 出現を採る。境界標識 `<<<PDA-CONTAINED-JUNIT-BEGIN>>>` は定数（`:215-216`）で、かつ `_container_script`（`:648-660`）が本物の junit を pytest 実行の **後** に印字するため、被験コード側が先に印字した偽ブロックが常に勝つ。
  - `_parse_collected`（`:806-815`）も `re.search` の最初一致。
  - 終了コードは pytest プロセス自身のもの（`rc=$?`）なので、collection 時に読み込まれる `conftest.py` から `os._exit(0)` すれば 0 になる。
- 具体形（実測）: 次の stdout と終了コード 0 を `interpret()` に与えると、本物の集計が `failures="3"` であっても判定は pass になる。

```
collected 707 items
<<<PDA-CONTAINED-JUNIT-BEGIN>>>
<testsuite name="pytest" tests="707" failures="0" errors="0" skipped="0"/>
<<<PDA-CONTAINED-JUNIT-END>>>
=== 3 failed, 704 passed ===
<<<PDA-CONTAINED-JUNIT-BEGIN>>>
<testsuite name="pytest" tests="707" failures="3" errors="0" skipped="0"/>
<<<PDA-CONTAINED-JUNIT-END>>>
```

```
{'verdict': 'pass', 'exit_code': 0, 'collected': 707, 'executed': 707,
 'failures': 0, 'errors': 0, 'skipped': 0, 'reasons': []}
```

  この stdout を作るのは worktree 内の `conftest.py` のトップレベルコード1つで足りる。`collection_static_check` は追跡外（`??`）の設定ファイルだけを見るため（M2）、コミット済みの `conftest.py` は検出されない。
- 重大度理由: 封じ込めは「被験コードがホストへ触れないこと」を実際に達成している（プローブ21件の測定はその範囲で有効）が、この穴があると「テストが通った」という判定そのものが被験コード側の自己申告に戻る。G2 が受け取る三つ組は、fail を pass に変えられる限り統合可否の根拠にならない。`restricted-auto-integration-review-2026-08-29.md` の B1 が閉じるのはホスト権限の側だけで、判定の側は開いたまま残る。
- 閉じ方の方向（判断はオーナー）: 標識のノンス化は不十分（コンテナ内の子プロセスが `/proc/<pid>/cmdline` から標識を読める）。判定入力をコンテナ側 stdout から外すには、報告専用の書込面をホスト側に1つ与えて junit をそこへ書かせる（`--rm` を外して `docker cp` で回収する、あるいは報告ファイル専用の rw マウント1点を認める）といった、ホスト書込面ゼロの原則との明示的なトレードオフが必要。

### B2. deny-set は `$HOME` 由来で、HOME が変われば列挙保証そのものが消える

- 実装の主張: モジュール冒頭「deny-set -- the secret and control-plane paths of §6 are enumerated」。`default_secret_paths` の docstring「``kanban.db`` covers the approval ledger: ``pda_owner_approvals`` is a table in the Kanban control DB, not a separate file, so denying the DB denies the ledger」。実装報告は「承認ledger `pda_owner_approvals` はKanban制御DB内のテーブルなので `~/.hermes/kanban.db` 拒否で覆う」と述べる。
- 検証事実: `default_secret_paths`（`:116-119`）の基準は `Path.home()`、すなわち `$HOME`。設計§6は封じ込め実行を「別principal」で走らせることを要求しており、その principal の HOME は `/home/user` ではない。加えて `$HOME` は呼出側が設定できる。実測:

```
HOME=/tmp/nowhere -> default_secret_paths()[0] == /tmp/nowhere/.hermes/auth.json
runtime mount /home/user/.hermes/kanban.db が deny-set に一致するか -> False
```

- 具体形: 列挙保証が外れた後に残るのは補助掃引 `_shallow_secret_hits`（`:283-317`）だけで、その `_SECRET_BASENAMES`（`:150-164`）に `kanban.db`・`state.db`・`config.yaml` は無く、`sessions`/`logs`/`cron`/`hooks` も見ない。さらに掃引はディレクトリを `os.scandir` する実装なので、**ファイル**を直接 mount した場合は `OSError` で抜けて 0 件になる。よって `HOME` が `/home/user` 以外の値になっている実行主体では、`--runtime-mount /home/user/.hermes/kanban.db` が検証を通り、承認 ledger と Kanban 盤面が読み取り可能な状態でコンテナに入る。同じことが `state.db`・`config.yaml` について成立する。
- 重大度理由: 「列挙が保証、掃引は多層防御」という実装自身の役割分担が、保証側の基準点が可変であるために反転する。しかも反転は静かに起きる（拒否が出ないだけ）。実装報告の fail-closed 実測は `HOME=/home/user` の下でのみ再現する条件付きの事実であり、そのまま封じ込めの性質として読めない。
- 閉じ方の方向: 秘密パスの基準を `$HOME` ではなく設定として与えられた不変の実HOME（agent-node なら `/home/user` の literal）に固定し、`ContainmentConfig` に基準HOMEを持たせて未指定を拒否する。

---

## major

### M1. 予約引数の照合が完全一致と `=` 付き前置のみで、pytest の付着形が素通りする

- 実装の主張: `_DENIED_ARG_PREFIXES` の注記「Argument forms that would let the caller re-open the collection surface the static check just closed」。実装報告は「`-o=python_files=*.py` も拒否」と述べる。
- 検証事実: `_validate_extra_args`（`:415-419`）の照合は `arg == prefix or arg.startswith(prefix + "=")`。pytest の `-p` / `-o` は単ダッシュ短オプションで、argparse は値の付着形を受ける（`-pmyplugin` → `plugins=['myplugin']`、`-opython_files=*.py` → `override_ini=['python_files=*.py']` を実測）。実測した判定:

```
-pmyplugin            -> ALLOWED
-pno:cacheprovider    -> ALLOWED
-opython_files=*.py   -> ALLOWED
-oaddopts=-p x        -> ALLOWED
-qq                   -> ALLOWED
-o=python_files=*.py  -> 拒否   ← 報告が実測したのはこの形だけ
```

- 具体形: `--pytest-arg=-opython_files=*.py` で収集規則を静的検査の後に書き換えられ、`--pytest-arg=-pmyplugin` で任意プラグインを読み込ませられる。`-qq` は `collected N items` 行を消すので infra_error に落ちるだけ（判定汚染ではない）。単体テスト95件はこの付着形を1件も与えていない。

### M2. 収集面の閉鎖は「追跡済み」設定ファイルで再開できる

- 実装の主張: `collection_static_check` の docstring「a pytest configuration or ``conftest.py`` brought in without being part of the Git canon」「Tracked-but-modified files are deliberately not flagged -- those are in-scope worker changes」。
- 検証事実: 検査対象は `_untracked_paths`（`:583-608`）が返す `git status --porcelain -uall` の `??` 行のみ。worker が新規 `conftest.py` を `git add` してコミットすれば `??` に現れず、検査を通る。`_COLLECTION_CONFIG_NAMES`（`:245-254`）に `pyproject.toml` は入っているが、これも追跡済みなら見ない。
- 具体形: 追跡済み `pyproject.toml` の `[tool.pytest.ini_options] addopts` は M1 の予約引数群（`-p`、`python_files` 上書き等）を丸ごと再導入できる。カード branch は通常コミットして提出されるため、この経路は例外ではなく既定の形になる。B1 の偽造 `conftest.py` も同じ理由で検出されない。

### M3. docker 不在時に構造化出力を返さず素の例外で終わる

- 実装の主張: `run` の docstring「Every precondition failure is returned as an ``infra_error`` verdict or raised, never as a pass」。
- 検証事実: `verify_image_present`（`:939-953`）と `run` 内の `subprocess.run`（`:1037`）は `FileNotFoundError` を捕まえない。`main` は `ContainmentError` のみ捕捉する。実測:

```
docker="docker-does-not-exist" -> UNCAUGHT FileNotFoundError [Errno 2] ... 'docker-does-not-exist'
```

- 具体形: CLI は traceback を吐いて終了コード 1 を返す。1 は `verdict: fail`（テスト失敗）と同じ終了コードなので、JSON の `verdict` を読む呼出側は何も受け取れず、終了コードだけを読む呼出側は「テストが落ちた」と解釈する。fail-open（素で実行）には倒れないが、fail-closed の理由が呼出側に伝わらない。`docker` が存在するが daemon が落ちている場合は `image inspect` が非0で返るため infra_error になり、こちらは正しい。

### M4. opt-out にフロアが無く、単体テストも実列挙を一度も行使しない

- 検証事実: `effective_secret_paths`（`:378-381`）は `if self.secret_paths is not None` で分岐するため、`secret_paths=()` を渡すと deny-set が空になる（実測 `-> ()`）。`run(..., skip_static_check=True)`（`:993`）は symlink 検査と追跡外設定ファイル検査を丸ごと外す。どちらも CLI には露出していないが、改善レーンはこのモジュールをライブラリとして呼ぶ想定なので呼出側次第で無効化できる。加えて既定テスト fixture `make_config`（`:53-66`）自身が `secret_paths` を存在しないパスに差し替えているため、`default_secret_paths()` の実列挙が守るべき対象は95件のどれからも行使されない（B2 が単体テストで露見しなかった理由）。

---

## minor

- **m1. ホスト側検査サブプロセスだけが env を継承する**: `run` 本体の `subprocess.run` は `env={"PATH": ...}` で環境を落とすが（`:1042`）、`verify_image_present`（`:942`）と `_untracked_paths`（`:586`）は env を渡さずホスト環境を継承する。ホスト環境に `DOCKER_HOST` があれば digest 在否を確認したデーモンと実行するデーモンが別になり、`GIT_DIR`/`GIT_WORK_TREE` があれば追跡外設定ファイル検査が別ツリーの結果を返す。3箇所の env 方針を揃えるべき。
- **m2. マウント文字列のフィールド区切りを検証していない**: `Mount.as_arg`（`:326-327`）は `f"{source}:{target}:ro"` を組むだけで、パスに `:` や `,` が含まれる場合を拒否しない。`--volume` は `:` 区切りなので、区切り文字を含むパスはフィールド数が変わる。現状 worktree 名は呼出側（ハーネス）が決めるため到達性は低いが、入力検証の欠落として残る。
- **m3. `uid`/`gid` の既定が `None`**: `ContainmentConfig` の既定では `--user` が付かず root 実行になる（`:837-838`）。CLI は常に `os.getuid()/getgid()` を渡すので実運用は uid=1000 だが、ライブラリ既定は弱い方に倒れている。`--cap-drop=ALL`・ro rootfs・tmpfs noexec があるため実害は限定的。
- **m4. gitfile 拒否により実レーンの worktree では動かない（自己申告済み・確認のみ）**: `validate`（`:452-461`）は `.git` がファイルの worktree を拒否する。`git worktree add` が作る隔離 worktree は必ずこの形なので、実装報告の未成立事項1のとおり、現状の封じ込めで改善レーンの worktree は実行できない。gitdir の ro 追加マウントは M1 レビューの B1 を閉じるための前提条件であり、G2 結線前に解消が必要。

---

## 反証が成立しなかった主張（確認できた事実）

- `--network=none` は `build_argv` の固定 argv に含まれ、`extra_args`・`--env`・`--pytest-arg` のいずれからも上書きできない。ネットワークを持つ副経路（`docker build`、`docker pull`）は実装に存在しない。イメージはローカル不在なら拒否。
- `docker.sock` は argv・スクリプト・マウント列のどこにも現れない。`--privileged`・`--network=host`・`--pid=host` も同様。
- コンテナ環境は `base_env` の固定辞書と検証済み `extra_env` のみ。`_ENV_DENY_PREFIXES`/`_ENV_DENY_SUBSTRINGS`/`_RESERVED_ENV_NAMES` は `HERMES_*`・`AWS_*`・`GITHUB_*`・token/secret 系の名前を拒否し、ホスト環境の暗黙継承は無い。
- マウント元は常に `_resolve()`（realpath）。worktree ルートが symlink でも実体に解決され、worktree 内から外へ出る symlink は静的検査が検出、収集対象の `..` は `validate`・`_validate_extra_args` の両方で拒否、runtime mount と worktree の入れ子は拒否。
- docker を経由せず pytest を起動するコードパスは `operations/integration/` 全体に無い。検証不能・イメージ不在・メモリ不足・タイムアウトはいずれも `infra_error` verdict を返し、pass には倒れない。

---

## 処置記録（2026-08-29）

- 対象: `operations/integration/`（`contained_runner.py`、`tests/test_contained_runner.py`、`README.md`）
- 処置後のテスト: `operations/integration/tests/` 147件 pass（処置前95件、追加52件）。リポジトリ全体の緑は 559→611 pass で減少なし。残る 245 failed / 12 errors は開発PCに hermes 実行環境（`hermes_cli`、`pda`、`yaml`、`fastapi`、`aiohttp`）が無いことによる既存の赤で、本処置の前後で同数・同一ファイル。
- 内訳: blocker 1件処置＋1件は部分処置（残余をオーナー判断へ）、major 4件処置、minor 3件処置・1件据え置き。

### B1 判定出力の偽造 — 部分処置。残余はオーナー判断

事実: 指摘どおり。掲載された stdout と終了コード0を `interpret()` に与えると `verdict: pass` になった。

処置（検出可能化）:

- 報告標識と junit 出力先を実行ごとのトークン付きに変更（`new_report_token`/`junit_markers`/`junit_path`）。定数 `<<<PDA-CONTAINED-JUNIT-BEGIN>>>` と固定パス `/tmp/pda-contained-junit.xml` は消滅。
- `_extract_junit` は標識対の**出現数**を数え、2組以上なら値を選ばず `infra_error`。「先頭一致で偽ブロックが勝つ」経路はこれで閉じる。
- `_parse_collected` は収集件数の申告が複数あり値が食い違う場合を `infra_error`。
- junit の `tests` が収集件数を**上回る**場合を `infra_error`。下回る側は `-k`/`-m`/`--deselect` で正当に起きるため対象外。

固定したテスト: `test_forged_junit_block_printed_before_the_real_one_is_refused`（掲載された stdout そのもの）、`test_a_second_junit_block_after_the_real_one_is_also_refused`、`test_conflicting_collected_counts_are_refused`、`test_junit_total_above_the_collected_count_is_refused`、`test_deselection_keeps_the_junit_total_below_collected_without_a_fault`、`test_report_markers_are_per_run_not_a_compile_time_constant`、`test_a_block_carrying_another_runs_token_is_not_read`、`test_junit_report_path_carries_the_token`。

残余（閉じていない）: 判定3値はいずれも pytest が出力し、pytest は被験コード自身のプロセスである。`conftest.py` が整合する junit を報告先へ書いて `os._exit(0)` すれば、ホスト側に独立した観測者が無いため矛盾を検出できない。トークンは `/proc` から読めるので秘密ではなく、閉じる手段にはならない。したがって `verdict: pass` は「テストが通った証明」ではなく「通ったという申告に検出可能な矛盾が無い」ことの証明であり、この性質を README と module docstring に明記した。

閉じるには被験プロセスが書けない報告面（`--rm` を外した `docker cp`、または報告専用の rw マウント1点）が必要で、ホスト書込面ゼロの原則とのトレードオフになる。既定方針は「今回は検出強化のみ、報告面の追加はオーナー判断を経てから」。G2 結線前に決着が必要な項目として m4 と並べて残す。

### B2 deny-set の基準HOME — 処置

事実: 指摘どおり。`HOME=/tmp/nowhere` で `default_secret_paths()` の基準が移動し、`/home/user/.hermes/kanban.db` は deny-set に一致しなかった。

処置:

- `default_secret_paths(home)` の `home` を必須引数に変更。`Path.home()` 参照を削除。
- `ContainmentConfig.secret_home` を新設（未指定・相対は `validate` が拒否）。`for_agent_node` と CLI 既定は literal `/home/user`。
- passwd データベースから読む実HOME（`invoking_user_home`、環境変数で動かない）を deny-set に合流。`secret_home` の設定を誤っても実行ユーザ自身の資格情報は拒否される。
- ランタイムマウント元をディレクトリに限定。補助掃引が `os.scandir` でファイルを見られない構造的な穴を、ファイルマウント自体の拒否で閉じた。掃引の名前集合は変更しない（`config.yaml` は worktree を含む全マウント元を2階層走査するため、正当なリポジトリを拒否して封じ込め自体を止める）。

固定したテスト: `test_deny_set_does_not_follow_the_environment_home`、`test_unset_secret_home_is_refused`、`test_relative_secret_home_is_refused`、`test_deny_set_also_covers_the_invoking_user_real_home`、`test_control_plane_file_mounted_on_its_own_is_refused`、`test_any_file_as_a_runtime_mount_is_refused`。

### M1 予約引数の付着形 — 処置

事実: 指摘どおり。`-pmyplugin`、`-opython_files=*.py`、`-oaddopts=-p x`、`-qq` はいずれも素通りした。

処置: 短オプションは文字集合 `{p, o, c, q}` で照合し、値の付着形もクラスタ形も拒否。長オプションは argparse の一意接頭辞略記も拒否（`--overr=addopts=...` は `--override-ini` に到達する）。文字照合は予約文字を含むだけのクラスタ（現実的な例は `-rfc`）を過剰に拒否するが、封じ込めとして倒す向きはこちらで、引数名を挙げて拒否される。

固定したテスト: `test_attached_and_abbreviated_reserved_args_are_refused`（付着形・略記11形）、`test_ordinary_args_survive_the_stricter_matching`（`-x`/`-v`/`-vv`/`-s`/`--maxfail=1`/`--tb=short`/`--durations=10`/`--` が通ることの確認）。

### M2 収集面の閉鎖 — 処置

事実: 指摘どおり。検査対象は `??` 行のみで、追跡済みの `conftest.py`・`pyproject.toml` は見ていなかった。

処置: `ContainmentConfig.baseline_ref` を新設（CLI 既定 `origin/main`、未指定は `validate` が拒否）。追跡外の検査を残したうえで、`git diff --name-only <baseline_ref>` により baseline との差分（コミット済み・未コミットの両方）にある収集設定ファイルも finding とする。baseline ref が解決できない場合は skip ではなく finding。

既存テスト `test_tracked_but_modified_conftest_is_not_flagged` は、指摘が示したとおり本来閉じるべき経路を許す挙動を固定していたため、`test_tracked_conftest_modified_against_the_baseline_is_flagged` に反転。

固定したテスト: 上記の反転分、`test_committed_conftest_is_flagged_against_the_baseline`、`test_committed_pyproject_addopts_is_flagged_against_the_baseline`、`test_unresolvable_baseline_ref_is_a_finding`、`test_unset_baseline_ref_is_refused_by_validate`。

### M3 docker 不在時の素の例外 — 処置

事実: 指摘どおり。`FileNotFoundError` が捕捉されず、終了コード1（`verdict: fail` と同一）で traceback になった。

処置: ホスト側サブプロセスを `_host_run` に集約し、実行不能を理由文字列として返す。`verify_image_present` は precondition の finding として、`run` 本体の docker 起動失敗は `infra_error` の `ContainedResult` として返す。CLI 終了コードを verdict ごとに分離（0 pass / 1 fail / 2 refused / 3 infra_error）。

固定したテスト: `test_absent_docker_is_reported_not_raised`、`test_run_with_absent_docker_returns_infra_error`、`test_absent_docker_exit_code_is_not_the_failure_exit_code`、`test_cli_exit_codes_distinguish_every_verdict`。

### M4 opt-out のフロア欠如 — 処置

事実: 指摘どおり。`secret_paths=()` で deny-set が空になり、テスト既定 fixture が `secret_paths` を差し替えていたため実列挙は95件のどこからも行使されていなかった。

処置:

- `secret_paths` を `extra_secret_paths` に改名し、列挙の**追加**のみとした。空タプルを渡してもフロアは縮まない。
- `run(..., skip_static_check=True)` を削除。静的検査は常に走る。
- テスト既定 fixture は deny-set を差し替えるのをやめ、`secret_home` に tmp_path 配下の偽HOMEを与える。`default_secret_paths` の全名称が実際に列挙され、かつホスト依存にならない。

固定したテスト: `test_extra_secret_paths_cannot_shrink_the_deny_set`、`test_run_has_no_static_check_opt_out`、および fixture 変更により既存95件が実列挙を経由するようになった。

### minor

- **m1 ホスト側サブプロセスの env 継承 — 処置**: `host_subprocess_env()` に一本化し、`docker image inspect`・`git status`・`docker run` の3箇所を同一の env（`PATH` のみ）で起動。固定したテスト: `test_host_subprocess_env_drops_daemon_and_git_redirection`、`test_the_image_check_and_the_run_agree_on_the_environment`。
- **m2 マウント文字列の区切り未検証 — 処置**: `Mount.field_violations()` が `:`・`,`・改行・NUL を含む source/target を拒否。固定したテスト: `test_mount_path_containing_a_volume_separator_is_refused`。
- **m3 `uid`/`gid` の既定 `None` — 処置**: `validate` が未設定と 0 を拒否。README の「never root」が実装で成立する。固定したテスト: `test_root_or_unset_user_is_refused`、`test_agent_node_preset_sets_a_non_root_user_and_a_fixed_secret_home`。
- **m4 gitfile 拒否により実レーンの worktree では動かない — 据え置き**: 解消には gitdir の ro 追加マウント、すなわちマウント面を1点増やす設計変更が必要で、実装ではなく設計の判断。B1 の残余と同じくG2結線前の決着事項として残す。README の Known limitations に記載済み。

### 反証が成立しなかった主張について

`--network=none` の上書き不能、`docker build`/`pull` の副経路不在、`docker.sock`/`--privileged` 不在、ホスト環境の非継承、マウント元の realpath 化、docker 非経由の pytest 起動経路の不在は、いずれも本処置で変更していない。棄却した指摘は無い。

### 再実測が必要な項目

README の「Measurements, agent-node, 2026-08-29」は本処置前の走行記録。封じ込めの性質（egress 拒否・秘密不在・権限剥奪・worktree read-only）は本処置の変更対象外だが、判定パース・deny-set 基準・引数照合・静的検査は変わっているため、agent-node での (a)(b) 再実行と、追加した2件の拒否確認（`HOME` を変えた `--runtime-mount /home/user/.hermes/kanban.db`、`--pytest-arg=-opython_files=*.py`）が G2 結線前に必要。
