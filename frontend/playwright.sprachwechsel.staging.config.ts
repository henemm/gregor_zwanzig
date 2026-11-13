import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #2681 (i18n A2) — Staging-Lauf der F12-Spec e2e/sprachwechsel.spec.ts (AC-8).
// nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login (Helfer-Konto GZ_AUTH_*, holt das
// staging-token fuer die beiden Wegwerf-Konten) ueber das bestehende Setup-Projekt
// issue-661 — Muster playwright.staging.config.ts. Kontingent: die Spec registriert
// genau ZWEI Konten (5 je IP und Stunde).
//   cd frontend && npx playwright test --config playwright.sprachwechsel.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		// Epic #2644: ohne angemeldeten Nutzer folgt die Sprache dem Browser
		// (Accept-Language). Fall 1 erwartet fuer neue Besucher Deutsch, also Deutsch fest.
		locale: 'de-DE',
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
		serviceWorkers: 'block'
	},
	projects: [
		{ name: 'setup', testMatch: /issue-661\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /sprachwechsel\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-661.json' }
		}
	]
});
