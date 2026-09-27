import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router';
import { AppLayout, TopNavigation, SideNavigation, BreadcrumbGroup, Button, Container, ExpandableSection, Flashbar, FormField, Header, Select, Spinner, Alert, useMobile } from './ui';
import { advance, sceneState } from './mock/actions';
import { scenarioNames } from './mock/content';
import { pendingTasks, flowCells, type Scene } from './mock/model';
import { seed } from './mock/seed';
import { useStore } from './store';
import { CellDetails } from './components/CellDetails';
import { Overview } from './pages/Overview';
import { Tasks } from './pages/Tasks';
import { TaskPage } from './pages/TaskPage';
import { NewTask } from './pages/NewTask';
import { Inbox } from './pages/Inbox';
import { Executors } from './pages/Executors';
import { StickyPanel } from './components/StickyPanel';
import { Skills } from './pages/Skills';
import { RoleEditor, Roles } from './pages/Roles';

export function App() {
  const { state, replace, update, notice, notify } = useStore(), mobile = useMobile(), location = useLocation(), navigate = useNavigate(), [params, setParams] = useSearchParams();
  const [nav, setNav] = useState(!mobile);
  useEffect(() => setNav(!mobile), [mobile]);
  const parts = location.pathname.split('/').filter(Boolean), section = parts[0] || 'overview';
  const sectionLabels: Record<string, string> = { overview: '概観', tasks: 'タスク', inbox: '入力待ち', executors: '実行器', new: '新しいタスク', roles: 'role設定', skills: 'skill登録' };
  const task = state.tasks.find(t => t.id === (section === 'executors' ? params.get('task') : parts[1]));
  const flow = task?.flow;
  const cell = flow && flowCells(flow).find(c => c.id === params.get('cell'));
  const waiting = flow?.rounds.flatMap(r => r.branches).map(b => b.waiting).find(w => w?.id === params.get('cell'));
  const closePanel = () => setParams(p => { p.delete('cell'); p.delete('task'); p.delete('role'); p.delete('focus'); return p; });
  const role = section === 'roles' ? state.roles.find(r => r.id === params.get('role')) : undefined;
  const panelOpen = !!(params.get('cell') && task) || !!role;
  const pending = pendingTasks(state).length;
  const breadcrumbs = [{ text: 'PDA', href: '#/overview' }, { text: sectionLabels[section] || '概観', href: `#/${section}` }];
  if (parts[1]) breadcrumbs.push({ text: section === 'executors' ? parts[1] : task?.title || parts[1], href: `#/${section}/${parts[1]}` });
  const sampleControls = <div className="sample-controls"><ExpandableSection headerText="見本の操作"><div className="sample-inner"><FormField label="見本の場面"><Select ariaLabel="見本の場面" selectedOption={{ value: state.scene, label: state.scene }} options={scenarioNames.map(s => ({ value: s, label: s }))} onChange={({ detail }) => { replace(sceneState(detail.selectedOption.value as Scene)); notify('見本の場面を切り替えました。'); navigate('/overview'); }}/></FormField><div className="button-row"><Button onClick={() => { replace(seed()); notify('見本を初期に戻しました。'); navigate('/overview'); }}>初期に戻す</Button><Button onClick={() => { let message = ''; update(s => { message = advance(s, task?.id); }, ''); notify(message); }}>1 歩進める</Button><span className="muted">{state.tick} 歩 · 操作はこのブラウザの見本に反映されます</span></div></div></ExpandableSection></div>;
  const special = state.scene === '読み込み中' ? <Container><Header variant="h1">タスクを読み込んでいます</Header><Spinner size="large"/><p>最新の報告と実行器の状態を確認しています。</p></Container> : state.scene === '上流に届かない' ? <Alert type="error" header="上流に届きません" action={<Button onClick={() => { replace(seed()); notify('再読み込みしました。'); }}>再読み込み</Button>}>状態を取得できませんでした。接続を確認して、再読み込みしてください。</Alert> : state.scene === 'タスクなし' && section === 'overview' ? <Container><Header variant="h1">まだタスクがありません</Header><p>最初の指示を出すと、ここにタスクと実行器の現在の作業が並びます。</p><Button variant="primary" href="#/new">最初のタスクを出す</Button></Container> : null;
  return <><div id="topbar"><TopNavigation visualContext="none"><div className="topbar-inner"><Button iconName="menu" ariaLabel="画面一覧" onClick={() => setNav(!nav)}/><a className="product-name" href="#/overview">PDA</a><div className="topbar-actions"><Button variant="primary" href="#/new">新しいタスク</Button><a className="pending-link" href="#/inbox" aria-label={`入力待ち ${pending} 件`}><svg className="inbox-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 3h16v18H4zM4 13h5l2 3h2l2-3h5M8 7h8M8 10h8"/></svg><span>入力待ち</span><strong>{pending}</strong></a></div></div></TopNavigation></div>
    <AppLayout headerSelector="#topbar" toolsHide navigationOpen={nav} onNavigationChange={({ detail }) => setNav(detail.open)} navigationWidth={200}
      navigation={<SideNavigation activeHref={`#/${section}`} header={{ text: '仕事の指令所', href: '#/overview' }} items={[{ type: 'link', text: '概観', href: '#/overview' }, { type: 'link', text: 'タスク', href: '#/tasks' }, { type: 'link', text: '実行器', href: '#/executors' }, { type: 'link', text: 'role設定', href: '#/roles' }, { type: 'link', text: 'skill登録', href: '#/skills' }]} onFollow={() => { if (mobile) setNav(false); }}/>} breadcrumbs={<BreadcrumbGroup items={breadcrumbs} ariaLabel="現在位置"/>}
      notifications={<Flashbar items={notice ? [{ type: 'success', content: notice, id: 'notice', dismissible: true, dismissLabel: '通知を閉じる', onDismiss: () => notify('') }] : []}/>}
      ariaLabels={{ navigation: '画面一覧', navigationToggle: '画面一覧の開閉', navigationClose: '画面一覧を閉じる' }}
      content={<div className={`app-content ${panelOpen ? 'has-sticky-panel' : ''}`}>{special || <Routes><Route path="/overview" element={<Overview/>}/><Route path="/tasks" element={<Tasks/>}/><Route path="/tasks/:taskId" element={<TaskPage key={parts[1]}/>}/><Route path="/roles" element={<Roles/>}/><Route path="/skills" element={<Skills/>}/><Route path="/new" element={<NewTask/>}/><Route path="/inbox" element={<Inbox/>}/><Route path="/inbox/:taskId" element={<Inbox/>}/><Route path="/executors" element={<Executors/>}/><Route path="/executors/:executorId" element={<Executors/>}/><Route path="*" element={<Navigate to="/overview" replace/>}/></Routes>}{sampleControls}</div>}/>
    {panelOpen && <StickyPanel title={role?.name || (waiting ? 'ユーザー応答待ち' : cell?.kind === 'owner' ? `${cell.type} · オーナー` : cell ? `${cell.type} · ${cell.executor}` : 'フローの接続点')} onClose={closePanel} onTitleClick={!role && task && params.get('cell') ? () => navigate(`/tasks/${task.id}?tab=flow&cell=${params.get('cell')}&focus=${Date.now()}`) : undefined}>{role ? <RoleEditor key={role.id} config={role}/> : task && <CellDetails key={params.get('cell')} task={task} cell={cell} waiting={waiting} close={closePanel}/>}</StickyPanel>}
  </>;
}
