import { defineConfig } from '@playwright/test';
// Staging-Re-Verifikation D2 von Epic #1301 (Amtliche-Warnungen-Schalter,
// Fix-Loop 2, AC-6, Commit 63c1fc95). Config-Muster identisch zu
// playwright.1301-c2.staging.config.ts.
const user = process.env.GZ_VALIDATOR_USER!;
const pass = process.env.GZ_VALIDATOR_PASS!;

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
		{ name: 'setup', testMatch: /d2-1301-official-alerts\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/d2-1301-official-alerts-single-control\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1301-d2.json' }
		}
	]
});
