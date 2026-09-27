import { test as base, expect, type Page } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import type { MockState, Task } from '../src/mock/model';

const evidence = 'docs/browser-verification.json';
const test = base.extend<{ audit: void }>({ audit: [async ({ page }, use, info) => {
  const errors: string[] = [], external: string[] = [], requests: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('request', req => { requests.push(req.url()); if (!req.url().startsWith('http://127.0.0.1:4173') && !/^(data|blob):/.test(req.url())) external.push(req.url()); });
  await use();
  expect(errors, 'JavaScript errors').toEqual([]); expect(external, 'external requests').toEqual([]);
  const records = existsSync(evidence) ? JSON.parse(readFileSync(evidence, 'utf8')) : {};
  records[`${info.project.name}/${info.title}`] = { status: info.status, javascriptErrors: errors, externalRequests: external, localRequestCount: requests.length, width: info.project.use.viewport?.width };
  writeFileSync(evidence, JSON.stringify(records, null, 2) + '\n');
}, { auto: true }] });

async function model(page: Page): Promise<MockState> { return page.evaluate(() => JSON.parse(localStorage.getItem('pda-ui-mock-v2')!)); }
async function task(page: Page, id: string): Promise<Task> { return (await model(page)).tasks.find(t => t.id === id)!; }
async function graphReady(page: Page) { if (await page.getByTestId('flow-canvas').count()) await expect(page.getByTestId('flow-canvas').first()).toHaveAttribute('data-ready', 'true'); }
async function layout(page: Page) {
  const dimensions = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
  expect(dimensions.scroll, 'page body must not overflow').toBeLessThanOrEqual(dimensions.width);
}
async function go(page: Page, path: string) { await page.goto(`/#${path}`); await expect(page.locator('.app-content')).toBeVisible(); await graphReady(page); await layout(page); }
async function screenshot(page: Page, uc: number) { await layout(page); mkdirSync('docs/screenshots', { recursive: true }); const fullPage = ![3, 5, 7, 8].includes(uc); if (fullPage) { await top(page); await page.waitForTimeout(100); } await page.screenshot({ path: `docs/screenshots/UC${String(uc).padStart(2, '0')}-${page.viewportSize()!.width}.png`, fullPage, animations: 'disabled' }); }
async function select(page: Page, label: string, text: string) { await page.getByRole('button', { name: new RegExp(label) }).click(); await page.getByRole('option', { name: text, exact: true }).click(); }
async function node(page: Page, id: string) { await page.getByRole('button', { name: '全体表示', exact: true }).click(); await page.waitForTimeout(300); await page.getByTestId(`node-${id}`).getByRole('button').click(); await expect(page.getByTestId('cell-details')).toBeVisible(); }
async function top(page: Page) { await page.evaluate(() => window.scrollTo(0, 0)); }
test.beforeEach(async ({ page }) => { await page.goto('/'); await page.evaluate(() => { localStorage.removeItem('pda-ui-mock-v2'); localStorage.removeItem('pda-last-reporter'); }); await page.reload(); await page.getByRole('heading', { name: '概観', exact: true }).waitFor(); });

