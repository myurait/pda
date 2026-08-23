# restricted: S3-M1 D-S3-7 / D-S3-8 実装の反証レビュー（レンズ: 迂回可能性 / d7-bypass）

- 対象差分: `e98b219`（実装）、`9179daa`（台帳追記）。基準点 `377fa33`。
- 対象ファイル: `integrations/hermes-scope-gate/scope_gate.py`、`integrations/hermes-scope-gate/tests/test_artifact_change_scope.py`、`integrations/hermes-scope-gate/plugin_runtime.py`、`integrations/hermes-scope-gate/README.md`、`docs/design/task-scope-admission-gate.md`、`docs/operations/adversarial-suite.md`、`docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md`。
- レンズ: 今回の差分は「許可の拡張」であり、これまでの修正と逆方向のリスクを持つ。主攻撃面は (1) 読み取り専用 git の引数面、(2) 作業記録系カタログ、(3) 拒否上限の計上限定。
- 欠陥ID: `I-DB-01` 〜 `I-DB-08`
- 再現スクリプト: `./tmp/probe-d7/probe_d7.py`、`./tmp/probe-d7/probe_d7b.py`（作業用 repo は `tempfile.mkdtemp()` 配下。リポジトリ木の中では `git init` が hook テンプレートを複製できないため）
- 確証と推測の区別: 「実測」と書いた行はすべて上記スクリプトまたは inline probe による実行結果。推測は「未確証」と明記した。

---

## I-DB-01 [blocker] 新設した作業記録系カテゴリが、SKILL.md が耐久制御面と宣言している面へ引数無検査で書き込む。契約検証失敗段でも許可される

**根拠**

`ARTIFACT_WORK_RECORD_TOOLS`（`scope_gate.py:492-508`）は 13 名の閉じたカタログとして locked 段（同 3182-3185）、lock 前段および契約検証失敗段（同 2761-2764）で許可される。許可は**ツール名のみで決まり、引数は一切検査されない**。

実測（`probe_d7.py` セクション C、locked 段）:

- 添付系ツールに locked root 外の絶対パスを与えた場合 → `allow=True action=record-work-state`
- 添付系ツールに上位参照を含む相対パスを与えた場合 → `allow=True action=record-work-state`
- URL 添付系ツールに外部ホストの URL を与えた場合 → `allow=True action=record-work-state`
- カード新規作成系ツールに依頼と無関係な題目を与えた場合 → `allow=True action=record-work-state`
- 作業段階ツールに当該ツールが持たないはずのフィールド（`command` / `workdir` / `path`）を混ぜた場合 → `allow=True action=record-work-state`

一方、`profiles/pda/skills/pda-autonomous-improvement/SKILL.md:17` は次を宣言している:

> The card, Git worktree, Kanban run history, and the plugin-owned approval ledger in the shared Kanban DB are the durable control plane.

そして `docs/design/improvement-orchestrator.md:10`（P1）は、カード面を 60 秒周期の dispatcher が読み、同 18 は「カードの ready 化、run の終端（done / review / blocked / failed）、承認・差戻しの記録、finalization 完了」を購読して割当てポリシー評価を回すと定めている。`operations/improvement/pda_improvement_cycle.py` は同じ DB へ割当てとコメントを書く。

したがって、設計本文と台帳が置いた前提「エージェントの作業管理平面にのみ作用し、**逸脱しうるスコープが無い**」は、リポジトリ書込境界については成り立つが、**審査ゲート自身の境界については成り立たない**。当該面は次ターンの割当てと run 終端シグナルの供給元である。

決定文がこのカテゴリから別エージェント起動系を除外した理由は「クラス予算 `subagents` が 0、§10 項目 5 でも拒否」であるが、その予算は run の起動経路を 1 つだけ塞いでいる。カード面への無検査書込は、dispatcher が起動判断に用いる面への書込であり、除外理由が守ろうとしたものと同じ資源に別経路で届く。

