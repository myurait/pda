# S3-M1 worker 配線の反証レビュー（レンズ: w-bypass、2026-08-23）

- 対象コミット: `f7cfe0f`（`913214a..HEAD`）。
- レンズ: worker がカード宣言・seed 経路を介して write scope を広げられないか。承認 metadata のゲート側導出化（Judgment A）で worker 申告への依存が真に消えたか。digest 対象変更で改竄面が開いていないか。
- 再現環境: `./tmp/probe-wb/`（`probe.py` / `git_probe.py` / `gitdir.py` / `decoy.py` / `hooks.py` / `hooks2.py`）。実行は `./tmp/venv-scope/bin/python`。すべて `tempfile.mkdtemp` 上の合成リポジトリで、リポジトリ本体・実機状態には触れていない。
- **本書は取扱制限。迂回手法の具体形を含む。** 親セッションへの戻り値には ID と抽象名のみを返す。

確証と推測を明示的に分ける。「確証」はこのラウンドで実際にコードを走らせて観測した事実、「推測」は観測していない前提を含む経路。

---

## W-B-01（major）宣言由来の書込上限に機械的な上限がない

### 確証部分

`derive_seed_payload` → `record_contract_seed` は `write_paths` の**幅**を一切制限しない。全域パターンがそのまま契約になる。

```
=== P1: write_paths ['**'] accepted? ===
ACCEPTED: {'task_id': 't1', 'write_paths': ['**'], 'test_paths': [], 'execution': [], 'git_write': None}

=== P1b: gate normalization of ['**'] ===
normalized: ('**',)
```

seed 記録後の locked 契約は `targets.write_paths = ["**"]` を持ち、worktree 直下の任意パスへの書込が admit される。`git_write` は省略時のクラス既定 `["stage","commit"]` が入る（`./tmp/probe-wb/e2e.py`）。

`**` と `**/*` の双方で、**worktree の Git メタデータ参照ファイルまで admit される**（`./tmp/probe-wb/git_probe.py`）。

```
--- seed write_paths=['**'] ---
  .git                         allowed=True  write inside the locked write scope
  .git/config                  allowed=True  write inside the locked write scope
  .git/hooks/pre-commit        allowed=True  write inside the locked write scope
  src/a.py                     allowed=True  write inside the locked write scope
  anything/new.txt             allowed=True  write inside the locked write scope

--- seed write_paths=['src/**'] ---
  .git                         allowed=False  .git is outside the locked write scope
  .git/config                  allowed=False  .git/config is outside the locked write scope
  .git/hooks/pre-commit        allowed=False  .git/hooks/pre-commit is outside the locked write scope
  src/a.py                     allowed=True  write inside the locked write scope
  anything/new.txt             allowed=False  anything/new.txt is outside the locked write scope
```

すなわち露出は宣言の幅の関数であり、宣言が狭ければ同じパスは拒否される。ゲート側にメタデータ面の無条件 carve-out は無い。

### 設計との衝突

設計ノート §3.2 は tenant 既定値を退けた理由を「seed の目的は狭い上限であり、既定で広い集合を配ると seed 経路の意味が失われる」と書いている。カード宣言経路は同じ状態へ到達でき、それを拒否する機構が無い。上限の幅を決めるのは AI が書いたカード本文であり、制約は日次リコンサイラプロンプトと運用手順の散文（「そのcardの成果に必要な最小範囲だけを書く」「リポジトリ全体や広いディレクトリを既定で置かない」）だけである。

### 推測部分（AI 介在の注入経路、未検証）

`daily_reconciler_prompt.txt` 手順 3 は「bodyと**コメント**から受入条件と書込スコープ宣言が十分か確認してreadyへpromoteする」と指示する。一方 `ARTIFACT_WORK_RECORD_TOOLS` は `kanban_comment` を全段で admit する（`kanban_create` は明示除外）。したがって worker はカードへコメントを残せる。ここから「worker が todo カードへ広い宣言ブロックをコメントし、specifier がそれを body へ写して ready 化する」経路が形式上成立する。

ただし `parse_scope_declaration` が読むのは `task.body` のみであり、コメントは直接には宣言にならない。成立には specifier が写す一段が必要で、これは機械的必然ではない。**未検証の推測として記録する。** 確証部分は「上限に機械的上限が無い」ことだけである。

### 検査されなかった面

新規テスト `test_scope_seed_wiring.py` に `**` およびメタデータ面の事例は無い（`grep '\.git\|hooks\|\*\*'` で該当なし）。

### 判断が必要な点

上限の上限を機械的に課すか、課すならどこか。ルータ側（`derive_seed_payload` で全域パターンを拒否）とゲート側（`normalize_scope_patterns` で拒否）の двух択で、後者は D-S3-7 決定 1 が触るなと定めた共有実装に当たる可能性がある。

