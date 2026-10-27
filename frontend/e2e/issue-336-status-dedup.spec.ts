import { test, expect } from '@playwright/test';

/**
 * Issue #336 — Doppelte Status-Anzeige im Trip-Kopf bereinigen.
 * Spec: docs/specs/modules/issue_336_status_dedup.md
 *
 * RED: Der Trip-Kopf rendert Status doppelt — Versalien-Präfix "AKTIV" (in
 *      `.status-text`, ohne Testid) + Pill "Aktiv". Es gibt noch keinen
 *      `trip-detail-status-supplement`-Span → AC-1/AC-4 schlagen fehl, das
 *      "AKTIV"-Präfix ist vorhanden → AC-2 schlägt fehl.
 * GRÜN: Präfix entfernt, `daysLabel` im getesteten Supplement-Span (gedämpft),
 *       Pill bleibt alleinige Statusdarstellung.
 *
 * Voraussetzung: Test-Trip `e2e-cockpit-test` (aktiv, Stages gestern/heute/morgen)
 * aus global.setup.ts.
 */

const ACTIVE_TRIP_ID = 'e2e-cockpit-test';
const PAUSED_TRIP_ID = 'e2e-336-paused';

test.describe('Issue #336 — Status-Dedup im Trip-Kopf', () => {
	test.use({ storageState: 'playwright/.auth/admin.json' });

	// AC-1: Zusatztext lebt im getesteten Supplement-Span, ohne Versalien-Präfix.
	test('AC-1: Supplement zeigt Zusatz ("läuft seit") ohne "AKTIV"-Präfix', async ({ page }) => {
		/**
		 * GIVEN: aktive Trip wird geöffnet
		 * WHEN: die Status-Zeile gerendert wird
		 * THEN: [data-testid="trip-detail-status-supplement"] enthält den Zusatz
		 *       und NICHT das Versalien-Präfix "AKTIV"
		 */
		await page.goto(`/trips/${ACTIVE_TRIP_ID}`);
		const supplement = page.getByTestId('trip-detail-status-supplement');
		await expect(supplement).toBeVisible();
		await expect(supplement).toContainText('läuft seit');
		await expect(supplement).not.toContainText('AKTIV');
	});

	// AC-2: Status erscheint genau einmal — Pill bleibt, Versalien-Präfix ist weg.
	test('AC-2: Pill zeigt "Aktiv", Trip-Kopf enthält kein "AKTIV"-Präfix mehr', async ({ page }) => {
		/**
		 * GIVEN: aktive Trip wird geöffnet
		 * WHEN: der Trip-Kopf gerendert wird
		 * THEN: Pill `trip-detail-status-badge` enthält "Aktiv", und im Kopf
		 *       taucht das Versalien-Präfix "AKTIV" nicht mehr auf
		 */
		await page.goto(`/trips/${ACTIVE_TRIP_ID}`);
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText('Aktiv');

		// Versalien-Präfix darf nirgends im Trip-Kopf mehr stehen (Dedup).
		const header = page.locator('header.trip-header');
		await expect(header).not.toContainText('AKTIV');
	});

	// AC-4: Zusatz ist gedämpfter Sekundärtext (--g-ink-muted), nicht Status-Accent.
	test('AC-4: Supplement nutzt gedämpfte Sekundärfarbe (= .meta-line)', async ({ page }) => {
		/**
		 * GIVEN: der Trip-Kopf wird gerendert
		 * WHEN: der Zusatz-Span dargestellt wird
		 * THEN: dessen color entspricht --g-ink-muted (gleiche Farbe wie die
		 *       bereits gedämpfte Meta-Zeile), nicht der Accent-Statusfarbe
		 */
		await page.goto(`/trips/${ACTIVE_TRIP_ID}`);
		const supplement = page.getByTestId('trip-detail-status-supplement');
		await expect(supplement).toBeVisible();

		const supplementColor = await supplement.evaluate(
			(el) => window.getComputedStyle(el).color
		);
		const metaColor = await page
			.getByTestId('trip-detail-meta')
			.evaluate((el) => window.getComputedStyle(el).color);

		expect(supplementColor).toBe(metaColor);
	});

	// AC-3: Regressions-Guard — Pill bleibt bei pausierter Trip sichtbar/korrekt.
	test('AC-3: pausierte Trip zeigt Pill "Pausiert" ohne "PAUSIERT"-Präfix', async ({
		page,
		request
	}) => {
		/**
		 * GIVEN: eine pausierte Trip
		 * WHEN: der Trip-Kopf gerendert wird
		 * THEN: Pill `trip-detail-status-badge` enthält "Pausiert", kein Versalien-Präfix
		 */
		const today = new Date().toISOString().slice(0, 10);
		await request.delete(`/api/trips/${PAUSED_TRIP_ID}`);
		await request.post('/api/trips', {
			data: {
				id: PAUSED_TRIP_ID,
				name: 'E2E #336 Paused',
				stages: [
					{
						id: 'e2e-336-s1',
						name: 'Etappe',
						date: today,
						waypoints: [{ id: 'e2e-336-wp1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
					}
				]
			}
		});
		await request.patch(`/api/trips/${PAUSED_TRIP_ID}/state`, { data: { paused: true } });

		await page.goto(`/trips/${PAUSED_TRIP_ID}`);
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText('Pausiert');

		const header = page.locator('header.trip-header');
		await expect(header).not.toContainText('PAUSIERT');

		await request.delete(`/api/trips/${PAUSED_TRIP_ID}`);
	});
});
