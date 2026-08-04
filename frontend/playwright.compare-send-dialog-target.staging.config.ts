import path from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
import { defineConfig } from '@playwright/test';
// Staging-Validierung Issue #1471. Analog playwright.staging.config.ts.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /compare-send-dialog-target\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /compare-send-dialog-target\.staging\.spec\.ts/, dependencies: ['setup'],
			dependencies: ['setup'],
			use: { storageState: path.join(__dirname, 'e2e', 'playwright', '.auth', 'staging-1471.json') },
		},
	],
});