さらに、カテゴリは**段階別・ツール別の絞り込みなしに 3 段すべてで一括許可**されている。台帳・設計本文が挙げた許可理由は INV-S6 の「座礁したターンが blocked として記録する」であり、これは記録系の一部（blocked 記録・コメント）しか正当化しない。実測では、契約検証が失敗して `mutation-denied` に落ちたターン（＝ゲートが信頼できる契約を確立できなかったターン）でも、run 終端に相当する状態遷移系ツール（完了記録・レビュー要求・差戻し）とカード新規作成が許可される（`probe_d7.py` の C 群と既存テスト `test_work_record_tools_are_admitted_before_lock_and_after_a_failed_seed` が `kanban_block` で同じ経路を固定している）。

**カタログの由来にも問題がある。** 語彙一致テスト（`tests/test_artifact_change_scope.py:2066-2081`）が参照する語彙源は `integrations/openwebui-hermes-progress/functions/hermes_progress_pipe.py` の `_PROGRESS_TOOL_ACTIVITY_GROUPS`、すなわち**進捗表示のラベル分類**である。同ファイルの kanban 系は 12 名で、カタログはその 12 名すべて＋`todo` を採っている。つまりカテゴリは効果分析による部分集合ではなく、表示分類の丸ごとの写しである。判定時に推論を使っていない点（R-11 同型の回避）は満たしているが、**各名前が「リポジトリ境界の外側にしか作用しない」とする根拠が表示分類である**点は、決定が排したはずの capability 推論を設計時に一度だけ行ったことと等価である。

**設計・決定との衝突**

- 設計 §11 第一層「エージェントの作業管理平面（タスクボード、作業段階リスト）にのみ作用し、リポジトリの書込境界へ作用しないツール群」— ボードは審査ゲートの入力面でもあるため、前提が不完全。
- 設計 §11 第一層「書込先になりうる全フィールドを検査する。未列挙のツールは変異系として G3 へ落とす」— 本カテゴリは書込先フィールドの検査へ一度も入らない。同じ差分の一世代前に `terminal` へ `terminal-argument-unlisted` を入れた理由（「allowlist に届かない引数は、allowlist が拒否するために存在するものと同じ代入を運べる」`scope_gate.py:3100-3106`）が、このカテゴリには適用されていない。
- 台帳 7 節 2「作業管理平面には逸脱しうるスコープが無く、座礁したターンに対して INV-S6 が求める行動（blocked として記録する）がこのカテゴリで行われる」— 許可はこの理由より広い（完了・レビュー要求・差戻し・カード作成を含む）。

**対応方針（案）**

1. カテゴリを「記録のみ」（コメント・心拍・blocked 記録・参照）と「制御面遷移」（完了・レビュー要求・差戻し・カード作成・リンク・添付）に二分し、後者は locked 段のみ、かつ契約検証失敗段では拒否する。
2. 書込先フィールド allowlist と同型の**引数フィールド閉鎖**をこのカテゴリにも適用する（少なくとも添付系のパス・URL フィールドを列挙し、locked root 内・許可ホストのみへ絞る）。
3. カタログの各名前について、表示分類ではなく実効果（どのテーブル・どの制御イベントを書くか）に基づく根拠を台帳へ記録する。

**未確証**: カード新規作成が実際に dispatcher による run 起動へ至るかは、orchestrator の ready 化ポリシー（本リポジトリのゲート外）に依存する。確証したのは「ゲートが制御面への無検査書込を許可している」ことまでである。

---

## I-DB-02 [blocker] 承認 metadata が必須とする読み取りが「逸脱試行」として計上され、6 件で拒否上限が枯渇してターンが座礁する（I-COM-01 の原症状の再現）

**根拠**

`ARTIFACT_GIT_READ_SUBCOMMANDS`（`scope_gate.py:2596`）に `rev-parse` が入っているため、`rev-parse` のあらゆる形は `_admit_artifact_change_git_read` へ入り、`_verification_action`（同 3355-3376）の 3 リテラル（`HEAD` / `--verify HEAD` / `--abbrev-ref HEAD`）以外は `git-read-unsafe` で拒否される。`artifact_deny_counter`（同 2639-2656）は `git-read-unsafe` を免除集合に入れていないため、**`denied_count` に計上される**。

