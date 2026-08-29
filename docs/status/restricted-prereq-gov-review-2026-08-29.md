# 統治面拡張・契約seed base commit 追加の反証レビュー（2026-08-29）

- Status: review complete / findings recorded（未コミット差分に対する反証記録）
- 対象: 未コミット差分（`operations/improvement/scope_seed.py`、`operations/improvement/install.py`、`integrations/hermes-pda-approvals/dashboard/plugin_api.py`、`integrations/hermes-scope-gate/scope_gate.py`、`integrations/hermes-scope-gate/schemas/scope-contract-v1.schema.json`、`operations/improvement/pda_improvement_cycle.py`、`integrations/hermes-scope-gate/tests/test_scope_seed_wiring.py`、`docs/operations/pda-improvement-cycle.md`、`operations/improvement/daily_reconciler_prompt.txt`）
- レンズ: (1) 列挙の全実装一致 (2) base commit の確定主体と既存seed互換 (3) 追加パスの前置一致の広狭 (4) テストによる固定
- 照合した一次資料: `docs/design/auto-integration-gate.md` 2節（追加面の正本）、`docs/design/task-scope-admission-gate.md`、`docs/roadmap/autonomous-improvement-goal.md`、および上記実装

## 件数

- blocker 0 件 / major 2 件 / minor 2 件（計 4 件）

## 確証できた事項（反証が通らなかった主張）

- **列挙は3実装で完全一致**。AST で `GOVERNANCE_PATHS` の代入を直接取り出して比較し、`scope_seed.py` / `install.py` / `plugin_api.py` の3本が **26 エントリ・同一順序で一致**。判定関数 `_is_governance_path` も3本で同一実装（`./` 剥がし → 名前が `conftest.py` なら真 → 末尾 `/` は前置一致、それ以外は完全一致）。第4の列挙（scope_gate 側の write 許可判定や plugin_runtime に独立の保護パス表）は存在しない。
- **追加10面は設計2節の指定と一致**。`docs/design/auto-integration-gate.md`（本設計）、M2設計 `docs/design/improvement-orchestrator.md`、M3設計 `docs/design/staged-verification.md`、`docs/operations/pda-improvement-cycle.md`、`docs/operations/worktree-lifecycle.md`、`schemas/`、`operations/backup/`、`src/pda/backup/`、`continuity/local-backup.json`、`docs/status/`。過不足なし。M2/M3設計のファイル同定は各ファイルの見出し（「(M2)」「(M3)」）と設計5行目の明示参照で確認した。設計2節が「実装フェーズでパス確定」とした4面（Tierマニフェスト・既知失敗リスト・G6パターン正本・回帰資産台帳）は未追加であり、これは設計どおり。
- **base commit は router 側で確定する**。値は `_assignment_base_commit`（`git merge-base <base_branch> <branch>` を primary repo で実行）が解決し、`_ensure_worktree` の戻り値として `_route_task` → `_record_scope_seed` → `record_seed` へ渡る。カード宣言のキー集合は `{write_paths, test_paths, execution, git_write}` の閉集合で `base_commit` は入らない（未知キーは `invalid-scope-declaration`）。worker の tool 面に `record_contract_seed` は露出しておらず（`plugin_runtime` はオーケストレータ dispatch 専用メソッドとして持つが、非テストの呼出は存在しない）、production の seed 記録経路は `scope_seed.record_seed` のみ。したがって worker 申告への依存は生じない。
- **既存seed互換は壊れていない**。`contract_seeds` は CREATE 時に `base_commit TEXT NOT NULL DEFAULT ''` を含み、既存ストアへは `PRAGMA table_info` 判定つき ALTER で追加。既存行は `''` のまま（推測backfillなし）。契約スキーマの `base_commit` は最上位の任意プロパティで `required` に入らず、`additionalProperties: false` の下でも既存契約は通る。検証は本物の `jsonschema` Draft202012 なので `pattern` は実効。自己宣言契約（`origin: self`）は base を持たないため契約へ書かれない。
- **test_paths も統治面判定の対象**。`write_paths` だけでなく `test_paths` を統治面へ向けた宣言も拒否されることを実測（`derive_seed_payload` は両者を合わせて `_reject_overbroad_scope` へ渡す）。宣言段のバイパスにはならない。
- **指定スイートは green を独立再現**。本開発PCには pytest / jsonschema が無かったため `$TMPDIR` に venv を作り（pytest, jsonschema, pyyaml）、`integrations/hermes-scope-gate/tests` で **648 passed / 1 failed** を再現。失敗1件は `test_hermes_integration.py::test_current_hermes_runtime_dispatches_plugin_and_shell_gate` で原因は `ModuleNotFoundError: No module named 'agent'`（Hermes ランタイム未インストール）であり、本差分とは無関係。

