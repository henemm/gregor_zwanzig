import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1256 Scheibe S8c (Hub-Fidelity R2+R3: Layout-
// Tab-Rahmen, SummaryCards-Copy, Orte-Tab-Rahmen, Breadcrumb, profileLabel,
// Mobile-Eyebrow, Mobile-Summary-Stack). Config-Muster identisch zu
// playwright.hub-send-dialog-target.staging.config.ts (nginx-Basic-Auth = GZ_VALIDATOR_*,
// App-Login separat via dediziertem Setup-Projekt — eigener storageState
// statt Login pro Testlauf, s. reference_staging_e2e_storagestate_login_rate_limit
// — 429-Rate-Limit).
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
		{ name: 'setup', testMatch: /feat-1256-s8c\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			// #2682: Versand-Historie/„Zuletzt raus" der geteilten Übersicht (VH-1..VH-4).
			// Nur /e2e-verify gegen Staging — VH-3 versendet echt, gehoert NICHT in ci_e2e_specs.txt.
			testMatch: [/compare-hub-fidelity-s8c\.spec\.ts/, /hub-uebersicht-versand-historie\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1256-s8c.json' }
		}
	]
});
