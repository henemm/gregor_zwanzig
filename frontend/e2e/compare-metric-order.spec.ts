// E2E (Staging) — Metrik-Reihenfolge im Ortsvergleich, AC-3.
//
// Spec: docs/specs/modules/compare_metric_order.md § Acceptance Criteria AC-3
//
// AC-3: "Nutzer verändert NUR die Reihenfolge der Metriken (keine an-/abgewählt)
// / Seite neu laden / die geänderte Reihenfolge ist noch da — sie wurde also
// tatsächlich GESPEICHERT, nicht nur auf dem Bildschirm bewegt."
//
// Zwei getrennte Nachweise, weil dieser Fix genau dazwischen scheitern kann
// (Kontext-Doku § Risiko 5 + Spec § 5):
//   1. Nach der Ziehgeste feuert TATSÄCHLICH ein PUT auf den Vergleich
//      (Diff-Guard `weatherMetricsCompareSave.norm()` sortiert heute vor dem
//      Vergleich → reine Umsortierung gilt als "keine Änderung" → kein PUT).
//   2. Nach Reload steht die Reihenfolge unverändert im Editor UND in
//      `display_config.active_metrics` des Presets.
// Nur (2) allein wäre kein Beweis: eine DOM-Bewegung ohne Persistenz sähe im
// selben Tab identisch aus, solange nicht neu geladen wird.
//
// Ausführen (gegen Staging, aus frontend/, NACH Push + Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.compare-metric-order.staging.config.ts
//
// HINWEIS: `frontend/playwright.compare-metric-order.staging.config.ts` fehlt
// noch — das Schreiben ausserhalb von `frontend/e2e/` ist in der RED-Phase
// gesperrt (edit_gate). Sie ist 1:1 nach
// `playwright.1256-s8d.staging.config.ts` anzulegen, mit
//   { name: 'setup',    testMatch: /compare-metric-order\.staging\.setup\.ts/ }
//   { name: 'chromium', testMatch: [/compare-metric-order\.spec\.ts/],
//     dependencies: ['setup'],
//     use: { storageState: 'playwright/.auth/staging-compare-metric-order.json' } }
// Kein `webServer`-Block: getestet wird die auf Staging deployte App selbst —
// GZ_API_BASE (Default = PRODUKTION, s. playwright.config.ts) spielt hier
// deshalb keine Rolle; zusätzlich sperrt `assertNotProdBaseURL` im Setup jeden
// Lauf gegen die Prod-Domain (#1265).
//
// Muster: compare-editor-autosave.spec.ts (PUT-Aufzeichnung, afterEach-Cleanup)
// + layout-tab-route.spec.ts (Pointer-Drag gegen svelte-dnd-action).
// Login über gespeicherten Sitzungszustand (storageState), NICHT per Test —
// der Login ist auf 30/h gedeckelt (reference_staging_e2e_storagestate_login_rate_limit).

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { createTestLocation } from './helpers';

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

// Drei gespeicherte Metriken (Frontend-Vokabular von display_config.active_metrics,
// s. compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID) — genug, um eine
// Umsortierung eindeutig zu erkennen, wenig genug für einen stabilen Drag.
const START_ORDER = ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h'];

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const loc = await createTestLocation(page.request, { name, lat, lon });
	createdLocationIds.push(loc.id);
	return loc.id;
}

async function createPreset(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			display_config: { active_metrics: [...START_ORDER] }
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdIds.push(body.id);
	return body.id as string;
}

/** Zeichnet jeden PUT auf diesen Vergleich auf (Speicher-Nachweis). */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

/**
 * Pointer-basierte Drag-Simulation gegen `svelte-dnd-action` (geteilter
 * SortableList, ADR-0024): die Bibliothek schaltet natives HTML5-Drag ab
 * (`draggableEl.draggable = false`) und hört nur auf Pointer-Events mit
 * 3px-Schwelle — Playwrights `locator.dragTo()` erzeugt nur EINEN Move-Schritt
 * und reißt diese Schwelle nicht. Übernommen aus layout-tab-route.spec.ts:23-48.
 */
async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void> {
	await source.scrollIntoViewIfNeeded();
	await target.scrollIntoViewIfNeeded();

	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('dragDndZoneItem: source/target ohne BoundingBox');

	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
	await page.mouse.down();
	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2 - 12, {
		steps: 6
	});
	await page.waitForTimeout(120);
	await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, {
		steps: 15
	});
	await page.waitForTimeout(120);
	await page.mouse.up();
}

/** Öffnet den Vergleich am Hub und wechselt per KLICK auf den Metriken-Tab. */
async function openMetricsTab(page: Page, id: string): Promise<Locator> {
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	// Validator-Fund (staging, reproduzierbar ~2/3): SvelteKit liefert die
	// Tab-Leiste server-gerendert VOR der Hydration aus — ein Klick, der vor
	// dem Attachen der Event-Listener ankommt, geht spurlos verloren (generische
	// SvelteKit-Race, nicht spezifisch fuer diesen Tab). `networkidle`
	// abwarten, bevor geklickt wird, macht den Klick deterministisch.
	await page.waitForLoadState('networkidle');
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 10_000 });
	return panel;
}

