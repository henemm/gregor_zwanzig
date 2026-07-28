import { defineConfig } from '@playwright/test';
// Staging-Verifikation Epic #1301 Scheibe C2 (Stundenverlauf-Steuerung im
// Hub-Layout-Tab, AC-5-Fix Issue #1299/Commit 8fdb514b).
// Config-Muster identisch zu playwright.1256-s8d.staging.config.ts
// (nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login separat via dediziertem
// Setup-Projekt — eigener storageState statt Login pro Testlauf, s.
// reference_staging_e2e_storagestate_login_rate_limit — 429-Rate-Limit).
const user = process.env.GZ_VALIDATOR_USER!;
const pass = process.env.GZ_VALIDATOR_PASS!;

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /feat-1301-c2-hub-zugang\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-hub-layout-hourly-c2\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1301-c2.json' }
		}
	]
});
