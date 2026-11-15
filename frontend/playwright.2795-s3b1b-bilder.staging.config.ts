import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #2795 S3b Teilschritt 1b (Reiter „Zustellung“): Soll/Ist-Aufnahmen und Textlisten für AC-38
// (Spec feat_2795_s3b_teil1_zustellung.md) gegen https://staging.gregor20.henemm.com — nur /e2e-verify,
// nie gegen Produktion, nicht in der CI-Positivliste. Basic-Auth (Validator-Creds), Login über das
// Setup-Projekt von #1895. Vorlage: playwright.2980-c2-bildabgleich.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.2795-s3b1b-bilder.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 600_000,
	retries: 0,
	// Gemeinsames Staging-Konto mit Profilzustand (Sprache wird umgeschaltet) => seriell.
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
			testMatch: /s3b2795-zustellung-bilder\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