SKILL.md 手順 6 / Phase 2 が承認 metadata として要求するのは（`SKILL.md:31,48`、`operations/improvement/install.py:357-380`）:

- `base_sha` と `head_sha`（base/head ancestry）
- `changed_files`（exact changed-files diff）
- 絶対・非 symlink の linked-worktree root
- canonical Git common-dir / worktree git-dir identities
- `pda-auto/<task_id>` ブランチ

**必須項目のうち、どこまでが admit 範囲内で取れるかの再検証**（自己反証。当初は過大に見積もっていた）:

- `head_sha` → `rev-parse HEAD`（admit）。
- ブランチ名 → `branch --show-current`（admit）。
- `base_sha` → **取得可能**。コミット前の `rev-parse HEAD` が base に当たる。呼び出し順序を守れば admit 範囲内で足りる（実測: `allow=True action=verify-local-head`）。
- `changed_files` → **取得可能**。リビジョン指定を伴わない差分の名前のみ形（未ステージ／ステージ済みの双方）と status 短縮形がいずれも admit（実測: `allow=True`）。
- 絶対・非 symlink の linked-worktree root → 契約が保持する root パスで代替しうるが、canonical 化そのものは契約内の手段では取れない。
- **canonical Git common-dir / worktree git-dir identities → 契約内の手段が存在しない。**

したがって「契約内で取れない必須項目」は上記 2 項であり、当初想定より狭い。**一方、座礁の性質は条件付きではない**: ロック済み worktree 内の純粋な読み取りで admit リテラルに一致しないものは、何であれ 6 件で上限に達する。

**実測**（inline probe。locked 段、予算は新規状態から）:

| 投入 | 判定 | action | 累積 denied_count |
| --- | --- | --- | --- |
| worktree root 取得 | deny | `git-read-unsafe` | 1 |
| git-dir 取得 | deny | `git-read-unsafe` | 2 |
| common-dir 取得 | deny | `git-read-unsafe` | 3 |
| worktree 内判定 | deny | `git-read-unsafe` | 4 |
| base SHA 取得（親コミット形） | deny | `git-read-unsafe` | 5 |
| base SHA 取得（検証付き親コミット形） | deny | `git-read-unsafe` | 6 |
| merge-base 取得 | deny | `deny-budget` | 6 |
| base との changed-files 取得 | deny | `deny-budget` | 6 |
| 単一コミットの changed-files 取得 | deny | `deny-budget` | 6 |
| ブランチ名取得（**admit 範囲内**） | deny | `deny-budget` | 6 |
| status 短縮形（**admit 範囲内**） | deny | `deny-budget` | 6 |
| write scope 内の `write_file` | deny | `deny-budget` | 6 |

すなわち、**必須手順を順に踏むだけで 6 件目で上限に達し、以後は admit 範囲内の読み取りも write scope 内の書込も `deny-budget` になる**。これは `restricted-s3-impl-review-2026-08-23-compat.md` の I-COM-01 で報告された座礁（手順 5 の再現）と同一の終状態であり、D-S3-7 決定 3 が取り除くために作られた失敗様態そのものである。

**台帳の根拠記述が事実と一致しない。** 台帳 7 節 3 と設計本文は、admit 範囲外の引数を計上する根拠を「当該拒否はロック済み worktree 外への読み取りか、読み取り形だけが許可された subcommand の書込形のいずれかである」としている。上表の 6 件はいずれもロック済み worktree の**内側**を読むだけであり、書込形でもない。第三の類型（ロック済み worktree 内の純粋な読み取りで、admit リテラルに一致しないもの）が根拠から抜けている。

差分の版で読み取り形が新たに `git-read-unsafe` に落ちるようになった点も効いている。基準点 `377fa33` では `rev-parse` は `git-subcommand` で拒否されていた（計上は同じだが、`ARTIFACT_GIT_READ_UNADMITTED` による免除の設計が無かった）。今回、`rev-parse` を admit 集合に入れたことで、**同一 subcommand の非リテラル形が免除対象から外れる**構造ができた。免除の粒度が「subcommand 名」であるため、admit した subcommand ほど計上されやすくなるという逆転が生じている。

