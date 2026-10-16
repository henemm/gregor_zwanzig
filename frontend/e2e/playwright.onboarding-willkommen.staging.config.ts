import { defineConfig } from '@playwright/test';
// E2E-Config Onboarding S2 (Spec docs/specs/modules/onboarding_willkommen_checkliste.md,
// AC-2/3/8/16/17) gegen Staging. Muster playwright.kanal-an-aus-kette.staging.config.ts.
//
// Eigene Config statt Aufnahme in .github/ci_e2e_specs.txt: Filter A dort
// schliesst `.staging.spec.ts` aus (die CI-Positivliste laeuft lokal).
//
// KEIN Setup-Projekt: die Spec registriert einen frischen Wegwerf-Nutzer
// (`gregor-test+<nutzer>@henemm.com`), denn nur ein NEU angelegtes Konto traegt
// das Merkmal `onboarding_pending`; das Altkonto ist das Bestandskonto GZ_AUTH_USER.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	// Testmail-Zustellung per IMAP wird bis zu 3 Minuten abgefragt.
	timeout: 300_000,
	retries: 0,
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{
			name: 'tests',
			testMatch: /onboarding-willkommen\.staging\.spec\.ts/
		}
	]
});