---

## W-B-02（blocker）第一層で許可された書込のみから、許可済み Git 書込動作が任意実行の起点になる

### 確証（end-to-end 再現済み）

W-B-01 で admit される**worktree 内のファイル書込だけ**を使って、リポジトリ自身の設定探索を agent 作成物へ向け替えられる。その後、契約が admit する commit 動作が agent 作成コードを実行する。

段階 1: メタデータ参照の向け替えが成立する（`./tmp/probe-wb/gitdir.py`）。

```
before: git-dir       = .../real/.git/worktrees/wt
before: git-common-dir= .../real/.git
after repointing wt/.git:
  git-dir        = .../decoy/.git/worktrees/dwt | rc 0
  git-common-dir = .../decoy/.git | rc 0
  branch         = pda-auto/t1
```

段階 2: 内容一致の decoy を用意すると、承認ゲートの Git 由来検査群がすべて decoy 側を読んだまま整合する（`./tmp/probe-wb/decoy.py`）。

```
git-dir        = .../decoy/.git/worktrees/dwt
git-common-dir = .../decoy/.git
linked?        = True
branch         = pda-auto/t1
HEAD           = 831a9ba6...  (real HEAD was 3255376a...)
status clean?  = True
toplevel       = .../wt
```

`verify_workspace`（plugin_api.py 408-511）の検査項目との対応:

- `rev-parse --show-toplevel` は作業ディレクトリ由来なので不変 → 「workspace_path is not the Git worktree root」通過。
- `resolved_git_dir != resolved_common_dir` は decoy 内でも成立 → 「workspace is not a linked worktree」通過。**そして Judgment A の `identities` はこの分岐で埋まる**ため、台帳へ書かれる正規同一性は decoy 側の値になる。
- `branch --show-current` 一致、`status --porcelain` 空 → 通過。
- 残る束縛 `head_sha` / `base_sha` / `changed_files` は **worker が `pda_approval` で申告する値**であり、検査は decoy 内で行われるので自己整合させられる。

段階 3: gitdir 一式を worktree 内に置くと commit フック実行に至る（`./tmp/probe-wb/hooks2.py`）。

```
git-dir        = .../wt/vendor/common.git/worktrees/w1
git-common-dir = .../wt/vendor/common.git
linked?        = True
toplevel       = .../wt
hooksPath      = .../wt/vendor/hooks
add rc 0
commit rc 0
HOOK EXECUTED: True hook-ran
```

先に試した「per-worktree gitdir にだけ設定を置く」形は不成立だった（`hooks.py`: `HOOK EXECUTED: False`）。`extensions.worktreeConfig` 無しでは per-worktree config が読まれないため。common 側まで worktree 内へ持ち込んだ段階 3 で成立する。

### 破られる性質

1. **第二層の既定閉鎖。** 契約は `execution.templates = []` を持つが、フック経由の実行は検証テンプレートを一切通らない。M1 は第二層を「宣言済み・未強制」として出荷するが、この経路は宣言も強制も迂回する。
2. **契約自身の禁止項。** `actions.forbidden` に `bypass-verification-hooks` / `rewrite-history` / `deploy-or-restart` / `delegate-or-background` が並ぶが、実行されるのは任意シェルなのでいずれも機械的裏付けを失う。
3. **第一層の書込上限そのもの。** 実行体は `git commit` の子プロセスであり、第一層は tool call 引数を検査する層なので視界に入らない。フックは worktree 外へ書ける。
4. **抑止フラグが塞がれている方向が逆。** `_ARTIFACT_COMMIT_REWRITE_TOKENS` は `--no-verify` / `-n` を拒否する（scope_gate.py 2577-2595）。したがって admit される commit では**フックが必ず走る**。実行は「可能」ではなく「強制」である。
5. **README の明文と衝突。** README は read-only Git が worktree 内に留まる根拠を「the seed check that fixed the locked root at a worktree top level plus Git's own repository discovery from there」と書く。その repository discovery の入力が、広い宣言下では agent 書込可能である。

### Judgment A に対する評価

Judgment A の狙い（申告値依存の除去）は**宣言依存については達成されている**。`validate_approval` / `_validate_approval_contract` は当該 2 欄が存在すれば拒否し、台帳 INSERT はトランザクション内の `fresh_identities` を書き、消費時は再導出を `marker`（台帳行由来）と比較する。この配線は決定に忠実で、実装として正しい（下記「健全と確認した点」参照）。

