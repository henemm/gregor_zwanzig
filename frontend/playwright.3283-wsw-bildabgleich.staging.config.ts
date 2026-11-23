import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #3283 (Karte „Was steht wo“, Optik-Befunde der Bildprüfung): Abnahme-Lauf (Spec
// fix_3283_was_steht_wo_optik.md, AC-7/AC-10) gegen https://staging.gregor20.henemm.com — nur /e2e-verify,
// nie gegen Produktion, nicht in der CI-Positivliste. Staging steht hinter nginx-Basic-Auth (Validator-Creds),
// Login über das Setup-Projekt von #1895. Analog playwright.2980-c2-bildabgleich.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.3283-wsw-bildabgleich.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 300_000,
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
			testMatch: /was-steht-wo-bildabgleich\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
