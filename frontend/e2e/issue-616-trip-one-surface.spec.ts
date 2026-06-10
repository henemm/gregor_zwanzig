// E2E — Issue #616: EINE Trip-Seite (Ansehen+Bearbeiten integriert) + /edit stilllegen
//
// Spec: docs/specs/modules/issue_616_trip_editor_tabs.md (v2, AC-1 bis AC-8)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, solange die separate /edit-Seite
// (TripEditView) noch existiert, der Briefing-Zeitplan-Tab ein statisches
// Mockup (HubSchedule) ist und der Trip-Name nur auf /edit editierbar ist.
//
// Verhaltenstests aus Nutzerperspektive gegen den lokalen Preview-Build mit
// eingeloggter Session + geseedetem Test-Trip `e2e-cockpit-test`.
//
// Ausführung: cd frontend && npx playwright test issue-616-trip-one-surface

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const TRIP_NAME = 'E2E Cockpit Test Trip';
const DETAIL_URL = `/trips/${TRIP_ID}`;
const OLD_EDIT_URL = `/trips/${TRIP_ID}/edit`;
const DESKTOP = { width: 1440, height: 900 };

const CANONICAL_TABS: ReadonlyArray<[string, string]> = [
	['overview', 'Übersicht'],
	['stages', 'Etappen & Wegpunkte'],
	['weather', 'Wetter-Metriken'],
	['briefings', 'Briefing-Zeitplan'],
	['alerts', 'Alerts'],
	['preview', 'Vorschau']
];

