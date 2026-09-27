import { activeCells, currentReport, flowCells, supported } from './model';
import type { Cell, Executor, MockState, Round, Scene, Task } from './model';
import { attachReport, cell, round, seed, task } from './seed';

let sequence = 0;
const id = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${++sequence}`;
function resume(t: Task) { t.state = '進行中'; t.waitingReason = undefined; t.waitingSince = undefined; t.stoppedAt = undefined; t.updated = '2026-09-25 09:43'; }
function nextRound(t: Task): Round {
  const run = t.flow, last = run.rounds.at(-1)!;
  if (last.judge.state === '待機') return last;
  const r = round(id(`${t.id}-r`), last.number + 1, [], { joined: false }); r.judge.state = activeCells(t).length ? '待機' : '動作中'; r.judge.decision = '次の仕事を判定';
  run.rounds.push(r); return r;
}
export function addInstruction(t: Task, input: string, rewrite = false) {
  t.lastInstructionAt = Date.now(); t.elapsed = 0;
  const r = nextRound(t);
  r.owners.push(cell(id('owner'), rewrite ? '書き換え' : '指示', 'オーナー', '終わった', { input, output: input, badge: `${rewrite ? '書き換え・' : ''}次の回から有効` }));
  if (rewrite) t.directive = input;
  resume(t);
}
export function restartTask(t: Task, input: string) {
  t.lastInstructionAt = Date.now(); t.elapsed = 0;
  const old = t.flow; flowCells(old).forEach(c => { if (['動作中', '待機'].includes(c.state)) c.state = '中断した'; });
  old.rounds.forEach(r => { r.joined = true; });
  const r = round(id(`${t.id}-r`), old.rounds.length + 1, [], { owners: [cell(id('rewrite'), '書き換え', 'オーナー', '終わった', { input, output: input, badge: '書き換え・最初から' })], joined: false });
  r.judge.state = '動作中'; r.judge.decision = '新しい指示から判定';
  t.flow.rounds.push(r); t.flow.stage = 0; t.directive = input; resume(t);
}
export function insertCell(t: Task, anchorId: string, position: 'after' | 'parallel', type: string, input: string, executors: Executor[]) {
  const r = t.flow.rounds.find(r => [r.judge, ...r.owners, ...r.branches.flatMap(b => b.cells), ...(r.report ? [r.report] : [])].some(c => c.id === anchorId));
  const executor = executors.find(e => e.life === '生きている' && supported(e, type));
  if (!r || !executor) return;
  const cells = flowCells(t.flow), anchor = cells.find(c => c.id === anchorId)!;
  const branch = r.branches.find(b => b.cells.some(c => c.id === anchorId));
  const index = branch?.cells.findIndex(c => c.id === anchorId) ?? -1;
  const predecessor = anchor.after || (branch ? branch.cells[index - 1]?.id || r.judge.id : r.owners.at(-1)?.id);
  const after = position === 'after' ? anchorId : predecessor;
  const waiting = cells.find(c => c.id === after)?.state !== '終わった';
  const added = cell(id('insert'), type, executor.id, waiting ? '待機' : '動作中', { input, after, output: waiting ? '接続元のセルの終了を待っています。' : '指定された入力で作業を開始しています。', origin: 'オーナーの操作', badge: 'オーナーが挿入' });
  if (position === 'after' && branch) {
    const next = branch.cells[index + 1];
    branch.cells.splice(index + 1, 0, added);
    if (next && (!next.after || next.after === anchorId)) next.after = added.id;
    branch.waiting = undefined;
  } else r.branches.push({ id: id('branch'), label: position === 'parallel' ? '並列に追加' : '後ろに追加', cells: [added] });
  r.joined = false; resume(t); return added.id;
}
export function extraInput(c: Cell, input: string) { c.extraInputs.push(input); c.badge = `追加入力 ${c.extraInputs.length} 件`; }
export function retryCell(t: Task, c: Cell, executor: string) {
  const run = t.flow, r = run.rounds.find(r => r.branches.some(b => b.cells.some(x => x.id === c.id)));
  const clone = cell(id('retry'), c.type, executor, '動作中', { input: c.input, prePrompt: c.prePrompt, origin: 'オーナーの操作', badge: 'オーナーの再試行', after: c.id, output: '同じ type と入力で、オーナーが選んだ実行器に再投入しました。' });
  if (!c.attempts.length) c.attempts.push({ cellId: c.id, executor: c.executor, state: c.state, source: c.origin });
  c.attempts.push({ cellId: clone.id, executor, state: clone.state, source: clone.origin }); clone.attempts = structuredClone(c.attempts);
  if (r) { const b = r.branches.find(b => b.cells.some(x => x.id === c.id))!; b.cells.push(clone); b.waiting = undefined; r.joined = false; }
  else { const next = nextRound(t); next.branches.push({ id: id('branch'), label: 'オーナーの再試行', cells: [clone] }); }
  resume(t); return clone.id;
}
export function interruptTask(t: Task, reason: string, executor?: string) {
  const run = t.flow;
  for (const r of run.rounds) {
    for (const b of r.branches) {
      const moving = b.cells.filter(c => c.state === '動作中' && (!executor || c.executor === executor));
      for (const c of moving) {
        c.state = '中断した'; c.output = `## 中断\n\nオーナーが実行を中断しました。\n\n${reason || '理由の指定はありません。'}`;
        b.cells.push(cell(id('stop-owner'), '中断指示', 'オーナー', '終わった', { input: reason || 'オーナーが中断しました。', output: reason || 'オーナーが中断しました。', badge: 'オーナーが中断' }), cell(id('stop-a'), 'judge', 'jev', '終わった', { decision: '分岐 A：オブザーバー', input: c.output }), cell(id('stop-b'), 'observe', 'claude-personal', '待機', { decision: '分岐 B：次の一歩で判定', input: c.output, output: '中断理由を受け取りました。修正方針を判定します。' }));
        r.joined = false;
      }
    }
    if (r.judge.state === '動作中' && (!executor || r.judge.executor === executor)) {
      r.judge.state = '中断した';
      r.branches.push({ id: id('interrupted-judge'), label: '判定の中断を扱う', cells: [cell(id('judge-a'), 'judge', 'jev', '待機', { decision: '分岐 A：オブザーバー', input: reason })] });
    }
    if (r.report?.state === '動作中' && (!executor || r.report.executor === executor)) {
      const stopped = r.report; stopped.state = '中断した'; r.report = undefined;
      r.branches.push({ id: id('interrupted-report'), label: '報告の中断を扱う', cells: [stopped, cell(id('report-a'), 'judge', 'jev', '待機', { decision: '分岐 A：再試行', input: reason })] });
    }
  }
  resume(t);
}
export function recordTask(t: Task, state: '完了' | '中止') {
  const run = t.flow;
  flowCells(run).forEach(c => { if (['動作中', '待機'].includes(c.state)) c.state = '中断した'; });
  t.stoppedAt = t.waitingSince || Date.now(); t.waitingSince = undefined; t.state = state; t.waitingReason = undefined;
}
export function answerQuestions(t: Task, reportId: string, answers: Record<string, string>) {
  const report = currentReport(t);
  if (t.state !== '入力待ち' || report?.id !== reportId || !report.questions.length || report.questions.every(q => q.answer)) return false;
  if (report.questions.some(q => !answers[q.id]?.trim())) return false;
  t.lastInstructionAt = Date.now(); t.elapsed = 0;
  report.questions.forEach(q => { q.answer = answers[q.id].trim(); });
  const r = nextRound(t), text = report.questions.map(q => `${q.text}\n返答：${q.answer}`).join('\n\n');
  r.owners.push(cell(id('answer'), '返答', 'オーナー', '終わった', { input: text, output: text, badge: '報告への返答' }));
  r.judge.state = '動作中'; r.judge.decision = '返答を受けて次の仕事を判定'; resume(t);
  return true;
}
export function createTask(input: string, workdir: string) {
  const t = task(id('task'), input.split('\n')[0].slice(0, 52), []); t.initial = input; t.directive = input; t.workdir = workdir; t.elapsed = 0; t.lastInstructionAt = Date.now();
  const r = t.flow.rounds[0]; r.owners[0].input = input; r.owners[0].output = input; r.judge.state = '動作中'; r.judge.decision = '指示を受け付けました'; r.joined = false; return t;
}
export function sceneState(scene: Scene): MockState {
  const s = seed(); s.scene = scene;
  if (scene === '複数の報告') {
    const t = s.tasks.find(t => t.id === 'questions')!;
    const latestRound = t.flow.rounds[0], latestReport = t.flow.reports[0];
    const samples = [
      { title: '既存セッションの調査結果', time: '2026-09-24 14:20', input: t.initial, body: '# 既存セッションの調査結果\n\n## 確認できたこと\n個人の記録と共有候補が混在しています。元ファイルは変更していません。\n\n## 未確認の範囲\n保存先と読み取り権限を確認する必要があります。' },
      { title: '読み取り専用での索引検証', time: '2026-09-24 17:45', input: '保存先は変更せず、読み取り専用で索引を検証してください。', body: '# 読み取り専用での索引検証\n\n## 結果\n索引の参照先と重複を検証しました。\n\n| 対象 | 結果 |\n| --- | --- |\n| 参照先 | 確認済み |\n| 重複 | なし |\n\n## 次に必要な判断\n保存範囲と取り込み先の判断が残っています。' },
    ];
    t.flow.rounds = []; t.flow.reports = [];
    samples.forEach((sample, i) => {
      const prefix = `questions-history-${i + 1}`;
      t.flow.rounds.push(round(prefix, i + 1, [{ id: `${prefix}-branch`, label: '調査', cells: [cell(`${prefix}-work`, 'review', 'claude-personal')] }], { owners: [cell(`${prefix}-owner`, i ? '指示' : '初期の指示', 'オーナー', '終わった', { input: sample.input, output: sample.input })] }));
      attachReport(t, sample.body);
      Object.assign(t.flow.reports.at(-1)!, { title: sample.title, time: sample.time });
    });
    latestRound.number = 3;
    const input = '読み取り専用を維持してください。失敗したセルの応答を確認し、保存範囲と取り込み先について必要な問いをまとめてください。';
    latestRound.owners = [cell('questions-latest-input', '指示', 'オーナー', '終わった', { input, output: input })];
    latestReport.userInput = input; latestReport.title = '保存範囲と取り込み先の確認';
    t.flow.rounds.push(latestRound); t.flow.reports.push(latestReport);
    t.waitingReason = '判断を求めています';
  }
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
  const run = t.flow; t.elapsed += 30; activeCells(t).forEach(c => c.elapsed += 30);
  const r = run.rounds.find(r => !r.joined || r.judge.state === '動作中' || r.judge.state === '待機') || run.rounds.at(-1)!;
  if (r.report?.state === '動作中') {
    const previous = r.report;
    attachReport(t, `# ${t.title}\n\n追加入力を反映して報告を作り直しました。`, [], 'markdown', { id: 'report', name: '報告担当', executor: previous.executor, model: previous.model || '', prompt: previous.prePrompt, skills: previous.skills || [] });
    r.report!.attempts = previous.attempts; r.report!.extraInputs = previous.extraInputs;
    return '報告を作り直し、入力待ちになりました。';
  }
  const available = (type: string, fallback: string) => s.executors.find(e => e.life === '生きている' && supported(e, type))?.id || fallback;
  if (r.judge.state === '動作中' || r.judge.state === '待機') {
    r.judge.state = '終わった'; r.judge.decision = '2 本に分岐して進める';
    if (!r.branches.length) r.branches = [
      { id: id('work-b'), label: '実装', cells: [cell(id('work'), 'implement', available('implement', 'codex-personal'), '動作中')] },
      { id: id('review-b'), label: '確認', cells: [cell(id('review'), 'review', available('review', 'claude-personal'), '動作中')] },
    ];
    else r.branches.forEach(b => b.cells.filter(c => c.state === '待機').forEach(c => c.state = '動作中'));
    r.joined = false; return '判定器が次の分岐を決めました。';
  }
  for (const b of r.branches) {
    const last = b.cells.at(-1); if (!last || b.waiting) continue;
    if (last.state === '失敗した' || last.state === '中断した') {
      b.cells.push(cell(id('a'), 'judge', available('judge', 'jev'), '動作中', { decision: '分岐 A：判定中', input: last.output })); return '失敗・中断を判定器へ渡しました。';
    }
    if (last.kind === 'judge' && ['動作中', '待機'].includes(last.state)) {
      last.state = '終わった'; const work = [...b.cells].reverse().find(c => c.kind === 'work');
      if (work && !b.cells.some(c => c.badge?.includes('再試行'))) {
        last.decision = '分岐 A：再試行'; const clone = cell(id('auto-retry'), work.type, available(work.type, work.executor), '動作中', { input: work.input, badge: '判定器の再試行・複製' });
        work.attempts = [{ cellId: work.id, executor: work.executor, state: work.state, source: work.origin }, { cellId: clone.id, executor: clone.executor, state: clone.state, source: clone.origin }]; clone.attempts = structuredClone(work.attempts); b.cells.push(clone);
      } else { last.decision = '分岐 A：オブザーバー'; b.cells.push(cell(id('observe'), 'observe', available('observe', 'claude-personal'), '動作中', { decision: '分岐 B：判定中' })); }
      return `判定器が選びました。${last.decision}`;
    }
    if (last.kind === 'observe' && ['動作中', '待機'].includes(last.state)) {
      last.state = '終わった';
      if (t.id === 'interrupted') {
        last.decision = '分岐 B：オーナーの判断が必要'; last.output = '書き込み範囲を推定できないため、オーナーの判断が必要です。'; b.waiting = { id: id('wait'), observerId: last.id, reason: last.output };
      } else {
        last.decision = '分岐 B：判断不要・仕事を分ける'; last.output = '環境の準備と元の作業を分けて実行するよう指示します。';
        b.cells.push(cell(id('redo'), 'implement', available('implement', 'codex-personal'), '動作中', { origin: 'オブザーバー', badge: '指示に従ってやり直し', input: last.output }));
      }
      return 'オブザーバーが判断し、分岐に結果が現れました。';
    }
  }
  const moving = r.branches.flatMap(b => b.cells).filter(c => c.state === '動作中' || c.state === '待機');
  if (moving.length) {
    moving.forEach(c => { c.state = '終わった'; c.output = '## 確認した結果\n\n入力の条件を満たすことを確認しました。結果を合流へ渡します。'; });
    const first = moving.find(c => c.kind === 'work' && c.origin !== 'オブザーバー');
    if (first && run.stage < 2) { first.state = '失敗した'; first.output = '一時的な環境の問題が発生しました。判定器に判断材料を渡します。'; run.stage++; }
    return '作業のセルが出力を返しました。';
  }
  if (!r.joined) { r.joined = true; return 'すべての分岐が合流しました。'; }
  const next = run.rounds.find(x => x.number > r.number && x.judge.state === '待機'); if (next) { next.judge.state = '動作中'; return '次の回の判定器が指示を受け取りました。'; }
  if (!r.report) {
    const waits = r.branches.filter(b => b.waiting);
    attachReport(t, `# ${t.title}の途中結果\n\n## 結果\n\n分岐の出力を合流しました。${waits.length ? 'オブザーバーが判断を要すると判定した内容を以下にまとめます。' : '自動で進める作業はありません。'}\n\n| 対象 | 結果 |\n| --- | --- |\n| 作業 | 合流済み |\n\n## 確認\n\n- 出力を照合しました。\n- 成果物は別の一覧から確認できます。`, waits.length ? [{ id: id('q'), text: '書き込みを行わず調査を続けますか', kind: 'approval' }] : []);
    return '指定された実行器が報告を書き、入力待ちになりました。';
  }
  return '次のオーナーの入力を待っています。';
}

