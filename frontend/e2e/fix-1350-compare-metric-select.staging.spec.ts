// Staging-Validierung — Issue #1350 Teil 2: Compare-Metrik-Auswahlliste bezieht
// ihre Einträge aus GET /api/compare/metrics statt aus dem statischen
// Frontend-Import COMPARE_METRIC_DEFS.
//
// Spec: docs/specs/modules/compare_metric_selection_source.md (AC-1, AC-4, AC-5)
// Workflow: fix-1350-compare-metric-select
//
// RED-Hinweis: Teil 2 ist zum Zeitpunkt dieser RED-Phase noch nicht deployt —
// diese Specs sind eine Laufzeit-Skizze fuer die spaetere Staging-Verifikation
// (Phase 7) und duerfen JETZT rot laufen (Feature fehlt). Wiederverwendet den
// bereits gueltigen storageState aus Issue #1332 (kein neuer Login-Request,
// Rate-Limit-Bucket #703 — analog fix-1335-compare-metric-parity.staging.spec.ts).
//
// Test-Artefakte (Ort + Preset) tragen das reservierte E2E-GZ--Praefix und
// werden im `finally`-Block sowie ueber global.teardown.ts (Praefix-Sweep)
// bereinigt.

import { test, expect, type Page, type Request } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { createTestLocation, createTestComparePreset, cleanupTracked } from './helpers';

function collectPutRequests(page: Page, urlSubstring: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(urlSubstring)) {
			puts.push(req);
		}
	});
	return puts;
}

