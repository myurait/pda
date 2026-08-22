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

## 適用手順（オーナー承認後のみ）

```bash
cd ~/.hermes/hermes-agent
git am ~/projects/pda/integrations/hermes-kanban-governance/0001-*.patch
systemctl --user restart hermes-gateway.service
```

適用はHermes gatewayの再起動を伴うため、finalization kindは `merge-and-restart` 相当。manifest.jsonの `base_commit` が実機HEADと一致することを適用前に確認し、不一致なら適用せずrebaseを検討する。
