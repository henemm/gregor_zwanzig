import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1269 — Speicher-Status-Anzeige lügt (Trip +
// Ortsvergleich, AC-1..AC-4). nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login
// separat via Setup-Projekt (getrennte Layer, analog playwright.1234.staging).
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
		{ name: 'setup', testMatch: /feat-1269-save-status-lie\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/save-status-indicator-honesty\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1269.json' }
		}
	]
});
