import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #2400: vollständiger Dark Mode, Messlauf aller Routen auf Staging.
// Kein lokaler webServer — geprüft wird die auf Staging deployte App. Login-Setup und
// storageState werden vom Kürzel-Legende-Setup (#1888) mitbenutzt (gleiches Credential-Paar).
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
		{ name: 'setup', testMatch: /kuerzel-legende-lesbar\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /dark-mode-alle-routen\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1888-legende.json')
			}
		}
	]
});
