import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #2794 S3a, Teil-PR 3 „Reiter Wetter": Staging-Lauf der Specs `s3a2794-teil3-*.spec.ts`
// (AC-9 bis AC-21, AC-38 bis AC-42) gegen https://staging.gregor20.henemm.com
// (nur /e2e-verify, nie gegen Produktion). Staging steht hinter nginx-Basic-Auth
// (Validator-Creds), Login ueber das Setup-Projekt von #1895. Analog playwright.2794-s3a2.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	retries: 0,
	// Fix-Loop 5: s3a2794-teil3-englisch.spec.ts switches the shared staging account to English;
	// in parallel the dialog spec would see English. Shared account with profile state => serial.
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		locale: 'de-DE',
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
		serviceWorkers: 'block'
	},
	projects: [
		{ name: 'setup', testMatch: /fix-1895-modus-rueckbau\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /s3a2794-teil3-[a-z-]+\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
