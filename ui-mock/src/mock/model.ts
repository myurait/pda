export type CellState = '待機' | '動作中' | '終わった' | '失敗した' | '中断した';
export type TaskState = '進行中' | '入力待ち' | '完了' | '中止';
export type CellKind = 'owner' | 'judge' | 'work' | 'observe' | 'report';
export type Origin = 'フロー定義' | '前のセルの指示' | '判定器' | 'オブザーバー' | 'オーナーの操作';
export interface Attempt { cellId: string; executor: string; state: CellState; source: Origin; input?: string; output?: string }
export interface Cell {
  id: string; kind: CellKind; type: string; executor: string; state: CellState; elapsed: number;
  origin: Origin; input: string; prePrompt: string; output: string; tools: { name: string; count: number }[];
  attempts: Attempt[]; badge?: string; decision?: string; extraInputs: string[]; after?: string; model?: string; skills?: string[];
}
export interface WaitingEnd { id: string; observerId: string; reason: string }
export interface Branch { id: string; label: string; cells: Cell[]; waiting?: WaitingEnd }
export interface Round { id: string; number: number; owners: Cell[]; judge: Cell; branches: Branch[]; joined: boolean; report?: Cell }
export interface Question { id: string; text: string; kind: 'approval' | 'choice' | 'text'; options?: string[]; answer?: string }
export interface Report { id: string; title: string; author: string; time: string; body: string; format: 'markdown' | 'html'; questions: Question[]; artifactIds: string[]; summary?: string; userInput?: string }
export interface TaskFlow { rounds: Round[]; reports: Report[]; stage: number }
export interface Artifact { id: string; kind: 'file' | 'git' | 'external'; name: string; path: string; size?: string; updated: string; content: string; mime: string; branch?: string; commit?: string; changedFiles?: number; sourceCellId?: string }
export interface Task { id: string; title: string; initial: string; directive: string; state: TaskState; waitingReason?: string; workdir: string; branch?: string; elapsed: number; updated: string; flow: TaskFlow; artifacts: Artifact[]; attention?: string; lastInstructionAt?: number; waitingSince?: number; stoppedAt?: number }
export interface Executor { id: string; name: string; environment: string; account: string; types: string[]; life: '生きている' | '止まっている' | '不明'; usageScript?: string; usage?: UsageMetric[] }
export type Scene = '通常' | '複数の報告' | 'タスクなし' | '読み込み中' | '上流に届かない' | '60件のタスク' | '入力待ちなし' | '実行器が不明';
export type RoleId = 'report' | 'judge' | 'observe';
export interface RoleConfig { id: RoleId; name: string; executor: string; model: string; prompt: string; skills: string[] }
export interface Skill { id: string; name: string; path: string; description: string }
export interface UsageMetric { title: string; value: string | number; limit?: string | number; alert?: string }
export interface MockState { version: number; tasks: Task[]; executors: Executor[]; roles: RoleConfig[]; skills: Skill[]; scene: Scene; tick: number }
export const roundCells = (round: Round): Cell[] => [...round.owners, round.judge, ...round.branches.flatMap(b => b.cells), ...(round.report ? [round.report] : [])];
export const flowCells = (flow: TaskFlow) => flow.rounds.flatMap(roundCells);
export const activeCells = (task: Task) => flowCells(task.flow).filter(c => c.state === '動作中');
export const currentReport = (task: Task) => task.flow.reports.at(-1);
export const pendingTasks = (state: MockState) => state.tasks.filter(t => t.state === '入力待ち');
export const executorCells = (state: MockState, executor: string) => state.tasks.flatMap(task => activeCells(task).filter(cell => cell.executor === executor).map(cell => ({ task, cell })));
export const elapsedText = (seconds: number) => seconds < 60 ? `${seconds}秒` : seconds < 3600 ? `${Math.floor(seconds / 60)}分${seconds % 60 ? ` ${seconds % 60}秒` : ''}` : `${Math.floor(seconds / 3600)}時間 ${Math.floor(seconds % 3600 / 60)}分`;
export const supported = (e: Executor, type: string) => e.types.includes(type) || (['observe', 'report'].includes(type) && e.types.includes('summarize'));

export function lastUserInput(task: Task, reportId?: string): string {
  const report = task.flow.reports.find(r => r.id === reportId);
  if (report?.userInput !== undefined) return report.userInput;
  const index = reportId ? task.flow.rounds.findIndex(r => r.report?.id === reportId) : -1;
  const rounds = index >= 0 ? task.flow.rounds.slice(0, index + 1) : task.flow.rounds;
  return rounds.flatMap(roundCells).filter(c => c.kind === 'owner').at(-1)?.input || task.initial;
}

export const waitingReasonText = (task: Task) => ({ '報告に問いがあります': '判断を求めています', '自動で進める作業がありません': '次の指示を待っています', 'コアの規則で実行が止まりました': 'タスクが中断されています' }[task.waitingReason || ''] || task.waitingReason || '次の指示を待っています');
export const isTaskInterrupted = (task: Task) => task.state === '入力待ち' && waitingReasonText(task) === 'タスクが中断されています';
export const waitingSeconds = (task: Task, now = Date.now()) => task.state === '入力待ち' && task.waitingSince ? Math.max(0, Math.floor((now - task.waitingSince) / 1000)) : 0;
export const taskElapsedSeconds = (task: Task, now = Date.now()) => task.lastInstructionAt ? Math.max(0, Math.floor((((task.state === '入力待ち' ? task.waitingSince : task.stoppedAt) || now) - task.lastInstructionAt) / 1000)) : task.elapsed;
export function parseUsage(value: string): UsageMetric[] {
  const data: unknown = JSON.parse(value);
  if (!Array.isArray(data) || data.some(item => !item || typeof item.title !== 'string' || !['string', 'number'].includes(typeof item.value) || (item.limit !== undefined && !['string', 'number'].includes(typeof item.limit)) || (item.alert !== undefined && typeof item.alert !== 'string'))) throw new Error('title と value を持つ JSON 配列を指定してください。');
  return data;
}
