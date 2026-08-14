import { defineConfig } from '@playwright/test';
// Staging-Verifikation der Trip-Vorschau-Spaltenauswahl (#1720 Scheibe 1,
// AC-6/AC-7/AC-11/AC-13). Config-Muster 1:1 nach
// playwright.compare-outlook.staging.config.ts — dieselbe Bedienflaeche, nur
// im Trip-Kontext.
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
		{ name: 'setup', testMatch: /trip-outlook-metric-selection\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/trip-outlook-metric-selection\.staging\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-trip-outlook.json' }
		}
	]
});
