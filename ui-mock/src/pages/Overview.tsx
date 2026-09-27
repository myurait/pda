import { Link } from 'react-router';
import { Container, Header, Status } from '../ui';
import { activeCells, elapsedText, executorCells, pendingTasks } from '../mock/model';
import { useStore } from '../store';
import { PendingCards } from '../components/PendingCards';
import { Usage } from '../components/Usage';
export function Overview() {
  const { state } = useStore(), waiting = pendingTasks(state), running = state.tasks.filter(t => t.state === '進行中');
  return <div className="stack overview"><Header variant="h1">概観</Header>
    <Container header={<Header variant="h2" counter={`(${waiting.length})`}>自分の番</Header>}>{waiting.length ? <PendingCards tasks={waiting}/> : <p>入力待ちはありません。</p>}</Container>
    <Container header={<Header variant="h2" counter={`(${running.length})`}>動作中タスク</Header>}>{running.length ? <div className="active-task-list">{running.map(t => <div className="active-task" key={t.id}><div className="section-heading"><Link to={`/tasks/${t.id}`}>{t.title}</Link></div>{activeCells(t).map(c => <Link className="work-line" key={c.id} to={`/tasks/${t.id}?tab=flow&cell=${c.id}`}><div className="section-heading"><span><Status value="動作中"/> <strong>{c.type}</strong> · {c.executor}</span><span className="muted work-duration">{elapsedText(c.elapsed)}</span></div><span>{c.output.replace(/#+\s|\*\*/g, '').trim().split('\n').filter(Boolean).at(-1)}</span></Link>)}{!activeCells(t).length && <p>次の作業を待っています。</p>}</div>)}</div> : <p>進行中のタスクはありません。</p>}</Container>
    <Container header={<Header variant="h2">実行器の見渡し</Header>}><div className="executor-overview">{state.executors.map(e => <Link key={e.id} to={`/executors/${e.id}`} className={`executor-summary ${e.life !== '生きている' ? 'unavailable' : ''}`}><strong>{e.id}</strong><Status value={e.life}/><span>{executorCells(state, e.id).length} セル</span><Usage items={e.usage}/></Link>)}</div></Container>
  </div>;
}
