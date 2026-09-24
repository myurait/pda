import { useState } from 'react';
import { Button, Container, Header, Modal } from '../ui';
import type { Artifact } from '../mock/model';
import { Document } from './Document';

export function Artifacts({ items, compact = false }: { items: Artifact[]; compact?: boolean }) {
  const [opened, set] = useState<Artifact | null>(null);
  const download = (a: Artifact) => { const url = URL.createObjectURL(new Blob([a.content], { type: a.mime })); const link = document.createElement('a'); link.href = url; link.download = a.kind === 'file' ? a.name : `${a.name}.txt`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
  return <div className="stack artifacts" data-testid="artifacts">
    {!items.length && <Container>成果物はありません。報告は「報告」タブから読めます。</Container>}
    {(['file', 'git', 'external'] as const).map(kind => { const group = items.filter(a => a.kind === kind); if (!group.length) return null; return <Container key={kind} header={<Header variant={compact ? 'h3' : 'h2'}>{kind === 'file' ? 'ファイル' : kind === 'git' ? 'git の所在' : '外部への出力'}</Header>}>{group.map(a => <div className="artifact-row" key={a.id} data-testid={`artifact-${a.id}`}><div><a href={`#artifact-${a.id}`} onClick={e => { e.preventDefault(); set(a); }}>{a.name}</a><p className="path">{a.path}</p>{kind === 'git' ? <p>ブランチ {a.branch} · コミット {a.commit} · {a.changedFiles} ファイル変更</p> : <p className="muted">{a.size} · 更新 {a.updated}</p>}</div><div className="button-row"><Button onClick={() => set(a)}>開く</Button><Button iconName="download" onClick={() => download(a)}>持ち出す</Button></div></div>)}</Container>; })}
    <Modal visible={!!opened} onDismiss={() => set(null)} header={opened?.name} size="large" closeAriaLabel="成果物を閉じる" footer={<Button onClick={() => set(null)}>閉じる</Button>}>{opened && <><p className="path">{opened.path}</p>{opened.mime.startsWith('image/') ? <img className="artifact-image" alt={opened.name} src={`data:${opened.mime};charset=utf-8,${encodeURIComponent(opened.content)}`}/> : <Document body={opened.content}/>}</>}</Modal>
  </div>;
}