test.describe('Issue #1350 Teil 2 AC-1: Compare-Auswahlliste aus GET /api/compare/metrics (Staging)', () => {
	test.beforeEach(async ({ page, baseURL }) => {
		assertNotProdBaseURL(baseURL ?? '');
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-1: Auswahlliste zeigt so viele Zeilen wie der Endpoint liefert, in Endpoint-Reihenfolge', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T2-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T2-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T2-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T2-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			// Endpoint-Reihenfolge/-Anzahl direkt abfragen — Vergleichsmaßstab,
			// nicht die alte COMPARE_METRIC_DEFS-Konstante.
			const metricsRes = await request.get('/api/compare/metrics');
			expect(metricsRes.ok(), `GET /api/compare/metrics HTTP ${metricsRes.status()}`).toBeTruthy();
			const catalog = (await metricsRes.json()) as { metrics: Array<{ key: string; label: string }> };

			await page.goto(`/compare/${preset.id}?tab=wetter-metriken`);
			const list = page.locator('[data-testid="weather-metrics-vergleich-list"]');
			await list.waitFor({ state: 'visible', timeout: 15000 });

			const rows = list.locator('[data-testid^="weather-metrics-vergleich-row-"]');
			await expect(rows).toHaveCount(catalog.metrics.length, { timeout: 10000 });

			for (let i = 0; i < catalog.metrics.length; i++) {
				const row = page.locator(
					`[data-testid="weather-metrics-vergleich-row-${catalog.metrics[i].key}"]`
				);
				await expect(row).toBeVisible();
				await expect(row).toContainText(catalog.metrics[i].label);
			}

			await page.screenshot({
				path: '../docs/artifacts/fix-1350-compare-metric-select/ac-1-list-from-endpoint.png'
			});
		} finally {
			await cleanupTracked(request);
		}
	});

	// AC-3 Regressionsschutz: der Wechsel der Auswahlliste auf die Endpoint-
	// Quelle darf die bestehende Persistenz-Kette (toggleCompareMetric ->
	// display_config.active_metrics) nicht veraendern — genau ein PUT pro
	// Klick, korrekter Key, Preset laedt nach Reload mit der neuen Auswahl.
	test('AC-3: Toggle schreibt korrekten Key, genau ein Save, Auswahl persistiert', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T2-AC3-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T2-AC3-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T2-AC3-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T2-AC3-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			await page.goto(`/compare/${preset.id}?tab=wetter-metriken`);
			await page
				.locator('[data-testid="weather-metrics-vergleich-list"]')
				.waitFor({ state: 'visible', timeout: 15000 });

			const row = page.locator('[data-testid="weather-metrics-vergleich-row-temp_max_c"]');
			await expect(row).toBeVisible({ timeout: 10000 });
			const checkbox = row.locator('input');
			const wasChecked = await checkbox.isChecked();

			const puts = collectPutRequests(page, `/api/compare/presets/${preset.id}`);
			const putPromise = page.waitForResponse(
				(r) =>
					r.url().includes(`/api/compare/presets/${preset.id}`) && r.request().method() === 'PUT',
				{ timeout: 8000 }
			);
			await checkbox.click();
			const putRes = await putPromise;
			expect(putRes.ok(), 'PUT (temp_max_c umschalten) fehlgeschlagen: ' + putRes.status()).toBeTruthy();
			await page.waitForTimeout(700);

			expect(puts.length, 'genau ein PUT pro Toggle-Klick').toBe(1);

			const body = puts[0].postDataJSON() as {
				display_config?: { active_metrics?: string[] };
			};
			const savedActive = body.display_config?.active_metrics ?? [];
			if (wasChecked) {
				expect(savedActive, 'PUT-Payload: temp_max_c wurde abgewaehlt').not.toContain('temp_max_c');
			} else {
				expect(savedActive, 'PUT-Payload: temp_max_c wurde angewaehlt').toContain('temp_max_c');
			}

			const getRes = await page.request.get(`/api/compare/presets/${preset.id}`);
			const savedPreset = await getRes.json();
			const persistedActive = savedPreset.display_config?.active_metrics ?? [];
			if (wasChecked) {
				expect(persistedActive, 'GET-Roundtrip: temp_max_c bleibt abgewaehlt').not.toContain(
					'temp_max_c'
				);
			} else {
				expect(persistedActive, 'GET-Roundtrip: temp_max_c bleibt angewaehlt').toContain(
					'temp_max_c'
				);
			}

			// Bestehendes Preset laedt nach Reload mit unveraendert der neuen Auswahl.
			await page.goto(`/compare/${preset.id}?tab=wetter-metriken`);
			await page
				.locator('[data-testid="weather-metrics-vergleich-list"]')
				.waitFor({ state: 'visible', timeout: 15000 });
			const rowAfterReload = page.locator(
				'[data-testid="weather-metrics-vergleich-row-temp_max_c"]'
			);
			const checkboxAfterReload = rowAfterReload.locator('input');
			await expect(checkboxAfterReload).toHaveJSProperty('checked', !wasChecked, { timeout: 8000 });

			await page.screenshot({
				path: '../docs/artifacts/fix-1350-compare-metric-select/ac-3-toggle-persist.png'
			});

			// Test-Hygiene: Ausgangszustand des Ausgangs-Presets wiederherstellen
			// (Toggle zurueck), auch wenn cleanupTracked das Preset gleich darauf
			// loescht — analog "mail_to zurueckstellen"-Konvention bei Staging-E2E.
			const restorePromise = page.waitForResponse(
				(r) =>
					r.url().includes(`/api/compare/presets/${preset.id}`) && r.request().method() === 'PUT',
				{ timeout: 8000 }
			);
			await checkboxAfterReload.click();
			await restorePromise;
			await page.waitForTimeout(500);
		} finally {
			await cleanupTracked(request);
		}
	});

	test('AC-5: reines Öffnen des Vergleich-Editors löst keinen PUT auf /api/compare/** aus', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T2-AC5-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T2-AC5-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T2-AC5-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T2-AC5-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			const puts = collectPutRequests(page, '/api/compare/');
			await page.goto(`/compare/${preset.id}?tab=wetter-metriken`);
			await page
				.locator('[data-testid="weather-metrics-vergleich-list"]')
				.waitFor({ state: 'visible', timeout: 15000 });
			await page.waitForLoadState('networkidle');
			await page.waitForTimeout(500);

			expect(
				puts.length,
				`AC-5 FAIL: reines Laden des Katalogs loeste ${puts.length} PUT(s) aus — Ladevorgang darf kein Save sein`
			).toBe(0);
		} finally {
			await cleanupTracked(request);
		}
	});

	// AC-4 (Fehlerpfad bei Endpoint-Ausfall): der ECHTE Staging-Dienst wird
	// NICHT gestoert. Stattdessen faengt Playwright im BROWSER die Anfrage an
	// GET /api/compare/metrics ab, bevor sie das Netz verlaesst — das ist
	// Fehlerinjektion auf Transport-Ebene der eigenen Testsitzung, kein
	// Mock-Theater (kein Ersetzen von Anwendungscode/Verhalten, nur der
	// Response fuer diese Seite). Der Rest der Anwendung (Login, andere
	// Endpoints) bleibt unberuehrt.
	test('AC-4: sichtbarer Fehlerzustand + Wiederholen-Button bei Endpoint-Fehler', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T2-AC4-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T2-AC4-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T2-AC4-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T2-AC4-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			await page.route('**/api/compare/metrics', (route) =>
				route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
			);

			await page.goto(`/compare/${preset.id}?tab=wetter-metriken`);

			const errorShell = page.locator('[data-testid="weather-metrics-vergleich-load-error"]');
			await expect(errorShell).toBeVisible({ timeout: 15000 });

			const retryBtn = page.locator('[data-testid="weather-metrics-vergleich-load-retry"]');
			await expect(retryBtn).toBeVisible();

			const list = page.locator('[data-testid="weather-metrics-vergleich-list"]');
			await expect(list).toHaveCount(0);
			await expect(page.locator('[data-testid^="weather-metrics-vergleich-row-"]')).toHaveCount(0);

			// Fehler beheben (Route entfernen) und ueber "Wiederholen" den echten
			// Endpoint erneut ansprechen — belegt Retry-Erfolg und (in Verbindung
			// mit F001) dass kein Doppel-Fetch/Auto-Retry-Loop haengt.
			await page.unroute('**/api/compare/metrics');
			await retryBtn.click();
			await expect(list).toBeVisible({ timeout: 15000 });

			await page.screenshot({
				path: '../docs/artifacts/fix-1350-compare-metric-select/ac-4-error-then-retry.png'
			});
		} finally {
			await cleanupTracked(request);
		}
	});
});
