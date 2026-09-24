import { activeCells, latestRun, runCells, supported } from './model';
import type { Cell, Executor, MockState, Round, Scene, Task } from './model';
import { attachReport, cell, round, seed, task } from './seed';

let sequence = 0;
const id = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${++sequence}`;
function resume(t: Task) { t.state = '進行中'; t.waitingReason = undefined; latestRun(t).state = '動いている'; t.updated = '2026-09-25 09:43'; }
function nextRound(t: Task): Round {
  const run = latestRun(t), last = run.rounds.at(-1)!;
  if (last.judge.state === '待機') return last;
  const r = round(id(`${t.id}-r`), last.number + 1, [], { joined: false }); r.judge.state = activeCells(t).length ? '待機' : '動いている'; r.judge.decision = '次の仕事を判定';
  run.rounds.push(r); return r;
}
export function addInstruction(t: Task, input: string, rewrite = false) {
  const r = nextRound(t);
  r.owners.push(cell(id('owner'), rewrite ? '書き換え' : '指示', 'オーナー', '終わった', { input, output: input, badge: `${rewrite ? '書き換え・' : ''}次の回から有効` }));
  if (rewrite) t.directive = input;
  resume(t);
}
export function restartTask(t: Task, input: string) {
  const old = latestRun(t); old.state = '中断した'; runCells(old).forEach(c => { if (['動いている', '待機'].includes(c.state)) c.state = '中断した'; });
  const r = round(id(`${t.id}-r`), 1, [], { owners: [cell(id('rewrite'), '書き換え', 'オーナー', '終わった', { input, output: input, badge: '書き換え・最初から' })], joined: false });
  r.judge.state = '動いている'; r.judge.decision = '新しい指示から判定';
  t.runs.push({ id: `run-${t.runs.length + 1}`, state: '動いている', rounds: [r], reports: [], stage: 0 }); t.directive = input; resume(t);
}
export function insertCell(t: Task, type: string, input: string, executors: Executor[]) {
  const r = nextRound(t), executor = executors.find(e => e.life === '生きている' && supported(e, type)) || executors.find(e => supported(e, type));
  if (!executor) return;
  r.branches.push({ id: id('branch'), label: 'オーナーの追加', cells: [cell(id('insert'), type, executor.id, '待機', { input, output: '次の回でこの入力を受け取ります。', origin: 'オーナーの操作', badge: 'オーナーが挿入' })] });
  r.judge.decision = `${r.branches.length} 本の追加分岐を含めて判定`; resume(t);
}
export function extraInput(c: Cell, input: string) { c.extraInputs.push(input); c.badge = `追加入力 ${c.extraInputs.length} 件`; }
export function retryCell(t: Task, c: Cell, executor: string) {
  const run = latestRun(t), r = run.rounds.find(r => r.branches.some(b => b.cells.some(x => x.id === c.id)));
  const clone = cell(id('retry'), c.type, executor, '動いている', { input: c.input, prePrompt: c.prePrompt, origin: 'オーナーの操作', badge: 'オーナーの再試行', after: c.id, output: '同じ type と入力で、オーナーが選んだ実行器に再投入しました。' });
  if (!c.attempts.length) c.attempts.push({ cellId: c.id, executor: c.executor, state: c.state, source: c.origin });
  c.attempts.push({ cellId: clone.id, executor, state: clone.state, source: clone.origin }); clone.attempts = structuredClone(c.attempts);
  if (r) { const b = r.branches.find(b => b.cells.some(x => x.id === c.id))!; b.cells.push(clone); b.waiting = undefined; r.joined = false; }
  else { const next = nextRound(t); next.branches.push({ id: id('branch'), label: 'オーナーの再試行', cells: [clone] }); }
  resume(t); return clone.id;
}
export function interruptTask(t: Task, reason: string, executor?: string) {
  const run = latestRun(t);
  for (const r of run.rounds) {
    for (const b of r.branches) {
      const moving = b.cells.filter(c => c.state === '動いている' && (!executor || c.executor === executor));
      for (const c of moving) {
        c.state = '中断した'; c.output = `## 中断\n\nオーナーが実行を中断しました。\n\n${reason || '理由の指定はありません。'}`;
        b.cells.push(cell(id('stop-owner'), '中断指示', 'オーナー', '終わった', { input: reason || 'オーナーが中断しました。', output: reason || 'オーナーが中断しました。', badge: 'オーナーが中断' }), cell(id('stop-a'), 'judge', 'jev', '終わった', { decision: '分岐 A：オブザーバー', input: c.output }), cell(id('stop-b'), 'observe', 'claude-personal', '待機', { decision: '分岐 B：次の一歩で判定', input: c.output, output: '中断理由を受け取りました。修正方針を判定します。' }));
        r.joined = false;
      }
    }
    if (r.judge.state === '動いている' && (!executor || r.judge.executor === executor)) {
      r.judge.state = '中断した';
      r.branches.push({ id: id('interrupted-judge'), label: '判定の中断を扱う', cells: [cell(id('judge-a'), 'judge', 'jev', '待機', { decision: '分岐 A：オブザーバー', input: reason })] });
    }
    if (r.report?.state === '動いている' && (!executor || r.report.executor === executor)) {
      const stopped = r.report; stopped.state = '中断した'; r.report = undefined;
      r.branches.push({ id: id('interrupted-report'), label: '報告の中断を扱う', cells: [stopped, cell(id('report-a'), 'judge', 'jev', '待機', { decision: '分岐 A：再試行', input: reason })] });
    }
  }
  resume(t);
}
export function recordTask(t: Task, state: '完了' | '中止') {
  const run = latestRun(t);
  runCells(run).forEach(c => { if (['動いている', '待機'].includes(c.state)) c.state = '中断した'; });
  run.state = state === '中止' ? '中断した' : '終わった'; t.state = state; t.waitingReason = undefined;
}
export function answerQuestion(t: Task, reportId: string, questionId: string, answer: string) {
  const report = latestRun(t).reports.find(r => r.id === reportId); if (!report) return;
  const q = report.questions.find(q => q.id === questionId); if (!q) return; q.answer = answer;
  if (report.questions.every(q => q.answer)) {
    const r = nextRound(t); const text = report.questions.map(q => `${q.text}\n返答：${q.answer}`).join('\n\n');
    r.owners.push(cell(id('answer'), '返答', 'オーナー', '終わった', { input: text, output: text, badge: '報告への返答' }));
    r.judge.state = '動いている'; r.judge.decision = '返答を受けて次の仕事を判定'; resume(t);
  }
}
export function createTask(input: string, workdir: string, reporter: string) {
  const t = task(id('task'), input.split('\n')[0].slice(0, 52), []); t.initial = input; t.directive = input; t.workdir = workdir; t.reporter = reporter; t.elapsed = 0;
  const r = latestRun(t).rounds[0]; r.owners[0].input = input; r.owners[0].output = input; r.judge.state = '動いている'; r.judge.decision = '指示を受け付けました'; r.joined = false; return t;
}
export function sceneState(scene: Scene): MockState {
  const s = seed(); s.scene = scene;
  if (scene === 'タスクなし') s.tasks = [];
  if (scene === '入力待ちなし') s.tasks = s.tasks.filter(t => t.state !== '入力待ち');
  if (scene === '実行器が不明') s.executors.find(e => e.id === 'fake-b')!.life = '不明';
  if (scene === '60件のタスク') {
    const subjects = ['作業手順を整える', '保存した記録を照合する', '画面の文言を確認する', '入力と応答の対応を確認する'];
    for (let i = s.tasks.length; i < 60; i++) { const t = task(`sample-${i + 1}`, `${subjects[i % subjects.length]}・${i + 1}`, []); recordTask(t, i % 2 ? '完了' : '中止'); s.tasks.push(t); }
  }
  return s;
}

