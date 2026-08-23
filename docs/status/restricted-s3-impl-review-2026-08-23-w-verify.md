# S3-M1 worker 配線修正の独立検証（2026-08-23、`312b1f4`）

- 対象コミット: `312b1f4`（基準点 `f7cfe0f`、19 ファイル）。
- 検証対象: 処置台帳 14 節が主張する修正 12 件（W-B-01〜06 のうち 07 を除く 6 件、W-C-01〜06）と、W-B-07 の誤検知棄却。
- 再現環境: `./tmp/verify-w/`（`harness.py` / `stubs.py` / `kanban_stub.py` / `p1`〜`p12`）。実行は `./tmp/venv-scope/bin/python`。合成リポジトリは `os.path.realpath(tempfile.gettempdir())` 配下に作成し、リポジトリ本体・`continuity/autonomous-improvement.json`・実機状態には触れていない。
- **本書は取扱制限。迂回手法の具体形を含む。** 親セッションへの戻り値には ID と抽象名のみを返す。

修正者の自己申告は根拠にしていない。各フェンスは負の対照（当該検査のみを無効化した同一コードパス）を取り、有効時の拒否がその検査に帰属することを確認した。

---

## 1. 反転を実測で確認した修正

| 欠陥 | 実測 | 負の対照 |
| --- | --- | --- |
| W-B-02 書込側 carve-out | `write_paths=['**']` 下で `.git` / `.git/config` / `.git/hooks/pre-commit` / `sub/.git/config` が `write-git-metadata` で拒否。狭い宣言下でも同一コード。書込カタログ 12 tool 全件（対フィールドの source 側・destination 側、listed、nested を分けて 1 turn ずつ）で拒否 | `artifact_path_is_git_metadata` を恒偽化すると `write-in-scope-change` で admit |
| W-B-02 ステージ側 carve-out | `git add .git/config` / `./.git/config` / `.git` / `.git/hooks/pre-commit` が `stage-git-metadata` で拒否。`git add src/app.py` は admit | 恒偽化すると `stage-in-scope-change` で admit |
| W-B-02 解決先の封じ込め（第一層） | ロック済み root 内へ向け替えた構成で `git add` / `git commit` が `git-discovery-redirected` で拒否 | `_artifact_git_discovery_verdict` を恒 None 化すると両者 admit |
| W-B-02 封じ込め（承認ゲート） | 向け替え済み workspace で `verify_workspace` が該当エラーを立て `identities` を `None` のまま返す（台帳へ値を渡さない） | `_resolves_inside` を恒偽化すると decoy 側の値で `identities` が埋まる |
| W-B-02 封じ込め（消費側） | `_verify_approved_artifact` が向け替え構成を該当 `ValueError` で拒否 | 当該 `raise` を除去したコピーでは同エラーが出ず後段の検査へ進む |
| W-B-01 ルータ側の上限 | `**` / `**/*` / `*` / `*/x` / `*/**` / `' ** '` / `'**/'` / `['src/**','**']` を `invalid-scope-declaration` で拒否。`run_cycle` 経由でも `**` 宣言カードが `refused` になる | ― |
| W-B-03 強制スイッチ | `_route_task` の `scope_seed_enabled` は既定値なし。省略は `TypeError`（keyword-only 必須） | ― |
| W-B-04 宣言ブロックの不活性領域 | 4 スペースインデント / 外側 4 バッククォート / 外側チルダ / ``` ```text ``` / ``` ````md ``` / 引用 / タブインデントのいずれも live にならない。実宣言は plain・3 スペース・チルダ・4 バッククォートいずれの綴りでも live。実宣言＋図解併記は 1 ブロックとして曖昧拒否されない。実宣言 2 件は依然拒否 | ― |
| W-B-06 / W-C-02 割当 queue の停止 | 宣言なし高優先度カードの後続が割当される（`assigned: ['t_good']`、`refused: [{'t_bad','missing-scope-declaration'}]`、`ok: true`）。拒否カードにコメント 1 件、worktree 非作成 | ― |
| W-C-06 一部割当後の失敗報告 | `per_tick=2` で先行割当が `assigned` に残る | ― |
| W-C-01 fixture 不足 | `_repo()` が `scope_gate.py` / `schemas/` / `scope_seed.py` を本リポジトリから複製（スタブでない）。同形 fixture を組んだ等価再現で `run_cycle` が seed 記録まで到達し `assigned` に載ることを確認 | ― |
| W-C-05 クラス既定の二重定義 | `test_the_class_default_matches_the_gate_that_enforces_it` が存在し green | ― |
| W-C-03 / W-B-05 / W-C-04 文書対応 | 手順書の例が受理形（`test_the_documented_declaration_example_is_the_accepted_form` green）。承認スキーマ移行の記載を確認 | ― |

false deny の非導入も確認した。`.gitignore` / `.gitattributes` / `.github/workflows/ci.yml` / `docs/.gitkeep` / `src/.gitignore` / `vendor/x.git/y` / `a/.gitmodules` / `tools/git/helper.py` / `git/config` はいずれも書込・ステージとも admit される。linked worktree（本番形）と通常リポジトリの双方で封じ込め検査は追加拒否を出さない。

## 2. W-B-07 の誤検知棄却は妥当

`install_scope_gate` を実行して実測した。plugin ディレクトリは symlink として設置され（`symlink_to(source_path, target_is_directory=True)` → `os.replace`）、`--source` の既定は install.py 自身のディレクトリである。強制側が読む `scope_gate.py` とルータが `repo_root` 経由で読む `scope_gate.py` は同一 inode に解決した。「別コピー」「版ずれ」という前提は成立しない。残る「cycle 設定の `repo_root` が別チェックアウトを指す場合」は台帳の記述どおり W-B-07 の主張内容ではない。

## 3. admission の非拡大と closeout 共有実装の不変

`scope_gate.py` の差分は 98 行の純増（削除 0）。AST 比較の結果:

- 追加関数: `artifact_path_is_git_metadata`、`_artifact_git_discovery_verdict`
- 変更関数: `_admit_artifact_change_git`、`_admit_artifact_change_locked`、`_artifact_stage_targets`（いずれも artifact-change クラス局所）
- closeout 名を含む関数の変更: 0 件。artifact 名を含まない関数の変更: 0 件
- モジュール定数の変更: `ARTIFACT_DEVIATION_DENY_ACTIONS` のみ（計上集合の拡大）

共有のパス正規化・pathspec 実装（`normalize_repo_relative_path` / `normalize_scope_pattern(s)` / `scope_patterns_match` / `_entity_resolved`）はいずれも無変更で、D-S3-7 決定 1 は守られている。3 箇所の変更はすべて拒否の追加であり admit 分岐を増やしていない。carve-out 対象パスの悪用による新たな迂回面は、carve-out が拒否のみを行うことから構造的に生じない（実測でも `.git` 系は全 tool で拒否側）。

## 4. litmus 判定: `git-discovery-*` の計上は litmus に適合する

計上集合の litmus は「admission が自ら行った確定判定が発行した理由コードのみ計上し、純粋な読み取りが到達しうるコードは計上しない」である（`scope_gate.py` 2840-2884 の明文）。

`_artifact_git_discovery_verdict` の呼び出し箇所は 1 箇所（3496 行、`_admit_artifact_change_git` 内）で、read 系 subcommand 分岐・`ARTIFACT_GIT_READ_UNADMITTED` 分岐・`{add, commit}` 判定・`git_write` 権限判定・branch drift 判定のすべてより後にある。`rev-parse --git-dir` / `--git-common-dir` のみを失敗させ（seed 検証は健全なまま）実測した結果:

- `git status` / `git diff` / `git rev-parse HEAD` / `git branch --show-current` は各自の read 判定で admit、`git log` / `git ls-files` は `git-read-unadmitted`、`git cat-file` は `git-subcommand`。**いずれも `git-discovery-unverified` に到達しない。**
- `read_file` は `inspect-locked-target` で admit、構造化書込 tool は `write-in-scope-change` で admit（この経路にも到達しない）。
- 到達するのは `git add` / `git commit` のみ。`git_write` を持たない契約では `git-write-forbidden` が先に返る。
- `write-git-metadata` は書込カタログの tool 同一性から、`stage-git-metadata` は `git add` からのみ到達する。

したがって 4 件の新規コードはいずれも計上対象として litmus に適合する。`git-discovery-unverified` は環境起因で発火し得るが、これは既に批准済みで計上対象の `target-drift`（`_validated_worktree_branches` の失敗経路）と同一の性質であり、扱いの一致は内部整合的である。計上集合の正本列挙テスト（26 件）は実装と一致し green。

## 5. 確証した新規欠陥

### WV-01（case-insensitive ファイルシステムでは blocker、Ubuntu の gateway では不成立）メタデータ carve-out がセグメント綴りの完全一致のみで判定し、正規化を経ていない

`artifact_path_is_git_metadata` はロック済み root への相対パスを `/` 分割し、各セグメントを文字列 `.git` と `==` で比較する。ファイルシステムの名前照合規則を経ていないため、同一実体を指す別綴りが carve-out を通過する。

実測（macOS / APFS、`./tmp/verify-w/p1b_carveout2.py`、`p1g_casefold.py`）:

```
  '.git'     same-inode-as-.git=True   normalized_rel='.git/config'   carve_out_flags=True
  '.Git'     same-inode-as-.git=True   normalized_rel='.Git/config'   carve_out_flags=False
  '.GIT'     same-inode-as-.git=True   normalized_rel='.GIT/config'   carve_out_flags=False
  '.gIt'     same-inode-as-.git=True   normalized_rel='.gIt/config'   carve_out_flags=False
  wrote to <root>/.Git ; real <root>/.git content changed: True
