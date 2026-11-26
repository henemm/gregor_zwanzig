import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// Issue #3037 (Abschlussabnahme Tabelle „Was steht wo“, Spec feat_3037_was_steht_wo_abnahme.md, AC-1–AC-4, AC-9):
// Lauf gegen https://staging.gregor20.henemm.com — nur /e2e-verify, nie gegen Produktion, nicht in der
// CI-Positivliste. Staging steht hinter nginx-Basic-Auth (Validator-Creds). Anders als #3283 KEIN Setup-Projekt
// aus #1895 und KEIN storageState: die Spec meldet das Prüfkonto selbst per /api/auth/login an
// (GZ_AUTH_USER/GZ_AUTH_PASS), damit die Seed-IDs (ELEMENTLISTE_TRIP_ID/ELEMENTLISTE_ORTE_ID) passen.
//   cd frontend && ABNAHME_KONTEXTE=orte,ort1 npx playwright test --config playwright.3037-wsw-abnahme.staging.config.ts
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	testMatch: /wsw-abnahme-3037\.staging\.spec\.ts/,
	timeout: 600_000,
	retries: 0,
	// Geteiltes Prüfkonto mit Profilzustand (Sprache wird umgeschaltet) => seriell.
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		locale: 'de-DE',
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
		serviceWorkers: 'block'
	}
});
