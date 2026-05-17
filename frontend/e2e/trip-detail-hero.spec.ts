// TDD: Issue #154 — Epic #135 Step 3: Trip-Hero E2E.
//
// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
//
// Voraussetzung: Test-Trip `e2e-cockpit-test` aus global.setup.ts
// (Stages: dynamisch relativ zu heute — yesterday / today / tomorrow).

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Issue #154 — Trip-Hero im Overview-Tab', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	test.afterAll(async ({ request }) => {
		await resetTripState(request);
	});

	test('AC-1: Hero rendert alle 6 TestIDs in fester Reihenfolge', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		// Overview-Tab ist Default
		await expect(page.getByTestId('trip-hero')).toBeVisible();
		await expect(page.getByTestId('trip-hero-title')).toBeVisible();
		await expect(page.getByTestId('trip-hero-date-range')).toBeVisible();
		await expect(page.getByTestId('trip-hero-stat-active-stage')).toBeVisible();
		await expect(page.getByTestId('trip-hero-stat-next-briefing')).toBeVisible();
		await expect(page.getByTestId('trip-hero-stat-days')).toBeVisible();
	});

	test('AC-1b: Trip-Name als H1', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const title = page.getByTestId('trip-hero-title');
		await expect(title).toHaveText('E2E Cockpit Test Trip');
		// H1?
		const tagName = await title.evaluate((el) => el.tagName);
		expect(tagName).toBe('H1');
	});

	test('AC-3: active Trip mit Stage 2/3 zeigt "Tag 2/3" + Stage-Name', async ({ page }) => {
		// e2e-cockpit-test hat 3 Stages (gestern, heute, morgen). Heute = Stage 2 "Heute".
		await page.goto(`/trips/${TRIP_ID}`);
		const activeStage = page.getByTestId('trip-hero-stat-active-stage');
		await expect(activeStage).toContainText('Tag 2/3');
		await expect(activeStage).toContainText('Heute');
	});

	test('AC-6: Trip ohne report_config zeigt "Briefings deaktiviert"', async ({
		page,
		request
	}) => {
		// Eigener Trip ohne report_config — Shared e2e-cockpit-test hat eines (#229).
		const NO_BRIEFING_TRIP_ID = 'e2e-hero-no-briefing-trip';
		await request.post('/api/trips', {
			data: {
				id: NO_BRIEFING_TRIP_ID,
				name: 'E2E Hero No-Briefing Trip',
				stages: [
					{
						id: 'hero-nb-stage-1',
						name: 'Etappe',
						date: new Date().toISOString().slice(0, 10),
						waypoints: [
							{ id: 'hero-nb-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }
						]
					}
				]
			}
		});

		await page.goto(`/trips/${NO_BRIEFING_TRIP_ID}`);
		const next = page.getByTestId('trip-hero-stat-next-briefing');
		await expect(next).toContainText('Briefings deaktiviert');
	});

	test('AC-10: active Trip zeigt "läuft seit Tag X"', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const days = page.getByTestId('trip-hero-stat-days');
		await expect(days).toContainText('läuft seit Tag 2');
	});

	test('AC-11: Date-Range zeigt Mai 2026 (kompakt)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const range = page.getByTestId('trip-hero-date-range');
		// Stages werden in global.setup.ts dynamisch auf yesterday/today/tomorrow gesetzt
		const today = new Date();
		const yesterday = new Date(today);
		yesterday.setDate(today.getDate() - 1);
		const tomorrow = new Date(today);
		tomorrow.setDate(today.getDate() + 1);
		await expect(range).toContainText('Mai 2026');
		await expect(range).toContainText(`${yesterday.getDate()}.`);
		await expect(range).toContainText(`${tomorrow.getDate()}.`);
	});

	test('AC-15: Reaktivität — nach "Pausieren" zeigt active-stage "Pausiert" ohne Reload', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const activeStage = page.getByTestId('trip-hero-stat-active-stage');
		await expect(activeStage).toContainText(/Tag \d+\/\d+/);
		// Pause-Button klicken (aus Step 2)
		await page.getByTestId('trip-detail-action-pause').click();
		// Hero stat reagiert ohne Reload
		await expect(activeStage).toContainText('Pausiert');
	});

	test('AC-16: Regressions-Guard — Tab-Navigation + Header bleiben sichtbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		// Step 1: Tab-Liste
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
		for (const tab of ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview']) {
			await expect(page.getByTestId(`trip-detail-tab-${tab}`)).toBeVisible();
		}
		// Step 2: Breadcrumb + Status-Badge
		await expect(page.getByTestId('trip-detail-breadcrumb')).toBeVisible();
		await expect(page.getByTestId('trip-detail-status-badge')).toBeVisible();
	});

	test('AC-16b: Tab-Wechsel funktioniert nach wie vor', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-alerts').click();
		await expect(page.getByTestId('trip-detail-tab-alerts')).toHaveAttribute('data-state', 'active');
		// Bei Tab-Wechsel ist Hero NICHT mehr im DOM (er ist im Overview-Tab-Panel)
		await expect(page.getByTestId('trip-hero')).not.toBeVisible();
		// Zurück zum Overview
		await page.getByTestId('trip-detail-tab-overview').click();
		await expect(page.getByTestId('trip-hero')).toBeVisible();
	});

	test('AC-18: Mobile-Layout — 3 Kacheln stacken auf schmalem Viewport', async ({ page }) => {
		await page.setViewportSize({ width: 400, height: 800 });
		await page.goto(`/trips/${TRIP_ID}`);
		const tile1 = page.getByTestId('trip-hero-stat-active-stage');
		const tile2 = page.getByTestId('trip-hero-stat-next-briefing');
		const box1 = await tile1.boundingBox();
		const box2 = await tile2.boundingBox();
		expect(box1).toBeTruthy();
		expect(box2).toBeTruthy();
		// Auf Mobile sollten die Kacheln untereinander sein (y2 > y1)
		expect(box2!.y).toBeGreaterThan(box1!.y);
	});

	test('AC-18b: Desktop-Layout — 3 Kacheln nebeneinander auf breitem Viewport', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 800 });
		await page.goto(`/trips/${TRIP_ID}`);
		const tile1 = page.getByTestId('trip-hero-stat-active-stage');
		const tile2 = page.getByTestId('trip-hero-stat-next-briefing');
		const box1 = await tile1.boundingBox();
		const box2 = await tile2.boundingBox();
		// Auf Desktop sind die Kacheln auf gleicher Höhe (y2 ≈ y1)
		expect(Math.abs(box2!.y - box1!.y)).toBeLessThan(10);
		// Und nebeneinander (x2 > x1)
		expect(box2!.x).toBeGreaterThan(box1!.x);
	});

	test('Screenshot des Hero für visuelle Verifikation', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.waitForSelector('[data-testid="trip-hero"]');
		await page.screenshot({
			path: 'docs/artifacts/epic-135-step3-trip-hero/screenshot-hero.png',
			fullPage: false
		});
	});

	test('AC-202-1: Hero zeigt Region wenn trip.region gesetzt', async ({ page }) => {
		// e2e-cockpit-test hat nach dem Seed-Update region: "Korsika"
		await page.goto(`/trips/${TRIP_ID}`);
		const regionEl = page.getByTestId('trip-hero-region');
		await expect(regionEl).toBeVisible();
		await expect(regionEl).toHaveText('Korsika');
	});

	test('AC-202-2: Hero zeigt kein Region-Element wenn trip.region fehlt', async ({ page, request }) => {
		const NO_REGION_ID = 'e2e-hero-no-region-trip';
		await request.delete(`/api/trips/${NO_REGION_ID}`);
		const today = new Date().toISOString().slice(0, 10);
		await request.post('/api/trips', {
			data: {
				id: NO_REGION_ID,
				name: 'Kein Region Trip',
				stages: [{ id: 'nr-s1', name: 'Tag 1', date: today,
					waypoints: [{ id: 'nr-w1', name: 'Start', lat: 42.0, lon: 9.0, elevation_m: 100 }] }]
			}
		});
		await page.goto(`/trips/${NO_REGION_ID}`);
		await expect(page.getByTestId('trip-hero-region')).not.toBeVisible();
		await request.delete(`/api/trips/${NO_REGION_ID}`);
	});
});
