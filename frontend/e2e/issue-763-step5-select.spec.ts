// E2E — Issue #763: Step5Versand „Horizont"-Select auf Design-System Select.svelte migrieren
//
// Spec: docs/specs/modules/issue_763_step5_forecast_select.md
//
// Verhaltensnachweis (DOM/Verhalten, KEIN Quelltext-Grep) als eingeloggter Nutzer
// gegen den lokalen Preview-Server (http://localhost:4173, webServer auto-start).
//
// RED-Erwartung (vor Migration):
//   AC-1/AC-3: FAIL — der native <select> liegt NICHT in einem .gz-select-Wrapper,
//              es existiert kein .gz-select__chevron neben dem Feld.
//   AC-2:      Number-Typ muss erhalten bleiben (forecast_hours === 72, nicht "72").
//   AC-4:      Genau drei Optionen mit Werten 24/48/72.
//
// Ausführen (lokal):
//   cd frontend && npx playwright test e2e/issue-763-step5-select.spec.ts

import { test, expect, type Locator, type Page } from '@playwright/test';

const FORECAST_HOURS_TESTID = 'compare-step5-forecast-hours';

// CompareEditor rendert Markup doppelt (.cm-desktop + .cm-mobile). Bei 1280px ist
// .cm-mobile display:none → alle Interaktionen auf den sichtbaren Desktop-Block scopen.
function desktop(page: Page): Locator {
	return page.locator('.cm-desktop');
}

// ── Hilfsfunktion: legt einen Compare-Preset an (mandantengebunden, echte API) ──
async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string }> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'Issue763 E2E ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['issue763-test@example.com'],
			display_config: {},
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id };
}

// ── Hilfsfunktion: zwei echte Locations anlegen (für Create-Flow) ──────────────
async function createTwoLocations(
	page: Page
): Promise<{ nameA: string; nameB: string }> {
	const suffix = Date.now();
	const nameA = 'Issue763-Ort-A-' + suffix;
	const nameB = 'Issue763-Ort-B-' + suffix;
	const [rA, rB] = await Promise.all([
		page.request.post('/api/locations', {
			data: { name: nameA, lat: 47.0, lon: 13.0, region: 'Issue763-Region' }
		}),
		page.request.post('/api/locations', {
			data: { name: nameB, lat: 47.1, lon: 13.1, region: 'Issue763-Region' }
		})
	]);
	expect(rA.ok() && rB.ok(), 'Location-Anlage fehlgeschlagen').toBeTruthy();
	return { nameA, nameB };
}

