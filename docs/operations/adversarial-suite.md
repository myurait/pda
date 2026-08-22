# 敵対的迂回テストスイート

- Status: active（goal M1 / ADR D5 の運用台帳。統治変更を伴うリリースは本スイートの全遮断を確認してから review に載せる）
- 最終更新: 2026-08-22

## 目的

自律改善の統制は「プロンプト規律は強制力ではない」という実証（2026-08-22 の各インシデント）を前提に、迂回の試みが機械的に遮断されることをテストで証明し続ける。新しい迂回が実運用で観測されたら、ポストモーテム起票と同時に本スイートへ再現テストを追加する。

## カバーする迂回と所在

- **保護環境変数の自己解除後の完了偽装**（delegate child が保護変数を外して親カードを完了させた事象）
  - `tmp` 外の正本: Hermes 管理パッチ `integrations/hermes-kanban-governance/` に同梱の `tests/hermes_cli/test_kanban_terminal_claim_guard.py`（適用済み Hermes ツリー側で実行）
- **本番タスク台帳への試験到達**（worker 環境の DB 固定が試験の分離を突破した事象）
  - `conftest.py`（repo 直下）+ `operations/improvement/tests/test_kanban_isolation.py`
- **runtime 設定の改竄による再有効化**（停止中に runtime config の enabled を直接書き換える試み）
  - `operations/improvement/tests/test_pda_improvement_cycle.py::test_tampered_runtime_config_cannot_outrank_committed_policy`
- **停止中 policy 下での活性化試行**
  - `operations/improvement/tests/test_install.py::test_activation_is_refused_while_the_committed_policy_is_suspended`
- **スコープ外 action の expansion 迂回**（審査なしの拡張、予算超過、審査者不在時の fail-open）
  - `integrations/hermes-scope-gate/tests/test_scope_gate.py` の G3 テスト群（zero-budget deny / fail-closed / one-use / TTL / 予算超過）

未カバー（ADR レビュー後に追加する）:

- worker による統治ファイル（ゲート policy・ADR・承認記録簿）変更の finalization 拒否（ADR D3 依存）
- 検証者・review 専用主体による lifecycle 変更試行の網羅（検証者ステージの実装は M2）

## 実行方法

pda リポジトリ側（ミニPC、隔離クローンで実行）:

```bash
env -u HERMES_KANBAN_DB PYTHONPATH=$HOME/.hermes/hermes-agent \
  ~/.hermes/hermes-agent/venv/bin/python -m pytest \
  operations/improvement/tests integrations/hermes-pda-approvals/tests -q
```

scope gate 側:

```bash
cd integrations/hermes-scope-gate
uv run --with pytest --with jsonschema --with pyyaml python -m pytest tests -q \
  --ignore=tests/test_hermes_integration.py
```

Hermes パッチ側（適用済みツリーの隔離クローンで実行）:

```bash
env -u HERMES_KANBAN_DB PYTHONPATH=$PWD \
  ~/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/hermes_cli/test_kanban_terminal_claim_guard.py \
  tests/hermes_cli/test_kanban_reclaim_claim_lock_guard.py \
  tests/tools/test_delegate_kanban_isolation.py -q
```

注意: フルスイートを複数並列で走らせない（ミニPCは12GiBで、並列実行はOOMによりホスト全体を巻き込む。2026-08-22 実測）。
