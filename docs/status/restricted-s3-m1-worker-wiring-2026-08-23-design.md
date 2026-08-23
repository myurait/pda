# S3-M1 worker 配線設計と残 judgment 2 件の処置案（2026-08-23）

- 対象: goal M1 残余（オーナー承認済み案A = worker 配線は M1 の成果物）。
- 入力: `docs/design/task-scope-admission-gate.md` S3-M1 節、`docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md` §10-4、`integrations/hermes-scope-gate/`、`operations/improvement/pda_improvement_cycle.py`、`integrations/hermes-pda-approvals/dashboard/plugin_api.py`、`operations/improvement/install.py`、`profiles/pda/skills/pda-autonomous-improvement/SKILL.md`。
- 本書は設計提案であり、実装は含まない。統治面（C1-C9・ADR D1）の緩和は含まない。judge 実接続・隔離実行は M2 のまま。

---

## 0. 実地で確認した前提事実

以下はすべてコード読解で確認した。判断の根拠がここに依存するため先に列挙する。

**F1. 承認ゲートは Git 同一性 2 項を既に自前で導出している。**
`integrations/hermes-pda-approvals/dashboard/plugin_api.py::verify_workspace`（416-427 行）は `git -C <workspace> rev-parse --git-dir` / `--git-common-dir` を自ら実行し、解決後の絶対パスを得る。`operations/improvement/install.py`（602-619 行）も同じ導出を行う。両者はその導出値を「申告値と一致するか」の比較にのみ使っている。

**F2. 実質的な安全性質は導出値のみで成立している。**
「対象が linked worktree であること」（= worker が primary repo 上で作業していないこと）の判定は `resolved_git_dir == resolved_common_dir` の比較であり（plugin_api.py 422-423、install.py 614-615）、**申告値を一切参照しない**。申告値を参照するのはその直後の drift 比較 2 行だけである。

**F3. install.py の比較は 2 段になっている。**
`verify_owner_approval` の戻り値 `approval` は **台帳行**（`pda_owner_approvals`）由来である（install.py 495-496 行）。install.py は (i) 台帳行 vs marker（570-578 行、`git_common_dir` / `git_dir` を含む）と (ii) 実地導出値 vs 台帳行（616-619 行）の 2 段を持つ。

**F4. 台帳へ書き込まれる値は worker 申告値である。**
plugin_api.py の `INSERT INTO pda_owner_approvals`（749-770 行付近）は `approval["git_common_dir"]` / `approval["git_dir"]` を書く。`approval` は worker が作成した `pda_approval` オブジェクトである。

**F5. 契約内で当該取得形は admit されない。**
`ARTIFACT_GIT_READ_SUBCOMMANDS`（scope_gate.py 2622 行）は `rev-parse` を含むが、引数検査は closeout 共有実装 `_verification_action`（3823-3828 行）を経由し、`rev-parse` に許す引数は `HEAD` / `--verify HEAD` / `--abbrev-ref HEAD` の 3 形のみ。それ以外は `verify-target` で拒否される。ここへ 2 形を足すことは共有実装の拡張であり D-S3-7 決定 1 に抵触する（= 選択肢 (c) が不採用である理由）。

**F6. seed の read-back 経路は存在する。**
seed 済みターンは `locked` で開始し（`start_turn` 1201-1223 行: seed があれば task_class を artifact-change へ固定し契約を構築）、その状態で `scope_gate action=lock` を呼ぶと契約が冪等に返る（`_lock_artifact_change` 1538-1555 行）。したがって seed に値を載せれば worker は読み出せる。ただしこれは「値が worker を経由する」ことを意味する。

**F7. seed の存在それ自体が強制のスイッチである。**
`start_turn` は seed があればターンを locked で作る。`admit_without_turn` の enforced 判定も seed 存在を参照する（2367 行）。artifact-change 用のレーン別スイッチは他に無い。`PDA_SCOPE_GATE_ARTIFACT_PRELOCK`（plugin_runtime.py 52 行）が制御するのは **seed が無いターンの lock 前段**だけである。

**F8. 読み取り系ツールはパス検査を受けない。**
`ARTIFACT_READ_TOOLS = {read_file, search_files, session_search}`（467-473 行）は unbound 段（2376-2379 行）・lock 前段（3045-3048 行）・locked 段（3637 行）のすべてで引数を見ずに admit される。`session_search` はファイルパス引数を持たない。

