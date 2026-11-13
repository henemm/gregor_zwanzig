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

	// AC-1 — UMGEDREHT durch #2913 c2 (Spec feat_2913_c2_seitenkopf.md, Mockup renderHead): neben
	// der Pill steht kein Zusatz („läuft seit …") mehr; der Zeitraum steht in der Meta-Zeile.
	test('AC-1 (#2913 c2): kein Zusatz neben der Pill, kein "AKTIV"-Präfix; Zeitraum in der Meta-Zeile', async ({ page }) => {
		await page.goto(`/trips/${ACTIVE_TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-status-badge')).toBeVisible();
		await expect(page.getByTestId('trip-detail-status-supplement')).toHaveCount(0);
		await expect(page.locator('header.trip-header')).not.toContainText('läuft seit');
		await expect(page.getByTestId('hub-kopf-meta')).toContainText('Etappen');
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

	// #2837 S1 (ADR-0110, Spec rework_2837_s1_hub_kopf.md AC-6) — UMGEDREHT: bisher stand der
	// Status in einer EIGENEN Zeile unter dem Kopf (genau einmal). Jetzt steht er genau einmal
	// als Badge IN DER TITELZEILE neben dem Namen, „Tag x von y" daneben; eine eigene
	// Statuszeile gibt es nicht mehr. Gemessen am Desktop (1440 px): die senkrechte Mitte von
	// Badge und Zusatz liegt innerhalb der Überschrift-Box.
	// #2913 c2: der Zusatz neben dem Badge entfällt (Mockup) — geprüft wird nur noch das Badge.
	test('AC-5 (#2837 S1): Status genau einmal, als Badge in der Titelzeile; keine Statuszeile', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		await page.goto(`/trips/${ACTIVE_TRIP_ID}`);
		const h1 = page.getByTestId('trip-detail-h1');
		await expect(h1).toBeVisible();
		const badge = page.getByTestId('trip-detail-status-badge');
		await expect(badge).toHaveCount(1);
		await expect(page.getByTestId('trip-detail-status-supplement')).toHaveCount(0);
		const titel = (await h1.boundingBox())!;
		for (const [name, loc] of [['Badge', badge]] as const) {
			const box = (await loc.boundingBox())!;
			const mitte = box.y + box.height / 2;
			expect(mitte, `${name} steht nicht in der Titelzeile (eigene Statuszeile?)`).toBeGreaterThanOrEqual(titel.y);
			expect(mitte, `${name} steht nicht in der Titelzeile (eigene Statuszeile?)`).toBeLessThanOrEqual(titel.y + titel.height);
		}
		await expect(page.locator('.status-line'), 'eigene Statuszeile existiert noch').toHaveCount(0);
	});

	// AC-4 — umgehängt durch #2913 c2: der Zusatz-Span entfällt; die Meta-Zeile (hub-kopf-meta) ist
	// gedämpfter Sekundärtext, nicht die Farbe der Status-Pill.
	test('AC-4 (#2913 c2): Meta-Zeile ist gedämpfter Sekundärtext, nicht Status-Farbe', async ({ page }) => {
		await page.goto(`/trips/${ACTIVE_TRIP_ID}`);
		const meta = page.getByTestId('hub-kopf-meta');
		await expect(meta).toBeVisible();
		const metaColor = await meta.evaluate((el) => window.getComputedStyle(el).color);
		const badgeColor = await page.getByTestId('trip-detail-status-badge').evaluate((el) => window.getComputedStyle(el).color);
		const h1Color = await page.getByTestId('trip-detail-h1').evaluate((el) => window.getComputedStyle(el).color);
		expect(metaColor, 'Meta-Zeile in Status-Farbe').not.toBe(badgeColor);
		expect(metaColor, 'Meta-Zeile so kräftig wie der Titel').not.toBe(h1Color);
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
