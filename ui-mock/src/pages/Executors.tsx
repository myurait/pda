import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { Button, Container, Header, Modal, Status } from '../ui';
import { elapsedText, executorCells, latestRun, type Cell, type Task } from '../mock/model';
import { interruptTask } from '../mock/actions';
import { useStore } from '../store';

export function handoff(task: Task, cell: Cell) {
  const run = latestRun(task);
  for (const r of run.rounds) {
    if (r.judge.id === cell.id) return { from: r.owners.at(-1)?.type || '前の回の合流', to: r.branches.map(b => b.cells[0]?.type).filter(Boolean).join('、') || '次の分岐' };
    for (const b of r.branches) { const i = b.cells.findIndex(c => c.id === cell.id); if (i >= 0) return { from: i ? `${b.cells[i - 1].type} / ${b.cells[i - 1].executor}` : `judge / ${r.judge.executor}`, to: b.cells[i + 1] ? `${b.cells[i + 1].type} / ${b.cells[i + 1].executor}` : b.waiting ? '返答待ちの終端 → 合流' : '合流 → 次の判定器または報告' }; }
    if (r.report?.id === cell.id) return { from: `第 ${r.number} 回の合流`, to: 'オーナーへ報告' };
  }
  return { from: 'オーナーの指示', to: '次の判定器' };
}
export function Executors() {
  const { state, update } = useStore(), { executorId } = useParams(), [filter, setFilter] = useState('すべて'), [stopping, setStopping] = useState('');
  const shown = state.executors.filter(e => (!executorId || e.id === executorId) && (filter === 'すべて' || filter === e.life || filter === '動いている' && executorCells(state, e.id).length));
  const stoppedCells = executorCells(state, stopping);
  return <div className="stack"><Header variant="h1" description="席ごとの担当と、いまの受け渡しを見渡す。">実行器{executorId && ` · ${executorId}`}</Header>{executorId && <Button href="#/executors">すべての実行器へ</Button>}
    <div className="filter-chips" role="group" aria-label="実行器を絞り込み">{['すべて', '生きている', '止まっている', '動いている', '不明'].map(x => <button key={x} className={x === filter ? 'active' : ''} aria-pressed={x === filter} onClick={() => setFilter(x)}>{x}</button>)}</div>
    <div className="executor-grid">{shown.map(e => { const assigned = executorCells(state, e.id); return <div key={e.id} className={`executor-block ${!assigned.length ? 'idle' : ''} ${e.life !== '生きている' ? 'unavailable' : ''}`} data-testid={`executor-${e.id}`}><Container header={<Header variant="h2" counter={`(${assigned.length} セル)`} description={`${e.name} · ${e.environment} / ${e.account}`} actions={e.life === '生きている' ? <Button onClick={() => setStopping(e.id)}>止める</Button> : <Button onClick={() => update(s => { s.executors.find(x => x.id === e.id)!.life = '生きている'; }, `${e.id} を起こしました。`)}>起こす</Button>}><Link to={`/executors/${e.id}`}>{e.id}</Link></Header>}><Status value={e.life}/><p className="muted">支える type：{e.types.join('、')}</p>{!assigned.length && <p className="muted">いま担っているセルはありません。</p>}{assigned.map(({ task, cell }) => { const route = handoff(task, cell); return <Link className="assigned-cell" key={`${task.id}-${cell.id}`} to={`/executors/${e.id}?task=${task.id}&cell=${cell.id}`} data-testid={`assigned-${cell.id}`}><div className="section-heading"><strong>{cell.type}</strong><span>{elapsedText(cell.elapsed)}</span></div><span>{task.title}</span><p>{cell.output.replace(/#+\s|\*\*/g, '').trim().split('\n').filter(Boolean).at(-1)}</p><div className="handoff"><span>受け取り元：{route.from}</span><span>渡し先：{route.to}</span></div></Link>; })}</Container></div>; })}</div>
    {!shown.length && <Container>条件に合う実行器はありません。</Container>}
    <Modal visible={!!stopping} onDismiss={() => setStopping('')} header={`${stopping} を止める`} closeAriaLabel="実行器の停止を閉じる" footer={<div className="button-row align-right"><Button onClick={() => setStopping('')}>戻る</Button><Button variant="primary" onClick={() => { update(s => { s.executors.find(e => e.id === stopping)!.life = '止まっている'; s.tasks.filter(t => executorCells(s, stopping).some(x => x.task.id === t.id)).forEach(t => interruptTask(t, `${stopping} をオーナーが停止しました。`, stopping)); }, `${stopping} を停止し、担当セルの中断を判定器へ渡しました。`); setStopping(''); }}>実行器を停止する</Button></div>}><p>担っている {stoppedCells.length} セルを中断し、それぞれの判定器へ渡します。</p>{stoppedCells.map(({ task, cell }) => <p key={cell.id}>{task.title} · {cell.type} · {elapsedText(cell.elapsed)}</p>)}</Modal>
  </div>;
}
