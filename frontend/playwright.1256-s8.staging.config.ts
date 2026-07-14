import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1256 Scheibe 8 — Mobile-Vervollständigung
// Orts-Vergleich (AC-21 Chevron statt Kebab, AC-22 geteilter Hub mit
// 4-Stat-2×2-Monitoring, AC-23 Lifecycle-Bottom-Sheet, AC-24 Lock-Toast +
// floating CTA). Config-Muster identisch zu playwright.1256-s7.staging.config.ts
// (nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login separat via dediziertem
// Setup-Projekt — eigener storageState statt Login pro Testlauf,
// s. reference_staging_e2e_storagestate_login_rate_limit — 429-Rate-Limit).
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
		{ name: 'setup', testMatch: /feat-1256-s8\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-mobile-vervollstaendigung\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-1256-s8.json' }
		}
	]
});
