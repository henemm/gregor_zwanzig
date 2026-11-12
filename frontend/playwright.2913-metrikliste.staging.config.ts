import { defineConfig } from '@playwright/test';
// Issue #2913, Fix „Metrik-Liste nach Mockup“: Abnahme-Lauf (AC-1 bis AC-13) gegen
// https://staging.gregor20.henemm.com — nur /e2e-verify, nie gegen Produktion, nicht in der CI-Positivliste.
// Staging steht hinter nginx-Basic-Auth (Validator-Creds), Login über das Setup-Projekt von #1895.
// Analog playwright.2794-s3a3.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.2913-metrikliste.staging.config.ts
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 300_000,
	retries: 0,
	// Gemeinsames Staging-Konto mit Profilzustand (Sprache wird umgeschaltet) => seriell.
	workers: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		locale: 'de-DE',
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
		serviceWorkers: 'block'
	},
	projects: [
		{ name: 'setup', testMatch: /fix-1895-modus-rueckbau\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /fix2913-metrikliste-mockup\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
