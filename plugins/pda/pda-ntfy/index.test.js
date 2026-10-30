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

test("replies in the owner's conversation notify with excerpt, title and click URL", async () => {
  const t = await setup();
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
  const t = await setup();
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
