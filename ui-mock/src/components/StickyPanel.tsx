import { useEffect, type ReactNode } from 'react';
import { Button } from '../ui';
export function StickyPanel({ title, onTitleClick, onClose, children }: { title: string; onTitleClick?: () => void; onClose: () => void; children: ReactNode }) {
  useEffect(() => { const key = (event: KeyboardEvent) => { if (event.key === 'Escape' && !document.querySelector('[role="dialog"]')) onClose(); }; document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key); }, [onClose]);
  return <aside className="sticky-panel" aria-label={title}><header className="sticky-panel-header"><h2>{onTitleClick ? <a href="#" onClick={e => { e.preventDefault(); onTitleClick(); }}>{title}</a> : title}</h2><Button variant="icon" iconName="close" ariaLabel="詳細を閉じる" onClick={onClose}/></header><div className="sticky-panel-body">{children}</div></aside>;
}