```

`normalize_repo_relative_path` は `_entity_resolved`（`realpath`）を通すが、`realpath` は名前の case を正規化しないため、返る相対パスは宣言された綴りのままである。末尾ドット・末尾空白・8.3 短縮名の各変種は当該 FS 上で別実体（`stat` 失敗）であり、成立するのは case 変種のみである。

**フェンス 2 も止められない。** ロック済み root は seed 検査で linked worktree の top level に固定されるが、`_artifact_git_discovery_verdict` は「root 配下に入らないこと」を検査し、`resolved == realpath(root/'.git')` を通常リポジトリ形として名指しで許容する。case 変種で `<root>/.git` 自身を作り直すと、この許容分岐に一致する。

end-to-end 実測（`./tmp/verify-w/p3b_purewrite.py`、ゲートが admit した呼び出しだけを使用。`git init` 等の非 admit コマンドは使っていない）:

```
  delete_file <root>/.Git -> allowed=True action=write-in-scope-change
  write_file <root>/.Git/HEAD                  allowed=True action=write-in-scope-change
  write_file <root>/.Git/config                allowed=True action=write-in-scope-change
  write_file <root>/.Git/objects/info/keep     allowed=True action=write-in-scope-change
  write_file <root>/.Git/refs/heads/keep       allowed=True action=write-in-scope-change
  write_file <root>/.Git/hooks/pre-commit      allowed=True action=write-in-scope-change

  <root>/.git is a dir
  rev-parse --git-dir         : .git
  rev-parse --show-toplevel   : <root>
  branch --show-current       : 'pda-auto/t1'

  verdict fn: None
  git add src/app.py       allowed=True action=stage-in-scope-change
  git commit -m x          allowed=True action=commit-in-scope-change
  commit rc: 0 | HOOK EXECUTED: True HOOK-RAN
