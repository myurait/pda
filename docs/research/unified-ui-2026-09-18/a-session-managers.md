# (a) セッション管理・オーケストレーション UI 調査結果 (subagent 出力の要約, 2026-09-18)

## Part A: ≥2 実行器 かつ スマホ到達可
1. Vibe Kanban — https://github.com/BloopAI/vibe-kanban / https://vibekanban.com/docs/supported-coding-agents — Claude Code, Codex, Gemini CLI, Copilot CLI, Amp, Cursor Agent, OpenCode, Droid, Qwen Code。Web UI (kanban+diff)。local npx / Docker self-host。CLI 自身のログインを流用。Apache-2.0。2026-09-18 push。**商用は sunset、OSS community-maintained へ**
2. Happy — https://happy.engineering/ / https://github.com/slopus/happy — Claude Code, Codex (`happy claude` / `happy codex` ラッパー)。iOS/Android/web、push、E2E 暗号化。relay server は self-host 可。MIT。2026-09-18
3. Omnara — https://github.com/omnara-ai/omnara / https://www.omnara.com/ — Claude Code, Codex ラッパー (App Store 記載; 現 README は汎用 agent SDK 寄りで不整合)。iOS/Android/web、push で承認。SaaS or Docker Compose self-host。Apache-2.0。2026-09-18
4. AgentDeck — https://github.com/mantou132/AgentDeck — Claude Code, Codex, Cursor, pi を **ACP** 経由。Tauri mobile ⇄ Relay ⇄ desktop。license 無し。2 stars。2026-09-17
5. amux — https://github.com/mixpeek/amux / https://amux.io — Claude Code, Codex, Gemini CLI, OpenCode, Ollama。Web dashboard :8824 + iOS app、Tailscale/tunnel 前提。Rust 単一バイナリ + SQLite。MIT + Commons Clause。2026-09-18
6. Orca — https://github.com/stablyai/orca — 「any CLI agent」Claude Code, Codex, Cursor, OpenCode, Copilot 等。iOS/Android companion、通知・follow-up。desktop app + remote SSH worktree。MIT。2026-09-18
7. Forge Remote — https://forgeremote.com/ — Claude Code, Codex, Aider ラッパー。iOS (Android 開発中)、push 承認。ユーザー自身の Firebase。closed source、freemium $9.99/mo
8. OmniHarness — https://github.com/danduma/omniharness — Codex (ACP adapter), Claude (claude-agent-acp), Gemini (native ACP), OpenCode (native ACP)。PWA/Electron/VS Code/iOS/Android、Tailscale 等で phone。self-host のみ。AGPL-3.0。17 stars。2026-09-17
9. Agent Orchestrator — https://github.com/AgentWrapper/agent-orchestrator — 27 harness。desktop app 中心、web/mobile は説明文のみで未確認。Apache-2.0。2026-09-18
10. openvide — https://github.com/open-vide/openvide — Codex, Claude Code (Gemini soon)。React Native app、SSH で daemon 接続。MIT。2026-07-06
11. Nimbalyst (Crystal 後継) — https://nimbalyst.com/ — Claude Code, Codex 並走。iOS companion は「monitoring」。license 未確認
12. Terragon (defunct) — https://github.com/terragon-labs/terragon-oss — Claude Code, Codex, Amp, Gemini。2026-01-16 サービス終了、as-is snapshot。Apache-2.0
13. Ona (旧 Gitpod) — https://ona.com/ — Claude Code, Codex。cloud web IDE。mobile は未確認。OpenAI に買収 (2026-06)

## Part B: ≥2 実行器 だが terminal/desktop のみ
- Claude Squad — https://github.com/smtg-ai/claude-squad — TUI、tmux+worktree。AGPL-3.0。2026-08-20
- CCManager — https://github.com/kbwo/ccmanager — Claude Code, Gemini, Codex, Cursor, Copilot, Cline, OpenCode, Kimi, MCode。TUI。MIT。2026-09-13
- Crystal — https://github.com/stravu/crystal — Electron。deprecated→Nimbalyst
- Conductor — https://www.conductor.build/docs/faq — Claude Code, Codex, Cursor。Mac-only local app

## Part C: 単一実行器
- Claude Code Remote Control (`/remote`) — https://code.claude.com/docs/ja/remote-control
- AgentView (`claude agents`, ≥2.1.139) — terminal dashboard (https://zenn.dev/tkou15/articles/claude-code-agentview)
- Gemini-CLI-UI — https://github.com/cruzyjapan/Gemini-CLI-UI
- OpenCode web/serve + OpenCode Portal/Mobile — OpenCode は単一 agent (LLM backend 切替) であり Claude Code/Codex を実行器として起動するものではない

## 未発見
- Symphony 系: 複数 fork あるが mobile/web client 未確認
- Kilo Code: 単一 agent、対象外
