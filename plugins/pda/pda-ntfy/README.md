# pda-ntfy

オーナーへの返事が届いたときと、エージェントからの質問が出たときに、スマートフォンへ ntfy で通知する。**主経路は OpenClaw 本体の Web Push** (ホーム画面に追加した Control UI に直接届き、タップするとそのアプリが開く)。ntfy は、Web Push では補えない情報 (返事・質問の本文の先頭) と、Web Push が出さない失敗の知らせを足す副経路。

## なぜ Click の URL を付けないか

ntfy の Click に https の URL を渡すと、iOS では既定のブラウザ (Safari) で開く。ホーム画面の Web アプリは、外から URL で開く手段が無い (URL スキームもユニバーサルリンクも持たない)。タップで Safari が開くのはオーナーの不満そのものなので、既定では Click を付けない (`clickLinks` = `false`)。ホーム画面のアプリが開くのは、OpenClaw 本体の Web Push の通知だけ。

## 通知の流れ

| 出来事 | Web Push (本体、主) | ntfy (このプラグイン、副) |
| --- | --- | --- |
| 承認待ち | 既定でオン。題「OpenClaw approval requested」、本文「Open OpenClaw to review this request.」。タップで `/approve/<id>` がアプリで開く | 既定では送らない (重複)。`events` に `approval` を足すと送る |
| 返事が届いた (Agent finished) | 設定でオンにしたとき。題「OpenClaw agent finished」、本文「An agent completed its response.」。タップでそのセッションがアプリで開く | 返事の先頭 100 字 (Web Push は本文を載せない設計) |
| `ask_user` の質問 | 設定でオンにしたとき (Agent question)。題「OpenClaw needs an answer」、本文「An agent has a question for you.」。タップで質問の画面 | 質問の先頭 100 字 |
| 実行の失敗 | 該当する分類が無い | エラーの先頭 100 字 |

通知しないもの: 子のエージェント (`subagent`)、cron などの返事、本文が空・`NO_REPLY`・`HEARTBEAT_OK` の返事、`sessions_yield` で待機に入った回の返事 (この回の途中で待機に入っていれば、最後の本文が後に続いても通知しない。道具の名前の接頭辞は問わない。claude-cli の実行では `agent_end` の `messages` に道具の呼び出しが載らないので、`before_tool_call` で `sessions_yield` の呼び出しをセッションごとに覚え、次の `agent_end` で使う。見送ったときは `reason: "yield"` を info に残す)。

## 設定 (`plugins.entries.pda-ntfy.config`)

| キー | 既定 | 意味 |
| --- | --- | --- |
| `ntfyEnvFile` | `/home/user/.config/claude-login-notify/ntfy.env` | `NTFY_TOPIC`、`NTFY_SERVER` を持つファイルのパス。送るたびに読む。トピックはここにしか書かない (コミット、ログ、設定に値を置かない) |
| `clickLinks` | `false` | `true` で ntfy の Click に Control UI の URL を付ける (タップで Safari が開く) |
| `clickUrl` | なし | 指定すると、どの通知も Click にこの URL を付ける。`clickLinks` より優先。公式 iOS アプリ (2026.10.70) を使うなら `openclaw://chat` (下の「公式 iOS アプリのリンク」を読む)。`openclaw://dashboard` は概要ページへ飛ぶので勧めない |
| `controlUiUrl` | `gateway.publicOrigin` | `clickLinks` が `true` のときの URL の土台 |
| `sessionKinds` | `["main","dashboard"]` | 返事を通知するセッションの種類 |
| `sessionKeys` | なし | 通知してよいセッションのキーの一覧 (例: `["agent:leader:main"]`)。指定すると、この一覧に完全に一致するセッションだけを、返事・質問・承認のどれでも通知する。返事では `sessionKinds` の代わりになる。指定が無ければ従来どおり (返事は `sessionKinds`、質問と承認はどのセッションでも) |
| `events` | `["reply","question"]` | 有効にする出来事 (`reply`、`question`、`approval`) |
| `excerptChars` | `100` | 本文に載せる文字数 |
| `timeoutMs` | `5000` | 送信の待ち時間 |

`agent_end` を読むので、`plugins.entries.pda-ntfy.hooks.allowConversationAccess` = `true` が要る。

## ログ

`[pda-ntfy] {"kind":"reply","agentId":"leader","sessionKey":"…","runId":"…","outcome":"sent"}`。失敗は `outcome:"failed"` と `code`。トピックと本文は出さない。

## テスト

```sh
cd plugins/pda/pda-ntfy && npm test
```

## 公式 iOS アプリのリンク

公式 iOS アプリ (App Store 2026.10.70 = ソース v2026.10.7。最新の main も同じ) の URL スキーム `openclaw://` は、特定のエージェントやセッションのチャットを開けない。ソース (`apps/shared/OpenClawKit/Sources/OpenClawKit/DeepLinks.swift`) の `DeepLinkParser.parse` が受けるホストは次の 3 つだけ。

| URL | 動き |
| --- | --- |
| `openclaw://dashboard` | 概要 (Overview) を開く (`NodeAppModel.handleDeepLink` → `RootTabs.handleDashboardNavigationRequest` → `.overview`)。セッションの指定は無い |
| `openclaw://agent?message=…&sessionKey=…` | エージェントへメッセージを送る。端末での確認ダイアログが出て (端末ごとの `key` を付ければ省ける)、送った後にチャットの画面へ移るが、開くのは既に選んでいるセッションで、`sessionKey` は送信先にしか効かない。通知のリンクには使えない |
| `openclaw://gateway?…` / `openclaw://gateway/add?…` | Gateway の接続設定 (設定の画面へ) |

ほかに、ユニバーサルリンク (associated-domains の権限なし)、Handoff (`NSUserActivity` なし)、通知の userInfo による遷移 (APNs の承認通知とウォッチの通知だけ) は無く、App Intents は `StartLiveVoiceIntent` (現在のチャットで音声会話を始める。Shortcuts 専用) だけ。起動引数 `--openclaw-initial-destination`、`--openclaw-chat-session` は URL からは渡せない。

そこで、概要のような別の画面へ飛ばさないため、`clickUrl` には解釈されないホスト `openclaw://chat` を使う。`parse` が `nil` を返してアプリは何もせず、iOS がアプリを前面に出すだけなので、**最後に開いていた画面のまま** 戻れる (起動し直したときは Chat。選ばれるセッションはアプリの既定のもので、通知の元のセッションではない)。アプリが新しく `chat` のようなホストを持ったときは、この URL の意味が変わる。
