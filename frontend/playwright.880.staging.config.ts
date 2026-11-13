import { defineConfig } from '@playwright/test';
import { ausUmgebung } from './e2e/stagingZugang';
// E2E-/Charakterisierungs-Config für feat_880 (Autospeicher-Overlay) gegen Staging.
// Kein lokaler webServer. Staging steht hinter nginx-Basic-Auth (Validator-Creds).
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /feat-880\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /feat-880-autosave-overlay\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-880.json' }
		}
	]
});