export function successorCellIds(t: Task, target: string): Set<string> {
  const links: [string, string][] = [];
  let previous: string[] = [];
  for (const r of t.flow.rounds) {
    for (const owner of r.owners) { previous.forEach(id => links.push([id, owner.id])); previous = [owner.id]; }
    previous.forEach(id => links.push([id, r.judge.id]));
    const tails: string[] = [];
    for (const branch of r.branches) {
      let last = r.judge.id; const parents = new Set<string>();
      for (const c of branch.cells) { const parent = c.after || last; links.push([parent, c.id]); parents.add(parent); last = c.id; }
      tails.push(...branch.cells.filter(c => !parents.has(c.id)).map(c => c.id));
    }
    previous = tails.length ? tails : [r.judge.id];
    if (r.report) { previous.forEach(id => links.push([id, r.report!.id])); previous = [r.report.id]; }
  }
  const removed = new Set<string>([target]);
  let changed = true;
  while (changed) { changed = false; for (const [from, to] of links) if (removed.has(from) && !removed.has(to)) { removed.add(to); changed = true; } }
  removed.delete(target); return removed;
}
export function addCellInstruction(t: Task, cellId: string, input: string, restart = false) {
  const target = flowCells(t.flow).find(c => c.id === cellId);
  if (!target || !input.trim() || ['完了', '中止'].includes(t.state) || target.kind === 'owner') return false;
  const source = t.flow.rounds.find(r => [r.judge, ...r.owners, ...r.branches.flatMap(b => b.cells), ...(r.report ? [r.report] : [])].some(c => c.id === cellId))!;
  const needsRestart = target.state !== '動作中' || source.joined;
  if (needsRestart && !restart) return false;
  if (needsRestart) {
    const removed = successorCellIds(t, cellId), outputIds = new Set([...removed, cellId]);
    const removedReports = t.flow.reports.filter(r => outputIds.has(r.id));
    t.flow.reports = t.flow.reports.filter(r => !outputIds.has(r.id));
    const retainedArtifacts = new Set(t.flow.reports.flatMap(r => r.artifactIds));
    const removedArtifacts = new Set(removedReports.flatMap(r => r.artifactIds).filter(id => !retainedArtifacts.has(id)));
    t.artifacts = t.artifacts.filter(a => !(a.sourceCellId && outputIds.has(a.sourceCellId)) && !removedArtifacts.has(a.id));
    t.flow.rounds = t.flow.rounds.filter(r => !removed.has(r.judge.id));
    for (const r of t.flow.rounds) {
      r.owners = r.owners.filter(c => !removed.has(c.id));
      r.branches = r.branches.map(b => ({ ...b, cells: b.cells.filter(c => !removed.has(c.id)), waiting: b.waiting && !outputIds.has(b.waiting.observerId) && !b.cells.some(c => outputIds.has(c.id)) ? b.waiting : undefined })).filter(b => b.cells.length);
      if (r.report && removed.has(r.report.id)) r.report = undefined;
    }
    source.joined = false;
    target.attempts.push({ cellId: `${cellId}-attempt-${target.attempts.length + 1}`, executor: target.executor, state: target.state, source: target.origin, input: [target.input, ...target.extraInputs].join('\n\n'), output: target.output });
    target.state = '動作中'; target.elapsed = 0; target.output = ''; target.tools = []; target.badge = '追加入力から再開';
  }
  target.extraInputs.push(input.trim());
  if (!needsRestart) target.badge = `追加入力 ${target.extraInputs.length} 件`;
  t.lastInstructionAt = Date.now(); t.elapsed = 0; resume(t);
  return true;
}
