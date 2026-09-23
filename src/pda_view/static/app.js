let selectedJob = null;
let selectedCell = null;
let busy = false;
const el = id => document.getElementById(id);
function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value == null ? '' : String(value);
  return node;
}
function stamp(value) { return value ? new Date(value).toLocaleString('ja-JP') : '—'; }
async function get(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) throw new Error(data.reason || '取得に失敗しました');
  return data;
}
function table(target, rows, columns, select, active) {
  const node = document.createElement('table');
  const head = document.createElement('thead');
  const titles = document.createElement('tr');
  columns.forEach(([label]) => titles.append(text('th', label)));
  head.append(titles); node.append(head);
  const body = document.createElement('tbody');
  rows.forEach(row => {
    const tr = document.createElement('tr');
    if (active(row)) tr.className = 'selected';
    columns.forEach(([label, value], index) => {
      const td = document.createElement('td'); td.dataset.label = label;
      if (index === 0) {
        const button = text('button', value(row));
        button.onclick = () => { select(row); refresh(); };
        button.setAttribute('aria-pressed', String(active(row)));
        td.append(button);
      } else if (label === '状態') {
        const badge = text('span', value(row));
        badge.className = 'status ' + row.status; td.append(badge);
      } else td.textContent = value(row) ?? '';
      tr.append(td);
    });
    body.append(tr);
  });
  node.append(body); target.replaceChildren(node);
}
async function refresh() {
  if (busy) return;
  busy = true;
  const job = selectedJob, cell = selectedCell;
  try {
    const jobs = await get('/api/jobs');
    table(el('jobs'), jobs, [
      ['仕事', r => r.initial_input || r.job_id], ['状態', r => r.status],
      ['開始', r => stamp(r.start_time)], ['実行器', r => r.executors.join(', ')]
    ], r => { selectedJob = r.job_id; selectedCell = null; }, r => r.job_id === selectedJob);
    if (job) {
      const [detail, events] = await Promise.all([
        get('/api/jobs/' + encodeURIComponent(job)),
        get('/api/jobs/' + encodeURIComponent(job) + '/events' +
            (cell ? '?cell=' + encodeURIComponent(cell) : ''))
      ]);
      if (job !== selectedJob || cell !== selectedCell) return;
      el('detail').hidden = false;
      el('description').textContent = `${detail.job_id} / ${detail.status}\n${detail.initial_input}\n${detail.reason || ''}`;
      table(el('cells'), detail.cells, [
        ['セル', r => r.ref], ['type / 実行器', r => `${r.type} / ${r.executor}`],
        ['状態', r => r.status], ['再試行 / 所要時間', r => `${r.retry_count} 回 / ${r.duration_ms} ms`],
        ['受け渡し / 理由', r => `${r.output_kind || ''} ${r.output_excerpt} ${r.reason || ''}`]
      ], r => { selectedCell = selectedCell === r.ref ? null : r.ref; }, r => r.ref === selectedCell);
      el('filter').textContent = cell ? `絞り込み：${cell}` : '全セル';
      el('events').replaceChildren(...events.map(r => text('li',
        `${stamp(r.time / 1000)} / ${r.cell || ''} / ${r.executor || ''} / ${r.kind} ${r.summary}`)));
    }
    el('error').textContent = '';
  } catch (error) { el('error').textContent = `更新できません：${error.message}`; }
  finally { busy = false; }
}
refresh();
setInterval(refresh, 3000);
