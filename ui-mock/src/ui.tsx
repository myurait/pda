import { useEffect, useState } from 'react';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
export { default as AppLayout } from '@cloudscape-design/components/app-layout';
export { default as TopNavigation } from '@cloudscape-design/components/top-navigation';
export { default as SideNavigation } from '@cloudscape-design/components/side-navigation';
export { default as BreadcrumbGroup } from '@cloudscape-design/components/breadcrumb-group';
export { default as SplitPanel } from '@cloudscape-design/components/split-panel';
export { default as Button } from '@cloudscape-design/components/button';
export { default as Container } from '@cloudscape-design/components/container';
export { default as Header } from '@cloudscape-design/components/header';
export { default as Flashbar } from '@cloudscape-design/components/flashbar';
export { default as Modal } from '@cloudscape-design/components/modal';
export { default as Table } from '@cloudscape-design/components/table';
export { default as Tabs } from '@cloudscape-design/components/tabs';
export { default as Input } from '@cloudscape-design/components/input';
export { default as Textarea } from '@cloudscape-design/components/textarea';
export { default as Select } from '@cloudscape-design/components/select';
export { default as FormField } from '@cloudscape-design/components/form-field';
export { default as SpaceBetween } from '@cloudscape-design/components/space-between';
export { default as ExpandableSection } from '@cloudscape-design/components/expandable-section';
export { default as Checkbox } from '@cloudscape-design/components/checkbox';
export { default as RadioGroup } from '@cloudscape-design/components/radio-group';
export { default as Pagination } from '@cloudscape-design/components/pagination';
export { default as Alert } from '@cloudscape-design/components/alert';
export { default as Spinner } from '@cloudscape-design/components/spinner';
export { default as Badge } from '@cloudscape-design/components/badge';
export { default as Icon } from '@cloudscape-design/components/icon';

const statusTypes = { '動作中': 'in-progress', '進行中': 'in-progress', '終わった': 'success', '完了': 'success', '生きている': 'success', '失敗した': 'error', '止まっている': 'error', '入力待ち': 'pending', '返答待ち': 'pending', '待機': 'pending', '不明': 'pending', '中断した': 'warning', '中止': 'stopped' } as const;
export function Status({ value, warning = false }: { value: string; warning?: boolean }) { const type = warning ? 'warning' : statusTypes[value as keyof typeof statusTypes] || 'info'; return <span className="status" data-status={value} data-type={type}><StatusIndicator type={type}>{value}</StatusIndicator></span>; }
export function useMobile() {
  const [mobile, set] = useState(() => matchMedia('(max-width: 767px)').matches);
  useEffect(() => { const m = matchMedia('(max-width: 767px)'); const update = () => set(m.matches); m.addEventListener('change', update); return () => m.removeEventListener('change', update); }, []);
  return mobile;
}
export function Mark({ kind }: { kind: string }) {
  const paths: Record<string, string> = { owner: 'M8 6a4 4 0 1 0 8 0a4 4 0 1 0-8 0M4 22v-4c0-7 16-7 16 0v4', judge: 'M12 2L22 12L12 22L2 12Z', work: 'M4 4h16v16H4ZM8 8h8M8 12h8M8 16h5', observe: 'M1 12Q12-4 23 12Q12 28 1 12ZM8 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0', report: 'M5 2h10l5 5v15H5ZM15 2v6h5M8 12h9M8 16h9', wait: 'M7 4v16M17 4v16', join: 'M2 6L12 12L22 6M12 12v10', collapsed: 'M3 3h18v18H3ZM7 8h10M7 12h10M7 16h10' };
  return <svg className="kind-mark" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d={paths[kind] || paths.work}/></svg>;
}
