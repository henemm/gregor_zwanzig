// TDD RED: Issue #407 — Dedizierter Wegpunkt-Editor-Screen für /trips/[id]/edit
//
// Spec: docs/specs/modules/issue_407_waypoint_editor_screen.md
//
// Diese Tests MÜSSEN FEHLSCHLAGEN bis Phase 6 (GREEN), weil:
//   - WaypointEditorPage.svelte existiert noch NICHT
//   - StageNavDropdown.svelte existiert noch NICHT
//   - AISuggestionBar.svelte existiert noch NICHT
//
// Abgedeckte ACs: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9,
//                 AC-10, AC-11, AC-12

// Deaktiviert in #494: Diese Tests beschreiben eine verworfene Architektur,
// in der /edit direkt WaypointEditorPage als Root-View öffnete.
// Die aktuelle Architektur (ab #500) lädt die TripEditView auf /edit;
// der WaypointEditor wird über Etappen-Kachel-Klick aktiviert.
// Tests NICHT löschen (historische Referenz) und NICHT aktivieren (Architektur überholt).
import { test, expect, devices } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

test.beforeEach(async ({ page }) => {
	await login(page);
});

// =============================================================================
// AC-1: Desktop — WaypointEditorPage ersetzt Akkordeon-Maske
// =============================================================================

test.skip('AC-1: Desktop zeigt WaypointEditorPage, nicht Akkordeon-Maske', async ({ page }) => {
	await page.goto(EDIT_URL);

	// NEU: Wegpunkt-Editor-Container muss sichtbar sein
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	// ALT: Akkordeon-Wrapper darf nicht mehr existieren
	await expect(page.getByTestId('trip-edit-view')).toHaveCount(0);

	// Desktop-Elemente: EtappenStrip, Karte, Profil, Sidebar
	await expect(page.getByTestId('etappen-strip')).toBeVisible();
	await expect(page.getByTestId('map-canvas')).toBeVisible();
	await expect(page.getByTestId('profile-editor')).toBeVisible();
	await expect(page.getByTestId('wp-editor-sidebar')).toBeVisible();
});

// =============================================================================
// AC-2: Etappen-Auswahl synchronisiert Karte, Profil und Sidebar
// =============================================================================

test.skip('AC-2: Etappen-Auswahl synchronisiert alle Panels', async ({ page }) => {
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	// Zweite StageCard klicken (Index 1)
	const card1 = page.getByTestId('stage-card-1');
	await expect(card1).toBeVisible();
	await card1.click();

	// Karte zeigt neue Stage (has-stage-id Attribut)
	const mapCanvas = page.getByTestId('map-canvas');
	await expect(mapCanvas).toBeVisible();

	// Sidebar: Wegpunkt-Zähler aktualisiert sich
	await expect(page.getByTestId('wp-editor-sidebar')).toBeVisible();
});

// =============================================================================
// AC-3: Mobile — KI-Vorschlag-Bar erscheint bei suggested Waypoints
// =============================================================================

test.skip('AC-3: Mobile Bottom-Sheet + KI-Vorschlag-Bar bei suggested Waypoints', async ({ browser }) => {
	// Staged: Trip mit einem suggested Waypoint patchen
	const apiCtx = await browser.newContext();
	const apiPage = await apiCtx.newPage();
	await login(apiPage);

	const tripRes = await apiPage.request.get(`/api/trips/${TRIP_ID}`);
	expect(tripRes.ok()).toBe(true);
	const trip = await tripRes.json();

	// Ersten Waypoint als suggested markieren
	const patched = structuredClone(trip);
	if (patched.stages?.[0]?.waypoints?.[0]) {
		patched.stages[0].waypoints[0].suggested = true;
	}
	const putRes = await apiPage.request.put(`/api/trips/${TRIP_ID}`, { data: patched });
	expect(putRes.ok()).toBe(true);
	await apiCtx.close();

	// Mobile Viewport
	const ctx = await browser.newContext({
		...devices['iPhone SE'],
		viewport: { width: 390, height: 844 },
	});
	const page = await ctx.newPage();
	await login(page);
	await page.goto(EDIT_URL);

	// Bottom-Sheet muss sichtbar/öffenbar sein
	await expect(page.getByTestId('wp-editor-sheet')).toBeVisible();

	// KI-Vorschlag-Bar muss erscheinen
	await expect(page.getByTestId('ai-suggestion-bar')).toBeVisible();

	await ctx.close();
});

