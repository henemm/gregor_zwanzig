import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1359 Scheibe 1 (Metrik-Reihenfolge im
// Ortsvergleich, AC-3/AC-6). Config-Muster identisch zu
// playwright.1256-s8d.staging.config.ts (nginx-Basic-Auth = GZ_VALIDATOR_*,
// App-Login separat via dediziertem Setup-Projekt — eigener storageState statt
// Login pro Testlauf, s. reference_staging_e2e_storagestate_login_rate_limit —
// 429-Rate-Limit).
// Kein `webServer`-Block: getestet wird die auf Staging deployte App selbst.
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
		{ name: 'setup', testMatch: /compare-metric-order\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-metric-order\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-compare-metric-order.json' }
		}
	]
});
