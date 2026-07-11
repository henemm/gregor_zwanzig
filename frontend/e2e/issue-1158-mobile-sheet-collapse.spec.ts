// TDD RED — Issue #1158: Wegpunkte-Schublade im Mobile-Trip-Editor einklappbar.
//
// Spec: docs/specs/modules/issue_1158_mobile_sheet_close.md (AC-1 bis AC-7)
//
// RED-Grund: Sheet.svelte (variant="embedded") hat aktuell weder eine vierte
// "collapsed"-Snap-Stufe noch einen Klick-Handler auf der Griffleiste
// (data-testid="sheet-handle" existiert im Code noch nicht) — jede Assertion,
// die auf dieses Element wartet, schlägt per Timeout fehl, bis Phase 6 die
// Collapse-Funktion einführt. AC-5/AC-6 prüfen unverändertes Bestandsverhalten
// (Regressionsschutz) und dürfen bereits heute grün sein.
//
// Ausführen: cd frontend && npx playwright test e2e/issue-1158-mobile-sheet-collapse.spec.ts

import { test, expect, type Page } from '@playwright/test';
import * as path from 'node:path';

const TRIP_ID = 'e2e-1158-mobile-sheet';
const TRIP_NAME = 'E2E #1158 Mobile Sheet Collapse';
const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 800 };

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] }
	],
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00'
	}
};

async function openMobileStagesEditor(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('mobile-editor')).toBeVisible();
}

function handle(page: Page) {
	return page.getByTestId('sheet-handle');
}
function sheetRoot(page: Page) {
	return page.locator('[data-snap]');
}
async function sheetHeight(page: Page): Promise<number> {
	return sheetRoot(page).evaluate((el) => el.getBoundingClientRect().height);
}
// Issue #963 — Map-First-Reorder korrigiert `.mobile-editor` auf die tatsächlich
// verfügbare Höhe (statt vorher fälschlich ~voller Viewport-Höhe). Sheet-%-Werte
// (full/half/peek) sind relativ zu `.mobile-editor`, NICHT zum Viewport — die
// Snap-Höhen-Assertions müssen daher gegen die echte Container-Höhe verifizieren,
// nicht gegen `vh` (Bug docs: docs/artifacts/fix-963-mobile-editor-controls/).
async function containerHeight(page: Page): Promise<number> {
	return page.getByTestId('mobile-editor').evaluate((el) => el.getBoundingClientRect().height);
}