**F9. 割当点は PDA 側コードにあるが worker 起動は gateway 側にある。**
`operations/improvement/pda_improvement_cycle.py::_route_task`（160-202 行）が worktree・branch・forced skill・assignee を CAS で書き、`notify_task_updated` で通知する。`integrations/hermes-kanban-governance/README.md` 6-7 行が明記するとおり、以後の worker 起動と lifecycle は gateway 内蔵の Kanban dispatcher が持つ。

**F10. seed store と kanban store は別 DB である。**
seed は `<HERMES_HOME>/plugin-data/pda-scope-gate/scope-gate.db`（`default_state_path` 3988-3996 行）。kanban は `~/.hermes/kanban.db`。同一トランザクションに入れられない。

**F11. seed は同一 payload に対して冪等、異 payload に対して硬く失敗する。**
`record_contract_seed`（1008-1030 行）は既存 seed と payload が完全一致なら既存を返し、相違があれば `ValueError("a different contract seed already exists for this task")` を送出する。

**F12. カードは write scope を宣言する欄を持たない。**
`_route_task` が書くのは `workspace_path` / `branch_name` / `skills` / `assignee` のみ。`docs/operations/pda-improvement-cycle.md` の日次サイクル手順 4 は Ready 化条件として「目的、受入条件、非目標、検証方法、最終反映対象」を要求するが、機械可読な write scope 宣言は存在しない。

---

## 1. Judgment A: 承認 metadata の Git 同一性 2 項の供給手段

### 1.1 選択肢

**(a) 割当 seed が値を供給する。**
`pda_improvement_cycle.py::_ensure_worktree` は既に worktree 内で git を実行しているため、2 項の導出をそこへ足すのは小さい。seed schema に 2 欄を追加し、worker は F6 の read-back 経路で読み出して `pda_approval` へ転記する。

**(b) 承認ゲート側が handoff 検証時に導出する。**
F1 のとおり導出コードは既に両検証点に存在する。変更は「台帳へ書く値を worker 申告値（F4）から自前導出値へ差し替え」「`pda_approval` から当該 2 欄を必須から外す（schema_version bump）」の 2 点。

**(c) 共有 allowlist を拡張して当該取得形を admit する。** — D-S3-7 決定 1 に抵触（F5）。不採用済み。

### 1.2 (a) の問題点

1. **設計原則との衝突。** 設計 395 行は「production safety approval と scope admission を別判定として維持する」と定める。seed は権限上限であり、承認 metadata をそこへ載せると 2 つの意図的に分離された判定が結合し、承認契約の schema が scope gate の schema に依存する。
2. **provenance が改善しない。** F6 のとおり値は worker を経由して `pda_approval` へ転記される。出所が orchestrator になる分は改善だが、承認オブジェクトが依然「実行主体が申告した値」を運ぶ構造は変わらない。
3. **false-deny 経路の新設。** seed は割当時に一度記録される（F11 により異 payload は硬く失敗）。worktree が正当に再作成されると、seed の値と承認時の実地導出値が乖離し、承認が fail-closed で落ちる。scope admission に何の関係もない値のために承認が止まる。
4. **schema 変更 2 箇所は避けられない。** seed schema と `pda_approval` schema の双方を触る。(b) は後者のみ。

### 1.3 (b) の設計（推奨）

導出点を 2 つに固定し、drift 検査の 2 点性を維持する。

- **承認時（plugin_api.py）**: `verify_workspace` が既に導出している値（F1）を台帳 INSERT（F4）へ渡す。worker 申告値は参照しない。
- **消費時（install.py）**: 実地再導出（602-613 行）と台帳行の比較（616-619 行）を**そのまま維持**する。F3 のとおりこの比較は既に台帳行に対して行われているため無改訂で成立する。台帳行 vs marker の比較（570-578 行）からは当該 2 キーを外す。
- **digest の扱い**: digest は worker 作成オブジェクト（2 欄を除いたもの）に対して取り、`schema_version` を上げる。**ゲート側で augment してから digest を取る形は採らない** — digest 実装は plugin_api.py（212 行）と install.py（556-563 行）に独立に 2 つあり、両者が同一に augment し続ける保証を要求する形は避ける。

結果として、2 点 drift 検査は「承認時のゲート導出値 vs 消費時のゲート導出値」となり、両端で provenance がゲート側になる。F2 のとおり実質的な安全性質（linked worktree 判定）は元から導出値のみで成立しているため、この変更で境界は一切弱まらない。

