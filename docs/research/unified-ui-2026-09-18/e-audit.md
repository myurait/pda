# (e) 監査衛星: transcript/telemetry 調査結果 (subagent 出力そのまま, 2026-09-18)

## A. Event/Transcript Export Per Tool

### Claude Code
- OpenTelemetry metrics/events/traces: https://code.claude.com/docs/en/monitoring-usage — events `user_prompt` / `assistant_response` / `tool_result` / `tool_decision`。内容は既定で redact。`OTEL_LOG_USER_PROMPTS=1`, `OTEL_LOG_ASSISTANT_RESPONSES=1`, `OTEL_LOG_TOOL_DETAILS=1`, `OTEL_LOG_TOOL_CONTENT=1` で開放。traces は beta。
- Hooks: https://code.claude.com/docs/en/hooks — Stop (session_id, transcript_path, last_assistant_message), PostToolUse, SessionEnd。redact なし。`"type": "http"` hook で外部 POST 可。
- Local transcript: `~/.claude/projects/<url-encoded-project-path>/<session-id>.jsonl` (二次資料 + hooks doc の transcript_path で裏付け)

### Codex CLI
- OpenTelemetry: https://learn.chatgpt.com/docs/config-file/config-advanced — `[otel]` セクション。`log_user_prompt = false` 既定。otlp-http / otlp-grpc。
- Hooks: https://learn.chatgpt.com/docs/hooks — SessionStart/End, Pre/PostToolUse, UserPromptSubmit, Stop, Interrupt, Pre/PostCompact, SubagentStart/Stop, PermissionRequest。transcript_path 付き。`codex exec` で SessionEnd が不安定という community 報告あり。
- Local transcript: `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl` (二次資料: https://github.com/Victarry/codex-trace)

### Gemini CLI
- OpenTelemetry: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/telemetry.md — logs/metrics/traces。trace attributes は既定無効、`logPrompts` は既定 true。
- Hooks: https://github.com/google-gemini/gemini-cli/blob/main/docs/hooks/reference.md — SessionStart/End, BeforeTool/AfterTool, BeforeAgent/AfterAgent, BeforeModel/AfterModel, Notification, PreCompress。transcript_path 付き。
- Local transcript: 未確認

## B. Backends ingesting from ≥2 agents
- Langfuse — https://langfuse.com/resources/engineering/coding-agent-tracing (Claude Code Stop-hook, Codex plugin ≥0.128, Copilot OTLP)。generic OTLP: https://langfuse.com/integrations/native/opentelemetry。self-host 可。core MIT / enterprise modules 商用 (https://langfuse.com/self-hosting/license-key)
- Arize Phoenix — https://github.com/Arize-ai/phoenix + https://github.com/Arize-ai/coding-harness-tracing (claude-code, cursor, codex)。self-host 可。ELv2 (非 OSI)
- Grafana — https://grafana.com/docs/grafana-cloud/monitor-infrastructure/integrations/integration-reference/integration-claude-code/ ; dashboard https://grafana.com/grafana/dashboards/25052-claude-code/。Grafana OSS AGPLv3
- TheophileDiot/ai-cli-observability — https://github.com/TheophileDiot/ai-cli-observability 「Codex, Claude Code, Gemini CLI」3 つを 1 つの Docker Compose (OTel Collector → Victoria* → Grafana)。Apache-2.0。prompt content は既定で保存しない
- Dynatrace — https://www.dynatrace.com/news/blog/dynatrace-expands-ai-coding-agent-monitoring/ SaaS のみ
- Braintrust (OTLP 受入 https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry, self-host 無し) / LangSmith (OTLP https://docs.langchain.com/langsmith/trace-with-opentelemetry, self-host は Enterprise) / AgentOps (未確認)

## C. Judgment runners
- Langfuse LLM-as-a-Judge — https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge — ingest 時に自動起動、結果を webhook 送出可
- Promptfoo `trajectory:goal-success` — https://www.promptfoo.dev/docs/guides/evaluate-coding-agents/ ; llm-rubric https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/ (CLI/CI)
- Inspect AI — https://github.com/UKGovernmentBEIS/inspect_ai (transcript viewer + scorer, CLI)
- DeepEval — https://deepeval.com/guides/guides-ai-agent-evaluation (pytest gate)
- TraceEval — https://github.com/tej007-awesome/TraceEval (OTel traces 入力の pass/fail gate)

## D. 「エージェントの主張を検証する」OSS (いずれも小規模・新興)
- groundtruth — https://github.com/ogyamada/groundtruth Claude Code Stop hook、末尾要約 vs 実 diff。MIT
- claim-check — https://github.com/bhumik154/claim-check テスト件数の主張を実行して照合。MIT
- coding-flow — https://github.com/LandryPouth/coding-flow 宣言コマンドを実行し exit code を取る
- Upheld — https://github.com/chuofringer/upheld harness-agnostic claims-vs-evidence。MIT
- AgentLiar — https://github.com/dakshjain-1616/AgentLiar 4 検査 + LLM judge、HTTP API あり
- ProofRun — https://github.com/yebiguo/ProofRun (未 fetch)
- claimproof — https://github.com/Cshearer210/claimproof (未 fetch)

## subagent の設計メモ
- 3 ツール共通の信号は OTLP。ただし既定は内容 redact。
- 完全 transcript は local JSONL + Stop/SessionEnd hook で外部へ送るのが確実 (hook は redact なし)。
- D の既存物はすべて同一ホスト・同一セッション内で動く。複数ツールから受ける外部衛星は存在せず、hook-export を 3 ツールへ一般化して out-of-process で判定する形になる。