test.describe('Issue #763: Step5 Horizont-Select → Design-System Select', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Create-Flow — Horizont-Feld wird über Design-System gerendert ────
	test('AC-1: Versand-Tab im Create-Modus rendert Horizont als .gz-select mit Chevron', async ({
		page
	}) => {
		const { nameA, nameB } = await createTwoLocations(page);
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		const d = desktop(page);

		// Name → schaltet Orte-Tab frei
		await d.locator('[data-testid="compare-editor-name"]').fill('Issue763-Create ' + Date.now());

		// Orte-Tab: zwei Orte aus der Bibliothek wählen (schaltet Idealwerte frei)
		await d.locator('[data-testid="compare-editor-tab-orte"]').click();
		await d.locator('[data-testid="compare-step2-library"]').waitFor({ timeout: 8_000 });
		await d.locator('[data-testid="compare-step2-library"]').getByText(nameA, { exact: true }).click();
		await d.locator('[data-testid="compare-step2-library"]').getByText(nameB, { exact: true }).click();

		// Idealwerte besuchen (schaltet Layout frei) — Horizont-Feld liegt jetzt im
		// Layout-Tab (CompareReportContentSection, Issue #1232 Scheibe 2b).
		await d.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await d.locator('[data-testid="compare-editor-tab-layout"]').click();

		// Horizont-Feld liegt INNERHALB eines .gz-select-Wrappers (RED: nacktes <select>)
		const wrapped = d.locator(`.gz-select [data-testid="${FORECAST_HOURS_TESTID}"]`);
		await expect(wrapped).toBeVisible({ timeout: 8_000 });

		// Chevron neben dem Feld vorhanden
		const chevron = d.locator('.gz-select', {
			has: page.locator(`[data-testid="${FORECAST_HOURS_TESTID}"]`)
		}).locator('.gz-select__chevron');
		await expect(chevron).toBeVisible();
	});

	// ── AC-2: Number-Typ-Erhalt (kritisch) ────────────────────────────────────
	//
	// `state.forecastHours` ist number ($state(48)). Das Horizont-Tile leitet seine
	// Sub-Zeile per STRIKT-numerischem Vergleich ab:
	//   state.forecastHours === 24 ? 'heute' : === 48 ? 'morgen…' : 'übermorgen…'
	// Würde `bind:value` einen String ("24") liefern, schlägt `'24' === 24` fehl →
	// Sub-Zeile fiele auf den else-Zweig ('übermorgen + Folgetag') zurück. Die
	// Sub-Zeile "heute" beweist also den erhaltenen Number-Typ aus der DOM-Bindung —
	// ohne Save-Request (saveNewPreset sendet forecast_hours bewusst nicht).
	test('AC-2: 24h erhält den Number-Typ (Horizont-Tile zeigt "heute")', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		const d = desktop(page);

		await d.locator('[data-testid="compare-editor-tab-layout"]').click();

		const select = d.locator(`[data-testid="${FORECAST_HOURS_TESTID}"]`);
		await expect(select).toBeVisible({ timeout: 8_000 });

		// 24h wählen → Tile-Sub muss exakt "heute" sein (nur bei number 24)
		await select.selectOption('24');
		const tileSub = d.locator('[data-testid="compare-step5-horizon-tile"]');
		await expect(tileSub).toContainText('heute');
		await expect(tileSub).not.toContainText('übermorgen');

		// Gegenprobe: 48h → "morgen + übermorgen" (ebenfalls strikt-numerisch)
		await select.selectOption('48');
		await expect(tileSub).toContainText('morgen + übermorgen');
	});

	// ── AC-3: Edit-Routenabdeckung — gleiches Feld als .gz-select ──────────────
	test('AC-3: Edit-Modus Versand-Tab rendert Horizont als .gz-select (kein nacktes select)', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		const d = desktop(page);

		await d.locator('[data-testid="compare-editor-tab-layout"]').click();
		await expect(
			d.locator('[data-testid="compare-editor-tab-layout"]')
		).toHaveAttribute('data-active', 'true');

		// Feld liegt in einem .gz-select-Wrapper (RED: nacktes <select> → 0 Treffer)
		const wrapped = d.locator(`.gz-select [data-testid="${FORECAST_HOURS_TESTID}"]`);
		await expect(wrapped).toBeVisible({ timeout: 8_000 });

		// Chevron vorhanden
		const chevron = d.locator('.gz-select', {
			has: page.locator(`[data-testid="${FORECAST_HOURS_TESTID}"]`)
		}).locator('.gz-select__chevron');
		await expect(chevron).toBeVisible();
	});

	// ── AC-4: Genau drei Optionen mit Werten 24/48/72 ─────────────────────────
	test('AC-4: Horizont-Feld hat genau drei Optionen 24/48/72', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		const d = desktop(page);

		await d.locator('[data-testid="compare-editor-tab-layout"]').click();

		const select = d.locator(`[data-testid="${FORECAST_HOURS_TESTID}"]`);
		await expect(select).toBeVisible({ timeout: 8_000 });

		const optionValues = await select.locator('option').evaluateAll((opts) =>
			opts.map((o) => (o as HTMLOptionElement).value)
		);
		expect(optionValues).toEqual(['24', '48', '72']);
	});
});
