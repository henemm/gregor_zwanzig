import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Validierung Issue #1350 Teil 3 (Schwellen-Editor des Ortsvergleichs
// bezieht seine CompareMetricDef-Objekte aus GET /api/compare/metrics statt
// aus dem statischen Frontend-Import compareMetricDefs.ts::ALL_METRICS). Kein
// lokaler webServer, gegen Staging hinter nginx-Basic-Auth (Validator-Creds).
// Wiederverwendet den bereits gueltigen App-Login-storageState aus Issue
// #1332 (kein neuer Login-Request, Rate-Limit-Bucket #703) — analog
// playwright.fix-1350.staging.config.ts (Teil 2).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nginxUser = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const nginxPass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	globalTeardown: './global.teardown.ts',
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: nginxUser, password: nginxPass }
	},
	projects: [
		{
			name: 'tests',
			testMatch: /fix-1350t3-compare-threshold-source\.staging\.spec\.ts/,
			use: { storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1332.json') }
		}
	]
});
