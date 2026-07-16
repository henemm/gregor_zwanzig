import { defineConfig } from '@playwright/test';
// Staging-E2E Issue #1272 — geteilter Sortier-Baustein (AC-1/4/5).
//
// Auth-Muster identisch zu playwright.1256-s6.staging.config.ts: nginx-Basic-Auth
// via GZ_VALIDATOR_*, App-Login über das geteilte Setup-Projekt (storageState statt
// per-Test-Login — sonst 429-Rate-Limit).
const user = process.env.GZ_VALIDATOR_USER!;
const pass = process.env.GZ_VALIDATOR_PASS!;

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 1,
	reporter: [['list']],
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /feat-1256-s2\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: /sortable-list-shared\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1256-s2.json' }
		}
	]
});
