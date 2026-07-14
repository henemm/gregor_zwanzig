import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1234 — Auto-Save-Hydration-Gate im Inhalt-Tab
// (AC-1, AC-2, AC-3, AC-4, AC-6). nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login
// separat via Setup-Projekt (getrennte Layer, analog playwright.1256-s2).
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
		{ name: 'setup', testMatch: /feat-1234\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/weather-metrics-tab-autosave\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1234.json' }
		}
	]
});
