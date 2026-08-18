# Hermes core semantic progress patch

このディレクトリは、PDAのOpen WebUI Progress Pipeが利用するHermes Runs APIの`plan.updated`拡張を、PDAの管理資産として復元可能に保存する。

## 管理対象

- Upstream: `https://github.com/NousResearch/hermes-agent.git`
- 適用基点: `4323c67dcc6048fc8e311cdff7600d3d6a17807f`
- 実稼働で検証したsource commit: `0778d86c310f9e4607029a5dc222f16bb0fc2d44`
- 期待する適用後tree: `f636609155e6e9bbaf49282ec915f869ebe0f836`
- Patch: `0001-feat-api-emit-semantic-plan-progress-events.patch`
- Patch SHA-256: `973b9a9af9204ab5910e5bdadea48d42605cf1b9e5f6d9dc6dea5671141d1d4a`

パッチには、Runs APIの`plan.updated`イベント、capability公開、秘密情報とcredential付きURLのredaction、入力上限・不正JSON・重複IDのfail-closed処理、回帰テスト、API文書が含まれる。秘密値は含まない。

NousResearchのupstream remoteへは所有者の許可なくpushしない。専用forkも存在しないため、PDA repository上のこのパッチとmanifestを遠隔保存の正本とする。ローカルHermes Git commitだけを唯一の保存先にしない。

## 復元

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
git checkout 4323c67dcc6048fc8e311cdff7600d3d6a17807f
git am /path/to/0001-feat-api-emit-semantic-plan-progress-events.patch
test "$(git rev-parse HEAD^{tree})" = "f636609155e6e9bbaf49282ec915f869ebe0f836"
```

## 検証

```bash
scripts/run_tests.sh   tests/gateway/test_api_server.py   tests/gateway/test_api_server_runs.py
```

さらに実環境では、`/v1/capabilities`の`features.plan_progress_events=true`、Runs SSEのsanitized `plan.updated`、Open WebUIの5分heartbeat、完了後の追加heartbeatがないことを確認する。Pipe側の管理コード・installer・E2E probeは親ディレクトリにある。

Hermes upstreamを更新する場合は、この基点へ無条件に戻さず、新しいupstream commit上へパッチをrebase/cherry-pickし、上記テストと実経路E2Eを再実行してから切り替える。
