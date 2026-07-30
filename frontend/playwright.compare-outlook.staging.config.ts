import { defineConfig } from '@playwright/test';
// Staging-Verifikation Ortsvergleich-Ausblick: gruppierte Metrik-Auswahl
// (Issue #1406 Scheibe A, geteiltes Muster #1411). Config-Muster identisch zu
// playwright.compare-metric-order.staging.config.ts.
const user = process.env.GZ_VALIDATOR_USER!;
const pass = process.env.GZ_VALIDATOR_PASS!;

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /compare-outlook-metric-selection\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-outlook-metric-selection\.staging\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-compare-outlook.json' }
		}
	]
});
