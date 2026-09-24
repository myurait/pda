import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button, Container, FormField, Header, Input, Select, Textarea } from '../ui';
import { Document } from '../components/Document';
import { createTask } from '../mock/actions';
import { supported } from '../mock/model';
import { useStore } from '../store';
export function NewTask() {
  const { state, update } = useStore(), navigate = useNavigate();
  const [input, setInput] = useState(''), [workdir, setWorkdir] = useState(''), [reporter, setReporter] = useState(localStorage.getItem('pda-last-reporter') || 'claude-personal'), [preview, showPreview] = useState(false);
  return <div className="stack new-task"><Header variant="h1">新しいタスク</Header><Container><div className="stack"><FormField label="指示" description="長い文章、Markdown、コードをそのまま貼り付けられます。"><Textarea ariaLabel="新しいタスクの指示" value={input} rows={13} onChange={({ detail }) => setInput(detail.value)}/></FormField><Button onClick={() => showPreview(!preview)}>{preview ? '編集に戻る' : '見た目を確認'}</Button>{preview && <div className="instruction-preview" data-testid="instruction-preview"><Document body={input || '指示を書くと、ここに見た目を表示します。'}/></div>}<FormField label="作業ディレクトリ（任意）"><Input ariaLabel="作業ディレクトリ" value={workdir} onChange={({ detail }) => setWorkdir(detail.value)} placeholder="/work/project"/></FormField><FormField label="報告を書く実行器"><Select ariaLabel="報告を書く実行器" selectedOption={{ label: reporter, value: reporter }} options={state.executors.filter(e => supported(e, 'report')).map(e => ({ label: e.id, value: e.id }))} onChange={({ detail }) => setReporter(detail.selectedOption.value!)}/></FormField><div className="form-action"><Button variant="primary" disabled={!input.trim()} onClick={() => { const task = createTask(input.trim(), workdir.trim(), reporter); update(s => { s.tasks.unshift(task); }, '新しいタスクを受け付けました。'); localStorage.setItem('pda-last-reporter', reporter); navigate(`/tasks/${task.id}`); }}>タスクを出す</Button></div></div></Container></div>;
}
