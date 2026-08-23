# S3-M1 write scope 設計 反証レビュー記録（2026-08-22）

- Status: open（確証欠陥の未解決分あり。対応は goal M1 の残作業）
- 読み取り方針: **本ファイルは `restricted-` 接頭辞の対象。迂回手法の具体形を含むため、Fable モデルのセッションでは直接読まない**（安全性分類器の誤検知で会話が停止した実績がある。2026-08-22 23:29 JST / 2026-08-23 12:20 JST）。対応作業は Opus のサブエージェントへ委譲し、本体へは判断項目と結果のみを返す。
- レビュー対象: `docs/design/task-scope-admission-gate.md` の「S3-M1: 決定論コアの具体設計」および関連実装（`integrations/hermes-scope-gate/`）
- 実施: 運用細則2（実装着手前の複数レンズ並列反証）に基づく 4 エージェント並列レビュー
- 確証欠陥: 20 件（blocker 6 / major 7 / minor 7）、棄却 0 件
- 判断項目の要約は `docs/design/task-scope-admission-gate.md` の「S3-M1 未解決の設計判断」に置く（そちらは全モデル可読）

## 対応の進め方

blocker 1・2・3 と major 7・12 は相互に矛盾するため個別修正を当てず、単一の整合した設計判断として解決する。blocker 5 は ADR とロードマップの正本不一致であり、設計変更ではなくオーナー承認を要する。

## 確証された欠陥

### 1. [blocker] terminalでのpytest許可が任意コード実行としてwrite_paths決定論境界を無効化する

**根拠**

docs/design/task-scope-admission-gate.md:394-395 は locked artifact-change の terminal に targeted verification として pytest/`python -m pytest` を許可する。pytestはrootdirから収集対象までの各階層のconftest.pyを自動import実行し、収集対象test_*.py自体もimport時にtop-levelコードを全実行するため、プロセス全権限での任意ファイルI/O・subprocess・外部通信が可能。§11:393のwrite_paths glob判定は`args.path`を持つ構造化書込ツールにのみ適用され、pytest実行中の書込・読取・送信はコマンド文字列検査に一切現れない。workerはwrite_paths配下へ正規のwrite_fileでconftest.py/test_*.pyを置き、続く「許可された」pytest呼び出しでwrite_paths外への任意操作を実行できる。ADR(docs/design/self-improvement-governance-adr.md:101-103)とgoal.mdのM1 exit gate「workerが…スコープ逸脱を試みる敵対的テストが全て遮断される」は敵対的workerを脅威モデルに含むため、これは境界の敗北である。closeoutのcommit hook自動実行許容(同設計:256)より広い暗黙実行サーフェスである点も確認した。(統合元: bypassレンズblocker + operabilityレンズ確認事項のpytest実行サーフェス注記)

**対応方針**

確証済み指摘「git add/commit不許可」「tests/書込免除なし」と一体の単一設計判断として解決する。選択肢は (a) targeted verification実行はwrite_paths境界保証の対象外であることを脅威モデルとして明文化し、ファイルシステム名前空間をwrite_pathsへ制限したsandbox実行と収集経路上のwrite_paths外conftest.py静的検査をM2の必須要件として設計に固定する、(b) M1決定論コアでは実行を伴わない検査(AST/静的検査系)のみ許可しテスト実行自体を許可しない、のいずれか。3指摘へ個別に機械的修正を当てると相互矛盾するため、1つの整合した決定を設計文書へ書く。

### 2. [blocker] pytest/py_compileの引数検査が位置引数のみで、フラグ迂回・stdin迂回・通常フラグのfalse denyが同時に生じる

**根拠**

§11:395は「位置引数のパスが全てwrite_paths配下またはtests/配下」と検査対象を位置引数へ明示限定。`pytest --basetemp=/outside tests/test_x.py`は位置引数のみ要件を満たし、`--basetemp`/`--rootdir`/`-c`/`--override-ini`/`-p`/`--confcutdir`等の`-`始まりトークンは検査外のまま一時ディレクトリ・config探索・plugin読込経路をwrite_paths外へ差し替えられる。CPythonのpy_compile.main()は引数['-']単体でstdinから1行1ファイル名を読むモードを持つことをソースで実確認済みで、`python -m py_compile -`のコンパイル対象(__pycache__書込)はコマンド文字列検査に一切現れない。逆に実運用の典型`pytest -x -q --maxfail=1 tests/test_foo.py`はフラグ不許可実装ならfalse denyになる。既存closeout実装(_commit_args_are_bounded scope_gate.py:1273-1294、_push_args_match_locked_ref 同:1297-1319、_diff_args_are_bounded 同:1204-1227)は全トークン網羅のallowlist方式であり、§11はこの既存水準に達していない。(統合元: bypassレンズblockerフラグ + bypassレンズmajor py_compile stdin + operabilityレンズmajor位置引数 + consistencyレンズmajorのフラグ部)

