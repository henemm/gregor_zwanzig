import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ausUmgebung } from './stagingZugang';
// E2E-Config Issue #1719 Scheibe 3, AC-3/AC-4/AC-8 (echte Platzgrenzen im
// Trip-Editor: Telegram-Kapplinie nach 7, SMS-Zeichengrenze 160, global
// abgewählte Metrik nirgends im Kanal-Reiter) gegen Staging. Vorbild:
// playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

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
		{ name: 'setup', testMatch: /kanal-grenzen-und-hinweise\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /kanal-grenzen-und-hinweise\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1719-s3-grenzen.json')
			}
		}
	]
});
