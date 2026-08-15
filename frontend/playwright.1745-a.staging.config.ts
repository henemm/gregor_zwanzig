import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1745 Scheibe A (Premium-SMS als vierter
// Alarm-Kanal). Muster: playwright.1461-s3b2b.staging.config.ts (nginx-Basic-Auth =
// GZ_VALIDATOR_*, App-Login = GZ_AUTH_* via API + storageState).
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
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /feat-1745-a\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /feat-1745-a.*\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1745-a.json' },
		},
	],
});