**対応方針**

検査を「位置引数のみ」から「全トークン」へ変更し、安全フラグ(-x, -q, -v, --maxfail=N, --tb=short等)の明示allowlistと未知フラグ即denyをcloseout同水準で設計に明記する。値を取る危険フラグ(-c, --rootdir, --confcutdir, --override-ini, -p, --import-mode, --basetemp等)は=結合形・空白区切り形の両方でdeny。py_compileは位置引数`-`単体(stdinモード)を明示denyするか、terminalのstdinを常に空へ固定することをM1受入テストに追加する。

### 3. [blocker] artifact-changeでgit add/commitが決定論コアで許可されず、既存運用(local commit)と正面矛盾する

**根拠**

§11:394はterminal許可を「(a) closeoutと同じGit読み取り部分集合、(b) targeted verificationテンプレート」に限定する。読み取り部分集合はstatus/diff/rev-parse/ls-remote/branch/remote(integrations/hermes-scope-gate/scope_gate.py:1084-1094)で、add/commitはallow_commitでゲートされる書込系(同:1095-1126)。classify_taskはrepository-closeout分岐(同:184-189)でのみallow_commit/allow_pushを立て、artifact-change(_classify_non_closeout 同:99-117)はデフォルトFalseのまま(tests/test_scope_gate.pyのG0 gold setがallow_commit is Falseを固定)。G3はjudge未接続でfail-closed(scope_gate.py:685-690、plugin_runtime.py:143-147のjudge=None)のため救済されない。一方docs/operations/pda-improvement-cycle.md:57とdocs/roadmap/autonomous-improvement-goal.md(103行・192行)はlocal commitをworkerの通常許可作業と明記しており、実装→focused test→local commit→handoffのflowがcommitで必ず止まる。

**対応方針**

write_paths配下(ロック済みworktree)を対象とした`git add`と`git commit -m <message>`(pushは含めない)を、closeoutの_add_args_are_bounded/_commit_args_are_bounded同水準の引数境界を課したうえで決定論allowlistへ明記する。pushは既存運用どおり承認後の別finalization契約に残すことを明文化し、pytest実行・tests/書込の指摘と同一の設計改訂で整合させる。

### 4. [blocker] lock前(audit)状態が無制限allow-allのままで、write境界がworkerのopt-inになる(INV-S8違反)

**根拠**

§11:388「lock前はG0/G1の既存挙動(audit)を維持する」。現行admit_tool(scope_gate.py:918-920)はtask_class != repository-closeoutならstateを見ず即GateDecision(True, "not-enforced")を返す。closeoutにはdiscovering段の既定deny(_admit_closeout_discovery 同:992-1014)があるがartifact-changeには相当フェーズが設計されておらず、lock_turnを呼ぶか否かはworkerの自発行動に委ねられる。呼ばれない限りwrite_file/patch/terminal破壊操作を含む全tool callが無制限許可され、INV-S8「enforcement is independent of agent self-restraint」と衝突する意図的選択が設計文書自身に明記されている。

**対応方針**

artifact-changeにもcloseoutのdiscovering相当のbounded pre-lockフェーズ(read/search/list系のみ許可、write_file/patch/terminal変異系は既定deny)を導入するか、オーケストレーターがdispatch時にlock済み契約を注入しlock未了のartifact-change turnでは変異系を常時denyする構造を§11へ明記し、「lock前は自由」というaudit挙動を明示的に置き換える。

### 5. [blocker] 「worker配線はM2」への切り出しがADR D2とgoal M1定義に矛盾する(統治正本の無言格下げ)

**根拠**

