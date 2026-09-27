import type { UsageMetric } from '../mock/model';
export function Usage({ items = [] }: { items?: UsageMetric[] }) {
  if (!items.length) return null;
  return <dl className="usage-metrics">{items.map((item, index) => <div key={index} className="usage-metric" data-alert={item.alert}><dt>{item.title}</dt><dd><span>{item.value}</span>{item.limit !== undefined && <span className="usage-limit"> / {item.limit}</span>}{item.alert && <span className="usage-alert">{item.alert}</span>}</dd></div>)}</dl>;
}
