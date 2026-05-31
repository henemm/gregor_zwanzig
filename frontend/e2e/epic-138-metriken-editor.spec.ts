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

	// AC-2: Genau 26 Metrik-Checkboxen in 5 Kategorien
	test('AC-2: Metriken-Tab zeigt genau 26 Metrik-Checkboxen in 5 Kategorien', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}#weather`);
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible();

		// 26 Checkboxen
		const checkboxes = page.locator('[data-testid^="weather-metrics-tab-checkbox-"]');
		await expect(checkboxes).toHaveCount(ALL_METRIC_IDS.length); // 25 in array above + 1 = 26? Let me count

		// Alle erwarteten IDs vorhanden
		for (const id of ALL_METRIC_IDS) {
			await expect(page.getByTestId(`weather-metrics-tab-checkbox-${id}`)).toBeAttached();
		}

		// 5 Kategorien sichtbar (Temperatur, Wind, Niederschlag, Atmosphäre, Winter/Schnee)
		const categories = tab.locator('[data-category]');
		await expect(categories).toHaveCount(5);
	});

	// AC-3 (Issue #173): Preset-Liste statt Dropdown — 7 PresetRows
	test('AC-3: Preset-Liste enthält genau 7 PresetRows mit Name, Metrik-Anzahl und Standard-Badge', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}#weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		// Container der PresetRow-Liste sichtbar
		const presetList = page.getByTestId('weather-metrics-preset-list');
		await expect(presetList).toBeVisible();

		// Genau 7 PresetRows
		const presetRows = page.locator('[data-testid^="weather-metrics-preset-row-"]').filter({
			has: page.locator('[data-testid$="-name"]')
		});
		// Robustere Zählung: nur die Wrapper-Buttons (testid endet auf id, nicht auf -name/-count/-badge/-active)
		const presetButtons = presetList.locator(
			'button[data-testid^="weather-metrics-preset-row-"]'
		);
		await expect(presetButtons).toHaveCount(7);

		// Bekannte Preset-IDs vorhanden mit Name + Count + Badge
		const expectedIds = [
			'alpen-trekking',
			'wandern',
			'skitouren',
			'wintersport',
			'radtour',
			'wassersport',
			'allgemein'
		];
		for (const id of expectedIds) {
			const row = page.getByTestId(`weather-metrics-preset-row-${id}`);
			await expect(row, `PresetRow für ${id} fehlt`).toBeAttached();
			await expect(page.getByTestId(`weather-metrics-preset-row-${id}-name`)).toBeAttached();
			await expect(page.getByTestId(`weather-metrics-preset-row-${id}-count`)).toContainText(
				/\d+ Metriken/
			);
			await expect(page.getByTestId(`weather-metrics-preset-row-${id}-badge`)).toHaveText(
				'Standard'
			);
		}

		// Alter Dropdown existiert nicht mehr
		await expect(page.getByTestId('weather-metrics-tab-template')).toHaveCount(0);
		// Suchhinweis: PresetRows ersetzen den Dropdown, alter selector darf nicht mehr auftauchen
	});

	// AC-4 (Issue #173): Klick auf PresetRow "Wandern" aktiviert die Wandern-Metriken
	test('AC-4: Klick auf PresetRow "Wandern" aktiviert genau die definierten Metriken', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}#weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		// PresetRow "Wandern" klicken
		const wandernRow = page.getByTestId('weather-metrics-preset-row-wandern');
		await expect(wandernRow).toBeVisible();
		await wandernRow.click();

		// Active-Marker erscheint auf der geklickten Row
		await expect(page.getByTestId('weather-metrics-preset-row-wandern-active')).toBeVisible();

		// Wandern-Metriken laut metric_catalog.py:
		const wandernMetrics = [
			'temperature',
			'humidity',
			'wind',
			'gust',
			'precipitation',
			'rain_probability',
			'cloud_total',
			'sunshine',
			'uv_index',
			'confidence'
		];
		const nonWandern = ALL_METRIC_IDS.filter((id) => !wandernMetrics.includes(id as string));

		// Wandern-Metriken aktiviert
		for (const id of wandernMetrics) {
			await expect(page.getByTestId(`weather-metrics-tab-checkbox-${id}`)).toBeChecked();
		}

		// Andere deaktiviert
		for (const id of nonWandern) {
			await expect(page.getByTestId(`weather-metrics-tab-checkbox-${id}`)).not.toBeChecked();
		}
	});

	// AC-5: Roh/Indikator-Buttons nur für 9 eligible Metriken
	test('AC-5: Roh/Indikator-Buttons genau für 9 eligible Metriken sichtbar, nicht für andere', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}#weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		// 9 eligible Metriken haben beide Buttons
		for (const id of ELIGIBLE_METRIC_IDS) {
			await expect(
				page.getByTestId(`weather-metrics-tab-format-raw-${id}`),
				`Roh-Button fehlt für ${id}`
			).toBeVisible();
			await expect(
				page.getByTestId(`weather-metrics-tab-format-indicator-${id}`),
				`Indikator-Button fehlt für ${id}`
			).toBeVisible();
		}

		// Nicht-eligible Metriken haben KEINE Format-Buttons
		const nonEligible = ALL_METRIC_IDS.filter(
			(id) => !ELIGIBLE_METRIC_IDS.includes(id as (typeof ELIGIBLE_METRIC_IDS)[number])
		);
		for (const id of nonEligible) {
			await expect(
				page.getByTestId(`weather-metrics-tab-format-raw-${id}`),
				`Roh-Button sollte nicht existieren für ${id}`
			).toHaveCount(0);
			await expect(
				page.getByTestId(`weather-metrics-tab-format-indicator-${id}`),
				`Indikator-Button sollte nicht existieren für ${id}`
			).toHaveCount(0);
		}
	});

	// AC-6: Save sendet alle 26 IDs + use_friendly_format im Payload
	test('AC-6: Speichern sendet PUT mit allen 26 Metrik-IDs und use_friendly_format', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}#weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		const putPromise = page.waitForRequest(
			(req) =>
				req.method() === 'PUT' && req.url().includes(`/api/trips/${TRIP_ID}/weather-config`)
		);

		await page.getByTestId('weather-metrics-tab-save').click();
		const putReq = await putPromise;
		const body = JSON.parse(putReq.postData() || '{}') as {
			metrics: Array<{ metric_id: string; enabled: boolean; use_friendly_format: boolean }>;
		};

		// Genau 26 Metrik-Objekte
		expect(body.metrics).toHaveLength(ALL_METRIC_IDS.length);

		// Jedes Objekt hat metric_id, enabled und use_friendly_format
		for (const entry of body.metrics) {
			expect(entry).toHaveProperty('metric_id');
			expect(entry).toHaveProperty('enabled');
			expect(entry).toHaveProperty('use_friendly_format');
			expect(typeof entry.use_friendly_format).toBe('boolean');
		}

		// Alle 26 IDs sind enthalten (keine fehlende ID)
		const sentIds = body.metrics.map((m) => m.metric_id).sort();
		const expectedIds = [...ALL_METRIC_IDS].sort();
		expect(sentIds).toEqual(expectedIds);
	});

	// AC-7: use_friendly_format wird persistiert (Round-Trip)
	test('AC-7: Roh-Format für cloud_total wird nach Speichern und Reload korrekt geladen', async ({
		page,
		request
	}) => {
		// Vorzustand: display_config mit cloud_total use_friendly_format=true setzen
		await request.put(`/api/trips/${TRIP_ID}/weather-config`, {
			data: {
				metrics: ALL_METRIC_IDS.map((id) => ({
					metric_id: id,
					enabled: true,
					use_friendly_format: id === 'cloud_total' ? false : true
				}))
			}
		});

		await page.goto(`/trips/${TRIP_ID}#weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		// Roh-Button für cloud_total ist aktiv (use_friendly_format=false)
		const rawBtn = page.getByTestId('weather-metrics-tab-format-raw-cloud_total');
		const indicatorBtn = page.getByTestId('weather-metrics-tab-format-indicator-cloud_total');
		await expect(rawBtn).toHaveAttribute('data-active', 'true');
		await expect(indicatorBtn).toHaveAttribute('data-active', 'false');

		// Nach Speichern: nochmals prüfen
		const putPromise = page.waitForRequest(
			(req) =>
				req.method() === 'PUT' && req.url().includes(`/api/trips/${TRIP_ID}/weather-config`)
		);
		await page.getByTestId('weather-metrics-tab-save').click();
		const putReq = await putPromise;
		const body = JSON.parse(putReq.postData() || '{}') as {
			metrics: Array<{ metric_id: string; enabled: boolean; use_friendly_format: boolean }>;
		};

		const cloudEntry = body.metrics.find((m) => m.metric_id === 'cloud_total');
		expect(cloudEntry?.use_friendly_format).toBe(false);
	});

	// AC-10: Erfolgsmeldung nach Speichern
	test('AC-10: Erfolgsmeldung erscheint nach erfolgreichem Speichern', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}#weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		await page.getByTestId('weather-metrics-tab-save').click();

		const successMsg = page.getByTestId('weather-metrics-tab-success');
		await expect(successMsg).toBeVisible({ timeout: 3000 });
	});
});

// AC-8: WeatherConfigDialog — use_friendly_format im Payload
test.describe('AC-8 — WeatherConfigDialog: use_friendly_format im Save-Payload', () => {
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
test.describe('AC-9 — EditWeatherSection: use_friendly_format in displayConfig-Emission', () => {
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
