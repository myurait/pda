# 自動統合ゲート設計の反証レビュー（2026-08-29）

- Status: review complete / findings recorded（批准前の反証記録）
- 対象: `docs/design/auto-integration-gate.md`（draft-for-owner-review、未コミット）
- レンズ: 迂回可能性（6軸A1-A6）／fail-openの穴／既存設計との矛盾（M2・M3・統治ADR・現行cycle）／運用成立性（agent-node資源・遅延・rollback安全性）／オーナー統制の閉性
- 照合した一次資料: `docs/roadmap/autonomous-improvement-goal.md`、`docs/roadmap/autonomous-improvement-operating-rules.md`、`docs/design/self-improvement-governance-adr.md`、`docs/design/improvement-orchestrator.md`、`docs/design/staged-verification.md`、`docs/status/m1-supervised-run-2026-08-29.md`、`docs/operations/pda-improvement-cycle.md`、`docs/operations/adversarial-suite.md`、および実装（`operations/improvement/scope_seed.py`、`operations/improvement/install.py`、`operations/improvement/c6_audit.py`、`integrations/hermes-pda-approvals/dashboard/plugin_api.py`、`integrations/hermes-scope-gate/scope_gate.py`、`infra/systemd/`、`schemas/`、`continuity/`）

## 表記について

対象文書は決定論ゲートを D1〜D7、統治ADRは判断を D1〜D5 と呼び、綴りが衝突している。本記録では前者を **ゲートD1**〜**ゲートD7**、後者を **ADR D1**〜**ADR D5** と書き分ける（この衝突自体を m1 として指摘する）。

## 件数

- blocker 11 件 / major 14 件 / minor 9 件（計 34 件）

## 脅威6軸に対する反証の到達点

- **A1 行動退行**: 迂回経路あり（B8）。プローブ対象面と統合で実際に変わる面が食い違う。
- **A2 テスト浸食**: 迂回経路あり（B3、M1）。ゲートD3の機械抽出はテストファイルの外を見ない。
- **A3 統治ドリフト**: 迂回経路あり（B2、B6、B9、M13）。Tier G の集合が実装に存在しない。
- **A4 自己増幅**: 迂回経路あり（B2、B9、M3、M13）。本設計・方針ファイル・検証契約スキーマが自動統合可能域にある。
- **A5 品質腐敗**: 部分的に迂回経路あり（B4、M13）。検証記録の出所が固定されていないため、品質判定の根拠が自己申告に戻る。
- **A6 資源暴走**: 迂回経路というより成立性の問題（M2、m9）。上限3件/日は起動回数の上限になっていない。

---

## blocker

### B1. ゲートD2のフルスイート実行に隔離が指定されておらず、worker著作コードを統合実行器の権限で走らせる

- 設計の主張: 4節ゲートD2「隔離worktreeでの focused test に加え、統合前に**フルスイート**を統合候補head上で実行する（agent-node直列・nice規律）」。3節「S2〜S4 は worker の書込権限外で動く（C3）」。
- 検証事実: `integrations/hermes-scope-gate/scope_gate.py:720-724` のコメントが「The process side effects of an admitted command are outside the first layer's write-boundary guarantee. The gate inspects arguments only. Namespace-isolated execution and static inspection of collection paths are fixed M2 requirements.」と明記する。`docs/operations/adversarial-suite.md` の第二層テスト群の項も「プロセス副作用は第一層の保証対象外であり、隔離実行と収集経路の静的検査は M2 の必須要件として未実装」と記録する。同種の指摘は `docs/status/restricted-s3-write-scope-review-2026-08-22.md:20` で既に確証済み（write_paths配下へ置いたテスト資産が、許可されたpytest呼び出し経由でプロセス全権限を得る）。本設計10節 Phase A は「M2実装を待たない」と明記する。
- 具体形: 統合候補headに含まれるテスト資産（宣言 `test_paths` 内の正規の成果物）は、フルスイート収集時に import 時点のトップレベルコードとして実行される。本設計はこの実行の隔離（名前空間分離・収集経路の静的検査・資格情報の遮断）を一切規定していないため、実装は既定で「統合実行器と同じユーザー・同じ環境」で走る。統合実行器は origin への push 権限と agent-node 同期権限を持つ必要があるため、テスト実行中の任意コードがゲート束の外で main へ直接 push でき、方針ファイル・統合ledger・検証記録の改変も同じ権限で可能になる。すなわちゲートD1〜D7とS3を全て通さずに統合が達成できる。
- 重大度理由: 単一の穴で6軸すべてが同時に破れる。かつ、既存の owner 承認モデルでは push 権限が人間側にあったため成立しなかった経路が、C5' によって初めて開く。

### B2. Tier G の集合が実装に存在せず、「宣言段で拒否済み（既存）」が事実に反する

- 設計の主張: 8節「**Tier G — 統治面**（既存の統治パス列挙 + 本設計 + 統合ledger + 方針ファイル）: 自動統合**恒久不可**。宣言段で拒否済み（既存）だが、D1で第3回検査を行う」。9節「ゲート実装・方針ファイル・統合ledger・検証者プロンプトは全て統治面（Tier G）に置き、workerの宣言可能域から恒久排除する（C3）」。
- 検証事実: 統治面の機械的正本は `GOVERNANCE_PATHS` であり、`operations/improvement/scope_seed.py:83-99`、`operations/improvement/install.py:307-323`、`integrations/hermes-pda-approvals/dashboard/plugin_api.py:62-79` の3実装が同一列挙を持ち、相互一致がテストで固定されている（`integrations/hermes-pda-approvals/tests/test_plugin_api.py` の `test_governance_path_lists_match_between_installer_and_plugin`）。この列挙に含まれないものとして、少なくとも次が確認できる: `docs/design/auto-integration-gate.md`（本設計）、`docs/design/improvement-orchestrator.md`、`docs/design/staged-verification.md`、`docs/operations/pda-improvement-cycle.md`、`docs/operations/worktree-lifecycle.md`、`docs/status/`配下、`personal_delegate_agent_plan.md`、`pda_minipc_setup_record.md`、`schemas/`配下（`verification-report-v1.schema.json`、`ai-invocation-audit-v1.schema.json` を含む）、`continuity/local-backup.json`、`src/pda/`配下、`operations/backup/`配下、`profiles/pda/skills/` のうち `pda-autonomous-improvement/` 以外（`task-scope-control/` 等）。「統合ledger」「方針ファイル」は本設計が新設するもので、文書内にパスの記載がないため列挙に追加する対象すら特定できない。
- 具体形: `schemas/verification-report-v1.schema.json` は ADR D2 判断層の契約そのもので、`profiles/pda/skills/pda-autonomous-improvement/SKILL.md:37` が worker へ必須添付として参照する。これは統治面列挙外であるため、宣言段（`scope_seed._reject_overbroad_scope`）でも承認段（`_is_governance_path`）でも拒否されない。Tier導出が機械可読な唯一の列挙（`GOVERNANCE_PATHS`）に基づく限り、このパスは Tier 0/1 に落ちて自動統合対象になる。検証契約の必須項目を緩めた版が S3 の単独検証と自動統合を通れば、以後の全カードの検証強度が下がる。同じことが本設計自身、方針ファイル（上限値・kill switch）、統合ledgerのスキーマについて成立する。
- 重大度理由: A4（自己増幅）の遮断が本設計の中核前提であり、その前提が「既存で成立している」という誤った事実認識の上に立っている。Phase A 初日から開く。

