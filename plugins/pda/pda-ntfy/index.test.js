import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createPlugin, parseSessionKey, sessionUrl, excerpt } from "./index.js";

const SECRET_TOPIC = "secret-topic-for-test";
const BASE = "https://gw.example:19114";

async function setup(config = {}) {
  const dir = await mkdtemp(join(tmpdir(), "pda-ntfy-"));
  const envFile = join(dir, "ntfy.env");
  await writeFile(envFile, `NTFY_TOPIC=${SECRET_TOPIC}\nNTFY_SERVER=https://ntfy.example/\n`);
  const sent = [];
  const logs = [];
  const hooks = {};
  let subscription;
  const fetchImpl = async (url, init) => {
    sent.push({ url, body: JSON.parse(init.body), headers: init.headers });
    return { ok: true, status: 200 };
  };
  createPlugin({ fetchImpl }).register({
    pluginConfig: { ntfyEnvFile: envFile, controlUiUrl: BASE, ...config },
    config: {},
    logger: { info: (l) => logs.push(l), warn: (l) => logs.push(l), debug: (l) => logs.push(l) },
    on: (name, handler) => { hooks[name] = handler; },
    agent: { events: { registerAgentEventSubscription: (s) => { subscription = s; } } },
  });
  return { dir, sent, logs, hooks, subscription, envFile, cleanup: () => rm(dir, { recursive: true, force: true }) };
}

const assistant = (text, extra = []) => ({ role: "assistant", content: [{ type: "text", text }, ...extra] });

test("session key parsing and Control UI URLs follow the documented rule", () => {
  assert.equal(sessionUrl(BASE, parseSessionKey("agent:leader:main")), `${BASE}/chat/leader`);
  assert.equal(sessionUrl(`${BASE}/`, parseSessionKey("agent:leader:dashboard:3205-aa")), `${BASE}/chat/leader/~key/dashboard/3205-aa`);
  assert.equal(parseSessionKey("agent:worker:subagent:x").kind, "subagent");
  assert.equal(parseSessionKey("nonsense"), undefined);
  assert.equal(excerpt("a\n\n b  c", 100), "a b c");
  assert.equal(excerpt("あいうえお", 3), "あいう…");
});

