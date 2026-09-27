import { useState } from 'react';
import { Link } from 'react-router';
import { Button, Checkbox, Container, FormField, Header, Input, Modal, Select, Textarea } from '../ui';
import type { RoleConfig } from '../mock/model';
import { useStore } from '../store';
export function RoleEditor({ config }: { config: RoleConfig }) {
  const { state, update } = useStore();
  const [executor, setExecutor] = useState(config.executor), [model, setModel] = useState(config.model), [prompt, setPrompt] = useState(config.prompt), [skills, setSkills] = useState(config.skills), [choosing, setChoosing] = useState(false), [selection, setSelection] = useState(config.skills);
  return <div className="stack">
    <FormField label="実行器"><Select ariaLabel={`${config.name}の実行器`} selectedOption={{ value: executor, label: executor }} options={state.executors.filter(e => e.types.some(type => ['judge', 'break-down', 'summarize'].includes(type))).map(e => ({ value: e.id, label: e.id }))} onChange={({ detail }) => setExecutor(detail.selectedOption.value!)}/></FormField>
    <FormField label="モデル"><Input ariaLabel={`${config.name}のモデル`} value={model} onChange={({ detail }) => setModel(detail.value)} placeholder="実行器の既定モデル"/></FormField>
    <FormField label="注入プロンプト"><Textarea ariaLabel={`${config.name}の注入プロンプト`} value={prompt} rows={6} onChange={({ detail }) => setPrompt(detail.value)}/></FormField>
    <FormField label="skill"><div className="stack"><div className="button-row">{skills.map(id => <span className="tag" key={id}>{state.skills.find(s => s.id === id)?.name || id}</span>)}{!skills.length && <span>指定なし</span>}</div><Button onClick={() => { setSelection(skills); setChoosing(true); }}>登録済みskillから選択</Button></div></FormField>
    <div className="form-action"><Button variant="primary" onClick={() => update(s => { const role = s.roles.find(r => r.id === config.id)!; Object.assign(role, { executor, model: model.trim(), prompt, skills }); }, `${config.name}の設定を保存しました。`)}>保存</Button></div>
    <Modal visible={choosing} onDismiss={() => setChoosing(false)} header="skillを選択" closeAriaLabel="skill選択を閉じる" footer={<div className="button-row align-right"><Button onClick={() => setChoosing(false)}>戻る</Button><Button variant="primary" onClick={() => { setSkills(selection); setChoosing(false); }}>選択を反映</Button></div>}><div className="stack">{state.skills.map(skill => <Checkbox key={skill.id} checked={selection.includes(skill.id)} onChange={({ detail }) => setSelection(ids => detail.checked ? [...ids, skill.id] : ids.filter(id => id !== skill.id))} description={`${skill.description}${skill.description ? ' · ' : ''}${skill.path}`}>{skill.name}</Checkbox>)}{!state.skills.length && <p>登録済みのskillはありません。</p>}<a href="#/skills">skill登録へ</a></div></Modal>
  </div>;
}
export function Roles() {
  const { state } = useStore();
  return <div className="stack"><Header variant="h1">role設定</Header><Container><div className="settings-list">{state.roles.map(role => <Link className="settings-list-row" key={role.id} to={`/roles?role=${role.id}`}><strong>{role.name}</strong><span>{role.executor} · {role.model || '既定モデル'}</span><span>{role.skills.map(id => state.skills.find(s => s.id === id)?.name || id).join('、') || 'skill指定なし'}</span></Link>)}</div></Container></div>;
}
