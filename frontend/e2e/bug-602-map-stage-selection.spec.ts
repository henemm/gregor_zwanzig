// Playwright E2E — Bug #602: Karte zeigt immer Etappe 1
//
// Spec: docs/specs/modules/bug_602_map_stage_selection.md
//
// Root Cause: Svelte 5 $effect in MapCanvas trackt `stage` nicht reaktiv
// (async gelesen) → Karte rendert nie neu bei Stage-Wechsel.
// Fix: {#key activeStageId} in EditStagesPanelNew erzwingt Remount.
//
// Verifikationsstrategie (DOM-Fingerprinting):
//   Ohne {#key} bleibt derselbe DOM-Knoten → custom property persistiert.
//   Mit {#key} wird der Knoten destroyed + re-created → property weg.
//
// Ausführung:
//   cd frontend && npx playwright test bug-602-map-stage-selection.spec.ts

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

// Zielt auf die Desktop-Karte (map-card enthält den map-canvas im editor-grid)
const DESKTOP_MAP_CANVAS = '[data-testid="map-card"] [data-testid="map-canvas"]';

// =============================================================================
// AC-1: Etappe 2 wählen → map-canvas wird remounted (neues DOM-Element)
// =============================================================================

test('AC-1: Etappe 2 wählen → map-canvas wird remounted', async ({ page }) => {
	await page.goto(`/trips/${TRIP_ID}`);
	await page.getByTestId('trip-detail-tab-stages').click();

	// Stages-Panel muss geladen sein
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });
	await expect(page.locator(DESKTOP_MAP_CANVAS)).toBeVisible({ timeout: 10_000 });

	// Stage-1-Fingerprint setzen
	await page.evaluate((sel) => {
		const el = document.querySelector(sel);
		if (el) (el as unknown as Record<string, unknown>)['__bug602_stage1__'] = true;
	}, DESKTOP_MAP_CANVAS);

	// Auf Stage 2 wechseln
	await page.getByTestId('stage-card-1').click();

	// Warten bis neues map-canvas-Element erscheint (ohne Stage-1-Property)
	await page.waitForFunction(
		(sel) => {
			const el = document.querySelector(sel);
			return el !== null && !(el as unknown as Record<string, unknown>)['__bug602_stage1__'];
		},
		DESKTOP_MAP_CANVAS,
		{ timeout: 5_000 }
	);

	const isNewElement = await page.evaluate((sel) => {
		const el = document.querySelector(sel);
		return !(el as unknown as Record<string, unknown>)['__bug602_stage1__'];
	}, DESKTOP_MAP_CANVAS);
	expect(isNewElement).toBe(true);
});

// =============================================================================
// AC-2: Zurück zu Etappe 1 → map-canvas wird erneut remounted
// =============================================================================

test('AC-2: Zurück zu Etappe 1 → map-canvas wird erneut remounted', async ({ page }) => {
	await page.goto(`/trips/${TRIP_ID}`);
	await page.getByTestId('trip-detail-tab-stages').click();

	await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });
	await expect(page.locator(DESKTOP_MAP_CANVAS)).toBeVisible({ timeout: 10_000 });

	// Auf Stage 2 wechseln
	await page.getByTestId('stage-card-1').click();
	await expect(page.locator(DESKTOP_MAP_CANVAS)).toBeVisible({ timeout: 10_000 });

	// Stage-2-Fingerprint setzen
	await page.evaluate((sel) => {
		const el = document.querySelector(sel);
		if (el) (el as unknown as Record<string, unknown>)['__bug602_stage2__'] = true;
	}, DESKTOP_MAP_CANVAS);

	// Zurück zu Stage 1
	await page.getByTestId('stage-card-0').click();

	// Warten bis neues map-canvas-Element erscheint (ohne Stage-2-Property)
	await page.waitForFunction(
		(sel) => {
			const el = document.querySelector(sel);
			return el !== null && !(el as unknown as Record<string, unknown>)['__bug602_stage2__'];
		},
		DESKTOP_MAP_CANVAS,
		{ timeout: 5_000 }
	);

	const isNewElement = await page.evaluate((sel) => {
		const el = document.querySelector(sel);
		return !(el as unknown as Record<string, unknown>)['__bug602_stage2__'];
	}, DESKTOP_MAP_CANVAS);
	expect(isNewElement).toBe(true);
});

// =============================================================================
// AC-3: Etappe ohne Wegpunkte → kein Absturz, Panel bleibt bedienbar
// =============================================================================

test('AC-3: Etappe ohne Wegpunkte → kein Absturz, Seite bleibt bedienbar', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (err) => errors.push(err.message));

	await page.goto(`/trips/${TRIP_ID}`);
	await page.getByTestId('trip-detail-tab-stages').click();

	// Stage 3 (0 Wegpunkte / Pausenetappe) wählen
	await page.getByTestId('stage-card-2').click();

	await page.waitForTimeout(500);

	// Keine ungefangenen JS-Fehler
	expect(errors).toEqual([]);

	// edit-stages-panel (die echte Komponente, WaypointsPanel ist dead code)
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
});
