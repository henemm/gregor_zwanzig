import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

/**
 * Issue #2270 — AC-12: eigene Karte „Deine Daten" auf der Konto-Seite, VOR der
 * Gefahrenzone, mit einem Knopf, der den Download wirklich ausloest.
 *
 * Warum nicht `toBeVisible()`: sichtbar sagt nichts ueber die Reihenfolge und
 * nichts darueber, ob der Knopf etwas bewirkt. Gemessen werden deshalb beide
 * Zusicherungen an ihrer Wirkstelle — die Dokumentreihenfolge ueber
 * compareDocumentPosition (kein Index-Rechnen, das beim Einfuegen einer
 * weiteren Karte still kippt) und das tatsaechlich ausgeloeste Download-
 * Ereignis.
 */
test.describe('Issue #2270 Datenexport auf /account', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/account');
	});

	test('Export-Karte steht in der Seitenreihenfolge vor der Gefahrenzone', async ({ page }) => {
		const exportKarte = page.locator('[data-testid="data-export-card"]');
		const gefahrenzone = page.locator('[data-testid="danger-zone-card"]');
		await expect(exportKarte).toBeVisible();
		await expect(gefahrenzone).toBeVisible();

		// Node.DOCUMENT_POSITION_FOLLOWING (4): b folgt a im Dokument.
		const exportKommtZuerst = await page.evaluate(() => {
			const a = document.querySelector('[data-testid="data-export-card"]');
			const b = document.querySelector('[data-testid="danger-zone-card"]');
			if (!a || !b) return null;
			return (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
		});
		expect(exportKommtZuerst).toBe(true);

		// Die Karte ist eigenstaendig und liegt NICHT in der Gefahrenzone.
		expect(await gefahrenzone.locator('[data-testid="data-export-card"]').count()).toBe(0);
	});

	test('Klick auf den Export-Knopf loest den Download des Archivs aus', async ({ page }) => {
		const downloadVersprechen = page.waitForEvent('download', { timeout: 30_000 });
		await page.locator('[data-testid="data-export-button"]').click();
		const download = await downloadVersprechen;
		expect(download.suggestedFilename()).toMatch(/\.zip$/);
		await expect(page.locator('[data-testid="data-export-error"]')).toHaveCount(0);
	});
});
