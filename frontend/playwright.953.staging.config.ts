import { defineConfig } from '@playwright/test';
// E2E-Config für issue_953 (Alerts-Empfindlichkeit über Tab-Wechsel) gegen Staging.
// Kein lokaler webServer. Staging steht hinter nginx-Basic-Auth (Validator-Creds).
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

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
		{ name: 'setup', testMatch: /issue-953\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-953-alerts-autosave-tabswitch\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-953.json' }
		}
	]
});
