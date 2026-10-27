import { defineConfig } from '@playwright/test';
// Staging-Lauf der geratschten Spec `gewitter-absolutregel-gesperrt.spec.ts`
// (#1895 Schritt 1) gegen https://staging.gregor20.henemm.com. Die Spec selbst
// bleibt unveraendert — sie arbeitet ausschliesslich mit relativen URLs und ist
// darum ohne Anpassung gegen jede baseURL fahrbar.
// Staging steht hinter nginx-Basic-Auth (Validator-Creds). Analog
// playwright.staging.config.ts.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 0,
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
			testMatch: /gewitter-absolutregel-gesperrt\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'e2e/playwright/.auth/staging-1895.json' },
		},
	],
});
