import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config für issue_1080 (compare/new: Ort per URL hinzufügen bleibt unsichtbar +
// kein Benennen) gegen Staging. Kein lokaler webServer. Staging steht hinter
// nginx-Basic-Auth (Validator-Creds).
//
// Abweichung vom 953-Vorbild: liegt bewusst UNTER frontend/e2e/ statt frontend/ root,
// weil der RED-Phase Edit-Gate (edit_gate.py) Code-Dateien außerhalb der
// always_allowed_dirs (u.a. "e2e/") in Phase phase5_tdd_red blockt. testDir '.' löst
// relativ zu dieser Datei auf, betrifft also weiterhin nur frontend/e2e/*.spec.ts.
// storageState als absoluter __dirname-Pfad (s. issue-1080.staging.setup.ts) statt
// String-Literal — vermeidet Mehrdeutigkeit zwischen CWD- und Config-relativer Auflösung.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	// #1329 Maßnahme B: Sicherheitsnetz-Räumlauf nach Suite-Ende.
	globalTeardown: './global.teardown.ts',
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /issue-1080\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-1080-compare-new-url\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1080.json') }
		}
	]
});
