// TDD RED: Epic #138 — Wetter-Metriken-Editor Tab (Trip-Detail)
//
// Spec: docs/specs/modules/epic_138_metriken_editor.md
//
// Diese Tests MÜSSEN in der RED-Phase scheitern, weil:
//   - WeatherMetricsTab.svelte existiert noch nicht
//   - data-testid="weather-metrics-tab" ist nicht im DOM
//   - use_friendly_format fehlt in WeatherConfigDialog/EditWeatherSection-Payloads
//   - Roh/Indikator-Buttons existieren noch nicht
//
// Eligible Metriken (has_friendly_format=true, 9 Stück):
//   wind_direction, thunder, cape, cloud_total, cloud_low,
//   cloud_mid, cloud_high, visibility, sunshine

import { test, expect } from '@playwright/test';
import { knopf, oeffneKarte, seedAbo, tabelle, tabelleGespeichert } from './was-steht-wo.helpers';

const TRIP_ID = 'e2e-epic138-metrics';

const ELIGIBLE_METRIC_IDS = [
	'wind_direction',
	'thunder',
	'cape',
	'cloud_total',
	'cloud_low',
	'cloud_mid',
	'cloud_high',
	'visibility',
	'sunshine'
] as const;

const ALL_METRIC_IDS = [
	'temperature',
	'wind_chill',
	'humidity',
	'dewpoint',
	'wind',
	'gust',
	'wind_direction',
	'precipitation',
	'rain_probability',
	'confidence',
	'thunder',
	'cape',
	'snowfall_limit',
	'precip_type',
	'cloud_total',
	'cloud_low',
	'cloud_mid',
	'cloud_high',
	'visibility',
	'sunshine',
	'uv_index',
	'pressure',
	'freezing_level',
	'snow_depth',
	'fresh_snow'
] as const;

async function createTestTrip(request: import('@playwright/test').APIRequestContext) {
	await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E Epic 138 Metriken Test',
			stages: [
				{
					id: 'e138-stage-1',
					name: 'Etappe 1',
					date: '2026-06-01',
					waypoints: [
						{ id: 'e138-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 },
						{ id: 'e138-wp-2', name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 700 }
					]
				}
			]
		}
	});
}

async function deleteTestTrip(request: import('@playwright/test').APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
}