### 1.4 (b) の正直な残余

オーナーが承認する digest が worktree 同一性を覆わなくなる。同一性の束縛はゲートが書いた台帳行へ移る。監査者は digest ではなく台帳行を見ることになる。これは (a) と比較したときの (b) の唯一の実質的な後退であり、記載すべきトレードオフである。ただし consume 時の実地再導出（install.py 602-619 行）が残るため、「承認された台帳行の同一性が消費時点でも成立していること」は引き続き機械的に検査される。

### 1.5 統治面

gate / approvals / cycle のいずれもガバナンス面（ADR D3）であり、(a)(b) いずれもオーナーコミット変更になる。差別化要因ではない。

---

## 2. Judgment B: 読み取り系ツールのパス境界検査の帰属

### 2.1 現状の主張範囲

設計 408 行は第一層を **write 境界**と定義し、「スコープ逸脱の機械的遮断」の主張をこの層に限る。508 行も同じ限定を繰り返す。448 行は読み取り系ツールがパス検査を受けないことを既存残余として明記している。したがって **F8 の事実は M1 の主張を反証しない**。争点は「その主張範囲のままで exit してよいか」である。

### 2.2 選択肢と評価

**M1 で閉じる。** 却下。理由は 4 点。

1. **決定済み許可集合に対する admission の縮小になる。** D-S3-7 で確定した第一層の許可集合に読み取り系ツールの引数検査は含まれない。exit gate 直前に許可範囲を縮める変更は批准対象を動かす。
2. **false deny ゼロ要件に対する実測根拠が無い。** 本クラスは false deny ゼロを要求する。正当な読み取り集合（worker が実際に読むパスの全体）は実機証拠を伴わない。設計側で推定した集合で境界を切ると、必須手順の読み取りを落とす risk がある。
3. **構造的に部分的にしかならない。** unbound 段（2376 行）と lock 前段（3045 行）には照合基準となる locked root が存在しない。M1 で入れられる境界は locked 段限定であり、前段の読み取り面は開いたままになる。加えて `session_search` はファイルパス引数を持たないため、パス境界では表現できず carve-out が必要になる。carve-out がそのまま穴になる。
4. **M2 の隔離実行が同じ問題を上位で解く。** 第二層の M2 必須要件 1（設計 510 行）は「ファイルシステム名前空間をロック済み worktree へ制限した隔離実行」である。これは OS 水準で全段・全ツールの読み取りを束縛し、引数検査を必要としない。引数水準の境界を M1 で作ると、M2 で上位機構が入った時点で二重になる。

**M2 残余として宣言（推奨）。** 第二層の M2 必須要件 1 へ併合する。「隔離実行は第二層の実行副作用のためだけでなく、本クラスの読み取り面の境界も供給する」と明示する。

**脅威モデルに明記のみ。** 単独では不足。448 行と README に既に残余として書かれているが、**write 境界の残余と confidentiality の残余が同じ扱いで並んでいる**。露出の性質が違う（前者はローカル履歴に留まる、後者はロック済み worktree 外の内容が読める）ため区別が必要。

### 2.3 推奨の内容

1. **M2 の必須要件 1 へ併合**し、隔離実行が読み取り境界を供給することを明記する。
2. **主張文そのものへ限定を書く。** 「第一層 = write 境界」を残余節ではなく主張文と exit gate の主張範囲に書く。読者が主張を読んだ時点で範囲が分かる形にする。
3. **confidentiality 残余として write 境界残余から分離して記載する。** 露出範囲を抽象名で記す（ロック済み worktree 外の資産、他タスクの作業領域、セッション記録面）。
4. **M1 exit 時点で live でないことを併記する。** 自律レーンの有効化は seed 配線と同時（D-S3-8）であり、seed 配線自体が既定 off（後述 3.4）であるため、M1 exit 時点でこの露出は運用上発生しない。

---

## 3. 配線設計

### 3.1 seed 呼び出し側の配置

**配置**: `operations/improvement/pda_improvement_cycle.py::_route_task`。

**呼び出し順序**: seed 記録 → assignment CAS → `notify_task_updated`。

F10 により seed store と kanban store は別 DB で同一トランザクションに入れられない。したがって失敗モードを順序で処理する。