function reihenfolgeRows(panel: Locator): Locator {
	return panel.locator('[data-testid="wm2-reihenfolge-row"]');
}

async function metricOrderInEditor(panel: Locator): Promise<(string | null)[]> {
	return reihenfolgeRows(panel).evaluateAll((els) =>
		els.map((el) => el.getAttribute('data-metric-id'))
	);
}

test.describe('Issue #1359 Scheibe 1: Metrik-Reihenfolge im Ortsvergleich', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-3: Reihenfolge ziehen → PUT feuert → Reload zeigt neue Reihenfolge ──
	test('AC-3: Metrik ziehen speichert die Reihenfolge und überlebt den Reload', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1359 AC3 A ${suffix}`, 47.0, 11.0);
		const locB = await createLocation(page, `E2E 1359 AC3 B ${suffix}`, 47.1, 11.1);
		const locC = await createLocation(page, `E2E 1359 AC3 C ${suffix}`, 47.2, 11.2);
		const id = await createPreset(page, `E2E 1359 AC3 ${suffix}`, [locA, locB, locC]);

		const panel = await openMetricsTab(page, id);

		// Der Reihenfolge-Block muss im Vergleich überhaupt existieren
		// (heute route-exklusiv über ROUTE_ONLY_SECTIONS gesperrt).
		await expect(reihenfolgeRows(panel)).toHaveCount(START_ORDER.length, { timeout: 10_000 });
		expect(await metricOrderInEditor(panel)).toEqual(START_ORDER);

		// Nur ZIEHEN — keine Metrik an- oder abwählen (AC-3 wörtlich).
		const puts = collectPresetPuts(page, id);
		const source = panel.locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="sunny_hours_h"]'
		);
		const target = panel.locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="temp_max_c"]'
		);
		await dragDndZoneItem(page, source, target);

		const expectedOrder = ['sunny_hours_h', 'temp_max_c', 'wind_max_kmh'];
		await expect
			.poll(async () => metricOrderInEditor(panel), {
				message: 'AC-3: die gezogene Metrik muss sofort an der neuen Position stehen',
				timeout: 5_000
			})
			.toEqual(expectedOrder);

		// Nachweis 1: es wurde WIRKLICH gespeichert (nicht nur bewegt).
		await expect
			.poll(() => puts.length, {
				message:
					'AC-3: nach der Ziehgeste muss ein Speichervorgang (PUT) feuern — ' +
					'der Diff-Guard darf reine Umsortierung nicht als "keine Änderung" werten',
				timeout: 8_000
			})
			.toBeGreaterThan(0);

		const lastPut = puts[puts.length - 1].postDataJSON() as {
			display_config?: { active_metrics?: string[] };
		};
		expect(
			lastPut.display_config?.active_metrics,
			'AC-3: der PUT muss die neue Reihenfolge tragen'
		).toEqual(expectedOrder);

		// Nachweis 2: der Server hat sie behalten …
		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${id}`);
					return ((await r.json()).display_config ?? {}).active_metrics as string[];
				},
				{ message: 'AC-3: die Reihenfolge muss serverseitig persistent sein', timeout: 8_000 }
			)
			.toEqual(expectedOrder);

		// … und der Editor zeigt sie nach einem echten Reload weiterhin.
		const reloadedPanel = await openMetricsTab(page, id);
		await expect
			.poll(async () => metricOrderInEditor(reloadedPanel), {
				message: 'AC-3: nach dem Neuladen muss die gezogene Reihenfolge noch da sein',
				timeout: 10_000
			})
			.toEqual(expectedOrder);
	});

	// ── AC-6 (Editor-Anteil): fixierte Amtliche-Warnungen-Zeile ist erklärt ──
	// Die Zeile ist bewusst NICHT Teil der ziehbaren Liste (Known Limitation der
	// Spec); ohne sichtbaren Hinweis wirkte das wie ein Sortier-Fehler.
	test('AC-6: "Amtliche Warnungen" ist nicht Teil der ziehbaren Liste, aber erklärt', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1359 AC6 A ${suffix}`, 47.3, 11.3);
		const locB = await createLocation(page, `E2E 1359 AC6 B ${suffix}`, 47.4, 11.4);
		const locC = await createLocation(page, `E2E 1359 AC6 C ${suffix}`, 47.5, 11.5);
		const id = await createPreset(page, `E2E 1359 AC6 ${suffix}`, [locA, locB, locC]);

		const panel = await openMetricsTab(page, id);
		await expect(reihenfolgeRows(panel)).toHaveCount(START_ORDER.length, { timeout: 10_000 });

		const draggableIds = await metricOrderInEditor(panel);
		expect(
			draggableIds.some((m) => (m ?? '').includes('official') || (m ?? '').includes('warn')),
			'AC-6: Amtliche Warnungen darf keine ziehbare Listenzeile sein'
		).toBe(false);

		await expect(
			panel.getByText(/Amtliche Warnungen.*(immer|zuerst|erster Stelle)/i).first(),
			'AC-6: sichtbarer Hinweis, dass Amtliche Warnungen immer zuerst kommt'
		).toBeVisible({ timeout: 10_000 });
	});
});
