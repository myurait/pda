import { createContext, useContext, useState, type ReactNode } from 'react';
import { migrate } from './mock/migrate';
import { seed } from './mock/seed';
import { flowCells } from './mock/model';
import type { MockState } from './mock/model';
const key = 'pda-ui-mock-v2';
function initial(): MockState { try { const stored = JSON.parse(localStorage.getItem(key) || 'null'); if ([2, 3].includes(stored?.version)) { const value = migrate(stored); localStorage.setItem(key, JSON.stringify(value)); return value; } } catch { /* A malformed saved scene can be reset. */ } const value = seed(); localStorage.setItem(key, JSON.stringify(value)); return value; }
interface Store { state: MockState; update: (change: (s: MockState) => void, message?: string) => void; replace: (s: MockState) => void; notice: string; notify: (s: string) => void }
const Context = createContext<Store>(null!);
export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, set] = useState(initial), [notice, notify] = useState('');
  const replace = (s: MockState) => { set(s); localStorage.setItem(key, JSON.stringify(s)); };
  const update = (change: (s: MockState) => void, message = '操作を受け付けました。') => {
    const existing = new Set(state.tasks.flatMap(t => flowCells(t.flow).map(c => c.id)));
    const next = structuredClone(state); change(next);
    for (const task of next.tasks) for (const cell of flowCells(task.flow)) {
      const role = next.roles.find(r => r.id === cell.kind);
      if (role && !existing.has(cell.id)) {
        cell.executor = role.executor; cell.model = role.model; cell.prePrompt = role.prompt; cell.skills = [...role.skills];
        const report = task.flow.reports.find(r => r.id === cell.id); if (report) report.author = role.executor;
      }
    }
    for (const task of next.tasks) { const cells = flowCells(task.flow); for (const cell of cells) for (const attempt of cell.attempts) { const current = cells.find(c => c.id === attempt.cellId); if (current) attempt.state = current.state; } }
    replace(next); notify(message);
  };
  return <Context.Provider value={{ state, update, replace, notice, notify }}>{children}</Context.Provider>;
}
export const useStore = () => useContext(Context);