### B3. ゲートD3のテスト浸食抽出がテスト収集設定の変更を観測しない

- 設計の主張: 4節ゲートD3「テストファイルへ触れるdiffは (a) テスト数・assert数が減る変更、(b) skip/xfail の追加、(c) 既存テストの期待値変更、を機械抽出し、該当があれば推論ゲートS3へ…引き渡す」。
- 検証事実: 本リポジトリに pytest 設定ファイルは存在しない（`pytest.ini` / `pyproject.toml` / `setup.cfg` / `tox.ini` のいずれもリポジトリ直下に無い）。収集集合は実行時のカレントと引数だけで決まる。`conftest.py` はどの階層のものも `_is_governance_path` が basename で統治面と判定するため宣言・承認の両段で止まるが、収集設定ファイルにはこの扱いがない。
- 具体形: 収集設定を新規に置く変更は「テストファイルへ触れるdiff」に該当しないため、抽出3項の対象外となる。`testpaths` / `addopts` / `norecursedirs` の指定でゲートD2のフルスイートの収集範囲を縮められ、変更が壊すテストを収集対象から外したまま「フルスイート緑」を成立させられる。テストファイル側でも抽出3項を回さない形が残る: テスト関数名の非 `test_` 化（数・assert数・期待値のいずれも変わらず収集から消える）、`parametrize` の候補削減（assert文数は不変）、テストが読む非テスト資産（ヘルパ・fixtureモジュール）側の無効化。
- 重大度理由: ゲートD3はA2（テスト浸食）の唯一の機械的検知手段で、S3への論点引き渡しもD3の発火に条件づけられている。発火しなければ推論ゲート側にも論点が届かない。

### B4. S3検証記録の出所が未規定で、現行実装ではworkerが自作できる

- 設計の主張: 5節「出力は verdict スキーマ（accept / refute、根拠、確認した受入条件、D3から引き渡された論点への回答）で、承認metadataの independent_verification 欄（M1で必須化済み）を埋める」。
- 検証事実: `integrations/hermes-pda-approvals/dashboard/plugin_api.py:350-381` の検査は、`verifier` と `implementer` の文字列不一致、`verdict == "pass"`、`verified_head_sha == head_sha`、`checks` が非空リスト、のみである。同箇所のコメントが自ら「until the M2 verifier stage exists, these are self-declared labels checked for internal consistency … they do not yet prove a separate principal ran the verification」と限界を明記し、`profiles/pda/skills/pda-autonomous-improvement/SKILL.md:37` も同旨を記す。承認metadata（`pda_approval`）は worker が組み立てる客体である（`docs/operations/pda-improvement-cycle.md` Phase 1）。
- 具体形: 本設計は S3 の verdict が「誰によって metadata へ書き込まれるか」を規定せず、worker 申告欄を統合実行器が排他的に上書きする（または worker 申告があれば拒否する）とも書いていない。現行実装のまま C5' を適用すると、worker が実在しない検証者名を置いた `independent_verification` を自作し、ラベル整合検査を通過して自動統合まで到達できる。ADR D2 の「AI検証者の合格は digest 承認に代替しない」という限界宣言は、digest 承認が残っていることを前提に成立していた安全余裕であり、C5' はその余裕だけを取り除く。
- 重大度理由: S3 は本設計が新設する唯一の意味的ゲートで、Tier 0 では単独、しかもゲートD3の論点処理の受け皿でもある。出所が固定されないかぎりゲート群は決定論層だけに縮退する。

### B5. S3合格headとS4統合headの束縛が無く、検証後の差し替え窓が開く

- 設計の主張: 3節「S1 worker完了合図 → 検証要求へ遷移」→ S2 → S3 → 6節「各統合は『現mainへrebase → D4/D2短縮版 → merge --no-ff → origin push → agent-node ff同期』を1トランザクションとして実行」。
- 検証事実: rebase後に再走するのはゲートD4とゲートD2短縮版（変更影響スイート＋smoke）だけで、ゲートD1（スコープ再検証）・ゲートD3（テスト浸食抽出）・S3（検証者）の再走は規定がない。branch と worktree はS3〜S4の間も存在し、`docs/status/m1-supervised-run-2026-08-29.md` 1節・4節課題2は、完了合図が失われた後に dispatcher が**同一worktreeへ第2 workerセッションを起動した**ことを実測として記録している。検証契約側の `verified_head_sha` は metadata の `head_sha` と一致すればよく、統合時点の branch 先端との一致を強制する経路はない。
- 具体形: S3 が head H1 を accept した後、同一 worktree で稼働中の（あるいは無統制再試行で起動した）セッションが H2 をコミットする。S4 は branch 先端を rebase して merge するため H2 が main に入る。H2 に対しては D1・D3・S3 が一度も走っていない。日次上限3件/日でキューに滞留したカードでは、この窓が数時間から翌日まで開く（S3 verdict の有効期限も未定義）。
- 重大度理由: 既存の owner 承認経路は digest 束縛と activation 時の `head_sha` 再照合でこの窓を閉じていた。本設計はその機構を外したうえで代替の head 固定を定義していない。

### B6. 割当時baseに正本が無く、ゲートD1・ゲートD3・Tier導出の観測範囲をworkerが狭められる

- 設計の主張: 4節ゲートD1「統合候補diffが割当時契約（seed由来のwrite_paths/test_paths）の内側であることを、統合時点のheadで再照合する」。ゲートD4「統合候補branchが割当時baseからの単一系譜であること」。8節「階層は**diffの実パス集合から決定論的に導出**する」。
- 検証事実: 割当時に記録される契約seedの payload は write_paths / test_paths / execution / git_write のみで、base コミットは含まれない（`operations/improvement/scope_seed.py` の `derive_seed_payload` / `record_seed`）。承認ゲート側の diff は worker 申告の `base_sha` を起点に取り、検査は「`base_sha` が `head_sha` の祖先であること」と「`changed_files` が `git diff --no-renames --name-only base head` と完全一致すること」である（`integrations/hermes-pda-approvals/dashboard/plugin_api.py:493-527`）。すなわち「割当時base」という値はどこにも保存されておらず、ゲートD4の主張には照合先が存在しない。
- 具体形: worker が branch 上に複数コミットを積み、最後のコミットの親を `base_sha` として申告すると、祖先性検査は通り、diff は最終コミット分だけになる。ゲートD1のスコープ再照合・ゲートD3のテスト浸食抽出・Tier導出はいずれもこの diff を入力にするため、それ以前のコミットに含まれる統治面変更・テスト削除は3者すべてから不可視になる。一方 S4 の `merge --no-ff` は branch 全体を取り込むため、観測されなかった変更が main に入る。diff 範囲と merge 範囲の乖離が、そのまま検査範囲と反映範囲の乖離になる。
- 重大度理由: B2 と合成すると、統治面の変更を隠したまま自動統合を通す完全な経路になる。単独でもゲートD1・D3・Tier導出の3機構を同時に空振りさせる。

