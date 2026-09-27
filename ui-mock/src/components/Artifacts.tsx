import { useState } from 'react';
import { Button, Container, Modal } from '../ui';
import type { Artifact } from '../mock/model';
import { Document } from './Document';
export function relativeArtifactPath(path: string, workdir: string): string {
  if (!path.startsWith('/')) return path;
  const target = path.split('/').filter(Boolean), base = workdir.split('/').filter(Boolean);
  let i = 0; while (i < base.length && base[i] === target[i]) i++;
  return [...base.slice(i).map(() => '..'), ...target.slice(i)].join('/');
}
const fileName = (a: Artifact) => a.kind === 'file' ? a.path.split('/').at(-1)! : a.kind === 'external' ? a.path : a.name;
export function Artifacts({ items, compact = false, workdir = '' }: { items: Artifact[]; compact?: boolean; workdir?: string }) {
  const [opened, set] = useState<Artifact | null>(null);
  const body = <div className="artifact-list">{items.map(a => <div className="artifact-row" key={a.id} data-testid={`artifact-${a.id}`}>
    {a.kind === 'external' ? <a href={a.path} target="_blank" rel="noreferrer">{a.path}</a> : <><a href={`#artifact-${a.id}`} onClick={e => { e.preventDefault(); set(a); }}>{fileName(a)}</a><span className="path">{a.kind === 'file' ? relativeArtifactPath(a.path, workdir) : a.path}</span></>}
  </div>)}</div>;
  return <div className="stack artifacts" data-testid="artifacts">{!items.length ? !compact && <Container>成果物はありません。</Container> : compact ? body : <Container>{body}</Container>}
    <Modal visible={!!opened} onDismiss={() => set(null)} header={opened ? fileName(opened) : ''} size="large" closeAriaLabel="成果物を閉じる" footer={<Button onClick={() => set(null)}>閉じる</Button>}>{opened && <><p className="path">{relativeArtifactPath(opened.path, workdir)}</p>{opened.mime.startsWith('image/') ? <img className="artifact-image" alt={fileName(opened)} src={`data:${opened.mime};charset=utf-8,${encodeURIComponent(opened.content)}`}/> : <Document body={opened.content}/>}</>}</Modal>
  </div>;
}
