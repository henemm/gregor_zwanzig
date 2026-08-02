// E2E — Bug #1436: Alarm-Empfindlichkeits-Tabelle (AlertMetricLevelTable)
// war auf schmalen Bildschirmen (<=899px) komplett unsichtbar.
//
// Ursache: `table, thead { display: none; }` in der Media Query hat den
// kompletten Teilbaum inkl. `tbody` aus dem Layout genommen —
// `tbody { display: block; }` konnte das nicht zurueckholen.
// Fix: nur `thead` wird ausgeblendet, `table` bleibt `display: block`.
//
// Ein reiner DOM-Praesenz-Check (isVisible() allein) haette den Bug NICHT
// erkannt — die Zeile war laut jsdom/Playwright-DOM "vorhanden", aber ihr
// Vorfahre (<table>) hatte display:none, die tatsaechliche Rendergroesse
// war 0x0. Dieser Test prueft deshalb explizit die Bounding-Box.
//
// Komponente ist geteilt (Touren UND Ortsvergleich) — ein Trip-Kontext
// deckt beide ab (Spec docs/specs/fast/fix-1436-mobile-table-display.md).

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-1436-mobile-alert-table';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Bug 1436 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			display_config: { metric_alert_levels: { wind_gust: 'standard' } }
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openAlarmeTab(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
	await page.getByTestId('trip-detail-tab-alarme').first().click();
	await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible();
}

test.describe('Bug #1436: Alarm-Tabelle auf schmalen Bildschirmen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('bei Viewport <=899px hat mindestens eine Alarm-Zeile eine sichtbare Bounding-Box (nicht nur DOM-Praesenz)', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id);
		try {
			// Handy-Breite, wie im Issue gemeldet (390x844, <=899px-Breakpoint).
			await page.setViewportSize({ width: 390, height: 844 });
			await openAlarmeTab(page, id);

			const table = page.locator('[data-testid="alert-metric-level-table"] table');
			await expect(table).toBeAttached();

			const row = page.locator('[data-testid="alert-metric-row-wind_gust"]');
			await expect(row).toBeAttached();

			// Der eigentliche Bug: die Zeile war im DOM "vorhanden" (isVisible()
			// haette hier faelschlich gruen gemeldet), aber ihr Vorfahre <table>
			// hatte display:none -> tatsaechliche Rendergroesse 0x0.
			const box = await row.boundingBox();
			expect(box, 'Alarm-Zeile muss eine gerenderte Bounding-Box haben').not.toBeNull();
			expect(box!.height).toBeGreaterThan(0);
			expect(box!.width).toBeGreaterThan(0);

			// Segmented-Control und Schwellwert der Zeile muessen ebenfalls
			// tatsaechlich sichtbar sein (nicht nur DOM-Praesenz).
			await expect(page.locator('[data-testid="alert-metric-segmented-wind_gust"]')).toBeVisible();
			await expect(row).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('bei Desktop-Breite (>899px) bleibt die Kopfzeile sichtbar (keine Regression)', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await openAlarmeTab(page, id);

			const row = page.locator('[data-testid="alert-metric-row-wind_gust"]');
			await expect(row).toBeVisible();
			const box = await row.boundingBox();
			expect(box).not.toBeNull();
			expect(box!.height).toBeGreaterThan(0);

			// Kopfzeile ist Desktop-exklusiv sichtbar — Regressionsschutz gegen
			// ein versehentliches globales `thead { display: none }`.
			await expect(page.locator('[data-testid="alert-metric-level-table"] thead')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});
});
