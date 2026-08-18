# Hermes core semantic progress patch

このディレクトリは、PDAのOpen WebUI Progress Pipeが利用するHermes Runs APIの`plan.updated`と`message.interim`拡張を、PDAの管理資産として復元可能に保存する。

## 管理対象

- Upstream: `https://github.com/NousResearch/hermes-agent.git`
- 適用基点: `4323c67dcc6048fc8e311cdff7600d3d6a17807f`
- 実稼働候補のsource commits（順序どおり）:
  1. `0778d86c310f9e4607029a5dc222f16bb0fc2d44` — semantic `plan.updated`
  2. `efcee40d0eafc8f2fc4e28600de681e07c225493` — live `message.interim`
- 期待する適用後tree: `a908d85ed237151360c63c542db71df4881aec8e`
- Patch seriesとSHA-256は`manifest.json`を正本とする

第1パッチには、Runs APIの`plan.updated`イベント、capability公開、秘密情報とcredential付きURLのredaction、入力上限・不正JSON・重複IDのfail-closed処理、回帰テストが含まれる。第2パッチには、`interim_assistant_callback`からRuns SSEの`message.interim`への重複防止付きbridge、回帰テスト、API文書が含まれる。いずれも秘密値を含まない。

NousResearchのupstream remoteへは所有者の許可なくpushしない。専用forkも存在しないため、PDA repository上のこのパッチとmanifestを遠隔保存の正本とする。ローカルHermes Git commitだけを唯一の保存先にしない。

## 復元

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
git checkout 4323c67dcc6048fc8e311cdff7600d3d6a17807f
git am /path/to/0001-feat-api-emit-semantic-plan-progress-events.patch \
  /path/to/0002-fix-api-stream-interim-assistant-messages-in-runs.patch
test "$(git rev-parse HEAD^{tree})" = "a908d85ed237151360c63c542db71df4881aec8e"
```

## 検証

```bash
scripts/run_tests.sh   tests/gateway/test_api_server.py   tests/gateway/test_api_server_runs.py
```

さらに実環境では、`/v1/capabilities`の`features.plan_progress_events=true`、Runs SSEのsanitized `plan.updated`、tool前の`message.interim`、Open WebUIでの即時中間表示、5分heartbeat、完了後の追加heartbeatがないことを確認する。Pipe側の管理コード・installer・E2E probeは親ディレクトリにある。

Hermes upstreamを更新する場合は、この基点へ無条件に戻さず、新しいupstream commit上へパッチをrebase/cherry-pickし、上記テストと実経路E2Eを再実行してから切り替える。