docs/design/self-improvement-governance-adr.md:101-103「承認後にM1実装として動くもの」に「スコープ審査ゲートS2/S3のworker実行への適用(artifact-changeクラス)」が明記されている。docs/roadmap/autonomous-improvement-goal.md:155のM1進捗記録も「残: スコープゲートS3(write scope)のworker適用」とM1残作業として記録し、M1 exit gate(同:160)は「workerが自己完了・保護解除・スコープ逸脱を試みる敵対的テストが全て遮断される」を要求する。ところがtask-scope-admission-gate.md:379は「worker profileへの配線・有効化…はM2(オーケストレーター設計)の残余とする」と明記し、ADRがM1に位置づけた成果物を一方的にM2へ付け替えている。ADRは統治正本であり変更にはADR改訂経路が必要だが、行われていない。goal.md:58も「worker実行(artifact-change相当)への機械的スコープ強制は未実装」と記す通りgapは実在する。

**対応方針**

①§11の対象をworker配線までM1として広げる、②ADR「承認後にM1実装として動くもの」とgoal.md:155のM1進捗記録をオーナー承認の下で改訂しworker適用をM2へ明示付け替える、のいずれかで3文書を一致させる。あわせてM1 exit gateの敵対的テストをどの層(ゲートライブラリ単体か配線込みか)で満たすかを明記する。

### 6. [blocker] lock_turnのartifact-change開放が現行state機械・candidates機構の双方から実行不能

**根拠**

scope_gate.py:356で非closeoutは常にstate="audit"開始。lock_turn(同:448)はtask_class検査で"turn is not a repository-closeout"を送出し、453-454はdiscovering以外からのlockを拒否する(誰がartifact-change turnをdiscoveringへ遷移させるかは未定義で、discovery段自体は§11:379でM2残余)。459-461のcandidates部分集合検査は事前挿入に依存するが、admit_tool:918-920の早期return(not-enforced)によりcandidates挿入(984-988)へ到達せず、record_worktree_candidates(559-562)も非closeoutを明示拒否する。つまり§11:388「closeoutと同じ原子的lock」は独立2要因(state遷移経路の欠如、candidates登録経路の欠如)で恒久失敗する。加えてcloseout専用ガードのValueError回帰テストがtests/test_scope_gate.pyに存在しないことをgrepで確認した(lock_turn関連は178/222-223/241行のみ)。

**対応方針**

§11に、artifact-change turnのlock到達経路(M1に簡易discoveryを含めるか、caller指定targetをどう検証するか)と、candidates事前登録なしでINV-S2(target set is closed)をどう満たすかを明記する。lock_turnのtask_class分岐を変更する前提で、closeout専用ガードの回帰テストを先行追加する。

### 7. [major] tests/配下の無条件許可がwrite_pathsと無関係にfull-suite実行を許す

**根拠**

§11:395は位置引数が「write_paths配下またはtests/配下」なら許可とし、禁止は「パス引数なしのfull-suite起動」のみ。`pytest tests/`は位置引数を持ちながら多くのレイアウトでfull suiteそのものであり、write_pathsがどれほど狭く固定されていても既存の全テストファイル・conftest.pyを収集・実行できる。INV-S4(§3)の趣旨と§13の却下理由「全taskでfull testsを必須化…を再び肥大化させる」に反し、pytest任意コード実行の指摘と組み合わせるとblast radiusがリポジトリ全体規模になる。(統合元: bypassレンズmajor + consistencyレンズmajorのfull-suite部)

**対応方針**

tests/carve-outを当該turnのwrite_paths由来のテストファイル単位へ限定し(ディレクトリ丸ごとの位置引数は拒否)、full-suite実行を許すか否かをcontractの明示フィールドとして持たせる。artifact-changeでの無条件tests/carve-outは撤廃する。

### 8. [major] fnmatchの`*`が`/`を跨ぐため、write_pathsが承認レビュー時の見た目より大幅に広い

**根拠**

python3実測で fnmatch.fnmatch("src/foo/bar/baz.py", "src/foo/*.py")==True、fnmatch.fnmatch("src/foobar/x.py", "src/foo*")==True を確認した(fnmatch.translateは`*`を(?s:.*)へ変換しパス区切りを特別扱いしない)。§11:383は「fnmatch、最大32件」と明示指名しており、「1階層のみ」を意図した`docs/design/*.md`等が任意深度のネスト、同名接頭辞の別パッケージ(foobar等)までマッチする。write_pathsはADR承認者がレビュー可能な有限文字列として設計されているため、レビュー時の理解と実効許可範囲が乖離する。(統合元: bypassレンズmajor + operabilityレンズmajorのfnmatch部 + consistencyレンズminor参考指摘)

**対応方針**

`*`が`/`を跨がない独自translate、または1階層`*`と再帰`**`を構文上区別する実装へ置き換え、パターン末尾のセグメント境界を明示する。ネストパス・接頭辞一致の挙動を受入テストへ追加し、§11へglob例を1つ載せて意図した粒度を明示する。

