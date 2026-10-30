# pda-common

`before_prompt_build` ごとに共通指示を読み、`appendSystemContext` でエージェントの system prompt に追加します。対象エージェントの絞り込みやキャッシュはありません。読めない場合はエラーの種類だけを記録して続行します。依頼や道具を止める hook、判定による割り当て、依頼者の指定を書き換える処理はありません。

共通指示のファイルは `plugins.entries.pda-common.config.commonFile` に絶対パスで指定します。ミニ PC では、反映用の取り出しの中の `/home/user/pda/deploy/openclaw/common.md` を直接読みます (写しは作りません)。設定が無いときの既定も同じ場所です。Gateway の `HOME` は `/home/user/v03/agent-home` なので、`~` は使いません。

```sh
openclaw plugins install /home/user/pda/plugins/pda/pda-common --link --force
openclaw config set plugins.entries.pda-common.config.commonFile /home/user/pda/deploy/openclaw/common.md
openclaw config set plugins.entries.pda-common.hooks.allowConversationAccess true --strict-json
openclaw plugins inspect pda-common --runtime --json
```

ローカルディレクトリを `--link` で、場所を指したまま導入します。ソースの更新は `/home/user/pda` で `git pull --ff-only` するだけで反映されます。入れ直すときに `uninstall` は使いません (`plugins.entries` の設定が消えます)。共通指示の変更には plugin の再導入や Gateway の再起動は不要です。ログには hook 名、agent/session/run、読込結果、バイト数、SHA-256 を記録し、指示本文と会話は記録しません。

検証はこのディレクトリで `npm test` を実行します。

公式資料: [prompt hook](https://docs.openclaw.ai/plugins/hooks/prompt-and-session)、[hook の有効化](https://docs.openclaw.ai/plugins/hooks)、[plugin の導入](https://docs.openclaw.ai/cli/plugins/install)。動作確認版は OpenClaw 2026.10.1 です。
