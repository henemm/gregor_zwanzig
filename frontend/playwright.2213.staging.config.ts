import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Staging-Lauf der Spec `etappen-bauliche-aenderung-speichert.spec.ts` (#2213)
// gegen https://staging.gregor20.henemm.com. Die Spec arbeitet mit relativen URLs
// und legt ihren Test-Trip selbst an und raeumt ihn wieder ab.
// Staging steht hinter nginx-Basic-Auth (Validator-Creds). Analog
// playwright.1895.staging.config.ts.
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 0,
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /fix-2213-bauliche-aenderung\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /etappen-bauliche-aenderung-speichert\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-2213.json' },
		},
	],
});
