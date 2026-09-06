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
			// Bestandsstrecke (#2128 AC-16): seit es src/service-worker.ts gibt,
			// registriert SvelteKit auf JEDER Seite einen Worker -- auch im
			// Vorschaubetrieb. Fuer die Bestandspruefungen wird er abgeschaltet,
			// damit ihr Verhalten unveraendert bleibt.
			name: 'tests',
			testIgnore: [/global\.setup\.ts/, /pwa-.*\.spec\.ts/],
			dependencies: ['setup'],
			use: {
				storageState: 'playwright/.auth/admin.json',
				serviceWorkers: 'block',
			},
		},
		{
			// Nur die PWA-Nachweise laufen mit aktivem Worker (#2128).
			// `--project=pwa` waehlt in der CI OHNE Datei-Argumente aus (ci.yml,
			// Drittlauf) -- deshalb muss die Staging-Fassung hier ausdruecklich
			// heraus: pwa-nachweis.staging.spec.ts passt auf dasselbe Muster,
			// zielt aber auf https://staging.… (eigene Config, eigene Anmeldung)
			// und wuerde gegen den lokalen Vorschauserver zuverlaessig scheitern.
			name: 'pwa',
			testMatch: /pwa-.*\.spec\.ts/,
			testIgnore: /\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: 'playwright/.auth/admin.json',
				serviceWorkers: 'allow',
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
