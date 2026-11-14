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
// Komponente ist geteilt (Trips UND Ortsvergleich) — ein Trip-Kontext
// deckt beide ab (Spec docs/specs/fast/fix-1436-mobile-table-display.md).
//
// #2795 S3b Teilschritt 1b (feat_2795_s3b_teil1_zustellung.md AC-31): die Alarm-Empfindlichkeits-
// Tabelle ist aus dem Hub abgelöst. Ihre beiden Nachfolger tragen dieselbe Zusicherung „auf dem
// Handy wirklich gerendert, nicht nur im DOM“: „Alarm ab“ je Metrik in der Metrik-Zeile des Reiters
// Wetter und die Kanal-Tabelle (Spalten Alarme/Dringlichkeit) des Reiters Zustellung.

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
			display_config: {
				metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }],
				metric_alert_levels: { wind_gust: 'standard' }
			}
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openReiter(page: Page, id: string, tab: 'wetter' | 'zustellung'): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
	await page.getByTestId(`trip-detail-tab-${tab}`).first().click();
	await expect(page.getByTestId(`trip-detail-panel-${tab}`)).toBeVisible();
}

/** „Alarm ab“ einer Metrik-Zeile im Reiter Wetter (ohne den Kopf-Schalter „alle“). */
const alarmAb = (page: Page) =>
	page.locator('[data-testid="wetter-tab"]:visible [data-testid^="wetter-alarm-ab-"]:not([data-testid="wetter-alarm-ab-alle"])').first();

/** Gerenderte Größe statt DOM-Präsenz (der eigentliche Bug #1436). */
async function hatBox(el: ReturnType<Page['locator']>, was: string): Promise<void> {
	await expect(el).toBeAttached({ timeout: 15_000 });
	const box = await el.boundingBox();
	expect(box, `${was} muss eine gerenderte Bounding-Box haben`).not.toBeNull();
	expect(box!.height).toBeGreaterThan(0);
	expect(box!.width).toBeGreaterThan(0);
	await expect(el).toBeVisible();
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

			// Nachfolger 1: „Alarm ab“ je Metrik im Reiter Wetter.
			await openReiter(page, id, 'wetter');
			await expect(page.locator('[data-testid="wetter-tab"]:visible [data-testid="wetter-tab-laden"]')).toHaveCount(0, { timeout: 15_000 });
			await hatBox(alarmAb(page), '„Alarm ab“ der Metrik-Zeile');

			// Nachfolger 2: Kanal-Tabelle mit Alarm- und Dringlichkeits-Spalte im Reiter Zustellung.
			await openReiter(page, id, 'zustellung');
			const tabelle = page.locator('[data-testid="zustellung-kanal-tabelle"]:visible');
			await expect(tabelle).toBeAttached({ timeout: 15_000 });
			for (const k of ['email', 'telegram', 'sms', 'premium_sms']) {
				await hatBox(page.locator(`[data-testid="zustellung-kanal-${k}"]:visible`), `Kanal-Zeile ${k}`);
			}
			await hatBox(page.locator('[data-testid="zustellung-kanal-email-dringlichkeit"]:visible'), 'Dringlichkeits-Zelle E-Mail');
			const alarmZelle = page.locator(
				'[data-testid="zustellung-kanal-email-alarm"]:visible, [data-testid="zustellung-kanal-email-alarm-gesperrt"]:visible'
			).first();
			await hatBox(alarmZelle, 'Alarm-Zelle E-Mail');
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
			await openReiter(page, id, 'wetter');
			await hatBox(alarmAb(page), '„Alarm ab“ der Metrik-Zeile');

			await openReiter(page, id, 'zustellung');
			await hatBox(page.locator('[data-testid="zustellung-kanal-email"]:visible'), 'Kanal-Zeile E-Mail');
			// Kopfzeile sichtbar — Regressionsschutz gegen ein globales `thead { display: none }`.
			const kopf = page.locator('[data-testid="zustellung-kanal-tabelle"]:visible thead');
			await expect(kopf).toBeVisible();
			await expect(kopf.locator('th')).toHaveText(['Kanal', 'Briefing', 'Alarme', 'Alarm schon ab Dringlichkeit']);
		} finally {
			await deleteTrip(request, id);
		}
	});
});