test("by default no click URL is sent, so tapping never opens Safari", async () => {
  const t = await setup();
  try {
    await t.hooks.agent_end({ runId: "r1", success: true, messages: [assistant("やあ")] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    await t.hooks.agent_end({ success: false, error: "boom", messages: [] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 2);
    for (const { body } of t.sent) assert.ok(!("click" in body));
  } finally { await t.cleanup(); }
});

test("default events leave approvals to the built-in Web Push; approval can be opted in", async () => {
  const t = await setup();
  try {
    assert.equal(t.subscription, undefined);
    assert.equal(typeof t.hooks.agent_end, "function");
    assert.equal(typeof t.hooks.before_tool_call, "function");
  } finally { await t.cleanup(); }
});

test("replies in the owner's conversation notify with excerpt, title and click URL when clickLinks is on", async () => {
  const t = await setup({ clickLinks: true });
  try {
    const long = "あ".repeat(150);
    await t.hooks.agent_end({ runId: "r1", success: true, messages: [{ role: "user", content: "hi" }, assistant(long)] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 1);
    const [{ url, body }] = t.sent;
    assert.equal(url, "https://ntfy.example");
    assert.equal(body.topic, SECRET_TOPIC);
    assert.equal(body.title, "[leader] 返事が届きました");
    assert.equal(body.message, `${"あ".repeat(100)}…`);
    assert.equal(body.click, `${BASE}/chat/leader`);
    await t.hooks.agent_end({ runId: "r2", success: true, messages: [assistant("やあ")] }, { agentId: "leader", sessionKey: "agent:leader:dashboard:32052b81-0e13" });
    assert.equal(t.sent[1].body.title, "[leader / dashboard 32052b81] 返事が届きました");
    assert.equal(t.sent[1].body.click, `${BASE}/chat/leader/~key/dashboard/32052b81-0e13`);
  } finally { await t.cleanup(); }
});

test("child agents, cron, empty replies, silent replies and yields do not notify", async () => {
  const t = await setup();
  try {
    const run = (key, messages, extra = {}) => t.hooks.agent_end({ runId: "r", success: true, messages, ...extra }, { agentId: "worker", sessionKey: key });
    await run("agent:worker:subagent:abc", [assistant("途中")]);
    await run("agent:leader:cron:abc", [assistant("x")]);
    await run("agent:leader:main", [{ role: "assistant", content: [{ type: "toolCall", name: "exec" }] }]);
    await run("agent:leader:main", [assistant("NO_REPLY")]);
    await run("agent:leader:main", [assistant("待ちます", [{ type: "toolCall", name: "sessions_yield" }])]);
    await t.hooks.agent_end({ messages: [assistant("x")], success: true }, {});
    assert.equal(t.sent.length, 0);
  } finally { await t.cleanup(); }
});

test("failed runs in the owner's conversation notify with the error excerpt", async () => {
  const t = await setup();
  try {
    await t.hooks.agent_end({ success: false, error: "boom", messages: [] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent[0].body.title, "[leader] 実行が失敗しました");
    assert.equal(t.sent[0].body.message, "boom");
  } finally { await t.cleanup(); }
});

test("pending approvals notify once per approval from any session, without the command", async () => {
  const t = await setup({ events: ["approval"], clickLinks: true });
  try {
    const event = { runId: "r", sessionKey: "agent:worker:subagent:abc", agentId: "worker", data: { phase: "requested", status: "pending", approvalId: "ap-1", command: "rm -rf secret-thing" } };
    await t.subscription.handle(event);
    await t.subscription.handle(event);
    await t.subscription.handle({ ...event, data: { ...event.data, approvalId: "ap-2", status: "unavailable" } });
    assert.equal(t.sent.length, 1);
    assert.equal(t.sent[0].body.title, "[worker] 承認待ちです");
    assert.equal(t.sent[0].body.click, `${BASE}/approve/ap-1`);
    assert.equal(t.sent[0].body.priority, 4);
    assert.ok(!JSON.stringify(t.sent[0].body).includes("secret-thing"));
    assert.deepEqual(t.subscription.streams, ["approval"]);
  } finally { await t.cleanup(); }
});

test("ask_user notifies without blocking the tool call; other tools are ignored", async () => {
  const t = await setup();
  try {
    assert.equal(t.hooks.before_tool_call({ toolName: "exec", params: {} }, { sessionKey: "agent:leader:main" }), undefined);
    assert.equal(t.hooks.before_tool_call({ toolName: "ask_user", params: { question: "どちらにしますか" } }, { agentId: "leader", sessionKey: "agent:leader:main" }), undefined);
    for (let i = 0; i < 100 && t.sent.length === 0; i++) await new Promise((resolve) => setTimeout(resolve, 5));
    assert.equal(t.sent.length, 1);
    assert.equal(t.sent[0].body.title, "[leader] 質問が来ています");
    assert.equal(t.sent[0].body.message, "どちらにしますか");
    assert.ok(!("click" in t.sent[0].body));
  } finally { await t.cleanup(); }
});

test("send failures and unreadable env files never throw, and logs never contain the topic or body", async () => {
  const t = await setup();
  try {
    await rm(t.envFile);
    await t.hooks.agent_end({ success: true, messages: [assistant("本文の秘密")] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.ok(t.logs.some((l) => l.includes('"outcome":"failed"') && l.includes('"code":"ENOENT"')));
    await writeFile(t.envFile, `NTFY_TOPIC=${SECRET_TOPIC}\n`);
    await t.hooks.agent_end({ success: true, messages: [assistant("本文の秘密")] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 1);
    assert.equal(t.sent[0].url, "https://ntfy.sh");
    assert.ok(t.logs.some((l) => l.includes('"outcome":"sent"')));
    assert.ok(t.logs.every((l) => !l.includes(SECRET_TOPIC) && !l.includes("本文の秘密")));
  } finally { await t.cleanup(); }
});

test("events config limits which hooks register", async () => {
  const t = await setup({ events: ["approval"] });
  try {
    assert.equal(t.hooks.agent_end, undefined);
    assert.equal(t.hooks.before_tool_call, undefined);
    assert.ok(t.subscription);
  } finally { await t.cleanup(); }
});

test("clickUrl sends every notification to the fixed URL, ahead of clickLinks", async () => {
  const t = await setup({ clickUrl: "openclaw://dashboard", clickLinks: true });
  try {
    await t.hooks.agent_end({ runId: "r1", success: true, messages: [assistant("やあ")] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 1);
    assert.equal(t.sent[0].body.click, "openclaw://dashboard");
  } finally { await t.cleanup(); }
});

test("sessionKeys limits reply, question and approval to the exact listed sessions", async () => {
  const t = await setup({ sessionKeys: ["agent:leader:main"], events: ["reply", "question", "approval"], sessionKinds: ["main", "dashboard"] });
  try {
    const reply = (agentId, sessionKey) => t.hooks.agent_end({ runId: "r", success: true, messages: [assistant("やあ")] }, { agentId, sessionKey });
    await reply("leader", "agent:leader:main");
    assert.equal(t.sent.length, 1);
    await reply("worker", "agent:worker:main");
    await reply("auditor", "agent:auditor:main");
    await reply("leader", "agent:leader:dashboard:32052b81-0e13");
    await reply("worker", "agent:worker:subagent:abc");
    assert.equal(t.sent.length, 1);

    t.hooks.before_tool_call({ toolName: "ask_user", params: { question: "q" } }, { agentId: "worker", sessionKey: "agent:worker:main" });
    t.hooks.before_tool_call({ toolName: "ask_user", params: { question: "q" } }, { agentId: "leader", sessionKey: "agent:leader:main" });
    for (let i = 0; i < 100 && t.sent.length < 2; i++) await new Promise((resolve) => setTimeout(resolve, 5));
    await new Promise((resolve) => setTimeout(resolve, 30));
    assert.equal(t.sent.length, 2);
    assert.equal(t.sent[1].body.title, "[leader] 質問が来ています");

    const approval = (id, sessionKey, agentId) => ({ runId: "r", sessionKey, agentId, data: { phase: "requested", status: "pending", approvalId: id } });
    await t.subscription.handle(approval("ap-1", "agent:worker:subagent:abc", "worker"));
    await t.subscription.handle(approval("ap-2", "agent:auditor:main", "auditor"));
    assert.equal(t.sent.length, 2);
    await t.subscription.handle(approval("ap-3", "agent:leader:main", "leader"));
    assert.equal(t.sent.length, 3);
    assert.equal(t.sent[2].body.title, "[leader] 承認待ちです");
  } finally { await t.cleanup(); }
});

test("sessionKeys can list a dashboard session, which sessionKinds alone would not allow", async () => {
  const t = await setup({ sessionKeys: ["agent:leader:dashboard:abc"], sessionKinds: ["main"] });
  try {
    await t.hooks.agent_end({ success: true, messages: [assistant("やあ")] }, { agentId: "leader", sessionKey: "agent:leader:dashboard:abc" });
    await t.hooks.agent_end({ success: true, messages: [assistant("やあ")] }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 1);
  } finally { await t.cleanup(); }
});

test("without sessionKeys, other agents' main sessions notify as before and questions come from any session", async () => {
  const t = await setup();
  try {
    await t.hooks.agent_end({ success: true, messages: [assistant("やあ")] }, { agentId: "worker", sessionKey: "agent:worker:main" });
    await t.hooks.agent_end({ success: true, messages: [assistant("やあ")] }, { agentId: "leader", sessionKey: "agent:leader:dashboard:abc" });
    await t.hooks.agent_end({ success: true, messages: [assistant("やあ")] }, { agentId: "worker", sessionKey: "agent:worker:subagent:abc" });
    assert.equal(t.sent.length, 2);
    t.hooks.before_tool_call({ toolName: "ask_user", params: { question: "q" } }, { agentId: "worker", sessionKey: "agent:worker:subagent:abc" });
    for (let i = 0; i < 100 && t.sent.length < 3; i++) await new Promise((resolve) => setTimeout(resolve, 5));
    assert.equal(t.sent.length, 3);
  } finally { await t.cleanup(); }
});

test("a run that yielded earlier does not notify, whatever the tool name prefix or type spelling", async () => {
  const t = await setup();
  try {
    const messages = [
      { role: "user", content: "やって" },
      assistant("", [{ type: "toolcall", name: "mcp__openclaw__sessions_spawn" }]),
      assistant("", [{ type: "toolcall", name: "mcp__openclaw__sessions_yield" }]),
      assistant("作業者に渡しました。待っています。"),
    ];
    await t.hooks.agent_end({ runId: "r1", success: true, messages }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 0);
    const later = [...messages, { role: "user", content: "完了の知らせ" }, assistant("終わりました。")];
    await t.hooks.agent_end({ runId: "r2", success: true, messages: later }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 1);
  } finally { await t.cleanup(); }
});

test("claude-cli: a yield seen only through before_tool_call (messages hold the final text alone) does not notify, and the next run does", async () => {
  const t = await setup();
  try {
    const ctx = { agentId: "leader", sessionKey: "agent:leader:main" };
    const messages = [{ role: "user", content: "やって" }, assistant("2 つの作業は作業者が進めています。")];
    for (const toolName of ["sessions_yield", "mcp__openclaw__sessions_yield"]) {
      assert.equal(t.hooks.before_tool_call({ toolName, params: {} }, { ...ctx, runId: "r1" }), undefined);
      await t.hooks.agent_end({ runId: "r1", success: true, messages }, ctx);
      assert.equal(t.sent.length, 0);
      assert.ok(t.logs.some((l) => l.includes('"reason":"yield"') && l.includes('"via":"tool-hook"')));
    }
    await t.hooks.agent_end({ runId: "r2", success: true, messages }, ctx);
    assert.equal(t.sent.length, 1);
  } finally { await t.cleanup(); }
});

test("a yield in one session does not silence another session, and other tools do not mark a yield", async () => {
  const t = await setup({ sessionKeys: ["agent:leader:main", "agent:leader:dashboard:d1"] });
  try {
    const messages = [{ role: "user", content: "x" }, assistant("返事")];
    t.hooks.before_tool_call({ toolName: "sessions_yield", params: {} }, { sessionKey: "agent:leader:dashboard:d1" });
    t.hooks.before_tool_call({ toolName: "sessions_spawn", params: {} }, { sessionKey: "agent:leader:main" });
    await t.hooks.agent_end({ runId: "a", success: true, messages }, { agentId: "leader", sessionKey: "agent:leader:main" });
    assert.equal(t.sent.length, 1);
    await t.hooks.agent_end({ runId: "b", success: true, messages }, { agentId: "leader", sessionKey: "agent:leader:dashboard:d1" });
    assert.equal(t.sent.length, 1);
  } finally { await t.cleanup(); }
});

test("a yield followed by a failed run is consumed and the failure still notifies", async () => {
  const t = await setup();
  try {
    const ctx = { agentId: "leader", sessionKey: "agent:leader:main" };
    t.hooks.before_tool_call({ toolName: "sessions_yield", params: {} }, ctx);
    await t.hooks.agent_end({ runId: "r", success: false, error: "boom", messages: [] }, ctx);
    assert.equal(t.sent.length, 1);
    await t.hooks.agent_end({ runId: "r2", success: true, messages: [assistant("終わり")] }, ctx);
    assert.equal(t.sent.length, 2);
  } finally { await t.cleanup(); }
});
