import { defineConfig } from '@playwright/test';
// Staging-Verifikation Issue #1373 S2 Scheibe B (Speicherformat der
// Metrik-Auswahl: Größe + Auswertung). Config-Muster identisch zu
// playwright.compare-metric-order.staging.config.ts: nginx-Basic-Auth =
// GZ_VALIDATOR_*, App-Login separat über ein dediziertes Setup-Projekt (eigener
// storageState statt Login pro Testlauf, s.
// reference_staging_e2e_storagestate_login_rate_limit — 429-Rate-Limit).
// Kein `webServer`-Block: getestet wird die auf Staging deployte App selbst.

// GZ_API_BASE wird hier EXPLIZIT gesetzt (Staging-Go, Port 8091). Ohne
// webServer-Block wirkt der Wert in diesem Lauf nicht — aber der Vorgabewert in
// playwright.config.ts zeigt auf einen Prod-nahen Pfad, und ein leerer/erbter
// Wert soll niemals versehentlich Richtung Produktion zeigen
// (reference_e2e_apibase_default_is_prod). Zusätzlich sperrt
// `assertNotProdBaseURL` im Setup jeden Lauf gegen die Prod-Domain (#1265).
process.env.GZ_API_BASE ??= 'http://localhost:8091';

const user = process.env.GZ_VALIDATOR_USER!;
const pass = process.env.GZ_VALIDATOR_PASS!;

export default defineConfig({
	testDir: 'e2e',
	timeout: 90_000,
	retries: 1,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /compare-active-metrics-format\.staging\.setup\.ts/ },
		{
			name: 'chromium',
			testMatch: [/compare-active-metrics-format\.staging\.spec\.ts/],
			dependencies: ['setup'],
			use: { storageState: 'playwright/.auth/staging-compare-active-metrics-format.json' }
		}
	]
});
