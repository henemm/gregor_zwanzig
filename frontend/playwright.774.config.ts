import { defineConfig } from '@playwright/test';

// Dedizierte Staging-Config für Issue #774 (Metriken-Überblick Checkbox-Persistenz).
// Einmaliger API-Login im setup-Projekt → storageState; Tests laufen
// vorauthentifiziert (vermeidet Auth-Rate-Limit bei parallelen Logins).
// Staging steht hinter nginx-Basic-Auth (Validator-Creds) → httpCredentials.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /issue-774\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-774-metrics-summary-persist\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-774.json' },
		},
	],
});
