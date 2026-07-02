// TDD RED: Issue #343 — HorizonChip-UI im Wetter-Editor
//
// Spec: docs/specs/modules/issue_343_horizon_chip_ui.md
//
// Diese E2E-Tests MUESSEN in der RED-Phase scheitern, weil:
//   - HorizonChip-Komponente existiert noch nicht
//   - data-testid="horizon-chip-{metric}-{day}" ist nicht im DOM
//   - data-testid="table-preview-day-today|tomorrow|day_after" fehlt
//   - data-testid="save-preset-horizon-summary" fehlt
//   - WeatherMetricsTab.svelte hat noch keinen horizonsMap-State
//
// Login wird via global.setup.ts gemacht — storageState wird automatisch
// in jeden Test injiziert (siehe playwright.config.ts).

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-issue-343-horizon';

async function createTestTrip(request: import('@playwright/test').APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'Issue #343 HorizonChip E2E',
			stages: [
				{
					id: 'i343-stage-1',
					name: 'Etappe heute',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: 'i343-wp-1', name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 }
					]
				},
				{
					id: 'i343-stage-2',
					name: 'Etappe morgen',
					date: new Date(Date.now() + 86_400_000).toISOString().slice(0, 10),
					waypoints: [
						{ id: 'i343-wp-2', name: 'Mitte', lat: 47.1015, lon: 11.2958, elevation_m: 1000 }
					]
				},
				{
					id: 'i343-stage-3',
					name: 'Etappe uebermorgen',
					date: new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10),
					waypoints: [
						{ id: 'i343-wp-3', name: 'Ende', lat: 47.2190, lon: 11.8767, elevation_m: 540 }
					]
				}
			]
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTestTrip(request: import('@playwright/test').APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
}

// Fix #964 — WICHTIGER BEFUND (kein reines Selector-Rename):
// Die interaktive HorizonChip-Toggle-UI (Klick auf einen Chip togglet horizonsMap
// pro Metrik/Tag direkt im Trip-Detail-Tab) existiert im aktuellen DOM NICHT MEHR.
// `MetricCheckbox.svelte` (rendert <HorizonChip>) wird von `WeatherMetricsTab.svelte`
// seit dem v2-Rewrite (#587/#848) nicht mehr importiert/gerendert (Dead Code, nur noch
// von eigenen Unit-Tests referenziert). `WeatherV2Reihenfolge.svelte` (die tatsächliche
// "Reihenfolge & Darstellung"-Sektion) hat KEINE Horizont-Chips — nur Roh/Einfach-Toggle
// + "Aus"-Button. `TablePreview.svelte` (table-preview-day-*) ist ebenfalls Dead Code —
// die reale Live-Vorschau ist `WeatherV2MailPreview.svelte` (Email/Telegram/SMS-Tabs,
// keine Tages-Tabellen). Verifiziert per `page.content()`-Probe gegen echten Server:
// weder "horizon-chip" noch "table-preview-day" kommen im gerenderten HTML vor.
//
// horizonsMap selbst existiert weiterhin im State (initFromTrip/buildWeatherPayload)
// und wird in SavePresetDialog nur noch READ-ONLY angezeigt (ZEITHORIZONTE-Block).
// Es gibt AKTUELL KEINEN Klick-Pfad in der Trip-Detail-UI, um horizonsMap zu ändern.
//
// AC-1/AC-2/AC-3/AC-6 testen exakt diesen (nicht mehr existierenden) Chip-Klick-Pfad —
// sie sind daher nicht auf "echten Klick-Pfad" migrierbar, ohne die entfernte Chip-UI
// als Produktcode wiederherzustellen (außerhalb des Scopes dieses Fixes: reine
// Testkorrektur, kein Produktcode außer dem 2-Zeilen-Rename in TripNewEditor.svelte).
// Sie bleiben bewusst .skip mit Befund-Kommentar statt künstlich grün gebogen zu werden
// (PO-Entscheidung nötig: Chip-UI wiederherstellen vs. Feature-Entfernung akzeptieren
// und ACs offiziell zurückziehen — separates Folge-Issue).
//
// AC-5 (TablePreview 3 Tabellen) ist aus demselben Grund (Dead Code) nicht migrierbar.
//
// AC-4 und AC-7 sind teilweise migrierbar: der Horizon-ZUSTAND wird über einen echten
// Backend-PUT vorab gesetzt (kein Mock — reale Persistenz, exakt das Muster das AC-4
// im Fix-Loop #1 bereits für den Backend-Reset nutzte), der KLICK-Pfad testet dafür
// real die noch existierenden Teile: Preset-Dialog öffnen (über den "als eigenes
// Profil speichern"-Link, der nur bei isDirty sichtbar ist — Dirty-State wird über
// einen ECHTEN Grundauswahl-Toggle-Klick hergestellt), Name eintragen, submitten,
// POST-Body/UI-Summary prüfen.