## 指摘

### G-01（major）router の fail-closed は入力側にしか掛かっておらず、記録結果は検証されない

`_route_task` は `base_commit` が空なら `CycleError("invalid-config")` を投げる（実装報告どおり）。しかし `_record_scope_seed` は `record_seed` の戻り値を破棄する。`record_contract_seed` の再記録判定 `_seed_payloads_agree` は「片側が空なら base を比較しない」という対称的許容を持ち、一致経路では**保存済みレコードをそのまま返す**（base を上書きしない）。したがって次が成立する。

- 既存ストアに base 無しの seed 行がある task を再ルーティングすると、router は base を解決して渡すが、記録される seed の `base_commit` は `''` のまま、`record_seed` は成功を返し、router は成功として扱う。
- この挙動は実装側のテスト `test_a_seed_written_before_the_base_field_existed_still_matches` で「意図」として固定されており（`again["base_commit"] == ""` を assert）、偶発ではない。

結果として「割当時 base が seed に記録されている」という保証は、**新規 task_id についてのみ**成立する。live gate store には M1 監督付き実運転（t_e2364a83）以降の既存 seed 行が存在するため、これは仮想的な状況ではない。設計2節が base を入れた目的（G1 のスコープ再照合・G3 のテスト浸食抽出の観測範囲を worker 申告の `base_sha` から切り離す）に対して、旧行を持つ task では範囲が「未記録」に退行し、それを検知する箇所が現時点で無い（base を要求する consumer は未実装であり、`_build_artifact_change_contract` は空なら単に契約へ書かない）。

処置案: `_record_scope_seed` で戻り値を受け、`base_commit` を渡したのに戻り値の `base_commit` が空または不一致なら割当を拒否する（記録結果に対する fail-closed）。旧行の扱いは「拒否してオーナーへ落とす」か「旧行を消してから再記録する」かの分岐があり、後者は seed が上限の正本である以上オーナー判断。

### G-02（major・オーナー判断事項）バックアップ面の回帰資産 `tests/backup/` が自動レーンに残る

設計2節は `operations/backup/`・`src/pda/backup/`・`continuity/local-backup.json` を統治面へ入れた（根拠: 憲章C3「バックアップは worker/core の書込権限外」、および systemd の ExecStart が checkout 内スクリプトへ実行到達する）。一方 `tests/backup/`（`test_local_snapshot.py`・`test_cli.py`・`test_install.py`・`test_managed_habit.py`）は列挙に無く、宣言段で受理されることを実測した（`write_paths` 経路・`test_paths` 経路のいずれでも受理）。

実装が Tier G で恒久的に自動統合不可である面について、その挙動を保証している唯一の資産が自動レーンで書き換え可能である。これは設計3節 A2（テスト浸食）が「実装者がテストへ書込可能な構造上、最も安価な偽装経路」と述べた形そのものであり、対象がバックアップ＝復旧手段であるため損害は他面より重い。ただし本差分は列挙をオーナー批准の閉集合としてテストで固定した（`test_the_governance_surfaces_are_the_ratified_closed_set`）ので、**列挙への追加はレビュアが行う変更ではない**。オーナー判断として提示する。

