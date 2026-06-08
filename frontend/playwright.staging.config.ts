import { defineConfig } from '@playwright/test';
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
		{ name: 'setup', testMatch: /issue-661\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-661-trip-new-mobile\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-661.json' },
		},
	],
});