test.describe('Issue #343: HorizonChip-UI', () => {
	test.beforeAll(async ({ request }) => {
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	// AC-1 — SKIP: Chip-Toggle-UI existiert nicht mehr im DOM (siehe Befund oben).
	test.skip('AC-1: Klick auf HorizonChip togglet data-active und zeigt dirty-Pill', async () => {});

	// AC-2 — SKIP: dito (kein Chip mehr, auch keine `weather-metrics-tab-checkbox-*`-
	// Checkbox mehr im v2-Layout — Aktivierung läuft über den Grundauswahl-Toggle).
	test.skip('AC-2: HorizonChip togglebar AUCH wenn Metrik-Checkbox aus', async () => {});

	// AC-3 — SKIP: Save+Reload-Persistenz von horizonsMap ist zwar weiterhin real
	// (siehe AC-7 unten, das denselben Persistenzpfad indirekt mitprüft), aber ohne
	// Chip gibt es keinen UI-Klick-Pfad, der den Toggle selbst auslöst.
	test.skip('AC-3: Save + Reload persistiert Chip-State', async () => {});

	// AC-5 — SKIP: TablePreview.svelte (table-preview-day-*) ist Dead Code, wird von
	// WeatherMetricsTab.svelte nicht gerendert.
	test.skip('AC-5: TablePreview rendert drei Tabellen heute/morgen/uebermorgen', async () => {});

	// AC-6 — SKIP: Mobile-Zeilenumbruch der Chips ist ohne existierende Chips nicht prüfbar.
	test.skip('AC-6: Mobile-Viewport bricht HorizonChips in Zeile 2 unter Metrik-Namen', async () => {});

	// AC-7: SavePresetDialog zeigt ZEITHORIZONTE-Box mit EXAKTEM Wording.
	// Horizon-Zustand wird real via Backend-PUT gesetzt (kein Chip-Klick mehr möglich);
	// der Dialog-Öffnen-/Anzeige-Pfad läuft über einen echten Klick.
	test('AC-7: SavePresetDialog zeigt ZEITHORIZONTE-Block mit Wording-Zusammenfassung', async ({
		page,
		request: apiRequest
	}) => {
		await apiRequest.put(`/api/trips/${TRIP_ID}/weather-config`, {
			data: {
				metrics: [
					{
						metric_id: 'temperature',
						enabled: true,
						use_friendly_format: true,
						horizons: { today: true, tomorrow: false, day_after: false }
					}
				]
			}
		});

		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		// Dirty-State herstellen über ein ANDERES Metrik-Toggle (Windchill), damit der
		// oben gesetzte "temperature"-Horizon-Zustand unangetastet bleibt.
		await page
			.getByTestId('wm2-grundauswahl')
			.getByRole('button', { name: 'Gefühlte Temperatur' })
			.click();

		await page.getByRole('button', { name: 'als eigenes Profil speichern' }).click();
		await expect(page.getByTestId('save-preset-dialog')).toBeVisible();
		await expect(page.getByTestId('save-preset-dialog')).toContainText(/ZEITHORIZONTE/);

		const summary = page.getByTestId('save-preset-horizon-summary');
		await expect(summary).toBeVisible();
		// Strict: temperature ist genau "nur heute" → "N nur heute" muss exakt vorkommen.
		await expect(summary).toContainText(/\b\d+ nur heute\b/);
	});

	// AC-4: Submit speichert horizons in POST /api/metric-presets.
	// Horizon-Zustand (day_after=false) wird real via Backend-PUT vorab gesetzt; der
	// Submit-Pfad (Dialog öffnen → Name eintragen → submitten) läuft über echte Klicks.
	test('AC-4: Submit speichert horizons in POST /api/metric-presets', async ({ page, request: apiRequest }) => {
		await apiRequest.put(`/api/trips/${TRIP_ID}/weather-config`, {
			data: {
				metrics: [
					{
						metric_id: 'temperature',
						enabled: true,
						use_friendly_format: true,
						horizons: { today: true, tomorrow: true, day_after: false }
					}
				]
			}
		});

		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		// Dirty-State herstellen über ein ANDERES Metrik-Toggle, damit die gesetzten
		// temperature-Horizonte unangetastet bleiben (Preset-Link ist nur bei isDirty sichtbar).
		await page
			.getByTestId('wm2-grundauswahl')
			.getByRole('button', { name: 'Gefühlte Temperatur' })
			.click();

		await page.getByRole('button', { name: 'als eigenes Profil speichern' }).click();
		await expect(page.getByTestId('save-preset-dialog')).toBeVisible();

		const presetName = `AC-4-Test-Preset-${Date.now()}`;
		await page.getByTestId('save-preset-name').fill(presetName);

		const requestPromise = page.waitForRequest(
			(req) => req.url().includes('/api/metric-presets') && req.method() === 'POST'
		);
		await page.getByTestId('save-preset-submit').click();
		const postReq = await requestPromise;

		const body = JSON.parse(postReq.postData() || '{}');
		expect(body.name).toBe(presetName);
		expect(Array.isArray(body.metrics)).toBe(true);
		expect(body.metrics.length).toBeGreaterThan(0);

		const tempMetric = body.metrics.find((m: { metric_id: string }) => m.metric_id === 'temperature');
		expect(tempMetric).toBeDefined();
		expect(tempMetric.horizons).toBeDefined();
		expect(tempMetric.horizons).toHaveProperty('today');
		expect(tempMetric.horizons).toHaveProperty('tomorrow');
		expect(tempMetric.horizons).toHaveProperty('day_after');
		// Vorab per API gesetzt: day_after=false → muss im Payload reflektiert sein.
		expect(tempMetric.horizons.day_after).toBe(false);

		// Dialog schließt sich nach erfolgreichem Save
		await expect(page.getByTestId('save-preset-dialog')).not.toBeVisible({ timeout: 5000 });
	});
});
