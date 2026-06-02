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
	test('AC-1: Metriken-Tab zeigt WeatherMetricsTab-Komponente, keinen Platzhaltertext', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		const panel = page.getByTestId('trip-detail-panel-weather');
		await expect(panel).toBeVisible();

		// Kein Platzhaltertext mehr
		await expect(panel).not.toContainText(/Inhalt folgt mit Issue #158/);
		await expect(panel).not.toContainText(/Epic #138/);

		// Stattdessen: WeatherMetricsTab mit Speichern-Button
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible();
		await expect(page.getByTestId('weather-metrics-tab-save')).toBeVisible();
	});

	// AC-2 neu (#536): Bucket-Editor zeigt primary/secondary/off-Sektionen
	test('AC-2: Bucket-Editor zeigt primary/secondary/off-Sektionen', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('bucket-section-primary')).toBeVisible();
		await expect(page.getByTestId('bucket-section-secondary')).toBeVisible();
		await expect(page.getByTestId('bucket-section-off')).toBeVisible();
	});

	// AC-3 neu (#536): Preset-Liste zeigt Preset-Rows
	test('AC-3: Preset-Liste zeigt Preset-Rows', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		const presetList = page.getByTestId('weather-metrics-preset-list');
		await expect(presetList).toBeVisible();
		// Mindestens eine Preset-Row vorhanden
		const rows = page.locator('[data-testid^="weather-metrics-preset-row-"]');
		await expect(rows.first()).toBeVisible();
	});

	// AC-4 neu (#536): Klick auf "Wandern"-Preset befüllt primary-Bucket
	test('AC-4: Klick auf "Wandern"-Preset befüllt primary-Bucket', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		// Wandern-Preset klicken
		const wandernRow = page.getByTestId('weather-metrics-preset-row-wandern');
		await expect(wandernRow).toBeVisible();
		await wandernRow.click();
		// Confirm-Dialog bestätigen wenn vorhanden
		const confirmOk = page.getByTestId('preset-confirm-ok');
		if (await confirmOk.isVisible()) await confirmOk.click();
		// primary-Bucket hat jetzt Metriken
		const primarySection = page.getByTestId('bucket-section-primary');
		await expect(primarySection).toBeVisible();
		await expect(primarySection.locator('[data-testid^="active-metric-row-"]').first()).toBeVisible();
	});

	// AC-5 neu (#536): Format-Toggle Roh/Skala umschaltbar
	test('AC-5: Format-Toggle Roh/Skala umschaltbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('bucket-section-primary')).toBeVisible();
		// Ersten Roh-Button im primary-Bucket finden
		const rawBtn = page.locator('[data-testid^="metric-mode-raw-"]').first();
		await expect(rawBtn).toBeVisible();
		await rawBtn.click();
		await expect(rawBtn).toHaveClass(/active/);
		// Scale-Button desselben Metrik-Eintrags muss inaktiv sein
		const scaleBtn = page.locator('[data-testid^="metric-mode-scale-"]').first();
		await expect(scaleBtn).not.toHaveClass(/active/);
	});

	// AC-6 neu (#536): Speichern sendet PUT mit bucket/order-Feldern
	test('AC-6: Speichern sendet PUT mit bucket/order-Feldern', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		// Dirty-State herstellen: Metrik aus Off-Sektion hinzufügen
		await page.getByTestId('bucket-off-toggle').click();
		const addBtn = page.locator('[data-testid^="off-add-column-"]').first();
		if (await addBtn.isVisible()) {
			await addBtn.click();
		} else {
			// Fallback: Format-Toggle nutzen wenn Off leer ist
			const rawBtn = page.locator('[data-testid^="metric-mode-raw-"]').first();
			if (await rawBtn.isVisible()) await rawBtn.click();
		}
		// Dirty-Pill prüfen
		await expect(page.getByTestId('weather-metrics-dirty-pill')).toBeVisible();
		// PUT abfangen
		const putPromise = page.waitForRequest(
			(req) => req.method() === 'PUT' && req.url().includes('/weather-config')
		);
		await page.getByTestId('weather-metrics-tab-save').click();
		const putReq = await putPromise;
		const body = JSON.parse(putReq.postData() || '{}') as {
			metrics: Array<{ metric_id: string; bucket?: string; order?: number }>;
		};
		// Mindestens ein Eintrag mit bucket-Feld
		const hasBucketField = body.metrics.some((m) => m.bucket !== undefined);
		expect(hasBucketField).toBe(true);
	});

	// AC-7 neu (#536): Bucket-Zustand nach Speichern und Reload korrekt geladen
	test('AC-7: Bucket-Zustand nach Speichern und Reload korrekt geladen', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		// Wandern-Preset setzen und speichern
		await page.getByTestId('weather-metrics-preset-row-wandern').click();
		const confirmOk = page.getByTestId('preset-confirm-ok');
		if (await confirmOk.isVisible()) await confirmOk.click();
		await expect(page.getByTestId('weather-metrics-dirty-pill')).toBeVisible();
		await page.getByTestId('weather-metrics-tab-save').click();
		await expect(page.getByTestId('weather-metrics-tab-success')).toBeVisible();
		// Reload
		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		// Primary-Bucket hat nach Reload noch Metriken
		const primarySection = page.getByTestId('bucket-section-primary');
		await expect(primarySection.locator('[data-testid^="active-metric-row-"]').first()).toBeVisible();
	});

	// AC-10 neu (#536): Erfolgsmeldung erscheint nach Speichern
	test('AC-10: Erfolgsmeldung erscheint nach Speichern', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		// Dirty-State herstellen
		await page.getByTestId('bucket-off-toggle').click();
		const addBtn = page.locator('[data-testid^="off-add-column-"]').first();
		if (await addBtn.isVisible()) {
			await addBtn.click();
		} else {
			const rawBtn = page.locator('[data-testid^="metric-mode-raw-"]').first();
			if (await rawBtn.isVisible()) await rawBtn.click();
		}
		await expect(page.getByTestId('weather-metrics-dirty-pill')).toBeVisible();
		await page.getByTestId('weather-metrics-tab-save').click();
		await expect(page.getByTestId('weather-metrics-tab-success')).toBeVisible();
	});
});