### 9. [major] args.pathの照合基準(絶対/相対・相対化root)が未定義で、「絶対パス即deny」が既存規約と矛盾する

**根拠**

§11:393「pathを正規化(絶対パス・`..`・制御文字は即deny)」を字面通り実装すると、絶対パスでargs.pathを渡すツール呼び出し(多くのコーディングエージェントの慣習)は常に即deny。既存実装は逆にread_file/search_files(scope_gate.py:1037-1039)とterminal workdir(1051-1052)へ絶対パスを要求している。write_pathsは「リポジトリ相対のglob」(§11:383)だが、どのtargets root(worktrees複数指定時を含む)に対して相対化するか未規定。テストfixtureも割れている: 相対パス"app/login.py"(tests/test_scope_gate.py 136行付近)と絶対パスstr(tmp_path / "file")(549行付近)が混在し、想定経路がテストからも判別できない。(統合元: operabilityレンズmajor + consistencyレンズmajor)

**対応方針**

正規化アルゴリズム(絶対パスへ解決→ロック済みrepo/worktree rootへの相対化→root外は即deny→相対パスをwrite_paths globへ照合)を§11に明記し、「絶対パス即deny」が引数の形式ではなく「正規化後にどのrootにも属さないパス」を指すことを明確化する。ツールがworkdirを持たない場合の解決基準も定める。

### 10. [major] write_paths照合がレキシカルのみでrealpath検証がなく、配下symlink経由で書込先が脱出できる

**根拠**

§11:393の正規化は文字列レベル(絶対パス・`..`・制御文字deny)のみでrealpath解決に触れず、write_paths照合はリポジトリ相対文字列へのfnmatch。write_paths配下の祖先ディレクトリが外部を指すsymlinkの場合(過去commitや先行する正規書込で作成可能)、新規ファイル書込のargs.pathは相対glob照合を通過するがOSの実書込先はlink先になる。なお生指摘中の「既存_is_withinはPath.resolve()でsymlink実体解決を行っていない」という下位主張は誤り(Path.resolve()はsymlinkを解決する)だが、§11で新設されるwrite_paths検査自体にresolve/realpath段が設計されていないという中核の指摘は正しい。

**対応方針**

書込先の直近祖先ディレクトリをos.path.realpath等で解決し、解決後の絶対パスがロック済みworktree root配下であることの検証を設計へ明記する。加えてwrite_paths配下に外部向きsymlinkが存在しないことをlock時またはadmission時に検査する受入テストを追加する。

### 11. [major] 構造化書込ツール判定が`args.path`単一フィールドの名前ヒューリスティックで、第二の書込先を捕捉できない

**根拠**

§11:393の判定は「write_file/patch等、args.pathを持つもの」というshape依存ヒューリスティックであり、本リポジトリにこれらツールの正式なスキーマ列挙は存在しない(scope_gate.py/plugin_runtime.pyともに実引数定義なし)。実workerツール群にはfile_path、notebook_path、複数編集を束ねるedits[]、src/dstを持つrename/move、diff本体へ複数書込先を埋め込むpatch等、単一pathフィールドに収まらない形状が一般的で、名前ヒューリスティックは(a)実引数名の不一致で機能不全になる、(b)一致してもdst等の第二フィールドが検査対象外になる、のいずれかに転ぶ。

**対応方針**

「構造化書込ツール」の判定を、worker profileへ実配線されるツールカタログの明示allowlist(ツール名→書込先を表す全フィールド名の対応表)として定義する。未列挙ツールは無条件でG3(default deny for mutation)へ落とし、列挙済みツールは書込先になりうる全フィールド(単一path、配列、src/dst等)をwrite_paths適合検査する。

### 12. [major] write_paths側にtests/配下の書込免除がなく、TDDのテスト新規作成・編集が構造的に塞がる(py_compileも同様)

**根拠**

§11:393の構造化書込許可は「いずれかのwrite_paths glob一致」のみで、§11:395のpytest実行側にあるtests/例外が書込側に存在しない。write_pathsが例えば`src/foo/**`のみのカードでは`tests/test_foo.py`へのwrite_file/patchはどのglobにも一致せずG3行きとなり、judge未接続fail-closedで拒否される。さらにpy_compileルール(§11:395末尾)にはtests/例外自体がなく、いま書いたテストのコンパイル確認すら通らない。運用文書のfocused test要件(docs/operations/pda-improvement-cycle.md:57)と正面から矛盾する。