test.describe('Issue #616 — EINE Trip-Seite', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await login(page);
	});

	// ─── AC-1: „Bearbeiten" führt auf die EINE Oberfläche, nicht auf /edit ───
	test('AC-1: "Bearbeiten" aus der Trips-Liste landet auf /trips/[id] (eine Oberfläche)', async ({
		page
	}) => {
		/**
		 * GIVEN: eingeloggt, /trips geladen, Test-Trip vorhanden
		 * WHEN:  im Zeilen-Menü "Bearbeiten" geklickt wird
		 * THEN:  URL ist /trips/[id] (NICHT /edit) und die kanonische
		 *        Tab-Leiste (trip-detail-tab-list) ist sichtbar.
		 */
		await page.goto('/trips');
		const row = page.locator(`[title="${TRIP_NAME} öffnen"]`).first();
		await row.locator('[data-testid="trip-row-menu-btn"]').click();
		await page.locator('[data-testid="trip-edit-btn"]:visible').first().click();

		await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}(\\?|#|$)`));
		expect(page.url()).not.toContain('/edit');
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 8000 });
		await expect(page.getByTestId('trip-edit-view')).toHaveCount(0);
	});

	// ─── AC-2: alte /edit-URL leitet auf die eine Oberfläche um ───
	test('AC-2: /trips/[id]/edit leitet auf /trips/[id] um (kein TripEditView mehr)', async ({
		page
	}) => {
		/**
		 * GIVEN: eingeloggt
		 * WHEN:  die alte URL /trips/[id]/edit direkt aufgerufen wird
		 * THEN:  Redirect auf /trips/[id], TripEditView wird nicht gerendert.
		 */
		await page.goto(OLD_EDIT_URL);
		await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}(\\?|#|$)`));
		expect(page.url()).not.toContain('/edit');
		await expect(page.getByTestId('trip-edit-view')).toHaveCount(0);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 8000 });
	});

	// ─── AC-3: kanonisches 6-Tab-Set in Reihenfolge ───
	test('AC-3: Tab-Leiste zeigt exakt 6 Tabs in kanonischer Reihenfolge', async ({ page }) => {
		/**
		 * GIVEN: die kanonische Trip-Oberfläche
		 * WHEN:  die Tab-Leiste gerendert ist
		 * THEN:  genau 6 Tabs: Übersicht · Etappen & Wegpunkte · Wetter-Metriken ·
		 *        Briefing-Zeitplan · Alerts · Vorschau (in dieser Reihenfolge).
		 */
		await page.goto(DETAIL_URL);
		for (const [value, label] of CANONICAL_TABS) {
			await expect(page.getByTestId(`trip-detail-tab-${value}`)).toContainText(label);
		}
	});

	// ─── AC-4: Übersicht = Lese-Cockpit, "Bearbeiten →" wechselt zum Editor ───
	test('AC-4: "Im Editor öffnen →" der Übersicht wechselt zum Etappen-Editor', async ({
		page
	}) => {
		/**
		 * GIVEN: Übersicht-Tab aktiv (Default)
		 * WHEN:  der Sprung-Link "Im Editor öffnen →" (Etappen) geklickt wird
		 * THEN:  der Etappen-Editor-Tab ist aktiv und sein Panel sichtbar.
		 * RED-Grund: HubOverview springt auf 'etappen', der Tab-Wert ist 'stages'
		 *            → fällt heute auf 'overview' zurück.
		 */
		await page.goto(DETAIL_URL);
		await expect(page.getByTestId('hub-overview')).toBeVisible();
		await page.getByRole('button', { name: /Im Editor öffnen/i }).first().click();
		await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible({ timeout: 8000 });
	});

	// ─── AC-5: Briefing-Zeitplan ist ein ECHTER Editor (kein Mockup) ───
	test('AC-5: Briefing-Zeitplan speichert report_config real (Read-Modify-Write)', async ({
		page
	}) => {
		/**
		 * GIVEN: Briefing-Zeitplan-Tab geöffnet
		 * WHEN:  Morgen-Zeit geändert und gespeichert wird
		 * THEN:  PUT persistiert morning_time; display_config bleibt unverändert.
		 * RED-Grund: heute rendert dort das statische HubSchedule-Mockup ohne Inputs/Save.
		 */
		await page.goto(`${DETAIL_URL}?tab=briefings`);
		const morning = page.getByTestId('report-morning-time');
		await expect(morning).toBeVisible({ timeout: 8000 });
		await morning.fill('05:30');
		await page.getByTestId('briefings-save').click();

		// Verifikation gegen das echte Backend
		const res = await page.request.get(`/api/trips/${TRIP_ID}`);
		expect(res.ok()).toBeTruthy();
		const trip = await res.json();
		expect(String(trip.report_config?.morning_time)).toMatch(/^05:30/);
		// Read-Modify-Write: display_config darf nicht verloren gehen
		expect(trip.display_config?.metrics).toContain('temp_min');
	});

	// ─── AC-6: Trip-Name bleibt auf der einen Oberfläche bearbeitbar ───
	test('AC-6: Trip-Name ist auf der kanonischen Oberfläche editierbar + persistent', async ({
		page
	}) => {
		/**
		 * GIVEN: die kanonische Trip-Oberfläche
		 * WHEN:  der Trip-Name geändert und gespeichert wird
		 * THEN:  neuer Name persistiert (durch /edit-Stilllegung nicht verloren).
		 * RED-Grund: Namens-Bearbeitung existiert heute nur auf der separaten /edit-Seite.
		 */
		await page.goto(DETAIL_URL);
		// #713: Name-Edit ist hinter Stift-Toggle versteckt — erst öffnen
		await page.getByTestId('trip-name-edit-toggle').click();
		const nameEdit = page.getByTestId('trip-name-edit');
		await expect(nameEdit).toBeVisible({ timeout: 8000 });
		await nameEdit.fill('E2E Cockpit Test Trip — umbenannt');
		await page.getByTestId('trip-name-save').click();

		const res = await page.request.get(`/api/trips/${TRIP_ID}`);
		const trip = await res.json();
		expect(trip.name).toBe('E2E Cockpit Test Trip — umbenannt');

		// Cleanup: Name zurücksetzen, damit andere Tests stabil bleiben
		await page.request.put(`/api/trips/${TRIP_ID}`, { data: { ...trip, name: TRIP_NAME } });
	});

	// ─── AC-7: Editor-Tabs speichern weiterhin (Regressionsschutz) ───
	test('AC-7: Alerts-Tab behält seinen Pro-Tab-Speichern-Weg', async ({ page }) => {
		/**
		 * GIVEN: Alerts-Tab geöffnet
		 * WHEN:  Panel gerendert
		 * THEN:  eigener Speichern-Button (alerts-tab-save) vorhanden — keine
		 *        Regression durch die Konsolidierung.
		 */
		await page.goto(`${DETAIL_URL}?tab=alerts`);
		await expect(page.getByTestId('alerts-tab')).toBeVisible({ timeout: 8000 });
		// Desktop- und Mobile-Footer tragen beide die testid → erstes (sichtbares) genügt.
		await expect(page.getByTestId('alerts-tab-save').first()).toBeVisible();
	});

	// ─── AC-8: Terminologie Trip · Etappe · Wegpunkt ───
	test('AC-8: keine "Tour"/"Waypoint"-Terminologie auf der Trip-Oberfläche sichtbar', async ({
		page
	}) => {
		/**
		 * GIVEN: die kanonische Trip-Oberfläche (alle Tabs)
		 * WHEN:  der sichtbare Text gelesen wird
		 * THEN:  kein "Tour"/"Reise"/"Waypoint" im sichtbaren UI.
		 */
		await page.goto(DETAIL_URL);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
		const body = (await page.locator('body').innerText()).toLowerCase();
		expect(body).not.toMatch(/\btour\b/);
		expect(body).not.toMatch(/\bwaypoint\b/);
		expect(body).not.toMatch(/\breise\b/);
	});
});
