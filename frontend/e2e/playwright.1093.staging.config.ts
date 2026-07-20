import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config für issue_1093 (Compare Layout-Tab: LayoutPreview crasht bei echten Orten →
// "Lade Metriken-Katalog…" hängt) gegen Staging. Kein lokaler webServer. Staging steht
// hinter nginx-Basic-Auth (Validator-Creds). Vorbild: playwright.1080.staging.config.ts.
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
		{ name: 'setup', testMatch: /issue-1093\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /issue-1093-compare-layout-crash\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1093.json') }
		}
	]
});