**対応方針**

write_paths globに加え、対応するtests/配下テストファイルへの決定論的な書込許可を追加する(境界はtests/全体か、write_pathsのbasenameに対応するtest_*ファイル限定かを明示)。py_compileルールにもpytestルールと対称のtests/例外を設け、pytest実行・git commit許可の指摘と同一の設計判断で整合させる。

### 13. [major] G3 expansion経路の実効性が設計想定と乖離 — judge未接続では全fail-closed denyが予算を消費し、stage2ショートカットもcloseout専用

**根拠**

EXPANSION_REVIEW_BUDGET["artifact-change"]=2(scope_gate.py:196-200)だがplugin_runtime.py:143-147はjudge=None固定で、request_expansion(scope_gate.py:685-690)はbudget内でも常にreviewer="fail-closed"でdenyし、deny結果もexpansion_permits行として挿入され予算を消費する。stage2の既許可ショートカット(同:675)は`task_class == "repository-closeout" and state == "locked"`にハードコードされ、artifact-changeで既に許可されるはずのアクションがG3へ回ると常にfail-closed denyで予算を浪費する。git commit不許可・tests/書込不許可が決定論コアに残ったままなら、通常のTDD flow(テストファイル書込1回+commit1回)だけで予算2回が尽きる。(統合元: operabilityレンズmajor予算 + bypassレンズminor stage2ショートカット)

**対応方針**

「予算2回で足りるか」はjudge未接続では回数に関わらず全拒否のため検証不能であることを設計へ明記し、commit・tests/書込を決定論許可へ取り込みG3が真に例外的な拡張のみを扱う状態にしてから、実トラフィックgold setで予算を較正する順序を固定する。stage2分岐はtask_classハードコードをやめ「そのtask_classのlocked admit関数」を呼ぶdispatchテーブルへ一般化することをM1実装要件に明記する。

### 14. [minor] artifact-changeのgit書込拒否をallow_commit/allow_push恒常Falseという偶発的事実に依存させない

**根拠**

classify_task/_classify_non_closeout経路のartifact-changeはTaskIntentデフォルトのallow_commit/allow_push=Falseのまま(scope_gate.py:99-117。tests/test_scope_gate.pyのG0 gold setがallow_commit is Falseを固定)。§11:394は「既存tokenizerを流用」としか述べておらず、_admit_closeout_lockedのadd/commit/push分岐(turn["allow_commit"]/turn["allow_push"]参照)を素で流用すると、git書込拒否が「このクラスで明示的に禁止」ではなく「フラグが偶然False」という副作用で成立し、将来classify_task側の変更で静かに崩れる。

**対応方針**

artifact-change用のterminal admission関数は、git add/commit/push(決定論許可へ取り込む範囲を除く)の扱いを独立した明示ロジックとして書き、closeout用関数とコードパスを共有しない。

### 15. [minor] パス正規化は単一の決定論関数へ統一し、将来の「親切な」正規化追加によるtraversal再燃を防ぐ

**根拠**

§11:393の正規化仕様は絶対パス・`..`・制御文字denyのみで、先頭./除去や大文字小文字畳み込みに触れない。fnmatchはPOSIX上ケースセンシティブだがmacOS等のAPFS/HFS+はケースインセンシティブ・ケース保存という不一致がある。現状は主に正当書込のfalse deny方向だが、usability目的でremoveprefix("./")のような単純文字列prefix除去を後付けすると`.//../secret`級の変則入力でtraversal文字列を再生成しうる。

**対応方針**

正規化は文字列操作の積み増しではなく、PurePosixPathのpartsを完全に解決して`..`コンポーネント不在と非絶対を検査する単一の決定論関数へ統一し、先頭./・大小文字を含む入力バリエーションの受入テストを追加する。

### 16. [minor] G3自己申告フィールド(reason/estimated_cost)はM1では到達不能だが、M2 judge接続時の主要攻撃面 — 受入テストを先行定義する

**根拠**

judge=Noneの間stage3は常にfail-closed(plugin_runtime.py:143-147、scope_gate.py:685-690)で、reason/estimated_costはstage1/2の判定に影響しないため、M1時点でこれらのフィールドを介した迂回は不成立。設計§6は既に「hard boundsはdeterministic validatorが保持する」と明記し、request_expansionのdocstringも「a judge can only approve what stages 1-2 did not already settle」と構造上一致している。未整備なのは、M2でjudgeが接続された際にexecutorの自己申告reasonが唯一の説得材料になることへの受入テスト定義のみ。

