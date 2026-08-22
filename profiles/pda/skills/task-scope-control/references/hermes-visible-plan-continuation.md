# Visible plan, continued execution, and direct-command boundaries

Use this reference when a Hermes task must show an immediate plan without stopping work, or when a direct `report`, `status`, `stop`, or `commit` command arrives during a longer run.

## Reliable foreground pattern

A completed text-only assistant response terminates `run_conversation()`. The same foreground run cannot resume by itself after that response. To show a plan and continue, keep the plan inside the live tool-calling loop:

1. Generate a one-to-three-line plan as visible assistant commentary.
2. Include the first required tool call in that same assistant step.
3. Let Hermes execute the tool result and continue the loop.
4. Send the final assistant response only after the requested completion or an honest blocker.

The provider-facing sequence remains valid: `user -> assistant(content + tool_calls) -> tool(s) -> assistant(final)`. This does not require another human turn.

If the owner specifically needs the first message to be a completed standalone response, dispatch a tracked background run or subagent before returning it. The foreground response may then close while the background worker continues and later reports its result.

## Hermes surfaces

Hermes v0.20.2 exposes interim commentary through `interim_assistant_callback`; TUI/desktop surfaces emit `message.interim`, and streaming API surfaces can expose live `message.delta` events. `display.interim_assistant_messages` gates interim display on supported gateway surfaces.

`agent.intent_ack_continuation` is a recovery path for a model that announces future action but emits no tool call. `auto` is scoped to the Codex response path; `true` enables all API modes, and the loop caps continuation nudges. Treat it as a heuristic fallback, not the primary design: wording and language affect detection, so a Japanese plan-only message may still terminate. The reliable contract is commentary plus the first tool call.

Re-check current Hermes documentation and installed source before changing transport behavior; event names and provider adapters can evolve.

## Direct commands during a live run

Do not merge a direct imperative invisibly into a broader objective.

- `report` or `status`: answer from already verified state at the next visible boundary; do not investigate first merely to polish the report.
- `stop`: stop starting new work, request safe interruption, and report what completed, remains running, or never started.
- `commit`: freeze optional exploration and run the bounded repository-closeout profile on task-owned artifacts only. Execute it or return the exact blocker.

A queued steer is not proof that the agent consumed the instruction. Surface whether the command is queued, started, completed, blocked, or undelivered. If a steer lands after the final tool boundary, replay it as the next user command rather than losing it.

## Verification used when this reference was added

The installed Hermes source was inspected at `agent/conversation_loop.py`, `agent/agent_runtime_helpers.py`, `gateway/platforms/api_server.py`, and `tui_gateway/server.py`. Targeted intent-continuation and interim-stream-hook tests passed (17 tests).