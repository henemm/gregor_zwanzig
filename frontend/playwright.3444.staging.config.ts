import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #3444 (ADR-0130): Staging-Abnahme des gemeinsamen Katalogtexts kind_required (AC-1, de und en)
// gegen https://staging.gregor20.henemm.com (nur /e2e-verify, nie gegen Produktion). Staging steht
// hinter nginx-Basic-Auth (Validator-Creds), Login ueber das Setup-Projekt von #1895.
// Analog playwright.2810.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.3444.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	retries: 0,
	// Der en-Test schaltet die Kontosprache des geteilten Staging-Kontos um => seriell.
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
			testMatch: /kind-required-3444\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
