import { sendNtfy } from "./ntfy.js";

const DEFAULT_ENV_FILE = "/home/user/.config/claude-login-notify/ntfy.env";
const SILENT_REPLIES = new Set(["NO_REPLY", "HEARTBEAT_OK"]);
const SEEN_APPROVALS_MAX = 200;
// 承認待ちは OpenClaw 本体の Web Push (既定でオン、タップでホーム画面のアプリが開く) が同じ内容を届けるので、既定には入れない。
const DEFAULT_EVENTS = ["reply", "question"];

// agent:<agentId>:main / agent:<agentId>:dashboard:<id> / agent:<agentId>:subagent:<id> ...
export function parseSessionKey(sessionKey) {
  const match = /^agent:([^:]+):(.+)$/.exec(sessionKey ?? "");
  if (!match) return undefined;
  const [, agentId, rest] = match;
  return { agentId, rest, kind: rest.split(":")[0] };
}

// Control UI の URL の規則: main は /chat/<agentId>、それ以外は /chat/<agentId>/~key/<キーから agent:<agentId>: を除き : を / にしたもの>
export function sessionUrl(base, parsed) {
  if (!base || !parsed) return undefined;
  const root = `${base.replace(/\/+$/, "")}/chat/${encodeURIComponent(parsed.agentId)}`;
  return parsed.rest === "main" ? root : `${root}/~key/${parsed.rest.split(":").map(encodeURIComponent).join("/")}`;
}

export function excerpt(text, limit) {
  const flat = String(text ?? "").replace(/\s+/g, " ").trim();
  if (limit <= 0) return "";
  return flat.length > limit ? `${flat.slice(0, limit)}…` : flat;
}

function blocks(message) {
  const content = message?.content;
  if (typeof content === "string") return [{ type: "text", text: content }];
  return Array.isArray(content) ? content : [];
}

// 最後の assistant の message から本文を取り、この回 (最後の user の message より後) に sessions_yield で待機に入ったかを見る。
// 待機に入った回の返事は中間の返事なので通知しない。実行器によって道具の名前に接頭辞 (mcp__openclaw__ など) が付き、
// 型の名前も toolCall / toolcall / tool_use と揺れるので、名前の末尾と大文字小文字を無視した型で見る。
const TOOL_CALL_TYPE = /^(toolcall|tool_use|tooluse)$/i;
const isYieldCall = (part) => TOOL_CALL_TYPE.test(part?.type ?? "") && typeof part.name === "string" && /(^|__)sessions_yield$/.test(part.name);

export function lastAssistantReply(messages) {
  const list = messages ?? [];
  const last = [...list].reverse().find((message) => message?.role === "assistant");
  if (!last) return undefined;
  const parts = blocks(last);
  const text = parts.filter((part) => part?.type === "text" && typeof part.text === "string").map((part) => part.text).join("\n").trim();
  let start = 0;
  list.forEach((message, index) => { if (message?.role === "user") start = index + 1; });
  const yielded = list.slice(start).some((message) => message?.role === "assistant" && blocks(message).some(isYieldCall));
  return { text, yielded };
}

