// Mobile-UX-Audit (#2601) gegen den lokalen Preview-Server (localhost:4173).
//
// Drei Chromium-Profile (die Umgebung hat kein WebKit):
//   iphone13     — 390x844 @3x, Touch, isMobile
//   iphone18pro  — 402x874 @3x (Annahme: Viewport wie iPhone 17 Pro)
//   landscape    — 844x390 @3x (Querformat Smartphone)
//
// Voraussetzungen: ci-stack.sh start (freie Ports), start-preview.sh, Haupt-global.setup
// (playwright/.auth/admin.json) — siehe Spec docs/specs/modules/mobile_ux_audit_2601.md,
// Abschnitt „Laufanleitung".
// Aufruf (im frontend/-Verzeichnis):
//   GZ_E2E_API_PROXY_TARGET=http://localhost:8191 GZ_AUDIT_LOCALE=de \
//     npx playwright test --config=playwright.mobile-ux.local.config.ts
// Strenger Modus (harte Assertions statt Report): GZ_AUDIT_STRICT=1
// Sprache (#2601 Runde 2, AC-16): GZ_AUDIT_LOCALE=de|en setzt die Browser-Locale aller Profile;
// die Profilsprache des Seed-Nutzers setzt der Audit selbst und stellt sie danach wieder her.

import { defineConfig, devices } from '@playwright/test';

// Staging-Schutz (#2601 Runde 2, AC-16): ohne eigenes Proxy-Ziel zeigt der Vorschau-Proxy /api
// auf localhost:8091 = STAGING. Dann bricht die Config vor dem ersten Test ab.
const PROXY_TARGET = process.env.GZ_E2E_API_PROXY_TARGET;
if (!PROXY_TARGET) {
	throw new Error(
		'GZ_E2E_API_PROXY_TARGET fehlt: der Mobile-UX-Audit läuft nur gegen einen lokalen Stack ' +
			'(z. B. GZ_E2E_API_PROXY_TARGET=http://localhost:8191). Ohne die Variable zeigt der ' +
			'Vorschau-Proxy auf Staging (localhost:8091) — Lauf abgebrochen.'
	);
}
// Auch ein gesetztes Ziel darf nicht auf Staging oder Produktion zeigen (Adversary F002):
// Go 8091 = Staging, 8090 = Produktion; Python-Core 8001 = Staging, 8000 = Produktion;
// dazu jeder Host unter gregor20.henemm.com.
const VERBOTENE_PORTS = new Set(['8090', '8091', '8000', '8001']);
let zielUrl: URL;
try {
	zielUrl = new URL(PROXY_TARGET);
} catch {
	throw new Error(`GZ_E2E_API_PROXY_TARGET=${PROXY_TARGET} ist keine gültige URL — Mobile-UX-Audit abgebrochen.`);
}
const zielHost = zielUrl.hostname.toLowerCase();
const zielPort = zielUrl.port || (zielUrl.protocol === 'https:' ? '443' : '80');
if (zielHost === 'gregor20.henemm.com' || zielHost.endsWith('.gregor20.henemm.com') || VERBOTENE_PORTS.has(zielPort)) {
	throw new Error(
		`GZ_E2E_API_PROXY_TARGET=${PROXY_TARGET} zeigt auf Staging oder Produktion (Host *gregor20.henemm.com ` +
			'bzw. Port 8090/8091/8000/8001) — der Mobile-UX-Audit läuft nur gegen einen eigenen lokalen Stack ' +
			'auf freien Ports (z. B. http://localhost:8191). Lauf abgebrochen.'
	);
}
process.env.GZ_API_BASE ??= PROXY_TARGET;

const LOCALE = process.env.GZ_AUDIT_LOCALE === 'en' ? 'en-US' : 'de-DE';

const mobileBase = {
	defaultBrowserType: 'chromium' as const,
	isMobile: true,
	hasTouch: true,
	deviceScaleFactor: 3,
	userAgent: devices['iPhone 13'].userAgent,
	storageState: 'playwright/.auth/admin.json',
	serviceWorkers: 'block' as const,
	locale: LOCALE,
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
