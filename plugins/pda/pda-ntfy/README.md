# pda-ntfy

オーナーの手を借りたいときと、オーナーへの返事が届いたときに、スマートフォンへ ntfy で通知する。OpenClaw の Web Push は、ホーム画面に追加した Control UI で購読を済ませたときだけ届く (購読が無いと 1 通も出ない) ので、購読に頼らない別の経路として足す。

## 置き場所の理由

`plugins/pda/`。使うのは公開された仕組み (hook `agent_end`、`before_tool_call`、エージェントのイベントの購読 `agent.events.registerAgentEventSubscription`、プラグインの設定) だけで、OpenClaw の画面や内部の作りには頼らない。

## 通知する出来事

| 出来事 | 拾う口 | 通知の文面 | 押したときの行き先 |
| --- | --- | --- | --- |
| オーナーとの会話 (`agent:<id>:main`、`agent:<id>:dashboard:<uuid>`) への返事 | `agent_end` | 題「[leader] 返事が届きました」、本文は返事の先頭 100 字 | そのセッションの Control UI の URL |
| 失敗して止まった | `agent_end` | 題「[leader] 実行が失敗しました」、本文はエラーの先頭 100 字 | 同上 |
| exec の承認待ち (どのセッションでも) | エージェントのイベント `approval` / `requested` / `pending` | 題「[worker] 承認待ちです」、本文は固定の文 (コマンドは送らない) | `/approve/<approvalId>` |
| `ask_user` でオーナーへの質問 | `before_tool_call` | 題「[leader] 質問が来ています」、本文は質問の先頭 100 字 | そのセッションの URL |

通知しないもの: 子のエージェント (`subagent`)、cron などの返事、本文が空・`NO_REPLY`・`HEARTBEAT_OK` の返事、`sessions_yield` で待機に入った回の返事。

## 設定 (`plugins.entries.pda-ntfy.config`)

| キー | 既定 | 意味 |
| --- | --- | --- |
| `ntfyEnvFile` | `/home/user/.config/claude-login-notify/ntfy.env` | `NTFY_TOPIC`、`NTFY_SERVER` を持つファイルのパス。送るたびに読む。トピックはここにしか書かない (コミット、ログ、設定に値を置かない) |
| `controlUiUrl` | `gateway.publicOrigin` | 通知の行き先の土台 |
| `sessionKinds` | `["main","dashboard"]` | 返事を通知するセッションの種類 |
| `events` | `["reply","approval","question"]` | 有効にする出来事 |
| `excerptChars` | `100` | 本文に載せる文字数 |
| `timeoutMs` | `5000` | 送信の待ち時間 |

`agent_end` を読むので、`plugins.entries.pda-ntfy.hooks.allowConversationAccess` = `true` が要る。

## ログ

`[pda-ntfy] {"kind":"reply","agentId":"leader","sessionKey":"…","runId":"…","outcome":"sent"}`。失敗は `outcome:"failed"` と `code`。トピックと本文は出さない。

## テスト

```sh
cd plugins/pda/pda-ntfy && npm test
```