ただし**信頼の根**は移っていない。導出の入力は worktree のメタデータ参照であり、それは seed が許可し得る書込面の内側にある。したがって provenance は「worker が申告した値」から「worker が書き得るファイルが述べる値」へ移っただけで、この構成では強化になっていない。§1.4 が記した残余（「オーナーが承認する digest が worktree 同一性を覆わなくなる。同一性の束縛はゲートが書いた台帳行へ移る」）は、台帳行側の束縛も同時に破られ得るという点で、記載より弱い。

### 現時点の運用上の緩和（欠陥の修正ではない）

`continuity/autonomous-improvement.json` は `enabled: false` かつ新設 `scope_seed.enabled: false` であり、M1 exit 時点で live 露出は無い。狭い宣言なら段階 1 の書込自体が拒否される（W-B-01 の観測どおり）。これは運用事実であり、層の主張の欠落を埋めるものではない。

### 判断が必要な点

メタデータ面の無条件 carve-out をどこへ置くか。書込対象検査は closeout と共有される実装であり、D-S3-7 決定 1（共有実装の拡張を避ける）との関係を司令塔が裁定する必要がある。宣言の幅に依存しない carve-out にすれば W-B-01 の最悪形も同時に無効化できる。

---

## W-B-03（minor）強制スイッチの既定値が呼び出し側の省略で無効側へ倒れる

`_route_task` の署名は `scope_seed_enabled: bool = False`（pda_improvement_cycle.py 273-283）。キーワードを省略した呼び出しは seed を記録せず、エラーも出さずに強制なしで割当を完了する。既存テスト `operations/improvement/tests/test_pda_improvement_cycle.py:204` は実際にこのキーワードなしで呼んでいる。

本番経路 `run_cycle` は明示的に渡しているため現時点で悪用可能な経路は無い。潜在的な形の問題として記録する。強制の有無を決める引数は必須引数にするのが fail-closed 規律に沿う。なお同時に追加された `repo: Path | None = None` は、enabled かつ `repo` 欠落で `CycleError` になるので fail-closed 側であり、こちらは正しい。

---

## W-B-04（minor）Markdown 上は不活性な宣言ブロックが実効宣言として解釈される

`_SCOPE_BLOCK_RE` は fence の入れ子・インデントコードブロックの不活性性を解さない（`./tmp/probe-wb/probe.py`）。

```
=== P4: indented / nested fence example parsed as live declaration? ===
  4-space-indented example -> {'task_id': 't1', 'write_paths': ['**'], ...}
  outer 4-backtick fence -> {'task_id': 't1', 'write_paths': ['**'], ...}
  blockquoted rejected: card has no machine-readable ```pda-scope``` write scope declaration
```

4 スペースインデント（Markdown では逐語テキスト）と、外側 4 バッククォート fence の内側（Markdown では図解）のいずれも、実効宣言として読まれる。引用形式のみ読まれない。

帰結は二方向ある。人間が「例」として読むテキストが実際の上限になる方向と、実宣言と図解を併記したカードが「2 ブロックある」として拒否される方向（fail closed だが可用性を落とす）。

---

## W-B-05（minor）運用手順の宣言例が実装の受理形と一致しない

`docs/operations/pda-improvement-cycle.md` 54 行は「宣言は情報文字列`pda-scope`のフェンス済みブロックへJSONオブジェクトで書く」と指示するが、直後 56-58 行の例は情報文字列の無い素の fence である。

```
54|宣言は情報文字列`pda-scope`のフェンス済みブロックへJSONオブジェクトで書く。
55|
56|```
57|{"write_paths": ["operations/improvement/*.py"], "test_paths": [...]}
58|```
```

この例を写したカードは `pda-scope` ブロックを持たないので `missing-scope-declaration` で割当されない。false deny ゼロを要求するクラスの Ready 化条件で、正本手順に従うと通らない形になっている。`daily_reconciler_prompt.txt` 側の例は fence を使わないインライン表記（`例: {...}`）で、こちらは fence 形を誤らせないが、情報文字列付きの実形を一度も示していない。

（W-B-04 の入れ子問題があるため、ドキュメント内に情報文字列付き fence を素朴に書けない事情は理解できる。その事情自体を注記する必要がある。）

---

## W-B-06（minor）一枚の不正カードが tick 全体を停止させる

`_record_scope_seed` は `CycleError` を送出し、それは per-task の回復なしに `run_cycle` の `except CycleError` まで伝播する（pda_improvement_cycle.py 411-419 のループ本体に try が無い）。`max_assignments_per_tick: 1` / `max_wip: 1` と優先度順の `_eligible_tasks` の組み合わせで、宣言が壊れた先頭カード 1 枚が以後すべての適格カードの割当を塞ぐ。

`_comment_once` により診断コメントは 1 件だけ残るので、日次リコンサイラまたはオーナーが直せば復旧する。境界の破れではなく可用性の問題として記録する。

---