// =============================================================================
// AC-4: KI-Vorschlag übernehmen → Bar verschwindet reaktiv
// =============================================================================

test.skip('AC-4: KI-Vorschlag übernehmen entfernt suggested-Flag reaktiv', async ({ browser }) => {
	// Trip mit suggested Waypoint vorbereiten
	const apiCtx = await browser.newContext();
	const apiPage = await apiCtx.newPage();
	await login(apiPage);

	const tripRes = await apiPage.request.get(`/api/trips/${TRIP_ID}`);
	const trip = await tripRes.json();
	const patched = structuredClone(trip);
	if (patched.stages?.[0]?.waypoints?.[0]) {
		patched.stages[0].waypoints[0].suggested = true;
	}
	await apiPage.request.put(`/api/trips/${TRIP_ID}`, { data: patched });
	await apiCtx.close();

	// Mobile
	const ctx = await browser.newContext({
		...devices['iPhone SE'],
		viewport: { width: 390, height: 844 },
	});
	const page = await ctx.newPage();
	await login(page);
	await page.goto(EDIT_URL);

	const acceptBtn = page.getByTestId('ai-suggestion-accept-btn');
	await expect(acceptBtn).toBeVisible();
	await acceptBtn.click();

	// Bar verschwindet nach Bestätigung
	await expect(page.getByTestId('ai-suggestion-bar')).toHaveCount(0);

	await ctx.close();
});

// =============================================================================
// AC-5: Speichern — PUT ohne suggested-Flags, redirect zu /trips
// =============================================================================

test.skip('AC-5: Speichern sendet PUT ohne suggested-Flags, redirectet zu /trips', async ({ page }) => {
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	let putBody: unknown = null;
	const putPromise = page.waitForRequest(req => {
		if (req.method() === 'PUT' && /\/api\/trips\//.test(req.url())) {
			putBody = req.postDataJSON();
			return true;
		}
		return false;
	});

	await page.getByTestId('wp-editor-save-btn').click();
	await putPromise;
	await page.waitForURL('/trips', { timeout: 8000 });

	// Kein suggested-Flag in den gespeicherten stages
	const body = putBody as { stages?: Array<{ waypoints?: Array<{ suggested?: boolean }> }> };
	const stages = body?.stages ?? [];
	const hasSuggested = stages.some(s =>
		s.waypoints?.some(w => w.suggested === true)
	);
	expect(hasSuggested).toBe(false);
});

// =============================================================================
// AC-6: Saving-State — Buttons disabled während PUT läuft
// =============================================================================

test.skip('AC-6: Speichern-Button ist disabled während des PUT-Calls', async ({ page }) => {
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	// Netzwerk verlangsamen
	await page.route('**/api/trips/**', async route => {
		await new Promise(r => setTimeout(r, 300));
		await route.continue();
	});

	const saveBtn = page.getByTestId('wp-editor-save-btn');
	await saveBtn.click();

	// Kurz danach: disabled
	await expect(saveBtn).toBeDisabled();
	await expect(page.getByTestId('wp-editor-cancel-btn')).toBeDisabled();

	await page.waitForURL('/trips', { timeout: 8000 });
});

// =============================================================================
// AC-7: Fehlerfall — saveError wird im Footer angezeigt
// =============================================================================

test.skip('AC-7: PUT-Fehler zeigt lesbare Fehlermeldung im Footer', async ({ page }) => {
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	// PUT-Request fehlschlagen lassen
	await page.route('**/api/trips/**', route => route.abort('failed'));

	await page.getByTestId('wp-editor-save-btn').click();

	// Fehlermeldung erscheint
	await expect(page.getByTestId('wp-editor-save-error')).toBeVisible({ timeout: 5000 });
});

// =============================================================================
// AC-8: Abbrechen — kein PUT, redirect zu /trips
// =============================================================================