判断項目: `tests/backup/` を `GOVERNANCE_PATHS` へ加えるか、設計2節が予告した「回帰資産台帳」の側で保護するか。

### G-03（minor）branch 再作成後の再ルーティングは恒久に近い拒否になり、拒否理由がカード宣言のせいに見える

`_assignment_base_commit` は merge-base を使うため `base_branch` の前進では動かない。しかし worktree/branch が worktree-lifecycle の掃除で削除され、同一 task_id が再度 ready へ戻った場合、branch は現在の `base_branch` から再作成され merge-base は別の commit になる。このとき `_seed_payloads_agree` は両側 base 非空・不一致で False を返し、`ValueError("a different contract seed already exists for this task")` → `ScopeSeedError("scope-seed-rejected")` → カードへ「書込スコープ宣言をゲートが受理しませんでした」というコメントが付いて割当が拒否される。

- 宣言は一切変わっていないのに、拒否理由の文言はカード宣言の問題として読める。オーナーがカード本文を直しても解消しない。
- 解消は `purge_expired` が retention cutoff を超えた seed 行を削除するまで待つか、gate store を手で触るかになる（`purge_expired` は `contract_seeds` を cutoff で削除するため恒久ではない）。

処置案: base 不一致だけは専用の理由コードとメッセージに分け（宣言の不一致とは別物である旨をカードコメントへ書く）、旧 seed の失効をオーナー操作として明示する。

### G-04（minor・既存機序、拒否面が広がったことで到達先が増えた）中間セグメントにワイルドカードを置くと宣言段の文字列判定を抜ける

`_pattern_names_governance` は宣言パターンの**文字列**が統治面を前置一致するかを見る。統治ディレクトリ名の一部をワイルドカードに置いた綴りは前置一致せず、かつ未存在ファイルを狙えばツリー走査側の照合にも当たらないため、宣言段で受理される。実測で受理された綴りは本節に列挙する（`docs/status/`・`schemas/` を狙う形、および `docs/*/`・`operations/*/`・`src/pda/*/` 形）。具体形は次のとおり。

- `docs/sta*/new.md`、`docs/statu?/new.md`、`schema*/x.json`、`docs/*/new.md`、`operations/*/new.py`、`src/pda/*/new.py` は受理された。
- 対して `docs/status/x.md`、`./docs/status/x.md`、`schemas/x.json`、`operations/backup/**`、`src/pda/backup/x.py`、`continuity/local-backup.json`、`docs/design/auto-integration-gate.md`、`docs/operations/worktree-lifecycle.md` は拒否された（前置一致・完全一致が効く綴り）。

この機序は本差分が作ったものではなく、既存の統治ディレクトリ（`docs/design/` 配下のファイル群、`integrations/hermes-*/`、`operations/improvement/`）に対しても同じ形で成立していた。本差分で新たに `docs/status/`・`schemas/` が到達先に加わった。

統治breachには至らない: 承認段（`install.py` / `plugin_api.py`）は `changed_files` に対して同じ `_is_governance_path` を適用するため、この綴りで作った `docs/status/...` の新規ファイルは finalization で拒否される。コストは「完走できない作業への起動」であり、これは `_pattern_names_governance` 自身の docstring が防ぎたいと述べたものと同じ損失である。

処置案（採るなら）: 宣言パターンの各セグメントにワイルドカードを含む場合、そのセグメントを統治面の対応セグメントと照合して交差可能性を見る（綴りの列挙ではなく、パターンとして交差するかの判定）。優先度は低い。

## テストによる固定状況（レンズ4）