- **seed 先行**: seed が失敗したら `CycleError` を送出し CAS へ進まない。CAS 成功後に seed が失敗する順序を採ると、seed 無しの worker が起動しうる（= 設計 580 行「seed 無しで自律レーンを強制する構成は採らない」に反する。厳密には「強制しない」ため危険ではないが、案A の成果物として意味を持たない）。
- **孤児 seed の扱い**: seed 成功後に CAS が `claim-race` で失敗すると、未割当タスクに seed が残る。seed は task_id を鍵とする上限であり、割当されないタスクに上限があること自体は無害。次 tick で同一 payload が再記録され F11 の冪等経路で通る。
- **`notify_task_updated` は CAS 後**: これが dispatcher を起こす契機であり、seed が既に存在する状態で worker が起動することが保証される。

### 3.2 write scope の出所

F12 のとおりカードに機械可読な write scope 宣言が無い。これが配線の実質的な前提条件である。

**方針**: カード側の宣言を必須にする。Ready 化条件（`docs/operations/pda-improvement-cycle.md` 日次サイクル手順 4）へ機械可読な scope 宣言を追加し、`_route_task` がそれを読む。宣言が無いカードは割当しない（`CycleError` + カードコメント）。

- tenant 既定値（リポジトリ全体など）を置く案は採らない。seed の目的は狭い上限であり、既定で広い集合を配ると seed 経路の意味が失われる。
- 宣言は **orchestrator が読む**ため出所は worker の外にある（INV-S8 を満たす）。

**seed の各欄の既定**:

- `write_paths`: カード宣言必須（`record_contract_seed` は空を拒否する。991-993 行）。
- `test_paths`: カード宣言があれば採用、無ければ空集合（設計どおりテスト資産の書込を許可しない）。
- `execution`: **既定は空集合**（第二層 opt-in 無し）。カードが検証テンプレート ID を宣言した場合のみ載せる。第二層は M2 まで「宣言済み・未強制」であるため、M1 では空を既定とするのが整合する。
- `git_write`: D-S3-3 のクラス既定（`stage` / `commit`）。カード側からの**縮小のみ**受ける。

**決定論性の要件**: F11 により、同一タスクに対して 2 度目の seed 記録が異 payload だと硬く失敗する。したがって導出はカードから決定論的でなければならない。

- パターンの正規化・順序は `normalize_scope_patterns` に一任し、cycle 側で並べ替えない。
- **タスク進行中に scope 宣言が編集されると、次 tick で「a different contract seed already exists」でタスクが詰まる。** これはオーナー操作の領域とし、`CycleError` + カードコメントで表面化させる（無言で新 payload を通す経路は作らない。seed の上限性が失われる）。scope の変更は新カード、または今日は存在しないオーナー側 seed 置換操作として扱う。

### 3.3 worker profile への適用方法

**profile 単位の plugin/hook 適用は不要であり、存在しない。**

scope gate は gateway 水準の plugin である（`plugin.yaml` が hooks を provide し、`install.py` が hermes config の `plugins.enabled` と `hooks.pre_tool_call` へ登録する）。profile 別の有効化スイッチは無い。**レーンの強制セレクタは seed の存在**（F7）であり、profile 設定ではない。

profile 側が担うのは次の 2 点のみで、いずれも既存である。

- forced skill `pda-autonomous-improvement` の付与（`_route_task` 164-166 行、既存）。
- SKILL.md の手順記述が admit 済み集合と整合していること。SKILL.md は具体 git コマンドを名指していないため、**admit 済みの読み取り形を positive に名指す記述を足す**のが整合化の方向である（worker が admit されない形へ手を伸ばさないようにする）。per-turn policy 文面（`_ARTIFACT_CHANGE_CONTEXT`、plugin_runtime.py 40-49 行）は既にこの内容を持つ。

### 3.4 有効化経路

**2 つのスイッチは別物であり、seeded レーンに必要なのは前者だけである。**

1. **cycle 側 seed フラグ（新設、既定 false）**: `continuity/autonomous-improvement.json` に `scope_seed.enabled` を置き、既定 false。false なら `_route_task` は seed を記録しない（従来どおり audit-only の worker になる）。**これが自律レーンの opt-in である**。F7 のとおり seed を記録すること自体が強制の発効であるため、他にスイッチは要らない。D-S3-8 の「自律 worker レーンの有効化は seed 配線と同時」を文字どおり実装する形になる。
2. **`PDA_SCOPE_GATE_ARTIFACT_PRELOCK`（既存、既定 off）**: **seed が無いターン**の lock 前段既定拒否を制御する。自己 lock レーン（対話ターン）のための D-S3-8 スイッチであり、seeded レーンには関与しない。gateway プロセスの環境変数として設定する必要がある（cycle プロセス側ではない）。

