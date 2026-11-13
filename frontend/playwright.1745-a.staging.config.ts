import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Staging-Verifikation Issue #1745 Scheibe A (Premium-SMS als vierter
// Alarm-Kanal). Muster: playwright.1273-s4c.staging.config.ts (nginx-Basic-Auth =
// GZ_VALIDATOR_*, App-Login = GZ_AUTH_* via API + storageState).
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

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