// One press represents one observable stage, never a timer or an owner completion.
export function advance(s: MockState, preferred?: string): string {
  s.tick++;
  const t = s.tasks.find(t => t.id === preferred && t.state === '進行中') || s.tasks.find(t => t.state === '進行中');
  if (!t) return '進める作業はありません。';
  const run = latestRun(t); t.elapsed += 30; activeCells(t).forEach(c => c.elapsed += 30);
  const r = run.rounds.find(r => !r.joined || r.judge.state === '動いている' || r.judge.state === '待機') || run.rounds.at(-1)!;
  const available = (type: string, fallback: string) => s.executors.find(e => e.life === '生きている' && supported(e, type))?.id || fallback;
  if (r.judge.state === '動いている' || r.judge.state === '待機') {
    r.judge.state = '終わった'; r.judge.decision = '2 本に分岐して進める';
    if (!r.branches.length) r.branches = [
      { id: id('work-b'), label: '実装', cells: [cell(id('work'), 'implement', available('implement', 'codex-personal'), '動いている')] },
      { id: id('review-b'), label: '確認', cells: [cell(id('review'), 'review', available('review', 'claude-personal'), '動いている')] },
    ];
    else r.branches.forEach(b => b.cells.filter(c => c.state === '待機').forEach(c => c.state = '動いている'));
    r.joined = false; return '判定器が次の分岐を決めました。';
  }
  for (const b of r.branches) {
    const last = b.cells.at(-1); if (!last || b.waiting) continue;
    if (last.state === '失敗した' || last.state === '中断した') {
      b.cells.push(cell(id('a'), 'judge', available('judge', 'jev'), '動いている', { decision: '分岐 A：判定中', input: last.output })); return '失敗・中断を判定器へ渡しました。';
    }
    if (last.kind === 'judge' && ['動いている', '待機'].includes(last.state)) {
      last.state = '終わった'; const work = [...b.cells].reverse().find(c => c.kind === 'work');
      if (work && !b.cells.some(c => c.badge?.includes('再試行'))) {
        last.decision = '分岐 A：再試行'; const clone = cell(id('auto-retry'), work.type, available(work.type, work.executor), '動いている', { input: work.input, badge: '判定器の再試行・複製' });
        work.attempts = [{ cellId: work.id, executor: work.executor, state: work.state, source: work.origin }, { cellId: clone.id, executor: clone.executor, state: clone.state, source: clone.origin }]; clone.attempts = structuredClone(work.attempts); b.cells.push(clone);
      } else { last.decision = '分岐 A：オブザーバー'; b.cells.push(cell(id('observe'), 'observe', available('observe', 'claude-personal'), '動いている', { decision: '分岐 B：判定中' })); }
      return `判定器が選びました。${last.decision}`;
    }
    if (last.kind === 'observe' && ['動いている', '待機'].includes(last.state)) {
      last.state = '終わった';
      if (t.id === 'interrupted') {
        last.decision = '分岐 B：オーナーの判断が必要'; last.output = '書き込み範囲を推定できないため、オーナーの判断が必要です。'; b.waiting = { id: id('wait'), observerId: last.id, reason: last.output };
      } else {
        last.decision = '分岐 B：判断不要・仕事を分ける'; last.output = '環境の準備と元の作業を分けて実行するよう指示します。';
        b.cells.push(cell(id('redo'), 'implement', available('implement', 'codex-personal'), '動いている', { origin: 'オブザーバー', badge: '指示に従ってやり直し', input: last.output }));
      }
      return 'オブザーバーが判断し、分岐に結果が現れました。';
    }
  }
  const moving = r.branches.flatMap(b => b.cells).filter(c => c.state === '動いている' || c.state === '待機');
  if (moving.length) {
    moving.forEach(c => { c.state = '終わった'; c.output = '## 確認した結果\n\n入力の条件を満たすことを確認しました。結果を合流へ渡します。'; });
    const first = moving.find(c => c.kind === 'work' && c.origin !== 'オブザーバー');
    if (first && run.stage < 2) { first.state = '失敗した'; first.output = '一時的な環境の問題が発生しました。判定器に判断材料を渡します。'; run.stage++; }
    return '作業のセルが出力を返しました。';
  }
  if (!r.joined) { r.joined = true; return 'すべての分岐が合流しました。'; }
  const next = run.rounds.find(x => x.number > r.number && x.judge.state === '待機'); if (next) { next.judge.state = '動いている'; return '次の回の判定器が指示を受け取りました。'; }
  if (!r.report) {
    const waits = r.branches.filter(b => b.waiting);
    attachReport(t, `# ${t.title}の途中結果\n\n## 結果\n\n分岐の出力を合流しました。${waits.length ? 'オブザーバーが判断を要すると判定した内容を以下にまとめます。' : '自動で進める作業はありません。'}\n\n| 対象 | 結果 |\n| --- | --- |\n| 作業 | 合流済み |\n\n## 確認\n\n- 出力を照合しました。\n- 成果物は別の一覧から確認できます。`, waits.length ? [{ id: id('q'), text: '書き込みを行わず調査を続けますか', kind: 'approval' }] : []);
    return '指定された実行器が報告を書き、入力待ちになりました。';
  }
  return '次のオーナーの入力を待っています。';
}