**対応方針（案）**

1. 免除の粒度を subcommand 名から「当該呼び出しが読み取りか」へ変える。`_admit_artifact_change_git_read` が返す拒否は、workdir 束縛の外を指す場合を除き read 系の理由コードへ分ける（例: `git-read-unsafe` を「範囲外引数（非計上）」と「境界外・書込形（計上）」の 2 コードに分割する）。
2. 承認 metadata に必要な読み取り形（worktree/git-dir 同一性、base SHA、base との changed-files）を admit 範囲へ入れるか、契約内で供給する別手段を定める。closeout に境界付き実装が無い形については、`log` と同じ扱い（非 admit だが**免除**）へ寄せるだけでも座礁は解消する。
3. 上限枯渇後に admit 範囲内の読み取りまで `deny-budget` になる点は D-S3-7 決定 3 の目的（規定フローに従うターンを座礁させない）に反するため、上限判定を「変異系・実行系の admission の前段」に限る案も検討対象。
4. `plugin_runtime.py` の per-turn policy 文面は admit 範囲を明示しており、これに完全に従う実行主体なら座礁を避けられる。しかし SKILL.md 手順 6 は policy 文面が手段を与えていない項目（git-dir / common-dir 同一性）を要求しており、二つの指示源が衝突している。衝突の自然な解消（コマンドを試す）が計上される限り、文面だけでは緩和にならない。どちらかを改める必要がある。

---

## I-DB-03 [major] 非計上レーンに状態変更形を持つ subcommand が含まれ、write 境界への逸脱試行が拒否上限を消費せずに 16 倍探索できる

**根拠**

`ARTIFACT_GIT_READ_UNADMITTED`（`scope_gate.py:2603-2616`）は「Read-only Git subcommands this class recognizes but does not admit」と注記され、`artifact_deny_counter` は `git-read-unadmitted` を `tool_count` へ回す（＝拒否上限を消費しない）。しかし当該集合の 9 名のうち 2 名（リモート設定系、reflog 系）は**読み取り形と状態変更形の両方を持つ** subcommand である。判定は subcommand 名のみで行い、tail を見ない。

実測（`probe_d7.py` セクション B、locked 段）:

- リモート設定の追加形・URL 変更形・削除形 → いずれも `allow=False action=git-read-unadmitted tool+1 deny+0`
- reflog の期限切れ形・削除形 → いずれも `allow=False action=git-read-unadmitted tool+1 deny+0`
- 認識外 subcommand（gc、checkout） → `git-subcommand`、`deny+1`（意図どおり計上）

実測（境界の有界性、inline probe）: リモート設定の追加形を反復投入すると **96 回目で `tool-budget` に到達して停止**（`tool_count=96`、`denied_count=0`）。有界性そのものは成立している。ただし拒否上限は 6 であり、当該 subcommand 族に対する探索余地は**上限の 16 倍**になる。

**設計・決定との衝突**

- 決定 3「計上を write 境界・実行境界への逸脱試行に限定する」— リモート設定の変更と reflog の削除は write 境界への逸脱試行であり、計上側に属する。
- 実装自身の原則「免除は『逸脱しえない subcommand』に対するものであり、『逸脱を試みる引数』に対するものではない」（`scope_gate.py:2624-2636`）— リモート設定系・reflog 系は「逸脱しえない subcommand」ではない。
- 新設テスト `test_the_read_only_git_subset_is_a_closed_set` は書込形の混入を `add` / `commit` / `push` / `reset` / `checkout` / `rebase` の 6 名でのみ検査しており、当該 2 名はこの列挙に入っていない。テスト設計上、この欠陥は原理的に検出されない。

**対応方針（案）**: 免除集合を「読み取り形しか持たない subcommand」に限定し、読み取り形と変更形を併せ持つ subcommand は集合から外す（＝計上側の認識外扱いへ戻す）。または I-DB-02 案 1 と同様に、tail を見て読み取り形かどうかで分ける。

