# pda-common

`before_prompt_build` ごとに共通指示を読み、`appendSystemContext` でエージェントの system prompt に追加します。対象エージェントの絞り込みやキャッシュはありません。読めない場合はエラーの種類だけを記録して続行します。依頼や道具を止める hook、判定による割り当て、依頼者の指定を書き換える処理はありません。

既定の配布先は `/home/user/v03/openclaw/pda/common.md` です。Gateway の `HOME` は `/home/user/v03/agent-home` なので、`~` は使いません。別の配置では `plugins.entries.pda-common.config.commonFile` に絶対パスを指定します。

```sh
mkdir -p /home/user/v03/openclaw/pda
cp deploy/openclaw/common.md /home/user/v03/openclaw/pda/common.md
/home/user/v03/openclaw/oc plugins install ./deploy/openclaw/plugins/pda-common --force --accept-capabilities
/home/user/v03/openclaw/oc plugins enable pda-common
/home/user/v03/openclaw/oc config set plugins.entries.pda-common.hooks.allowConversationAccess true --strict-json
/home/user/v03/openclaw/oc plugins inspect pda-common --runtime --json
```

ローカルディレクトリを公式 CLI でコピーして導入します。ソースの更新には同じ install コマンドを使います。共通指示の変更には plugin の再導入や Gateway の再起動は不要です。ログには hook 名、agent/session/run、読込結果、バイト数、SHA-256 を記録し、指示本文と会話は記録しません。

検証はこのディレクトリで `npm test` を実行します。

公式資料: [prompt hook](https://docs.openclaw.ai/plugins/hooks/prompt-and-session)、[hook の有効化](https://docs.openclaw.ai/plugins/hooks)、[plugin の導入](https://docs.openclaw.ai/cli/plugins/install)。動作確認版は OpenClaw 2026.10.1 です。
