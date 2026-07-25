// E2E — Issue #1361/#1372 S1b (ADR-0035): das Tagesfenster-Control ist eine
// GETEILTE Bedienfläche im Reiter "Wetter-Metriken" — für Trip UND
// Ortsvergleich gleichermaßen sichtbar und bedienbar.
//
// Spec: docs/specs/modules/compare_shared_day_window.md (AC-4)
//
// LÖST AB: e2e/daywindow-compare-exclusion.spec.ts (Epic #1319 Scheibe B+C,
// DEC-4 „Compare hat kein Tagesfenster"). Diese Entscheidung ist mit
// #1361/#1372 S1b zurückgenommen (ADR-0035): das Feld zieht aus dem
// Versand-Tab in den geteilten Reiter Wetter-Metriken — für BEIDE Kontexte,
// nicht mehr nur für den Trip. Der alte Test prüfte genau das Gegenteil
// (Control MUSS im Vergleich fehlen) und ist damit strukturell überholt,
// nicht nur verschoben.
//
// Muster übernommen aus daywindow-schedule-control.spec.ts (Trip-Hälfte) +
// weather-metrics-tab-autosave.spec.ts (Hub-Wetter-Metriken-Tab-Klick).
//
// Ausführen (gegen Staging/Preview):
//   cd frontend && npx playwright test e2e/daywindow-shared-both-contexts.spec.ts

import { test, expect, type APIRequestContext, type Page, type Request } from '@playwright/test';
import { login } from './helpers.js';
import { cleanupTracked, createTestLocation, createTestComparePreset } from './helpers';

const TRIP_PREFIX = 'e2e-1361-daywindow-shared';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1361 S1b ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config: { enabled: true, morning_enabled: true, morning_time: '07:00', send_email: true }
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

/** Öffnet den Compare-Hub und wartet die Hydration ab (SvelteKit-Race, #1359). */
async function openHubMetricsTab(page: Page, id: string) {
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]:visible').first().click();
	const panel = page.locator('[data-testid="compare-detail-panel-wetter-metriken"]:visible').first();
	await expect(panel).toBeVisible({ timeout: 10_000 });
	return panel;
}

/** Zeichnet jeden PUT auf dieses Preset auf (Speicher-Nachweis, AC-4). */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

async function readPreset(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok(), `GET des Presets fehlgeschlagen: ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

test.describe('Issue #1361/#1372 S1b (AC-4): Tagesfenster-Control — geteilt, beide Kontexte', () => {
	// AC-4 (Trip-Hälfte): Reiter Wetter-Metriken, context="route" — Control MUSS da sein.
	test('AC-4: Tagesfenster-Control ist im Trip-Reiter Wetter-Metriken sichtbar', async ({ page }) => {
		const id = tripId('route');
		await page.request.delete(`/api/trips/${id}`).catch(() => {});
		await createTrip(page.request, id);
		try {
			await login(page);
			await page.goto(`/trips/${id}`);
			await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
			await page.getByTestId('trip-detail-tab-weather').first().click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			await expect(page.locator('[data-testid="day-window-control"]:visible').first()).toBeVisible({
				timeout: 10_000
			});
		} finally {
			await deleteTrip(page.request, id);
		}
	});

	// AC-4 (Vergleich-Hälfte, PO-Entscheidung 2026-07-25, ADR-0035): dasselbe
	// Control ist im Hub-Reiter Wetter-Metriken des Ortsvergleichs ebenfalls
	// sichtbar UND BEDIENBAR — nicht nur sichtbar. Voller Nachweis analog der
	// Trip-Hälfte: Wert wählen -> PUT abfangen -> Rumpf prüfen -> Server-Stand
	// per GET bestätigen -> Reload behält den Wert. Fund Adversary Runde 2
	// (F001, HIGH): eine reine toBeVisible()-Prüfung hätte einen abgerissenen
	// Speicherweg (Umzug ohne mitgewanderten Bubble-Wrapper, bekannte S1a-Falle)
	// nicht gefangen.
	test('AC-4: Tagesfenster-Control im Compare-Hub ist bedienbar — Wert wählen, PUT, Server-Stand, Reload', async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const loc = await createTestLocation(page.request);
		const preset = await createTestComparePreset(page.request, {
			name: 'Daywindow-Shared-Vergleich',
			locationIds: [loc.id]
		});

		await login(page);
		const panel = await openHubMetricsTab(page, preset.id);

		const control = panel.locator('[data-testid="day-window-control"]:visible').first();
		await expect(control).toBeVisible({ timeout: 10_000 });
		const startSelect = control.locator('[data-testid="day-window-start-hour"]:visible').first();
		const endSelect = control.locator('[data-testid="day-window-end-hour"]:visible').first();

		const puts = collectPresetPuts(page, preset.id);
		// Stunde 0 bewusst gewählt (Team-Hinweis): eine `||`-Verkettung statt `??`
		// würde die falsy-aber-gültige Stunde 0 stillschweigend verschlucken.
		// Beide Selects nacheinander -- jede Aenderung kann ueber den
		// Bubble-Wrapper einen eigenen PUT ausloesen (Zwischenstand mit der
		// Default-Endstunde moeglich); massgeblich fuer die folgenden Pruefungen
		// ist ausschliesslich der LETZTE PUT nach dem Debounce-Fenster.
		await startSelect.selectOption('0');
		await endSelect.selectOption('10');
		await page.waitForTimeout(1_500); // Debounce-Fenster (Autosave-Muster anderer Tabs)

		// Nachweis 1 — es wurde WIRKLICH gespeichert, nicht nur umgeschaltet.
		expect(
			puts.length,
			'AC-4: nach der Bedienung muss mindestens ein Speichervorgang (PUT) gefeuert haben — beim Umzug ' +
				'muss der Bubble-Wrapper (.hub-wetter-metriken-wrap) mitwandern'
		).toBeGreaterThan(0);

		const lastPut = puts[puts.length - 1].postDataJSON() as {
			day_window_start_hour?: number;
			day_window_end_hour?: number;
		};
		expect(lastPut.day_window_start_hour, 'AC-4: PUT-Rumpf muss day_window_start_hour=0 tragen (kein ||-Verlust)').toBe(0);
		expect(lastPut.day_window_end_hour, 'AC-4: PUT-Rumpf muss day_window_end_hour=10 tragen').toBe(10);

		// Nachweis 2 — der Server hat es behalten (nicht nur der Request-Body).
		await expect
			.poll(
				async () => {
					const p = await readPreset(page, preset.id);
					return p.day_window_start_hour;
				},
				{ message: 'AC-4: die Startstunde muss serverseitig persistent sein (0, nicht null/undefined)', timeout: 10_000 }
			)
			.toBe(0);
		const persisted = await readPreset(page, preset.id);
		expect(persisted.day_window_end_hour).toBe(10);

		// Nachweis 3 — ein echter Reload zeigt weiterhin den gespeicherten Wert.
		const reloadedPanel = await openHubMetricsTab(page, preset.id);
		const reloadedControl = reloadedPanel.locator('[data-testid="day-window-control"]:visible').first();
		await expect(reloadedControl.locator('[data-testid="day-window-start-hour"]:visible').first()).toHaveValue(
			'0',
			{ timeout: 10_000 }
		);
		await expect(reloadedControl.locator('[data-testid="day-window-end-hour"]:visible').first()).toHaveValue(
			'10',
			{ timeout: 10_000 }
		);
	});
});
