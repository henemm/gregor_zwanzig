import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1256 Scheibe 6 — Hub-Orte-Tab Drag/Entfernen/
// Add-Panel + eingebetteter CorridorEditor im Hub-Idealwerte-Tab (AC-14/15/
// 16/31/32/33/34). Config-Muster identisch zu playwright.1256-s2.staging.config.ts
// (nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login separat via geteiltem
// Setup-Projekt — kein neuer Auth-Layer nötig, gleiches Staging-Konto).
// Seit #2347 S3a trägt compare-hub-inline-edit nur noch den Orte-Teil
// (AC-14/15/31/32); der Idealwerte-Teil (AC-33/34, F002) liegt je kind in
// hub-wertebereiche-wertprops.spec.ts.
const user = process.env.GZ_VALIDATOR_USER!;
const pass = process.env.GZ_VALIDATOR_PASS!;

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /feat-1256-s2\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-hub-inline-edit\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1256-s2.json' }
		}
	]
});
