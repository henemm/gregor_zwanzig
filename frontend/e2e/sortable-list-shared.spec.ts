// E2E (Staging) — Issue #1272: Geteilter Sortier-Baustein (drag-to-sort überall)
//
// Spec:    docs/specs/modules/issue_1272_shared_sortable.md
// ADR:     docs/adr/0024-ein-sortier-baustein-svelte-dnd-action.md
// Context: docs/context/refactor-1272-drag-sort.md
//
// TDD RED: Diese Tests MÜSSEN vor der Implementierung scheitern.
//   AC-1 — SMS-Liste ist heute NICHT ziehbar (OutputLayoutEditor.svelte:139-176
//          rendert eine reine ▲/▼-Liste ohne dndzone) → Reihenfolge bleibt gleich.
//   AC-4 — Es gibt heute keinen fokussierbaren Sortier-Griff → Tastatur-Pfad fehlt.
//   AC-5 — Die ▲/▼-Buttons existieren heute noch (OutputLayoutEditor.svelte:149/158,
//          ActiveMetricRow.svelte:85/93) → Erwartung "null Treffer" scheitert.
//
// Daten-Setup nach dem etablierten Muster aus compare-hub-inline-edit.spec.ts:62-92:
// der Test legt seinen Vergleich selbst per API an und räumt ihn wieder ab — kein
// Verlass auf vorhandene Staging-Daten. Die Tabs werden danach echt geklickt.
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env
//   source /home/hem/gregor_zwanzig_staging/.env; set +a
//   npx playwright test --config=playwright.1272.staging.config.ts

import { test, expect, type Page, type Locator } from '@playwright/test';

// Pointer-basierte Drag-Simulation. `svelte-dnd-action` schaltet natives HTML5-Drag
// bewusst ab (`draggableEl.draggable = false`) und fährt eine eigene Pointer-Logik mit
// 3px-Schwelle (MIN_MOVEMENT_BEFORE_DRAG_START_PX) — Playwrights `locator.dragTo()`
// erzeugt nur EINEN Move-Schritt und reißt die Schwelle nicht zuverlässig.
// Übernommen aus dem etablierten Muster in compare-hub-inline-edit.spec.ts:22-38.
async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void> {
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

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const id = (await res.json()).id as string;
	createdLocationIds.push(id);
	return id;
}

async function createPreset(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wintersport',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const id = (await res.json()).id as string;
	createdIds.push(id);
	return id;
}

// Legt einen Vergleich an und öffnet dessen Layout-Tab auf dem SMS-Kanal.
// Tabs/Kanal werden echt geklickt (kein goto auf den Zielzustand).
async function openLayoutSms(page: Page): Promise<void> {
	const suffix = Date.now();
	const locA = await createLocation(page, `E2E 1272 Ort-A ${suffix}`, 47.26, 11.4);
	const locB = await createLocation(page, `E2E 1272 Ort-B ${suffix}`, 47.1, 11.29);
	const locC = await createLocation(page, `E2E 1272 Ort-C ${suffix}`, 47.05, 11.32);
	const id = await createPreset(page, `E2E 1272 Sortier ${suffix}`, [locA, locB, locC]);

	// Die Sortier-Liste sitzt im EDITOR (/compare/{id}/edit → CompareEditor.svelte:904),
	// nicht im Hub (/compare/{id} → CompareTabs.svelte), dessen Layout-Tab nur eine
	// Kanal-Übersicht zeigt. Vgl. Issue-Screenshot "04-edit-layout-desktop.png".
	await page.goto(`/compare/${id}/edit`);
	await page.waitForLoadState('networkidle');
	// Erst warten, bis der Editor hydratisiert ist — ein Klick davor markiert den Tab
	// zwar als aktiv, schaltet den Inhalt aber nicht um (beobachteter Race auf Staging).
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();

	// Desktop- und Mobil-Variante liegen gleichzeitig im DOM → Testids existieren doppelt.
	// Immer auf die sichtbare Variante einschränken (gilt auch für sms-row-/drag-handle).
	const layoutEditor = page.locator('[data-testid="layout-editor"]:visible');
	await expect(async () => {
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').click();
		await expect(layoutEditor).toBeVisible({ timeout: 5_000 });
	}).toPass({ timeout: 30_000 });
	// Kanal-Umschalter des geteilten LayoutTab (shared/layout-tab/LTChannelPicker.svelte:34)
	await page.locator('[data-testid="channel-tab-sms"]:visible').click();
	await expect(page.locator('[data-testid="sms-budget-display"]:visible')).toBeVisible();
}

