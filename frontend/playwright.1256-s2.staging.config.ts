import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1256 Scheibe 2 — Fluss-Verdrahtung Klickpfad
// (Kachel→Detail, Create-Aktivieren→Detail-Redirect, Create-Abbrechen→Liste,
// Hub-Zurück→Liste, AC-25–AC-29). nginx-Basic-Auth = GZ_VALIDATOR_*,
// App-Login separat via Setup-Projekt (getrennte Layer, analog feat-1231-s6).
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
		{ name: 'setup', testMatch: /feat-1256-s2\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-flow-navigation\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1256-s2.json' }
		}
	]
});
