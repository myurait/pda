# (d) ベンダー公式のリモート経路 調査結果 (subagent 出力の要約, 2026-09-18)

## Anthropic Claude Code
- Remote Control — https://code.claude.com/docs/en/remote-control — ローカル PC 上の CLI/VS Code セッションを claude.ai/code・iOS/Android から閲覧・操作、push 受信。Pro/Max/Team/Enterprise、claude.ai ログイン必須。**Team/Enterprise は既定 off、Owner が admin-settings で有効化**。`disableRemoteControl` 管理設定あり。setup-token の長期トークンでは確立不可
- Claude Code on the web / Cloud sessions — https://code.claude.com/docs/en/claude-code-on-the-web — Anthropic 管理インフラで完結。ブラウザ・モバイル app (Code タブ)・desktop app (Cloud)・`claude --cloud`・Routines から開始、PC を閉じても継続。`claude -p "msg" --cloud <id>` でフォローアップ。`--teleport` で cloud→端末。**端末→cloud は desktop app の「Continue in」メニューのみ**。組織ポリシー `allow_remote_sessions`。ZDR 組織不可
- Desktop app (Code タブ) — https://code.claude.com/docs/en/desktop — Local/Cloud/SSH/WSL。Local セッションはスマホから見えない。Remote Control 有効化か「Continue in」で cloud へ
- headless / SDK — https://code.claude.com/docs/en/headless , https://code.claude.com/docs/en/agent-sdk , https://code.claude.com/docs/en/authentication — `claude -p` はサブスクログインで動く。`--bare` は API key 必須。再配布 Agent SDK は「サードパーティ製品に claude.ai ログインを提供することを許可しない (事前承認なし)」。

## OpenAI Codex
- Cloud tasks (ChatGPT web/iOS/Android) — https://developers.openai.com/codex/cloud , https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan — スレッド閲覧、diff レビュー、承認、新規タスク。**2026-05「Work with Codex from anywhere」でローカル Codex セッションもリレー経由でスマホから監視・操作・承認可** (openai.com ブログは 403 で直接 fetch できず、検索要約と報道で裏取り)。Windows は coming soon
- CLI — https://developers.openai.com/codex/cli — `codex cloud` (閲覧・投入・結果 apply)、`codex resume`
- `codex exec` — https://developers.openai.com/codex/noninteractive — 自動化は `CODEX_API_KEY` 推奨、ChatGPT 認証も可
- Admin — https://learn.chatgpt.com/docs/enterprise/admin-setup — 「Allow members to use Codex locally」

## Google Gemini CLI
- 公式モバイル/リモート面: 未発見
- headless — https://geminicli.com/docs/cli/headless/
- ACP mode — https://geminicli.com/docs/cli/acp-mode/ (`--acp`, stdio JSON-RPC)
- 認証 — https://geminicli.com/docs/get-started/authentication/ — **2026-06-18 付で個人 Google アカウントログイン (無料枠/AI Pro/Ultra) を廃止、「Antigravity CLI」へ誘導**、と subagent が報告。残る経路は Gemini API key (無料 250req/日 Flash のみ)、Vertex AI、有償 Code Assist Standard/Enterprise。→ **本体で要検証**
- Workspace 管理 — https://docs.cloud.google.com/gemini/docs/codeassist/control-individuals-access
- Jules 拡張 — https://github.com/gemini-cli-extensions/jules — `/jules <prompt>` で委譲。Jules 公式モバイル app は無し
