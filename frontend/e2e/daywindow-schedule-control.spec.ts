// E2E — Epic #1319 Scheibe B+C: konfigurierbares Tagesfenster im Trip-Editor
// (Versand-Tab, "SMS-/Zeitplan-Einstellung", context="route").
//
// Spec: docs/specs/modules/daywindow_configurable_window.md (AC-5)
// Kontext: docs/context/issue-1319-slice-b.md
// Workflow: issue-1319-slice-b
//
// TDD RED: das Fenster-Control (Testid `day-window-control`, s.u.) existiert
// noch nicht in VTSchedulePlan.svelte -- dieser Test muss NICHT lokal laufen
// (kein Staging-/Preview-Verify in der RED-Phase), aber er MUSS existieren
// und den Ziel-Testid referenzieren, damit die Implement-Phase gegen ein
// konkretes Ziel arbeitet. Erwartete Fehlschlagsursache heute: Timeout beim
// Warten auf `[data-testid="day-window-control"]` (Locator nie sichtbar).
//
// Muster uebernommen aus versand-tab.spec.ts (createTrip/openTripOverview/
// clickVersandTab) + weather-metrics-tab-autosave.spec.ts (collectTripPuts).
//
// Ausfuehren (sobald implementiert, gegen Staging/Preview):
//   cd frontend && npx playwright test e2e/daywindow-schedule-control.spec.ts

import { test, expect, type APIRequestContext, type Page, type Request } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-1319-daywindow';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1319 Slice B ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: false,
				morning_time: '07:00',
				send_email: true
			}
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openTripOverview(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
}

async function clickVersandTab(page: Page): Promise<void> {
	await page.getByTestId('trip-detail-tab-briefings').first().click();
	await expect(page.getByTestId('trip-detail-panel-briefings')).toBeVisible();
}

/** Zeichnet jeden PUT-Request auf den Trip auf (Muster: weather-metrics-tab-autosave.spec.ts). */
function collectTripPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/trips/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

test.describe('Epic #1319 Scheibe B+C: Tagesfenster-Control im Versand-Tab (context=route)', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${tripId('ac5')}`).catch(() => {});
		await createTrip(page.request, tripId('ac5'));
	});

	test.afterEach(async ({ page }) => {
		await deleteTrip(page.request, tripId('ac5'));
	});

	// AC-5: Startstunde setzen -> Endstunde-Optionen nur > Startstunde; Speichern
	// loest genau EINEN PUT aus, der das Feld-Paar persistiert; Reload behaelt
	// den Wert.
	test('AC-5: Startstunde begrenzt Endstunde-Optionen, genau 1 PUT, Reload persistiert', async ({
		page
	}) => {
		await login(page);
		await openTripOverview(page, tripId('ac5'));
		await clickVersandTab(page);

		const control = page.locator('[data-testid="day-window-control"]:visible').first();
		await expect(control).toBeVisible({ timeout: 10_000 });

		const startSelect = control.locator('[data-testid="day-window-start-hour"]:visible').first();
		const endSelect = control.locator('[data-testid="day-window-end-hour"]:visible').first();

		await startSelect.selectOption('6');

		// Nur Endstunden > 6 duerfen waehlbar sein (0-23 begrenzt).
		const endOptionValues = await endSelect.locator('option').evaluateAll((opts) =>
			opts.map((o) => (o as HTMLOptionElement).value)
		);
		for (const v of endOptionValues) {
			expect(Number(v), `Endstunde-Option ${v} muss > 6 sein`).toBeGreaterThan(6);
		}

		const puts = collectTripPuts(page, tripId('ac5'));
		await endSelect.selectOption('16');
		await page.waitForTimeout(1_500); // Debounce-Fenster (Autosave-Muster anderer Tabs)

		expect(puts.length, `Erwartet genau 1 PUT nach Fenster-Aenderung, erhalten ${puts.length}`).toBe(1);
		const body = puts[0].postDataJSON() as {
			report_config?: { day_window_start_hour?: number; day_window_end_hour?: number };
		};
		expect(body.report_config?.day_window_start_hour).toBe(6);
		expect(body.report_config?.day_window_end_hour).toBe(16);

		await page.reload();
		await page.waitForLoadState('networkidle');
		await clickVersandTab(page);

		await expect(startSelect).toHaveValue('6', { timeout: 10_000 });
		await expect(endSelect).toHaveValue('16', { timeout: 10_000 });
	});
});
