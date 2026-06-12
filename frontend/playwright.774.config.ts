import { defineConfig } from '@playwright/test';

// Dedizierte Staging-Config für Issue #774 (Metriken-Überblick Checkbox-Persistenz).
// Einmaliger API-Login im setup-Projekt → storageState; Tests laufen
// vorauthentifiziert (vermeidet Auth-Rate-Limit bei parallelen Logins).
export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
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
