import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #1703 Scheibe 8 (kanal-eigene Metrikauswahl der
// Vergleichs-Uebersicht) gegen Staging — EIN Setup fuer ALLE Buendel:
// die beiden Hub-Buendel (Bearbeiten-Pfad) und den Anlege-Pfad
// (compare-neu-kanal-anlegen: /compare/new, EIN POST statt PUT je Geste).
// Vorbild: playwright.metrik-abwahl-schreibt-alle-kanaele-durch.staging.config.ts.
// retries: 0 — die Klickpfade veraendern ihren eigenen Test-Vergleich; ein
// Wiederholungslauf traefe auf einen bereits editierten Stand.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	timeout: 120_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /compare-uebersicht-kanal\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: [
				/compare-uebersicht-kanal-(bedienung|persistenz)\.staging\.spec\.ts/,
				/compare-neu-kanal-anlegen\.staging\.spec\.ts/
			],
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1703-s8-kanal.json')
			}
		}
	]
});
