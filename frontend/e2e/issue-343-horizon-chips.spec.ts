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
// von eigenen Unit-Tests referenziert; #2794 S3a Teil-PR 4a hat MetricCheckbox, MetricGroup,
// HorizonChip und HorizonChips geloescht — dieser Spec prueft nur noch den bleibenden
// SavePresetDialog). `WeatherV2Reihenfolge.svelte` (die tatsächliche
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

// #2794 Teil 3 (Spec docs/specs/modules/feat_2794_s3a_teil3_wetter.md §5 und AC-42): der Dialog
// „Als eigene Vorlage speichern" enthält Name, Beschreibung, „Als Standard für neue Trips" und den
// Hinweis „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. …", aber WEDER
// Zeithorizonte NOCH Zusammenfassung; die Dialog-Payload trägt kein `horizons` (Migration
// `scripts/migrate_2794_preset_horizons.py` entfernt sie aus dem Bestand). Die beiden verbliebenen
// Fälle AC-4/AC-7 prüfen deshalb jetzt das Gegenteil des Alt-Solls am selben Klickpfad: der
// gespeicherte Horizont-Zustand des Trips erscheint NICHT im Dialog und NICHT im POST, stattdessen
// trägt der POST die Ampel und die Art (`kind`).
const reiter = (page: import('@playwright/test').Page) => page.locator('[data-testid="wetter-tab"]:visible');

async function oeffneDialog(page: import('@playwright/test').Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=wetter`);
	await expect(reiter(page)).toBeVisible({ timeout: 15_000 });
	await expect(reiter(page).getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 15_000 });
	await reiter(page).getByTestId('wetter-vorlage-als-eigene').click();
	await expect(page.getByTestId('save-preset-dialog')).toBeVisible();
}

test.describe('Issue #343: HorizonChip-UI', () => {
	test.beforeAll(async ({ request }) => {
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	// AC-7 (#2794 Teil 3, AC-42): der Dialog zeigt KEINEN Zeithorizonte-Block und keine
	// Zusammenfassung, auch wenn der Trip Horizonte gespeichert hat; er zeigt den Hinweis.
	test('AC-7: SavePresetDialog zeigt KEINEN Zeithorizonte-Block und keine Zusammenfassung (AC-42)', async ({
		page,
		request: apiRequest
	}) => {
		const res = await apiRequest.put(`/api/trips/${TRIP_ID}/weather-config`, {
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
		expect(res.ok(), 'Messaufbau: Horizont-Zustand gesetzt').toBeTruthy();

		await oeffneDialog(page);
		const dialog = page.getByTestId('save-preset-dialog');
		await expect(dialog).not.toContainText(/ZEITHORIZONTE|Zeithorizont/i);
		await expect(page.getByTestId('save-preset-horizon-summary')).toHaveCount(0);
		await expect(dialog.locator('[data-testid^="horizon-chip-"]')).toHaveCount(0);
		await expect(page.getByTestId('save-preset-hinweis')).toHaveText(
			'Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.'
		);
	});

	// AC-4 (#2794 Teil 3, AC-42): Submit sendet KEINE horizons, dafür die Ampel des Abos und `kind`.
	test('AC-4: Submit sendet keine horizons, sondern Ampel und Art in POST /api/metric-presets (AC-42)', async ({
		page,
		request: apiRequest
	}) => {
		const res = await apiRequest.put(`/api/trips/${TRIP_ID}/weather-config`, {
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
		expect(res.ok(), 'Messaufbau: Horizont-Zustand gesetzt').toBeTruthy();

		await oeffneDialog(page);
		const presetName = `AC-4-Test-Preset-${Date.now()}`;
		await page.getByTestId('save-preset-name').fill(presetName);

		const requestPromise = page.waitForRequest(
			(req) => req.url().includes('/api/metric-presets') && req.method() === 'POST'
		);
		await page.getByTestId('save-preset-submit').click();
		const postReq = await requestPromise;

		const body = JSON.parse(postReq.postData() || '{}');
		expect(body.name).toBe(presetName);
		expect(body.kind, 'AC-42: die Vorlage trägt die Art des Kontexts').toBe('route');
		expect(body.ampel?.metrics, 'AC-42: die Vorlage trägt die Ampel des Abos').toBeTruthy();
		expect(body.ampel.metrics.temperature?.enabled, 'die gewählte Metrik steht aktiv in der Ampel').toBe(true);
		expect(JSON.stringify(body), 'AC-42: keine Zeithorizonte im POST').not.toContain('horizons');
		expect(body, 'AC-42: keine Zusammenfassung im POST').not.toHaveProperty('summary');

		await expect(page.getByTestId('save-preset-dialog')).not.toBeVisible({ timeout: 5000 });
		const list = (await (await apiRequest.get('/api/metric-presets')).json()) as Array<{ id: string; name: string }>;
		const created = list.find((p) => p.name === presetName);
		expect(created, 'Vorlage gespeichert').toBeTruthy();
		await apiRequest.delete(`/api/metric-presets/${created!.id}`).catch(() => {});
	});
});
