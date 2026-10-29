import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import plugin from "./index.js";

test("all agents receive current file contents; unreadable files do not stop a turn", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pda-common-"));
  const commonFile = join(dir, "common.md");
  const logs = [];
  let hook;
  plugin.register({
    pluginConfig: { commonFile },
    logger: { info: (line) => logs.push(line), warn: (line) => logs.push(line) },
    on(name, handler) {
      assert.equal(name, "before_prompt_build");
      assert.equal(hook, undefined);
      hook = handler;
    },
  });
  try {
    await writeFile(commonFile, "共通の指示\n");
    for (const agentId of ["leader", "worker", "auditor", "claude", "codex"]) {
      assert.deepEqual(await hook({}, { agentId }), { appendSystemContext: "共通の指示\n" });
    }
    await writeFile(commonFile, "更新した指示\n");
    assert.deepEqual(await hook({}, {}), { appendSystemContext: "更新した指示\n" });
    await rm(commonFile);
    assert.equal(await hook({}, {}), undefined);
    assert.ok(logs.some((line) => line.includes('"code":"ENOENT"')));
    assert.ok(logs.every((line) => !line.includes("共通の指示") && !line.includes("更新した指示")));
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
