import { defineConfig } from '@playwright/test';
import { assertNotProdBaseURL } from './e2e/prodUrlGuard.ts';
// Issue #3440 (S5a): Staging-Lauf von `hub-send-menue.staging.spec.ts` gegen https://staging.gregor20.henemm.com
// (nur /e2e-verify bzw. /60-validate, nie gegen Produktion, nicht im PR-CI).
// Login mit dem Prüfkonto im Speicher (GZ_AUTH_USER/GZ_AUTH_PASS = GZ_PRUEFKONTO_USER/GZ_PRUEFKONTO_PASS aus der
// Staging-.env), Seed-IDs aus scripts/staging_pruefkonto_mockupdaten.py (ELEMENTLISTE_TRIP_ID, ELEMENTLISTE_ORTE_ID).
// nginx-Basic-Auth nur, wenn GZ_VALIDATOR_* gesetzt ist.
//   cd frontend && npx playwright test --config playwright.3440-test-menue.staging.config.ts
const baseURL = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
assertNotProdBaseURL(baseURL);
const basicAuth =
	process.env.GZ_VALIDATOR_USER && process.env.GZ_VALIDATOR_PASS
		? { httpCredentials: { username: process.env.GZ_VALIDATOR_USER, password: process.env.GZ_VALIDATOR_PASS } }
		: {};

export default defineConfig({
	testDir: 'e2e',
	testMatch: /hub-send-menue\.staging\.spec\.ts/,
	timeout: 180_000,
	retries: 0,
	workers: 1,
	use: {
		baseURL,
		headless: true,
		locale: 'de-DE',
		viewport: { width: 1280, height: 900 },
		ignoreHTTPSErrors: true,
		serviceWorkers: 'block',
		...basicAuth
	}
});
