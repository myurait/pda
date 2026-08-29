# hermes-kanban-governance

Hermes本体のKanban状態機械へ適用する管理パッチ series。goal M0(c)（`docs/roadmap/autonomous-improvement-goal.md`）の成果で、インシデント t_877230c3 の再発防止。

## 0001 terminal遷移のclaim束縛

`complete_task` / `block_task` / `archive_task` は従来、`expected_run_id` なしの匿名呼び出しを無条件に受理し、生存中workerの `claim_lock` / `worker_pid` を黙って消去できた。実運用で、review専用delegate childが保護用環境変数を自己解除したうえで親タスクを匿名completeし、生存中のworkerをdoneタスク上に取り残す事象が発生した。

このパッチは3つのterminal遷移に「live foreign claim guard」を追加する。

- 拒否対象は「statusがrunning、claimが未失効、記録された `worker_pid` が呼び出しプロセスと異なる生存プロセスである」場合の匿名呼び出しのみ。拒否時は `terminal_transition_refused` イベントをカードへ記録する。`worker_pid` 未登録のclaim（ラベルclaimerによる同一プロセス運用・テスト規約）は生存する外部workerへ帰属できないため従来挙動を維持する — dispatcher起動の実workerは常に `worker_pid` が登録されるので、インシデント経路の遮断は保たれる。これが本ガードの残余であり、`worker_pid` 未登録の匿名claimは保護対象外である。
- workerは従来どおり自runの `expected_run_id` を渡して所有権を証明する。オペレーターは CLI の `--force`（complete / block / archive に追加）で明示上書きできる。
- 同一プロセスでclaim→terminalする既存の手動・テスト規約、claim未取得タスクへの手動操作、claim所有者プロセスが死んでいる場合の回収操作は従来どおり通る。
- 環境変数ベースのdelegate child保護（`HERMES_DELEGATED_CHILD_CONTEXT`）は子プロセスが自己解除できる原理的限界を持つため、このガードはDB側のchokepoint（`write_txn` 配下の遷移関数）で成立する。

検証: `tests/hermes_cli/test_kanban_terminal_claim_guard.py`（インシデント再現の迂回試験を含む9件）を追加。関連既存回帰（`test_kanban_reclaim_claim_lock_guard.py`、`test_delegate_kanban_isolation.py`、`test_kanban_db.py`）と、`tests/hermes_cli` + `tests/tools/test_kanban_tools.py` の全域をパッチ前後で比較実行して確認する。

## 0002 再spawn前の進捗判定ガード

`detect_crashed_workers` は、workerプロセスが rc=0 で終了したのにタスクが `running` のまま残っている状態を protocol violation と分類し、違反streakが上限（3）未満なら**そのrunが何を生産したかを一切見ずに** `ready` へ戻す。次tickの `dispatch_once` はこれを通常のready カードとして扱い、同一worktree上に第2 workerセッションを起動する。実運転では、コミット済みの成果を残して終了したrunの直後に第2セッションが同じ checkout 上で開始した（`docs/status/m1-supervised-run-2026-08-29.md` 4節課題2）。生産物ゼロのrunの場合は、同じ空振りがstreak上限まで無言で反復する。

このパッチは `check_respawn_guard`（`dispatch_once` が claim 前に呼ぶ既存フック）へ進捗判定を追加する。判定入力は task worktree の git コミットと盤面の run / event 行のみで、AIは使わない。

適用条件は次の全てを満たすカードに限る。`ready` レーン、`workspace_kind` が `worktree`、閉じたrunが1件以上あり、直近の閉じたrun（`rate_limited` は中立として除外）の outcome が `crashed`。これ以外（scratch/dir ワークスペース、初回spawn、review レーン、直近runが completed / blocked / reclaimed / timed_out）は従来挙動のまま。既存の4判定（`rate_limit_cooldown` / `blocker_auth` / `recent_success` / `active_pr`）は先に評価され、優先する。

判定は「worktreeの新規コミット」×「当該runが記録した完了合図（`completed` / `review_requested` イベント）」で決まる。

