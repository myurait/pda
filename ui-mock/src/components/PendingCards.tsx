import { Link } from 'react-router';
import { useState } from 'react';
import { Status } from '../ui';
import { currentReport, elapsedText, isTaskInterrupted, waitingReasonText, waitingSeconds, type Task } from '../mock/model';
export function PendingCards({ tasks }: { tasks: Task[] }) {
  const [now] = useState(Date.now);
  return <div className="pending-cards">{tasks.map(task => <Link className="pending-card" key={task.id} to={`/tasks/${task.id}?tab=report`}>
    <div className="section-heading"><Status value="入力待ち" warning={isTaskInterrupted(task)}/><span className="muted">通知から {elapsedText(waitingSeconds(task, now))}</span></div>
    <strong>{task.title}</strong><span className="waiting-reason">{waitingReasonText(task)}</span><p>{currentReport(task)?.summary}</p>
  </Link>)}</div>;
}
