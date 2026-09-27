import type { MockState } from './model';
import { seed } from './seed';
export function migrate(saved: MockState): MockState {
  if (saved.version === 3) return saved;
  const defaults = seed(), now = Date.now();
  saved.skills = defaults.skills;
  for (const role of saved.roles) for (const id of role.skills) if (!saved.skills.some(s => s.id === id)) saved.skills.push({ id, name: id, path: id, description: '' });
  for (const executor of saved.executors) {
    const example = defaults.executors.find(e => e.id === executor.id);
    executor.usageScript ??= example?.usageScript;
    executor.usage ??= example?.usage;
  }
  for (const task of saved.tasks) {
    if (task.state === '入力待ち') task.waitingSince ??= now;
    if (['完了', '中止'].includes(task.state)) task.stoppedAt ??= now;
    task.lastInstructionAt ??= (task.waitingSince || task.stoppedAt || now) - task.elapsed * 1000;
    for (const report of task.flow.reports) report.summary ??= defaults.tasks.find(t => t.id === task.id)?.flow.reports.at(-1)?.summary || '作業結果を整理しました。報告を確認してください。';
  }
  saved.version = 3;
  return saved;
}
