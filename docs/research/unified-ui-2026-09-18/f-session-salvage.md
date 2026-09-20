# (f) 既存セッションのサルベージ (subagent 出力の要約, 2026-09-19)

## 保存形式
- Claude Code (CLI/desktop 共通): `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`。hooks doc の transcript_path で公式裏付け (https://code.claude.com/docs/en/hooks)
- Codex: `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (openai/codex discussion #24042)。7 日超で `.jsonl.zst` 圧縮は未確認
- ChatGPT web: Settings → Data Controls → Export → `conversations.json` (help.openai.com は 403、未直接確認)
- Gemini CLI: `~/.gemini/tmp/<project_hash>/chats/` (`/chat save`)、checkpoints は同 `checkpoints/` (https://geminicli.com/docs/cli/session-management/)

## パーサ・エクスポータ
- claude-code-log https://github.com/daaain/claude-code-log — JSONL → HTML/Markdown。MIT
- chatgpt-to-markdown https://github.com/sanand0/chatgpt-to-markdown — ChatGPT と Claude の export JSON → Markdown。MIT、v1.13.0 2026-06-11
- ai-memory-reader https://github.com/nvwalj/ai-memory-reader — Codex rollout viewer (macOS)。GPL-3.0
- agent-sessions https://github.com/jazzyalex/agent-sessions — 「Codex, Claude Code, Cursor, and 12 other coding agents」をローカルで検索する Mac app。読み取り・再開。MIT
- 未 fetch: cc2md, claude-code-chat-export, codex-replay, agent-session-view, claude-code-history-viewer
- Gemini CLI 専用エクスポータ: 見つからず
- 複数ベンダーを単一の自前ストアへ書き込む統合ツール: 見つからず (agent-sessions は読み取りのみ)
