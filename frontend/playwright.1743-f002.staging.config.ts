import { defineConfig } from '@playwright/test';
// Staging-Lauf der #1743-F002-Tests (Versand-Abschnitt bleibt nach Alt-Link im
// Blick) aus `hub-reiter-alt-kennungen-umleitung.spec.ts` gegen
// https://staging.gregor20.henemm.com. Die Spec arbeitet mit relativen URLs.
// Staging steht hinter nginx-Basic-Auth (Validator-Creds). Analog
// playwright.1895.staging.config.ts.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 90_000,
	retries: 0,
	workers: 2,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /fix-1895-modus-rueckbau\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /hub-reiter-alt-kennungen-umleitung\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' },
		},
	],
});
