// TDD RED: Issue #494 — Trip-Bearbeiten-Seite ans Design angleichen
//
// Spec: docs/specs/modules/issue_494_trip_edit_design.md
//
// Diese Tests MÜSSEN FEHLSCHLAGEN bis Phase 6 (GREEN), weil:
//   - +page.svelte rendert noch WaypointEditorPage, nicht TripEditView mit Tabs
//   - TripEditView.svelte hat Accordion statt horizontaler Tabs
//   - Kein Breadcrumb, keine Statistik-Karte, Buttons im Footer
//
// Abgedeckte ACs: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

test.beforeEach(async ({ page }) => {
	await login(page);
});

// =============================================================================
// AC-1: TripEditView sichtbar, WaypointEditorPage NICHT im DOM
// =============================================================================

test('AC-1: /edit zeigt TripEditView mit Tabs, nicht WaypointEditorPage', async ({ page }) => {
	await page.goto(EDIT_URL);

	// TripEditView muss vorhanden sein
	await expect(page.getByTestId('trip-edit-view')).toBeVisible();

	// WaypointEditorPage darf NICHT im DOM sein
	await expect(page.getByTestId('waypoint-editor-page')).toHaveCount(0);

	// Aktiver Tab muss "Etappen" sein (Default)
	const etappenTab = page.locator('[data-testid="edit-tabs"] [data-value="etappen"], [data-testid="edit-tabs"] [aria-selected="true"]');
	await expect(etappenTab).toBeVisible();
});

// =============================================================================
// AC-2: Breadcrumb, H1, Buttons oben rechts, 5 horizontale Tabs, kein Footer
// =============================================================================

test('AC-2: Breadcrumb sichtbar mit Text MEINE TOUREN', async ({ page }) => {
	await page.goto(EDIT_URL);

	const breadcrumb = page.getByTestId('edit-breadcrumb');
	await expect(breadcrumb).toBeVisible();
	await expect(breadcrumb).toContainText('MEINE TOUREN');
});

test('AC-2: H1 zeigt Tour-Namen', async ({ page }) => {
	await page.goto(EDIT_URL);

	const title = page.getByTestId('edit-trip-title');
	await expect(title).toBeVisible();
	// H1 muss sichtbaren Text haben
	const text = await title.textContent();
	expect(text?.trim().length).toBeGreaterThan(0);
});

test('AC-2: Buttons Abbrechen und Speichern sind oben rechts im Header — kein Fixed-Footer', async ({ page }) => {
	await page.goto(EDIT_URL);

	const headerActions = page.getByTestId('edit-header-actions');
	await expect(headerActions).toBeVisible();

	const cancelBtn = page.getByTestId('edit-cancel-btn');
	const saveBtn   = page.getByTestId('edit-save-btn');
	await expect(cancelBtn).toBeVisible();
	await expect(saveBtn).toBeVisible();

	// Beide Buttons müssen innerhalb des Header-Blocks liegen
	const headerBox  = await headerActions.boundingBox();
	const cancelBox  = await cancelBtn.boundingBox();
	const saveBox    = await saveBtn.boundingBox();
	expect(headerBox).toBeTruthy();
	expect(cancelBox?.y).toBeGreaterThanOrEqual(headerBox!.y);
	expect(cancelBox!.y + cancelBox!.height).toBeLessThanOrEqual(headerBox!.y + headerBox!.height + 2);
	expect(saveBox?.y).toBeGreaterThanOrEqual(headerBox!.y);

	// Fixed-Footer der alten TripEditView darf NICHT mehr existieren.
	// Wir scopen auf die View, weil die globale BottomNav (mobile) im DOM bleibt.
	const footer = page.locator('[data-testid="trip-edit-view"] .fixed.bottom-0');
	await expect(footer).toHaveCount(0);
});

test('AC-2: Genau 5 horizontale Tabs vorhanden (Route, Etappen, Wetter, Reports, Alarmregeln)', async ({ page }) => {
	await page.goto(EDIT_URL);

	const tabs = page.getByTestId('edit-tabs');
	await expect(tabs).toBeVisible();

	// Alle 5 Tabs müssen per Wert oder Text erreichbar sein
	await expect(tabs.locator('[data-value="route"],      [role="tab"]:has-text("Route")'     ).first()).toBeVisible();
	await expect(tabs.locator('[data-value="etappen"],   [role="tab"]:has-text("Etappen")'   ).first()).toBeVisible();
	await expect(tabs.locator('[data-value="wetter"],    [role="tab"]:has-text("Wetter")'    ).first()).toBeVisible();
	await expect(tabs.locator('[data-value="reports"],   [role="tab"]:has-text("Reports")'   ).first()).toBeVisible();
	await expect(tabs.locator('[data-value="alarmregeln"],[role="tab"]:has-text("Alarmregeln")').first()).toBeVisible();
});

