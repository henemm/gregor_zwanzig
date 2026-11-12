import { defineConfig } from '@playwright/test';
// Issue #2794 S3a, Teil-PR 4b und Fix-Loop teil4b: Staging-Lauf von `s3a2794-teil4b-staging.spec.ts`
// (feat_2794_s3a_teil4_entfernen AC-32/33/34/48, fix_2794_s3a_teil4b_befunde AC-4/6/7/8) gegen https://staging.gregor20.henemm.com
// (nur /e2e-verify, nie gegen Produktion). Staging steht hinter nginx-Basic-Auth
// (Validator-Creds), Login ueber das Setup-Projekt von #1895. Analog playwright.2794-s3a2.staging.config.ts.
//   cd frontend && npx playwright test --config playwright.2794-s3a4b.staging.config.ts
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	retries: 0,
	// Fix-Loop 5: s3a2794-teil3-englisch.spec.ts switches the shared staging account to English;
	// in parallel the dialog spec would see English. Shared account with profile state => serial.
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
			testMatch: /s3a2794-teil4b-staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' }
		}
	]
});
