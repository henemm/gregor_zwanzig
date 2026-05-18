// TDD RED: Epic #138 Block B — Issues #174–178 (Metriken-Editor UI-Erweiterungen)
//
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md
//
// Diese Tests MÜSSEN in der RED-Phase scheitern, weil folgende Elemente noch nicht existieren:
//   - data-testid="weather-metrics-dirty-pill"       (#178)
//   - data-testid="weather-metrics-discard"          (#178)
//   - data-testid="metric-group-{slug}"              (#174)
//   - data-testid="weather-metrics-table-preview"    (#176)
//   - data-testid="save-preset-dialog-trigger"       (#177)
//   - GET /api/metric-presets                        (#177)
//
// INDICATOR_MAP (12 Metriken im UI, 9 vom Backend + 3 frontend-erweitert):
const INDICATOR_MAP_IDS = [
	'wind_direction', 'thunder', 'cape',
	'cloud_total', 'cloud_low', 'cloud_mid', 'cloud_high',
	'visibility', 'sunshine',
	'wind', 'gust', 'rain_probability'
] as const;

// Kategorie-Slugs aus CATEGORY_ORDER in WeatherMetricsTab
const CATEGORY_SLUGS = ['temperature', 'wind', 'precipitation', 'atmosphere', 'winter'] as const;

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-block-b-metrics';

async function createTestTrip(request: import('@playwright/test').APIRequestContext) {
	await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E Block B — Metriken-Editor Erweiterungen',
			stages: [
				{
					id: 'blk-b-stage-1',
					name: 'Tag 1',
					date: '2026-06-10',
					waypoints: [
						{ id: 'blk-b-wp-1', name: 'Berghaus', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: 'blk-b-wp-2', name: 'Gipfel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
					]
				}
			]
		}
	});
}

async function deleteTestTrip(request: import('@playwright/test').APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
}

