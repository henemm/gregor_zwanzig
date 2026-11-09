import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #2371 (AC-1/2/3/5): Kontrastmessung der Anlege-Editoren und des Archivs.
// Kein lokaler webServer — geprueft wird die auf Staging deployte App selbst. Login-Setup und
// storageState werden vom Kuerzel-Legende-Setup (#1888) mitbenutzt (gleiches Credential-Paar).
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
		{ name: 'setup', testMatch: /kuerzel-legende-lesbar\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /ink4-kontrast\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1888-legende.json')
			}
		}
	]
});