- 固定されている: 列挙の閉集合（26エントリのリテラル）／`scope_seed` と `install.py` の相互一致（AST 読み取りによる比較）／ディレクトリ表記は末尾スラッシュ必須（かつ非スラッシュ項目が実在ファイルであること）／新統治面10面の宣言段拒否（未存在ファイルを狙う綴りを含む）／base の記録・カードからの申告不可・不正値（ref・短縮prefix）拒否・欠如互換・両側非空の不一致拒否／router 経由の受け渡しと base 未指定時の割当拒否／`base_branch` 前進で base が動かないこと。
- 固定されていない: **`plugin_api.py` の列挙一致を確かめるテスト（`operations/improvement/tests/test_install.py:150`）は本開発PCで収集不能**。`hermes_cli` が無いため（fastapi・httpx を入れても解消しない）、実装報告の「収集不能」は事実として確認した。実装報告の「相互一致テスト2件green」は、green を確認できたのが `scope_seed`↔`install` の一致テストと閉集合テストの2件であり、`plugin_api` 側の一致テストは含まれない。一致という**事実**は本レビューの AST 直接比較で確認済みだが、ピン留めテストの green は agent-node 側で確認する必要がある。
- 固定されていない: G-01（記録結果の検証）、G-02（`tests/backup/`）、G-04（ワイルドカード綴り）に対応するテストは無い。G-03 は「不一致は拒否」として固定されているが、拒否理由の識別性は固定されていない。

## 検証環境

- 反証実行は本開発PC（macOS、`.claude/worktrees/m1-resume-classifier-fix-da21a3`）。pytest / jsonschema が未導入だったため `$TMPDIR` に一時 venv を作成して実行した（リポジトリ内へは何も置いていない）。
- 宣言段の受理/拒否の実測は `scope_seed.derive_seed_payload` を実リポジトリのツリーに対して直接呼び出して行った。gate store への書き込みは行っていない。

## 処置記録（2026-08-29）

修正3件 / 棄却0件 / オーナー判断へ差し戻し1件。棄却（誤検知）は無し。

### G-01（修正）記録結果に対する fail-closed

base の比較を非対称にした。`GateStore._seed_payloads_agree` を `_reject_disagreeing_seed` へ置き換え、base を申告した側と記録行が食い違う場合（記録行が空の場合を含む）は新しい例外 `ContractSeedBaseConflict`（`ValueError` の派生）を投げる。base を申告しない呼出は従来どおり許容し、記録済みの値をそのまま残す（申告のない呼出は base について何も主張していないため、記録行を否認できる側ではない）。

これにより「割当時 base が seed に記録されている」保証は新規 task_id 限定ではなくなった。記録行の書き換えは行わない（旧行の削除・backfill はオーナー判断のため実施していない）。

運転上の影響: base 未記録の既存 seed 行を持つ task が再ルーティングされると、従来は成功扱いだった経路が拒否になる。解消は既存 seed の失効（retention 経過による `purge_expired`、またはオーナーによる削除）を要する。

### G-03（修正）拒否理由の分離

base 不一致は宣言不一致と別の理由コードにした。`record_seed` は `ContractSeedBaseConflict` を `scope-seed-base-mismatch` として送出し（宣言不一致は従来の `scope-seed-rejected` のまま）、`_refuse_for_scope` に専用のカードコメントを追加した。コメントは「宣言には問題がない」「カード本文を直しても解消しない」「既存seedの失効が必要」を明示する。

### G-04（修正）宣言段の判定をパターン交差へ

`scope_seed._pattern_names_governance` に、統治ディレクトリをセグメント単位で照合する判定（`_pattern_reaches_below`）を追加した。`fnmatch` でセグメントごとに照合し、`**` は複数セグメントを消費する。ディレクトリ自体を指すだけの綴りは対象外（配下を覆っていないため、`_is_governance_path` と同じ線）。単一ファイル項目は文字列比較のまま（いずれも実在ファイルであり、ワイルドカード綴りはツリー走査側で捕まる）。

変更は `scope_seed.py` のみ。`_is_governance_path` と3実装の列挙は触っていないため相互一致テストは維持される。

本PCのリポジトリに対し、レビュー G-04 節が受理と記録した6綴りすべてが拒否に変わり、拒否と記録した8綴りは拒否のまま、`integrations/openwebui-hermes-progress/*.py`・`src/*.py`・`src/pda/*.py`・`docs/*.md` 等の通常形は受理のままであることを確認した。

