import { defineConfig } from '@playwright/test';
// E2E-Config Issue #2422 Scheibe S3 (AC-26: "Abend aktiv" abgehakt => auf
// Staging kommt kein Abend-Briefing an) gegen Staging.
//
// Eigene Config statt Aufnahme in .github/ci_e2e_specs.txt: Filter A dort
// schliesst `.staging.spec.ts`-Dateien strukturell aus (die CI-Positivliste
// laeuft gegen den isolierten LOKALEN Stack, nicht gegen Staging).
//
// KEIN Setup-Projekt / keine storageState-Datei: die Spec registriert einen
// eigenen, frischen Wegwerf-Nutzer (genau ein Trip) und meldet ihn selbst an --
// ein vorhandenes Konto (admin, Validator-Nutzer) haette weitere Trips, und der
// ausgeloeste Sammellauf waere dann ein echter Mehr-Trip-Versand.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	// Der Lauf ist synchron (Wetterabruf + Renderer + SMTP) und der Go-Proxy
	// wartet bis zu 120 s -- Testzeit darueber.
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
			testMatch: /kanal-an-aus-kette\.staging\.spec\.ts/
		}
	]
});
