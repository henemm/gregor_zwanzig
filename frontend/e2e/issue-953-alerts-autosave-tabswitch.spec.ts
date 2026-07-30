// Issue #953 — Alerts-Tab: Empfindlichkeits-Änderung geht nach Tab-Klick optisch verloren.
// Reproduktion des Bugs gegen den LIVE-Code auf Staging (kein Mock; der Tab-Klick
// ist echte Nutzer-Interaktion, keine Verhaltens-Simulation).
// Issue #1231 Slice 6 (Adversary F001): AlertsTab/AlertMetricLevelTable wurden in
// Slice 5 durch CorridorEditor(Mobile) ersetzt — Selektoren/Datenmodell auf den
// Warnen-Toggle (Corridor.notify) migriert, fachlicher Kern (Autosave
// überlebt echten Tab-Klick) unverändert gegenüber der Original-Reproduktion.
// Issue #1371: "Warnen" entfernt — "Markieren" bleibt ein echter `<button>`
// in derselben Zeile, schreibt über denselben Autosave-Pfad, trägt denselben
// #953-Kern. Zusätzlich AC-1-Live-Nachweis: kein "Warnen"-Bedienelement mehr
// (Ortsvergleich-Pendant: compare-editor-autosave.spec.ts).
// Ausführen: cd frontend && npx playwright test e2e/issue-953-alerts-autosave-tabswitch.spec.ts \
//   --config=playwright.953.staging.config.ts --reporter=list

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-953-alerts';
const TRIP_NAME = 'E2E #953 Alerts Autosave';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

// Metriken + Alert-Stufen bereits gesetzt (wie in einem real konfigurierten Trip).
const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] }
	],
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00'
	},
	display_config: {
		metrics: [
			{ metric_id: 'thunder_level', enabled: true },
			{ metric_id: 'wind_gust', enabled: true },
			{ metric_id: 'precipitation_sum', enabled: true }
		],
		metric_alert_levels: {
			thunder_level: 'standard',
			wind_gust: 'standard',
			precipitation_sum: 'standard'
		}
	},
	// Issue #1231: Corridor bereits gesetzt (wie in einem real konfigurierten Trip)
	// → die Gewitter-Zeile erscheint direkt im CorridorEditor, kein Pool-Zustand.
	corridors: [{ metric: 'thunder_level', range: [null, 40], notify: false, mark: false }]
};

function thunderRow(page: Page) {
	return page.getByTestId('corridor-row-thunder_level');
}
function markToggle(page: Page) {
	return thunderRow(page).getByRole('button', { name: 'Markieren' });
}

test.describe('issue_953 — Wertebereiche-Einstellung überlebt Tab-Klick', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});

	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	// KERN: Markieren-Toggle bleibt nach echtem Tab-Klick sichtbar (Issue #953-
	// Regression; Issue #1371: Auslöser von "Warnen" auf "Markieren" umgestellt,
	// da "Warnen" entfernt ist — derselbe Autosave-Pfad, derselbe Button-Typ).
	test('KERN: Markieren-Toggle überlebt Tab-Wechsel in der Anzeige', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}?tab=alerts`);
		await expect(page.getByTestId('corridor-editor-route')).toBeVisible();

		// Ausgangszustand: Markieren inaktiv (aus dem Seed-Corridor).
		await expect(markToggle(page)).toHaveAttribute('aria-pressed', 'false');

		// Auf "an" klicken → lokal sofort sichtbar.
		await markToggle(page).click();
		await expect(markToggle(page)).toHaveAttribute('aria-pressed', 'true');

		// Echter Nutzer-Pfad: Tab-BUTTON klicken (nicht goto/Reload — der Bug tritt
		// nur beim Klick-Pfad auf).
		await page.getByTestId('trip-detail-tab-preview').click();
		await page.getByTestId('trip-detail-tab-alerts').click();

		// HAUPT-ASSERTION: Der Toggle zeigt weiterhin "an".
		await expect(markToggle(page)).toHaveAttribute('aria-pressed', 'true');

		// Trennt UI-Bug von Save-Bug: die DB ist korrekt (Wert wurde gespeichert,
		// Bereich unverändert). Issue #1371: metric_alert_levels bleibt vom
		// Markieren-Save unangetastet (AC-2/AC-3 — keine zweite Alarmquelle mehr).
		const check = await page.request.get(`/api/trips/${TRIP_ID}`);
		expect(check.ok(), `GET trip HTTP ${check.status()}`).toBeTruthy();
		const trip = await check.json();
		const corridor = (trip.corridors ?? []).find((c: { metric: string }) => c.metric === 'thunder_level');
		expect(corridor?.mark).toBe(true);
		expect(trip.display_config?.metric_alert_levels?.thunder_level).toBe('standard');
	});

	// Issue #1371 AC-1 (Live-Nachweis Trip-Kontext): in der Wertebereiche-Zeile
	// existiert kein "Warnen"-Bedienelement mehr — nur Markieren + "✕ entfernen"
	// bleiben. Ortsvergleich-Pendant: compare-editor-autosave.spec.ts.
	test('AC-1 (Trip): kein "Warnen"-Bedienelement mehr in der Wertebereiche-Zeile', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}?tab=alerts`);
		await expect(page.getByTestId('corridor-editor-route')).toBeVisible();

		await expect(thunderRow(page).getByRole('button', { name: 'Warnen' })).toHaveCount(0);
		await expect(markToggle(page)).toBeVisible();
		await expect(thunderRow(page).getByRole('button', { name: '✕ entfernen' })).toBeVisible();
	});
});
