import { createContext, useContext, useState, type ReactNode } from 'react';
import { seed } from './mock/seed';
import type { MockState } from './mock/model';
const key = 'pda-ui-mock-v2';
function initial(): MockState { try { const stored = JSON.parse(localStorage.getItem(key) || 'null'); if (stored?.version === 1) return stored; } catch { /* A malformed saved scene can be reset. */ } const value = seed(); localStorage.setItem(key, JSON.stringify(value)); return value; }
interface Store { state: MockState; update: (change: (s: MockState) => void, message?: string) => void; replace: (s: MockState) => void; notice: string; notify: (s: string) => void }
const Context = createContext<Store>(null!);
export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, set] = useState(initial), [notice, notify] = useState('');
  const replace = (s: MockState) => { set(s); localStorage.setItem(key, JSON.stringify(s)); };
  const update = (change: (s: MockState) => void, message = '操作を受け付けました。') => { const next = structuredClone(state); change(next); replace(next); notify(message); };
  return <Context.Provider value={{ state, update, replace, notice, notify }}>{children}</Context.Provider>;
}
export const useStore = () => useContext(Context);
