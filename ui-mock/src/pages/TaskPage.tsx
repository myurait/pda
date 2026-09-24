import { useCallback, useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { Alert, Button, Container, ExpandableSection, FormField, Header, Modal, RadioGroup, Select, Status, Tabs, Textarea } from '../ui';
import { activeCells, elapsedText, latestRun, type Task } from '../mock/model';
import { addInstruction, insertCell, interruptTask, recordTask, restartTask } from '../mock/actions';
import { useStore } from '../store';
import { Artifacts } from '../components/Artifacts';
import { Flow } from '../components/Flow';
import { ReportView } from '../components/Report';

export function TaskPage() {
  const { taskId } = useParams(), { state, update } = useStore(), [params, setParams] = useSearchParams();
  const task = state.tasks.find(t => t.id === taskId);
  const [operation, setOperation] = useState(''), [input, setInput] = useState(''), [instruction, setInstruction] = useState(''), [mode, setMode] = useState('future'), [type, setType] = useState('verify.lint');
  const selectCell = useCallback((id: string) => setParams(p => { p.set('tab', 'flow'); p.set('cell', id); return p; }), [setParams]);
  const insert = useCallback(() => { setOperation('insert'); setInput(''); }, []);
  if (!task) return <Alert type="warning">タスクが見つかりません。「見本の操作」で初期に戻すと見本を復元できます。</Alert>;
  const run = task.runs.find(r => r.id === params.get('run')) || latestRun(task), tab = params.get('tab') || 'flow';
  const editable = !['完了', '中止'].includes(task.state) && run.id === latestRun(task).id;
  const mutate = (fn: (t: Task) => void, message: string) => update(s => fn(s.tasks.find(t => t.id === task.id)!), message);
  const open = (op: string) => { setOperation(op); setInput(op === 'rewrite' ? task.directive : ''); setMode('future'); };
  const execute = () => {
    if (operation === 'interrupt') mutate(t => interruptTask(t, input), '実行を中断しました。中断理由を判定器へ渡しました。');
    if (operation === 'complete') mutate(t => recordTask(t, '完了'), '完了として記録しました。');
    if (operation === 'cancel') mutate(t => recordTask(t, '中止'), '中止として記録しました。');
    if (operation === 'rewrite') {
      mutate(t => mode === 'restart' ? restartTask(t, input) : addInstruction(t, input, true), mode === 'restart' ? '新しい実行を始めました。前の実行は中断として残っています。' : '書き換えた指示を次の回に加えました。');
      if (mode === 'restart') setParams({ run: `run-${task.runs.length + 1}`, tab: 'flow' });
    }
    if (operation === 'insert') { mutate(t => insertCell(t, type, input, state.executors), '次の回の分岐にセルを挿し込みました。'); setParams({ run: run.id, tab: 'flow' }); }
    setOperation('');
  };
  const modalTitle: Record<string, string> = { interrupt: '実行を中断する', complete: '完了として記録', cancel: '中止として記録', rewrite: '初期の指示を書き換える', insert: '次の回にセルを挿し込む' };
  const confirmText = operation === 'rewrite' ? '書き換えを保存' : operation === 'insert' ? 'セルを挿し込む' : modalTitle[operation];
  const moving = activeCells(task);
  return <div className="stack task-page" data-testid="task-page">
    <Header variant="h1" description={<Status value={task.state}/>}>{task.title}</Header>
    <ExpandableSection headerText="指示の全文"><p className="prompt-text">{task.directive}</p></ExpandableSection>
    <dl className="task-meta"><div><dt>報告を書く実行器</dt><dd>{task.reporter}</dd></div><div><dt>作業ディレクトリ</dt><dd>{task.workdir || '指定なし'}</dd></div><div><dt>経過時間</dt><dd>{elapsedText(task.elapsed)}</dd></div></dl>
    {editable && <div className="button-row task-actions"><Button onClick={() => open('interrupt')} disabled={!moving.length}>中断</Button><Button onClick={() => open('rewrite')}>初期の指示を書き換える</Button><Button onClick={() => open('complete')}>完了として記録</Button><Button onClick={() => open('cancel')}>中止として記録</Button></div>}
    <div className="execution-bar"><FormField label="実行"><Select ariaLabel="実行を切り替える" selectedOption={{ value: run.id, label: `実行 ${task.runs.indexOf(run) + 1} · ${run.state}` }} options={task.runs.map((r, i) => ({ value: r.id, label: `実行 ${i + 1} · ${r.state}` }))} onChange={({ detail }) => setParams({ run: detail.selectedOption.value!, tab })}/></FormField><div className="current-sentence" data-testid="current-sentence">{run.id !== latestRun(task).id ? '以前の実行を表示しています。' : task.state === '入力待ち' ? task.waitingReason : ['完了', '中止'].includes(task.state) ? `オーナーが${task.state}として記録しました。` : `第 ${run.rounds.find(r => !r.joined)?.number || run.rounds.at(-1)?.number} 回。${moving.length} セルが動いています。`}</div></div>
    <Tabs activeTabId={tab} onChange={({ detail }) => setParams(p => { p.set('tab', detail.activeTabId); p.delete('cell'); return p; })} tabs={[
      { id: 'flow', label: 'フロー', content: <div className="stack"><Flow run={run} selected={params.get('cell') || undefined} onSelect={selectCell} onInsert={editable ? insert : undefined}/>{editable && <Container header={<Header variant="h2">指示を重ねる</Header>}><p>次の回から有効になります。入力待ちなら実行を再開します。</p><Textarea ariaLabel="重ねる指示" value={instruction} onChange={({ detail }) => setInstruction(detail.value)} rows={3} placeholder="追加したい条件や、次にしてほしいこと"/><div className="form-action"><Button variant="primary" disabled={!instruction.trim()} onClick={() => { mutate(t => addInstruction(t, instruction), '指示を受け付けました。次の回から有効です。'); setInstruction(''); }}>指示を送る</Button></div></Container>}</div> },
      { id: 'report', label: `報告${run.reports.length ? ` (${run.reports.length})` : ''}`, content: <div className="stack">{run.reports.length > 1 && <FormField label="報告を選ぶ"><Select ariaLabel="報告を選ぶ" selectedOption={{ value: params.get('report') || run.reports.at(-1)!.id, label: run.reports.find(r => r.id === params.get('report'))?.time || run.reports.at(-1)!.time }} options={run.reports.map((r, i) => ({ value: r.id, label: `${i + 1} · ${r.time}` }))} onChange={({ detail }) => setParams(p => { p.set('report', detail.selectedOption.value!); return p; })}/></FormField>}<ReportView task={task} run={run} selectedReport={params.get('report')}/></div> },
      { id: 'artifacts', label: `成果物 (${task.artifacts.length})`, content: <Artifacts items={task.artifacts}/> },
    ]}/>
    <Modal visible={!!operation} onDismiss={() => setOperation('')} header={modalTitle[operation]} closeAriaLabel="操作を閉じる" size="medium" footer={<div className="button-row align-right"><Button variant="link" onClick={() => setOperation('')}>戻る</Button><Button variant="primary" disabled={['rewrite', 'insert'].includes(operation) && !input.trim()} onClick={execute}>{confirmText}</Button></div>}>
      <div className="stack">{['interrupt', 'complete', 'cancel'].includes(operation) && <><p>{operation === 'interrupt' ? '動いているセルを止め、中断したことを判定器へ渡します。' : operation === 'cancel' ? 'タスクを中止として記録します。動いている実行は止まります。' : 'タスクを完了として記録します。動いているセルがあれば終了させます。'}</p><h3>止まるセル（{moving.length}）</h3>{moving.length ? moving.map(c => <p key={c.id}>{c.type} · {c.executor} · {elapsedText(c.elapsed)}</p>) : <p>動いているセルはありません。</p>}</>}
      {operation === 'interrupt' && <FormField label="判定器に渡す理由か次の指示（任意）"><Textarea ariaLabel="中断の理由" value={input} onChange={({ detail }) => setInput(detail.value)}/></FormField>}
      {operation === 'rewrite' && <><FormField label="書き換える指示"><Textarea ariaLabel="書き換える指示" rows={7} value={input} onChange={({ detail }) => setInput(detail.value)}/></FormField><RadioGroup ariaLabel="書き換えの適用方法" value={mode} onChange={({ detail }) => setMode(detail.value)} items={[{ value: 'future', label: '以後の回から有効', description: 'いまの作業は続けます。書き換えた指示のセルを加え、次の回の判定器から使います。' }, { value: 'restart', label: '最初からやり直す', description: '現在の実行を止め、新しい実行を同じタスクに積みます。以前の実行と報告は中断として残ります。' }]}/></>}
      {operation === 'insert' && <><p>次の回に分岐として置き、その回の終わりで他の分岐と合流します。</p><FormField label="type"><Select ariaLabel="挿し込む type" selectedOption={{ value: type, label: type }} options={['break-down', 'implement', 'review', 'summarize', 'verify.test', 'verify.lint'].map(t => ({ label: t, value: t }))} onChange={({ detail }) => setType(detail.selectedOption.value!)}/></FormField><FormField label="セルへの入力"><Textarea ariaLabel="挿し込むセルへの入力" value={input} onChange={({ detail }) => setInput(detail.value)}/></FormField></>}
    </div></Modal>
  </div>;
}
