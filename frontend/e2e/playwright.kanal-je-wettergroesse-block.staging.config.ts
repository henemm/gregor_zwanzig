import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config Issue #1895 S3b1 (Block „Kanäle je Wettergröße", AC-52/55/58/62)
// gegen Staging. Vorbild: playwright.compare-uebersicht-kanal.staging.config.ts.
// retries: 0 — die Klickpfade verändern ihre eigenen Test-Objekte; ein
// Wiederholungslauf träfe auf einen bereits editierten Stand.
// Sprache: GZ_LANG=de|en (Standard de), gesetzt als Cookie gz_lang in der Spec.
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
	testDir: '.',
	timeout: 180_000,
	retries: 0,
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: process.env.GZ_VALIDATOR_USER ?? '', password: process.env.GZ_VALIDATOR_PASS ?? '' }
	},
	projects: [
		{ name: 'setup', testMatch: /kanal-je-wettergroesse-block\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /kanal-je-wettergroesse-block\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1895-s3b1-kanal-block.json')
			}
		}
	]
});
