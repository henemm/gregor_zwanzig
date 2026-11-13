// E2E — Issue #2810: Anlege-Helfer `anlegenPflicht` sprachneutral (AC-1 bis AC-4).
// Spec: docs/specs/modules/fix_2810_anlegen_helfer_sprachneutral.md
// Konto-Sprache wird per PUT /api/auth/profile gesetzt und im Abbau auf `de` zurueckgestellt.
//
//   cd frontend && npx playwright test --config playwright.2810.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, createTestLocation } from './helpers';

const HANDY = { width: 375, height: 812 };
const SHEET_ZU = '[data-testid="sheet-close"]';

async function sprache(page: Page, lang: 'de' | 'en') {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

test.afterEach(async ({ page }) => {
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
});

for (const lang of ['en', 'de'] as const) {
	test(`AC-${lang === 'en' ? 1 : 2}: anlegenPflicht Vergleich mobil mit Konto ${lang} — Sheet am Ende geschlossen`, async ({ page }) => {
		test.setTimeout(90_000);
		await sprache(page, lang);
		await page.setViewportSize(HANDY);
		await anlegenPflicht(page, 'vergleich', { name: `E2E-GZ-2810-${lang}`, mobil: true });
		await expect(page.locator(SHEET_ZU)).toHaveCount(0);
		await expect(page.getByTestId('compare-step2-mobile-library-btn')).toBeVisible();
	});

	test(`AC-3: Schliessen-Knopf im Orte-Sheet (${lang}) traegt Kennung, Beschriftung uebersetzt, Klick schliesst`, async ({ page }) => {
		test.setTimeout(90_000);
		await sprache(page, lang);
		await page.setViewportSize(HANDY);
		await createTestLocation(page.request, { lat: 47.1, lon: 11.2 });
		await page.goto(ANLEGE_SEL.vergleich.url);
		await expect(page.getByTestId('compare-editor')).toBeVisible({ timeout: 15_000 });
		await ANLEGE_SEL.vergleich.name(page, true).fill(`E2E-GZ-2810-sheet-${lang}`);
		await ANLEGE_SEL.vergleich.reiter(page, 'orte', true).click();
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		const zu = page.locator(`${SHEET_ZU}:visible`);
		await expect(zu).toHaveCount(1);
		await expect(zu).toHaveAttribute('aria-label', lang === 'de' ? 'Schliessen' : 'Close');
		await zu.click();
		await expect(page.locator(SHEET_ZU)).toHaveCount(0);
	});
}

test('AC-4: anlegenPflicht Trip mobil mit Konto en — Etappen-Reiter ueber Kennung, GPX je Etappe', async ({ page }) => {
	test.setTimeout(90_000);
	await sprache(page, 'en');
	await page.setViewportSize(HANDY);
	await anlegenPflicht(page, 'route', { name: 'E2E-GZ-2810-trip-en', mobil: true });
});

test('Desktop-Pfad (en) bleibt unveraendert: Orte aus der Bibliothek, Sheet nicht beteiligt', async ({ page }) => {
	test.setTimeout(90_000);
	await sprache(page, 'en');
	await page.setViewportSize({ width: 1280, height: 900 });
	await anlegenPflicht(page, 'vergleich', { name: 'E2E-GZ-2810-desktop-en' });
	await expect(page.locator(SHEET_ZU)).toHaveCount(0);
});
