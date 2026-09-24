import { Link, useNavigate, useParams } from 'react-router';
import { Button, Container, Header, Status, useMobile } from '../ui';
import { pendingTasks } from '../mock/model';
import { recordTask } from '../mock/actions';
import { useStore } from '../store';
import { ReportView } from '../components/Report';

export function Inbox() {
  const { state, update } = useStore(), { taskId } = useParams(), navigate = useNavigate(), mobile = useMobile();
  const pending = pendingTasks(state), task = state.tasks.find(t => t.id === taskId) || (!mobile ? pending[0] : undefined);
  const next = () => { const item = pending.find(t => t.id !== task?.id); navigate(item ? `/inbox/${item.id}` : '/inbox'); };
  return <div className="stack"><Header variant="h1" counter={`(${pending.length})`}>入力待ち</Header>{!pending.length && !taskId && <Container>入力待ちはありません。進行中のタスクを概観から確認できます。</Container>}
    <div className={`inbox-layout ${taskId ? 'has-detail' : ''}`}>
      {(!mobile || !taskId) && <aside className="inbox-list" aria-label="入力待ちの報告">{pending.map(t => <Link key={t.id} className={`inbox-item ${task?.id === t.id ? 'selected' : ''}`} to={`/inbox/${t.id}`}><Status value="入力待ち"/><strong>{t.title}</strong><span>{t.waitingReason}</span></Link>)}</aside>}
      {task && <div className="stack inbox-detail">{mobile && <Button href="#/inbox">入力待ちの一覧に戻る</Button>}<div className="section-heading"><Header variant="h2">{task.title}</Header><Status value={task.state}/></div><ReportView key={task.id} task={task} context next={next}/>{task.state === '入力待ち' && <div className="button-row"><Button href={`#/tasks/${task.id}?tab=flow`}>指示を重ねて続ける</Button><Button onClick={() => update(s => recordTask(s.tasks.find(t => t.id === task.id)!, '完了'), '完了として記録しました。')}>完了として記録</Button></div>}</div>}
    </div>
  </div>;
}
