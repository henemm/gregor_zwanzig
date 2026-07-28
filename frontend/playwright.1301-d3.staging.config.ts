import { defineConfig } from '@playwright/test';
// Staging-Verifikation D3 von Epic #1301 (Alarm-Tab Struktur/Beschriftung,
// Commit e203a2d5). Config-Muster identisch zu playwright.1301-d2.staging.config.ts.
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
		{ name: 'setup', testMatch: /d3-1301-alarm-tab-struktur\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/d3-1301-alarm-tab-struktur\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1301-d3.json' }
		}
	]
});
