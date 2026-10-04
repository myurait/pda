import { SessionManager } from './runtime/node_modules/@enderfga/claw-orchestrator/dist/src/session-manager.js';
import { appendFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const evidence = '/home/user/pda-v03a/docs/reports/evidence/v0.3-claw-orchestrator/09-handoff.txt';
const cwd = '/home/user/v03/work/claw-orchestrator/scratch';
const prompt = 'hello.py に、名前を引数で受け取って挨拶する関数を足し、README.md に使い方を 1 行書き足してください。何をしているかを短く書きながら進めてください。';
const [sourceEngine, targetEngine, attempt = '1'] = process.argv.slice(2);
const sourceName = `t9-${sourceEngine}-to-${targetEngine}-source-a${attempt}`;
const targetName = `t9-${sourceEngine}-to-${targetEngine}-target-a${attempt}`;
function log(kind, data) {
  appendFileSync(evidence, `${new Date().toISOString()} ${kind} ${JSON.stringify(data)}\n`);
}
const manager = new SessionManager({ maxConcurrentSessions: 2 });
const timeout = setTimeout(() => {
  log('TRIAL_TIMEOUT', { sourceEngine, targetEngine });
  manager.shutdown().finally(() => process.exit(2));
}, 360000);
try {
  log('BEGIN', { sourceEngine, targetEngine, attempt, cwd, access: 'Official SessionManager library API; no added skill/MCP integration', cliBinaryPath: '/home/user/.local/bin' });
  const info = await manager.startSession({ name: sourceName, engine: sourceEngine, cwd, permissionMode: 'bypassPermissions', skipPersistence: true });
  log('SOURCE_START', info);
  const sourceMessage = `この依頼は次に ${targetEngine} セッションへ製品の handoffSession 機能で引き継ぎます。ここではファイルを変更せず、依頼内容を短い引き継ぎメモとして返してください。\n\n${prompt}`;
  log('SOURCE_REQUEST', sourceMessage);
  const source = await manager.sendMessage(sourceName, sourceMessage, {
    timeout: 120000,
    onChunk: text => log('SOURCE_CHUNK', { session: sourceName, text }),
  });
  log('SOURCE_RESULT', source);
  if (source.error) throw new Error(source.error);
  log('HANDOFF_REQUEST', { name: sourceName, engine: targetEngine, newName: targetName });
  const handoff = await manager.handoffSession(sourceName, { engine: targetEngine, newName: targetName });
  log('HANDOFF_RESPONSE', handoff);
  log('TARGET_REQUEST', { name: targetName, message: prompt });
  const begin = Date.now();
  let firstChunkMs;
  let chunks = 0;
  const result = await manager.sendMessage(targetName, prompt, {
    timeout: 180000,
    onChunk: text => {
      chunks++;
      firstChunkMs ??= Date.now() - begin;
      log('TARGET_CHUNK', { session: targetName, elapsedMs: Date.now() - begin, text });
    },
    onEvent: event => {
      if (event.type !== 'text') log('TARGET_EVENT', { session: targetName, event });
    },
  });
  log('TARGET_RESULT', { session: targetName, firstChunkMs, chunks, elapsedMs: Date.now() - begin, result });
  log('TARGET_STATUS', manager.getStatus(targetName));
  log('SOURCE_STILL_EXISTS', manager.hasSession(sourceName));
  log('GIT_DIFF', execFileSync('git', ['diff', '--', 'README.md', 'hello.py'], { cwd, encoding: 'utf8' }));
  if (result.error) throw new Error(result.error);
  console.log(JSON.stringify({ sourceEngine, targetEngine, chunks, firstChunkMs, ok: true }));
} catch (error) {
  log('TRIAL_ERROR', { sourceEngine, targetEngine, error: String(error) });
  process.exitCode = 1;
} finally {
  clearTimeout(timeout);
  for (const name of [sourceName, targetName]) {
    if (manager.hasSession(name)) {
      await manager.stopSession(name);
      log('STOP_SESSION', name);
    }
  }
  await manager.shutdown();
  log('MANAGER_SHUTDOWN', { sourceEngine, targetEngine });
}
