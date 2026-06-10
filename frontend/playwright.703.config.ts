import { defineConfig } from '@playwright/test';

// Dedizierte Staging-Config für Issue #703 (Login Rate-Limit IP-Weitergabe).
// Testet das Login-Formular selbst — kein pre-auth Setup nötig.
export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
	},
	projects: [
		{
			name: 'tests',
			testMatch: /bug-703-login-ratelimit\.spec\.ts/,
		},
	],
});
