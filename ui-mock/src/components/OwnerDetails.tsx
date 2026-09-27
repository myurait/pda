import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button, FormField, Modal, RadioGroup, Textarea } from '../ui';
import type { Cell, Task } from '../mock/model';
import { flowCells } from '../mock/model';
import { addInstruction, restartTask } from '../mock/actions';
import { useStore } from '../store';
export function OwnerDetails({ task, cell }: { task: Task; cell: Cell }) {
  const { update } = useStore(), navigate = useNavigate(), [editing, setEditing] = useState(false), [input, setInput] = useState(task.directive), [mode, setMode] = useState('future');
  const initial = flowCells(task.flow).find(c => c.kind === 'owner')?.id === cell.id;
  return <div className="stack owner-details" data-testid="cell-details"><div className="owner-kind">{initial ? '初期の指示' : cell.type === '返答' ? '報告への返答' : cell.type}</div><section><h3>指示内容</h3><p className="prompt-text">{cell.input}</p></section><dl className="details-grid"><dt>出所</dt><dd>オーナーの操作</dd><dt>適用</dt><dd>{cell.badge || (initial ? 'タスクの初期入力' : '後続の判定器への入力')}</dd></dl>
    {initial && !['完了', '中止'].includes(task.state) && <Button onClick={() => { setInput(task.directive); setEditing(true); }}>初期の指示を書き換える</Button>}
    <Modal visible={editing} onDismiss={() => setEditing(false)} header="初期の指示を書き換える" closeAriaLabel="指示の編集を閉じる" footer={<div className="button-row align-right"><Button onClick={() => setEditing(false)}>戻る</Button><Button variant="primary" disabled={!input.trim()} onClick={() => { update(s => { const t = s.tasks.find(t => t.id === task.id)!; if (mode === 'restart') restartTask(t, input.trim()); else addInstruction(t, input.trim(), true); }, '書き換えた指示を保存しました。'); setEditing(false); navigate(`/tasks/${task.id}?tab=flow`); }}>書き換えを保存</Button></div>}><div className="stack"><FormField label="書き換える指示"><Textarea ariaLabel="書き換える指示" rows={6} value={input} onChange={({ detail }) => setInput(detail.value)}/></FormField><RadioGroup ariaLabel="書き換えの適用方法" value={mode} onChange={({ detail }) => setMode(detail.value)} items={[{ value: 'future', label: '現在の作業を続ける', description: '以後の判定に書き換えた指示を使用します。' }, { value: 'restart', label: '最初からやり直す', description: '現在のセルを中断し、新しい指示から再開します。以前のフローは履歴に残ります。' }]}/></div></Modal>
  </div>;
}