```

すなわち W-B-02 が記した破れ 5 点（第二層の既定閉鎖、契約の禁止項、第一層の書込上限、`--no-verify` 拒否によりフック実行が強制であること、README の探索前提）は、この FS 上では修正後も同じ形で成立する。`delete_file` が実体の pointer file を消すため、可用性・承認ゲートの同一性導出の破壊も同時に起こる（後者は fail closed）。

**プラットフォーム条件。** gateway は Ubuntu Server 24.04（GMKtec M8）であり、ext4 は case-sensitive なので `<root>/.Git` は別ディレクトリとなり Git は読まない。したがって**本番形では現時点で live な迂回ではない**。問題は次の 3 点である。

1. `scope_gate.py` の当該コメントは「which no contract admits」と無条件の性質を主張しており、実際には FS の名前照合規則に依存する。
2. 開発 PC（macOS / APFS）は同じゲートで同じスイートを実行する環境であり、`artifact-change` の実行環境が Linux に限られることを固定する検査は無い。
3. 新設テストに case 変種の事例は無い（`grep '\.Git\|\.GIT\|casefold\|lower()'` で該当なし）。

**処置の方向（判断が必要）。** (a) セグメント比較を case-fold 比較へ改める（1 行）。(b) フェンス 2 の通常リポジトリ許容を、契約が固定するクラス形（linked worktree、すなわち git-dir ≠ git-common-dir）でのみ通す形へ狭める。(b) は綴り問題と独立に本連鎖を閉じるため、2 系統独立の設計意図に合う。(a) と (b) は排他でない。

### WV-02（major）宣言由来上限に対する「機械的上限」が綴りの列挙であり、全域相当の上限が依然表現可能

`_reject_unanchored_patterns` は先頭セグメントを `{"*", "**"}` の 2 綴りと照合する。パターン文字集合は `^[A-Za-z0-9._*?/\[\]-]+$` であり `?` と文字クラスを許すため、同じ幅を別の綴りで書ける。

実測（`./tmp/verify-w/p4_anchor.py`）:

```
  ['?*']                     -> ACCEPTED
  ['?*/**']                  -> ACCEPTED
  ['?*', '?*/**']            -> ACCEPTED
  ['?**']                    -> ACCEPTED
  ['*?']                     -> ACCEPTED
  ['*?/**']                  -> ACCEPTED
  ['[a-zA-Z0-9._-]*/**']     -> ACCEPTED
  ['??*/**']                 -> ACCEPTED
