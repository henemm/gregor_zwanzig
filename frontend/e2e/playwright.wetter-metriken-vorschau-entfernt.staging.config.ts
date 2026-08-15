import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #1719 Scheibe 3, AC-1/AC-2 (Live-Vorschau "So kommt es
// an" ist ersatzlos entfernt) gegen Staging. Kein lokaler webServer. Staging
// steht hinter nginx-Basic-Auth (Validator-Creds) + App-Login (GZ_AUTH_*).
// Vorbild: playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts.
//
// Liegt bewusst UNTER frontend/e2e/ (nicht frontend/ root): der RED-Phase
// Edit-Gate blockt Code-Dateien außerhalb der always_allowed_dirs (u.a.
// "e2e/", s. openspec.yaml). testDir '.' löst relativ zu dieser Datei auf.
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
		{ name: 'setup', testMatch: /wetter-metriken-vorschau-entfernt\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /wetter-metriken-vorschau-entfernt\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1719-s3-vorschau.json')
			}
		}
	]
});