export function createPlugin({ fetchImpl } = {}) {
  return {
    id: "pda-ntfy",
    name: "PDA ntfy notifications",
    register(api) {
      const config = api.pluginConfig ?? {};
      const envFile = config.ntfyEnvFile ?? DEFAULT_ENV_FILE;
      const timeoutMs = config.timeoutMs ?? 5000;
      const excerptChars = config.excerptChars ?? 100;
      const sessionKinds = new Set(config.sessionKinds ?? ["main", "dashboard"]);
      // 指定したときは、この一覧に完全に一致するセッションだけを、どの出来事でも通知する (reply では sessionKinds の代わりになる)。
      const sessionKeys = Array.isArray(config.sessionKeys) ? new Set(config.sessionKeys) : undefined;
      const allowedKey = (sessionKey) => !sessionKeys || sessionKeys.has(sessionKey);
      const events = new Set(config.events ?? DEFAULT_EVENTS);
      const base = config.controlUiUrl ?? api.config?.gateway?.publicOrigin;
      // ntfy の iOS アプリは Click の https を Safari で開く。ホーム画面の Web アプリは外から開けないので、既定では付けない。
      const clickLinks = config.clickLinks === true;
      // clickUrl を指定すると、どの通知もタップでその URL を開く (例: 公式 iOS アプリの openclaw://dashboard)。
      const clickUrl = typeof config.clickUrl === "string" && config.clickUrl.length > 0 ? config.clickUrl : undefined;
      const seenApprovals = new Set();

      // ログにはトピックも本文も出さない。出すのは出来事の種類、エージェント、セッション、結果だけ。
      async function notify(kind, ids, { title, message, click, priority }) {
        const record = { kind, agentId: ids.agentId, sessionKey: ids.sessionKey, runId: ids.runId };
        try {
          await sendNtfy({ envFile, timeoutMs, title, message, click: clickUrl ?? (clickLinks ? click : undefined), priority, fetchImpl });
          api.logger.info(`[pda-ntfy] ${JSON.stringify({ ...record, outcome: "sent" })}`);
        } catch (error) {
          api.logger.warn(`[pda-ntfy] ${JSON.stringify({ ...record, outcome: "failed", code: error.code ?? error.name ?? "SEND_FAILED" })}`);
        }
      }

      function skip(kind, ids, reason) {
        api.logger.debug?.(`[pda-ntfy] ${JSON.stringify({ kind, agentId: ids.agentId, sessionKey: ids.sessionKey, outcome: "skipped", reason })}`);
      }

      if (events.has("reply")) {
        // オーナーとの会話 (main、dashboard) の返事が届いたとき。子のエージェントや cron の返事では通知しない。
        api.on("agent_end", async (event, ctx) => {
          const ids = { agentId: ctx.agentId, sessionKey: ctx.sessionKey, runId: event.runId ?? ctx.runId };
          const parsed = parseSessionKey(ctx.sessionKey);
          if (sessionKeys) {
            if (!parsed || !sessionKeys.has(ctx.sessionKey)) return skip("reply", ids, "session-key");
          } else if (!parsed || !sessionKinds.has(parsed.kind)) return skip("reply", ids, "session-kind");
          const agentId = ctx.agentId ?? parsed.agentId;
          const click = sessionUrl(base, parsed);
          const where = parsed.kind === "main" ? agentId : `${agentId} / ${parsed.kind} ${parsed.rest.split(":")[1]?.slice(0, 8) ?? ""}`.trim();
          if (event.success === false) {
            return notify("reply", ids, { title: `[${where}] 実行が失敗しました`, message: excerpt(event.error, excerptChars) || "エラーで止まりました", click });
          }
          const reply = lastAssistantReply(event.messages);
          if (!reply?.text || SILENT_REPLIES.has(reply.text)) return skip("reply", ids, "no-text");
          if (reply.yielded) return skip("reply", ids, "yield");
          return notify("reply", ids, { title: `[${where}] 返事が届きました`, message: excerpt(reply.text, excerptChars), click });
        });
      }

      if (events.has("approval")) {
        // exec の承認待ち。承認はオーナーしか進められないので、どのセッションの承認でも通知する。
        api.agent.events.registerAgentEventSubscription({
          id: "pda-ntfy-approval",
          description: "exec の承認待ちを ntfy で通知する",
          streams: ["approval"],
          phases: ["requested"],
          payload: "metadata",
          async handle(event) {
            const data = event.data ?? {};
            const ids = { agentId: event.agentId, sessionKey: event.sessionKey, runId: event.runId };
            if (data.status !== "pending") return skip("approval", ids, `status-${data.status}`);
            if (!allowedKey(event.sessionKey)) return skip("approval", ids, "session-key");
            const approvalId = typeof data.approvalId === "string" ? data.approvalId : undefined;
            if (approvalId) {
              if (seenApprovals.has(approvalId)) return skip("approval", ids, "duplicate");
              seenApprovals.add(approvalId);
              if (seenApprovals.size > SEEN_APPROVALS_MAX) seenApprovals.delete(seenApprovals.values().next().value);
            }
            const parsed = parseSessionKey(event.sessionKey);
            const click = base && approvalId ? `${base.replace(/\/+$/, "")}/approve/${encodeURIComponent(approvalId)}` : sessionUrl(base, parsed);
            // コマンドの中身は送らない。承認の画面で確かめる。
            return notify("approval", ids, {
              title: `[${event.agentId ?? parsed?.agentId ?? "?"}] 承認待ちです`,
              message: "コマンドの実行に、あなたの承認が必要です。",
              click,
              priority: 4,
            });
          },
        });
      }

      if (events.has("question")) {
        // ask_user でオーナーへの質問が出たとき。ツールの実行は止めないので、待たずに送る。
        api.on("before_tool_call", (event, ctx) => {
          if (event.toolName !== "ask_user") return;
          const parsed = parseSessionKey(ctx.sessionKey);
          const ids = { agentId: ctx.agentId ?? parsed?.agentId, sessionKey: ctx.sessionKey, runId: event.runId ?? ctx.runId };
          if (!allowedKey(ctx.sessionKey)) return skip("question", ids, "session-key");
          const question = typeof event.params?.question === "string" ? excerpt(event.params.question, excerptChars) : "";
          void notify("question", ids, {
            title: `[${ids.agentId ?? "?"}] 質問が来ています`,
            message: question || "エージェントがあなたの答えを待っています。",
            click: sessionUrl(base, parsed),
            priority: 4,
          });
        });
      }
    },
  };
}

export default createPlugin();