### B7. ADR D1 と運用細則に正面から衝突する変更を「一切緩和しない」と記述している

- 設計の主張: 5行目「統治ADR（`docs/design/self-improvement-governance-adr.md`）D1のオーナー固定判断は一切緩和しない」。1節 C5'「main統合は…全通過した変更に限り自動で行う」。12節「統治ADR: D1の固定判断一覧に『本設計・統合ledger・方針ファイルの変更』を明示追加」。
- 検証事実: ADR D1 は「オーナーにのみ許される判断（自動化禁止・self-improvement の対象外）」の第1項として「最終反映の承認（digest 束縛。main統合・push・デプロイ・restart・外部送信の解錠）」を挙げる（`docs/design/self-improvement-governance-adr.md:26`）。同ADRは approved 状態で、D1境界の変更は「本 ADR の改訂（＝オーナー承認）に固定する」と自ら規定する（同:13）。`docs/roadmap/autonomous-improvement-operating-rules.md:4` も「ADR D1 の『オーナー固定判断』（統治変更・再有効化・秘密・課金・**外部公開**・不可逆削除）は一切緩和しない」と宣言する。origin は GitHub リモートであり、push は外部公開・外部送信に当たる。
- 具体形: 本設計は ADR D1 第1項の中核（main統合・push の自動化禁止）をまさに反転させながら、12節では「固定判断一覧への項目追加」しか予定していない。必要な改訂（ADR D1 第1項の書き換え、goal 文書 C5 の C5' への改定、運用細則4行目の整合）が改訂対象として特定されていないため、批准後も統治正本と実装方針が矛盾したまま並存する。オーナーが承認する対象が「本設計」だけであれば、ADR D1 は改訂されないまま自動 push が動くことになる。
- 重大度理由: 統治正本と衝突する自動化を「衝突しない」と記述した状態で批准を求めており、批准の意味が確定しない。C4（自己正当化による無効化の禁止）が問題にするのはまさにこの形である。

### B8. 観測窓とプローブ対象が、統合によって実際に変わる面と食い違っている

- 設計の主張: 7節「統合後、D7プローブ束を T=30分 後に再実行し、テレメトリ（error rate・表示レート・run失敗率）を比較する。閾値超過で**自動rollback**」。4節ゲートD7の束は「gateway health・kanban CRUD・dashboard応答・進捗表示の表示レート上限」。8節 Tier 2「mergeまで自動可、**デプロイ・restartはオーナー承認**」。
- 検証事実: ゲートD7が観測する面（gateway・dashboard・進捗表示）は、merge と agent-node ff同期だけでは挙動が変わらない。これらは installer によって配備される資産で、Tier 2 の反映（デプロイ・restart）はオーナー承認後の正常化窓に置かれる。b11e01c の行動回帰も承認後の本番反映で発現した（`docs/roadmap/autonomous-improvement-goal.md:42`）。逆に、merge + ff同期だけで挙動が変わる面は存在する（B9）が、そこはプローブ束に入っていない。M3設計は観測窓を「runtime へ影響する finalization（restart 系・関数再インストール等）」に紐づけている（`docs/design/staged-verification.md:17`）。
- 具体形: Tier 0/1 の統合後30分のプローブは、統合とは因果のない変動を測る。閾値超過が起きれば無関係なカードが自動 revert され（誤rollback）、逆に統合起因の退行は反映時（数時間〜数日後、オーナー承認済みデプロイ時）に初めて現れるが、そのときすでに観測窓は閉じている。A1に対する主防御が、A1を引き起こす事象に接続していない。
- 重大度理由: 本設計がA1の恒久対策として提示する唯一の反映後機構であり、接続先が誤っているため機能しない。M3設計との定義衝突も同時に生じる。

### B9. live systemd unit が checkout から直接実行する面が、統治列挙外かつTier表に置き場が無い

- 設計の主張: 8節 Tier 1「非常駐コード（テスト・ツーリング・runtime未接続のintegrations）: 自動統合可」、Tier 2「常駐接続コード（稼働gateway/dashboardが読み込む面）: mergeまで自動可、デプロイ・restartはオーナー承認」。
- 検証事実: `infra/systemd/pda-local-backup.service:12` の ExecStart は `/usr/bin/sg docker -c '%h/.hermes/hermes-agent/venv/bin/python %h/projects/pda/operations/backup/pda_backup.py run --config %h/.config/pda/local-backup.json'` であり、**checkout 内のファイルを直接実行する**（配備コピー・再起動の介在がない。`TimeoutStartSec=18h`、docker グループ権限つき）。`operations/backup/` と `src/pda/backup/`、`continuity/local-backup.json` はいずれも `GOVERNANCE_PATHS` に含まれない。goal 文書 C3 は「ゲートpolicy・承認ledger・監査log・**バックアップ**はworker/coreの書込権限外に置く」と定める（`docs/roadmap/autonomous-improvement-goal.md:121`）。
- 具体形: `operations/backup/*.py` を宣言スコープに持つカードは宣言段で拒否されない。Tier表には「gateway/dashboard が読み込む面」でも「runtime未接続」でもないこの面の置き場がなく、素直に読めば Tier 1（非常駐コード）に落ちて自動統合可・日中窓・D7必須となる。統合と ff同期の直後、次回のバックアップ timer 発火時に worker 著作コードが docker グループ権限・18時間タイムアウトで実行される。オーナー承認もrestart判断も介在せず、ゲートD7の束（gateway/dashboard/表示レート）はこの面を一切観測しない。バックアップと復元経路が対象であるため C3 と C4（復元手段を自己正当化で無効化できないこと）に直接触れる。
- 重大度理由: 「mergeは自動・デプロイはオーナー承認」という本設計の安全分割が、この面では成立しない（merge + ff同期がそのまま実行到達になる）。分割の前提が誤っている面が現に存在する。

### B10. 注入演習が実レーン・実mainで行われる設計で、失敗が実害になる

