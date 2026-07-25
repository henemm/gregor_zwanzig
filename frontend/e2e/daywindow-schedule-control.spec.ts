// E2E — Epic #1319 Scheibe B+C, erweitert Issue #1361/#1372 S1b (ADR-0035):
// konfigurierbares Tagesfenster im Trip-Editor, Reiter "Wetter-Metriken"
// (context="route").
//
// Spec: docs/specs/modules/compare_shared_day_window.md (AC-4/AC-5)
// Vorgaenger: docs/specs/modules/daywindow_configurable_window.md (AC-5,
// Epic #1319) — das Control lag dort noch im Versand-Tab; #1361/#1372 S1b
// verschiebt es in den Reiter Wetter-Metriken (Inhalts-, keine Versandfrage)
// und macht ein Fenster ueber Mitternacht gueltig (ADR-0035, Punkt 5).
//
// Muster uebernommen aus versand-tab.spec.ts (createTrip/openTripOverview)
// + weather-metrics-tab-autosave.spec.ts (clickWeatherTab/collectTripPuts).
//
// Ausfuehren (gegen Staging/Preview):
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

async function clickWeatherTab(page: Page): Promise<void> {
	await page.getByTestId('trip-detail-tab-weather').first().click();
	await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();
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

test.describe('Issue #1361/#1372 S1b: Tagesfenster-Control im Reiter Wetter-Metriken (context=route)', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${tripId('ac5')}`).catch(() => {});
		await createTrip(page.request, tripId('ac5'));
	});

	test.afterEach(async ({ page }) => {
		await deleteTrip(page.request, tripId('ac5'));
	});

	// AC-5: Startstunde setzen -> Endstunde-Optionen bieten alle Stunden AUSSER
	// der Startstunde (ADR-0035: ein Fenster ueber Mitternacht ist gueltig, die
	// Endstunde darf also auch VOR der Startstunde liegen); Speichern loest
	// genau EINEN PUT aus, der das Feld-Paar persistiert; Reload behaelt den Wert.
	test('AC-5: Endstunde-Optionen schliessen nur die Startstunde selbst aus, genau 1 PUT, Reload persistiert', async ({
		page
	}) => {
		await login(page);
		await openTripOverview(page, tripId('ac5'));
		await clickWeatherTab(page);

		const control = page.locator('[data-testid="day-window-control"]:visible').first();
		await expect(control).toBeVisible({ timeout: 10_000 });

		const startSelect = control.locator('[data-testid="day-window-start-hour"]:visible').first();
		const endSelect = control.locator('[data-testid="day-window-end-hour"]:visible').first();

		await startSelect.selectOption('6');

		// ADR-0035: alle Stunden AUSSER der Startstunde sind waehlbar (auch
		// Werte VOR der Startstunde -- das bildet ein Fenster ueber Mitternacht).
		const endOptionValues = await endSelect.locator('option').evaluateAll((opts) =>
			opts.map((o) => (o as HTMLOptionElement).value)
		);
		expect(endOptionValues.map(Number)).not.toContain(6);
		expect(endOptionValues.length, 'erwartet 23 Optionen (alle 24 Stunden ausser der Startstunde)').toBe(23);

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
		await clickWeatherTab(page);

		await expect(startSelect).toHaveValue('6', { timeout: 10_000 });
		await expect(endSelect).toHaveValue('16', { timeout: 10_000 });
	});

	// AC-3/AC-5 (ADR-0035, Punkt 5): ein Fenster ueber Mitternacht (Endstunde
	// VOR der Startstunde) ist ueber die Oberfläche waehlbar, persistiert, und
	// die Karte zeigt den Mitternachts-Hinweis.
	test('AC-3: Mitternachts-Fenster (22-2 Uhr) ist waehlbar, zeigt den Hinweis, persistiert nach Reload', async ({
		page
	}) => {
		await login(page);
		await openTripOverview(page, tripId('ac5'));
		await clickWeatherTab(page);

		const control = page.locator('[data-testid="day-window-control"]:visible').first();
		await expect(control).toBeVisible({ timeout: 10_000 });

		const startSelect = control.locator('[data-testid="day-window-start-hour"]:visible').first();
		const endSelect = control.locator('[data-testid="day-window-end-hour"]:visible').first();

		const puts = collectTripPuts(page, tripId('ac5'));
		await startSelect.selectOption('22');
		await endSelect.selectOption('2');
		await page.waitForTimeout(1_500);

		expect(puts.length, `Erwartet mindestens 1 PUT, erhalten ${puts.length}`).toBeGreaterThanOrEqual(1);
		const lastBody = puts[puts.length - 1].postDataJSON() as {
			report_config?: { day_window_start_hour?: number; day_window_end_hour?: number };
		};
		expect(lastBody.report_config?.day_window_start_hour).toBe(22);
		expect(lastBody.report_config?.day_window_end_hour).toBe(2);

		await expect(control.locator('[data-testid="day-window-wrap-hint"]:visible').first()).toBeVisible();

		await page.reload();
		await page.waitForLoadState('networkidle');
		await clickWeatherTab(page);

		await expect(startSelect).toHaveValue('22', { timeout: 10_000 });
		await expect(endSelect).toHaveValue('2', { timeout: 10_000 });
	});
});
