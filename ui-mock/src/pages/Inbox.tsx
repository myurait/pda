import { Navigate, useParams } from 'react-router';
import { Container, Header } from '../ui';
import { pendingTasks } from '../mock/model';
import { useStore } from '../store';
import { PendingCards } from '../components/PendingCards';
export function Inbox() {
  const { state } = useStore(), { taskId } = useParams(), pending = pendingTasks(state);
  if (taskId) return <Navigate to={`/tasks/${taskId}?tab=report`} replace/>;
  return <div className="stack"><Header variant="h1" counter={`(${pending.length})`}>入力待ち</Header>{pending.length ? <PendingCards tasks={pending}/> : <Container>入力待ちはありません。</Container>}</div>;
}
