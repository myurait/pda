export type CellState = '待機' | '動いている' | '終わった' | '失敗した' | '中断した';
export type TaskState = '進行中' | '入力待ち' | '完了' | '中止';
export type CellKind = 'owner' | 'judge' | 'work' | 'observe' | 'report';
export type Origin = 'フロー定義' | '前のセルの指示' | '判定器' | 'オブザーバー' | 'オーナーの操作';
export interface Attempt { cellId: string; executor: string; state: CellState; source: Origin }
export interface Cell {
  id: string; kind: CellKind; type: string; executor: string; state: CellState; elapsed: number;
  origin: Origin; input: string; prePrompt: string; output: string; tools: { name: string; count: number }[];
  attempts: Attempt[]; badge?: string; decision?: string; extraInputs: string[];
}
export interface WaitingEnd { id: string; observerId: string; reason: string }
export interface Branch { id: string; label: string; cells: Cell[]; waiting?: WaitingEnd }
export interface Round { id: string; number: number; owners: Cell[]; judge: Cell; branches: Branch[]; joined: boolean; report?: Cell }
export interface Question { id: string; text: string; kind: 'approval' | 'choice' | 'text'; options?: string[]; answer?: string }
export interface Report { id: string; title: string; author: string; time: string; body: string; format: 'markdown' | 'html'; questions: Question[]; artifactIds: string[] }
export interface Run { id: string; state: Exclude<CellState, '待機'>; rounds: Round[]; reports: Report[]; stage: number }
export interface Artifact { id: string; kind: 'file' | 'git' | 'external'; name: string; path: string; size?: string; updated: string; content: string; mime: string; branch?: string; commit?: string; changedFiles?: number }
export interface Task { id: string; title: string; initial: string; directive: string; state: TaskState; waitingReason?: string; reporter: string; workdir: string; elapsed: number; updated: string; runs: Run[]; artifacts: Artifact[]; attention?: string }
export interface Executor { id: string; name: string; environment: string; account: string; types: string[]; life: '生きている' | '止まっている' | '不明' }
export type Scene = '通常' | 'タスクなし' | '読み込み中' | '上流に届かない' | '60件のタスク' | '入力待ちなし' | '実行器が不明';
export interface MockState { version: number; tasks: Task[]; executors: Executor[]; scene: Scene; tick: number }
export const latestRun = (task: Task) => task.runs[task.runs.length - 1];
export const roundCells = (round: Round): Cell[] => [...round.owners, round.judge, ...round.branches.flatMap(b => b.cells), ...(round.report ? [round.report] : [])];
export const runCells = (run: Run) => run.rounds.flatMap(roundCells);
export const activeCells = (task: Task) => runCells(latestRun(task)).filter(c => c.state === '動いている');
export const currentReport = (task: Task, run = latestRun(task)) => run.reports[run.reports.length - 1];
export const pendingTasks = (state: MockState) => state.tasks.filter(t => t.state === '入力待ち');
export const executorCells = (state: MockState, executor: string) => state.tasks.flatMap(task => activeCells(task).filter(cell => cell.executor === executor).map(cell => ({ task, cell })));
export const elapsedText = (seconds: number) => seconds < 60 ? `${seconds}秒` : seconds < 3600 ? `${Math.floor(seconds / 60)}分${seconds % 60 ? ` ${seconds % 60}秒` : ''}` : `${Math.floor(seconds / 3600)}時間 ${Math.floor(seconds % 3600 / 60)}分`;
export const supported = (e: Executor, type: string) => e.types.includes(type) || (['observe', 'report'].includes(type) && e.types.includes('summarize'));
