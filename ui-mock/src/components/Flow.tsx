import { useEffect, useMemo, useState } from 'react';
import { Background, Handle, MarkerType, MiniMap, Position, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node, type NodeProps } from '@xyflow/react';
import ELK from 'elkjs/lib/elk.bundled.js';
import { Button, Mark, Modal, Status, useMobile } from '../ui';
import { elapsedText, roundCells, type Cell, type Run } from '../mock/model';

type Data = { kind: string; label: string; cell?: Cell; detail?: string; mobile: boolean; round: number; branch?: string; expand?: () => void; onSelect: (id: string) => void };
type FlowNode = Node<Data>;
const elk = new ELK();
function NodeBox({ data, id, selected }: NodeProps<FlowNode>) {
  const c = data.cell;
  return <div data-testid={`node-${id}`} data-kind={data.kind} data-branch={data.branch} data-state={c?.state || ''} className={`flow-node kind-${data.kind} ${c?.state === '動いている' ? 'moving' : ''} ${selected ? 'selected' : ''}`}>
    <Handle type="target" position={data.mobile ? Position.Top : Position.Left}/>
    <button className="node-button nodrag" onClick={() => data.expand ? data.expand() : data.onSelect(id)} aria-label={`${data.label}${c ? ` ${c.executor} ${c.state}` : ''}`}>
      <div className="node-heading"><Mark kind={data.kind}/><strong>{data.label}</strong></div>
      {c ? <><span className="node-executor">{c.executor}</span><span className="node-status"><Status value={c.state}/><span>{elapsedText(c.elapsed)}</span></span>{(c.badge || c.decision) && <span className="node-note">{c.badge || c.decision}</span>}</> : <span className="node-note">{data.detail}</span>}
    </button>
    <Handle type="source" position={data.mobile ? Position.Bottom : Position.Right}/>
  </div>;
}
const nodeTypes = { cell: NodeBox };

