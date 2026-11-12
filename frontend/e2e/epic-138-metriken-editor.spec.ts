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
	// 🔴 Issue #2049: der Locator zielt auf den KANAL-Block (Stundentabelle der
	// Mail). WeatherV2Reihenfolge wird auf derselben Seite ein zweites Mal im
	// 3-Tages-Vorschau-Block gerendert — deshalb ist er hier ausdrücklich auf
	// `wm2-reihenfolge` gescopt. Für die Vorschau gilt eine EIGENE
	// Fähigkeitsliste (Test AC-5b darunter); `thunder` hat dort bewusst keinen
	// Umschalter.
	test('AC-5: Format-Toggle Roh/Einfach umschaltbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-zustellung').click(); // #2794 S3a: Layout/Kanal im Reiter Zustellung
		const row = page
			.getByTestId('weather-metrics-kanal-reihenfolge')
			.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="thunder"]');
		await expect(row).toBeVisible();
		const rawBtn = row.getByRole('tab', { name: 'Roh' });
		const einfachBtn = row.getByRole('tab', { name: 'Einfach' });
		await rawBtn.click();
		await expect(rawBtn).toHaveAttribute('data-active', 'true');
		await expect(einfachBtn).toHaveAttribute('data-active', 'false');
	});

	// AC-5b / Issue #2049 (AC-3 + AC-14): der Roh/Einfach-Umschalter im Block
	// „3-Tages-Vorschau" ist WIRKSAM — bis #2049 war er eine Attrappe (No-Op-
	// Handler, immer leere Übersetzungstabelle), ein Klick veränderte nichts.
	//
	// Der Vorgänger-Test darüber konnte das strukturell nicht sehen: er klickte
	// nur „Roh" (die Ausgangsstellung) und prüfte nur den Schalterzustand, also
	// eine reine Frontend-Eigenschaft. Hier wird stattdessen „Einfach" geklickt
	// und die WIRKUNG geprüft — der abgesetzte PUT trägt das neue Feld
	// `display_config.outlook_metric_formats`. Ohne wirksamen Handler entsteht
	// dieses Feld nie.
	//
	// Trägermetrik `gust`: im Ausblick fähig (Wortstufe über
	// format_wind_strength) UND default_enabled, steht also ohne Preset-Klick
	// in der Vorschau-Liste.
	test('AC-5b (#2049): Vorschau-Umschalter auf „Einfach" schreibt outlook_metric_formats', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-zustellung').click(); // #2794 S3a: Ausblick im Reiter Zustellung

		const ausblick = page.getByTestId('weather-metrics-ausblick');
		await expect(ausblick).toBeVisible();

		// AC-3: die Vorschau hat eine EIGENE Fähigkeitsliste — `thunder` zeigt
		// roh bereits das Stufenwort und bekommt hier keinen Umschalter, obwohl
		// `indicatorCapable()` (Kanal-Block, Test darüber) ihn dort anbietet.
		const thunderRow = ausblick.locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="thunder"]'
		);
		if ((await thunderRow.count()) > 0) {
			await expect(thunderRow.getByRole('tab', { name: 'Einfach' })).toHaveCount(0);
		}

		const row = ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]');
		await expect(row).toBeVisible();
		const einfachBtn = row.getByRole('tab', { name: 'Einfach' });
		await expect(einfachBtn).toBeVisible();

		const putPromise = page.waitForRequest(
			(req) => req.method() === 'PUT' && req.url().includes('/weather-config')
		);
		await einfachBtn.click();

		// 1. Wirkung: das neue Feld reist zum Backend.
		const putReq = await putPromise;
		const body = JSON.parse(putReq.postData() || '{}') as {
			outlook_metric_formats?: Record<string, boolean>;
			outlook_metrics?: unknown;
		};
		expect(body.outlook_metric_formats?.gust).toBe(true);
		// AC-1: `outlook_metrics` bleibt eine reine Kennungsliste — die
		// Darstellungsform liegt in einem PARALLELEN Feld, nicht in einer
		// Objektform (#1848 A2 bleibt in Kraft).
		if (Array.isArray(body.outlook_metrics)) {
			for (const eintrag of body.outlook_metrics) {
				expect(typeof eintrag).toBe('string');
			}
		}

		// 2. Sichtbare Zustandsänderung in genau dieser Zeile.
		await expect(einfachBtn).toHaveAttribute('data-active', 'true');
		await expect(row.getByRole('tab', { name: 'Roh' })).toHaveAttribute('data-active', 'false');
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
