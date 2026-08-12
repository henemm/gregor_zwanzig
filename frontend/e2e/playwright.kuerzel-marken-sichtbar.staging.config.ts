import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #1719 Scheibe S4 (AC-5, AC-10..AC-14): die Kuerzel-Marken im
// Bereich "Reihenfolge" bleiben in 14 Fensterbreiten vollstaendig lesbar.
// Kein lokaler webServer — geprueft wird die auf Staging deployte App selbst.
// Staging steht hinter nginx-Basic-Auth (GZ_VALIDATOR_*) + App-Login (GZ_AUTH_*).
//
// Liegt bewusst UNTER frontend/e2e/ (nicht frontend/ root): das RED-Phasen-
// Edit-Gate laesst nur die Ordner test/tests/__tests__/spec/e2e zu.
// testDir '.' loest relativ zu dieser Datei auf.
//
// 14 Aufloesungen x 2 Flaechen sind ~28 Messlaeufe (Spec Risiko 7, bewusst in
// Kauf genommen) — deshalb ein grosszuegiges Zeitlimit je Test.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	timeout: 180_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /kuerzel-marken-sichtbar\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /kuerzel-marken-sichtbar\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1719-s4.json')
			}
		}
	]
});
