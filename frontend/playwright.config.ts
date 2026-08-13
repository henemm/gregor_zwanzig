import { defineConfig } from '@playwright/test';

// Issue #1284 Fix-Loop 5: der Default MUSS im selben Prozess gesetzt werden,
// der auch den webServer-Kindprozess (unten, `bash e2e/start-preview.sh`)
// spawnt -- ein `export` INNERHALB von start-preview.sh lebt nur in dessen
// eigenem Prozess und propagiert nicht zurück zu diesem Prozess, in dem
// e2e/global.setup.ts denselben Wert prüft (assertNotProdApiProxyTarget
// gegen process.env.GZ_API_BASE). Ohne diese Zeile hier sähen Guard-Check und
// tatsächlicher SvelteKit-Server unterschiedliche Werte. start-preview.sh
// behält denselben Default redundant für den Fall eines direkten Aufrufs
// ohne Playwright.
process.env.GZ_API_BASE ??= 'http://localhost:8091';

export default defineConfig({
	testDir: 'e2e',
	// #1329 Maßnahme B: Sicherheitsnetz-Räumlauf nach Suite-Ende (auch bei
	// Testfehlern/Abbrüchen) — löscht alle E2E-GZ--Präfix-Objekte.
	globalTeardown: './e2e/global.teardown.ts',
	timeout: 30_000,
	// #1771 Scheibe 2: workers: 1 in CI -- Tests teilen dieselbe Datenwurzel
	// und Seed-IDs (`e2e-loc-*`), Parallel-Laeufe wuerden sich stoeren.
	workers: process.env.CI ? 1 : undefined,
	retries: 0,
	use: {
		baseURL: 'http://localhost:4173',
		headless: true,
		// Diagnose im Runner; Artefakt nur bei Fehlschlag hochgeladen (ci.yml).
		trace: process.env.CI ? 'retain-on-failure' : 'off',
	},
	projects: [
		{
			name: 'setup',
			testMatch: /global\.setup\.ts/,
		},
		{
			name: 'tests',
			testIgnore: /global\.setup\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: 'playwright/.auth/admin.json',
			},
		},
	],
	webServer: {
		command: 'bash e2e/start-preview.sh',
		port: 4173,
		// CI-Runner ist pro Lauf frisch -- kein Alt-Prozess zum Wiederverwenden.
		reuseExistingServer: !process.env.CI,
		timeout: 120_000,
	},
});
