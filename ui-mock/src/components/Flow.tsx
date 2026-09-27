import { useEffect, useMemo, useRef, useState } from 'react';
import { Background, BaseEdge, Handle, MarkerType, MiniMap, Position, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type EdgeProps, type Node, type NodeProps } from '@xyflow/react';
import ELK from 'elkjs/lib/elk.bundled.js';
import type { ElkExtendedEdge } from 'elkjs';
import { Button, Mark, Modal, Status, useMobile } from '../ui';
import { elapsedText, roundCells, type Cell, type TaskFlow } from '../mock/model';

type Data = { kind: string; label: string; cell?: Cell; detail?: string; mobile: boolean; round: number; branch?: string; expand?: () => void; onSelect: (id: string) => void };
type FlowNode = Node<Data>;
const elk = new ELK();
function NodeBox({ data, id, selected }: NodeProps<FlowNode>) {
  const c = data.cell;
  return <div data-testid={`node-${id}`} data-kind={data.kind} data-branch={data.branch} data-state={c?.state || ''} className={`flow-node kind-${data.kind} ${c?.state === '動作中' ? 'moving' : ''} ${selected ? 'selected' : ''}`}>
    <Handle type="target" position={data.mobile ? Position.Top : Position.Left}/>
    <button className="node-button nodrag" onClick={() => data.expand ? data.expand() : data.onSelect(id)} aria-label={`${data.label}${c ? ` ${c.executor} ${c.state}` : ''}`}>
      <div className="node-heading"><Mark kind={data.kind}/><strong>{data.label}</strong></div>
      {c?.kind === 'owner' ? <><span className="owner-node-input">{c.input}</span><span className="node-note">{c.badge || 'ユーザーの指示'}</span></> : c ? <><span className="node-executor">{c.executor}</span><span className="node-status"><Status value={c.state}/><span>{elapsedText(c.elapsed)}</span></span>{(c.badge || c.decision) && <span className="node-note">{c.badge || c.decision}</span>}</> : <span className="node-note">{data.detail}</span>}
    </button>
    <Handle type="source" position={data.mobile ? Position.Bottom : Position.Right}/>
  </div>;
}
const nodeTypes = { cell: NodeBox };
function RoutedEdge({ id, data, markerEnd, style, label }: EdgeProps) {
  return <BaseEdge id={id} path={String(data?.path || '')} markerEnd={markerEnd} style={style} label={label} labelX={Number(data?.labelX)} labelY={Number(data?.labelY)} labelStyle={{ fontSize: 14 }} labelBgPadding={[5, 3]} labelBgStyle={{ fill: '#f7f8fa' }}/>;
}
const edgeTypes = { routed: RoutedEdge };

