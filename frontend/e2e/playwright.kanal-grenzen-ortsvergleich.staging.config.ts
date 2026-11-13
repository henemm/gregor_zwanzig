import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ausUmgebung } from './stagingZugang';
// E2E-Config Issue #1719 Scheibe 3 AC-6 (Ortsvergleich: echte Zeichengrenze
// in Versand-Reiter/Alarme-Reiter/SMS-Vorschau) gegen Staging. Vorbild:
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
		{ name: 'setup', testMatch: /kanal-grenzen-ortsvergleich\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /kanal-grenzen-ortsvergleich\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1719-s3-ortsvergleich.json')
			}
		}
	]
});