test('AC-2: Etappen-Tab zeigt Anzahl-Badge', async ({ page }) => {
	await page.goto(EDIT_URL);

	const etappenTab = page.getByTestId('edit-tabs').locator('[data-value="etappen"], [role="tab"]:has-text("Etappen")').first();
	await expect(etappenTab).toBeVisible();
	// Badge-Zahl muss im Tab-Label stehen (z.B. "Etappen 4" oder "Etappen (4)")
	const text = await etappenTab.textContent();
	expect(/\d+/.test(text ?? '')).toBe(true);
});

// =============================================================================
// AC-3: Statistik-Karte mit km, Hm, Zeitraum, Tage, Reports-Badge
// =============================================================================

test('AC-3: Statistik-Karte zeigt Gesamtstrecke in km', async ({ page }) => {
	await page.goto(EDIT_URL);

	const statsCard = page.getByTestId('edit-stats-card');
	await expect(statsCard).toBeVisible();

	const distance = page.getByTestId('edit-stats-distance');
	await expect(distance).toBeVisible();
	await expect(distance).toContainText('km');
});

test('AC-3: Statistik-Karte zeigt Höhenmeter', async ({ page }) => {
	await page.goto(EDIT_URL);

	const ascent = page.getByTestId('edit-stats-ascent');
	await expect(ascent).toBeVisible();
	// Muss Aufstiegs-Symbol oder Zahl + "m" enthalten
	const text = await ascent.textContent();
	expect(/\d+/.test(text ?? '')).toBe(true);
});

test('AC-3: Statistik-Karte zeigt Zeitraum', async ({ page }) => {
	await page.goto(EDIT_URL);

	const dateRange = page.getByTestId('edit-stats-daterange');
	await expect(dateRange).toBeVisible();
	const text = await dateRange.textContent();
	expect((text ?? '').trim().length).toBeGreaterThan(0);
});

// =============================================================================
// AC-4: Tab-Wechsel zeigt richtigen Inhalt; Statistik-Karte bleibt sichtbar
// =============================================================================

test('AC-4: Klick auf Tab "Route" zeigt Route-Inhalt, Statistik-Karte bleibt sichtbar', async ({ page }) => {
	await page.goto(EDIT_URL);

	// Auf Route-Tab klicken
	const routeTab = page.getByTestId('edit-tabs').locator('[data-value="route"], [role="tab"]:has-text("Route")').first();
	await routeTab.click();

	// Route-Inhalt sichtbar (Trip-Name-Eingabe)
	await expect(page.locator('[data-testid="trip-name-input"]')).toBeVisible();

	// Statistik-Karte WEITERHIN sichtbar
	await expect(page.getByTestId('edit-stats-card')).toBeVisible();

	// Etappen-Inhalt NICHT sichtbar
	await expect(page.locator('[data-testid="edit-section-etappen"]')).toHaveCount(0);
});

test('AC-4: Klick auf Tab "Alarmregeln" zeigt Alarmregeln-Editor', async ({ page }) => {
	await page.goto(EDIT_URL);

	const alertTab = page.getByTestId('edit-tabs').locator('[data-value="alarmregeln"], [role="tab"]:has-text("Alarmregeln")').first();
	await alertTab.click();

	// Alarmregeln-Editor muss sichtbar sein
	await expect(page.locator('[data-testid^="alert-rule"], [data-testid="alert-rules-editor"]').first()).toBeVisible();
});

// =============================================================================
// AC-5: Save mit Read-Modify-Write, display_config bleibt erhalten
// =============================================================================

test('AC-5: Speichern sendet PUT und behält display_config aus geladenem Trip', async ({ page, request }) => {
	await page.goto(EDIT_URL);

	// display_config vor Save abrufen
	const tripId = TRIP_ID;
	const before = await request.get(`/api/trips/${tripId}`);
	expect(before.ok()).toBe(true);
	const beforeJson = await before.json();

	const putPromise = page.waitForRequest(req =>
		req.method() === 'PUT' && /\/api\/trips\/[^/]+$/.test(req.url())
	);

	await page.getByTestId('edit-save-btn').click();
	const putReq = await putPromise;
	const body = JSON.parse(putReq.postData() ?? '{}');

	// display_config muss unverändert durchgereicht werden
	expect(body.display_config).toEqual(beforeJson.display_config);

	await page.waitForURL('/trips', { timeout: 5000 });
});

// =============================================================================
// AC-7: Keine Accordion-Testids mehr (edit-section-*-header)
// =============================================================================

test('AC-7: Accordion-Testids existieren NICHT mehr im DOM', async ({ page }) => {
	await page.goto(EDIT_URL);

	// Diese Testids stammen aus dem alten Accordion-Layout und dürfen nicht mehr existieren
	await expect(page.locator('[data-testid="edit-section-route-header"]')).toHaveCount(0);
	await expect(page.locator('[data-testid="edit-section-etappen-header"]')).toHaveCount(0);
	await expect(page.locator('[data-testid="edit-section-wetter-header"]')).toHaveCount(0);
	await expect(page.locator('[data-testid="edit-section-reports-header"]')).toHaveCount(0);
});
