// Staging-Validierung (SKIZZE, noch nicht ausgeführt) — Issue #1350 Teil 3:
// Schwellen-Editor des Ortsvergleichs (CorridorEditor/CorridorEditorMobile,
// context="vergleich") bezieht seine CompareMetricDef-Objekte aus
// GET /api/compare/metrics statt aus dem statischen Frontend-Import
// compareMetricDefs.ts::ALL_METRICS.
//
// Spec: docs/specs/modules/compare_metric_ssot_final.md (AC-1, AC-4)
// Workflow: fix-1350-compare-metric-ssot-final
//
// RED-Hinweis: Teil 3 ist zum Zeitpunkt dieser RED-Phase noch nicht deployt —
// diese Specs sind eine Laufzeit-Skizze fuer die spaetere Staging-Verifikation
// (Phase 7) und werden JETZT NICHT ausgefuehrt (kein Staging-Netzzugriff aus
// der RED-Phase heraus). Testid-Namen sind an die Spec angelehnt
// ("data-testid, z.B. corridor-editor-vergleich-load-error/-loading") und
// muessen in GREEN gegen die tatsaechliche Implementierung bestaetigt werden.
// Wiederverwendet den bereits gueltigen storageState aus Issue #1332 (kein
// neuer Login-Request, Rate-Limit-Bucket #703) — analog
// fix-1350-compare-metric-select.staging.spec.ts (Teil 2).

import { test, expect, type Page, type Request } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { createTestLocation, createTestComparePreset, cleanupTracked } from './helpers';

// Analog Teil 2 (fix-1350-compare-metric-select.staging.spec.ts::collectPutRequests):
// zaehlt PUT-Requests auf den Compare-Save-Endpoint waehrend des Ladezyklus.
function collectPutRequests(page: Page, urlSubstring: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(urlSubstring)) {
			puts.push(req);
		}
	});
	return puts;
}