残る同種の抜け穴: 最終セグメントがワイルドカードのとき、まだ存在しない `conftest.py` を狙う綴り（`integrations/x/*.py` 等）は宣言段では捕まらない。`*.py` は `conftest.py` に一致するため、この判定を入れると運用文書が例示している通常形まで拒否される。承認段が同一判定で拒否するため統治breachには至らず、現状は据え置いた。

### G-02（オーナー判断へ差し戻し）

`tests/backup/` は `GOVERNANCE_PATHS` へ追加していない。列挙はオーナー批准の閉集合としてテストで固定されており、追加は統治面の変更そのものであるため、レビュア側でも実装側でも決められない。判断項目はレビュー本文のとおり（列挙へ加えるか、回帰資産台帳の側で保護するか）。

なお本処置で追加したテストには、`tests/backup/` 配下を受理する挙動を固定するケースは入れていない（オーナー判断を先取りしないため）。

### テストによる固定

追加したテスト（`integrations/hermes-scope-gate/tests/test_scope_seed_wiring.py`）:

- base 未記録の既存行に対する記録は拒否され、記録行に副作用がないこと（G-01）
- base を申告しない呼出は記録済みの base を残すこと（非対称許容の許容側）
- base 不一致のカードコメントが宣言の不備として読めないこと（G-03）
- G-04 節の6綴りと再帰形2綴りが拒否されること／通常形6綴りが受理されること

書き換えたテスト:

- `test_a_seed_written_before_the_base_field_existed_still_matches` は G-01 の欠陥を意図として固定していたため、拒否を固定するテストへ置き換えた（名称も変更）。
- `test_two_different_bases_for_one_task_are_refused` の期待 kind を `scope-seed-base-mismatch` へ更新した。
- 広さ測定の3テスト（`test_an_anchored_pattern_of_any_depth_is_still_accepted`・`test_the_measured_breadth_is_the_union_of_both_declared_fields`・`test_the_limit_is_configurable_without_changing_the_measurement`）は、合成ツリー上の便宜的な広いパターンとして `src/**`・`docs/**` を使っていた。これらは実リポジトリの統治ディレクトリ（`src/pda/backup/`・`docs/status/` 等）へ到達するため G-04 の判定で拒否される。各テストの主題は広さ計数であって統治面判定ではないので、統治面を含まない top-level（`assets/`・`tests/`・`README.md`・`Makefile`）へ綴り替えた。

### テスト結果

- `integrations/hermes-scope-gate/tests`: 664 passed / 1 failed。失敗はレビュー時と同一の `test_hermes_integration.py::test_current_hermes_runtime_dispatches_plugin_and_shell_gate`（`ModuleNotFoundError: No module named 'agent'`、Hermes ランタイム未導入）であり、本差分とは無関係。
- `operations/improvement/tests/test_c6_audit.py`: 4 passed。
- 本PCで収集不能（`hermes_cli` 不在）: `operations/improvement/tests/test_install.py`（`plugin_api.py` の列挙一致テストを含む）、`operations/improvement/tests/test_pda_improvement_cycle.py`、`operations/improvement/tests/test_kanban_isolation.py`、`integrations/hermes-pda-approvals/tests/test_plugin_api.py`。レビューが挙げた未確認項目はそのまま残る（列挙一致という事実はレビューの AST 直接比較で確認済み、ピン留めテストの green は agent-node 側で要確認）。
- `tests/backup`: `PYTHONPATH=src` で収集できるが 41 failed。原因は macOS 同梱 rsync 2.6.9 が `--acls` を持たないことであり、本差分とは無関係（`src/pda/backup/` は本差分で変更していない）。

### 検証環境

`$TMPDIR` の一時 venv（pytest, jsonschema, pyyaml, fastapi, httpx）。リポジトリ内へ一時ファイルは置いていない。
