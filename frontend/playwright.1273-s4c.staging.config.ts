import { defineConfig } from '@playwright/test';
// Staging-Verifikation Epic #1273 Slice S4c — E2E-Migration Compare-Hub/Wizard.
// Deckt die migrierten Dateien ab, die keine eigene committete Staging-Config
// haben. Zwei Layer: nginx-Basic-Auth = GZ_VALIDATOR_* (httpCredentials),
// App-Login separat.
//
// Ein Testprojekt-Muster (Issue #1321): `chromium-storagestate` — alle
// migrierten Compare-Spec-Dateien nutzen die vom Setup-Projekt einmalig
// erzeugte App-Session (storageState), kein Pro-Test-UI-Login mehr. Das
// verhindert den Login-Rate-Limit-Kollaps bei wiederholten Staging-Läufen.
//
// Die Versand-Specs (vormals versand-tab-vergleich, compare-hub-briefing-times)
// sind seit #2347 S3b geteilte hub-versand-*-Specs auf der CI-Positivliste
// und daher hier NICHT gelistet.
const user = process.env.GZ_VALIDATOR_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 90_000,
	retries: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /f1-1273-s4c\.staging\.setup\.ts/ },
		{
			name: 'chromium-storagestate',
			testMatch: [
				/compare-editor-autosave\.spec\.ts/,
				/hub-editor-autosave-user-isolation\.spec\.ts/,
				/compare-radar-toggle\.spec\.ts/,
				/compare-alarm-config\.spec\.ts/,
				/compare-legacy-fields-survive-save\.spec\.ts/,
				/layout-tab-vergleich\.spec\.ts/,
				/issue-718-idealwert-validation\.spec\.ts/
			],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1273-s4c.json' }
		}
	]
});