function Canvas({ run, selected, onSelect, onInsert, compact = false }: { run: Run; selected?: string; onSelect: (id: string) => void; onInsert?: () => void; compact?: boolean }) {
  const mobile = useMobile();
  const initialCollapsed = () => run.rounds.length > 4 ? run.rounds.filter(r => r.joined && !roundCells(r).some(c => c.state === '動いている')).map(r => r.id) : [];
  const [collapsed, setCollapsed] = useState<string[]>(initialCollapsed), [legend, showLegend] = useState(false);
  const [nodes, setNodes] = useState<FlowNode[]>([]), [ready, setReady] = useState(false);
  const api = useReactFlow<FlowNode>();
  const graph = useMemo(() => {
    const list: FlowNode[] = [], edges: Edge[] = [];
    let previous = '';
    const add = (id: string, data: Omit<Data, 'mobile' | 'onSelect'>) => { list.push({ id, type: 'cell', data: { ...data, mobile, onSelect }, position: { x: 0, y: 0 }, selected: id === selected, width: data.kind === 'join' ? 130 : 228, height: data.kind === 'join' || data.kind === 'wait' ? 86 : 140 }); };
    const edge = (from: string, to: string, label?: string, dashed = false) => { if (from) edges.push({ id: `${from}>${to}`, source: from, target: to, type: 'smoothstep', label, style: { stroke: '#687585', strokeWidth: 1.5, strokeDasharray: dashed ? '5 4' : undefined }, markerEnd: { type: MarkerType.ArrowClosed, color: '#687585' }, labelStyle: { fontSize: 14 }, labelBgPadding: [5, 3], labelBgStyle: { fill: '#f7f8fa' } }); };
    for (const r of run.rounds) {
      if (collapsed.includes(r.id) && !roundCells(r).some(c => c.id === selected)) {
        add(r.id, { kind: 'collapsed', label: `第 ${r.number} 回・終了`, detail: `${roundCells(r).length} セル / 押して展開`, round: r.number, expand: () => setCollapsed(xs => xs.filter(x => x !== r.id)) }); edge(previous, r.id); previous = r.id; continue;
      }
      for (const c of r.owners) { add(c.id, { kind: c.kind, label: c.type, cell: c, round: r.number }); edge(previous, c.id); previous = c.id; }
      add(r.judge.id, { kind: 'judge', label: `第 ${r.number} 回 · judge`, cell: r.judge, round: r.number }); edge(previous, r.judge.id);
      const joinId = `${r.id}-join`; add(joinId, { kind: 'join', label: '合流', detail: r.joined ? '分岐の出力が揃いました' : `${r.branches.length} 本の分岐を待つ`, round: r.number });
      for (const b of r.branches) {
        let prev = r.judge.id;
        b.cells.forEach((c, i) => { add(c.id, { kind: c.kind, label: c.type, cell: c, round: r.number, branch: b.id }); edge(prev, c.id, i === 0 ? b.label : undefined); prev = c.id; });
        if (b.waiting) { add(b.waiting.id, { kind: 'wait', label: '返答待ち', detail: '分岐の終端', round: r.number, branch: b.id }); edge(prev, b.waiting.id); prev = b.waiting.id; }
        edge(prev, joinId, undefined, !!b.waiting);
      }
      if (!r.branches.length) edge(r.judge.id, joinId, '次の分岐を判定中');
      previous = joinId;
      if (r.report) { add(r.report.id, { kind: 'report', label: 'report', cell: r.report, round: r.number }); edge(previous, r.report.id); previous = r.report.id; }
    }
    return { nodes: list, edges };
  }, [run, collapsed, mobile, selected, onSelect]);
  useEffect(() => {
    let alive = true;
    setReady(false);
    elk.layout({ id: 'root', layoutOptions: { 'elk.algorithm': 'layered', 'elk.direction': mobile ? 'DOWN' : 'RIGHT', 'elk.spacing.nodeNode': '44', 'elk.layered.spacing.nodeNodeBetweenLayers': '72', 'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES', 'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF' }, children: graph.nodes.map(n => ({ id: n.id, width: n.width, height: n.height })), edges: graph.edges.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] })) }).then(layout => {
      if (!alive) return;
      setNodes(graph.nodes.map(n => { const p = layout.children!.find(x => x.id === n.id)!; return { ...n, position: { x: p.x || 0, y: p.y || 0 } }; })); setReady(true);
    }); return () => { alive = false; };
  }, [graph]);
  useEffect(() => { if (!ready) return; const frame = requestAnimationFrame(() => { const current = selected ? nodes.filter(n => n.id === selected) : nodes.filter(n => n.data.cell?.state === '動いている'); api.fitView({ nodes: mobile && !compact && current.length ? current.slice(0, 1) : undefined, padding: 0.14, maxZoom: 1, minZoom: mobile && !compact ? 0.65 : 0.12 }); }); return () => cancelAnimationFrame(frame); }, [ready]);
  const current = () => { const running = nodes.filter(n => n.data.cell?.state === '動いている'); const targets = running.length ? running : nodes.filter(n => n.data.round === run.rounds.at(-1)?.number); api.fitView({ nodes: mobile ? targets.slice(0, 1) : targets, maxZoom: 1, minZoom: 0.7, padding: 0.2, duration: 250 }); };
  return <div className={compact ? 'flow-section compact' : 'flow-section'}>
    {!compact && <div className="flow-toolbar"><div className="button-row"><Button ariaLabel="拡大" iconName="zoom-in" onClick={() => api.zoomIn()}/><Button ariaLabel="縮小" iconName="zoom-out" onClick={() => api.zoomOut()}/><Button onClick={() => api.fitView({ padding: 0.1, minZoom: 0.02, maxZoom: 1, duration: 250 })}>全体表示</Button><Button onClick={current}>いま動いているところへ</Button><Button onClick={() => showLegend(true)}>凡例</Button></div>
      <div className="button-row">{run.rounds.length > 1 && <Button onClick={() => setCollapsed(collapsed.length ? [] : run.rounds.filter(r => r.joined).map(r => r.id))}>{collapsed.length ? '終わった回をすべて開く' : '終わった回を畳む'}</Button>}{onInsert && <Button iconName="add-plus" onClick={onInsert}>次の回にセルを挿し込む</Button>}</div></div>}
    <div className="flow-canvas" data-testid="flow-canvas" data-ready={ready} data-direction={mobile ? 'DOWN' : 'RIGHT'}>
      <ReactFlow<FlowNode> nodes={nodes} edges={graph.edges} nodeTypes={nodeTypes} nodesDraggable={false} nodesConnectable={false} elementsSelectable={true} minZoom={0.02} maxZoom={1.5} proOptions={{ hideAttribution: true }} ariaLabelConfig={{ 'minimap.ariaLabel': 'フローの縮小図' }}>
        <Background color="#d7dce2" gap={24}/>{!mobile && !compact && <MiniMap pannable zoomable nodeColor={n => (n.data.cell as Cell | undefined)?.state === '動いている' ? '#0972d3' : '#b7bfc8'}/>}<div className="canvas-caption">{run.rounds.length} 回 · {run.rounds.flatMap(roundCells).length} セル{!compact && ' / 図の中をドラッグして移動'}</div>
      </ReactFlow>
    </div>
    <Modal visible={legend} onDismiss={() => showLegend(false)} header="フロー図の凡例" closeAriaLabel="凡例を閉じる" footer={<Button onClick={() => showLegend(false)}>閉じる</Button>}><div className="legend-grid">{[['owner', 'オーナー：指示・返答・書き換え'], ['judge', '判定器：次の仕事・分岐 A'], ['work', '作業：実装・検証など'], ['observe', 'オブザーバー：分岐 B・指示だけ'], ['report', '報告：結果と問い'], ['wait', '返答待ち：セルではなく分岐の終端']].map(([kind, label]) => <div key={kind} className={`legend-item kind-${kind}`}><Mark kind={kind}/>{label}</div>)}</div><p>線は入力の受け渡し、分かれた線は並行作業、集まった線は合流です。</p><div className="button-row">{['待機', '動いている', '終わった', '失敗した', '中断した', '返答待ち'].map(s => <Status value={s} key={s}/>)}</div></Modal>
  </div>;
}
export function Flow(props: Parameters<typeof Canvas>[0]) { return <ReactFlowProvider><Canvas key={props.run.id} {...props}/></ReactFlowProvider>; }
