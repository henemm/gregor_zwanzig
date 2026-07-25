import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1360 (Scheibe S1a von Epic #1372): Layout-Reiter
// des Ortsvergleichs aufgelöst, Stundenverlauf im Reiter Wetter-Metriken
// (AC-1..AC-6). Config-Muster identisch zu
// playwright.compare-metric-order.staging.config.ts (nginx-Basic-Auth =
// GZ_VALIDATOR_*, App-Login separat via dediziertem Setup-Projekt — eigener
// storageState statt Login pro Testlauf, s.
// reference_staging_e2e_storagestate_login_rate_limit — 429-Rate-Limit).
//
// Kein `webServer`-Block: getestet wird die auf Staging deployte App selbst.
// `baseURL` zeigt deshalb EXPLIZIT auf Staging — `GZ_API_BASE` aus
// playwright.config.ts zeigt per Default auf PRODUKTION und darf hier nie
// greifen; zusätzlich sperrt `assertNotProdBaseURL` im Setup jeden Lauf gegen
// die Prod-Domain (#1265).
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
		{ name: 'setup', testMatch: /compare-layout-tab-dissolution\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-layout-tab-dissolution\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-compare-layout-tab.json' }
		}
	]
});