```

`_segment_matches` は `fnmatch.fnmatchcase` なので `?*` は 1 文字以上の任意の名前に一致する。ロック済み契約での書込 admit を実測すると:

```
    src/app.py                                   allowed=True action=write-in-scope-change
    continuity/autonomous-improvement.json       allowed=True action=write-in-scope-change
    anything/deep/new.txt                        allowed=True action=write-in-scope-change
    toplevel.txt                                 allowed=True action=write-in-scope-change
    operations/improvement/scope_seed.py         allowed=True action=write-in-scope-change
    .git/config                                  allowed=False action=write-git-metadata
```

`run_cycle` 経由でも当該宣言のカードは拒否されず割当される（`assigned: ['t_qs']`、`refused: []`）。`test_paths` 側も同様（`['?*/**']` は ACCEPTED）。

なお `scope_gate.py` に governance パスの carve-out は無い（`grep 'GOVERNANCE\|governance'` で該当なし）。`GOVERNANCE_PATHS` の照合は `install.py` の承認契約検証（`changed_files`）にのみ存在するので、上表の `operations/improvement/scope_seed.py` は「第一層が書込を admit する」という意味であり、最終化まで通るという意味ではない。第一層の上限が主張する性質が成立していないという点が本欠陥である。

したがって W-B-01 の確証部分（「上限に機械的な上限が無い」）は反転していない。`.git` carve-out 以外の全域が依然として宣言 1 行で到達可能であり、幅を決めるのは AI が書いたカード本文である、という状態は変わっていない。設計 §3.2 が tenant 既定値を退けた理由（「既定で広い集合を配ると seed 経路の意味が失われる」）に対する機械的な裏付けは、現状では成立していない。

新設テストの拒否パラメタは `["**", "**/*", "*", "*/**", "*/src/*.py", " ** ", "**/*.py"]` の 7 綴りの列挙であり、当該テストの docstring 自身が満たすと述べる性質（「a card body is written by a model, so without a mechanical limit the same breadth is reachable through the declaration」）を満たしていない。なお `scope_gate.py` の `artifact_deny_counter` docstring は同種の失敗形について「an open argument space cannot be closed by enumerating spellings」と既に記録しており、本件は同じ形の反復である。

**処置の方向（判断が必要）。** 綴りの追加ではなく性質での判定が必要である。先頭セグメントが「ワイルドカード metacharacter を除いた literal 部分を持たない」ことを条件にする（`*` `**` `?*` `*?` `?**` `[...]*` を一括で捕らえ、`src*` `*.py` は通す）か、あるいは幅を宣言の字面ではなく「先頭セグメントが literal であること」で要求する形が候補である。いずれもルータ側に置ける（共有実装に触れない）。

### WV-03（minor）周期戻り値 `ok` の意味論変更が処置台帳の批准項目より広い

台帳 14 節 14 項 1 は「宣言不備のみのときに `ok` が false から true へ変わる」と記す。実測では per-card 回復は割当ループ内の**すべての** `CycleError` を捕らえるため、宣言と無関係な拒否でも `ok: true` になる（`./tmp/verify-w/p12_okbreadth.py`）。

```
  seed flag ON   ok: True | assigned: ['t_b'] | refused: [{'t_a','workspace-collision'}] | reason: assigned
  seed flag OFF  ok: True | assigned: ['t_b'] | refused: [{'t_a','workspace-collision'}] | reason: assigned
  基準点 f7cfe0f ok: False | assigned: [] | error_kind: workspace-collision
```

`workspace-collision` / `dirty-worktree` / `claim-race` が該当する。とくに `scope_seed.enabled: false`（M1 exit 時点の live 構成）でも変わるため、批准対象は「seed 経路の宣言不備」ではなく「割当ループの失敗報告全体」である。`refused` には出るので不可視ではないが、周期の `ok` を見る監視から見える形は変わる。批准項目の記述をこの範囲へ改めるべきである。

### WV-04（minor）「割当されないカードに worktree を残さない」はゲート段の拒否では成立しない

`_check_scope_declaration` は `derive_seed_payload` のみを走らせるため、宣言が構文上妥当でゲートが拒否する形（未登録の実行テンプレート等）は事前検査を通過し、`_ensure_worktree` の後に `_record_scope_seed` で拒否される。実測:

```
=== 宣言は解析できるがゲートが拒否する形 ===
   ok: True | assigned: ['t_good'] | refused: [{'task_id': 't_gate', 'error_kind': 'scope-seed-rejected'}]
   worktrees on disk: ['t_gate', 't_good']
