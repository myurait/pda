import assert from 'node:assert/strict';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { seed } from '../src/mock/seed';
import { activeCells, executorCells, latestRun, runCells, supported } from '../src/mock/model';
import { addInstruction, advance, answerQuestion, createTask, insertCell, interruptTask, recordTask, restartTask, retryCell, sceneState } from '../src/mock/actions';
import { longReport } from '../src/mock/content';

const s = seed();
assert(s.tasks.length >= 8);
assert.equal(s.executors.length, 6);
assert.equal(executorCells(s, 'codex-personal').length, 3);
assert.equal(new Set(executorCells(s, 'codex-personal').map(x => x.task.id)).size, 2);
assert.equal(runCells(latestRun(s.tasks.find(t => t.id === 'large')!)).length, 30);
assert.equal(latestRun(s.tasks.find(t => t.id === 'large')!).rounds.length, 8);
assert(longReport.length >= 3000);
for (const t of s.tasks) for (const run of t.runs) {
  const cells = runCells(run), ids = cells.map(c => c.id); assert.equal(new Set(ids).size, ids.length);
  for (const report of run.reports) { assert(cells.some(c => c.id === report.id && c.kind === 'report')); assert.equal(report.author, t.reporter); if (report.questions.length) assert(run.rounds.some(r => r.report?.id === report.id && r.joined && r.branches.some(b => b.waiting && b.cells.find(c => c.id === b.waiting?.observerId)?.kind === 'observe'))); }
  for (const c of cells) if (c.kind !== 'owner') assert(supported(s.executors.find(e => e.id === c.executor)!, c.type), `${c.id} has unsupported executor`);
}
const a = s.tasks.find(t => t.id === 'api')!;
interruptTask(a, '読み取りだけに切り替える'); assert.equal(activeCells(a).length, 0); assert(latestRun(a).rounds[0].branches.every(b => b.cells.some(c => c.decision === '分岐 A：オブザーバー')));
addInstruction(a, '追加の条件'); assert(latestRun(a).rounds.at(-1)!.owners.some(c => c.input === '追加の条件'));
insertCell(a, 'verify.lint', '静的検査', s.executors); assert(latestRun(a).rounds.at(-1)!.branches.some(b => b.cells[0].origin === 'オーナーの操作'));
restartTask(a, '新しい条件'); assert.equal(a.runs.length, 2); assert.equal(a.runs[0].state, '中断した');
const q = s.tasks.find(t => t.id === 'questions')!, report = latestRun(q).reports[0];
report.questions.forEach(question => answerQuestion(q, report.id, question.id, '回答')); assert.equal(q.state, '進行中'); assert(latestRun(q).rounds.at(-1)!.owners.some(c => c.type === '返答'));
const retry = s.tasks.find(t => t.id === 'retry')!, failed = runCells(latestRun(retry)).find(c => c.state === '失敗した')!;
const copyId = retryCell(retry, failed, 'claude-personal'); assert(runCells(latestRun(retry)).some(c => c.id === copyId && c.input === failed.input));
const simulation = seed(); simulation.tasks = [createTask('模擬的に進める', '', 'claude-personal')];
const steps: string[] = []; for (let i = 0; i < 24 && simulation.tasks[0].state === '進行中'; i++) steps.push(advance(simulation));
assert.equal(simulation.tasks[0].state, '入力待ち'); assert(steps.some(s => s.includes('オブザーバー'))); assert(steps.some(s => s.includes('合流'))); assert(latestRun(simulation.tasks[0]).reports.length);
recordTask(simulation.tasks[0], '完了'); advance(simulation); assert.equal(simulation.tasks[0].state, '完了');
assert.equal(sceneState('60件のタスク').tasks.length, 60); assert.equal(sceneState('タスクなし').tasks.length, 0); assert(!sceneState('入力待ちなし').tasks.some(t => t.state === '入力待ち'));
const files = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(d => d.isDirectory() ? files(`${dir}/${d.name}`) : [`${dir}/${d.name}`]);
for (const path of files('src')) assert(!/\p{Extended_Pictographic}/u.test(readFileSync(path, 'utf8')), `Emoji in ${path}`);
const design = readFileSync('docs/ux-design.md', 'utf8'); for (let i = 1; i <= 12; i++) assert(design.includes(`UC${i} |`)); for (let i = 1; i <= 9; i++) assert(design.includes(`## ${i}.`));
writeFileSync('docs/model-verification.json', JSON.stringify({ tasks: s.tasks.length, executors: s.executors.length, largeFlow: { rounds: 8, cells: 30 }, reportCharacters: longReport.length, codexConcurrentCells: 3, emojiFilesChecked: files('src').length, simulationSteps: steps, passed: true }, null, 2) + '\n');
console.log(`見本・操作・段階進行の整合性を確認しました。長文報告 ${longReport.length} 字。`);
