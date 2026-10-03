// Mobile-Usability-Audit gegen Staging — Darstellungsprobleme finden
// (horizontaler Overflow, Mini-Fenster, zu kleine Texte), kein harter Gate.
//
// Zwei Projekte zum Vergleich Safari/WebKit vs. Chrome/Chromium-Rendering:
//   iphone13     — WebKit, echtes iPhone-13-Profil (Touch, isMobile, dsf 3)
//   chromium-390 — Chromium, 390x844, isMobile/hasTouch
//
// Remote-Ziel: KEIN webServer-Block. Auth wie in playwright.staging.config.ts:
// nginx-Basic-Auth via GZ_VALIDATOR_* (Fallback E2E_*), App-Login im Setup-
// Projekt via GZ_AUTH_* (storageState). Screenshots/Videos/Traces landen in
// test-results/mobile-usability/_pw-artifacts, Route-Screenshots + Report
// schreibt der Spec selbst nach test-results/mobile-usability/.

import { defineConfig, devices } from '@playwright/test';

const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
const storageState = 'playwright/.auth/staging-mobile-usability.json';

export default defineConfig({
	testDir: 'e2e',
	timeout: 300_000,
	retries: 0,
	workers: 1,
	outputDir: 'test-results/mobile-usability/_pw-artifacts',
	reporter: [['list']],
	use: {
		baseURL: 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
		serviceWorkers: 'allow',
		screenshot: 'on',
		video: 'on',
		trace: 'retain-on-failure',
	},
	projects: [
		{
			name: 'setup',
			testMatch: /mobile-usability\.staging\.setup\.ts/,
		},
		{
			name: 'iphone13',
			testMatch: /mobile-usability-audit\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				...devices['iPhone 13'],
				storageState,
			},
		},
		{
			name: 'chromium-390',
			testMatch: /mobile-usability-audit\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				defaultBrowserType: 'chromium',
				viewport: { width: 390, height: 844 },
				isMobile: true,
				hasTouch: true,
				deviceScaleFactor: 3,
				userAgent: devices['Pixel 5'].userAgent,
				storageState,
			},
		},
	],
});
