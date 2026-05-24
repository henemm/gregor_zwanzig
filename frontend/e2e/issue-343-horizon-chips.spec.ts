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

test.describe('Issue #343: HorizonChip-UI', () => {
	test.beforeAll(async ({ request }) => {
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	// AC-1: Klick togglet visuell + dirty-State
	test('AC-1: Klick auf HorizonChip togglet data-active und zeigt dirty-Pill', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		const chip = page.locator('[data-testid^="horizon-chip-"][data-day="tomorrow"]').first();
		await expect(chip).toBeVisible();
		await expect(chip).toHaveAttribute('data-active', 'true');

		await chip.click();
		await expect(chip).toHaveAttribute('data-active', 'false');
		await expect(page.getByTestId('weather-metrics-dirty-pill')).toBeVisible();
	});

	// AC-2: Chips bleiben togglebar wenn Checkbox aus
	test('AC-2: HorizonChip togglebar AUCH wenn Metrik-Checkbox aus', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		const cb = page.getByTestId('weather-metrics-tab-checkbox-cloud_total');
		await cb.uncheck();

		const chip = page.getByTestId('horizon-chip-cloud_total-today');
		await expect(chip).toBeVisible();
		const before = await chip.getAttribute('data-active');
		await chip.click();
		const after = await chip.getAttribute('data-active');
		if (after === before) {
			throw new Error(`Chip data-active musste sich toggeln, ist aber "${after}" geblieben`);
		}
		await expect(page.getByTestId('weather-metrics-dirty-pill')).toBeVisible();
	});

	// AC-3: Save + Reload bringt Horizonte unveraendert zurueck
	test('AC-3: Save + Reload persistiert Chip-State', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		const chip = page.getByTestId('horizon-chip-wind-today');
		await expect(chip).toBeVisible();
		const before = await chip.getAttribute('data-active');
		await chip.click();
		const expected = before === 'true' ? 'false' : 'true';
		await expect(chip).toHaveAttribute('data-active', expected);

		await page.getByTestId('weather-metrics-tab-save').click();
		await expect(page.getByTestId('weather-metrics-tab-success')).toBeVisible();

		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();
		await expect(page.getByTestId('horizon-chip-wind-today')).toHaveAttribute('data-active', expected);
		await expect(page.getByTestId('weather-metrics-dirty-pill')).not.toBeVisible();
	});

	// AC-5: TablePreview zeigt drei Tabellen
	test('AC-5: TablePreview rendert drei Tabellen heute/morgen/uebermorgen', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		const today = page.getByTestId('table-preview-day-today');
		const tomorrow = page.getByTestId('table-preview-day-tomorrow');
		const dayAfter = page.getByTestId('table-preview-day-day_after');
		await expect(today).toBeVisible();
		await expect(tomorrow).toBeVisible();
		await expect(dayAfter).toBeVisible();
		await expect(today.locator('table')).toHaveCount(1);
		await expect(tomorrow.locator('table')).toHaveCount(1);
		await expect(dayAfter.locator('table')).toHaveCount(1);
	});

	// AC-6: Mobile-Viewport bricht HorizonChips in Zeile 2 unter Metrik-Namen
	test('AC-6: Mobile-Viewport bricht HorizonChips in Zeile 2 unter Metrik-Namen', async ({ page }) => {
		await page.setViewportSize({ width: 393, height: 852 });
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		const metricLabel = page
			.locator('[data-testid="weather-metrics-tab-checkbox-temperature"]')
			.locator('xpath=ancestor::*[@data-slot="metric-row"][1]')
			.locator('[data-slot="metric-label"]')
			.first();
		const horizonChip = page.getByTestId('horizon-chip-temperature-today');

		await expect(metricLabel).toBeVisible();
		await expect(horizonChip).toBeVisible();

		const labelBox = await metricLabel.boundingBox();
		const chipBox = await horizonChip.boundingBox();
		expect(labelBox).not.toBeNull();
		expect(chipBox).not.toBeNull();

		// Chip ist UNTER dem Label (groesseres y) — Toleranz 5 px
		expect(chipBox!.y).toBeGreaterThan(labelBox!.y + labelBox!.height - 5);
		// Chip ist auf/ab Hoehe des Labels eingerueckt (gleich oder weiter rechts)
		expect(chipBox!.x).toBeGreaterThanOrEqual(labelBox!.x - 2);
		// Touch-Target gross genug (Spec verlangt 32 px Chip-Hoehe, 44 px Touch-Target)
		expect(chipBox!.height).toBeGreaterThanOrEqual(44);
	});

	// AC-7: SavePresetDialog zeigt ZEITHORIZONTE-Box
	test('AC-7: SavePresetDialog zeigt ZEITHORIZONTE-Block mit Wording-Zusammenfassung', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

		await page.getByTestId('save-preset-dialog-trigger').click();
		await expect(page.getByTestId('save-preset-dialog')).toBeVisible();
		await expect(page.getByTestId('save-preset-dialog')).toContainText(/ZEITHORIZONTE/);

		const summary = page.getByTestId('save-preset-horizon-summary');
		await expect(summary).toBeVisible();
		await expect(summary).toContainText(/(alle drei Tage|nur heute|nur morgen|sonstige Kombinationen)/);
	});
});
