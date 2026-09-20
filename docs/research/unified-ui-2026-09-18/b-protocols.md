# (b) プロトコル統一 (ACP 等) 調査結果 (subagent 出力の要約, 2026-09-18)

## ACP (Agent Client Protocol, https://agentclientprotocol.com)
- registry JSON https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json — 41 entries
- adapters:
  - Claude: https://github.com/agentclientprotocol/claude-agent-acp (Claude Agent SDK ラップ、protocol-org 管理、Anthropic 公式ではない。Apache-2.0、2026-09-17)
  - Codex: https://github.com/agentclientprotocol/codex-acp (Codex CLI 依存、OpenAI 公式ではない。license 表記不一致、2026-09-18)
  - Gemini CLI: native `gemini --acp` (Google 公式、Apache-2.0、2026-09-18)
  - Google Antigravity: `antigravity-acp` 別 entry、proprietary binary
  - goose (→ aaif-goose/goose), OpenCode (→ anomalyco/opencode, MIT), Cline, Cursor, Copilot CLI, Qwen Code, Kimi CLI, Devin, Droid, Junie ほか
- clients (https://agentclientprotocol.com/get-started/clients):
  - editors: Zed, JetBrains, VS Code 拡張, Neovim, Emacs, Sublime, Obsidian...
  - web UI: Anycode, Casper, DeepChat, Kepler (GitKraken), Sidequery...
  - headless/orchestration: acpx, Remote Agent Server (self-hosted ACP execution gateway), Kronos (scheduler dashboard), Jockey, CompozyOS, stdio Bus
  - mobile: Happy, Runmote (QR で任意 ACP agent を phone から), Shellular, Mobvibe, Agmente, Ferngeist, VACP
  - messaging bridges: Telegram/Discord/Slack/Matrix 等
- spec: `session/new`, `session/load` (履歴再生), `session/resume` (stabilized、履歴無しで再接続 https://agentclientprotocol.com/announcements/session-resume-stabilized)。v2 RFD で `session/list` 等を必須化 (https://agentclientprotocol.com/rfds/v2/required-session-methods)。remote transport は RFD Active 2026-07-02 (Streamable HTTP / WebSocket, https://agentclientprotocol.com/rfds/streamable-http-websocket-transport)、現行既定は stdio
- 同時複数 session の保証: v1 で明文なし (未確認)

## ベンダー native surface
- Claude Agent SDK sessions https://code.claude.com/docs/en/agent-sdk/sessions — resume/continue/fork は保存 transcript に対して。実行中 session への attach 不可
- `claude -p` https://code.claude.com/docs/en/headless — `--output-format stream-json`, `--input-format stream-json`。`--continue` は「終了した background session は開けるが実行中は開けない」(v2.1.257+)
- Codex App Server https://learn.chatgpt.com/docs/app-server , https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md — stdio JSONL 既定、WebSocket は experimental。`thread/start` `thread/resume` `thread/fork`。ChatGPT login / API key 両対応
- `codex exec` https://learn.chatgpt.com/docs/non-interactive-mode — `codex exec resume` は完了 session のみ
- Gemini CLI headless https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/headless.md / ACP https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/acp-mode.md (`newSession`, `loadSession`, `prompt`, `cancel`, `setSessionMode`)
- **Gemini CLI → Antigravity CLI**: https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/ 「On June 18, 2026, Gemini CLI ... will stop serving requests for Google AI Pro and Ultra, as well as those using it free of charge」。Standard/Enterprise Code Assist は継続。repo は archive されず活動中。個人 API key で動くかは未確認

## AG-UI / A2A
- CopilotKit × Claude Agent SDK https://docs.copilotkit.ai/claude-sdk-typescript/backend/ag-ui — SDK レベルの bridge、CLI session の描写ではない
- A2A https://a2a-protocol.org/latest/ — coding-agent UI 統一との関連なし

## 実行器抽象
- Vibe Kanban — 10+ agent の executor profile。shutdown 告知 https://www.vibekanban.com/blog/shutdown (2026-04-10、OSS として継続)
- OpenCode provider model は LLM API 抽象であり executor 抽象ではない (https://opencode.ai/docs/providers/)
- ACP 自体が de facto の executor 抽象層 (Remote Agent Server, Jockey, Kronos 等はその上に構築)
- Vercel AI SDK community ACP provider https://ai-sdk.dev/providers/community-providers/acp — ACP agent (Claude Code, Gemini CLI, Codex CLI) を LanguageModel interface で
