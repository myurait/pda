# (c) 指示・文脈共有 調査結果 (subagent 出力の要約, 2026-09-18)

## A. 指示ファイル規約
- agents.md (https://agents.md/) — Agentic AI Foundation (Linux Foundation) 管轄。Codex, Jules, Factory, Aider, Goose, OpenCode, Zed, Warp, VS Code, Devin, Amp, Cursor, RooCode, Gemini CLI, Copilot Coding Agent 等が採用
- Claude Code: https://code.claude.com/docs/en/memory 「Claude Code reads CLAUDE.md, not AGENTS.md」。`@AGENTS.md` import か symlink `CLAUDE.md -> AGENTS.md` が公式推奨パターン
- Codex: https://learn.chatgpt.com/docs/agent-configuration/agents-md — `~/.codex/AGENTS.md` + git root→cwd 階層 concat、32KiB 上限
- Gemini CLI: https://geminicli.com/docs/cli/gemini-md/ — 既定 GEMINI.md、`context.fileName` に `["AGENTS.md","GEMINI.md"]` 指定可
- Cursor: https://cursor.com/docs/rules — AGENTS.md と (CLI では) CLAUDE.md も読む
- Copilot Coding Agent: https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/
- Jules: https://jules.google/docs/ — repo root AGENTS.md 自動
- Amp: https://ampcode.com/docs/customize/agents-md
- OpenCode: https://opencode.ai/docs/rules/ — AGENTS.md / CLAUDE.md 先に見つかった方、`~/.claude/CLAUDE.md` も fallback

## B. 同期ツール
- Ruler https://github.com/intellectronica/ruler — 30+ ターゲット、MIT、2026-09-16 push。最有力
- rulesync https://github.com/dyoshikawa/rulesync — MIT、2026-09-18、1,442★
- ai-rules-sync (PanisHandsome) https://github.com/PanisHandsome/ai-rules-sync — MIT
- ai-rules-sync (lbb00) https://github.com/lbb00/ai-rules-sync — Unlicense、rules/skills/commands/subagents も
- agent_sync https://github.com/yelmuratoff/agent_sync — GPL-3.0
- agentsync https://github.com/x0c/agentsync — MIT、1★
- dotagents https://github.com/shunkakinoki/dotagents — Ruler をラップ
- dotagent https://github.com/johnlindquist/dotagent — 145★

## C. Skills / MCP
- agentskills.io — Anthropic 発の open standard。
  - Claude Code https://code.claude.com/docs/en/skills (Claude 独自 frontmatter 拡張あり)
  - Codex https://learn.chatgpt.com/docs/build-skills (`.agents/skills`, `~/.agents/skills`)
  - Gemini CLI https://geminicli.com/docs/cli/skills/ (`~/.agents/skills/`, `.agents/skills/` も読む)
  - OpenCode https://opencode.ai/docs/skills/ (`.claude/skills/` も読む)
  - Cursor https://cursor.com/docs/context/skills (未 fetch)
- MCP 設定: Claude `.mcp.json`/settings.json `mcpServers` (https://code.claude.com/docs/en/mcp) / Codex `config.toml` `[mcp_servers.<name>]` (https://developers.openai.com/codex/mcp, ChatGPT desktop・CLI・IDE 拡張で共有) / Gemini `settings.json` `mcpServers` (https://geminicli.com/docs/tools/mcp-server/) / Copilot は root key `servers`。**共通ファイル形式は無い**

## D. 共有メモリ・引き継ぎ
- mem0 MCP https://github.com/mem0ai/mem0 (Apache-2.0) docs https://docs.mem0.ai/platform/mem0-mcp — user_id スコープなのでツール横断で同一ストア
- basic-memory https://github.com/basicmachines-co/basic-memory (AGPL-3.0) — Obsidian 互換 Markdown
- 公式 memory server https://github.com/modelcontextprotocol/servers (src/memory)
- mcp-memory-service https://github.com/doobidoo/mcp-memory-service (Apache-2.0)
- セッション引き継ぎ Claude Code→Codex: 公式機能なし。Markdown export を `codex chat --context` に渡す手作業 (https://www.jona.ca/2026/05/exporting-claude-code-session-to-codex.html)
- 「Claude Code と Codex で一つのメモリ」を謳うベンダー公式製品: 見つからず (未確認扱い)

## E. 日本語記事
- Qiita 2026-05-18 https://qiita.com/ennagara128/items/0560f092e0f1451d9faf — 横断記憶共有 5 パターン
- Zenn 2026-02-10 https://zenn.dev/explaza/articles/33f1dd2003c981 — AGENTS.md 実体 + CLAUDE.md symlink

## 支持行列 (要約)
| Tool | AGENTS.md | CLAUDE.md | GEMINI.md | SKILL.md | MCP |
|---|---|---|---|---|---|
| Claude Code | import/symlink のみ | Yes | 未確認 | Yes | Yes |
| Codex | Yes | 未確認 | No | Yes | Yes |
| Gemini CLI | 設定で Yes | 未確認 | Yes | Yes | Yes |
| Cursor | Yes | CLI で Yes | 未確認 | Yes | Yes |
| OpenCode | Yes | Yes | 未確認 | Yes | Yes |