async function navigateToMetricsTab(page: import('@playwright/test').Page) {
	await page.goto(`/trips/${TRIP_ID}#weather`);
	await page.waitForSelector('[data-testid="weather-metrics-tab"]', { timeout: 10_000 });
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-1 + AC-2: dirty-State (#178)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Block B — #178 dirty-State', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTestTrip(request);
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	test('AC-1: Dirty-Pill erscheint nach Checkbox-Änderung', async ({ page }) => {
		await navigateToMetricsTab(page);

		// Pill darf initial NICHT sichtbar sein
		await expect(
			page.locator('[data-testid="weather-metrics-dirty-pill"]')
		).not.toBeVisible();

		// Erste Checkbox umschalten
		const firstCheckbox = page.locator('[data-testid^="weather-metrics-tab-checkbox-"]').first();
		await firstCheckbox.click();

		// Dirty-Pill MUSS jetzt erscheinen
		await expect(
			page.locator('[data-testid="weather-metrics-dirty-pill"]')
		).toBeVisible();
		await expect(
			page.locator('[data-testid="weather-metrics-dirty-pill"]')
		).toContainText('Ungespeicherte Änderungen');
	});

	test('AC-2: Verwerfen-Button setzt Zustand zurück', async ({ page }) => {
		await navigateToMetricsTab(page);

		const firstCheckbox = page.locator('[data-testid^="weather-metrics-tab-checkbox-"]').first();
		const initialState = await firstCheckbox.isChecked();
		await firstCheckbox.click();

		// Dirty-Pill ist sichtbar
		await expect(
			page.locator('[data-testid="weather-metrics-dirty-pill"]')
		).toBeVisible();

		// Verwerfen klicken
		await page.click('[data-testid="weather-metrics-discard"]');

		// Checkbox ist wieder im Ausgangszustand
		await expect(firstCheckbox).toBeChecked({ checked: initialState });

		// Dirty-Pill verschwunden
		await expect(
			page.locator('[data-testid="weather-metrics-dirty-pill"]')
		).not.toBeVisible();
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-3 + AC-8: MetricGroup (#174)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Block B — #174 MetricGroup', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTestTrip(request);
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	test('AC-3: Alle 5 Kategorie-Gruppen mit Eyebrow und Zähler sichtbar', async ({ page }) => {
		await navigateToMetricsTab(page);

		for (const slug of CATEGORY_SLUGS) {
			const group = page.locator(`[data-testid="metric-group-${slug}"]`);
			await expect(group).toBeVisible();

			// Header mit Eyebrow muss vorhanden sein
			const eyebrow = group.locator('[data-slot="eyebrow"]');
			await expect(eyebrow).toBeVisible();

			// Zähler "X / Y" muss vorhanden sein
			const counter = group.locator('[data-testid="metric-group-counter"]');
			await expect(counter).toBeVisible();
		}
	});

	test('AC-8: Zähler in MetricGroup reagiert auf Checkbox-Änderungen', async ({ page }) => {
		await navigateToMetricsTab(page);

		const group = page.locator('[data-testid="metric-group-temperature"]');
		const counter = group.locator('[data-testid="metric-group-counter"]');

		const initialText = await counter.textContent();

		// Eine Checkbox in Temperatur-Gruppe umschalten
		const tempCheckbox = group.locator('[data-testid^="weather-metrics-tab-checkbox-"]').first();
		await tempCheckbox.click();

		// Zähler muss sich geändert haben (reaktiv)
		const updatedText = await counter.textContent();
		expect(updatedText).not.toBe(initialText);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-4: INDICATOR_MAP / ModeBtn (#175)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Block B — #175 ModeBtn / INDICATOR_MAP', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTestTrip(request);
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	test('AC-4a: Roh/Indikator-Toggle genau für 12 INDICATOR_MAP-Metriken sichtbar', async ({ page }) => {
		await navigateToMetricsTab(page);

		// Alle Roh-Buttons zählen
		const rawBtns = page.locator('[data-testid^="weather-metrics-tab-format-raw-"]');
		await expect(rawBtns).toHaveCount(12);

		// Alle Indikator-Buttons zählen
		const indBtns = page.locator('[data-testid^="weather-metrics-tab-format-indicator-"]');
		await expect(indBtns).toHaveCount(12);
	});

	test('AC-4b: Toggle-Buttons haben Pill-Stil (data-slot="pill")', async ({ page }) => {
		await navigateToMetricsTab(page);

		// Roh-Pill für wind_direction muss data-slot="pill" haben
		const rawPill = page.locator('[data-testid="weather-metrics-tab-format-raw-wind_direction"]');
		await expect(rawPill).toHaveAttribute('data-slot', 'pill');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-5: TablePreview (#176)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Block B — #176 TablePreview', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTestTrip(request);
		await createTestTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
	});

	test('AC-5a: TablePreview ist sichtbar und zeigt aktivierte Metriken als Spalten', async ({ page }) => {
		await navigateToMetricsTab(page);

		const preview = page.locator('[data-testid="weather-metrics-table-preview"]');
		await expect(preview).toBeVisible();

		// Mindestens eine Spalte muss vorhanden sein
		const headers = preview.locator('th');
		const count = await headers.count();
		expect(count).toBeGreaterThan(1); // Zeit-Spalte + mind. 1 Metrik-Spalte
	});

	test('AC-5b: Spalte verschwindet wenn Checkbox deaktiviert', async ({ page }) => {
		await navigateToMetricsTab(page);

		const preview = page.locator('[data-testid="weather-metrics-table-preview"]');
		const initialCount = await preview.locator('th').count();

		// Erste Metrik-Checkbox deaktivieren (nicht Zeit-Spalte)
		const firstCheckbox = page.locator('[data-testid^="weather-metrics-tab-checkbox-"]').first();
		const isChecked = await firstCheckbox.isChecked();
		if (isChecked) {
			await firstCheckbox.click();
			const newCount = await preview.locator('th').count();
			expect(newCount).toBe(initialCount - 1);
		}
	});

	test('AC-5c: Indikator-Zellen haben data-mode="indicator" wenn friendly=true', async ({ page }) => {
		await navigateToMetricsTab(page);

		// Indikator-Modus für wind_direction einschalten
		const indBtn = page.locator('[data-testid="weather-metrics-tab-format-indicator-wind_direction"]');
		await indBtn.click();

		// Zellen für wind_direction im Indikator-Modus
		const cells = page.locator('[data-testid^="table-preview-cell-wind_direction-"]');
		for (let i = 0; i < await cells.count(); i++) {
			await expect(cells.nth(i)).toHaveAttribute('data-mode', 'indicator');
		}
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-6 + AC-7: SavePresetDialog (#177)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Block B — #177 SavePresetDialog', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTestTrip(request);
		await createTestTrip(request);
		// Alle Test-Presets von vorherigen Läufen bereinigen
		const listResp = await request.get('/api/metric-presets');
		if (listResp.ok()) {
			const presets = await listResp.json() as Array<{ id: string; name: string }>;
			for (const p of presets) {
				if (p.name.startsWith('Test-Preset') || p.name.startsWith('Preset A') || p.name.startsWith('Preset B')) {
					await request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
				}
			}
		}
	});

	test.afterAll(async ({ request }) => {
		await deleteTestTrip(request);
		// Presets aufräumen
		const listResp = await request.get('/api/metric-presets');
		if (listResp.ok()) {
			const presets = await listResp.json() as Array<{ id: string; name: string }>;
			for (const p of presets) {
				if (p.name.startsWith('Test-Preset') || p.name.startsWith('Preset A') || p.name.startsWith('Preset B')) {
					await request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
				}
			}
		}
	});

	test('AC-6a: GET /api/metric-presets gibt 200 zurück', async ({ request }) => {
		const response = await request.get('/api/metric-presets');
		expect(response.status()).toBe(200);
		const body = await response.json();
		expect(Array.isArray(body)).toBe(true);
	});

	test('AC-6b: Dialog-Trigger ist sichtbar, Dialog öffnet sich', async ({ page }) => {
		await navigateToMetricsTab(page);

		const trigger = page.locator('[data-testid="save-preset-dialog-trigger"]');
		await expect(trigger).toBeVisible();
		await trigger.click();

		const dialog = page.locator('[data-testid="save-preset-dialog"]');
		await expect(dialog).toBeVisible();
	});

	test('AC-6c: Speichern-Button deaktiviert bei leerem Namen', async ({ page }) => {
		await navigateToMetricsTab(page);
		await page.click('[data-testid="save-preset-dialog-trigger"]');

		const nameInput = page.locator('[data-testid="save-preset-name"]');
		await nameInput.fill('');

		const submitBtn = page.locator('[data-testid="save-preset-submit"]');
		await expect(submitBtn).toBeDisabled();
	});

	test('AC-6d: POST /api/metric-presets speichert Preset, Preset erscheint in Liste', async ({ page, request }) => {
		await navigateToMetricsTab(page);
		await page.click('[data-testid="save-preset-dialog-trigger"]');

		await page.fill('[data-testid="save-preset-name"]', 'Test-Preset Block-B');
		await page.click('[data-testid="save-preset-submit"]');

		// Dialog schließt sich
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		// Preset taucht in der PresetRow-Liste auf
		await expect(
			page.locator('[data-testid^="weather-metrics-preset-row-"]', { hasText: 'Test-Preset Block-B' })
		).toBeVisible();

		// API gibt das gespeicherte Preset zurück
		const listResp = await request.get('/api/metric-presets');
		const presets = await listResp.json() as Array<{ name: string }>;
		expect(presets.some((p) => p.name === 'Test-Preset Block-B')).toBe(true);
	});

	test('AC-7: is_default=true setzt alle anderen auf false', async ({ request }) => {
		// Zwei Presets anlegen, zweites als Default
		await request.post('/api/metric-presets', {
			data: {
				name: 'Preset A',
				metrics: ['temperature', 'wind'],
				friendly_ids: [],
				is_default: true
			}
		});
		await request.post('/api/metric-presets', {
			data: {
				name: 'Preset B',
				metrics: ['temperature'],
				friendly_ids: ['wind_direction'],
				is_default: true
			}
		});

		const resp = await request.get('/api/metric-presets');
		const presets = await resp.json() as Array<{ name: string; is_default: boolean }>;
		const defaults = presets.filter((p) => p.is_default);
		expect(defaults).toHaveLength(1);
		expect(defaults[0].name).toBe('Preset B');
	});
});