- 設計の主張: 7節「Tier 1 へ拡大する前に、意図的な退行（プローブが検知すべき挙動変化）を仕込んだカードを流し、S2/S3/S5のいずれかが機械的に止めることを実証する」。10節 Phase A exit「注入演習1件（scope外diff・テスト弱体化・統治面接触の3種いずれか）が止まる」。
- 検証事実: M3設計は演習の条件として「演習は本番 surface・本番台帳に触れない専用資産で行い、演習であることをカードに明示する」を明記する（`docs/design/staged-verification.md:32`）。本設計は演習の実行環境について何も規定せず、実カードを実レーンへ流す形として書かれている。
- 具体形: 演習の目的は「止まること」の実証だが、止まらなかった場合の帰結は「意図的に仕込んだ退行が main へ自動統合される」ことである。Phase A の exit gate がこの実験の成功に依存しているため、実験は必ず実行され、失敗時のコストは実害として現れる。dry-run 統合器（merge先をshadow branchにする、push を伴わない）や演習専用 surface の指定がない。
- 重大度理由: 安全性の実証手段そのものが、未実証の安全機構に依存している。M3が明示的に禁じた形をとっている。

### B11. 統合実行器の相互排他が未設計で、tick再入により並行統合が起こり得る

- 設計の主張: 6節「**直列キュー**: 統合は常に1件ずつ」。10節 Phase A「30分tick統合（イベント駆動はM2で置換）」。
- 検証事実: 「直列」を保証する機構（ロック・リース・単一実行の保証）は文書内で定義されていない。ゲートD2はフルスイート、ゲートD4後に短縮版、ゲートD7でプローブ、S3で検証者起動を伴う。`docs/roadmap/autonomous-improvement-operating-rules.md:22-23` は agent-node のフルスイートを直列・nice付きで走らせることを求め、同ホストは12GiB・OOM実証済みと記録する。1回の統合が30分を超えることは十分あり得る。M2のオーケストレーター設計にある `host_guard`（`docs/design/improvement-orchestrator.md`）は Phase A では存在しない。
- 具体形: 前回tickの統合が完了する前に次のtickが起動すると、2つの実行器が同時に rebase・merge・push を行う。片方の push が他方の rebase 前提を無効化し、統合ledgerの記録順序と Git の実順序が食い違う。両者が同一branchを扱った場合は二重mergeになり、別branchでも「現mainへrebase」の前提が実行中に動く。
- 重大度理由: 直列性は6節の並走衝突処理・7節の日次上限・9節の方針二重確認がすべて前提にしている性質で、その保証機構が存在しない。

---

## major

### M1. 「フルスイート」の集合が定義できず、インフラ起因の終了と成功の区別も規定されていない

- 設計の主張: 4節ゲートD2「フルスイートを統合候補head上で実行する…失敗1件でも不通過」。
- 検証事実: (a) リポジトリに pytest 設定ファイルがないため収集集合は実行時の引数依存であり、`.gitignore` が `tmp/` を無視対象に挙げていることからも分かるとおり、リポジトリ直下には未追跡のディレクトリが置かれる運用がある（未追跡内容はGit正本に含まれないのに収集対象へ入る）。(b) `docs/status/restricted-s3-impl-fix-2026-08-23-disposition.md` 15節・16節の実行結果は `integrations/hermes-scope-gate/tests`（`test_hermes_integration.py` **除く**）598 passed と記録し、`operations/improvement/tests` と `integrations/hermes-pda-approvals/tests` は開発PCでは `hermes_cli` / `fastapi` 不在で実行不能と記録する。すなわち現に運用されている「フルスイート」には固定的な除外とホスト依存がある。(c) `docs/roadmap/autonomous-improvement-goal.md:156` は「フルスイート比較（patched 236失敗 = baseline 236失敗、patched固有の失敗0件）」というベースライン比較を先例として記録する。
- 具体形: 判定入力の集合が再現不能であるため、「失敗1件でも不通過」は文字どおりには実装できず、実務は先例どおりベースライン比較（差分のみを見る）になる。ベースライン比較は、既に失敗していたテストを別要因で壊す変更を不可視にする fail-open である。加えて、OOM kill・収集エラー・依存不足でプロセスが落ちた場合、終了コードとパース済み結果件数の**両方**を必須にしなければ「失敗0件」と区別できない。本設計はこの区別を規定していない。
- 重大度理由: ゲートD2はA1・A2両方の主防御として置かれており、その入力集合と判定規則が未定義。

### M2. 資源規律（agent-node 12GiB・OOM実証済み）と正面から衝突する

- 設計の主張: 7節「日次上限: 自動統合は当初 3件/日」。4節ゲートD2（統合毎フルスイート）、ゲートD4（rebase後に短縮版）、ゲートD7（プローブ束）、5節（Tier 1以上は3レンズ並列検証）。
- 検証事実: `docs/roadmap/autonomous-improvement-operating-rules.md:22-23`（active、統治面ファイル）が「agent-node 上のフルスイートは常に**直列・nice付き**で実行し、変更をバッチして gate 直前に原則1回にまとめる。実行前に `free -h` を確認する」「並列化してよいのは開発PC側の分析エージェントのみ（agent-node は 12GiB・OOM 実証済み。2026-08-22）」と定める。
- 具体形: 統合毎のフルスイートは「gate 直前に原則1回」の反対である。1日3件なら最低3回、rebase衝突・キュー再投入でさらに増える。Phase B の3レンズ並列反証は agent-node 上のAI起動並列化に当たり得る。`host_guard` は M2 資産で Phase A/B には存在しない。運用細則は統治面ファイルであり、本設計の批准だけでは改定されない。
- 重大度理由: 成立性そのものが疑わしいうえ、active な運用細則と矛盾したまま実装フェーズへ入ることになる。

### M3. 統合ledgerの配置が ADR D3 の既知の未達と矛盾し、C3準拠の主張が成立しない

- 設計の主張: 6節「同内容を統合ledger（worker書込権限外、承認ledgerと同居）へatomicに記録する」。9節「統合ledger…は全て統治面（Tier G）に置き、workerの宣言可能域から恒久排除する（C3）」。
- 検証事実: ADR D3 は「承認 ledger（`pda_owner_approvals`）は現在 Kanban DB 内にあり、DB に書ける主体からは物理的に隔離されていない…『worker の書込権限外への物理配置』…は未達である」と明記し、物理分離を identity 計画へ後回しにする決定を記録している（`docs/design/self-improvement-governance-adr.md:52`、確定済みオーナー決定4）。
- 具体形: 「承認ledgerと同居」＝Kanban DB 内であり、ADR自身が物理隔離未達と認めている場所である。C3準拠を主張しているが、C3が要求する性質は満たされない。しかも C5' により、オーナーのdigest承認という人間側の照合点が消えるため、ledgerの改竄検知はledger自身と Git の突き合わせに依存する。X6（盤面・Git・ledgerの3面から再構成）はこの前提に乗る。
- 重大度理由: 監査の最終根拠の配置に関する主張が、統治正本の既知の未達を追認せずに書かれている。

