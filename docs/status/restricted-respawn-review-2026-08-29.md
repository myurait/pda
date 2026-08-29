# 再spawn進捗判定ガード（patch 0002）反証レビュー 2026-08-29

対象は未コミット差分。`integrations/hermes-kanban-governance/0002-fix-kanban-gate-respawn-on-deterministic-worktree-pr.patch`（`hermes_cli/kanban_db.py` へ `_worktree_progress_guard` 系を追加し `check_respawn_guard` から呼ぶ）、および同ディレクトリの `manifest.json` / `README.md` の更新。

検査軸は遮断方向の完全性、誤遮断、fail-closed、既存 respawn guard および patch 0001（terminal遷移のclaim束縛）との相互作用。

## 判定

適用前に処置が必要。設計の主目的（コミット済み成果を残したrunの直後に第2 workerが同一checkout上で作業を再実行することの防止）が、伝達経路の取り違えにより成立していない（F1）。遮断の非原子性が patch 0001 のガードと衝突してカードを「blockedでもspawnでもない」状態に置く経路がある（F2）。F1・F2 は適用前の修正対象。F3〜F6 は適用可否の判断材料。

## F1 回収指示が worker に届かない（重大）

`_RECOVERY_RESPAWN_INSTRUCTION` は `tasks.last_failure_error` へ書かれる。しかし `build_worker_context`（`hermes_cli/kanban_db.py:11513`）は同カラムを参照しない。worker prompt が「前回試行のエラー」として描画するのは `task_runs.error`（`## Prior attempts on this task` 節の `_error_:` 行）である。

リポジトリ全体で `tasks.last_failure_error` を読むのは次の3か所のみ。`check_respawn_guard` の `blocker_auth` 判定（`kanban_db.py:9951`, `:9996`）、`kanban_diagnostics.py:563`、`apps/desktop/src/plugins/kanban/types.ts:106`。worker への投入経路は存在しない。

結果として、コミットあり×合図なしの象限——実運転で観測された事象そのもの——では、ガードは再spawnを許可した上で第2 workerに何も伝えない。二重実行リスクは未緩和で、増えるのは `respawn_recovery_granted` イベントと2回目の遮断だけになる。

副作用がもう一つある。protocol violation 経路（`kanban_db.py:9219`）は違反メッセージと是正ガイダンスを同カラムへ意図的に書いている。ガードはこれを上書きするため、盤面UIと `kanban_diagnostics` が読む情報が失われる。

新規テストは `SELECT last_failure_error` でカラムの中身だけを検証しており、worker へ届くかは検証していない。

処置案は2つ。`task_runs.error` へ書く（違反経路が既に使い、`build_worker_context` が描画する）、またはカードコメントとして残す（コメント欄は `build_worker_context` に含まれる）。いずれの場合も、指示が worker prompt に現れることをテストで押さえる。

## F2 遮断が非原子で、patch 0001 のガードと衝突する（中〜重大）

`_park_respawn_loop` は `respawn_progress_blocked` イベント → コメント → `block_task` の順に3つの独立したトランザクションで書く。

`block_task` は patch 0001 の live foreign claim guard 下にある。ready レーンのスナップショット取得後、ガード評価までの間に別の dispatcher または terminal の `claim_task` が入ると、カードは status=running かつ live claim を持つ。`_park_respawn_loop` の呼び出しは `expected_run_id=None` / `force=False` なので拒否され、`block_task` は False を返す。

この時点でイベントとコメントだけが残り、カードは blocked にならない。以降の tick では dedup 条件（`created_at >= since`、`since` は直近の閉じたrunの `ended_at`）が成立して park が再実行されないため、`check_respawn_guard` は理由文字列を返すだけになる。dispatcher は毎tick `respawn_guarded` イベントを積むが、カードは blocked にも spawn にもならない。新しいrunが閉じて `since` が進むまで解消しない。

処置は `block_task` を先に成功させてからイベントとコメントを書く、あるいは単一トランザクションにまとめる。いずれにせよ `block_task` の戻り値を検査し、False の場合はイベントを残さない。

## F3 rate_limited が回収予算を焼く（中）

無進捗streakの計算は `outcome != "rate_limited"` で除外している。一方 `_respawn_recovery_spent` は `task_runs` を outcome 無条件で `id > granted_after` 検索するため、回収runがクォータ壁で即終了しただけでも「回収は消費済み」と判定する。次のcrashで `recovery_exhausted` として blocked に落ちる。

README が掲げる「rate_limited は中立」と不整合。`_respawn_recovery_spent` 側にも同じ除外を入れる。

## F4 コミット帰属が壁時計窓のみで、両方向に誤判定する（中）

`_worktree_commit_log` は worktree HEAD の直近50件を読み、`_run_produced_commit` はそのcommitter dateがrunの `[started_at, ended_at]` に入るかだけを見る。