M1 成果物としては呼び出し側を配置し、フラグ既定 false で inert に出荷する。加えて cycle 自体が `enabled: false`（オーナー停止、`continuity/autonomous-improvement.json`）であるため、M1 exit 時点で live 影響はゼロである。本番有効化は次 gate の承認事項。

### 3.5 synthetic payload 確認

設計第 7 項の確認項目（audit フック発火粒度、task_id/session_id の到達）を 2 段に分ける。

**A. 開発機で閉じられる部分（store 意味論）**

- スクラッチの `HERMES_HOME` と scope-gate store を作り、synthetic な task_id / session_id で `record_contract_seed` → `start_turn` → `admit_tool` の列を回す（先行事例: `tmp/probe-d8/` / `tmp/probe-d9/`、git 管理外）。
- 確認する性質: seed 記録後の初回 `start_turn` が `locked` で作られること、`admit_without_turn` が seed 存在で enforced になること、seed 再記録が同一 payload で冪等・異 payload で失敗すること、`scope_gate action=lock` が契約を冪等に返すこと。
- 発火粒度が「ユーザーターン単位でない」場合の closure 規範（設計第 4 項）を synthetic に再現し、閉じたターンで変異が拒否されることを確認する。
- **確認は専用の設定ファイルと synthetic id で行い、`continuity/autonomous-improvement.json` には触れない**（オーナー停止状態を維持する）。

**B. 実機確認リスト（ミニPC。開発機では確定できない host 事実）**

1. dispatcher 起動の Kanban worker で `pre_llm_call` / `pre_tool_call` に **非空の `task_id` が届くこと**（設計第 9 項「host 識別子の配線が前提条件」）。task_id / session_id の双方が欠けたターンは照会対象を持たない。
2. `post_llm_call` の**発火粒度**（ユーザーターン単位か LLM 呼び出し単位か）。設計第 7 項の明示確認項目。
3. cycle プロセスと gateway プロセスが**同一の `scope-gate.db` を解決すること**（両 systemd unit の `HERMES_HOME`）。併せて cycle の実行ユーザーが当該ファイルへ書けること、および **SQLite のクロスプロセス競合**（gateway の hook 経由アクセスと cycle の seed 記録が `BEGIN IMMEDIATE` で衝突した際の busy timeout 挙動）。
4. `PDA_SCOPE_GATE_ARTIFACT_PRELOCK` の**実効値が gateway プロセス側から読み戻せること**（D-S3-8 が要求する運用側確認）。
5. gateway の実機 HEAD が plugin `install.py` / kanban-governance patch の前提と一致すること、および installer の冪等性。
6. **ツール語彙の一致**: `ARTIFACT_READ_TOOLS`・作業記録系カタログの名前が `default` profile worker の実 tool 語彙と一致すること（架空名は許可の空振り、実名の欠落は false deny）。
7. cycle が記録する worktree path と gate の canonical root（`_canonical_targets` + `rev-parse --show-toplevel`）が**実ファイルシステム上で一致すること**（symlink / realpath の差異）。

---

## 4. 設計文書への追記案

`design_doc_diff_proposal`（戻り値）を参照。追記は抽象水準に留め、実装差分は含めない。

## 5. 波及先

`cross_dependencies`（戻り値）を参照。

## 6. 実装時に判明した本書の事実誤認（2026-08-23、実装ラウンドで追記）

**§1.3 および F3 の「消費時（install.py）の実地導出値 vs 台帳行の比較は無改訂で成立する」は誤りである。** 実装時に確認したところ、`_verify_approved_artifact` の当該比較は台帳行ではなく **worker 作成オブジェクト**（`approval`）を参照していた。台帳行は同関数の `marker` 引数として別に渡っている。したがって案(b) で当該 2 欄が worker オブジェクトから消えると、この比較は `None` との照合になり常に失敗する。

実装では比較先を `marker`（台帳行由来）へ変更した。これは司令塔決定（「消費時の実地再導出と台帳比較は維持」）に忠実な実装であり、決定からの逸脱ではない。本書の記述が現行コードを取り違えていただけである。併せて、同関数の「worker オブジェクト vs 台帳行」の欄別比較ループからも当該 2 欄を外した（§1.3 が指示したとおり）。
