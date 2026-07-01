import { defineConfig } from '@playwright/test';

const GZ_USER = process.env.GZ_VALIDATOR_USER ?? 'validator-issue110';
const GZ_PASS = process.env.GZ_VALIDATOR_PASS ?? '';
const basicAuth = Buffer.from(`${GZ_USER}:${GZ_PASS}`).toString('base64');

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		extraHTTPHeaders: { Authorization: `Basic ${basicAuth}` }
	},
	projects: [
		{ name: 'setup', testMatch: /issue-946\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-946-alerts-tab\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-946.json' }
		}
	]
});