function Canvas({ flow, selected, onSelect, focusKey, compact = false }: { flow: TaskFlow; selected?: string; focusKey?: string; onSelect: (id: string) => void; compact?: boolean }) {
  const mobile = useMobile(), section = useRef<HTMLDivElement>(null);
  const initialCollapsed = () => flow.rounds.length > 4 ? flow.rounds.filter(r => r.joined && !roundCells(r).some(c => c.state === '動作中')).map(r => r.id) : [];
  const [collapsed, setCollapsed] = useState<string[]>(initialCollapsed), [legend, showLegend] = useState(false);
  const [nodes, setNodes] = useState<FlowNode[]>([]), [edges, setEdges] = useState<Edge[]>([]), [ready, setReady] = useState(false);
  const api = useReactFlow<FlowNode>();
  const graph = useMemo(() => {
    const list: FlowNode[] = [], edges: Edge[] = [];
    let previous = '';
    const add = (id: string, data: Omit<Data, 'mobile' | 'onSelect'>) => { list.push({ id, type: 'cell', data: { ...data, mobile, onSelect }, position: { x: 0, y: 0 }, selected: id === selected, width: data.kind === 'join' ? 130 : 228, height: data.kind === 'join' || data.kind === 'wait' ? 86 : 140 }); };
    const edge = (from: string, to: string, label?: string, dashed = false) => { if (from) edges.push({ id: `${from}>${to}`, source: from, target: to, type: 'smoothstep', label, style: { stroke: '#687585', strokeWidth: 1.5, strokeDasharray: dashed ? '5 4' : undefined }, markerEnd: { type: MarkerType.ArrowClosed, color: '#687585' }, labelStyle: { fontSize: 14 }, labelBgPadding: [5, 3], labelBgStyle: { fill: '#f7f8fa' } }); };
    for (const r of flow.rounds) {
      if (collapsed.includes(r.id) && !roundCells(r).some(c => c.id === selected)) {
        add(r.id, { kind: 'collapsed', label: `第 ${r.number} 回・終了`, detail: `${roundCells(r).length} セル / 押して展開`, round: r.number, expand: () => setCollapsed(xs => xs.filter(x => x !== r.id)) }); edge(previous, r.id); previous = r.id; continue;
      }
      for (const c of r.owners) { add(c.id, { kind: c.kind, label: c.id === flow.rounds[0]?.owners[0]?.id ? '初期の指示' : c.type, cell: c, round: r.number }); edge(previous, c.id); previous = c.id; }
      add(r.judge.id, { kind: 'judge', label: `第 ${r.number} 回 · judge`, cell: r.judge, round: r.number }); edge(previous, r.judge.id);
      const joinId = `${r.id}-join`; if (r.joined) add(joinId, { kind: 'join', label: '合流', detail: r.joined ? '分岐の出力が揃いました' : `${r.branches.length} 本の分岐を待つ`, round: r.number });
      for (const b of r.branches) {
        let prev = r.judge.id;
        const hasSuccessor = new Set<string>();
        b.cells.forEach((c, i) => { add(c.id, { kind: c.kind, label: c.type, cell: c, round: r.number, branch: b.id }); const from = c.after && flow.rounds.flatMap(roundCells).some(x => x.id === c.after) ? c.after : prev; edge(from, c.id, i === 0 ? b.label : c.after ? 'オーナーの操作' : undefined); hasSuccessor.add(from); prev = c.id; });
        if (r.joined) b.cells.filter(c => !hasSuccessor.has(c.id) && c.id !== prev).forEach(c => edge(c.id, joinId));
        if (b.waiting) { add(b.waiting.id, { kind: 'wait', label: '返答待ち', detail: '分岐の終端', round: r.number, branch: b.id }); edge(prev, b.waiting.id); prev = b.waiting.id; }
        if (r.joined) edge(prev, joinId, undefined, !!b.waiting);
      }
      if (r.joined && !r.branches.length) edge(r.judge.id, joinId);
      previous = r.joined ? joinId : r.judge.id;
      if (r.report) { add(r.report.id, { kind: 'report', label: 'report', cell: r.report, round: r.number }); edge(previous, r.report.id); previous = r.report.id; }
    }
    return { nodes: list, edges };
  }, [flow, collapsed, mobile, selected, onSelect, compact]);
  useEffect(() => {
    let alive = true;
    setReady(false);
    elk.layout({ id: 'root', layoutOptions: { 'elk.algorithm': 'layered', 'elk.direction': mobile ? 'DOWN' : 'RIGHT', 'elk.edgeRouting': 'ORTHOGONAL', 'elk.spacing.nodeNode': '44', 'elk.layered.spacing.nodeNodeBetweenLayers': '72', 'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES', 'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF' }, children: graph.nodes.map(n => ({ id: n.id, width: n.width, height: n.height, layoutOptions: { 'elk.portConstraints': 'FIXED_POS' }, ports: [{ id: `${n.id}-in`, x: mobile ? n.width! / 2 : 0, y: mobile ? 0 : n.height! / 2, width: 0, height: 0, properties: { 'port.side': mobile ? 'NORTH' : 'WEST' } }, { id: `${n.id}-out`, x: mobile ? n.width! / 2 : n.width!, y: mobile ? n.height! : n.height! / 2, width: 0, height: 0, properties: { 'port.side': mobile ? 'SOUTH' : 'EAST' } }] })), edges: graph.edges.map(e => ({ id: e.id, sources: [`${e.source}-out`], targets: [`${e.target}-in`] })) }).then(layout => {
      if (!alive) return;
      setNodes(graph.nodes.map(n => { const p = layout.children!.find(x => x.id === n.id)!; return { ...n, position: { x: p.x || 0, y: p.y || 0 } }; }));
      setEdges(graph.edges.map(e => { const section = (layout.edges!.find(x => x.id === e.id)! as ElkExtendedEdge).sections![0]; const points = [section.startPoint, ...(section.bendPoints || []), section.endPoint]; const segments = points.slice(1).map((p, i) => ({ x: (p.x + points[i].x) / 2, y: (p.y + points[i].y) / 2, length: Math.abs(p.x - points[i].x) + Math.abs(p.y - points[i].y) })); const label = segments.sort((a, b) => b.length - a.length)[0]; return { ...e, type: 'routed', data: { path: points.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' '), labelX: label.x, labelY: label.y } }; })); setReady(true);
    }); return () => { alive = false; };
  }, [graph]);
  useEffect(() => { if (!ready) return; const frame = requestAnimationFrame(() => { const current = selected ? nodes.filter(n => n.id === selected) : nodes.filter(n => n.data.cell?.state === '動作中'); api.fitView({ nodes: !compact && current.length && (selected || mobile || flow.rounds.length > 4) ? mobile ? current.slice(0, 1) : current : undefined, padding: 0.14, maxZoom: 1, minZoom: mobile && !compact ? 0.65 : 0.12 }); }); return () => cancelAnimationFrame(frame); }, [ready]);
  useEffect(() => { if (!ready || !selected || compact) return; section.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }); api.fitView({ nodes: nodes.filter(n => n.id === selected), maxZoom: 1, padding: 0.2, duration: 200 }); }, [ready, focusKey, selected, compact]);
  const current = () => { const running = nodes.filter(n => n.data.cell?.state === '動作中'); const targets = running.length ? running : nodes.filter(n => n.data.round === flow.rounds.at(-1)?.number); api.fitView({ nodes: mobile ? targets.slice(0, 1) : targets, maxZoom: 1, minZoom: 0.7, padding: 0.2, duration: 250 }); };
  return <div ref={section} className={compact ? 'flow-section compact' : 'flow-section'}>
    {!compact && <div className="flow-toolbar"><div className="button-row"><Button ariaLabel="拡大" iconName="zoom-in" onClick={() => api.zoomIn()}/><Button ariaLabel="縮小" iconName="zoom-out" onClick={() => api.zoomOut()}/><Button onClick={() => api.fitView({ padding: 0.1, minZoom: 0.02, maxZoom: 1, duration: 250 })}>全体表示</Button><Button onClick={current}>動作中のセルへ</Button><Button onClick={() => showLegend(true)}>凡例</Button></div>
      <div className="button-row">{flow.rounds.length > 1 && <Button onClick={() => setCollapsed(collapsed.length ? [] : flow.rounds.filter(r => r.joined).map(r => r.id))}>{collapsed.length ? '終わった回をすべて開く' : '終わった回を畳む'}</Button>}</div></div>}
    <div className="flow-canvas" data-testid="flow-canvas" data-ready={ready} data-direction={mobile ? 'DOWN' : 'RIGHT'}>
      <ReactFlow<FlowNode> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} nodesDraggable={false} nodesConnectable={false} elementsSelectable={true} minZoom={0.02} maxZoom={1.5} proOptions={{ hideAttribution: true }} ariaLabelConfig={{ 'minimap.ariaLabel': 'フローの縮小図' }}>
        <Background color="#d7dce2" gap={24}/>{!mobile && !compact && <MiniMap pannable zoomable nodeColor={n => (n.data.cell as Cell | undefined)?.state === '動作中' ? '#0972d3' : '#b7bfc8'}/>}<div className="canvas-caption">{flow.rounds.length} 回 · {flow.rounds.flatMap(roundCells).length} セル{!compact && ' / 図の中をドラッグして移動'}</div>
      </ReactFlow>
    </div>
    <Modal visible={legend} onDismiss={() => showLegend(false)} header="フロー図の凡例" closeAriaLabel="凡例を閉じる" footer={<Button onClick={() => showLegend(false)}>閉じる</Button>}><div className="legend-grid">{[['owner', 'オーナー：指示・返答・書き換え'], ['judge', '判定器：次の仕事・分岐 A'], ['work', '作業：実装・検証など'], ['observe', 'オブザーバー：分岐 B・指示だけ'], ['report', '報告：結果と問い'], ['wait', '返答待ち：セルではなく分岐の終端']].map(([kind, label]) => <div key={kind} className={`legend-item kind-${kind}`}><Mark kind={kind}/>{label}</div>)}</div><p>線は入力の受け渡し、分かれた線は並行作業、集まった線は合流です。</p><div className="button-row">{['待機', '動作中', '終わった', '失敗した', '中断した', '返答待ち'].map(s => <Status value={s} key={s}/>)}</div></Modal>
  </div>;
}
export function Flow(props: Parameters<typeof Canvas>[0]) { return <ReactFlowProvider><Canvas  {...props}/></ReactFlowProvider>; }