当該runが作っていないコミットが窓に入り得る。main から分岐した際の祖先コミット、run中の merge / rebase で取り込んだ他タスクのコミットは committer date を保持するため、「進捗あり」と誤判定される。この場合、無進捗ループに対して tip が変わるたび新しい回収許可が出る。実効的な上限は既存の `_PROTOCOL_VIOLATION_FAILURE_LIMIT`（3）だけになり、本ガードは無進捗ループに対して何も足さない。

逆方向として、run終了後の amend / rebase は committer date を窓外へ動かすため「進捗なし」と誤判定する。こちらは遮断側に倒れる。

run開始時に base sha を記録し、`base..HEAD` の差分で判定すれば帰属が決定的になる。

## F5 例外が tick 全体を落とす（低〜中）

`_worktree_progress_guard` 内の `conn.execute` 例外と `_park_respawn_loop` の `block_task` 例外は、呼び出し点（`kanban_db.py:10712`）で捕捉されない。1枚の異常カードが dispatcher tick 全体を中断させる。spawnしないので方向は fail-closed だが、他の全カードも同時に停止する。ガード本体を try で囲み、例外時はそのカードのみ遮断する。

## F6 コミット0件のリポジトリで誤遮断（低）

`_worktree_commit_log` は `git log` の出力が空でも `None` を返すため、`progress_undeterminable` として blocked になる。初期化直後のリポジトリを対象とする worktree タスクが対象外にならない。空出力は「読めた上でコミットが無い」状態であり、読取不能とは区別できる。

## F7 base commit と実行基盤の検証状況（記録）

本レビューの読み取りは、開発PCへ複製された agent-node HEAD のミラー（hermes 側の git 履歴を持たない複製、0002 適用済み）に対して行った。0002 の逆適用検査は開発PC上で通過するため、読み取った `kanban_db.py` は「ある基点 + 本パッチのみ」であることが確認できる。一方 `manifest.json` の `base_commit` 084cdbf1 そのものは開発PCから検証できない。「084cdbf1 に対する `git apply --check` 通過」と「複製元が agent-node HEAD と一致すること」は実装者の報告のみを根拠とする。

`manifest.json` に記録された 0002 の sha256（a52d4078cd091050dd5539250cae11dc82281e8907f4b9face41864ede2b833c）は実ファイルと一致する。

## 反証できなかった点

- review レーンの除外は成立する。`check_respawn_guard` は `lane == "review"` で `kanban_db.py:10003` の早期 return に入り、進捗判定へ到達しない。dispatcher の review レーン呼び出しへ追加された `dry_run` 引数は無害な no-op。
- オーナー手動 ready 化は素通りする。`block_task` が outcome `blocked` の run を閉じるため、再 ready 後の直近の閉じたrunは crashed でなくなり、ガードは `None` を返す。永久停止はしない。
- `_RECOVERY_RESPAWN_INSTRUCTION` の文言は `_RESPAWN_BLOCKER_RE` に一致しない。次tickで `blocker_auth` に捕まる経路は無い。
- 既存4判定の優先は保たれる。進捗判定は最後段にあり、`rate_limit_cooldown` / `blocker_auth` / `recent_success` / `active_pr` はいずれも先に return する。
- `completed` / `review_requested` は `run_id` 付きで記録される（`kanban_db.py:5622`, `:6737`）ため、`_completion_signal_in_run` の run 単位照合は成立する。ただし `complete_task` は patch 0001 の拒否時に `completed` イベントを出さずに戻るため、`completion_signal_lost` 象限が実運転で立つ頻度は低い。
- `write_txn` のネスト違反は無い。`check_respawn_guard` の呼び出し点はトランザクション外にあり、`_park_respawn_loop` 内の `write_txn` と `block_task` / `add_comment` の内部トランザクションは衝突しない。
- 適用外の扱いは設計どおり。scratch / dir ワークスペース、初回spawn、直近runが completed / blocked / reclaimed / timed_out のカードは素通りする。`dry_run` は許可記録・コメント・blocked遷移のいずれも書かない。

## 処置記録 2026-08-29

パッチ 0002 を再生成した。`manifest.json` の 0002 sha256 は
`4d8c05687166186ed4f5e1d1c37db93797991e2d22023e86f0d915e8a221872c`、
`source_commits` の 0002 側は再生成ツリー上の `2decf3b8` へ差し替えた（旧
`9367943d` は破棄）。再生成後のパッチは 0002 適用前の `hermes_cli/kanban_db.py`
に対して `git apply --check` と逆適用検査の双方を通過する。

### F1 修正

回収指示の書込先を `tasks.last_failure_error` から crashed run の
`task_runs.error` へ変更した（既存のエラー文の後ろに追記し、上書きしない）。
`build_worker_context` が `## Prior attempts on this task` 節で描画するのはこの
カラムであり、指示は worker prompt に現れる。`tasks.last_failure_error` は書か
なくなったため、protocol violation 経路が同カラムへ記録する違反メッセージは
残る。