test.describe('Issue #1350 Teil 3 AC-1: Schwellen-Editor-Pool aus GET /api/compare/metrics (Staging)', () => {
	test.beforeEach(async ({ page, baseURL }) => {
		assertNotProdBaseURL(baseURL ?? '');
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-1: Pool im Idealwerte-Tab zeigt so viele Metriken wie der Endpoint liefert', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T3-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T3-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T3-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T3-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			const metricsRes = await request.get('/api/compare/metrics');
			expect(metricsRes.ok(), `GET /api/compare/metrics HTTP ${metricsRes.status()}`).toBeTruthy();
			const catalog = (await metricsRes.json()) as { metrics: Array<{ key: string; label: string }> };

			// TODO GREEN: Deep-Link-Query bestätigen (CompareTabs.svelte nutzt
			// heute ?tab=idealwerte für den Hub-Detail-Idealwerte-Tab, s.
			// CorridorEditor context="vergleich"-Einbettung).
			await page.goto(`/compare/${preset.id}?tab=idealwerte`);

			// GREEN bestätigt: CorridorEditor.svelte setzt data-testid="corridor-editor-vergleich"
			// auf den Wurzel-Container (unveraendert seit RED).
			const editor = page.locator('[data-testid="corridor-editor-vergleich"]');
			await editor.waitFor({ state: 'visible', timeout: 15000 });

			// Zeilen (bereits als Corridor gespeichert) + Pool-Rest zusammen
			// müssen der Endpoint-Anzahl entsprechen (kein Metrik verloren/erfunden).
			// GREEN bestätigt: Pool-Item-testid ist NEU (corridor-editor-pool-item-{metric},
			// Spec Punkt 6); Zeilen-testid ist der BESTEHENDE corridor-row-{metric}
			// (bewusst NICHT umbenannt — 4 andere E2E-Suiten haengen bereits daran).
			const poolEntries = page.locator('[data-testid^="corridor-editor-pool-item-"]');
			const rowEntries = page.locator('[data-testid^="corridor-row-"]');
			await expect(async () => {
				const total = (await poolEntries.count()) + (await rowEntries.count());
				expect(total).toBe(catalog.metrics.length);
			}).toPass({ timeout: 10000 });

			await page.screenshot({
				path: '../docs/artifacts/fix-1350-compare-metric-ssot-final/ac-1-threshold-pool-from-endpoint.png'
			});
		} finally {
			await cleanupTracked(request);
		}
	});

	// AC-4 (PUT-frei): analog Teil-2-AC-5 (fix-1350-compare-metric-select.staging.spec.ts) —
	// reines Laden (Mount -> Katalog-Fetch-Resolve, ohne Nutzer-Interaktion) darf kein
	// syncToWizard()-Schreiben/PUT ausloesen, das ueber das bestehende
	// Fresh-Create-Prefill-Verhalten hinausgeht (Spec AC-4). Navigations-/storageState-Pfad
	// wie AC-1 oben: bestehendes Preset, Idealwerte-Tab (kein Fresh-Create-Aufruf in dieser
	// Datei — der Fresh-Create-Prefill-Fall ist reines State-Schreiben ohne PUT und bereits
	// heute so, s. Spec Punkt 6; hier wird der Lesepfad eines bestehenden Presets geprueft,
	// analog den Schwester-Tests dieser Datei).
	test('AC-4 (PUT-frei): reines Öffnen des Schwellen-Editors löst keinen PUT auf /api/compare/presets/** aus', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T3-AC4PUT-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T3-AC4PUT-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T3-AC4PUT-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T3-AC4PUT-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			const puts = collectPutRequests(page, `/api/compare/presets/${preset.id}`);

			await page.goto(`/compare/${preset.id}?tab=idealwerte`);
			const editor = page.locator('[data-testid="corridor-editor-vergleich"]');
			await editor.waitFor({ state: 'visible', timeout: 15000 });

			// Kompletter Ladezyklus: Mount -> Katalog-Fetch-Resolve -> networkidle +
			// kurze Wartezeit (Guard gegen verzoegerte/asynchrone PUTs nach dem
			// $effect-Ladepfad, analog Teil-2-AC-5-Puffer).
			await page.waitForLoadState('networkidle');
			await page.waitForTimeout(500);

			expect(
				puts.length,
				`AC-4 FAIL: reines Laden des Schwellen-Editors loeste ${puts.length} PUT(s) auf /api/compare/presets/** aus — Ladevorgang darf kein Save sein`
			).toBe(0);
		} finally {
			await cleanupTracked(request);
		}
	});

	// AC-4 (Fehlerpfad bei Endpoint-Ausfall): der ECHTE Staging-Dienst wird NICHT
	// gestoert. Playwright faengt im BROWSER die Anfrage an GET /api/compare/metrics
	// ab, bevor sie das Netz verlaesst — Fehlerinjektion auf Transport-Ebene der
	// eigenen Testsitzung, kein Mock-Theater.
	test('AC-4: sichtbarer Fehlerzustand + Wiederholen-Button bei Endpoint-Fehler, kein gerenderter Pool', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createTestLocation(request, { name: `1350T3-AC4-A-${suffix}` });
		const locB = await createTestLocation(request, { name: `1350T3-AC4-B-${suffix}` });
		const locC = await createTestLocation(request, { name: `1350T3-AC4-C-${suffix}` });
		const preset = await createTestComparePreset(request, {
			name: `1350T3-AC4-${suffix}`,
			locationIds: [locA.id, locB.id, locC.id]
		});

		try {
			await page.route('**/api/compare/metrics', (route) =>
				route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
			);

			await page.goto(`/compare/${preset.id}?tab=idealwerte`);

			// GREEN bestätigt: testid wie in Spec Punkt 6 vorgeschlagen umgesetzt.
			const errorShell = page.locator('[data-testid="corridor-editor-vergleich-load-error"]');
			await expect(errorShell).toBeVisible({ timeout: 15000 });

			const retryBtn = page.locator('[data-testid="corridor-editor-vergleich-load-retry"]');
			await expect(retryBtn).toBeVisible();

			// Kein still leerer/kaputter Editor: keine Zeilen, kein Pool-Eintrag
			// gerendert, solange der Fehlerzustand aktiv ist.
			await expect(page.locator('[data-testid^="corridor-row-"]')).toHaveCount(0);
			await expect(page.locator('[data-testid^="corridor-editor-pool-item-"]')).toHaveCount(0);

			await page.unroute('**/api/compare/metrics');
			await retryBtn.click();
			await expect(page.locator('[data-testid="corridor-editor-vergleich"]')).toBeVisible({
				timeout: 15000
			});

			await page.screenshot({
				path: '../docs/artifacts/fix-1350-compare-metric-ssot-final/ac-4-threshold-error-then-retry.png'
			});
		} finally {
			await cleanupTracked(request);
		}
	});
});