```

台帳 14 節 5 の「割当されないカードに branch と worktree を残さない」は宣言解析段の拒否に限られる。queue 停止の解消自体には影響しないので minor とする。

## 6. 回帰

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **576 passed**。台帳の申告値と一致。
- 新設テストのうち本ラウンドで名指しで確認した 41 件（carve-out / discovery / whole-tree / anchored / inert / worked-example / two-live / documented-declaration / class-default / installer-deploys / counting-set / test-assets）はすべて green。
- closeout 側の回帰は AST 上で発生し得ない（3 節）。`test_closeout_guards.py` も green。
- `operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` は開発 PC で実行不能（`hermes_cli` / `fastapi` 不在）。本書では最小スタブ（`./tmp/verify-w/stubs.py`、`kanban_stub.py`）で当該モジュールを実際に読み込み、`run_cycle` / `verify_workspace` / `_verify_approved_artifact` を本物のコードで駆動した。ミニPC でのスイート実行は親セッションが行う。

## 7. 再現手順

```
cd /Users/fox4foofighter/dev/pda/.claude/worktrees/m1-resume-classifier-fix-da21a3
./tmp/venv-scope/bin/python ./tmp/verify-w/p1b_carveout2.py   # 書込・ステージ carve-out と負の対照、綴り変種
./tmp/venv-scope/bin/python ./tmp/verify-w/p1g_casefold.py    # WV-01 の実体同一性
./tmp/venv-scope/bin/python ./tmp/verify-w/p2b_discovery.py   # 封じ込めと負の対照、false deny 非導入
./tmp/venv-scope/bin/python ./tmp/verify-w/p3b_purewrite.py   # WV-01 end-to-end（admit された呼び出しのみ）
./tmp/venv-scope/bin/python ./tmp/verify-w/p4_anchor.py       # WV-02
./tmp/venv-scope/bin/python ./tmp/verify-w/p5_fence.py        # W-B-04
./tmp/venv-scope/bin/python ./tmp/verify-w/p6b_litmus.py      # litmus 判定
./tmp/venv-scope/bin/python ./tmp/verify-w/p7_approval.py     # 承認ゲート側封じ込め
./tmp/venv-scope/bin/python ./tmp/verify-w/p8b_consume.py     # 消費側封じ込め
./tmp/venv-scope/bin/python ./tmp/verify-w/p9_installer.py    # W-B-07 の前提
./tmp/venv-scope/bin/python ./tmp/verify-w/p10_router.py      # 割当ループ（W-B-06 / W-C-02 / W-C-06 / W-B-03）
./tmp/venv-scope/bin/python ./tmp/verify-w/p11_falsedeny.py   # Git 近傍パスの false deny 非導入
./tmp/venv-scope/bin/python ./tmp/verify-w/p12_okbreadth.py   # WV-03
```

`./tmp/` 配下と OS 一時ディレクトリのみを使用。`continuity/autonomous-improvement.json` および実機状態には触れていない。

---

# WV 処置の焦点再検証（2026-08-23、`a91a2a7`）

- 対象コミット: `a91a2a7`（基準点 `312b1f4`、13 ファイル）。範囲は本差分に限定。
- 検証対象: WV-01〜04 の反転、実効照合が持ち込む非決定性・false deny、admission / closeout / 計上集合の不変、全ローカルテスト。
- 再現環境: `./tmp/verify-wv2/`（`q1_ast.py`〜`q8_router.py`）。`./tmp/verify-w/` の harness / stub を再利用。実行は `./tmp/venv-scope/bin/python`。合成リポジトリは OS 一時ディレクトリ配下。`continuity/autonomous-improvement.json` および実機状態には触れていない。
- **本書は取扱制限。迂回手法の具体形を含む。** 親セッションへの戻り値には ID と抽象名のみを返す。

修正者の自己申告は根拠にしていない。フェンスごとに負の対照（当該機構のみを無効化した同一コードパス）を取り、拒否がその機構に帰属することを確認した。

## 8. 反転を実測で確認した 4 件

| 欠陥 | 実測 | 負の対照 |
| --- | --- | --- |
| WV-01 | `.Git` / `.GIT` / `.gIt` が書込カタログ 9 tool 全件で `write-git-metadata`、ステージ 4 綴りで `stage-git-metadata`。`src/app.py` は admit のまま。carve-out 述語を直接呼ぶと 3 変種すべて `True` | 実体同一性の段のみを処置前の本体（綴り照合のみ）へ戻すと、case 変種が `write-in-scope-change` / `stage-in-scope-change` で admit へ戻る。字面 `.git` は対照下でも拒否のまま |
| WV-01 連鎖 | §5 の end-to-end 連鎖は**1 手目**（別綴りでの pointer file 削除）で `write-git-metadata`。2〜4 手目も同様に拒否。連鎖後も pointer file は `gitdir:` のまま無変化。`git add` / `git commit` は admit のまま（通常作業を狭めていない） | ― |
| WV-02 | §5 が ACCEPTED と記録した 8 綴りすべてと追加 2 綴り（`?[a-z]*/**`・`*[!x]/**`）が `invalid-scope-declaration`。プライマリリポジトリのツリーに対しても同一。ルータ経由でも当該カードが `refused` へ移り worktree を残さず、後続カードは割当される | 実効幅測定を no-op 化すると当該綴り族が受理へ戻る |
| WV-02 統治面 | `operations/improvement/*.py`・`integrations/hermes-scope-gate/**`・`conftest.py`・`docs/design/task-scope-admission-gate.md`・`continuity/*.json` が拒否。3 実装（`scope_seed.py` / `operations/improvement/install.py` / `plugin_api.py`）の `GOVERNANCE_PATHS` は 16 件で**タプル一致**、突き合わせテストは実在し green | ― |
| WV-03 | `workspace-collision` で `ok: true`（seed flag ON / OFF 双方）。運用手順・設計本文・台帳の記述がこの範囲へ改まっている | ― |
| WV-04 | 拒否段の分岐を実測。宣言なし・幅超過・統治面の 3 段は worktree を残さない。未登録実行テンプレート（宣言は解析可・ゲートが拒否）は `scope-seed-rejected` で worktree を**残す**。縮小後の記述と一致 | ― |

false deny の非導入も確認した。`.gitignore` / `.gitattributes` / `.github/workflows/ci.yml` / `docs/.gitkeep` / `src/.gitignore` / `vendor/x.git/y` / `a/.gitmodules` / `tools/git/helper.py` / `git/config` / `gitlab/ci.yml` / `.gitkeep` は書込・ステージとも admit。字面照合段は空セグメント除去の追加後も処置前と論理同値（13 入力で差分なし）。宣言側は運用手順の新例（`src/pda/backup/*.py` ＋ `tests/backup/test_local_snapshot.py`）・`src/**`・`src/**`＋`tests/**`・`docs/status/*.md`・同一最上位内の複数ディレクトリがいずれも受理。

上限の設定経路も実測した。`scope_seed.max_top_level_entries` はルータへ届き境界で効く（4 件被覆に対し 3 で拒否・4 で受理）。非整数・0 以下は `invalid-config` で `ok: false`（割当ループ外の失敗として従来どおり）。測定不能（ツリー不在・ディレクトリでない）は `scope-breadth-unmeasured` で fail closed。ツリー内の symlink は追跡しない。

## 9. 非決定性・冪等性

payload は測定に依存しない。同一 body を内容の異なる 3 ツリー（合成 2 種＋本リポジトリ）へ通しても payload はバイト同一。宣言範囲内へのファイル追加、宣言範囲外の最上位エントリ新設のいずれの後でも同一。測定量が「被覆する最上位エントリ数」であるため、深さ方向の書込では増えない。割当前検査（プライマリリポジトリ）と seed 記録（worktree）の payload も同一で、前者は未追跡最上位を多く含むため測定値は後者以上、すなわち近似は拒否側にのみ振れる。

台帳 15 節 2 の「測定が worker の書込後のツリーを見ることはない」根拠を確認した。`_eligible_tasks` は `status == ready` かつ `assignee is None` に限り、`_ensure_worktree` は `_record_scope_seed` より前に `git status --porcelain` の clean を要求する（dirty なら `dirty-worktree`）。

## 10. 不変の確認

`scope_gate.py` の AST 比較（docstring 除去後）:

- 追加・削除関数: 0 件。変更関数 3 件（`artifact_path_is_git_metadata`、`_artifact_stage_targets`、`_admit_artifact_change_locked`）はすべて artifact-change クラス局所。
- closeout 名を含む関数の変更: 0 件。artifact 名を含まない関数の変更: 0 件。モジュール定数の変更・追加・削除: 0 件。
- 理由コード集合（`GateDecision(False, …)` / `PathRejected(…)`）は 72 件で処置前と一致（増減 0）。`ARTIFACT_DEVIATION_DENY_ACTIONS` は 26 件でタプル一致。計上集合・litmus は無改訂。
- `GateDecision(True` 28 件 / `GateDecision(False` 80 件がいずれも処置前後で同数。新規 admit 分岐は無い。WV-01 は既存の拒否分岐の到達範囲を広げる変更のみ。
- 新規理由種別 `scope-breadth-unmeasured` はルータ側（`scope_seed.py`）にのみ存在し、ゲートには 0 件。計上集合の要素ではない。
- ルータ側差分に closeout の言及は 0 件。`derive_seed_payload` / `record_seed` の呼び出し元は `pda_improvement_cycle.py` の 2 箇所のみで、いずれも `tree_root` を明示的に渡す。

## 11. 回帰とフェンス実効性

- `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` 除く）: **598 passed**。台帳の申告値と一致。
- 負の対照（実体同一性の段と実効幅測定の両方を無効化）で **19 failed / 579 passed**。台帳の申告値（19 失敗）と一致。落ちた 19 件は WV-01 の 2 件と WV-02 の 17 件で、内訳も申告どおり。対照解除後に 598 passed へ復帰、`git status` clean。
- `operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` は開発 PC で実行不能（`hermes_cli` / `fastapi` 不在）。ルータ経由の新規挙動は本書 §8 の `q8_router.py`（実モジュール＋stub Kanban）で等価再現した。ミニPC でのスイート実行は親セッションが行う。

## 12. 確証した新規欠陥

### WV2-01（minor）宣言段の統治面ガードが字面照合であり、未作成の統治面あて宛先を覆えない

`_pattern_names_governance` は `GOVERNANCE_PATHS` の各エントリに対する `str.startswith`（ディレクトリ形）または完全一致（ファイル形）と、`Path(text).name == "conftest.py"` である。ツリー走査側（`_is_governance_path`）は**実在するファイル**のみを見る。したがって「統治ディレクトリ配下のまだ存在しないファイル」は、パターンの字面が統治面の接頭辞を綴っているときにのみ捕まる。

実測（`./tmp/verify-wv2/q6_newdefect.py`、`q7_reach.py`）:

```
  ['operations/improvement/newname.py']  literal, file absent      -> REFUSED
  ['operations/*/newname.py']            wildcard mid, absent      -> ACCEPTED
  ['operations/improve*/newname.py']     wildcard tail, absent     -> ACCEPTED
  ['operations/**/newname.py']           recursive wildcard        -> ACCEPTED
  ['integrations/*/newmodule.py']        wildcard mid, absent      -> ACCEPTED
  ['profiles/pda/skills/*/NEW.md']       wildcard mid, absent      -> ACCEPTED
  ['infra/*/pda.service']                wildcard over systemd     -> ACCEPTED
  ['tests/*/conftest.py']                conftest by name          -> REFUSED
  ['tests/*/conftes?.py']                同一実名に一致する別綴り  -> ACCEPTED