テストは `check_respawn_guard` 実行後に `build_worker_context` の文字列を検査
する形へ改めた（`RECOVERY RUN` / `kanban_complete` の出現と、crashed run 自身
のエラー文の残存）。`tasks.last_failure_error` を事前に埋めたカードで、同カラム
が無変更のまま指示が prompt に届くことも別途固定した。

### F2 修正

`_park_respawn_loop` の順序を「blocked遷移 → イベント → コメント」へ変更し、
`block_task` の戻り値が False の場合は理由だけを返して何も記録しないようにした。
`block_task` は内部で `write_txn` を開くため単一トランザクション化はできない。
重複抑止の検査は従来どおり先頭に置いてあり、既に park 済みの状態に対する再
`block_task` 呼び出し（`block_recurrences` を進めて triage へ逃がす経路）は発生
しない。

テストは、live foreign claim 下で park が拒否された際にイベント・コメント・
status のいずれも動かず理由が返ること、claim が消えた次の呼び出しで実際に
blocked へ落ちることを固定した。

### F3 修正（指摘の帰結は成立せず、整合性の修正として適用）

`_respawn_recovery_spent` の後続run検索から `rate_limited` を除外した。ただし
指摘が述べる帰結——「次のcrashで `recovery_exhausted` として blocked に落ちる」
——は成立しない。`check_respawn_guard` の rate-limit cooldown 判定は、直近の
閉じたrunが `rate_limited` の場合、クールダウン経過後に `None` を返して早期
returnする。進捗判定へ到達しない。到達する場合（`rate_limited` より後に
`crashed` run が閉じている）は、その `crashed` run 自身が後続runとして数えられる
ため、修正前後で答えは変わらない。

そのため誤遮断の実害はないが、README が掲げる「rate_limited は中立」と関数の
実装を一致させる価値はある。テストは到達不能な経路を装わず、
`_respawn_recovery_spent` 単体の戻り値（rate_limited のみが後続の場合は False、
実際に閉じた回収runがある場合は True）で固定した。

### F4 残存制限として記録（コード変更なし）

コミット帰属が壁時計窓のみである点は指摘のとおり。ただし処置案（run開始時の
base sha 記録）は claim 経路の変更を伴い、本パッチの範囲外である。窓による誤
判定が残す影響は次の範囲に収まる。

- 誤って「進捗あり」と読んだ場合の消費は先端sha 1つにつき回収1回で、次のrunが
  無進捗で閉じれば `recovery_exhausted` に落ちる。F1 の修正により、その1回は
  「やり直さず確認して報告せよ」と指示された run になる。
- 逆方向（run終了後の amend / rebase）は遮断側に倒れる。
- 反復の外側の天井は指摘自身が挙げている violation streak 3 のままである。

README の 0002 節へ「既知の限界」として同内容を記載した。

### F5 修正

`check_respawn_guard` の進捗判定呼び出しを try で囲み、例外時は
`progress_guard_error` を返してそのカードのspawnのみを見送る。`block_task` の
意図的な park と例外由来の見送りを区別するため、`progress_undeterminable` とは
別の理由文字列にした。テストは、例外時に書込が発生しないこと、および同一tick内
の健全なカードが引き続きspawnされることを固定した。

### F6 棄却

指摘の機構が存在しない。コミット0件のリポジトリで `git log` は rc=128 で失敗
するため、`_worktree_commit_log` は `returncode != 0` の分岐で `None` を返し、
`if not commits` の分岐には到達しない（開発PC上で確認）。加えて
`workspace_kind == "worktree"` のパスは `git worktree add`（`kanban_db.py:7845`,
`:7848`）が作成し、同コマンドはコミットを持たないリポジトリでは成功しない。
`if not commits` は到達しない防御として残す。

### 検証

`tests/hermes_cli/test_kanban_respawn_progress_guard.py` は 27件、全pass。追加・
改訂した6件は修正前の実装に対して失敗し、修正後に通ることを確認した（F3 は
上記のとおり単体レベルでの固定）。

`tests/hermes_cli/test_kanban*.py` + `tests/tools/test_kanban_tools.py` の
比較実行結果。

```
0002未適用（新規テストファイルなし）: 290 passed, 43 failed, 3 skipped, 5 errors
0002適用（本処置後）:                 317 passed, 43 failed, 3 skipped, 5 errors
```

失敗・エラーの50件は両者で完全に同一のID集合であり、開発PCの実行環境に由来
する（git worktree の削除がサンドボックスに阻まれる、ネットワーク到達性、
HOME配下の書込ガードなど）。本パッチによる新規失敗は0件、増分は追加した27件の
passである。
