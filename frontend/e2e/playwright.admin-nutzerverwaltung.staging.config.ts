import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './stagingZugang';
// E2E-Config Issue #2155 S4: Admin-Seite `/admin` gegen Staging (Muster:
// playwright.konto-naechste-pruefung.staging.config.ts). Zwei Anmeldezustaende
// (Admin, Nicht-Admin) entstehen im Setup; die Spec oeffnet je Kontext den passenden.
// Kein lokaler webServer. Staging steht hinter nginx-Basic-Auth (GZ_VALIDATOR_*).
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: '.',
	timeout: 90_000,
	retries: 0,
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /admin-nutzerverwaltung\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /admin-nutzerverwaltung\.staging\.spec\.ts/,
			dependencies: ['setup']
		}
	]
});
