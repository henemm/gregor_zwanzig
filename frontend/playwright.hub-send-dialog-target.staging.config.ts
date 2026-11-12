import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Staging-Validierung Issue #2347 S2 (vormals #1471, umbenannt aus der früheren
// Compare-only-Config). Analog playwright.staging.config.ts.
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /hub-send-dialog-target\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /hub-send-dialog-target\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: fileURLToPath(new URL('./e2e/playwright/.auth/staging-1471.json', import.meta.url)),
			},
		},
	],
});