test('UC1 概観から30秒で見渡す', async ({ page }) => {
  await expect(page.getByRole('heading', { name: '自分の番 (3)' })).toBeVisible();
  await expect(page.locator('.pending-card')).toHaveCount(3);
  await expect(page.locator('.work-line')).toHaveCount(9);
  await expect(page.locator('.attention-tag')).toHaveCount(0); await expect(page.getByText('長時間の作業', { exact: true })).toHaveCount(0); await expect(page.locator('.executor-summary').filter({ hasText: 'codex-personal' })).toContainText('5時間制限');
  await expect(page.locator('.executor-summary').filter({ hasText: 'fake-b' })).toContainText('止まっている');
  await page.getByRole('link', { name: '画面 API を実装する', exact: true }).click();
  await expect(page.getByTestId('task-page')).toBeVisible();
  await go(page, '/overview'); await screenshot(page, 1);
});
test('UC2 長文で新しいタスクを出す', async ({ page }) => {
  await page.getByRole('link', { name: '新しいタスク', exact: true }).click();
  const instruction = '# セッション検索を実装する\n\nスマートフォンの操作を先に確認してください。\n\n- 指示とタスク ID を検索\n- 空の結果を明示\n\n' + '確認したことを報告にまとめる。'.repeat(100);
  await page.getByRole('textbox', { name: '指示', exact: true }).fill(instruction);
  await page.getByRole('button', { name: '見た目を確認' }).click(); await expect(page.getByTestId('instruction-preview').locator('h1')).toHaveText('セッション検索を実装する');
  await page.getByRole('textbox', { name: '作業ディレクトリ', exact: true }).fill('/work/search');
  await expect(page.getByRole('button', { name: /報告を書く実行器/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'タスクを出す' }).click(); await graphReady(page);
  const created = (await model(page)).tasks[0]; expect(created.initial).toBe(instruction); expect('reporter' in created).toBe(false);
  await expect(page.getByText('新しいタスクを受け付けました。')).toBeVisible();
  expect(created.flow.rounds[0].owners).toHaveLength(1); expect(created.flow.rounds[0].judge.state).toBe('動作中');
  await expect(page.getByRole('tab', { name: '報告', exact: true })).toHaveAttribute('aria-selected', 'true');
  await go(page, `/tasks/${created.id}`); await screenshot(page, 2);
});
test('UC3 分岐とセルの内部を見る', async ({ page }) => {
  await go(page, '/tasks/api?tab=flow');
  await expect(page.locator('.react-flow__edge')).toHaveCount(3);
  await page.getByRole('button', { name: '動作中のセルへ' }).click();
  await node(page, 'api-implement');
  await expect(page).toHaveURL(/cell=api-implement/);
  await page.getByTestId('cell-details').getByRole('button', { name: 'プロンプト' }).click();
  await expect(page.getByTestId('cell-details')).toContainText('タスク一覧の状態と入力待ちの理由を返す API');
  await expect(page.getByTestId('cell-details')).toContainText('read_file');
  await expect(page.getByTestId('cell-details')).toContainText('13分 40秒');
  await screenshot(page, 3);
});
test('UC4 意図しない実行を中断する', async ({ page }) => {
  await go(page, '/tasks/api?tab=flow'); await page.getByRole('button', { name: '中断', exact: true }).click();
  const modal = page.getByRole('dialog'); await expect(modal).toContainText('止まるセル（2）');
  await modal.getByRole('textbox', { name: '判定器に渡す理由か次の指示（任意）', exact: true }).fill('個人の環境では書き込まず、読み取りだけにしてください。');
  await modal.getByRole('button', { name: '実行を中断する', exact: true }).click(); await graphReady(page);
  await expect(page.getByTestId('node-api-implement')).toHaveAttribute('data-state', '中断した');
  const t = await task(page, 'api'); for (const b of t.flow.rounds[0].branches) { expect(b.cells.some(c => c.decision === '分岐 A：オブザーバー')).toBeTruthy(); expect(b.cells.some(c => c.kind === 'owner' && c.input.includes('読み取りだけ'))).toBeTruthy(); }
  await page.getByRole('button', { name: '全体表示', exact: true }).click(); await screenshot(page, 4);
});
test('UC5 次の回へ指示を重ねる', async ({ page }) => {
  await go(page, '/tasks/api?tab=flow'); await page.getByRole('textbox', { name: '重ねる指示' }).fill('検索結果が空の場合の案内も加えてください。');
  await page.getByRole('button', { name: '送信', exact: true }).click(); await graphReady(page);
  const t = await task(page, 'api'), added = t.flow.rounds.at(-1)!.owners[0]; expect(added.badge).toBe('次の回から有効');
  await expect(page.getByTestId(`node-${added.id}`)).toHaveAttribute('data-kind', 'owner');
  await node(page, added.id); await screenshot(page, 5);
});
test('UC6 指示を書き換え同じフローでやり直す', async ({ page }) => {
  await go(page, '/tasks/api?tab=flow'); await node(page, 'api-owner'); await page.getByRole('button', { name: '初期の指示を書き換える', exact: true }).click();
  await page.getByRole('textbox', { name: '書き換える指示', exact: true }).fill('まず読み取り用 API だけを実装してください。');
  await page.getByRole('button', { name: '書き換えを保存' }).click();
  expect((await task(page, 'api')).flow.rounds.at(-1)!.owners[0].type).toBe('書き換え');
  await node(page, 'api-owner'); await page.getByRole('button', { name: '初期の指示を書き換える', exact: true }).click();
  await page.getByRole('textbox', { name: '書き換える指示', exact: true }).fill('スマートフォンの読み取り用 API を最初から作ってください。');
  await page.getByRole('radio', { name: /最初からやり直す/ }).check();
  await page.getByRole('button', { name: '書き換えを保存' }).click(); await graphReady(page);
  const t = await task(page, 'api'); expect('runs' in t).toBe(false); expect(t.flow.rounds[0].branches[0].cells[0].state).toBe('中断した');
  await expect(page.getByRole('button', { name: /実行を切り替える/ })).toHaveCount(0);
  await screenshot(page, 6);
});
test('UC7 選択したセルの次と並列に追加する', async ({ page }) => {
  await go(page, '/tasks/api?tab=flow');
  await expect(page.getByTestId('node-insert-next')).toHaveCount(0);
  await node(page, 'api-r1-judge');
  await page.getByRole('button', { name: 'この次にセルを追加', exact: true }).click();
  await page.getByRole('textbox', { name: 'セルへの入力', exact: true }).fill('変更した API の静的検査を実行してください。');
  await page.getByRole('button', { name: 'セルを追加する', exact: true }).click(); await graphReady(page);
  const t = await task(page, 'api'), c = t.flow.rounds[0].branches.flatMap(b => b.cells).find(c => c.input.startsWith('変更した API'))!;
  expect(c.after).toBe('api-r1-judge'); expect(c.origin).toBe('オーナーの操作'); expect(t.flow.rounds).toHaveLength(1);
  await node(page, 'api-implement'); await page.getByRole('button', { name: '並列するセルを追加', exact: true }).click();
  await page.getByRole('textbox', { name: 'セルへの入力', exact: true }).fill('並列で検査してください。');
  await page.getByRole('button', { name: 'セルを追加する', exact: true }).click(); await graphReady(page);
  const parallel = (await task(page, 'api')).flow.rounds[0].branches.flatMap(b => b.cells).find(c => c.input === '並列で検査してください。')!;
  expect(parallel.after).toBe('api-r1-judge'); await screenshot(page, 7);
});
test('UC8 動作中セルへ追加入力を送る', async ({ page }) => {
  await go(page, '/tasks/api?tab=flow'); await node(page, 'api-implement');
  await page.getByRole('textbox', { name: '指示を追加', exact: true }).fill('状態名は requirements.md の4つに合わせてください。');
  await page.getByTestId('cell-details').getByRole('button', { name: '送信', exact: true }).click();
  await expect(page.getByTestId('extra-inputs')).toContainText('状態名は'); await expect(page.getByTestId('node-api-implement')).toContainText('追加入力 1 件'); await screenshot(page, 8);
});
test('UC9 失敗の分岐とオーナー再試行を追う', async ({ page }) => {
  await go(page, '/tasks/retry?tab=flow'); await expect(page.getByTestId('node-retry-a')).toContainText('分岐 A：再試行'); await expect(page.getByTestId('node-retry-copy')).toContainText('複製');
  await node(page, 'retry-failed'); await select(page, '再試行する実行器', 'claude-personal 生きている');
  await page.getByRole('button', { name: 'セルを再試行する' }).click(); await expect(page.getByTestId('cell-details')).toContainText('オーナーの再試行');
  expect((await task(page, 'retry')).flow.rounds[0].branches[0].cells[0].attempts.at(-1)!.executor).toBe('claude-personal');
  await go(page, '/tasks/environment?tab=flow'); await expect(page.getByTestId('node-env-b')).toContainText('分岐 B：判断不要'); await expect(page.getByTestId('node-env-redo')).toContainText('やり直し');
  await go(page, '/tasks/questions?tab=flow'); await node(page, 'q-wait'); await expect(page.getByTestId('cell-details')).toContainText('保存範囲');
  await go(page, '/tasks/retry?tab=flow'); await page.getByRole('button', { name: '全体表示', exact: true }).click(); await screenshot(page, 9);
});
test('UC10 報告と文脈を見て3形式の問いに答える', async ({ page }) => {
  await go(page, '/inbox'); await page.locator('.pending-cards').getByRole('link').filter({ hasText: '判定器の問いと保存範囲を見直す' }).click();
  await expect(page.getByTestId('report-view').locator('table').first()).toBeVisible();
  const context = page.getByTestId('question-context'); await expect(context.getByTestId('node-questions-owner')).toContainText('初期の指示'); await expect(context).toContainText('失敗したセルの最終応答'); await expect(context).toContainText('オブザーバーの判断'); await expect(context.locator('.react-flow')).toBeVisible(); await expect(page.getByTestId('report-view')).toContainText('design-notes.md'); await expect(page.getByTestId('artifact-notes')).toContainText('docs/design-notes.md');
  await page.getByTestId('question-approve').getByRole('textbox', { name: /それ以外/ }).fill('対象の一覧を確認してから承認します。'); await expect(page.getByRole('button', { name: '送信', exact: true })).toBeDisabled();
  expect((await task(page, 'questions')).state).toBe('入力待ち');
  await page.getByTestId('question-destination').getByRole('radio', { name: '個人の記憶に保存', exact: true }).check();
  await page.getByRole('textbox', { name: '保存するときに守る条件を教えてください' }).fill('共有可能と確認した記録だけを残してください。'); await page.getByRole('button', { name: '送信', exact: true }).click();
  expect((await task(page, 'questions')).state).toBe('進行中'); expect((await task(page, 'questions')).flow.rounds.at(-1)!.owners[0].type).toBe('返答');
  await expect(page).toHaveURL(/tasks\/questions/);
  await expect(page.getByText('返答を送信しました。', { exact: true })).toBeVisible(); await screenshot(page, 10);
  await go(page, '/inbox'); await expect(page.locator('.pending-cards')).not.toContainText('判定器の問いと保存範囲を見直す');
});
test('UC11 整形報告と成果物を受け取り完了を記録する', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await go(page, '/tasks/result?tab=report'); await expect(page.locator('.document table')).toHaveCount(1); await expect(page.locator('.document pre')).toHaveCount(1); await expect(page.locator('.document li')).toHaveCount(18);
  await page.getByRole('navigation', { name: '報告の目次' }).getByRole('link', { name: '検証結果', exact: true }).click();
  await page.getByRole('button', { name: 'コードを複写' }).click(); expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('TaskState');
  await page.getByRole('tab', { name: '成果物 (4)', exact: true }).click();
  await page.getByTestId('artifact-notes').getByRole('link').click(); await expect(page.getByRole('dialog').locator('h1')).toHaveText('画面 API の設計ノート'); await page.getByRole('dialog').getByRole('button', { name: '閉じる', exact: true }).click();
  await expect(page.getByRole('button', { name: '持ち出す' })).toHaveCount(0);
  await page.getByTestId('artifact-diagram').getByRole('link').click(); await expect(page.getByRole('dialog').getByRole('img', { name: 'flow.svg' })).toBeVisible(); await page.getByRole('dialog').getByRole('button', { name: '閉じる', exact: true }).click();
  await page.getByTestId('artifact-git').getByRole('link').click(); await expect(page.getByRole('dialog')).toBeVisible(); await page.getByRole('dialog').getByRole('button', { name: '閉じる', exact: true }).click(); await expect(page.getByTestId('artifact-published').getByRole('link')).toHaveAttribute('target', '_blank');
  await page.getByRole('tab', { name: '報告 (1)', exact: true }).click(); await page.getByRole('button', { name: '完了', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: '完了', exact: true }).click();
  expect((await task(page, 'result')).state).toBe('完了'); await top(page); await screenshot(page, 11);
});
test('UC12 実行器の3セルを見て起動と停止を行う', async ({ page }) => {
  await go(page, '/executors'); const codex = page.getByTestId('executor-codex-personal'); await expect(codex.locator('.assigned-cell')).toHaveCount(3); await expect(codex).not.toContainText('受け取り元：'); await expect(codex).not.toContainText('渡し先：');
  await page.getByTestId('assigned-api-implement').click(); await expect(page.getByTestId('cell-details')).toContainText('read_file'); await page.getByRole('complementary').getByRole('link', { name: 'implement · codex-personal', exact: true }).click(); await expect(page).toHaveURL(/tasks\/api.*cell=api-implement/);
  await go(page, '/executors'); await page.getByTestId('executor-fake-b').getByRole('button', { name: '起こす', exact: true }).click(); await expect(page.getByTestId('executor-fake-b')).toContainText('生きている');
  await page.getByTestId('executor-codex-personal').getByRole('button', { name: '止める', exact: true }).click(); await expect(page.getByRole('dialog')).toContainText('担っている 3 セルを中断'); await page.getByRole('button', { name: '実行器を停止する', exact: true }).click();
  await expect(page.getByTestId('executor-codex-personal')).toContainText('止まっている'); expect((await task(page, 'api')).flow.rounds[0].branches[0].cells[0].state).toBe('中断した'); await top(page); await screenshot(page, 12);
});

