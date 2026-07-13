// TDD RED: Issue #302 — Trip-Detail-Seite vollständiges Redesign.
//
// Spec: docs/specs/modules/issue_302_trip_detail_page.md
//
// Voraussetzung: Test-Trip `e2e-cockpit-test` aus global.setup.ts existiert.
// Der Trip ist aktiv (stages: gestern + heute + morgen).
//
// Diese Tests scheitern in RED-Phase, weil:
//   - TripHeader zeigt h2 statt H1 mit data-testid
//   - Tab-Labels sind noch die alten Bezeichnungen
//   - DetailCards existieren nicht (TripOverview hat anderes Layout)
//   - Danger-Zone existiert nicht
//   - Test-Briefing-Button existiert nicht

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Issue #302 — Trip-Detail-Seite Redesign', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	// -------------------------------------------------------------------------
	// Header: H1, Statuszeile, Buttons

	test('AC-1: Header zeigt H1 mit data-testid="trip-detail-h1"', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const h1 = page.getByTestId('trip-detail-h1');
		await expect(h1).toBeVisible();
		await expect(h1).toContainText('E2E Cockpit Test Trip');
	});

	test('AC-2: Statuszeile zeigt km und Höhenmeter (data-testid="trip-detail-meta")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const meta = page.getByTestId('trip-detail-meta');
		await expect(meta).toBeVisible();
		await expect(meta).toContainText('km');
	});

	// Fix-Loop 2026-07-13 (F002): Test-Briefing ist heute ein Dropdown-Toggle
	// (Morgen/Abend-Auswahl) statt eines Direkt-Buttons — Testid entsprechend
	// aktualisiert (routes/trips/[id]/+page.svelte:244).
	test('AC-7: Test-Briefing-Menü vorhanden (data-testid="test-briefing-menu-toggle")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const btn = page.getByTestId('test-briefing-menu-toggle');
		await expect(btn).toBeVisible();
		await expect(btn).toContainText('Test-Briefing');
	});

	// Bug #505: "Bearbeiten"-Button wurde laut Design-Vorgabe aus dem Header entfernt.
	// Editing geschieht inline in den Tabs; /trips/[id]/edit redirectet auf ?tab=stages.
	test('AC-10: Kein "Bearbeiten"-Button im Header (bug #505)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const btn = page.getByTestId('trip-detail-action-edit');
		await expect(btn).not.toBeVisible();
	});

	// -------------------------------------------------------------------------
	// Tab-Leiste: Neue Labels + Badges

	// Fix-Loop 2026-07-13 (F003): Label ist seit langem "Etappen & Wegpunkte"
	// (Konsistenz mit CANONICAL_TABS in issue-616-trip-one-surface.spec.ts) —
	// die alte "Etappen"-Kurzform existiert nicht mehr.
	test('AC-3a: Tab "stages" heißt "Etappen & Wegpunkte"', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const stagesTab = page.getByTestId('trip-detail-tab-stages');
		await expect(stagesTab).toBeVisible();
		await expect(stagesTab).toContainText('Etappen & Wegpunkte');
	});

	// Issue #529 — Kanonische Tab-Namen (nav-map.jsx Drift aufgelöst).
	test('AC-3b: Tab "weather" heißt "Wetter-Metriken" (nicht "Wetter-Briefing")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const weatherTab = page.getByTestId('trip-detail-tab-weather');
		await expect(weatherTab).toContainText('Wetter-Metriken');
		await expect(weatherTab).not.toContainText('Wetter-Briefing');
	});

	// Fix-Loop 2026-07-13 (F004): Label seit #736/Slice 6 "Versand" (nicht mehr
	// "Briefing-Zeitplan" — das war der Zwischenstand vor #736).
	test('AC-3c: Tab "briefings" heißt "Versand" (nicht "Reports & Kanäle")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const briefingsTab = page.getByTestId('trip-detail-tab-briefings');
		await expect(briefingsTab).toContainText('Versand');
		await expect(briefingsTab).not.toContainText('Reports & Kanäle');
	});

	// Issue #1231 Slice 6: alerts-Label erneut umbenannt ("Alerts" -> "Wertebereiche").
	test('AC-3d: Tab "alerts" heißt "Wertebereiche" (nicht "Alarmregeln")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const alertsTab = page.getByTestId('trip-detail-tab-alerts');
		await expect(alertsTab).toContainText('Wertebereiche');
		await expect(alertsTab).not.toContainText('Alarmregeln');
	});

	test('AC-3e: Etappen-Tab hat Badge mit Etappenanzahl', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const badge = page.getByTestId('trip-detail-tab-badge-stages');
		await expect(badge).toBeVisible();
	});

	// -------------------------------------------------------------------------
	// Übersicht-Tab: 4 DetailCards im 2x2-Grid

	// Superseded by Issue #409 — TripOverview nutzt FullProfile + StageList + rechte Spalte statt DetailCards.
	test.skip('AC-4a: Übersicht zeigt DetailCard Reports (data-testid="detail-card-reports")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const card = page.getByTestId('detail-card-reports');
		await expect(card).toBeVisible();
	});

	// Superseded by Issue #409 — TripOverview nutzt FullProfile + StageList + rechte Spalte statt DetailCards.
	test.skip('AC-4b: Übersicht zeigt DetailCard Alarmregeln (data-testid="detail-card-alarmregeln")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const card = page.getByTestId('detail-card-alarmregeln');
		await expect(card).toBeVisible();
	});

	// Superseded by Issue #409 — TripOverview nutzt FullProfile + StageList + rechte Spalte statt DetailCards.
	test.skip('AC-4c: Übersicht zeigt DetailCard Route (data-testid="detail-card-route")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const card = page.getByTestId('detail-card-route');
		await expect(card).toBeVisible();
	});

	// Superseded by Issue #409 — TripOverview nutzt FullProfile + StageList + rechte Spalte statt DetailCards.
	test.skip('AC-4d: Übersicht zeigt DetailCard Datenstand (data-testid="detail-card-datenstand")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const card = page.getByTestId('detail-card-datenstand');
		await expect(card).toBeVisible();
	});

	// -------------------------------------------------------------------------
	// Danger-Zone — entfernt 2026-07-13: danger-zone-Konzept abgebaut, s.
	// #1231-Slice-6-Lauf (F005–F008). Pausieren/Archivieren leben heute in der
	// Breadcrumb-Actions-Leiste (routes/trips/[id]/+page.svelte), ohne eigene
	// Testids; Löschen ist auf die /trips-Listenansicht (Zeilen-Menü)
	// verlagert und aus der Trip-Detail-Seite entfernt (kein Ersatz-Testid,
	// daher keine 1:1-Migration — AC-8a–d ersatzlos gestrichen).
});
