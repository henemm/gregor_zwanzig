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

// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4/§5, AC-11, AC-12, AC-42): der Reiter Wetter ist
// der WetterTab. Die Auswahl ändert „−" an einer Metrik-Zeile (AC-19); „ungespeicherte" Abweichung
// von der Vorlage zeigt der Picker („{n} Abweichung(en)") samt Knopf „Auf ‚…‘ zurücksetzen"; der
// Dialog heißt „Als eigene Vorlage speichern" (Knopf `wetter-vorlage-als-eigene`), eigene Vorlagen
// stehen im Picker unter „Eigene" (Pillen der alten Preset-Leiste gibt es nicht mehr).
const reiter = (page: import('@playwright/test').Page) => page.locator('[data-testid="wetter-tab"]:visible');

async function navigateToMetricsTab(page: import('@playwright/test').Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=wetter`);
	await expect(reiter(page)).toBeVisible({ timeout: 10_000 });
	await expect(reiter(page).getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 10_000 });
}

async function oeffneDialog(page: import('@playwright/test').Page) {
	await reiter(page).getByTestId('wetter-vorlage-als-eigene').click();
	await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();
}

// Eine Metrik in der Grundauswahl umschalten → Tab wird „dirty".
// Fix #971: realer v2-Klickpfad statt totem `weather-metrics-tab-checkbox-*`.
// Der Live-Trip-Detail-Tab läuft im Autosave-Modus (#758, saveController gesetzt):
// die frühere `weather-metrics-dirty-pill`/`weather-metrics-discard`-UI existiert
// dort nicht mehr (nur ohne saveController). Die sichtbare „ungespeichert"-Affordanz
// ist der Speichern-Link „als eigenes Profil speichern" (nur bei Dirty sichtbar,
// bevor der 700ms-Autosave den Snapshot zurücksetzt) — daher sofort prüfen/klicken.
async function makeDirty(page: import('@playwright/test').Page) {
	await reiter(page).locator('[data-testid^="wetter-zeile-entfernen-"]').first().click();
	await expect(reiter(page).getByTestId('wetter-vorlage-status')).toHaveText(/^\d+ Abweichung/);
	await expect(reiter(page).getByTestId('wetter-vorlage-zuruecksetzen')).toBeVisible();
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
	test('AC-1: Auswahl-Änderung zeigt die Abweichung von der Vorlage („ungespeichert" gegenüber der Vorlage)', async ({ page }) => {
		await navigateToMetricsTab(page);

		// Initial: keine Abweichung von der Vorlage, kein Zurücksetzen-Knopf (nichts geändert).
		await expect(reiter(page).getByTestId('wetter-vorlage-status')).toHaveText('unverändert');
		await expect(reiter(page).getByTestId('wetter-vorlage-zuruecksetzen')).toHaveCount(0);

		// Eine Metrik aus dem Briefing nehmen → Abweichung + Zurücksetzen-Knopf erscheinen.
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

	test('AC-6b: nach einer Änderung öffnet „Als eigene Vorlage speichern" den Dialog', async ({ page }) => {
		await navigateToMetricsTab(page);
		await makeDirty(page);

		await oeffneDialog(page);
		await expect(page.locator('[data-testid="save-preset-hinweis"]')).toHaveText(
			'Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.'
		);
	});

	test('AC-6c: leerer Name → Pflicht-Hinweis, Dialog bleibt offen, nichts gespeichert', async ({ page }) => {
		await navigateToMetricsTab(page);
		await makeDirty(page);
		await oeffneDialog(page);

		const nameInput = page.locator('[data-testid="save-preset-name"]');
		await nameInput.fill('');

		// #2794 Teil 3 (Spec AC-42): Name ist Pflicht — statt eines gesperrten Knopfs meldet der Dialog
		// „Gib der Vorlage einen Namen.", bleibt offen und sendet NICHTS.
		const posts: string[] = [];
		page.on('request', (r) => {
			if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/metric-presets') posts.push(r.url());
		});
		await page.locator('[data-testid="save-preset-submit"]').click();
		await expect(page.locator('[data-testid="save-preset-error"]')).toHaveText('Gib der Vorlage einen Namen.');
		await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();
		expect(posts, 'ohne Namen darf keine Vorlage gesendet werden').toEqual([]);
	});

	test('AC-6d: POST /api/metric-presets speichert Preset, Preset erscheint unter „Eigene"', async ({ page, request }) => {
		await navigateToMetricsTab(page);
		await makeDirty(page);
		await oeffneDialog(page);

		await page.fill('[data-testid="save-preset-name"]', 'Test-Preset Block-B');
		await page.click('[data-testid="save-preset-submit"]');

		// Dialog schließt sich
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		// API gibt das gespeicherte Preset zurück
		const listResp = await request.get('/api/metric-presets');
		const presets = await listResp.json() as Array<{ id: string; name: string }>;
		const created = presets.find((p) => p.name === 'Test-Preset Block-B');
		expect(created, 'Preset muss persistiert sein').toBeTruthy();

		// AC-42: Erfolgsmeldung, und die neue Vorlage steht im Picker unter „Eigene"
		await expect(reiter(page).getByTestId('wetter-vorlage-gespeichert')).toHaveText(
			'Vorlage ‚Test-Preset Block-B‘ gespeichert. Du findest sie unter ‚Eigene‘.'
		);
		await reiter(page).getByTestId('wetter-vorlage-picker').click();
		await expect(reiter(page).getByTestId('wetter-vorlage-eigene').getByTestId(`wetter-vorlage-eigene-${created!.id}`)).toBeVisible();
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
