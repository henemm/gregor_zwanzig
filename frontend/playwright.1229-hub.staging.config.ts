import { defineConfig } from '@playwright/test';
// Staging-Validierung #1229 (Compare-Hub Briefing-Zeiten + Neutralisierung).
// nginx-Basic-Auth = GZ_VALIDATOR_*; App-Login erfolgt EINMAL ueber das
// bestehende Setup-Projekt feat-1231-s6.staging.setup.ts (spart die
// e2e-loc-*-Seed-Daten, die compare-hub-briefing-times.spec.ts als
// location_ids referenziert). Alle Spec-Projekte teilen sich den
// gespeicherten storageState statt sich pro Test einzeln einzuloggen —
// sonst erschoepft die Testsuite das Staging-Login-Rate-Limit (429).
// Muster 1:1 aus playwright.1231-s6.staging.config.ts uebernommen.
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
		{ name: 'setup', testMatch: /feat-1231-s6\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-hub-briefing-times\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1231-s6.json' }
		}
	]
});
