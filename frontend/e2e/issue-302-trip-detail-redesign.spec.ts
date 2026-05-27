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

	test('AC-7: Test-Briefing-Button vorhanden (data-testid="trip-detail-action-test-briefing")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const btn = page.getByTestId('trip-detail-action-test-briefing');
		await expect(btn).toBeVisible();
		await expect(btn).toContainText('Test-Briefing');
	});

	test('AC-10: Bearbeiten-Button mit data-testid="trip-detail-action-edit" vorhanden', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const btn = page.getByTestId('trip-detail-action-edit');
		await expect(btn).toBeVisible();
		await expect(btn).toContainText('Bearbeiten');
	});

	// -------------------------------------------------------------------------
	// Tab-Leiste: Neue Labels + Badges

	test('AC-3a: Tab "stages" heißt "Etappen" (nicht "Etappen & Wegpunkte")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const stagesTab = page.getByTestId('trip-detail-tab-stages');
		await expect(stagesTab).toBeVisible();
		const text = await stagesTab.textContent();
		expect(text).not.toContain('& Wegpunkte');
	});

	test('AC-3b: Tab "weather" heißt "Wetter-Briefing" (nicht "Wetter-Metriken")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const weatherTab = page.getByTestId('trip-detail-tab-weather');
		await expect(weatherTab).toContainText('Wetter-Briefing');
	});

	test('AC-3c: Tab "briefings" heißt "Reports & Kanäle" (nicht "Briefing-Zeitplan")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const briefingsTab = page.getByTestId('trip-detail-tab-briefings');
		await expect(briefingsTab).toContainText('Reports & Kanäle');
	});

	test('AC-3d: Tab "alerts" heißt "Alarmregeln" (nicht "Alerts")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const alertsTab = page.getByTestId('trip-detail-tab-alerts');
		await expect(alertsTab).toContainText('Alarmregeln');
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
	// Danger-Zone

	test('AC-8a: Danger-Zone vorhanden (data-testid="danger-zone")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const dz = page.getByTestId('danger-zone');
		await expect(dz).toBeVisible();
	});

	test('AC-8b: Pause-Button in Danger-Zone (trip-detail-action-pause)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const dz = page.getByTestId('danger-zone');
		const pauseBtn = dz.getByTestId('trip-detail-action-pause');
		await expect(pauseBtn).toBeVisible();
	});

	test('AC-8c: Archiv-Button in Danger-Zone (trip-detail-action-archive)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const dz = page.getByTestId('danger-zone');
		const archiveBtn = dz.getByTestId('trip-detail-action-archive');
		await expect(archiveBtn).toBeVisible();
	});

	test('AC-8d: Löschen-Button in Danger-Zone (trip-detail-action-delete)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const deleteBtn = page.getByTestId('trip-detail-action-delete');
		await expect(deleteBtn).toBeVisible();
		await expect(deleteBtn).toContainText('löschen');
	});
});
