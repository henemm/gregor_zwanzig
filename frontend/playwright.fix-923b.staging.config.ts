import { defineConfig } from '@playwright/test';
// Staging-Verifikation Fix #923b — SMS-Fidelity-Vorschau live anschliessen.
// Config-Muster identisch zu playwright.compare-outlook.staging.config.ts.
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
		{ name: 'setup', testMatch: /fix-923b-wire-live-sms-preview\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/fix-923b-wire-live-sms-preview\.staging\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-923b.json' }
		}
	]
});
