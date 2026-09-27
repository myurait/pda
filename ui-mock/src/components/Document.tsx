import { useMemo, useState, type ReactNode, Children, isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import { Button } from '../ui';
const flatten = (children: ReactNode): string => Children.toArray(children).map(child => typeof child === 'string' || typeof child === 'number' ? String(child) : isValidElement<{ children?: ReactNode }>(child) ? flatten(child.props.children) : '').join('');
const slug = (s: string) => `heading-${s.replace(/[^\p{L}\p{N}]+/gu, '-')}`;
function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, set] = useState(false);
  return <div className="code-block"><div className="code-action"><Button variant="icon" iconName={copied ? 'check' : 'copy'} ariaLabel={copied ? '複写しました' : 'コードを複写'} nativeButtonAttributes={{ title: copied ? '複写しました' : 'コードを複写' }} onClick={async () => { await navigator.clipboard.writeText(flatten(children)); set(true); }}/></div><pre>{children}</pre></div>;
}
export function Document({ body, toc = false }: { body: string; toc?: boolean }) {
  const headings = useMemo(() => [...body.matchAll(/^#{1,3}\s+(.+)$/gm)].map(m => m[1]).concat([...body.matchAll(/<h[1-3][^>]*>(.*?)<\/h[1-3]>/g)].map(m => m[1].replace(/<[^>]+>/g, ''))), [body]);
  const heading = (Tag: 'h1' | 'h2' | 'h3', children: ReactNode) => <Tag id={slug(flatten(children))}>{children}</Tag>;
  return <div className="document-wrap">
    {toc && headings.length > 1 && <nav className="document-toc" aria-label="報告の目次"><strong>この報告の目次</strong>{headings.map((h, i) => <a key={i} href={`#${slug(h)}`} onClick={e => { e.preventDefault(); document.getElementById(slug(h))?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}>{h}</a>)}</nav>}
    <article className="document"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw, rehypeSanitize]} components={{
      h1: ({ children }) => heading('h1', children), h2: ({ children }) => heading('h2', children), h3: ({ children }) => heading('h3', children),
      pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
      table: ({ children }) => <div className="document-table"><table>{children}</table></div>,
      img: ({ alt }) => <span>画像：{alt || '添付画像'}</span>,
      a: ({ children, href }) => <a href={href?.startsWith('#/') ? href : '#'} onClick={e => { if (!href?.startsWith('#/')) e.preventDefault(); }} title={href}>{children}</a>,
    }}>{body}</ReactMarkdown></article>
  </div>;
}