test.describe('Issue #1158 — Wegpunkte-Schublade einklappbar (Mobile)', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});
	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('AC-1: Tap auf Griffleiste klappt Schublade auf ≤64px — Karte frei antippbar', async ({
		page
	}) => {
		await openMobileStagesEditor(page);

		await handle(page).click();
		const height = await sheetHeight(page);
		expect(height, `Schublade ist ${height}px hoch statt ≤64px`).toBeLessThanOrEqual(64);

		// Issue #963 (Fix-Loop 3, F004-Folgekorrektur): `.mobile-editor` ist jetzt
		// BottomNav-bewusst dimensioniert (siehe EditStagesPanelNew.svelte) und dadurch
		// bei manchen Trip-Namen deutlich niedriger als vorher (hier real ≈135px statt
		// vormals ~788px). Die ursprüngliche Klick-Position (5%,50%) lag im geschrumpften
		// Layout innerhalb des Leaflet-Zoom-Controls (oben links) statt auf der Karte —
		// (25%,50%) trifft zuverlässig den Karten-Hintergrund (fern von Zoom-Control
		// oben-links, MapControl-Cluster oben-rechts und der Marker-Spalte in der Mitte).
		// Kurze Wartezeit lässt Leaflets `fitBounds`-Übergang abschließen, bevor geklickt
		// wird (vermeidet Flakiness durch noch verschiebende Marker-Positionen).
		await page.waitForTimeout(300);
		const map = page.getByTestId('mobile-editor').getByTestId('map-canvas');
		const box = await map.boundingBox();
		if (!box) throw new Error('map-canvas nicht gefunden');
		await map.click({ position: { x: box.width * 0.25, y: box.height * 0.5 } });

		// Persistenz ans Backend ist ein separates, vorbestehendes Thema
		// (handleMapClick ruft aktuell kein scheduleSave/save auf — Folge-Issue).
		// Hier wird geprüft, dass der Kartentipp im UI-State nachweislich einen
		// dritten Wegpunkt anlegt (Seed hat 2 Wegpunkte, Index 0 und 1).
		await handle(page).click(); // wieder ausklappen
		await expect(page.getByTestId('waypoint-list').getByTestId('waypoint-card-2')).toBeVisible();
	});

	test('AC-2: erneuter Tap auf Griffleiste klappt Schublade wieder auf', async ({ page }) => {
		await openMobileStagesEditor(page);

		await handle(page).click(); // collapse
		expect(await sheetHeight(page)).toBeLessThanOrEqual(64);

		await handle(page).click(); // expand
		const height = await sheetHeight(page);
		// Issue #963: Schwelle war 200px (fixer Wert, implizit gegen die vorher
		// fälschlich fast-viewport-hohe Karte kalibriert) — jetzt gegen die echte
		// (kleinere, aber stabile) `.mobile-editor`-Höhe geprüft: 'half' ≈ 55%.
		const ch = await containerHeight(page);
		expect(height, `Schublade ist nach Re-Expand nur ${height}px hoch (Container ${ch}px)`).toBeGreaterThan(ch * 0.4);
		await expect(page.getByTestId('waypoint-list').getByTestId('waypoint-card-0')).toBeVisible();
	});

	test('AC-3: Sheet blockiert Tab-Leiste/Speicher-Status nicht dauerhaft', async ({ page }) => {
		await openMobileStagesEditor(page);

		const cycle = page.getByTestId('snap-cycle');
		await cycle.click(); // half -> full
		await expect(cycle).toContainText('full');

		// Tab-Leiste liegt oben und bleibt unabhängig vom Sheet-Zustand klickbar.
		await page.getByTestId('trip-detail-tab-weather').click();
		await expect(page.getByTestId('trip-detail-panel-weather')).toBeVisible();

		await page.getByTestId('trip-detail-tab-stages').click();
		await expect(page.getByTestId('mobile-editor')).toBeVisible();

		// Nach dem Einklappen (Griffleiste) darf der Speicher-Status (Issue #758,
		// unten rechts fix positioniert) nicht mehr von der Schublade verdeckt sein.
		await handle(page).click();
		expect(await sheetHeight(page)).toBeLessThanOrEqual(64);

		const indicator = page.getByTestId('save-indicator');
		await expect(indicator).toBeVisible();
		const box = await indicator.boundingBox();
		if (!box) throw new Error('save-indicator nicht gefunden');
		const hitsSheet = await page.evaluate(
			([x, y]) => !!document.elementFromPoint(x, y)?.closest('[data-snap]'),
			[box.x + box.width / 2, box.y + box.height / 2]
		);
		expect(hitsSheet, 'Speicher-Status wird von der Schublade verdeckt').toBe(false);
	});

	test('AC-4: identisches Verhalten im Trip-Anlage-Wizard (Etappen-Schritt)', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');
		await page.getByTestId('trip-new-name-input-mobile').fill('E2E #1158 Wizard');
		await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

		const tabbar = page.getByTestId('tn-mobile-tabbar');
		await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

		const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
		// GPX in JEDE Etappe laden. Der Datei-Input einer Etappe verschwindet aus dem
		// DOM, sobald deren GPX gesetzt ist — daher immer den ERSTEN verbleibenden
		// offenen Input neu auflösen, kein `.nth(i)` (Muster: issue-776-metrics-toggle.spec.ts).
		const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
		for (let i = 0; i < stageCount; i++) {
			const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
			await Promise.all([
				page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
				input.setInputFiles(gpx)
			]);
			await page.waitForTimeout(600);
		}

		await tabbar.getByRole('tab', { name: /Wegpunkte/ }).click({ force: true });

		const mobileHandle = page.locator('.tn-mobile [data-testid="sheet-handle"]');
		const mobileSheet = page.locator('.tn-mobile [data-snap]');
		await expect(mobileHandle).toBeVisible();

		await mobileHandle.click(); // collapse
		let height = await mobileSheet.evaluate((el) => el.getBoundingClientRect().height);
		expect(height, `Wizard-Schublade ist ${height}px hoch statt ≤64px`).toBeLessThanOrEqual(64);

		await mobileHandle.click(); // expand
		height = await mobileSheet.evaluate((el) => el.getBoundingClientRect().height);
		expect(height, `Wizard-Schublade bleibt nach Re-Expand nur ${height}px hoch`).toBeGreaterThan(
			200
		);
	});

	test('AC-5: Desktop (>=900px) zeigt unverändert das Grid ohne Bottom-Sheet', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto(`/trips/${TRIP_ID}?tab=stages`);
		await expect(page.getByTestId('editor-grid')).toBeVisible();

		const display = await page
			.getByTestId('mobile-editor')
			.evaluate((el) => getComputedStyle(el).display);
		expect(display, 'mobile-editor sollte auf Desktop display:none sein').toBe('none');
	});

	test('AC-6: modales Sheet (Etappen-Auswahl) bleibt unverändert', async ({ page }) => {
		await openMobileStagesEditor(page);

		await page.getByTestId('stage-switcher-pill').click();
		const overlay = page.locator('div[role="presentation"]');
		await expect(overlay).toBeVisible();
		const bodyOverflow = await page.evaluate(() => document.body.style.overflow);
		expect(bodyOverflow).toBe('hidden');

		await page.getByRole('button', { name: 'Schliessen' }).click();
		await expect(overlay).toHaveCount(0);
		const bodyOverflowAfter = await page.evaluate(() => document.body.style.overflow);
		expect(bodyOverflowAfter).not.toBe('hidden');
	});

	test('AC-7: Höhe-wechseln-Button durchläuft alle vier Stufen', async ({ page }) => {
		await openMobileStagesEditor(page);
		const cycle = page.getByTestId('snap-cycle');
		// Issue #963: Sheet-%-Werte sind relativ zu `.mobile-editor`, nicht zum
		// Viewport — vorher zufällig fast identisch, weil `.mobile-editor` fälschlich
		// fast die volle `dvh`-Höhe hatte. Jetzt korrekt gegen die echte (kleinere)
		// Container-Höhe geprüft.
		const ch = await containerHeight(page);

		await cycle.click(); // half -> full
		await expect(cycle).toContainText('full');
		let h = await sheetHeight(page);
		expect(h, `full: ${h}px (Container ${ch}px)`).toBeGreaterThan(ch * 0.7);

		await cycle.click(); // full -> collapsed
		await expect(cycle).toContainText('collapsed');
		h = await sheetHeight(page);
		expect(h, `collapsed: ${h}px`).toBeLessThanOrEqual(64);

		await cycle.click(); // collapsed -> peek
		await expect(cycle).toContainText('peek');
		h = await sheetHeight(page);
		expect(h, `peek: ${h}px (Container ${ch}px)`).toBeGreaterThan(ch * 0.15);
		expect(h, `peek: ${h}px (Container ${ch}px)`).toBeLessThan(ch * 0.45);

		await cycle.click(); // peek -> half
		await expect(cycle).toContainText('half');
		h = await sheetHeight(page);
		expect(h, `half: ${h}px (Container ${ch}px)`).toBeGreaterThan(ch * 0.4);
		expect(h, `half: ${h}px (Container ${ch}px)`).toBeLessThan(ch * 0.65);
	});
});
