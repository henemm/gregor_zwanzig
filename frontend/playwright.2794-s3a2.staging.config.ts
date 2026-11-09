import { defineConfig } from '@playwright/test';
// Issue #2794 S3a, Teil-PR 2 „Leiste und Umleitung": Staging-Lauf der Spec
// `s3a2794-hub-reiter-wetter-zustellung.spec.ts` und `s3a2794-zustellung-inventar-speicherweg.spec.ts`
// (AC-7/AC-8, Fix-Loop 1) gegen https://staging.gregor20.henemm.com
// (nur /e2e-verify, nie gegen Produktion). Staging steht hinter nginx-Basic-Auth
// (Validator-Creds), Login ueber das Setup-Projekt von #1895. Analog playwright.1895.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.2794-s3a2.staging.config.ts
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	retries: 0,
	workers: 2,
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
			testMatch: /s3a2794-(hub-reiter-wetter-zustellung|zustellung-inventar-speicherweg)\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