- コミットあり・合図なし: worktree先端sha 1つにつき1回だけ「回収」再spawnを許可する。次workerへの指示は crashed run の `task_runs.error` へ追記する。worker promptが「前回試行のエラー」として描画するのはこの欄であり（`build_worker_context` の `## Prior attempts on this task` 節）、`tasks.last_failure_error` はspawn経路のどこからも読まれないため指示の伝達には使えない。指示内容は、作業をやり直さず git log と diff で前回runの成果を確認してから `kanban_complete` で報告すること。許可は `respawn_recovery_granted` イベントに先端shaとrun idで記録し、同一先端に対する2回目は `recovery_exhausted` として止める。
- コミットあり・合図あり / コミットなし・合図あり: `completion_signal_lost` として止める。runは自身の終了を報告済みで、失われたのは成果ではなく遷移である。別workerの起動は完了済み作業の重複実行になるため、カードを止めて人へ渡す。
- コミットなし・合図なし: 従来どおり1回だけ再試行を許し、無進捗runが2回連続した時点で `no_progress_blocked` として止める。
- worktreeが読めない（パス未設定・ディレクトリ不在・git checkoutでない・git実行失敗）: `progress_undeterminable` として止める（fail-closed）。
- 判定自体が例外で落ちた: `progress_guard_error` を返し、そのカードのspawnだけを見送る（書込なし）。ガードはdispatcherのカードループから1枚ずつ呼ばれるため、例外を素通しすると異常カード1枚がtick全体を止める。

止める場合は `block_task(kind="needs_input")` でカードを blocked へ落とし、理由コメントを1件残す。blocked遷移を先に実行し、成功した場合のみイベントとコメントを書く。`block_task` は 0001 の live foreign claim guard によって拒否され得る（dispatcherのready読み取りとこの呼び出しの間に別claimが入った場合）ため、先にイベントを書くと重複抑止が働いてカードが blocked でも spawn 対象でもない状態に留まる。拒否時は理由だけを返し、次tickで再試行する。同一状態に対する2回目の停止処置は記録しないため、コメントは状態ごとに1件で、tickごとに増えない。`dry_run` のtickでは判定結果のみを返し、許可記録・コメント・blocked遷移のいずれも書かない。既存の違反streak上限3は緩めず、本ガードの外側の天井として残る。

既知の限界: コミットの帰属はrunの壁時計窓（`started_at`〜`ended_at`）に入る committer date で判定する。run開始時のsha記録を持たないため、run中に main から取り込んだ他タスクのコミットが窓に入れば「進捗あり」と読む。誤って回収許可が出た場合の消費は先端sha 1つにつき1回で、次のrunが無進捗で閉じれば `recovery_exhausted` に落ちる。逆にrun終了後の amend / rebase は committer date が窓外へ動くため「進捗なし」と読む（遮断側）。帰属を決定的にするにはrun開始時のbase shaを記録する必要があり、claim経路の変更を伴うため本パッチには含めない。

検証: `tests/hermes_cli/test_kanban_respawn_progress_guard.py`（4象限・回収指示が worker prompt に現れること・`last_failure_error` 不干渉・回収1回限りの台帳・rate_limited中立・無進捗streak・block拒否時の無記録・fail-closed・例外時のtick継続・レーンとワークスペース種別の適用外・dry_run無書込・dispatcher結合の27件）を追加。関連既存回帰（`test_kanban_db.py`、`test_kanban_review_lifecycle.py`、`test_kanban_terminal_claim_guard.py`）と `tests/hermes_cli/test_kanban*.py` + `tests/tools/test_kanban_tools.py` の全域をパッチ前後で比較実行し、新規失敗がないことを確認する。

## 適用手順（オーナー承認後のみ）

```bash
cd ~/.hermes/hermes-agent
git am ~/projects/pda/integrations/hermes-kanban-governance/0002-*.patch
systemctl --user restart hermes-gateway.service
```

適用はHermes gatewayの再起動を伴うため、finalization kindは `merge-and-restart` 相当。manifest.jsonの `base_commit` が実機HEADと一致することを適用前に確認し、不一致なら適用せずrebaseを検討する。series は番号順に適用する。0001 は base_commit 084cdbf1 の時点で既に適用済みであり、未適用の環境では 0001 → 0002 の順に `git am` する。
