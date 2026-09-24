import { defineConfig } from '@playwright/test';
import path from 'node:path';
process.env.PLAYWRIGHT_BROWSERS_PATH = path.resolve('.cache/ms-playwright');
export default defineConfig({
  testDir: './tests', testMatch: 'walkthrough.spec.ts', fullyParallel: false, workers: 1,
  timeout: 60000, expect: { timeout: 10000 }, reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  use: { baseURL: 'http://127.0.0.1:4173', locale: 'ja-JP', timezoneId: 'Asia/Tokyo', reducedMotion: 'reduce', trace: 'retain-on-failure' },
  webServer: { command: 'python3 -m http.server 4173 --bind 127.0.0.1 --directory site', url: 'http://127.0.0.1:4173', reuseExistingServer: false, timeout: 15000 },
  projects: [1440, 390].map(width => ({ name: `${width}px`, use: { viewport: { width, height: width === 1440 ? 1000 : 844 } } })),
});
