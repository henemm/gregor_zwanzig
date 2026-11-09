import { defineConfig } from '@playwright/test';
const FE = '/home/hem/gregor_zwanzig/.claude/worktrees/shimmering-doodling-ritchie/frontend';
export default defineConfig({
	testDir: FE + '/e2e',
	timeout: 120_000,
	retries: 0,
	workers: 2,
	use: {
		baseURL: 'https://staging.gregor20.henemm.com',
		headless: true,
		locale: 'de-DE',
		ignoreHTTPSErrors: true,
		httpCredentials: { username: process.env.GZ_VALIDATOR_USER ?? 'admin', password: process.env.GZ_VALIDATOR_PASS ?? 'test1234' },
		serviceWorkers: 'block'
	},
	projects: [
		{ name: 'setup', testMatch: /fix-1895-modus-rueckbau\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /s3a2794-hub-reiter-wetter-zustellung\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: FE + '/e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
