import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #1719 Scheibe 3 AC-10 (Persistenz-Fix) gegen Staging.
// Vorbild: playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts.
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
		{ name: 'setup', testMatch: /metrik-abwahl-schreibt-alle-kanaele-durch\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /metrik-abwahl-schreibt-alle-kanaele-durch\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1719-s3-alle-kanaele.json')
			}
		}
	]
});