**対応方針**

悪意ある・説得的なreason文字列を与えてもstage1/2の決定論的hard bounds(budget・forbidden・target閉集合)がcontractを超えて緩和されないことを検証するM2受入テストを、M1のうちに設計へ先行定義しておく。

### 17. [minor] terminal許可コマンドのプロセス副作用(.pytest_cache/__pycache__等)がゲート観測対象外であることを明文化する

**根拠**

ゲートはterminal引数(command文字列)のみ検査し(_admit_closeout_locked scope_gate.py:1016-1152)、許可コマンドがサブプロセスとして書き込むキャッシュ・カバレッジ等のファイルはpost_tool_call(plugin_runtime.py:163-208)の証跡対象にも構造化書込経路にも乗らない。これはcloseoutのcommit hook自動実行許容(設計:256)と整合的でありバグではないことを確認した。あわせて§11:384のbudget allOfバグ診断(存在しないキーminutes/tool_callsへのrequiredなしproperties制約で常に真)は、schemas/scope-contract-v1.schema.json:200-251を読んで正しいことを確認した — 実キー置換の修正方針で問題ない。

**対応方針**

設計へ「terminal経由で許可されたコマンドのプロセス副作用(キャッシュ・カバレッジ等のファイル書込)はゲートの観測対象外であり、closeoutのcommit hook前例と同じ扱いである」旨を一文明記する。

### 18. [minor] schema修正時の再発防止 — write_paths必須化にはrequiredキーワードが必要、max_expansions上限もスキーマへ反映する

**根拠**

既存バグ(schemas/scope-contract-v1.schema.json:200-251)は、then節がrequiredを伴わないpropertiesのみの制約(かつ存在しないキー名)のため常に真になっていた。新設のtargets.write_paths「artifact-changeで必須」を同じallOf/if/then/propertiesパターンで書くと、requiredを伴わない限り同種の空振り(存在すれば形状検査、欠落は素通り)が再発する。またEXPANSION_REVIEW_BUDGET["artifact-change"]=2(scope_gate.py:196-200)に対応するmax_expansions上限がスキーマにない(budget定義116-158行は0-20の汎用範囲のみ)ため、決定論バリデータとスキーマの二重防御が不一致。

**対応方針**

write_paths必須化にはthen節へ"required": ["write_paths"]を用いること(properties単独では効かない)を§11に明記し、budget.max_expansionsへartifact-change: maximum 2、bounded-operation: maximum 1の制約を追加してEXPANSION_REVIEW_BUDGETと一致させる。

### 19. [minor] targets.worktree_branches(全class必須)のartifact-change lockでの扱いが未記載

**根拠**

schemas/scope-contract-v1.schema.json:49-74でtargets.worktree_branchesはtask_classに関わらずrequiredかつminProperties:1。closeout専用の_validated_worktree_branches(scope_gate.py:1166-1191、git branch --show-current必須・detached HEAD拒否)をartifact-change lockでも同形で呼ぶのか、§11に記載がない。

**対応方針**

artifact-change lockでも同じbranch検証(worktree_branches)を再利用するのか、別の検証へ置換・緩和するのかを§11へ一文追加する。

### 20. [minor] plugin_runtimeのscope_gate(action=lock)ハンドラがwrite_pathsを配線していない — 実装チェックリストへ明記

**根拠**

handle_scope_gate(plugin_runtime.py:124-134)はtargetsのrepositories/worktrees/branchesのみをlock_turnへ渡し、write_pathsを読み取っていない。M1でlock_turnへwrite_paths引数を追加する場合、このハンドラの同時更新が必要になるが§11に明記されていない。

**対応方針**

§11の実装チェックリストへ、plugin_runtime.pyのlockアクションでparams["targets"]["write_paths"]をlock_turnへ渡す変更を明記する。

## 欠陥ID採番対応表（2026-08-23 追記）

上記「確証された欠陥」の見出し番号 1〜20 を、そのまま `R-01`〜`R-20` として採番する（見出し番号 N ↔ `R-{N:02d}`）。以後、本ファイルを直接読めない（`restricted-` 隔離対象の）文脈では、この ID と抽象名のみで参照する。抽象名は `docs/operations/adversarial-suite.md` と同じ抽象化水準に揃えてあり、迂回手法の具体形を含まない。

