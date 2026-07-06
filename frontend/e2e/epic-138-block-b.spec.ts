// E2E: Epic #138 Block B — Issues #177/#178 (Metriken-Editor UI, post-v2-Redesign)
//
// Spec: docs/specs/modules/fix_970_971_1011_e2e_ui_drift.md (Bündel I)
//
// Fix #971: Die v2-Metriken-Ansicht (#587/#848) rendert keine
// `weather-metrics-tab-checkbox-*`-Checkboxen, keine `metric-group-*`-Header,
// keine `weather-metrics-table-preview` und keinen `save-preset-dialog-trigger`
// mehr. Die zugehörigen Gruppen #174 (MetricGroup), #175 (ModeBtn/INDICATOR_MAP)
// und #176 (TablePreview) wurden PO-seitig zurückgezogen (Dead Code, keine
// Wiederherstellung). #178 (dirty-State) und #177 (SavePresetDialog) laufen weiter,
// migriert auf die realen v2-Selektoren: Grundauswahl-Toggle (`wm2-grundauswahl`)
// und Preset-Pills (`weather-preset-pill-{id}`) — echter Klickpfad, kein Mock.

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
	await page.goto(`/trips/${TRIP_ID}?tab=weather`);
	await page.waitForSelector('[data-testid="weather-metrics-tab"]', { timeout: 10_000 });
}

// Eine Metrik in der Grundauswahl umschalten → Tab wird „dirty".
// Fix #971: realer v2-Klickpfad statt totem `weather-metrics-tab-checkbox-*`.
// Der Live-Trip-Detail-Tab läuft im Autosave-Modus (#758, saveController gesetzt):
// die frühere `weather-metrics-dirty-pill`/`weather-metrics-discard`-UI existiert
// dort nicht mehr (nur ohne saveController). Die sichtbare „ungespeichert"-Affordanz
// ist der Speichern-Link „als eigenes Profil speichern" (nur bei Dirty sichtbar,
// bevor der 700ms-Autosave den Snapshot zurücksetzt) — daher sofort prüfen/klicken.
async function makeDirty(page: import('@playwright/test').Page) {
	await page
		.getByTestId('wm2-grundauswahl')
		.getByRole('button', { name: 'Gefühlte Temperatur' })
		.click();
	await expect(page.getByRole('button', { name: 'als eigenes Profil speichern' })).toBeVisible();
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

	// Fix #971: die frühere Dirty-Pill/Verwerfen-UI (AC-2) ist auf der Live-Trip-Detail-
	// Oberfläche Dead Code — dort läuft Autosave (#758), kein expliziter Verwerfen-Button.
	// Der reale „ungespeichert"-Zustand zeigt sich am Speichern-Link, der nur bei Dirty
	// erscheint. AC-1 prüft genau diese reale Affordanz (echter Klickpfad, kein Mock).
	test('AC-1: Grundauswahl-Änderung markiert den Tab als „ungespeichert"', async ({ page }) => {
		await navigateToMetricsTab(page);

		// Der Speichern-Link darf initial NICHT sichtbar sein (nichts geändert).
		await expect(
			page.getByRole('button', { name: 'als eigenes Profil speichern' })
		).toHaveCount(0);

		// Eine Grundauswahl-Metrik umschalten → „ungespeichert"-Affordanz erscheint.
		await makeDirty(page);
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

	test('AC-6b: Speichern-Link ist bei Dirty sichtbar, Dialog öffnet sich', async ({ page }) => {
		await navigateToMetricsTab(page);
		await makeDirty(page);

		const trigger = page.getByRole('button', { name: 'als eigenes Profil speichern' });
		await expect(trigger).toBeVisible();
		await trigger.click();

		const dialog = page.locator('[data-testid="save-preset-dialog"]');
		await expect(dialog).toBeVisible();
	});

	test('AC-6c: Speichern-Button deaktiviert bei leerem Namen', async ({ page }) => {
		await navigateToMetricsTab(page);
		await makeDirty(page);
		await page.getByRole('button', { name: 'als eigenes Profil speichern' }).click();
		await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();

		const nameInput = page.locator('[data-testid="save-preset-name"]');
		await nameInput.fill('');

		const submitBtn = page.locator('[data-testid="save-preset-submit"]');
		await expect(submitBtn).toBeDisabled();
	});

	test('AC-6d: POST /api/metric-presets speichert Preset, Preset erscheint als Pille', async ({ page, request }) => {
		await navigateToMetricsTab(page);
		await makeDirty(page);
		await page.getByRole('button', { name: 'als eigenes Profil speichern' }).click();
		await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();

		await page.fill('[data-testid="save-preset-name"]', 'Test-Preset Block-B');
		await page.click('[data-testid="save-preset-submit"]');

		// Dialog schließt sich
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		// API gibt das gespeicherte Preset zurück
		const listResp = await request.get('/api/metric-presets');
		const presets = await listResp.json() as Array<{ id: string; name: string }>;
		const created = presets.find((p) => p.name === 'Test-Preset Block-B');
		expect(created, 'Preset muss persistiert sein').toBeTruthy();

		// Das neue Preset erscheint als Pille in der v2-Preset-Leiste
		await expect(page.locator(`[data-testid="weather-preset-pill-${created!.id}"]`)).toBeVisible();
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
