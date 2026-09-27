import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Container, FormField, Header, Input, Pagination, Select, Status, Table, useMobile } from '../ui';
import { activeCells, elapsedText, isTaskInterrupted, taskElapsedSeconds, waitingReasonText, waitingSeconds, type Task, type TaskState } from '../mock/model';
import { useStore } from '../store';
function TaskStateDetail({ task }: { task: Task }) {
  const active = activeCells(task);
  const detail = task.state === '入力待ち' ? waitingReasonText(task) : active.length ? `${active[0].type} を ${active[0].executor}${active.length > 1 ? `、ほか ${active.length - 1} セル` : ''}` : task.state === '進行中' ? '次の作業を待っています' : '';
  return <div className="task-state-detail"><Status value={task.state} warning={isTaskInterrupted(task)}/>{detail && <span>{detail}</span>}</div>;
}
function UpdatedTime({ value }: { value: string }) { const [date, time] = value.split(' '); return <span className="task-updated"><span>{date}</span><span>{time}</span></span>; }
export function Tasks() {
  const { state } = useStore(), mobile = useMobile(), [now] = useState(Date.now);
  const [status, setStatus] = useState<TaskState | 'すべて'>('すべて'), [query, setQuery] = useState(''), [sort, setSort] = useState('updated'), [page, setPage] = useState(1);
  const filtered = useMemo(() => state.tasks.filter(t => (status === 'すべて' || t.state === status) && `${t.title} ${t.initial} ${t.id}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'elapsed' ? taskElapsedSeconds(b, now) - taskElapsedSeconds(a, now) : sort === 'title' ? a.title.localeCompare(b.title, 'ja') : b.updated.localeCompare(a.updated)), [state.tasks, status, query, sort, now]);
  const items = filtered.slice((page - 1) * 10, page * 10), count = Math.max(1, Math.ceil(filtered.length / 10));
  const pagination = <Pagination currentPageIndex={page} pagesCount={count} onChange={({ detail }) => setPage(detail.currentPageIndex)} ariaLabels={{ nextPageLabel: '次のページ', previousPageLabel: '前のページ', pageLabel: n => `${n} ページへ` }}/>;
  return <div className="stack"><Header variant="h1" counter={`(${state.tasks.length})`}>タスク</Header><div className="filter-chips" role="group" aria-label="状態で絞り込み">{(['すべて', '進行中', '入力待ち', '完了', '中止'] as const).map(s => <button className={s === status ? 'active' : ''} key={s} onClick={() => { setStatus(s); setPage(1); }} aria-pressed={s === status}>{s} ({s === 'すべて' ? state.tasks.length : state.tasks.filter(t => t.state === s).length})</button>)}</div>
    <div className="filters"><FormField label="文字で絞り込み"><Input type="search" ariaLabel="タスクを検索" value={query} onChange={({ detail }) => { setQuery(detail.value); setPage(1); }} placeholder="指示またはタスク ID"/></FormField><FormField label="並べ替え"><Select ariaLabel="並べ替え" selectedOption={{ value: sort, label: ({ updated: '最終更新が新しい順', elapsed: '実行時間が長い順', title: 'タスク名順' })[sort] }} options={[{ value: 'updated', label: '最終更新が新しい順' }, { value: 'elapsed', label: '実行時間が長い順' }, { value: 'title', label: 'タスク名順' }]} onChange={({ detail }) => { setSort(detail.selectedOption.value!); setPage(1); }}/></FormField></div>
    <p className="muted">{filtered.length} 件 · {page} / {count} ページ</p>
    {mobile ? <><div className="task-cards">{items.map(t => <Container key={t.id} header={<Header variant="h3"><Link to={`/tasks/${t.id}`}>{t.title}</Link></Header>}><TaskStateDetail task={t}/><dl className="task-list-meta"><div><dt>実行時間</dt><dd className="task-duration">{elapsedText(taskElapsedSeconds(t, now))}</dd></div><div><dt>待機時間</dt><dd className="task-duration">{t.state === '入力待ち' ? elapsedText(waitingSeconds(t, now)) : '—'}</dd></div><div><dt>最終更新</dt><dd><UpdatedTime value={t.updated}/></dd></div></dl></Container>)}</div>{!items.length && <p>該当するタスクはありません。絞り込みを変更してください。</p>}{pagination}</> : <Table items={items} columnDefinitions={[
      { id: 'title', header: 'タスク（指示の先頭）', cell: t => <Link to={`/tasks/${t.id}`}>{t.title}</Link>, minWidth: 190 },
      { id: 'state', header: '状態', cell: t => <TaskStateDetail task={t}/>, minWidth: 180 },
      { id: 'elapsed', header: '実行時間', cell: t => <span className="task-duration">{elapsedText(taskElapsedSeconds(t, now))}</span>, minWidth: 100 },
      { id: 'waiting', header: '待機時間', cell: t => <span className="task-duration">{t.state === '入力待ち' ? elapsedText(waitingSeconds(t, now)) : '—'}</span>, minWidth: 100 },
      { id: 'updated', header: '最終更新', cell: t => <UpdatedTime value={t.updated}/>, minWidth: 110 },
    ]} wrapLines pagination={pagination} empty="該当するタスクはありません。絞り込みを変更してください。"/>}
  </div>;
}