// Liest die sichtbare Reihenfolge der SMS-Zeilen als Metrik-ID-Liste.
async function smsOrder(page: Page): Promise<string[]> {
	return page
		.locator('[data-testid^="sms-row-"]:visible')
		.evaluateAll((nodes) => nodes.map((n) => n.getAttribute('data-metric-id') ?? ''));
}

test.describe('#1272 — Geteilter Sortier-Baustein', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// AC-1: SMS-Liste per Maus sortierbar.
	test('AC-1: SMS-Metrik laesst sich per Maus an andere Position ziehen', async ({ page }) => {
		await openLayoutSms(page);

		const before = await smsOrder(page);
		expect(before.length, 'Test braucht mindestens 2 SMS-Metriken').toBeGreaterThanOrEqual(2);

		const first = page.locator(`[data-testid="sms-row-${before[0]}"]:visible`);
		const second = page.locator(`[data-testid="sms-row-${before[1]}"]:visible`);
		await dragDndZoneItem(page, first, second);

		const after = await smsOrder(page);
		expect(after[0], 'nach dem Ziehen muss die zweite Metrik vorne stehen').toBe(before[1]);
		expect(after[1]).toBe(before[0]);
	});

	// AC-4: Tastatur-Pfad ueber den fokussierbaren Griff.
	test('AC-4: Reihenfolge laesst sich ohne Maus ueber den Griff aendern', async ({ page }) => {
		await openLayoutSms(page);

		const before = await smsOrder(page);
		expect(before.length).toBeGreaterThanOrEqual(2);

		const handle = page.locator(
			`[data-testid="sms-row-${before[0]}"]:visible [data-testid="drag-handle"]`
		);
		await expect(handle, 'Sortier-Griff muss existieren und sichtbar sein').toBeVisible();

		await handle.focus();
		await page.keyboard.press('Space'); // Sortier-Modus an
		await page.keyboard.press('ArrowDown'); // eine Position nach unten
		await page.keyboard.press('Space'); // bestaetigen

		const after = await smsOrder(page);
		expect(after[0], 'nach ArrowDown muss die zweite Metrik vorne stehen').toBe(before[1]);
		expect(after[1]).toBe(before[0]);
	});

	// AC-5: Die ▲/▼-Buttons sind verschwunden.
	test('AC-5: keine Pfeil-Buttons mehr zum Sortieren', async ({ page }) => {
		await openLayoutSms(page);

		const before = await smsOrder(page);
		expect(before.length, 'Test braucht mindestens 1 SMS-Metrik').toBeGreaterThanOrEqual(1);

		await expect(
			page.getByRole('button', { name: 'Nach oben' }),
			'SMS-Liste darf keine "Nach oben"-Schaltflaeche mehr haben'
		).toHaveCount(0);
		await expect(
			page.getByRole('button', { name: 'Nach unten' }),
			'SMS-Liste darf keine "Nach unten"-Schaltflaeche mehr haben'
		).toHaveCount(0);
		await expect(
			page.locator('[data-testid^="metric-up-"]'),
			'Metrik-Zeilen duerfen keine metric-up-Buttons mehr haben'
		).toHaveCount(0);
		await expect(
			page.locator('[data-testid^="metric-down-"]'),
			'Metrik-Zeilen duerfen keine metric-down-Buttons mehr haben'
		).toHaveCount(0);
	});
});
