// Lokaler Mobile-Usability-Audit gegen den Preview-Server (localhost:4173) —
// Nachweis-Lauf für Fix-Pakete (Ist-Stand: report-iphone13.json aus Staging).
//
// Voraussetzungen:
//   - Preview läuft (bash e2e/start-preview.sh bzw. Haupt-Playwright-Config)
//   - Auth: playwright/.auth/admin.json (Haupt-global.setup) + via Env-Override
//     im Audit-Spec: GZ_AUDIT_BASE=http://localhost:4173,
//     GZ_AUDIT_STORAGE=playwright/.auth/admin.json
//   - Test-Trip 'ma-alpen-x' per API geseedet (siehe Doku im Commit)
//
// Aufruf (im frontend/-Verzeichnis):
//   GZ_AUDIT_BASE=http://localhost:4173 \
//   GZ_AUDIT_STORAGE=playwright/.auth/admin.json \
//   npx playwright test --config=playwright.mobile-usability.local.config.ts

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: 'e2e',
	timeout: 300_000,
	retries: 0,
	workers: 1,
	outputDir: 'test-results/mobile-usability/_pw-artifacts',
	reporter: [['list']],
	use: {
		baseURL: 'http://localhost:4173',
		headless: true,
		serviceWorkers: 'allow',
		screenshot: 'on',
	},
	projects: [
		{
			name: 'chromium-390',
			testMatch: /mobile-usability-audit\.spec\.ts/,
			use: {
				defaultBrowserType: 'chromium',
				viewport: { width: 390, height: 844 },
				isMobile: true,
				hasTouch: true,
				deviceScaleFactor: 3,
				userAgent: devices['Pixel 5'].userAgent,
				storageState: 'playwright/.auth/admin.json',
			},
		},
	],
});