- R-01 [blocker] 実行を伴う検証が write 境界の保証外になる
- R-02 [blocker] 許可コマンドの引数検査水準が既存実装（closeout）に達していない
- R-03 [blocker] ローカルコミットが決定論allowlistに含まれず既存運用と正面矛盾する
- R-04 [blocker] lock 前の既定が無制限で、境界が自己抑制に依存する（INV-S8）
- R-05 [blocker] M1/M2 境界の付け替えが統治正本（ADR / goal）と矛盾する
- R-06 [blocker] artifact-change の lock 到達経路が存在しない
- R-07 [major] テスト対象範囲の無条件免除が verification 範囲を広げる
- R-08 [major] glob のセグメント境界扱いが承認レビュー時の理解と乖離する
- R-09 [major] パス照合基準（正規化・相対化 root）が未定義
- R-10 [major] 書込先の実体解決がなく境界脱出の余地が残る
- R-11 [major] 書込先フィールドの網羅がツール形状ヒューリスティックに依存する
- R-12 [major] テスト資産の書込が構造的に封鎖される
- R-13 [major] G3 拡張審査経路の実効性と予算較正の前提が未成立
- R-14 [minor] git 書込拒否がフラグの偶発値に依存する
- R-15 [minor] パス正規化が一元化されておらず将来の再燃余地がある
- R-16 [minor] judge 接続時の自己申告フィールドに対する受入テストが未定義
- R-17 [minor] 許可コマンドのプロセス副作用が観測対象外であることが未明文
- R-18 [minor] 契約スキーマの条件付き必須指定漏れと上限未反映
- R-19 [minor] artifact-change lock でのブランチ検証の扱いが未記載
- R-20 [minor] runtime ハンドラでの write scope 配線漏れ

### D-S3-1 / D-S3-2 / D-S3-3 の決定（2026-08-23、推奨案「二層契約」）と欠陥の対応

所掌内で解決（13件 = blocker 3 / major 7 / minor 3）: R-01, R-02, R-03, R-07, R-08, R-09, R-10, R-11, R-12, R-13, R-14, R-15, R-17。

- 第一層（write 境界・硬い決定論保証）で解決: R-03, R-07（書込側）, R-08, R-09, R-10, R-11, R-12, R-14, R-15
- 第二層（実行・契約単位の明示 opt-in、保証対象外の宣言）で解決: R-01（境界の明示と残余の M2 要件化）, R-02, R-07（実行側）, R-17
- 決定の帰結として前提が成立: R-13（決定論許可の範囲確定後に予算較正する順序を固定）

所掌外（7件）: R-04・R-06・R-19 は lock ライフサイクル（D-S3-4 / D-S3-5）、R-05 は M1/M2 境界（D-S3-6、オーナー判断）、R-16・R-18・R-20 は実装／テスト計画チェックリスト。

### 実装時の申し送り

- 引数allowlistの具体トークン列は本ファイルにも列挙しない。実装時に `integrations/hermes-scope-gate/scope_gate.py` の closeout 側 allowlist 実装（`_diff_args_are_bounded` / `_add_args_are_bounded` / `_commit_args_are_bounded` / `_push_args_match_locked_ref` / `_short_option_bundle_contains`）を正本として参照し、同水準の全トークン走査型で artifact-change 用に新規実装する（closeout 用関数とコードパスは共有しない。R-14）。
- artifact-change のステージ許可は closeout より**狭い**。closeout は「既存差分を一括で保存する」意味論のため一括指定を許容できるが、artifact-change ではステージ範囲を write scope へ従属させる必要があるため、一括ステージ系の指定を除外する。「closeout同水準」は検査の厳密さの下限であって許可範囲の上限ではない。
- 第二層の許可テンプレートは、実行される具体コマンド列ではなくテンプレートIDとして契約に載せ、ID→検査規則の対応はゲート実装側の閉じたレジストリに置く（契約側に自由記述のコマンド文字列を持たせない。設計 §13「Agentが自由記述したcontractを無検証で採用」の却下理由と整合させる）。

## 欠陥ID採番対応表（2026-08-23 追記）

本記録の欠陥見出しには元々IDが無いため、以降の設計判断・戻り値・チェックリストでは
`R-NN` を正式IDとして用いる。番号は上記「確証された欠陥」の見出し番号と一対一で対応する。

