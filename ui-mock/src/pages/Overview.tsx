import { Link } from 'react-router';
import { Container, Header, Status } from '../ui';
import { activeCells, currentReport, elapsedText, executorCells, pendingTasks } from '../mock/model';
import { useStore } from '../store';

export function Overview() {
  const { state } = useStore(), waiting = pendingTasks(state), running = state.tasks.filter(t => t.state === '進行中');
  return <div className="stack overview"><Header variant="h1" description="自分の番を確認して、いまの仕事を見渡す。">概観</Header>
    <Container header={<Header variant="h2" counter={`(${waiting.length})`}>自分の番</Header>}>{waiting.length ? <div className="attention-grid">{waiting.map(t => <Link className="attention-card" key={t.id} to={`/inbox/${t.id}`}><div><Status value="入力待ち"/><span className="tag">{currentReport(t)?.questions.length ? `${currentReport(t).questions.length} 問` : t.id === 'core' ? '規則で停止' : '結果の報告'}</span></div><strong>{t.title}</strong><p>{t.waitingReason}</p><span className="open-label">報告を開く →</span></Link>)}</div> : <p>入力待ちはありません。進行中の仕事は下で確認できます。</p>}</Container>
    <Container header={<Header variant="h2" counter={`(${running.length})`}>動いているタスク</Header>}>{running.length ? <div className="active-task-list">{running.map(t => <div className="active-task" key={t.id}><div className="section-heading"><Link to={`/tasks/${t.id}`}>{t.title}</Link>{t.attention && <span className="attention-tag">{t.attention}</span>}</div>{activeCells(t).map(c => <Link className="work-line" key={c.id} to={`/tasks/${t.id}?tab=flow&cell=${c.id}`}><span><Status value="動いている"/> <strong>{c.type}</strong> · {c.executor}</span><span>{c.output.replace(/#+\s|\*\*/g, '').trim().split('\n').filter(Boolean).at(-1)}</span><span className="muted">{elapsedText(c.elapsed)}{c.elapsed >= 1800 && ' · 長時間'}</span></Link>)}{!activeCells(t).length && <p>次の回を待っています。</p>}</div>)}</div> : <p>進行中のタスクはありません。</p>}</Container>
    <Container header={<Header variant="h2">実行器の見渡し</Header>}><div className="executor-overview">{state.executors.map(e => { const cells = executorCells(state, e.id); return <Link key={e.id} to={`/executors/${e.id}`} className={`executor-summary ${e.life !== '生きている' ? 'unavailable' : ''}`}><strong>{e.id}</strong><Status value={e.life}/><span>{cells.length} セル{!cells.length && ' · 担当なし'}</span><p>{cells.map(({ cell }) => cell.type).join(' / ') || e.name}</p></Link>; })}</div></Container>
  </div>;
}
