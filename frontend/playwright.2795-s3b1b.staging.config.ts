import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #2795 S3b, Teilschritt 1b „Reiter Zustellung": Staging-Lauf der Specs
// `s3b2795-zustellung-*.spec.ts` gegen https://staging.gregor20.henemm.com (nur /e2e-verify,
// nie gegen Produktion). Staging steht hinter nginx-Basic-Auth (Validator-Creds), Login ueber das
// Setup-Projekt von #1895. Analog playwright.2794-s3a3.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	retries: 0,
	// s3b2795-zustellung-englisch.spec.ts schaltet das geteilte Staging-Konto auf Englisch;
	// parallel saehen die anderen Specs englische Texte. Geteiltes Konto mit Profilzustand => seriell.
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
			testMatch: /s3b2795-zustellung-[a-z-]+\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