- R-01 = 見出し1 [blocker] 検証実行が決定論境界を無効化する
- R-02 = 見出し2 [blocker] 許可コマンドの引数検査水準が既存実装に達していない
- R-03 = 見出し3 [blocker] ローカルコミットが決定論許可に無く既存運用と矛盾
- R-04 = 見出し4 [blocker] lock前の既定が無制限許可（INV-S8衝突）
- R-05 = 見出し5 [blocker] M1/M2 境界が統治正本と不一致（オーナー判断）
- R-06 = 見出し6 [blocker] artifact-change の lock 到達経路が存在しない
- R-07 = 見出し7 [major] テスト配置の無条件許可が検証範囲を広げる
- R-08 = 見出し8 [major] glob の区切り扱いが承認レビュー時の理解と乖離
- R-09 = 見出し9 [major] 書込先パスの照合基準（相対化root）が未定義
- R-10 = 見出し10 [major] 書込先の実体解決が設計に無い
- R-11 = 見出し11 [major] 書込先フィールドの網羅が形状ヒューリスティック依存
- R-12 = 見出し12 [major] テスト資産側の書込許可が無くTDD運用が塞がる
- R-13 = 見出し13 [major] G3 経路の実効性（judge未接続時の予算消費とクラス固定分岐）
- R-14 = 見出し14 [minor] git書込の拒否が分類器フラグの偶発的既定に依存
- R-15 = 見出し15 [minor] パス正規化の一元化
- R-16 = 見出し16 [minor] G3 自己申告フィールドのM2受入テスト先行定義
- R-17 = 見出し17 [minor] 許可コマンドのプロセス副作用が観測対象外である旨の明文化
- R-18 = 見出し18 [minor] スキーマ必須指定と上限反映の再発防止
- R-19 = 見出し19 [minor] artifact-change lock での worktree/branch 検証の扱いが未記載
- R-20 = 見出し20 [minor] lock ハンドラの write scope 配線漏れ

## D-S3-4 / D-S3-5（契約ライフサイクル）対応メモ（2026-08-23）

担当範囲: R-04, R-06, R-19, R-20 を解決する単一のライフサイクル設計。
R-05 はオーナー判断（両分岐に対する適用範囲だけを設計側で用意する）。
R-09 の相対化root、R-13 の admission dispatch、R-14 の権限の出所、R-18 のスキーマ整合は
本ライフサイクル設計と同一の変更点に触れるため、実装は単一の変更へまとめる。

### 採用した構造（推奨案 L-3）

1. 契約は二経路で `locked` に到達する。(a) オーケストレーターが割当時に与える seed 契約、
   (b) それが無いターンでの自己 lock。(a) は上限（authoritative ceiling）、(b) は縮小のみ。
2. lock 前は「既知の読み取り系のみ許可、変異系と未知ツールは既定拒否」の bounded 段とする。
   M1 では独立した discovery 予算は設けず、クラス予算のみを上限とする（discovery段はM2残余のまま）。
3. artifact-change の lock は M1 では単一 worktree に限定する。この単一 root が
   書込先照合の相対化基準（R-09 の未定義部分）を与える。
4. lock 時にリポジトリ実体検証（worktree root 一致・現在ブランチ取得）を closeout と同じ検証器で行う
   （R-19 の回答）。seed の branch と実ブランチが不一致なら fail-closed。

### 設計に落とすべき規範要件（本記録側の作業メモ）

- L-1（closure）: 強制クラスのターン終了は明示 `complete` と session 終了に限る。
  中間の監査フックでターンを閉じない。閉じたターンでの変異系は拒否のまま維持する。
- L-2（binding）: 当該タスクに seed が存在する場合、契約へバインドできない tool call は
  変異系を拒否する（未登録ターンを未強制として扱わない）。
- L-3（seed 検証失敗）: seed の実体検証が失敗したターンは「変異拒否のまま存在する」状態にし、
  未強制へ落とさない。

### 実装前に実機で確認すべき前提

- 監査フック（LLM 呼び出し後フック）の発火粒度が「ユーザーターン単位」か「LLM 呼び出し単位」か。
  本リポジトリからは Hermes 実装を参照できない（実体はミニPC側）。
  ユーザーターン単位でない場合、多段のターンは中間で閉じられ得るため、L-1 の明示 closure が前提になる。
  この依存は S1（closeout）が既に持っているものであり、artifact-change 固有の新規リスクではないが、
  反復回数が多いクラスでは露出が大きい。有効化前に synthetic payload で確認する。
- `lock_turn` のクラス分岐を変更する前に、closeout 専用ガードの回帰テストを先行追加する（R-06 の対応方針）。
