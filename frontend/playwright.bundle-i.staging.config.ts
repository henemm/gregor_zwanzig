import { defineConfig } from '@playwright/test';

// Dedizierte Staging-Config für Bündel I (#970/#971) — vereint die vier E2E-Specs,
// deren Selektoren nach dem v2-Redesign migriert/zurückgezogen wurden:
//   - issue-343-horizon-chips.spec.ts
//   - issue-690-custom-metrics-persist.spec.ts
//   - epic-138-block-b.spec.ts
//   - issue-776-metrics-toggle.spec.ts
//
// Staging steht hinter nginx-Basic-Auth (Validator-Creds) → httpCredentials.
// Einmaliger API-Login im setup-Projekt → storageState; Tests laufen
// vorauthentifiziert (vermeidet Auth-Rate-Limit bei parallelen Logins).
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
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /bundle-i\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /(issue-343-horizon-chips|issue-690-custom-metrics-persist|epic-138-block-b|issue-776-metrics-toggle)\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-bundle-i.json' }
		}
	]
});