```

受理された宣言に対し第一層は当該宛先を admit する（`write-in-scope-change`）。`conftes?.py` は `fnmatch` 上 `conftest.py` に一致するため、`tests/<dir>/conftest.py` の新設が admit される。

**より一般形でも成立する。** 字面が統治面を綴らない通常宣言でも、統治名のファイルがツリーに未実在であれば受理され、その宛先の新設が admit される:

```
  ツリーに conftest.py なし: ['tests/**'] -> ACCEPTED  → write tests/unit/conftest.py  allowed=True
                             ['src/**']   -> ACCEPTED  → write src/conftest.py        allowed=True
  ツリーに conftest.py あり: ['tests/**'] -> REFUSED（走査側が捕らえる）
```

すなわち判定はツリーの現状に依存し、「常に拒否」ではない。

**主張との不一致が本欠陥である。** (1) `_pattern_names_governance` の docstring は「ツリー走査が見られない未作成ファイルあてのパターンを本判定が捕らえる」と述べるが、字面が統治接頭辞を綴る場合に限られる。(2) 設計本文は「**統治面の被覆は常に拒否する**」と無条件に述べる。(3) これは同一リポジトリが既に名指している失敗形（開いた引数空間は綴りの列挙では閉じない）の反復であり、WV-02 の処置が測定側へ移した保証を、統治面判定については字面側に残している。

**severity を minor とする根拠（後段の backstop は健全）。** 最終化側は 2 実装とも intact で、`GOVERNANCE_PATHS` は 3 実装タプル一致。`changed_files` に統治面が入る契約は無条件に拒否される（`install.py:388`、`plugin_api.py:324`）。未追跡のまま残す経路も閉じている: 活性化前に `git status --porcelain` の clean を要求する（`install.py:654`、`plugin_api.py:489`）ため、commit すれば差分で拒否、しなければ clean 検査で拒否となる。したがって統治面の変更が live へ届く経路は無い。実害は「最終化できない作業を買う 1 ターン」と「当該ターン内で自らのテスト証跡を改変しうること（最終化はできない）」に限られる。

**批准への影響。** 修正報告の判断事項 1（統治面被覆を宣言段で拒否する範囲の批准）は、拒否範囲が「常に」であることを前提に「実質的な縮小は無い」と述べている。実際の範囲は上記のとおり字面依存であるため、批准の前提が実態と異なる。

**処置の方向（判断が必要）。** 字面の照合を綴りの前方一致から性質へ改める形が候補である。統治面の各エントリについて「そのエントリ配下に到達しうるパターンか」をパターン言語の意味で判定する（各統治ディレクトリを 1 本の代表パスとして被覆判定にかける、あるいは統治ディレクトリの実在するセグメントまでを被覆判定で照合する）。いずれもルータ側に置ける。あるいは主張の側を実態へ縮小する（WV-04 と同じ処置形）。

## 13. 欠陥としない観察（前提が到達不能・仕様の意図どおり）

1. **pointer file への深い hard link は実体同一性の段を通る。** 判定は「候補と同一親ディレクトリの `.git`」のみを比較するため、`<root>/sub/alias` を `<root>/.git` の hard link にすると carve-out は `False` を返し、書込が admit される。ただしこの前提を作る呼び出しが無い: `ln` / `cp -al` は `execution-not-opted-in`、実行テンプレートを宣言しても `execution-template` で拒否される。実行テンプレートは閉じたレジストリ（`focused-test` / `syntax-check` の 2 件のみ）であり、任意コマンドは opt-in できない。`git worktree add` は `git-subcommand`。前提付きの観察として記録する。
2. **実体同一性の段は対象実体の実在を要する。** `<root>/.git` が不在なら別綴りは検出できない。ただし削除自体が拒否（§8 の連鎖 1 手目）であり、`.git` を欠く worktree では `seed-verification-failed` で fail closed する。字面照合の段は実在に依存せず常に成立する。
3. **保証の性質が「全域不可」から「被覆最上位 N 件以下」へ変わった。** 最上位エントリが上限以下のツリーでは、先頭セグメントに名前内ワイルドカードを持つ宣言が全域へ届く（空ツリーでは `?*` / `?*/**` が受理される）。本リポジトリの最上位は 20 件であり、また測定は常にリポジトリ／worktree のツリーに対して行われるため到達しない。設計本文が測定量を明記しているとおりの意図された性質である。
4. **再導出は同一 body でも拒否へ振れうる。** 先頭セグメントに名前内ワイルドカードを持つ宣言（例 `s?c/**`）は、一致する最上位エントリが増えると測定値が増える。§9 の 2 経路（`_eligible_tasks` の絞り込みと `_ensure_worktree` の clean 要求）が通常の再導出を塞ぐが、worker の commit 後にカードが ready へ戻され worktree が残る経路は覆われない（`status --porcelain` は clean のままツリーは変化している）。拒否側のみで許可は広がらず、必要な前提が 3 つ重なるため観察として記録する。台帳 15 節 2 の当該文は保証よりわずかに強い。
5. **reconciler prompt の `integrations/hermes-*/` 表記は現ツリーでは正確。** `integrations/` 配下の `hermes-*` は 3 件で、いずれも `GOVERNANCE_PATHS` に含まれる。`openwebui-hermes-progress` は当該綴りに一致しない。文書上のずれは無い。

## 14. 再現手順

```
cd /Users/fox4foofighter/dev/pda/.claude/worktrees/m1-resume-classifier-fix-da21a3
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q1_ast.py         # §10 AST・定数・理由コードの不変
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q2_wv01.py        # WV-01 反転・負の対照・false deny
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q3_wv01_e2e.py    # WV-01 連鎖と残余
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q4_wv02.py        # WV-02 反転・床の性質・false deny
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q5_idem.py        # §9 冪等性
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q6_newdefect.py   # WV2-01・観察 1/2/5
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q7_reach.py       # WV2-01 到達範囲と backstop
./tmp/venv-scope/bin/python ./tmp/verify-wv2/q8_router.py      # WV-03 / WV-04 / ルータ経由の WV-02
```

負の対照は `scope_gate.py` の実体同一性段と `scope_seed.py` の `_reject_overbroad_scope` を一時的に無効化して測る（実施後は `git checkout --` で復元し 598 passed と `git status` clean を確認済み）。`./tmp/` 配下と OS 一時ディレクトリのみを使用。