### M4. 統合トランザクションが原子でなく、どの main が正本かも規定されていない

- 設計の主張: 6節「『現mainへrebase → D4/D2短縮版 → merge --no-ff → origin push → agent-node ff同期』を1トランザクションとして実行し、途中失敗はbranchを無傷のままキューへ戻す（2回失敗でオーナーへ落とす）」。
- 検証事実: `docs/roadmap/autonomous-improvement-operating-rules.md:32` は再開時の ground truth として「origin / agent-node の HEAD、ライブ Hermes の HEAD、盤面、承認 ledger」を**別個に**列挙する。すなわち origin と agent-node の HEAD は一致が保証されない別の事実として扱われている。本設計は「現main」がどちらを指すかを規定していない。
- 具体形: push 成功後に ff同期が失敗した場合、branch は既に origin/main に入っているのに「途中失敗」として扱われ、キュー再投入で二重mergeを試みる。逆に agent-node 側が origin より進んでいれば ff同期は原理的に失敗し、force は本設計が禁じているため、統合済みの main と稼働checkoutが恒久的に乖離する（ledger上は統合済み、稼働系は旧コード）。「2回失敗でオーナーへ落とす」は失敗の段階を区別しないため、オーナーに届く情報も状態を特定できない。
- 重大度理由: 部分成功と失敗の区別がないまま自動リトライを設計しており、Git履歴と稼働系の整合が壊れる経路が複数ある。

### M5. kill switch の伝播経路が未定義で、9節の停止根拠が10節と矛盾する

- 設計の主張: 9節「**kill switch**: オーナーが方針ファイルの `auto_integration.enabled` を false でコミットすると、次の統合から全停止する（既存のサイクル停止と独立）。緊急時はrouterのtimer停止でも止まる（統合はカード完了イベント起点のため）」。
- 検証事実: 方針ファイルのパスが文書内に無い（既存の `continuity/autonomous-improvement.json` を使うのか新設するのかも書かれていない）。既存の停止機構は committed policy を router が二重確認する形で、その正本は `continuity/autonomous-improvement.json`（統治面）である。10節 Phase A は「30分tick統合（イベント駆動はM2で置換）」であり、統合はカード完了イベント起点ではない。
- 具体形: (a) 方針ファイルのパスが未指定のため、実装が統治面列挙外のファイルを新設すれば kill switch 面そのものが自動統合可能域に入る（B2と同型）。(b) オーナーのコミットが実行ホストの checkout に届く手順（fetch/pull）が規定されていない。origin と agent-node の HEAD が別事実として扱われる運用（M4）では、オーナーが origin 側へコミットしても実行器が読む「コミット済み版」に反映される保証がない。(c) Phase A で統合が router timer とは別の起動経路を持つなら、「routerのtimer停止でも止まる」は成立しない。文書自身の記述が矛盾している。
- 重大度理由: オーナー統制の最終手段の到達性が保証されていない。

### M6. M2設計原則 P1・P3 と衝突する

- 設計の主張: 6節（S4統合執行器の直列キュー）、10節 Phase A（30分tick統合）、6節（統合ledgerの新設）。
- 検証事実: `docs/design/improvement-orchestrator.md` の P1「**二つ目の dispatcher を作らない。**」、P3「**状態の正本は Kanban DB と Git のみ。** オーケストレーター固有の永続状態を増やさない。増やす場合は再構築可能なキャッシュに限る」。
- 具体形: S4は独自の周期起動・独自のキュー・独自の永続記録（統合ledger、日次上限のカウンタ、キュー滞留状態）を持つ。M2はループ全体の状態機械を単一のオーケストレーターが所有する前提で、その実装カード（t_9174eb5d）はM1 exitの停止ゲート下にある。Phase Aが先にこれを作ると、M2は稼働中の第2 dispatcher を後から置換することになる。
- 重大度理由: M2の設計原則を破る資産をM2着手前に本番へ入れる順序になっており、後続の統合コストと二重定義が構造的に残る。

### M7. 分類語彙が四重化し、Tier と既存 risk_class の写像が無い

- 設計の主張: 8節 Tier 0/1/2/G を「diffの実パス集合から決定論的に導出」。
- 検証事実: 既存の強制済み語彙として、承認metadataの `risk_class`（`local-reversible` / `service-restart` / `external-visible` / `security-sensitive`、`integrations/hermes-pda-approvals/dashboard/plugin_api.py:47-52`）、admission の分類クラス（bounded-operation / artifact-change / repository-closeout）がある。M3設計は観測窓の長さを **risk_class に応じて** 定める（`docs/design/staged-verification.md:17`）。
- 具体形: Tier は5つ目の分類軸として導入されるが、`risk_class` との写像が定義されていない。M3が risk_class で決める観測窓と、本設計が Tier で決める観測窓・検証深度・統合窓が並存し、同一変更に2つの答えが出る。`finalization.kind`（merge-only / merge-and-restart 等）との関係も未定義。
- 重大度理由: 実装が語彙を選ぶ余地を残し、どちらを選んでも他方の設計文書と食い違う。

### M8. rollback契約が二重定義で、revert後の再統合がGit意味論上成立しない

- 設計の主張: 7節「**自動rollback**: merge commit の revert のみ（force push・履歴書換・他統合の巻き添えは行わない）。rollback発生時はカードを blocked へ戻し、ポストモーテムカードを自動起票する」。
- 検証事実: 承認metadataは `finalization.rollback` を非空文字列リストとして必須にする（`integrations/hermes-pda-approvals/dashboard/plugin_api.py:383-392`）。M3設計は「finalization contract は rollback 手順を事前宣言済み（既存契約）であることを前提に、観測窓内の異常検知で宣言済み rollback を自動実行してよい範囲をオーナーが承認する」と定める（`docs/design/staged-verification.md:20`）。本リポジトリには前進のみのスキーマ変更の前例がある（`integrations/hermes-scope-gate/scope_gate.py` の `ALTER TABLE decisions ADD COLUMN execution_status`、承認ledgerの `CREATE TABLE IF NOT EXISTS`）。
- 具体形: (a) 宣言済み rollback 手順（metadata必須項目）と「merge revert のみ」のどちらが正本か未規定。(b) merge commit を revert した後、同一branchを修正して再merge しても、Git は既にマージ済みの変更を再適用しないため、rollback → blocked → 再実装 → 再統合というループが成立しない（revert の revert か、branch の作り直しが必要）。この扱いが書かれていない。(c) ファイル形式・スキーマ・ディスク上の生成物のように前進のみの状態変化を伴う変更では、コードの revert が状態を戻さない。down 手順の要求がない。
- 重大度理由: 自動rollbackは Phase C の中心機構で、実行後の復帰経路が定義されていない。

### M9. S3検証者の「読取専用」を保証する機構が無い