---

## I-DB-04 [major] 新設した §10 受入項目と回帰テストが、必須手順より狭い流れで書かれており、I-DB-02 を通す

**根拠**

設計 §10 の新設項目 15 は通常フローを「差分確認 → 対象編集 → 焦点検証 → ステージ → ローカルコミット → 作業記録の更新」と定義し、対応テスト `test_replay_the_worker_flow_completes_without_spending_the_deny_ceiling` は 13 手順でこの列を再生して `denied_count == 0` を固定する。しかし SKILL.md 手順 6 が要求する承認 metadata の収集（I-DB-02 の表の 6 件）は項目 15 の列に入っておらず、テストにも現れない。受入項目が、受け入れるべき手順ではなく実装の許可範囲に合わせて書かれている。

項目 16 も同様である。「admit されない読み取り（**第一層の読み取り部分集合の外にある読み取り専用 subcommand**）が 1 件混じっても座礁しない。拒否上限の消費は 0」という表現は、免除が subcommand 名粒度であるという実装の性質をそのまま条件に写している。対応テスト `test_replay_the_worker_flow_survives_one_unadmitted_read_attempt` は履歴表示系 1 件のみを使い、実運用でより頻出する「admit 済み subcommand の非リテラル形」を対象外にしている。同じく `test_read_refusals_do_not_strand_a_turn_that_keeps_working` も履歴表示系のみで `ceiling + 2` 回反復し `denied_count == 0` を固定するが、I-DB-02 の形に置き換えると 6 回で座礁する。

`docs/operations/adversarial-suite.md` の新カテゴリ「拒否上限の計上規則を使った座礁と免除の悪用」は false deny 側と fail-open 側の両方を掲げているが、列挙されたテストはいずれも免除される形のみを使うため、false deny 側は実質未カバーである。

**対応方針（案）**: 項目 15 の列に承認 metadata 収集を加え、項目 16 を「admit 済み subcommand の読み取り形が admit リテラルに一致しない場合」も含む表現に改める。回帰テストは I-DB-02 の表をそのまま fixture 化する。

---

## I-DB-05 [minor] ブランチの生成・削除形が読み取り系の理由コードで記録される

**根拠**

`branch` は admit 集合に入っており、`_verification_action` は `--show-current` のみを通す。実測（`probe_d7.py` セクション A）では、ブランチ削除形・生成形はいずれも `allow=False action=git-read-unsafe deny+1`。境界は保たれており計上もされるため実害は無いが、ref を変更する試行が「unsafe read」として監査記録に残る。設計は免除の分類根拠を理由コードに置いているため、コードの意味と実際の試行内容が乖離すると、後続で免除集合を拡張する判断を誤らせる。

**対応方針（案）**: I-DB-02 案 1 の分割時に、書込形と判定できるものは write 境界側の理由コードへ回す。

---

## I-DB-06 [minor] 設計本文が読み取りの確定根拠を workdir 束縛に帰しているが、実際に確定させている機構は別である

**根拠**

設計本文（§11 第一層、読み取り専用 git の項）は「workdir 束縛が読み取りをロック済み root 内に留めている」と記述し、`scope_gate.py:2911-2915` の注記も同旨。実測では:

- `status` は tail を一切検査しない（`probe_d7.py` セクション A。任意フラグ、上位参照 pathspec でも `allow=True`）。読み取りを worktree 内に留めているのは、seed 検証が `_validated_worktree_branches` でロック済み root が worktree の top-level であることを確認しており（部分ディレクトリを root にした seed は実測で `mutation-denied` に落ちる。`probe_d7b.py` セクション G）、そこから起動する git 自身の repository 探索が worktree を出ないためである。workdir 束縛は cwd を root に固定するだけで、それ単独では確定させない。
- 同じ locked 段で `read_file` / `search_files` はパス検査を一切受けない（`probe_d7b.py` セクション F。locked root 外の絶対パス・上位参照・ルート起点の検索がいずれも `allow=True action=inspect-locked-target`）。したがって「読み取りがロック済み root 内に留まる」という記述はクラス全体としては成り立たない。

