// Issue #953 — Alerts-Tab: Empfindlichkeits-Änderung geht nach Tab-Klick optisch verloren.
// Reproduktion des Bugs gegen den LIVE-Code auf Staging (kein Mock; der Tab-Klick
// ist echte Nutzer-Interaktion, keine Verhaltens-Simulation).
// Issue #1231 Slice 6 (Adversary F001): AlertsTab/AlertMetricLevelTable wurden in
// Slice 5 durch CorridorEditor(Mobile) ersetzt — Selektoren/Datenmodell auf den
// neuen Warnen-Toggle (Corridor.notify) migriert, fachlicher Kern (Autosave
// überlebt echten Tab-Klick) unverändert gegenüber der Original-Reproduktion.
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
	corridors: [{ metric: 'thunder_level', range: [null, 40], notify: true, mark: false }]
};

function thunderRow(page: Page) {
	return page.getByTestId('corridor-row-thunder_level');
}
function notifyToggle(page: Page) {
	return thunderRow(page).getByRole('button', { name: 'Warnen' });
}

test.describe('issue_953 — Wertebereiche-Empfindlichkeit überlebt Tab-Klick', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});

	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	// KERN: Warnen-Toggle bleibt nach echtem Tab-Klick sichtbar (Issue #953-Regression,
	// migriert auf CorridorEditor, da AlertsTab in Slice 5 entfernt wurde).
	test('KERN: Warnen-Toggle überlebt Tab-Wechsel in der Anzeige', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}?tab=alerts`);
		await expect(page.getByTestId('corridor-editor-route')).toBeVisible();

		// Ausgangszustand: Warnen aktiv (aus dem Seed-Corridor).
		await expect(notifyToggle(page)).toHaveAttribute('aria-pressed', 'true');

		// Auf "aus" klicken → lokal sofort sichtbar.
		await notifyToggle(page).click();
		await expect(notifyToggle(page)).toHaveAttribute('aria-pressed', 'false');

		// Echter Nutzer-Pfad: Tab-BUTTON klicken (nicht goto/Reload — der Bug tritt
		// nur beim Klick-Pfad auf).
		await page.getByTestId('trip-detail-tab-preview').click();
		await page.getByTestId('trip-detail-tab-alerts').click();

		// HAUPT-ASSERTION: Der Toggle zeigt weiterhin "aus".
		await expect(notifyToggle(page)).toHaveAttribute('aria-pressed', 'false');

		// Trennt UI-Bug von Save-Bug: die DB ist korrekt (Wert wurde gespeichert,
		// Δ-Wächter-Level entsprechend "off", Bereich unverändert — analog AC-10).
		const check = await page.request.get(`/api/trips/${TRIP_ID}`);
		expect(check.ok(), `GET trip HTTP ${check.status()}`).toBeTruthy();
		const trip = await check.json();
		const corridor = (trip.corridors ?? []).find((c: { metric: string }) => c.metric === 'thunder_level');
		expect(corridor?.notify).toBe(false);
		expect(trip.display_config?.metric_alert_levels?.thunder_level).toBe('off');
	});
});
