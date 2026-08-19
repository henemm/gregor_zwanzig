import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #1727 S5e (AC-4, AC-7): die Konto-Seite beschriftet den
// Scheduler-Tick als "Nächste Prüfung" und zeigt ihn in der Zone des Browsers.
// Kein lokaler webServer — geprueft wird die auf Staging deployte App selbst.
// Staging steht hinter nginx-Basic-Auth (GZ_VALIDATOR_*) + App-Login (GZ_AUTH_*).
//
// Liegt bewusst UNTER frontend/e2e/ (nicht frontend/ root): das RED-Phasen-
// Edit-Gate laesst nur die Ordner test/tests/__tests__/spec/e2e zu.
// testDir '.' loest relativ zu dieser Datei auf.
//
// Die Zeitzonen werden NICHT hier gesetzt, sondern je Browser-Kontext im Test
// (`browser.newContext({ timezoneId })`) — beide Zonen gehoeren in denselben
// Testlauf, damit der Vergleich beider Anzeigen eine einzige Zusicherung ist.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	timeout: 90_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /konto-naechste-pruefung\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /konto-naechste-pruefung\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1727-s5e.json')
			}
		}
	]
});