- 設計の主張: 5節「実装workerと異なるprofile/モデルで起動し、対象worktreeへは読取専用でアクセスする。検証者はKanbanのライフサイクル操作権限を持たない」。
- 検証事実: 同一ホスト・同一ユーザーで動くAIセッションに対する「読取専用」の強制機構は存在しない。スコープゲートは契約seedを持つタスクに対して write を拒否する形で働き、検証者向けの読取専用契約は定義されていない。プロンプト規律版の保護が強制力でないことは2026-08-22に実証済み（`docs/design/self-improvement-governance-adr.md:7`、goal 2.2）。terminal遷移のclaim束縛はライフサイクル操作を止めるが、ファイル書込は止めない。実行主体は11節 Open Question 3 で未決のまま Phase A が依存する。
- 重大度理由: 新しい信頼の起点（S3）の隔離性が、既に反証済みの手段に依存している。

### M10. Phase A の entry 条件が未成立

- 設計の主張: 10節「**Phase A（本設計承認後すぐ、M2実装を待たない）**」。11節 Open Question 1「Phase A は M2 の停止ゲート（M1 exit）と独立に着手してよいか（Decision案: 着手可）」。
- 検証事実: `docs/status/m1-supervised-run-2026-08-29.md` は5節で「t_e2364a83 の成果の扱い」をオーナー判断待ちとして残し、M1の正式完了記録カード（t_8aa3fd90）は未完である。同4節の実測課題1（tool budget座礁で完了合図が失われる）、課題2（無統制の自動再試行が同一worktreeへ第2セッションを起動）、課題3（独立検証者ステージ未配線）は未解決で、いずれもK10（M2）への入力とされている。
- 具体形: Phase A の S1 は課題1の解決（budget座礁のhandoff）を前提にするが、本設計は方式を Open Question 2 として実装フェーズへ送る。S3 は課題3が解決されていることを前提にするが、検証者の実行主体は Open Question 3 で未決。S4のTOCTOU（B5）は課題2が未解決であることに直接依存する。すなわち Phase A の前提3件がすべて未決のまま「承認後すぐ」着手する構成になっている。
- 重大度理由: 着手可否がオーナー判断事項として提示されているが、判断に必要な前提の未成立が文書に明示されていない。

### M11. ゲートD7プローブの後始末・分離契約が無い

- 設計の主張: 4節ゲートD7「最小プローブ束（gateway health・kanban CRUD・dashboard応答・進捗表示の表示レート上限）を統合前にshadow実行する」。7節「統合後、D7プローブ束を T=30分 後に再実行し…」。
- 検証事実: M3設計は回帰資産の宣言項目として「対象 surface、実行コマンド、消費クレジットの目安、**後始末契約（valve 復元・外部通知抑止）**」を要求する（`docs/design/staged-verification.md:11`）。goal 9節も live probe 実行の条件として「valve復元とntfy抑止を義務とする」と定める（`docs/roadmap/autonomous-improvement-goal.md:192`）。C7は試験が本番状態に接触しないことを要求する。
- 具体形: 「kanban CRUD」プローブは本番盤面への書込を含み得る（C7・混入インシデントの再来）。「進捗表示の表示レート」プローブは valve 操作と外部通知を伴い得る。プローブが途中で失敗した場合の残留状態（valve が復元されない、合成カードが残る）と、次回判定がその残留を読むことによる汚染に契約がない。
- 重大度理由: 既存の運用義務が本設計の新規プローブ経路に引き継がれておらず、過去のインシデント類型（試験の本番接触）に接続する。

### M12. 完了合図のbudget外恒久許可案が、固定済みの迂回クラスを再開する

- 設計の主張: 6節「(a) 完了合図1回はbudget外で常に許可する（冪等・1回限り）、または (b) 次ターンが前ターンの完了状態を機械的に回収する再開契約、のいずれかを実装する。方式は実装フェーズで…決定する」。
- 検証事実: `docs/operations/adversarial-suite.md` は「拒否上限の計上規則を使った座礁と免除の悪用（…非計上経路を無償の無制限探索に使う fail-open 側）」を固定済み迂回クラスとして列挙し、`test_uncounted_denials_stay_bounded_by_the_class_budget` / `test_an_uncounted_denial_lane_is_closed_by_the_tool_budget` を挙げる。また「統治シグナルの汚染（契約が検証できていないターンから run 終端シグナルを発信する）」「引数無検査カテゴリへの宛先の持ち込み」も固定済みクラスである。ADR D5 は「統治の変更を伴うリリースは、次の迂回試行がすべて遮断されることを回帰スイートで証明してから review に載せる」と要求する。
- 具体形: 案(a)は budget/計上の外側に恒久的な許可レーンを作るもので、既に「非計上レーンは class budget と tool budget で閉じる」という形で閉じられた性質を再び開く。run終端シグナル系ツールは引数を運ぶため、免除レーンの引数検査が甘ければ宛先持ち込みの経路になる。本設計は方式選定を実装フェーズへ委ねる一方、D5の適用（本設計の実装が統治変更に当たること、迂回テストの追加が前提であること）をどこにも書いていない。
- 重大度理由: 既に閉じた迂回クラスを再開し得る変更を、迂回テストの要求なしに実装フェーズへ委ねている。

### M13. docs/status/ を Tier 0 に置くと監査記録自体が自動書換え可能になる

- 設計の主張: 8節「**Tier 0 — 記録・文書**（`docs/status/` 等、統治面を除くdocs）: 自動統合可。単独検証者、D7省略可、常時窓」。
- 検証事実: `docs/status/` には走行評価（`m1-supervised-run-2026-08-29.md`）、反証レビュー記録（`restricted-s3-*` 群）、処置記録、ポストモーテムが集約されており、goal 文書・カード・ADR がこれらを根拠として参照する。X6（盤面から再構成）・X7（ポストモーテムの資産化）の証拠基盤でもある。これらは `GOVERNANCE_PATHS` に含まれない。
- 具体形: Tier 0 は単独検証者・D7省略・常時窓（深夜も可）である。既存ファイルの改変と新規追加が区別されていないため、過去の欠陥記録・課題記録・反証記録から不都合な項目を削る変更が、オーナーの目に触れないまま自動統合され得る。統治面変更の検知はパス列挙に依存しており、記録の内容改変は検知対象にならない。
- 重大度理由: 監査可能性を担保する記録そのものが最弱の階層に置かれている。A3/A4の実効的な経路になる。

### M14. Tier表がパス完全でなく、未分類パスの既定が無い

