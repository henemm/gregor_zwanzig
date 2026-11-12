import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './stagingZugang';

// Wegwerf-Staging-Config für den RED/GREEN-Nachweis von Issue #1059 (Fortsetzen-Button
// ohne Fehler-Feedback). Analog e2e/playwright.fix-1047.staging.config.ts — liegt bewusst
// unter e2e/, damit strict_code_gate ihn wie eine Testdatei behandelt.
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: '.',
	// #1329 Maßnahme B: Sicherheitsnetz-Räumlauf nach Suite-Ende.
	globalTeardown: './global.teardown.ts',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /issue-1059\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-1059-trip-resume-error-feedback\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1059.json' }
		}
	]
});