読み取り無制限自体は今回の差分の外（基準点でも同じ）であり、機密境界の後退ではない。文書の根拠記述の正確性のみの問題である。

**対応方針（案）**: 確定機構を「seed 検証が root を worktree top-level に固定していること」と書き直し、クラスの読み取りが root 外にも及ぶ点は既存残余として明記する。

---

## I-DB-07 [minor] 否定側の閉集合テストが、語彙に存在しないツール名で構成されている

**根拠**

`test_tools_outside_the_work_record_catalogue_stay_denied` の 3 パラメタのうち 2 つは、語彙源 `_PROGRESS_TOOL_ACTIVITY_GROUPS` に存在しない名前である。語彙一致テストは `ARTIFACT_WORK_RECORD_TOOLS <= vocabulary` の一方向のみを固定するため、否定側は検査されない。カタログは語彙側の kanban 系 12 名すべてを含むので、実在する近傍ツールでの否定例は現状構成できない。これは「許可集合とツール語彙の乖離」（既知カテゴリ）の否定側での再発である。

**対応方針（案）**: 否定側は実在する非記録系（外部情報取得系・スキル定義系・永続状態系）のみで構成し、架空名は使わない。

---

## I-DB-08 [minor] 座礁時の記録手段の許可根拠が、ターン束縛を失った経路には適用されていない

**根拠**

作業記録系カテゴリを契約検証失敗段で許可した根拠は「座礁したターンが blocked として記録できないと INV-S6 の規範自体が実行不能になる」である。一方 `admit_without_turn`（`scope_gate.py:2340-2360`）は `ARTIFACT_READ_TOOLS` のみを許可し、作業記録系は `contract-unbound` で拒否する（実測: `probe_d7b.py` セクション H）。同じ根拠が当てはまる経路で扱いが分かれている。

fail-closed 側の不一致であり、安全側の判断としては妥当である。根拠の適用範囲を文書で明示するか、当該経路も同様に許可するかを決めておくのが望ましい。

---

## D-S3-8（lock 前段の既定値）について

差分は文書のみ（既定値・設定経路は無変更）。設計本文の記述は決定文と一致している。lock 前段の既定拒否が off のとき当該段の判定に到達しないことは基準点から不変であり、今回の許可拡張が既定 off の範囲を広げた形跡は無い（作業記録系の lock 前段許可は、有効化時の挙動にのみ効く）。反証事項なし。

---

## exit_check の判定

- **I-COM-01 残余: not-closed**。作業記録系カテゴリの新設で記録系ツールの一律拒否は解消し、承認 metadata の大半（head/base の SHA、changed files、ブランチ名）は admit 範囲内で取得可能になった。しかし原症状の後段（必須手順の拒否が拒否上限を枯渇させ、admit 範囲内の呼び出しと write scope 内の書込まで `deny-budget` になる）が、契約内に手段の無い残り 2 項（git-dir / common-dir 同一性）を含む読み取り経路で再現する（I-DB-02、実測表あり）。閉鎖には免除粒度の変更か admit 範囲の拡張が必要。
- **I-COM-06: not-closed**。構造面（読み取り専用 git の第一層追加、§10 artifact-change 版受入項目 15〜17 の別立て新設、強制状態 replay テスト 3 件、push の対象外明記）はいずれも実装済みで、既存項目 1〜14 は無改訂。ただし新設受入項目が必須手順より狭く書かれており、整合の対象が縮小されたフローになっている（I-DB-04）。「第一層の許可集合と §10 受入項目の整合」という本体要件は未達。
- **J-FID-01: not-closed**。計上規則は明示表として実装され、未分類は計上側・予算枯渇は無計上という原則は成立している。しかし免除の粒度が subcommand 名であるため両方向に誤りがある: 状態変更形を持つ subcommand が免除側に入り（I-DB-03）、worktree 内の純粋な読み取りが計上側に落ちる（I-DB-02）。台帳 7 節 3 が示した「当該拒否は境界外読み取りか書込形のいずれか」という二分は、第三の類型を落としている。