- 設計の主張: 8節「階層は**diffの実パス集合から決定論的に導出**する…複数階層に跨るdiffは最も厳しい側へ丸める」。
- 検証事実: 4階層の定義文（記録・文書／非常駐コード／常駐接続コード／統治面）はいずれも意味カテゴリで、パス列挙を伴わない。少なくとも次の面に置き場がない: `schemas/`、`profiles/pda/skills/`（`pda-autonomous-improvement/` 以外）、`personal_delegate_agent_plan.md`、`pda_minipc_setup_record.md`、`docs/operations/`、`docs/design/`（ADRとS3設計以外）、`src/`、`operations/backup/`（B9）、`continuity/local-backup.json`。
- 具体形: 「最も厳しい側へ丸める」は分類済みパスにしか適用できない。未分類パスに対する既定（fail-closed でオーナーへ落とす）が書かれていないため、実装は「docsに見えるものは Tier 0、コードに見えるものは Tier 1」といった推測分類を行う。`personal_delegate_agent_plan.md` はADRが「根拠となる規範」として引用する構想書だが、統治面列挙外かつ Tier 表外である。
- 重大度理由: Tier がすべてのゲート強度・窓・検証深度を決める入力であり、その全域性が担保されていない。

---

## minor

### m1. ゲートD1〜D7 と ADR D1〜D5 が同一文書内で綴りを共有している

5行目は ADR D1、4節は ゲートD1 を指し、5節の「D3から引き渡された論点」は ゲートD3、`docs/design/self-improvement-governance-adr.md` の D3 は別物である。実装仕様として参照が壊れる。ゲート側の識別子を別系統（G1〜G7 等）にする。

### m2. 5節の事実帰属が実測記録と一致しない

5節は「M1実測で確証した『review専用delegateの完了強行』」と書くが、当該事象は2026-08-22の初回実運転（`docs/roadmap/autonomous-improvement-goal.md:44`）であり、2026-08-29のM1実運転で確証されたのは別の3件（budget座礁・無統制再試行・検証者未配線）である（`docs/status/m1-supervised-run-2026-08-29.md` 4節）。

### m3. Tier 1 の統合窓と観測窓の時刻が整合しない

7節は Tier 1 の統合窓を 07:00-22:00 JST（オーナーが観測可能な時間帯）とし、観測窓を T=30分後とする。21:31以降の統合では観測窓と自動rollbackがオーナー観測時間帯の外へ出る。窓の定義が統合時刻のみで、観測完了時刻を含んでいない。

### m4. C6監査イベントの発行主体が Phase A に存在しない

5節は「検証者の出力は承認metadataとして消費されるため、制限対象の『参照されない起動』に当たらない」とする。この判断自体は `operations/improvement/c6_audit.py` の契約と整合する（検証・レビュー起動は制限対象外）。ただし同モジュールの docstring は監査イベントの発行主体を「the emitting orchestrator (M2)」と明記しており、M2を待たない Phase A では S3 起動の監査イベントを残す経路がない。C6適合が検証可能な形にならない。

### m5. ゲートD6（秘密・資格情報スキャン）の資産と定義が未指定

決定論パターンの正本、`.env`系の判定規則、既存資産の有無に言及がない。新規実装依存の項目として実装フェーズの作業量が見積もれない。

### m6. finalization契約とS4固定トランザクションのどちらが正本か未規定

承認metadataは `finalization.kind` / `targets` / `steps` / `rollback` を必須で持つ（非空必須）。S4は固定の手順列を実行する。worker宣言の手順が装飾になるのか、S4がそれを読むのかが書かれていない。

### m7. オーナーへ落とす経路に総量上限が無い

「2回失敗でオーナーへ落とす」「3回rebaseしても衝突が解けない」「レンズ間で結論が割れた場合」「規模上限超過」がすべてオーナーキューへ流れる。日次上限3件/日と組み合わせると、自動化の目的（オーナー関与の削減）と逆にオーナー処理量が単調増加し得る。この量の見積りと上限がない。

### m8. 12節が、オーナーのみが書ける面の改訂を実装フェーズへ割り当てている

12節は goal 文書のC5改定、統治ADRのD1追記、`docs/roadmap/` の運用文書更新を「実装フェーズで反映」とする。これらはすべて `GOVERNANCE_PATHS` に含まれ、オーナーがコミットする面である。実装フェーズの主体は書き込めない。オーナー作業として分離して提示する必要がある。

### m9. S3検証者の起動回数に上限が無い（A6）

完了合図ごとに検証者が起動し、Tier 1以上は3レンズで3起動、rollback後の再実装で再度起動する。統合の日次上限3件は起動回数の上限になっていない。A6（資源暴走）に対する上限が統合回数側にしか置かれていない。

---

## 反証で経路を見つけられなかった点

- 9節の「統合執行器は方針ファイルの**コミット済み版**を二重確認する」は、既存のルーターにおける同型の機構（runtime config 改竄では起動できないことを敵対テストで固定済み、`operations/improvement/tests/test_pda_improvement_cycle.py::test_tampered_runtime_config_cannot_outrank_committed_policy`）と整合しており、runtime複製の改竄による起動という経路は見つからなかった。ただし伝播経路（M5）と方針ファイルの所在（B2）は別問題として残る。
- 2節A3の「rename によるdiff隠蔽はM1レビューで確証・修正済み」は事実として確認できた（承認ゲートの diff は `--no-renames` で取得され、`changed_files` との完全一致を要求する）。
- 8節「階層は…workerの申告やカードの自己分類を使わない」という原則そのものは、既存の `risk_class` が worker 申告であることに対する正しい修正方向である。破れているのは導出規則の全域性（M14）と統治集合の実在（B2）であって、原則ではない。

---

## 処置記録（2026-08-29、設計側の対応）

対象: `docs/design/auto-integration-gate.md`（改訂版）。指摘の綴りは本記録の表記（ゲートD1〜D7 / ADR D1〜D5）を維持し、設計文書側は決定論ゲートを G1〜G7 へ改称した。処置区分は 改訂（設計文書を修正して欠陥を潰した）／棄却（誤検知として根拠付きで退けた）／OQ化（オーナー判断が本質的に必要なため Open Questions へ移した）。

内訳: 改訂 32 件 / 棄却 0 件 / OQ化 2 件（計 34 件）。

### blocker