test.skip('AC-8: Abbrechen navigiert ohne PUT zu /trips', async ({ page }) => {
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	let putCalled = false;
	page.on('request', req => {
		if (req.method() === 'PUT' && /\/api\/trips\//.test(req.url())) putCalled = true;
	});

	await page.getByTestId('wp-editor-cancel-btn').click();
	await page.waitForURL('/trips', { timeout: 5000 });

	expect(putCalled).toBe(false);
});

// =============================================================================
// AC-9: Mobile — TopAppBar mit Titel + StageNavDropdown
// =============================================================================

test.skip('AC-9: Mobile zeigt TopAppBar "Wegpunkt-Editor" + StageNavDropdown', async ({ browser }) => {
	const ctx = await browser.newContext({
		...devices['iPhone SE'],
		viewport: { width: 390, height: 844 },
	});
	const page = await ctx.newPage();
	await login(page);
	await page.goto(EDIT_URL);

	// TopAppBar Titel
	await expect(page.getByTestId('wp-editor-topbar')).toBeVisible();
	await expect(page.getByTestId('wp-editor-topbar')).toContainText('Wegpunkt-Editor');

	// Back-Button im TopAppBar
	await expect(page.getByTestId('wp-editor-back-btn')).toBeVisible();

	// Stage-Nav Dropdown mit Select + Prev/Next
	await expect(page.getByTestId('stage-nav-dropdown')).toBeVisible();
	await expect(page.getByTestId('stage-nav-dropdown').locator('select')).toBeVisible();
	await expect(page.getByTestId('stage-nav-prev-btn')).toBeVisible();
	await expect(page.getByTestId('stage-nav-next-btn')).toBeVisible();

	await ctx.close();
});

// =============================================================================
// AC-10: Pausenetappe — PauseStageView, kein MapCanvas, kein Profil
// =============================================================================

test.skip('AC-10: Pausenetappe zeigt PauseStageView, kein Karte/Profil', async ({ page }) => {
	// Pause-Stage via Index aktivieren (e2e-cockpit-test hat Pause an Index 2)
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	// Pause-StageCard klicken (Index 2 ist Pausentag — StageCard rendert Pausentage als stage-card-pause-{i})
	const pauseCard = page.getByTestId('stage-card-pause-2');
	await expect(pauseCard).toBeVisible();
	await pauseCard.click();

	// PauseStageView erscheint
	await expect(page.getByTestId('pause-stage-view')).toBeVisible();

	// Karte und Profil dürfen nicht aktiv sein
	// (entweder nicht sichtbar oder content zeigt Pause-Hinweis)
	const profileEditor = page.getByTestId('profile-editor');
	// Bei Pause: kein ProfileEditor sichtbar
	const profileVisible = await profileEditor.isVisible({ timeout: 500 }).catch(() => false);
	expect(profileVisible).toBe(false);
});

// =============================================================================
// AC-11: Prev/Next Navigation — wechselt Stage, disables bei Grenzen
// =============================================================================

test.skip('AC-11: Next-Button wechselt Stage; bei letzter Etappe disabled', async ({ browser }) => {
	const ctx = await browser.newContext({
		...devices['iPhone SE'],
		viewport: { width: 390, height: 844 },
	});
	const page = await ctx.newPage();
	await login(page);
	await page.goto(EDIT_URL);

	const nextBtn = page.getByTestId('stage-nav-next-btn');
	const prevBtn = page.getByTestId('stage-nav-prev-btn');

	// Erste Stage: Prev muss disabled sein
	await expect(prevBtn).toBeDisabled();

	// Zu nächster Stage navigieren
	await nextBtn.click();

	// Jetzt Prev enabled
	await expect(prevBtn).toBeEnabled();

	// Zur letzten Stage navigieren (e2e-cockpit-test hat 3 Stages, Index 0,1,2)
	await nextBtn.click();

	// Bei letzter Stage: Next disabled
	await expect(nextBtn).toBeDisabled();

	await ctx.close();
});

// =============================================================================
// AC-12: Kein Akkordeon für Wetter/Alarmregeln/Reports in Edit-Route
// =============================================================================

test.skip('AC-12: Edit-Route hat keine Wetter/Alarmregeln/Reports-Sektionen', async ({ page }) => {
	await page.goto(EDIT_URL);
	await expect(page.getByTestId('waypoint-editor-page')).toBeVisible();

	// Diese Sektionen dürfen nicht existieren
	await expect(page.getByTestId('edit-section-wetter')).toHaveCount(0);
	await expect(page.getByTestId('edit-section-wetter-header')).toHaveCount(0);
	await expect(page.getByTestId('edit-section-alerts')).toHaveCount(0);
	await expect(page.getByTestId('edit-section-reports')).toHaveCount(0);
});
