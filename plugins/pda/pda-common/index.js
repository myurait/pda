import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";

export default {
  id: "pda-common",
  name: "PDA common instructions",
  register(api) {
    // The Gateway HOME is agent-home, so use the deployment path explicitly.
    const commonFile = api.pluginConfig?.commonFile ?? "/home/user/v03/openclaw/pda/common.md";

    api.on("before_prompt_build", async (_event, ctx) => {
      let content;
      try {
        content = await readFile(commonFile, "utf8");
      } catch (error) {
        api.logger.warn(`[pda-common] before_prompt_build ${JSON.stringify({
          agentId: ctx.agentId,
          sessionKey: ctx.sessionKey,
          runId: ctx.runId,
          outcome: "skipped",
          code: error.code ?? "READ_FAILED",
        })}`);
        return;
      }

      api.logger.info(`[pda-common] before_prompt_build ${JSON.stringify({
        agentId: ctx.agentId,
        sessionKey: ctx.sessionKey,
        runId: ctx.runId,
        outcome: "loaded",
        bytes: Buffer.byteLength(content, "utf8"),
        sha256: createHash("sha256").update(content).digest("hex"),
      })}`);
      return { appendSystemContext: content };
    });
  },
};
