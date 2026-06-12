import { defineConfig } from '@playwright/test';
// RED/E2E-Config für Issue #758 gegen Staging (kein lokaler webServer,
// kein Produktions-Backend). Feature in der RED-Phase abwesend → Tests rot.
export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true
	},
	projects: [
		{ name: 'setup', testMatch: /issue-758\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-758-save-indicator\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-758.json' }
		}
	]
});