- B1 改訂: 6節「実行の封じ込め」を新設し、worker著作コードを実行する全ゲートを push資格・同期資格・秘密環境変数を持たない別主体で走らせることと、封じ込め不能時のfail-closedを Phase A entry 条件に置いた。
- B2 改訂: 2節「批准に伴うオーナー作業」で `GOVERNANCE_PATHS` へ追加すべき面を列挙し、10節 Tier G の「宣言段で拒否済み（既存）」を「列挙追加後に初めて成立する」へ訂正した。
- B3 改訂: G3 を収集テストID集合の base/head 比較へ拡張し、収集設定ファイルの追加・変更を fail-closed とした（関数名変更・parametrize削減・ヘルパ無効化も同一機構で捕捉）。
- B4 改訂: verdict は統合実行器が検証者セッション出力から直接記録し、worker が組み立てた `independent_verification` は自動レーンの入力にしない（存在時は不通過）と規定した。
- B5 改訂: verified head を不変refで固定し、S4 が統合するのは verdict が指す commit のみ・branch先端が異なれば統合しない・verdict に有効期限を置く、を規定した。
- B6 改訂: 契約seed payload へ割当時base commit を追加する（オーナーコミット面）ことを2節へ置き、G1・G3・Tier導出の入力を「割当時base..verified head」に固定した。
- B7 改訂: ヘッダの「ADR D1 を一切緩和しない」を撤回し、ADR D1 第1項と衝突する設計であることを明記。批准が伴う統治正本改訂（ADR D1・goal C5・運用細則）を2節と15節でオーナー作業として分離した。push を「外部公開」に含めるかの解釈は Open Question 1 へ移した（改訂＋部分OQ化。件数は改訂へ計上）。
- B8 改訂: 観測窓を「その統合が実行到達する面」へ接続し直し、Tier 0 は観測窓なし、checkout直接実行面は Tier 2、Tier 2 の窓は反映完了時点から開くと規定した。
- B9 改訂: checkout直接実行面を Tier 表へ新設（Tier 2）し、バックアップ面（`operations/backup/`・`src/pda/backup/`・`continuity/local-backup.json`）は C3 に従い Tier G として `GOVERNANCE_PATHS` 追加対象へ入れた。
- B10 改訂: 注入演習を専用surface・shadow branch（push を伴わない）・本番main非接触に限定し、M3設計32行目の既存規定へ従わせた。
- B11 改訂: 単一lease（TTL・保持者記録・回収規定）を機構として規定し、tick は前回実行中ならスキップ、統合は router tick の1ステップとした。

### major

- M1 改訂: 「フルスイート」を統治面のスイートマニフェスト列挙で定義し、未追跡ディレクトリ除外・実行ホスト併記・終了コードと収集/実行件数の両方必須・インフラ異常の区別・既知失敗リスト方式（ベースライン比較単独は不採用）を規定した。
- M2 改訂: 6節に資源契約（統合毎の全数スイートは1回・直列nice・空きメモリ閾値・同時AI起動1・host_guard最小版）を置き、運用細則の負荷規律追記と適用対象明記を2節のオーナー作業へ入れた（同細則の適用対象が現在「goal実行主体の作業運用」である点は設計側で明記した）。
- M3 OQ化: 統合記録の正本を Git trailer と Kanban承認ledger の2面照合へ変更したうえで、ADR D3 の物理隔離未達を受容するか物理分離を entry 条件にするかを Open Question 3 とした。
- M4 改訂: origin/main を唯一の正本と定義し、統合段（push成功で確定・再投入しない）と同期段（未同期状態として同期のみ再試行）へ分割、agent-node 先行時は統合を開始しないと規定した。
- M5 改訂: 方針ファイルを既存統治面 `continuity/autonomous-improvement.json` の節とし新設を禁止、伝播を「統合直前に origin の コミット済み版を読む」と規定、起動経路を router tick の1ステップに統一して記述矛盾を解消した。
- M6 改訂: 第2 dispatcher を作らず既存 router tick のステップとし、統合記録は Git と Kanban を正本・独立ファイルは再構築可能キャッシュのみ、上限カウンタとキュー滞留も盤面から導出とした（P1・P3準拠）。
- M7 改訂: Tier は `risk_class` と `finalization.kind` を置き換えないことを明記し、写像と矛盾時の扱い（厳しい側・矛盾自体を不通過事由）を定義。観測窓の長さと閾値は M3 の risk_class 別定義に従わせた。
- M8 改訂: 自動実行は merge revert に限定し宣言済み rollback との正本関係を規定、revert後の再統合は割当時baseから新規branchを作り直す、前進のみの状態変化は down 手順がなければ自動統合対象外とした。
- M9 改訂: 検証者は統合実行器が作る読取専用clone を読み live worktree へ触れない、書込可能ツリー・push資格・lifecycle権限を持たない、読取専用契約を seed 側に定義する、へ変更した。
- M10 OQ化: Phase A entry を3件（オーナー作業完了・封じ込め実行器・実測課題2の遮断）として12節へ明記し、未成立の前提（M1完了記録未完・課題1/2/3未解決）を事実として示した上で着手可否を Open Question 2 とした（旧「Decision案: 着手可」は撤回）。
- M11 改訂: プローブに M3 の後始末契約（valve復元・外部通知抑止）とC7（本番Kanban/承認ledger/runtime非接触・試験DB・本番パス検出でfail-closed）、残留状態の検出と残留中の判定停止を義務づけた。
- M12 改訂: 案(a)採用時の必須条件として、免除レーンが class budget / tool budget で閉じること・引数検査・run終端シグナルの契約検証を ADR D5 に従い回帰スイートで先に固定することを明記し、13節へ迂回テスト要求を集約した。
- M13 改訂: `docs/status/` 全体を `GOVERNANCE_PATHS` 追加対象（Tier G・自動レーン外）とし、Tier 0 は「統治面と `docs/status/` を除くdocsへの新規ファイル追加のみ」へ限定、既存記録ファイルの変更・削除・行削除は昇格とした。
- M14 改訂: Tier 導出の正本を統治面のコミット済み Tierマニフェスト（パス列挙）とし、未列挙パスは fail-closed でオーナーへ落とす既定を置き、初版で置き場を与える面を列挙した。

### minor

- m1 改訂: 決定論ゲートを G1〜G7 へ改称し、`D` 単独の綴りはADR判断のみを指すと識別子規約へ明記した。
- m2 改訂: 当該事象を2026-08-22の初回実運転の実証として帰属し直し、2026-08-29のM1実運転で確証された3件と書き分けた。
- m3 改訂: Tier 1 の窓を「観測完了時刻までがオーナー観測時間帯に収まる」定義へ変更し、統合開始を 07:00-21:00 JST とした。
- m4 改訂: Phase A では統合実行器自身を C6 監査イベントの発行主体とし、`ai-invocation-audit-v1` 準拠・発行前検証を規定した。
- m5 改訂: G6 のパターン正本を統治面マニフェストに置き、`.env`系判定は既存スコープゲートの denial 規則を参照、未整備の間は自動統合を開始しないと規定した。
- m6 改訂: S4 の固定手順を正本とし、worker宣言の `finalization.steps` は自動レーンで実行しない・`kind`/`targets`/`rollback` は入力としてのみ使う・矛盾は不通過とした。
- m7 改訂: オーナーキューへ落とす件数の日次上限を方針値へ置き、分類別に日次1通へ集約、超過分は滞留（自動レーンは停止しない）、上限常時到達はゲート欠陥として起票、とした。
- m8 改訂: 15節を「オーナーがコミットする面」と「実装フェーズで反映する面」に分割し、統治面の改訂を2節のオーナー作業へ移した。
- m9 改訂: 検証者起動の上限（Tier別・再検証は最大2回）と日次AI起動上限を方針値として置き、統合件数の上限とは別軸であることを明記した。