test.describe('Epic #138 — Wetter-Metriken-Editor Tab', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTestTrip(request);
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	// AC-1: Tab zeigt Editor statt Platzhaltertext
	// Fix #964: Der explizite "Speichern"-Button (weather-metrics-tab-save) wird nur
	// gerendert wenn KEIN saveController übergeben ist (createMode). Auf der echten
	// Trip-Detail-Seite bekommt WeatherMetricsTab IMMER einen saveController (Issue #758
	// Auto-Save) → der Button existiert dort nie. Der reale Speicher-Status-Indikator
	// ist stattdessen der SaveIndicator im TripHeader (data-testid="save-indicator").
	test('AC-1: Metriken-Tab zeigt WeatherMetricsTab-Komponente, keinen Platzhaltertext', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		const panel = page.getByTestId('trip-detail-panel-wetter');
		await expect(panel).toBeVisible();

		// Kein Platzhaltertext mehr
		await expect(panel).not.toContainText(/Inhalt folgt mit Issue #158/);
		await expect(panel).not.toContainText(/Epic #138/);

		// Stattdessen: WeatherMetricsTab mit Auto-Save-Indikator (Header)
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible();
		await expect(page.getByTestId('save-indicator')).toBeVisible();
	});

	// AC-2 (Fix #964, ex #536): Grundauswahl-Sektion zeigt Metrik-Toggle-Buttons.
	// Die alte primary/secondary/off-Bucket-Struktur (BucketSection.svelte) wurde seit
	// Issue #587 durch WeatherV2Grundauswahl ersetzt (Dead Code, nicht mehr importiert).
	// Secondary ist seit #587 immer leer — es gibt nur noch EINE Grundauswahl-Sektion.
	test('AC-2: Grundauswahl-Sektion zeigt Metrik-Toggle-Buttons (aktiv/inaktiv)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		const grundauswahl = page.getByTestId('wm2-grundauswahl');
		await expect(grundauswahl).toBeVisible();
		// Mindestens ein aktivierter Toggle-Button (Metrik "on") vorhanden.
		await expect(grundauswahl.locator('.toggle-btn.on').first()).toBeVisible();
		// Mindestens ein deaktivierter Toggle-Button (Metrik "off") vorhanden.
		await expect(grundauswahl.locator('.toggle-btn:not(.on)').first()).toBeVisible();
	});

	// AC-3 (Fix #964, ex #536): Preset-Leiste zeigt Preset-Pills (User-Presets + Templates)
	test('AC-3: Preset-Leiste zeigt Preset-Pills', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		const pills = page.locator('[data-testid^="weather-preset-pill-"]');
		await expect(pills.first()).toBeVisible();
	});

	// AC-4 (Fix #964, ex #536): Klick auf "Wandern"-Preset aktiviert Metriken in der Grundauswahl
	test('AC-4: Klick auf "Wandern"-Preset befüllt Grundauswahl mit aktiven Metriken', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		const wandernPill = page.getByTestId('weather-preset-pill-wandern');
		await expect(wandernPill).toBeVisible();
		await wandernPill.click();
		// Confirm-Dialog bestätigen wenn vorhanden
		const confirmOk = page.getByTestId('preset-confirm-ok');
		if (await confirmOk.isVisible()) await confirmOk.click();
		// Grundauswahl hat jetzt aktive (on) Metrik-Toggles
		const grundauswahl = page.getByTestId('wm2-grundauswahl');
		await expect(grundauswahl).toBeVisible();
		await expect(grundauswahl.locator('.toggle-btn.on').first()).toBeVisible();
	});

	// AC-5 (Fix #964, ex #536): Format-Toggle Roh/Einfach umschaltbar
	// "thunder" ist has_friendly_format=true UND default_enabled=true → im
	// wm2-reihenfolge-row von Anfang an sichtbar, kein Preset-Klick nötig.
	//
	// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): Kanal-Block und „3-Tages-Vorschau“
	// der Metrik-Oberflaeche sind aus dem Reiter Zustellung entfernt; Roh/Einfach schaltet im Hub die Karte
	// „Was steht wo“ je Stelle. AC-5 (Roh/Einfach im Kanal-Block umschaltbar) ist gestrichen — Ersatz
	// was-steht-wo-karte.spec.ts WS-3 (Umschalten, Neuladen, andere Stellen unveraendert, drei Faelle).
	// AC-5b laeuft an der Ausblick-Spalte der Karte.
	test('AC-5b (#2049): Ausblick-Umschalter auf „Einfach" wird gespeichert, thunder hat dort keinen', async ({ page }) => {
		const abo = await seedAbo(page.request, 'route');
		try {
			const karte = await oeffneKarte(page, 'route', abo.id);
			// AC-3: die Vorschau hat eine EIGENE Faehigkeitsliste — `thunder` bekommt dort keinen Umschalter.
			await expect(knopf(karte, 'thunder', 'outlook')).toHaveCount(0);
			const k = knopf(karte, 'gust', 'outlook');
			await expect(k).toBeVisible();
			const neu = (await k.getAttribute('data-wert')) === 'raw' ? 'simplified' : 'raw';
			const gespeichert = tabelleGespeichert(page, abo.id);
			await k.click();
			await gespeichert;
			await expect(k).toHaveAttribute('data-wert', neu);
			const row = ((await tabelle(page.request, 'route', abo.id)).placements.rows as Array<{ metric_id: string; formats?: Record<string, string> }>).find((r) => r.metric_id === 'gust');
			expect(row?.formats?.outlook, 'die Form reist als Stelle outlook in placements').toBe(neu);
		} finally {
			await abo.aufraeumen();
		}
	});

	// AC-6 (Fix #964, ex #536): Metrik-Änderung löst Auto-Save-PUT mit bucket/order-Feldern aus.
	// Kein expliziter Speichern-Button auf der Trip-Detail-Seite (siehe AC-1-Kommentar) —
	// die Grundauswahl-Toggle-Interaktion selbst löst scheduleAutoSave() aus (Issue #758).
	test('AC-6: Metrik-Toggle löst Auto-Save-PUT mit bucket/order-Feldern aus', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		const putPromise = page.waitForRequest(
			(req) => req.method() === 'PUT' && req.url().includes('/weather-config')
		);
		// Dirty-State herstellen: erste Metrik in der Grundauswahl togglen.
		await page.locator('[data-testid="wm2-grundauswahl"] .toggle-btn').first().click();
		const putReq = await putPromise;
		const body = JSON.parse(putReq.postData() || '{}') as {
			metrics: Array<{ metric_id: string; bucket?: string; order?: number }>;
		};
		// Mindestens ein Eintrag mit bucket-Feld (aktive Metrik).
		const hasBucketField = body.metrics.some((m) => m.bucket !== undefined);
		expect(hasBucketField).toBe(true);
	});

	// AC-7 (Fix #964, ex #536): Grundauswahl-Zustand nach Auto-Save und Reload korrekt geladen
	test('AC-7: Grundauswahl-Zustand nach Auto-Save und Reload korrekt geladen', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		await page.getByTestId('weather-preset-pill-wandern').click();
		const confirmOk = page.getByTestId('preset-confirm-ok');
		if (await confirmOk.isVisible()) await confirmOk.click();
		// Auto-Save abwarten: Indikator kehrt nach dem Debounce-PUT zu "idle" zurück.
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 5000
		});
		await page.reload();
		await page.getByTestId('trip-detail-tab-wetter').click();
		// Grundauswahl hat nach Reload noch aktive Metriken.
		await expect(
			page.locator('[data-testid="wm2-grundauswahl"] .toggle-btn.on').first()
		).toBeVisible();
	});

	// AC-10 (Fix #964, ex #536): Erfolgsmeldung nach Speichern
	// Ersetzt durch den Auto-Save-Kreislauf des SaveIndicator (Issue #758): "saving" → "idle"
	// ist das reale Erfolgssignal auf der Trip-Detail-Seite (kein separater Success-Text mehr).
	test('AC-10: SaveIndicator zeigt saving→idle-Übergang nach Metrik-Änderung', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-wetter').click();
		await page.locator('[data-testid="wm2-grundauswahl"] .toggle-btn').first().click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'saving');
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 5000
		});
	});
});
