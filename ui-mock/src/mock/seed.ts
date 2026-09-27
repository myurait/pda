import type { Artifact, Branch, Cell, CellKind, CellState, Executor, MockState, Report, Round, Task, TaskState, RoleConfig, Skill } from './model';
import { lastUserInput } from './model';
import { coreReport, diagramSvg, longReport, shortReport, typePrompts } from './content';

export const executors: Executor[] = [
  { id: 'codex-personal', name: 'Codex 個人契約', environment: 'minipc', account: 'personal', types: ['break-down', 'implement', 'review', 'summarize'], life: '生きている' },
  { id: 'claude-personal', name: 'Claude Code 個人契約', environment: 'minipc', account: 'personal', types: ['break-down', 'implement', 'review', 'summarize'], life: '生きている' },
  { id: 'jev', name: 'jev 判定器', environment: 'minipc', account: 'none', types: ['judge'], life: '生きている' },
  { id: 'tools', name: '検証ツール', environment: 'minipc', account: 'none', types: ['verify.test', 'verify.lint'], life: '生きている' },
  { id: 'fake-a', name: '試験用エージェント A', environment: 'minipc', account: 'none', types: ['break-down', 'implement', 'review', 'summarize'], life: '生きている' },
  { id: 'fake-b', name: '試験用エージェント B', environment: 'minipc', account: 'none', types: ['break-down', 'implement', 'review', 'summarize'], life: '止まっている' },
];
export const skills: Skill[] = [
  { id: 'report-format', name: '報告の整形', path: 'skills/report-format/SKILL.md', description: '確認した結果と判断事項をまとめる' },
  { id: 'code-review', name: 'コードレビュー', path: 'skills/code-review/SKILL.md', description: '要求と実装の対応を確認する' },
  { id: 'task-observation', name: 'タスクの観察', path: 'skills/task-observation/SKILL.md', description: '失敗原因と再開に必要な条件を整理する' },
];
executors[0].usageScript = 'scripts/codex-usage.sh';
executors[0].usage = [{ title: '5時間制限', value: '75%', limit: '100%', alert: 'warning' }, { title: '週制限', value: '95%', limit: '100%', alert: 'critical' }, { title: 'クレジット利用額', value: '1$' }];
executors[1].usageScript = 'scripts/claude-usage.sh';
executors[1].usage = [{ title: '契約クレジット残量', value: '28,000 credits' }, { title: '従量課金額', value: '$12.40' }];
export const roles: RoleConfig[] = [
  { id: 'report', name: '報告担当', executor: 'claude-personal', model: '', prompt: typePrompts.report, skills: [] },
  { id: 'judge', name: '判定器', executor: 'jev', model: '', prompt: typePrompts.judge, skills: [] },
  { id: 'observe', name: 'タスクオブザーバー', executor: 'claude-personal', model: '', prompt: typePrompts.observe, skills: [] },
];
export function cell(id: string, type: string, executor: string, state: CellState = '終わった', patch: Partial<Cell> = {}): Cell {
  const kind: CellKind = executor === 'オーナー' ? 'owner' : type === 'judge' ? 'judge' : type === 'observe' ? 'observe' : type === 'report' ? 'report' : 'work';
  return { id, type, executor, state, kind, elapsed: state === '待機' ? 0 : 140, origin: kind === 'owner' ? 'オーナーの操作' : '判定器',
    prePrompt: typePrompts[type] || typePrompts.implement, input: '前のセルの確認結果を読み、入力の条件に沿って作業を進める。',
    output: `## いまの作業\n\n${state === '動作中' ? '入力の条件を確認し、変更を検証しています。' : '確認した結果を次のセルへ渡しました。'}`,
    tools: kind === 'work' ? [{ name: 'read_file', count: 4 }, { name: 'exec_command', count: 2 }] : [], attempts: [], extraInputs: [], ...patch };
}
export function round(id: string, number: number, branches: Branch[], patch: Partial<Round> = {}): Round {
  return { id, number, owners: [], judge: cell(`${id}-judge`, 'judge', 'jev', '終わった', { decision: `${branches.length} 本に分岐`, origin: 'フロー定義' }), branches, joined: branches.every(b => b.cells.every(c => c.state !== '動作中' && c.state !== '待機')), ...patch };
}
const branch = (id: string, label: string, cells: Cell[]): Branch => ({ id, label, cells });
export function task(id: string, title: string, branches: Branch[], state: TaskState = '進行中'): Task {
  const initial = `${title}。スマートフォンでも使える形にし、変更した理由と検証の結果を読める報告にまとめてください。`;
  return { id, title, initial, directive: initial, state, lastInstructionAt: Date.now() - 1420000, workdir: `/work/pda/${id}`, elapsed: 1420, updated: '2026-09-25 09:42', flow: { rounds: [round(`${id}-r1`, 1, branches, { owners: [cell(`${id}-owner`, '指示', 'オーナー', '終わった', { input: initial, output: initial, origin: 'フロー定義' })] })], reports: [], stage: 0 }, artifacts: [] };
}
export function attachReport(t: Task, body: string, questions: Report['questions'] = [], format: Report['format'] = 'markdown', config: RoleConfig = roles[0], presentation: { summary: string; artifactIds: string[] } = { summary: '作業結果を整理しました。報告を確認してください。', artifactIds: [] }) {
  const flow = t.flow, last = flow.rounds.at(-1)!;
  const id = `${last.id}-report`;
  last.joined = true;
  last.report = cell(id, 'report', config.executor, '終わった', { model: config.model, prePrompt: config.prompt, skills: [...config.skills], origin: 'フロー定義', output: '合流した結果をまとめ、オーナー向けの報告を書きました。', badge: questions.length ? '問いあり' : undefined });
  flow.reports.push({ id, title: t.title, author: config.executor, time: '2026-09-25 09:40', body, format, questions, userInput: lastUserInput(t), summary: presentation.summary, artifactIds: presentation.artifactIds });
  t.state = '入力待ち'; t.waitingSince = Date.now(); t.stoppedAt = undefined; t.waitingReason = questions.length ? '判断を求めています' : '次の指示を待っています';
}
function artifacts(): Artifact[] {
  return [
    { id: 'notes', kind: 'file', name: '設計ノート.md', path: '/work/pda/result/design-notes.md', size: '4.8 KB', updated: '2026-09-25 09:38', mime: 'text/markdown', content: '# 画面 API の設計ノート\n\n## 受け渡し\n\nタスクとセルを識別し、指示から報告までを一続きのフローとして保持します。\n\n| 入力 | 出力 |\n| --- | --- |\n| オーナーの指示 | 判定器の入力 |\n| 分岐の結果 | 合流後の報告 |\n\n## 検証\n\n- 依頼から報告までを確認\n- 問いへの返答後に次の回へ進むことを確認' },
    { id: 'diagram', kind: 'file', name: '構成図.svg', path: '/work/pda/result/flow.svg', size: '0.9 KB', updated: '2026-09-25 09:39', mime: 'image/svg+xml', content: diagramSvg },
    { id: 'git', kind: 'git', name: '画面 API の変更', path: 'git://minipc/pda', branch: 'feature/task-api', commit: '8e2c9a1', changedFiles: 7, updated: '2026-09-25 09:39', mime: 'text/plain', content: 'リポジトリ: git://minipc/pda\nブランチ: feature/task-api\nコミット: 8e2c9a1\n変更ファイル数: 7\n\nこの所在は見本です。' },
    { id: 'published', kind: 'external', name: '画面 API の共有資料', path: 'https://example.invalid/pda/task-api', updated: '2026-09-25 09:40', mime: 'text/markdown', content: '# 画面 API の共有資料\n\n公開先の内容の見本です。\n\nタスクを受け付け、フローを返し、報告と成果物を別々に提供します。' },
  ];
}
export function seed(): MockState {
  const api = task('api', '画面 API を実装する', [
    branch('api-b1', '一覧 API', [cell('api-implement', 'implement', 'codex-personal', '動作中', { elapsed: 820, input: 'タスク一覧の状態と入力待ちの理由を返す API を実装する。', output: '## 一覧 API の実装\n\n状態の絞り込みを実装済み。**ページ送りの境界**を確認しています。' })]),
    branch('api-b2', '型の確認', [cell('api-review', 'review', 'codex-personal', '動作中', { elapsed: 780, output: '## 応答の確認\n\nセルの状態とタスクの状態を分け、型の対応を照合しています。' })]),
  ]);
  const sessions = task('sessions', '旧アプリのセッションを取り込む', [branch('sessions-b1', '取り込み', [cell('sessions-implement', 'implement', 'codex-personal', '動作中', { elapsed: 2420, output: '## 取り込みの照合\n\n**204 件の索引**を作成しました。本文と添付ファイルの参照を照合しています。' })])]); sessions.attention = '長時間の作業';
  const retryOriginal = cell('retry-failed', 'implement', 'fake-a', '失敗した', { output: '一時的な接続エラーで入力を取得できませんでした。' });
  const retryCopy = cell('retry-copy', 'implement', 'fake-a', '動作中', { badge: '判定器の再試行・複製', input: retryOriginal.input, output: '接続が戻りました。同じ入力で実装を再開しています。' });
  retryOriginal.attempts = [{ cellId: retryOriginal.id, executor: 'fake-a', state: '失敗した', source: '判定器' }, { cellId: retryCopy.id, executor: 'fake-a', state: '動作中', source: '判定器' }];
  const retry = task('retry', '接続が途切れた取り込み処理を再試行する', [branch('retry-b1', '取り込み処理', [retryOriginal, cell('retry-a', 'judge', 'jev', '終わった', { decision: '分岐 A：再試行', input: retryOriginal.output }), retryCopy])]); retry.attention = '再試行で立て直し中';
  const environment = task('environment', '検証環境を整えてテストを再開する', [branch('environment-b1', '環境の問題を扱う', [
    cell('env-failed', 'verify.test', 'tools', '失敗した', { output: 'テスト用のデータディレクトリが存在しません。' }),
    cell('env-a', 'judge', 'jev', '終わった', { decision: '分岐 A：オブザーバー' }),
    cell('env-b', 'observe', 'claude-personal', '終わった', { decision: '分岐 B：判断不要・仕事を分ける', output: '## 判断\n\nオーナーの判断は不要です。環境の準備と本来のテストを分けるよう指示します。自分では作業しません。' }),
    cell('env-plan', 'break-down', 'claude-personal', '終わった', { origin: 'オブザーバー', badge: 'オブザーバーの指示', output: '環境の準備を実装し、その後に検証を行う二段に分けました。' }),
    cell('env-redo', 'implement', 'claude-personal', '動作中', { origin: 'オブザーバー', badge: '指示に従ってやり直し', output: '不足していたデータの準備スクリプトを実装しています。' }),
  ])]); environment.attention = 'オブザーバーから立て直し中';
  const qBranch: Branch = { ...branch('questions-b1', '保存範囲の確認', [
    cell('q-failed', 'review', 'claude-personal', '失敗した', { output: '共有の可否が判別できない記録があります。保存範囲の方針が必要です。' }),
    cell('q-a', 'judge', 'jev', '終わった', { decision: '分岐 A：オブザーバー' }),
    cell('q-b', 'observe', 'claude-personal', '終わった', { decision: '分岐 B：オーナーの判断が必要', output: '保存範囲と取り込み先はオーナーの判断が必要です。推定では決めず、この分岐を返答待ちで終えます。' }),
  ]), waiting: { id: 'q-wait', observerId: 'q-b', reason: '保存範囲と取り込み先をオーナーが選ぶ必要があります。推定による変更はできません。' } };
  const questions = task('questions', '判定器の問いと保存範囲を見直す', [qBranch, branch('questions-b2', '索引の確認', [cell('q-index', 'summarize', 'fake-a')])], '入力待ち');
  questions.branch = 'feature/question-context';
  questions.artifacts = [
    { ...artifacts()[0], path: '/work/pda/questions/docs/design-notes.md' },
    { id: 'review-html', kind: 'file', name: 'review.html', path: '/work/pda/questions/reports/review.html', updated: '2026-09-25 09:40', mime: 'text/html', content: '<h1>保存範囲の比較</h1><p>個人の記録と共有候補を分け、保存先を確認するための資料です。</p>' },
    { id: 'mockup', kind: 'external', name: '画面モック', path: 'http://localhost:8767/#/overview', updated: '2026-09-25 09:40', mime: 'text/html', content: '' },
  ];
  attachReport(questions, shortReport, [
    { id: 'approve', text: '個人の記録を読み取り専用で取り込みますか', kind: 'approval' },
    { id: 'destination', text: '取り込み先を選んでください', kind: 'choice', options: ['個人の記憶に保存', '共有の候補として保留', '今回は見送る'] },
    { id: 'conditions', text: '保存するときに守る条件を教えてください', kind: 'text' },
  ]);
  Object.assign(questions.flow.reports.at(-1)!, { summary: '読み取り専用で索引を確認済みです。保存範囲と取り込み先の判断が必要です。', artifactIds: ['mockup', 'review-html', 'notes'] });
  const result = task('result', '画面 API の実装結果を受け取る', [branch('result-b1', '検証', [cell('result-test', 'verify.test', 'tools'), cell('result-finish', 'judge', 'jev', '終わった', { decision: '自動で進める作業なし' })])], '入力待ち'); result.artifacts = artifacts(); attachReport(result, longReport); Object.assign(result.flow.reports.at(-1)!, { summary: '画面 API の実装と検証が完了しました。結果を確認し、続行する場合は次の指示を入力してください。', artifactIds: ['notes', 'diagram'] });
  const interrupted = task('interrupted', '意図しない実行器への割り振りを直す', [branch('interrupted-b1', '割り振りの修正', [cell('int-work', 'implement', 'fake-a', '中断した'), cell('int-owner', '中断指示', 'オーナー', '終わった', { input: 'この環境では書き込みをしないでください。', badge: 'オーナーが中断' }), cell('int-a', 'judge', 'jev', '終わった', { decision: '分岐 A：オブザーバー' }), cell('int-b', 'observe', 'claude-personal', '動作中', { decision: '分岐 B：確認中', output: 'オーナーの中断理由に従って、読み取りだけで進める方法を確認しています。' })])]);
  const core = task('core', '検証用実行器の起動を確認する', [branch('core-b1', '起動確認', [cell('core-failed', 'verify.test', 'tools', '失敗した'), cell('core-a', 'judge', 'jev', '終わった', { decision: '分岐 A：再試行', output: '同じ入力で再試行を指示しました。' }), cell('core-copy', 'verify.test', 'tools', '失敗した', { badge: '判定器の再試行・複製', output: 'フォールバック起動が失敗。コアの規則に該当しました。' })])], '入力待ち'); attachReport(core, coreReport, [], 'html'); core.waitingReason = 'タスクが中断されています'; core.flow.reports.at(-1)!.summary = '検証用実行器の再起動に失敗して中断しました。起動設定の確認が必要です。';
  const restart = task('restart', '検索画面を新しい指示でやり直す', [branch('restart-old-b', '旧案', [cell('restart-old-work', 'implement', 'fake-a')])]);
  attachReport(restart, '# 以前の指示への報告\n\n旧案の検索欄を実装しました。新しい指示から作業を再開しました。');
  const revised = '検索対象を指示とタスク識別子に絞り、スマートフォンを先に確認してください。';
  restart.flow.rounds.push(round('restart-r2', 2, [branch('restart-new-b', '新案', [cell('restart-new-work', 'implement', 'fake-a', '動作中')])], { owners: [cell('restart-rewrite', '書き換え', 'オーナー', '終わった', { input: revised, badge: '書き換え・最初から' })] })); restart.directive = revised; restart.state = '進行中'; restart.waitingReason = undefined;
  const large = task('large', '8 回に分けて移行手順を整える', []);
  const rounds: Round[] = Array.from({ length: 8 }, (_, i) => round(`large-r${i + 1}`, i + 1, Array.from({ length: i < 5 ? 3 : 2 }, (_, j) => branch(`large-${i}-b${j}`, `検証 ${j + 1}`, [cell(`large-${i}-c${j}`, j === 0 ? 'verify.test' : 'summarize', j === 0 ? 'tools' : 'fake-a', i === 7 ? '動作中' : '終わった', j === 1 && i === 5 ? { origin: 'オーナーの操作', badge: 'オーナーが挿入' } : {})]))));
  rounds[0].owners = large.flow.rounds[0].owners; large.flow.rounds = rounds;
  const complete = task('complete', 'README の開き方を確認する', [branch('complete-b1', '確認', [cell('complete-work', 'review', 'fake-a', '終わった', { badge: 'オーナーの再試行', origin: 'オーナーの操作', attempts: [{ cellId: 'complete-first', executor: 'fake-b', state: '失敗した', source: '判定器' }, { cellId: 'complete-work', executor: 'fake-a', state: '終わった', source: 'オーナーの操作' }] })])]); attachReport(complete, '# README の確認結果\n\n記載された手順で開けることを確認しました。成果物はありません。'); complete.state = '完了'; complete.waitingReason = undefined;
  const cancelled = task('cancelled', '古い索引の更新を取りやめる', [branch('cancelled-b1', '索引', [cell('cancelled-work', 'implement', 'fake-a', '中断した')])], '中止');
  const now = Date.now();
  [questions, result, core].forEach((t, i) => { t.waitingSince = now - (i + 1) * 300000; t.lastInstructionAt = t.waitingSince - t.elapsed * 1000; });
  [complete, cancelled].forEach(t => { t.stoppedAt = now; t.waitingSince = undefined; t.lastInstructionAt = now - t.elapsed * 1000; });
  return { version: 3, skills: structuredClone(skills), tasks: [questions, result, core, api, sessions, retry, environment, interrupted, restart, large, complete, cancelled], executors: structuredClone(executors), roles: structuredClone(roles), scene: '通常', tick: 0 };
}
