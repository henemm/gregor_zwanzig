import { defineConfig } from '@playwright/test';
import { assertNotProdBaseURL } from './e2e/prodUrlGuard.ts';
// Issue #2913 (Epic #2791) — Staging-Abgleich der Elementliste (AC-13 bis AC-15).
// Läuft NICHT im PR-CI (kein Eintrag in .github/workflows), sondern in /60-validate bzw. /e2e-verify
// und am Ende jeder Scheibe. Start bevorzugt über den Starter (CLI-Flags, Exit-Code):
//   cd frontend && npm run elementliste:abgleich -- [--strict] [--scope <reiter[/zustand]>] [--sprache en]
// Kein Setup-Projekt und keine Auth-Datei: die Spec meldet sich mit GZ_AUTH_USER/GZ_AUTH_PASS im
// Speicher an und am Ende wieder ab. nginx-Basic-Auth nur, wenn GZ_VALIDATOR_* gesetzt ist.
const baseURL = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
// Prod-Schutz schon beim Laden der Config: kein Projekt startet gegen Produktion.
assertNotProdBaseURL(baseURL);
const basicAuth =
	process.env.GZ_VALIDATOR_USER && process.env.GZ_VALIDATOR_PASS
		? { httpCredentials: { username: process.env.GZ_VALIDATOR_USER, password: process.env.GZ_VALIDATOR_PASS } }
		: {};

export default defineConfig({
	testDir: 'e2e',
	testMatch: /elementliste-abgleich\.staging\.spec\.ts/,
	timeout: 1_800_000,
	retries: 0,
	workers: 1,
	use: {
		baseURL,
		headless: true,
		locale: process.env.ELEMENTLISTE_SPRACHE === 'en' ? 'en-US' : 'de-DE',
		viewport: { width: 1280, height: 900 },
		ignoreHTTPSErrors: true,
		serviceWorkers: 'block',
		...basicAuth
	}
});
