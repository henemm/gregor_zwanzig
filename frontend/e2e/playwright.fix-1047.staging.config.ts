import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './stagingZugang';

// Wegwerf-Staging-Config für den RED-Nachweis von Fix #1047 (Mail-Inhalt-Karte im
// Wetter-Metriken-Reiter). Wird nach Implementierung/Deploy wieder entfernt — kein
// dauerhaftes Repo-Artefakt. Setup-Projekt wiederverwendet aus Bündel I.
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

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
		{ name: 'setup', testMatch: /bundle-i\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /(issue-619-mail-elements-ui|issue-723-email-tab-eindampfen)\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-bundle-i.json' }
		}
	]
});
