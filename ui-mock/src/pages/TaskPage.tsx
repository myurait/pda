import { useCallback, useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { Alert, Button, Container, ExpandableSection, FormField, Header, Modal, Select, Status, Tabs, Textarea } from '../ui';
import { activeCells, elapsedText, isTaskInterrupted, taskElapsedSeconds, waitingSeconds, type Task } from '../mock/model';
import { addInstruction, interruptTask, recordTask } from '../mock/actions';
import { useStore } from '../store';
import { Artifacts } from '../components/Artifacts';
import { Flow } from '../components/Flow';
import { ReportView } from '../components/Report';
export function TaskPage() {
  const { taskId } = useParams(), { state, update } = useStore(), [params, setParams] = useSearchParams();
  const [now] = useState(Date.now);
  const task = state.tasks.find(t => t.id === taskId);
  const [operation, setOperation] = useState(''), [input, setInput] = useState(''), [instruction, setInstruction] = useState('');
  const selectCell = useCallback((id: string) => setParams({ tab: 'flow', cell: id }), [setParams]);
  if (!task) return <Alert type="warning">タスクが見つかりません。</Alert>;
  const flow = task.flow, tab = params.get('tab') || 'report';
  const editable = !['完了', '中止'].includes(task.state), moving = activeCells(task);
  const index = flow.reports.findIndex(r => r.id === params.get('report')), selectedIndex = index < 0 ? flow.reports.length - 1 : index, selectedReport = flow.reports[selectedIndex];
  const chooseReport = (i: number) => setParams({ tab: 'report', report: flow.reports[i].id });
  const mutate = (fn: (t: Task) => void, message: string) => update(s => fn(s.tasks.find(t => t.id === task.id)!), message);
  const execute = () => {
    if (operation === 'interrupt') mutate(t => interruptTask(t, input), '動作中のセルを中断しました。中断理由を判定器へ渡しました。');
    if (operation === 'complete') mutate(t => recordTask(t, '完了'), '完了として記録しました。');
    if (operation === 'cancel') mutate(t => recordTask(t, '中止'), '中止として記録しました。');
    setOperation(''); setInput('');
  };
  const titles: Record<string, string> = { interrupt: '実行を中断する', complete: '完了として記録', cancel: '中止として記録' };
  return <div className="stack task-page" data-testid="task-page">
    <header className="task-heading"><div className="task-heading-main"><Header variant="h1">{task.title}</Header><div className="task-status"><Status value={task.state} warning={isTaskInterrupted(task)}/></div></div>{editable && <div className="button-row task-actions"><Button onClick={() => setOperation('interrupt')} disabled={!moving.length}>中断</Button><Button nativeButtonAttributes={{ title: 'タスクを完了として記録' }} onClick={() => setOperation('complete')}>完了</Button><Button nativeButtonAttributes={{ title: 'タスクを中止として記録' }} onClick={() => setOperation('cancel')}>中止</Button></div>}</header>
    <ExpandableSection headerText="指示の全文"><p className="prompt-text">{task.directive}</p></ExpandableSection>
    <dl className="task-meta"><div><dt>作業ディレクトリ</dt><dd>{task.workdir || '指定なし'}</dd></div>{task.branch && <div><dt>作業ブランチ</dt><dd>{task.branch}</dd></div>}<div><dt title="タスクが入力待ちになってからの時間">待機時間</dt><dd>{task.state === '入力待ち' ? elapsedText(waitingSeconds(task, now)) : '—'}</dd></div><div><dt title="最終指示からページを開いた時点、または入力待ちになるまでの時間">実行時間</dt><dd>{elapsedText(taskElapsedSeconds(task, now))}</dd></div></dl>
    <Tabs activeTabId={tab} onChange={({ detail }) => setParams({ tab: detail.activeTabId })} tabs={[
      { id: 'report', label: `報告${flow.reports.length ? ` (${flow.reports.length})` : ''}`, content: <div className="stack">{flow.reports.length > 1 && <div className="report-navigation"><Button iconName="angle-left" disabled={selectedIndex === 0} onClick={() => chooseReport(selectedIndex - 1)}>戻る</Button><div className="report-selector"><Select ariaLabel="報告を選ぶ" selectedOption={{ value: selectedReport.id, label: `${selectedReport.title} · ${selectedReport.time}` }} options={flow.reports.map((r, i) => ({ value: r.id, label: `${i + 1} · ${r.title} · ${r.time}` }))} onChange={({ detail }) => setParams({ tab: 'report', report: detail.selectedOption.value! })}/></div><Button iconName="angle-right" iconAlign="right" disabled={selectedIndex === flow.reports.length - 1} onClick={() => chooseReport(selectedIndex + 1)}>進む</Button></div>}<ReportView task={task} selectedReport={selectedReport?.id}/></div> },
      { id: 'flow', label: 'フロー', content: <div className="stack"><Flow flow={flow} selected={params.get('cell') || undefined} focusKey={params.get('focus') || undefined} onSelect={selectCell}/>{editable && <Container header={<Header variant="h2">指示を重ねる</Header>}><Textarea ariaLabel="重ねる指示" value={instruction} onChange={({ detail }) => setInstruction(detail.value)} rows={3} placeholder="追加したい条件や、次にしてほしいこと"/><div className="form-action"><Button variant="primary" disabled={!instruction.trim()} onClick={() => { mutate(t => addInstruction(t, instruction), '指示を受け付けました。'); setInstruction(''); }}>送信</Button></div></Container>}</div> },
      { id: 'artifacts', label: `成果物 (${task.artifacts.length})`, content: <Artifacts items={task.artifacts} workdir={task.workdir}/> },
    ]}/>
    <Modal visible={!!operation} onDismiss={() => setOperation('')} header={titles[operation]} closeAriaLabel="操作を閉じる" size="medium" footer={<div className="button-row align-right"><Button variant="link" onClick={() => setOperation('')}>戻る</Button><Button variant="primary" onClick={execute}>{operation === 'complete' ? '完了' : operation === 'cancel' ? '中止' : titles[operation]}</Button></div>}>
      <div className="stack"><p>{operation === 'interrupt' ? '動作中のセルを止め、中断したことを判定器へ渡します。' : operation === 'cancel' ? 'タスクを中止として記録します。動作中のセルは止まります。' : 'タスクを完了として記録します。動作中のセルがあれば終了させます。'}</p><h3>止まるセル（{moving.length}）</h3>{moving.length ? moving.map(c => <p key={c.id}>{c.type} · {c.executor} · {elapsedText(c.elapsed)}</p>) : <p>動作中のセルはありません。</p>}
      {operation === 'interrupt' && <FormField label="判定器に渡す理由か次の指示（任意）"><Textarea ariaLabel="中断の理由" value={input} onChange={({ detail }) => setInput(detail.value)}/></FormField>}
      </div>
    </Modal>
  </div>;
}