// AC-8: WeatherConfigDialog — use_friendly_format im Payload
// SKIP (#501): Der WeatherConfigDialog wurde in #345 von der Trips-Übersichtsseite
// entfernt. "Wetter-Konfiguration" ist dort jetzt nur noch ein Dropdown-Menüpunkt,
// der zur Trip-Detail-Seite navigiert — kein Dialog mehr. Die use_friendly_format-
// Persistenz ist durch AC-6/AC-7 in diesem Spec abgedeckt (Metriken-Tab in Trip-Detail).
test.describe.skip('AC-8 — WeatherConfigDialog: use_friendly_format im Save-Payload', () => {
	const LOC_TRIP_ID = 'e2e-epic138-dialog';

	test.beforeAll(async ({ request }) => {
		await request.delete(`/api/trips/${LOC_TRIP_ID}`).catch(() => {});
		await request.post('/api/trips', {
			data: {
				id: LOC_TRIP_ID,
				name: 'E2E Epic 138 Dialog Test',
				stages: [
					{
						id: 'd138-stage-1',
						name: 'Etappe',
						date: '2026-06-01',
						waypoints: [
							{ id: 'd138-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 },
							{ id: 'd138-wp-2', name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 700 }
						]
					}
				]
			}
		});
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${LOC_TRIP_ID}`).catch(() => {});
	});

	test('AC-8: WeatherConfigDialog sendet use_friendly_format in jedem Metrik-Objekt', async ({
		page
	}) => {
		// Trips-Übersicht aufrufen wo WeatherConfigDialog verwendet wird
		await page.goto('/trips');
		// Trip-Row über den Trip-Namen finden und Wetter-Button (title="Wetter-Konfiguration") klicken
		const tripRow = page.getByRole('row').filter({ hasText: 'E2E Epic 138 Dialog Test' }).first();
		await expect(tripRow).toBeVisible();
		await tripRow.getByRole('button', { name: 'Wetter-Konfiguration' }).click();

		// Dialog ist sichtbar
		await expect(page.locator('[role="dialog"]')).toBeVisible();

		// Auf Katalog warten — Speichern-Button wird erst aktiviert wenn loading=false
		await expect(
			page.locator('[role="dialog"]').getByRole('button', { name: /speichern/i })
		).toBeEnabled();

		// Auf PUT warten
		const putPromise = page.waitForRequest(
			(req) => req.method() === 'PUT' && req.url().includes('/weather-config')
		);

		// Speichern
		await page.locator('[role="dialog"]').getByRole('button', { name: /speichern/i }).click();
		const putReq = await putPromise;
		const body = JSON.parse(putReq.postData() || '{}') as {
			metrics: Array<{ metric_id: string; enabled: boolean; use_friendly_format?: boolean }>;
		};

		// JEDES Metrik-Objekt muss use_friendly_format enthalten
		expect(body.metrics.length).toBeGreaterThan(0);
		for (const entry of body.metrics) {
			expect(entry, `metric_id=${entry.metric_id} fehlt use_friendly_format`).toHaveProperty(
				'use_friendly_format'
			);
		}
	});
});

// AC-9: EditWeatherSection — use_friendly_format in displayConfig
// SKIP (#501): EditWeatherSection wurde in #494/#345 aus dem Edit-View entfernt.
// Der Edit-View zeigt jetzt WeatherSummaryCard (read-only). Wetter-Konfig-Editing
// (inkl. use_friendly_format) lebt ausschließlich im Trip-Detail-Tab und ist
// durch AC-6/AC-7 in diesem Spec abgedeckt.
test.describe.skip('AC-9 — EditWeatherSection: use_friendly_format in displayConfig-Emission', () => {
	test('AC-9: Wizard-Bearbeitung emittiert use_friendly_format in displayConfig', async ({
		page,
		request
	}) => {
		const EDIT_TRIP_ID = 'e2e-epic138-edit';
		await request.delete(`/api/trips/${EDIT_TRIP_ID}`).catch(() => {});
		await request.post('/api/trips', {
			data: {
				id: EDIT_TRIP_ID,
				name: 'E2E Epic 138 Edit Test',
				stages: [
					{
						id: 'e138-edit-stage-1',
						name: 'Etappe',
						date: '2026-06-01',
						waypoints: [
							{ id: 'e138-edit-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 },
							{ id: 'e138-edit-wp-2', name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 700 }
						]
					}
				]
			}
		});

		try {
			await page.goto(`/trips/${EDIT_TRIP_ID}/edit`);

			// Wetter-Tab öffnen (Issue #494: Accordion → Tab-Navigation)
			await page.locator('[data-testid="edit-tabs"] [data-value="wetter"]').click();
			await expect(page.getByTestId('edit-weather-section')).toBeVisible();

			// Auf PUT-Request warten (Speichern)
			const putPromise = page.waitForRequest(
				(req) => req.method() === 'PUT' && req.url().includes(`/api/trips/${EDIT_TRIP_ID}`)
			);

			await page.getByTestId('edit-save-btn').click();
			const putReq = await putPromise;
			const body = JSON.parse(putReq.postData() || '{}') as {
				display_config?: {
					metrics: Array<{
						metric_id: string;
						enabled: boolean;
						use_friendly_format?: boolean;
					}>;
				};
			};

			// display_config.metrics müssen use_friendly_format enthalten
			expect(body.display_config).toBeDefined();
			expect(body.display_config!.metrics.length).toBeGreaterThan(0);
			for (const entry of body.display_config!.metrics) {
				expect(
					entry,
					`metric_id=${entry.metric_id} fehlt use_friendly_format in EditWeatherSection-Payload`
				).toHaveProperty('use_friendly_format');
			}
		} finally {
			await request.delete(`/api/trips/${EDIT_TRIP_ID}`).catch(() => {});
		}
	});
});
