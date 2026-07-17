import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config für Epic #1273 Slice S2 (Compare-Hub: Name/Region/Aktivitätsprofil
// inline editierbar) gegen Staging. Kein lokaler webServer. Staging steht hinter
// nginx-Basic-Auth (Validator-Creds) + App-Login (GZ_AUTH_*). 1:1-Muster von
// playwright.1273-s1.red.config.ts.
//
// Liegt bewusst UNTER frontend/e2e/ (nicht frontend/ root): der RED-Phase
// Edit-Gate blockt Code-Dateien außerhalb der always_allowed_dirs (u.a. "e2e/").
// testDir '.' löst relativ zu dieser Datei auf, betrifft also nur frontend/e2e/.
// Eigener storageState-Pfad (staging-1273-s2.json) für Test-Isolation gegenüber S1.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /compare-hub-name-region-profil\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /compare-hub-name-region-profil\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1273-s2.json')
			}
		}
	]
});
