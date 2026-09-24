import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button, ExpandableSection, FormField, Select, Status, Table, Textarea } from '../ui';
import { extraInput, retryCell } from '../mock/actions';
import { elapsedText, latestRun, runCells, supported, type Cell, type Run, type Task, type WaitingEnd } from '../mock/model';
import { useStore } from '../store';
import { Document } from './Document';
import { ReportView } from './Report';

export function CellDetails({ task, run, cell, waiting, close }: { task: Task; run: Run; cell?: Cell; waiting?: WaitingEnd; close: () => void }) {
  const { state, update } = useStore(), navigate = useNavigate();
  const [input, setInput] = useState(''), [executor, setExecutor] = useState(cell?.executor || '');
  if (waiting) return <div className="stack" data-testid="cell-details"><Status value="返答待ち"/><p>これはセルではなく分岐の終端です。</p><h3>オブザーバーの判断</h3><p>{waiting.reason}</p><Button onClick={() => navigate(`/tasks/${task.id}?run=${run.id}&tab=flow&cell=${waiting.observerId}`)}>判断したオブザーバーを開く</Button><Button onClick={() => navigate(`/tasks/${task.id}?run=${run.id}&tab=report`)}>報告と問いを開く</Button></div>;
  if (!cell) return <p>合流は各分岐の出力が揃う位置です。セルを選ぶと作業の詳細が開きます。</p>;
  const live = task.state !== '完了' && task.state !== '中止' && run.id === latestRun(task).id;
  return <div className="stack cell-details" data-testid="cell-details"><div className="section-heading"><h3>{cell.type}</h3><Status value={cell.state}/></div><dl className="details-grid"><dt>実行器</dt><dd>{cell.executor}</dd><dt>出所</dt><dd>{cell.origin}</dd><dt>経過時間</dt><dd>{elapsedText(cell.elapsed)}</dd></dl>{cell.decision && <strong>{cell.decision}</strong>}{cell.badge && <span className="tag">{cell.badge}</span>}
    <section><h3>いまの作業</h3><Document body={cell.output}/></section>
    <ExpandableSection headerText="プロンプト"><h4>type の事前プロンプト</h4><p>{cell.prePrompt}</p><h4>入力</h4><div className="prompt-text">{cell.input}</div></ExpandableSection>
    <Table variant="embedded" header={<h3>使ったツール</h3>} columnDefinitions={[{ id: 'name', header: '名前', cell: t => t.name }, { id: 'count', header: '回数', cell: t => t.count }]} items={cell.tools} empty="使ったツールはありません。"/>
    <section><h3>試行の履歴</h3>{cell.attempts.length ? cell.attempts.map(a => <p key={a.cellId}><Status value={a.state}/> · {a.executor} · {a.source}</p>) : <p>このセルの初回の実行です。</p>}</section>
    {cell.extraInputs.length > 0 && <section data-testid="extra-inputs"><h3>オーナーからの追加入力</h3>{cell.extraInputs.map((x, i) => <p className="prompt-text" key={i}>{x}</p>)}</section>}
    {live && cell.state === '動いている' && <FormField label="追加入力"><Textarea ariaLabel="セルへの追加入力" value={input} onChange={({ detail }) => setInput(detail.value)}/><div className="form-action"><Button disabled={!input.trim()} onClick={() => { update(s => extraInput(runCells(latestRun(s.tasks.find(t => t.id === task.id)!)).find(c => c.id === cell.id)!, input), 'このセルへ追加入力を送りました。'); setInput(''); }}>追加入力を送る</Button></div></FormField>}
    {live && ['終わった', '失敗した'].includes(cell.state) && cell.kind !== 'owner' && <div className="stack"><FormField label="再試行する実行器"><Select ariaLabel="再試行する実行器" selectedOption={{ label: executor, value: executor }} onChange={({ detail }) => setExecutor(detail.selectedOption.value!)} options={state.executors.filter(e => supported(e, cell.type)).map(e => ({ label: e.id, value: e.id, disabled: e.life !== '生きている', description: e.life }))}/></FormField><Button disabled={!state.executors.some(e => e.id === executor && e.life === '生きている')} onClick={() => { let result: string | undefined; update(s => { const t = s.tasks.find(t => t.id === task.id)!; result = retryCell(t, runCells(latestRun(t)).find(c => c.id === cell.id)!, executor); }, '同じ type と入力でセルを再試行しました。'); navigate(`/tasks/${task.id}?run=${run.id}&tab=flow&cell=${result}`); }}>セルを再試行する</Button></div>}
    {cell.kind === 'report' && <><Button onClick={() => { close(); navigate(`/tasks/${task.id}?run=${run.id}&tab=report&report=${cell.id}`); }}>報告タブへ</Button>{run.reports.find(r => r.id === cell.id)?.questions.some(q => !q.answer) && <ReportView task={task} run={run} selectedReport={cell.id}/>}</>}
    <Button onClick={() => navigate(`/tasks/${task.id}?run=${run.id}&tab=flow&cell=${cell.id}`)}>フロー図のこのセルへ</Button>
  </div>;
}