## W-B-07（minor）seed を書く実装と強制する実装が別コピーで、正規化の同一性が検査されていない

ルータは `load_scope_gate(repo_root)`（scope_seed.py 154-192）で**リポジトリ作業ツリーの** `scope_gate.py` を読み込み、`record_contract_seed` と `normalize_*` をそのコピーで実行する。一方強制は gateway にインストールされた plugin のコピーが行う。両者が同一リビジョンであることを主張する検査は無い。

`normalize_scope_patterns` / `normalize_git_write_actions` / `normalize_execution_templates` の意味が両コピー間でずれると、記録された上限と強制される上限が食い違う。worker から到達できる経路ではない（プライマリリポジトリは全 worker の上限外）ので、迂回ではなく整合性の穴として記録する。設計 §3.5 B-5 の「gateway の実機 HEAD が plugin install.py の前提と一致すること」は installer の前提についての項目で、seed 書き手と強制側の正規化パリティは別項である。

---

## 健全と確認した点（反証を試みて破れなかったもの）

反証レビューとして、破れなかった側も明示する。

1. **Judgment A の配線は決定に忠実。** `verify_owner_approval`（install.py 470-511）は `pda_owner_approvals` から `git_common_dir` / `git_dir` を含む列を SELECT し、その値で `marker` を組む。したがって `_verify_approved_artifact` の比較先を `approval` から `marker` へ変えた実装は「消費時の実地再導出と台帳比較を維持」に一致する。設計ノート §6 の自己訂正（「台帳行は `marker` 引数として別に渡っている」）は現行コードと合っている。
2. **申告経路は両 validator で閉じている。** `validate_approval` と `_validate_approval_contract` の双方が当該 2 欄の存在を拒否し、`APPROVAL_METADATA_SCHEMA_VERSION` と `GATE_DERIVED_IDENTITY_KEYS` が両側に定数として置かれている。
3. **台帳へ書かれるのはトランザクション内導出値。** INSERT は `fresh_identities` を使う（plugin_api.py 844-846）。冪等 replay 経路も `_identity_drift_errors` で台帳行と再導出値を比較する。導出失敗時は `identities = None` として 409 を返す fail-closed。
4. **INV-S8 は tool 面で成立。** worker 向け `scope_gate` の action 分岐は `lock` / `review` / `complete` / `block` のみ（plugin_runtime.py 213-260）。`record_contract_seed` は runtime メソッドとして orchestrator dispatch 専用に置かれ、tool 面に無い。worker が自分の seed を作る・広げる経路は無い。
5. **パターン強化は有効。** `..`、絶対パス、制御文字、セグメント跨ぎの `*` はすべて拒否される。書込対象側の上方参照も拒否される（`../repo/src/app.py` → `the target path carries an upward reference`）。
6. **`git_write` は縮小のみ。** クラス既定外の action は `derive_seed_payload` が拒否し、空配列は「Git 書込なし」へ正しく縮小する。前後空白付きの値はゲートより手前で拒否される（ゲートは strip するので、ルータ側が厳しい = fail closed 方向）。
7. **未登録の実行テンプレート ID は fail closed。** `derive_seed_payload` は通すが `record_contract_seed` が `PathRejected`（`ValueError` 派生）で拒否し、`record_seed` が `ScopeSeedError("scope-seed-rejected")` へ変換してコメント + `CycleError` になる。例外型の取りこぼしは無い。
8. **有効化フラグは committed policy 由来で、非 dict 値では無効側へ倒れる。** `isinstance(scope_seed_policy, dict)` により `scope_seed: true` のような形は enabled にならない。
9. **seed 順序は設計どおり。** seed 記録 → 割当 CAS → `notify_task_updated`。CAS 前の claim-race 事前検査があり、seed は再取得した `current` の body から導出される。

---

## 再現手順

```
cd /Users/fox4foofighter/dev/pda/.claude/worktrees/m1-resume-classifier-fix-da21a3
./tmp/venv-scope/bin/python ./tmp/probe-wb/probe.py      # W-B-01 確証部分, W-B-04
./tmp/venv-scope/bin/python ./tmp/probe-wb/git_probe.py  # W-B-01 メタデータ面
./tmp/venv-scope/bin/python ./tmp/probe-wb/e2e.py        # locked 契約と書込 admit
./tmp/venv-scope/bin/python ./tmp/probe-wb/gitdir.py     # W-B-02 段階 1
./tmp/venv-scope/bin/python ./tmp/probe-wb/decoy.py      # W-B-02 段階 2
./tmp/venv-scope/bin/python ./tmp/probe-wb/hooks2.py     # W-B-02 段階 3
```

`./tmp/` 配下のみを使用。`continuity/autonomous-improvement.json` および実機状態には触れていない。
