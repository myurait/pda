# Hermes core エラー分類パッチ（prompt-cacheヒント400）

このディレクトリは、prompt-cacheヒント（`prompt_cache_key` / `prompt_cache_retention`）を名指しするHTTP 400をリトライ可能な`server_error`として分類するhermes-agentパッチを、PDAの管理資産として復元可能に保存する。

## 背景

2026-08-19 11:32–11:44 JST、chatgpt.com Codexバックエンドへのリクエストが「prompt_cache_retention is not supported on this model」（HTTP 400, `code=invalid_parameter`, `param=prompt_cache_retention`）で3回失敗した。hermes-agentは同フィールドをBedrock Mantleホストと対応モデル許可リストに限定して付与し、Codex経路では送信しない。従来の分類ではこの400が非リトライの`format_error`となり、該当ターンが中断してOpen WebUIに応答が返らなかった。経緯の詳細は[`docs/status/hermes-prompt-cache-400-2026-08-19.md`](../../../docs/status/hermes-prompt-cache-400-2026-08-19.md)を参照。

## 管理対象

- Upstream: `https://github.com/NousResearch/hermes-agent.git`
- 適用基点: `0778d86c310f9e4607029a5dc222f16bb0fc2d44`（`integrations/openwebui-hermes-progress/hermes-core/`の第1パッチ適用後commit）
- Source commit: `9a9f72812d27108ae7d4e3b0b23010096c6d929b`
- 期待する適用後tree: `2653073b0dc95636c5f8da464d168bcda47ab2d0`
- Patch seriesとSHA-256は`manifest.json`を正本とする

パッチは`agent/error_classifier.py`の`_classify_400`に、bodyの`error.param`またはメッセージがprompt-cacheヒントを名指しする400を`FailoverReason.server_error`（retryable）として返すガードを追加する。回帰テスト3件を含み、秘密値を含まない。

NousResearchのupstream remoteへは所有者の許可なくpushしない。PDA repository上のこのパッチとmanifestを遠隔保存の正本とする。

## 復元

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
git checkout 0778d86c310f9e4607029a5dc222f16bb0fc2d44
git am /path/to/0001-fix-errors-retry-400s-that-reject-prompt-cache-hints.patch
test "$(git rev-parse HEAD^{tree})" = "2653073b0dc95636c5f8da464d168bcda47ab2d0"
```

## 検証

```bash
scripts/run_tests.sh tests/agent/test_error_classifier.py
```

100 passed（本パッチ由来の`TestPromptCacheHintRejection` 3件を含む）。

Hermes upstreamを更新する場合は、この基点へ無条件に戻さず、新しいupstream commit上へパッチをrebase/cherry-pickし、上記テストを再実行してから切り替える。
