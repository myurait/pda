import { useState } from 'react';
import { Button, Container, FormField, Header, Input, Modal, Textarea } from '../ui';
import { useStore } from '../store';
export function Skills() {
  const { state, update } = useStore();
  const [editing, setEditing] = useState<string | null>(null), [name, setName] = useState(''), [path, setPath] = useState(''), [description, setDescription] = useState('');
  const open = (id = '') => { const skill = state.skills.find(s => s.id === id); setEditing(id); setName(skill?.name || ''); setPath(skill?.path || ''); setDescription(skill?.description || ''); };
  return <div className="stack"><Header variant="h1" actions={<Button onClick={() => open()}>skillを登録</Button>}>skill登録</Header><Container><div className="settings-list">{state.skills.map(skill => <button className="settings-list-row" key={skill.id} onClick={() => open(skill.id)}><strong>{skill.name}</strong><span className="path">{skill.path}</span><span>{skill.description}</span></button>)}{!state.skills.length && <p>登録済みのskillはありません。</p>}</div></Container>
    <Modal visible={editing !== null} onDismiss={() => setEditing(null)} header={editing ? 'skillを編集' : 'skillを登録'} closeAriaLabel="skill登録を閉じる" footer={<div className="button-row align-right"><Button onClick={() => setEditing(null)}>戻る</Button><Button variant="primary" disabled={!name.trim() || !path.trim()} onClick={() => { update(s => { const value = { id: editing || `skill-${Date.now().toString(36)}`, name: name.trim(), path: path.trim(), description }; const old = s.skills.find(x => x.id === editing); if (old) Object.assign(old, value); else s.skills.push(value); }, 'skillを保存しました。'); setEditing(null); }}>保存</Button></div>}><div className="stack"><FormField label="名前"><Input ariaLabel="skillの名前" value={name} onChange={({ detail }) => setName(detail.value)}/></FormField><FormField label="参照先"><Input ariaLabel="skillの参照先" value={path} placeholder="skills/example/SKILL.md" onChange={({ detail }) => setPath(detail.value)}/></FormField><FormField label="説明"><Textarea ariaLabel="skillの説明" value={description} onChange={({ detail }) => setDescription(detail.value)}/></FormField></div></Modal>
  </div>;
}