test('受け入れ：全画面・場面・字の大きさ・明色・60件の一覧', async ({ page }) => {
  for (const path of ['/overview', '/tasks', '/new', '/tasks/api', '/tasks/result?tab=report', '/tasks/result?tab=artifacts', '/inbox', '/inbox/questions', '/executors', '/executors/codex-personal', '/roles', '/skills']) {
    await go(page, path);
    const small = await page.evaluate(() => [...document.querySelectorAll('p,button,input,textarea,th,td,li,label,a')].filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (el.textContent || '').trim() && !el.closest('.react-flow__minimap'); }).map(el => ({ text: el.textContent!.slice(0, 40), size: parseFloat(getComputedStyle(el).fontSize) })).filter(x => x.size < 14));
    expect(small, `text sizes on ${path}`).toEqual([]);
    expect(await page.evaluate(() => getComputedStyle(document.body).colorScheme)).toBe('light');
  }
  for (const [scene, expected] of [['タスクなし', 'まだタスクがありません'], ['読み込み中', 'タスクを読み込んでいます'], ['上流に届かない', '上流に届きません'], ['入力待ちなし', '入力待ちはありません。'], ['実行器が不明', '不明'], ['60件のタスク', '自分の番']]) {
    if (await page.getByRole('button', { name: '見本の操作', exact: true }).getAttribute('aria-expanded') !== 'true') await page.getByRole('button', { name: '見本の操作', exact: true }).click(); await select(page, '見本の場面', scene); await expect(page.getByText(expected, { exact: false }).first()).toBeVisible(); await layout(page);
  }
  await go(page, '/tasks'); await expect(page.getByText('60 件 · 1 / 6 ページ')).toBeVisible(); await page.getByRole('button', { name: '次のページ', exact: true }).click(); await expect(page.getByText('60 件 · 2 / 6 ページ')).toBeVisible();
  await page.getByRole('searchbox', { name: 'タスクを検索' }).fill('画面 API'); await expect(page.getByText('2 件 · 1 / 1 ページ')).toBeVisible();
  await select(page, '並べ替え', '実行時間が長い順');
  await page.getByRole('button', { name: '完了 (25)', exact: true }).click(); await layout(page);
});
test('受け入れ：8回30セル・全体表示・現在位置・凡例・中止', async ({ page }) => {
  await go(page, '/tasks/large?tab=flow'); await expect(page.locator('.canvas-caption')).toContainText('8 回 · 30 セル'); await expect(page.locator('[data-kind="collapsed"]')).toHaveCount(7);
  await page.getByRole('button', { name: '全体表示', exact: true }).click(); await page.waitForTimeout(300); const overview = await page.locator('.react-flow__viewport').getAttribute('style'); await page.getByRole('button', { name: '動作中のセルへ' }).click(); await page.waitForTimeout(300); expect(await page.locator('.react-flow__viewport').getAttribute('style')).not.toBe(overview);
  await page.getByRole('button', { name: '終わった回をすべて開く' }).click(); await graphReady(page); await expect(page.locator('.flow-node[data-state]:not([data-state=""])')).toHaveCount(30);
  await page.getByRole('button', { name: '凡例', exact: true }).click(); await expect(page.getByRole('dialog').locator('.legend-item')).toHaveCount(6); await page.getByRole('dialog').getByRole('button', { name: '閉じる', exact: true }).click();
  await page.getByRole('button', { name: '中止', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: '中止', exact: true }).click(); expect((await task(page, 'large')).state).toBe('中止');
  await go(page, '/tasks/restart?tab=report'); await expect(page.getByRole('heading', { name: '以前の指示への報告' })).toBeVisible();
});
test('受け入れ：一歩ずつの進行・HTML無害化・途中の報告', async ({ page }) => {
  await go(page, '/tasks/api?tab=report'); await expect(page.getByText('途中です。オーナー向けの報告はまだありません。')).toBeVisible();
  await go(page, '/tasks/api?tab=flow'); await page.getByRole('button', { name: '見本の操作', exact: true }).click();
  for (let i = 0; i < 24 && (await task(page, 'api')).state === '進行中'; i++) { await page.getByRole('button', { name: '1 歩進める', exact: true }).click(); await graphReady(page); }
  const t = await task(page, 'api'); expect(t.state).toBe('入力待ち'); expect(t.flow.reports).toHaveLength(1); expect(t.flow.rounds[0].branches.some(b => b.cells.some(c => c.kind === 'observe'))).toBeTruthy();
  await page.getByRole('textbox', { name: '重ねる指示' }).fill('もう一度検証してください。'); await page.getByRole('button', { name: '送信', exact: true }).click(); expect((await task(page, 'api')).state).toBe('進行中');
  await go(page, '/tasks/core?tab=report'); await expect(page.locator('.document table')).toHaveCount(1);
  await page.evaluate(() => { const s = JSON.parse(localStorage.getItem('pda-ui-mock-v2')!); s.tasks.find((t: { id: string }) => t.id === 'core').flow.reports[0].body += '<script>window.__unsafe=1</script><img src="https://example.invalid/track" onerror="window.__unsafe=2"><a href="javascript:window.__unsafe=3">不正リンク</a>'; localStorage.setItem('pda-ui-mock-v2', JSON.stringify(s)); });
  await page.reload(); expect(await page.evaluate(() => '__unsafe' in window)).toBeFalsy(); await expect(page.locator('.document script')).toHaveCount(0); await expect(page.locator('.document img')).toHaveCount(0); await layout(page);
});
