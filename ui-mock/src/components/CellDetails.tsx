import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button, Modal, ExpandableSection, FormField, Select, Status, Table, Textarea } from '../ui';
import { addCellInstruction, insertCell, retryCell } from '../mock/actions';
import { elapsedText, flowCells, supported, type Cell, type Task, type WaitingEnd } from '../mock/model';
import { useStore } from '../store';
import { Document } from './Document';
import { OwnerDetails } from './OwnerDetails';
import { ReportView } from './Report';

export function CellDetails({ task, cell, waiting, close }: { task: Task; cell?: Cell; waiting?: WaitingEnd; close: () => void }) {
  const { state, update } = useStore(), navigate = useNavigate();
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [input, setInput] = useState(''), [executor, setExecutor] = useState(cell?.executor || '');
  const [position, setPosition] = useState<'after' | 'parallel' | null>(null), [type, setType] = useState('verify.lint'), [addition, setAddition] = useState('');
  if (waiting) return <div className="stack" data-testid="cell-details"><Status value="返答待ち"/><p>これはセルではなく分岐の終端です。</p><h3>オブザーバーの判断</h3><p>{waiting.reason}</p><Button onClick={() => navigate(`/tasks/${task.id}?tab=flow&cell=${waiting.observerId}`)}>判断したオブザーバーを開く</Button><Button onClick={() => navigate(`/tasks/${task.id}?tab=report`)}>報告と問いを開く</Button></div>;
  if (!cell) return <p>合流は各分岐の出力が揃う位置です。セルを選ぶと作業の詳細が開きます。</p>;
  if (cell.kind === 'owner') return <OwnerDetails task={task} cell={cell}/>;
  const live = task.state !== '完了' && task.state !== '中止';
  const source = task.flow.rounds.find(r => [r.judge, ...r.branches.flatMap(b => b.cells), ...(r.report ? [r.report] : [])].some(c => c.id === cell.id));
  const needsRestart = cell.state !== '動作中' || source?.joined;
  const submit = (restart = false) => { update(s => addCellInstruction(s.tasks.find(t => t.id === task.id)!, cell.id, input, restart), restart ? '後続の成果を破棄し、このセルから再開しました。' : 'このセルへ追加入力を送りました。'); setInput(''); setConfirmRestart(false); };
  return <div className="stack cell-details" data-testid="cell-details"><div className="section-heading"><h3>{cell.type}</h3><Status value={cell.state}/></div><dl className="details-grid"><dt>実行器</dt><dd>{cell.executor}</dd>{cell.model !== undefined && <><dt>モデル</dt><dd>{cell.model || '実行器の既定'}</dd></>}<dt>出所</dt><dd>{cell.origin}</dd><dt>経過時間</dt><dd>{elapsedText(cell.elapsed)}</dd></dl>{cell.decision && <strong>{cell.decision}</strong>}{cell.badge && <span className="tag">{cell.badge}</span>}
    <ExpandableSection headerText="この試行に与えた入力" defaultExpanded><p className="prompt-text">{cell.input}</p>{cell.extraInputs.map((text, i) => <p className="prompt-text" key={i}>{text}</p>)}</ExpandableSection>
    <section><h3>{cell.state === '動作中' ? 'いまの作業' : '最終応答'}</h3><Document body={cell.output}/></section>
    <ExpandableSection headerText="プロンプト"><h4>{['report', 'judge', 'observe'].includes(cell.kind) ? 'roleの注入プロンプト' : 'type の事前プロンプト'}</h4><p>{cell.prePrompt}</p>{cell.skills && <><h4>skill指定</h4><p>{cell.skills.join('、') || '指定なし'}</p></>}</ExpandableSection>
    <Table variant="embedded" header={<h3>使ったツール</h3>} columnDefinitions={[{ id: 'name', header: '名前', cell: t => t.name }, { id: 'count', header: '回数', cell: t => t.count }]} items={cell.tools} empty="使ったツールはありません。"/>
    <section><h3>試行の履歴</h3>{cell.attempts.length ? cell.attempts.map(a => <ExpandableSection key={a.cellId} headerText={`${a.executor} · ${a.state}`}><h4>試行に与えた入力</h4><p className="prompt-text">{a.input || flowCells(task.flow).find(c => c.id === a.cellId)?.input || cell.input}</p>{a.output && <><h4>最終応答</h4><Document body={a.output}/></>}</ExpandableSection>) : <p>このセルの初回の実行です。</p>}</section>
    {cell.extraInputs.length > 0 && <section data-testid="extra-inputs"><h3>オーナーからの追加入力</h3>{cell.extraInputs.map((x, i) => <p className="prompt-text" key={i}>{x}</p>)}</section>}
    {live && <FormField label="指示を追加"><Textarea ariaLabel="セルへの追加入力" value={input} onChange={({ detail }) => setInput(detail.value)}/><div className="form-action"><Button disabled={!input.trim()} onClick={() => needsRestart ? setConfirmRestart(true) : submit()}>送信</Button></div></FormField>}
    <Modal visible={confirmRestart} onDismiss={() => setConfirmRestart(false)} header="このセルからやり直す" closeAriaLabel="やり直しの確認を閉じる" footer={<div className="button-row align-right"><Button onClick={() => setConfirmRestart(false)}>戻る</Button><Button variant="primary" onClick={() => submit(true)}>破棄してやり直す</Button></div>}><p>後続のセルの成果を破棄し、このセルからやり直しますか？</p><p className="prompt-text">{input}</p></Modal>
    {live && ['終わった', '失敗した'].includes(cell.state) && <div className="stack"><FormField label="再試行する実行器"><Select ariaLabel="再試行する実行器" selectedOption={{ label: executor, value: executor }} onChange={({ detail }) => setExecutor(detail.selectedOption.value!)} options={state.executors.filter(e => supported(e, cell.type)).map(e => ({ label: e.id, value: e.id, disabled: e.life !== '生きている', description: e.life }))}/></FormField><Button disabled={!state.executors.some(e => e.id === executor && e.life === '生きている')} onClick={() => { let result: string | undefined; update(s => { const t = s.tasks.find(t => t.id === task.id)!; result = retryCell(t, flowCells(t.flow).find(c => c.id === cell.id)!, executor); }, '同じ type と入力でセルを再試行しました。'); navigate(`/tasks/${task.id}?tab=flow&cell=${result}`); }}>セルを再試行する</Button></div>}
    {cell.kind === 'report' && <><Button onClick={() => { close(); navigate(`/tasks/${task.id}?tab=report&report=${cell.id}`); }}>報告タブへ</Button>{task.flow.reports.find(r => r.id === cell.id)?.questions.some(q => !q.answer) && <ReportView task={task}  selectedReport={cell.id}/>}</>}
    {live && <div className="button-row"><Button onClick={() => { setPosition('after'); setAddition(''); }}>この次にセルを追加</Button><Button onClick={() => { setPosition('parallel'); setAddition(''); }}>並列するセルを追加</Button></div>}
    <Modal visible={position !== null} onDismiss={() => setPosition(null)} header={position === 'parallel' ? '並列するセルを追加' : 'この次にセルを追加'} closeAriaLabel="セルの追加を閉じる" footer={<div className="button-row align-right"><Button onClick={() => setPosition(null)}>戻る</Button><Button variant="primary" disabled={!addition.trim() || !state.executors.some(e => e.life === '生きている' && supported(e, type))} onClick={() => { let added: string | undefined; update(s => { added = insertCell(s.tasks.find(t => t.id === task.id)!, cell.id, position!, type, addition, s.executors); }, '指定した位置にセルを追加しました。'); setPosition(null); if (added) navigate(`/tasks/${task.id}?tab=flow&cell=${added}`); }}>セルを追加する</Button></div>}>
      <div className="stack"><p>対象：{cell.type} · {cell.executor}</p><FormField label="type"><Select ariaLabel="追加するtype" selectedOption={{ value: type, label: type }} options={['break-down', 'implement', 'review', 'summarize', 'verify.test', 'verify.lint'].map(t => ({ value: t, label: t }))} onChange={({ detail }) => setType(detail.selectedOption.value!)}/></FormField><FormField label="セルへの入力"><Textarea ariaLabel="追加するセルへの入力" value={addition} onChange={({ detail }) => setAddition(detail.value)}/></FormField></div>
    </Modal>
  </div>;
}
