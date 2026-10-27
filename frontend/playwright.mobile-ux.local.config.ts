// Mobile-UX-Audit (#2601) gegen den lokalen Preview-Server (localhost:4173).
//
// Drei Chromium-Profile (die Umgebung hat kein WebKit):
//   iphone13     — 390x844 @3x, Touch, isMobile
//   iphone18pro  — 402x874 @3x (Annahme: Viewport wie iPhone 17 Pro)
//   landscape    — 844x390 @3x (Querformat Smartphone)
//
// Voraussetzungen: ci-stack.sh start, start-preview.sh, Haupt-global.setup
// (playwright/.auth/admin.json) — siehe docs im Spec-Kopf.
// Aufruf (im frontend/-Verzeichnis):
//   npx playwright test --config=playwright.mobile-ux.local.config.ts
// Strenger Modus (harte Assertions statt Report): GZ_AUDIT_STRICT=1

import { defineConfig, devices } from '@playwright/test';

process.env.GZ_API_BASE ??= 'http://localhost:8091';

const mobileBase = {
	defaultBrowserType: 'chromium' as const,
	isMobile: true,
	hasTouch: true,
	deviceScaleFactor: 3,
	userAgent: devices['iPhone 13'].userAgent,
	storageState: 'playwright/.auth/admin.json',
	serviceWorkers: 'block' as const,
};

export default defineConfig({
	testDir: 'e2e',
	testMatch: /mobile-ux-audit\.spec\.ts/,
	timeout: 600_000,
	retries: 0,
	workers: 1,
	outputDir: 'test-results/mobile-ux/_pw-artifacts',
	reporter: [['list']],
	use: {
		baseURL: 'http://localhost:4173',
		headless: true,
		screenshot: 'off',
		trace: 'off',
	},
	projects: [
		{ name: 'iphone13', use: { ...mobileBase, viewport: { width: 390, height: 844 } } },
		{ name: 'iphone18pro', use: { ...mobileBase, viewport: { width: 402, height: 874 } } },
		{ name: 'landscape', use: { ...mobileBase, viewport: { width: 844, height: 390 } } },
	],
});
