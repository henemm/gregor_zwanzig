import { defineConfig } from '@playwright/test';

// Dedizierte Staging-Config für Issue #675 (Startzeiten je Etappe).
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
		{ name: 'setup', testMatch: /issue-675\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-675-stage-start-time\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-675.json' },
		},
	],
});
