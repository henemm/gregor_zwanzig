// TDD RED: Epic #135 Step 4 — Trip-Detail Overview, linke Spalte E2E.
//
// Spec: docs/specs/modules/epic_135_step4_left_column.md
// Issues: #156 (Full-Profil-SVG) + #157 (Stage-Row-Liste)
//
// Voraussetzung: Test-Trip `e2e-cockpit-test` aus global.setup.ts
// (3 Stages: Gestern 2026-05-11, Heute 2026-05-12, Morgen 2026-05-13).
//
// Erwartet: Alle Tests scheitern in RED-Phase, weil
//   - TripOverview.svelte noch nicht existiert
//   - FullProfile / StageList / StageDetailRow noch nicht existieren
//   - TestIDs trip-overview, trip-full-profile, trip-stage-list, trip-stage-row-*
//     noch nicht im DOM sind.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
const STAGE_1 = 'e2e-stage-1'; // Gestern
const STAGE_2 = 'e2e-stage-2'; // Heute (aktive Stage)
const STAGE_3 = 'e2e-stage-3'; // Morgen

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Epic #135 Step 4 — Trip-Detail Overview, linke Spalte (#156 + #157)', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	test.afterAll(async ({ request }) => {
		await resetTripState(request);
	});

	test('AC-1: TripOverview + Hero + linke + rechte Spalte sichtbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		// Overview-Tab ist Default
		await expect(page.getByTestId('trip-overview')).toBeVisible();
		// Hero bleibt innerhalb von TripOverview gerendert
		await expect(page.getByTestId('trip-hero')).toBeVisible();
		// Beide Spalten existieren
		await expect(page.getByTestId('trip-overview-left-column')).toBeVisible();
		await expect(page.getByTestId('trip-overview-right-column')).toBeVisible();
	});

	test('AC-2: FullProfile + StageList in DOM-Reihenfolge', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-full-profile')).toBeVisible();
		await expect(page.getByTestId('trip-stage-list')).toBeVisible();

		// DOM-Reihenfolge prüfen: trip-full-profile vor trip-stage-list innerhalb left-column
		const orderOk = await page.evaluate(() => {
			const profile = document.querySelector('[data-testid="trip-full-profile"]');
			const list = document.querySelector('[data-testid="trip-stage-list"]');
			if (!profile || !list) return false;
			// DOCUMENT_POSITION_FOLLOWING = 4
			return (profile.compareDocumentPosition(list) & 4) !== 0;
		});
		expect(orderOk).toBe(true);
	});

	test('AC-3: SVG mit Polyline + 3 Hit-Areas für 3 Stages', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const profile = page.getByTestId('trip-full-profile');
		await expect(profile).toBeVisible();

		// SVG-Element vorhanden
		const svgCount = await profile.locator('svg').count();
		expect(svgCount).toBeGreaterThan(0);

		// Polyline mit mindestens 3 Punkten (4 Waypoints total mit elevation_m im Test-Trip)
		const polyline = profile.locator('polyline').first();
		await expect(polyline).toBeAttached();
		const pointsAttr = await polyline.getAttribute('points');
		expect(pointsAttr).toBeTruthy();
		// "x1,y1 x2,y2 ..." → mindestens 3 Tokens
		const tokens = pointsAttr!.trim().split(/\s+/).filter((t) => t.length > 0);
		expect(tokens.length).toBeGreaterThanOrEqual(3);

		// Genau 3 Hit-Areas, eine pro Stage
		await expect(page.getByTestId(`trip-full-profile-stage-${STAGE_1}`)).toBeAttached();
		await expect(page.getByTestId(`trip-full-profile-stage-${STAGE_2}`)).toBeAttached();
		await expect(page.getByTestId(`trip-full-profile-stage-${STAGE_3}`)).toBeAttached();
	});

	test('AC-4: Stage-Labels in DOM-Reihenfolge S1, S2, S3', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId(`trip-full-profile-label-${STAGE_1}`)).toBeAttached();
		await expect(page.getByTestId(`trip-full-profile-label-${STAGE_2}`)).toBeAttached();
		await expect(page.getByTestId(`trip-full-profile-label-${STAGE_3}`)).toBeAttached();

		const order = await page.evaluate(
			({ s1, s2, s3 }) => {
				const l1 = document.querySelector(`[data-testid="trip-full-profile-label-${s1}"]`);
				const l2 = document.querySelector(`[data-testid="trip-full-profile-label-${s2}"]`);
				const l3 = document.querySelector(`[data-testid="trip-full-profile-label-${s3}"]`);
				if (!l1 || !l2 || !l3) return false;
				const l1ToL2 = (l1.compareDocumentPosition(l2) & 4) !== 0;
				const l2ToL3 = (l2.compareDocumentPosition(l3) & 4) !== 0;
				return l1ToL2 && l2ToL3;
			},
			{ s1: STAGE_1, s2: STAGE_2, s3: STAGE_3 }
		);
		expect(order).toBe(true);
	});

	test('AC-5: Active-Stage hat Fill ohne User-Klick (heutige Stage 2)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		// Heutige Stage = STAGE_2. Active-Fill ist ein <rect> mit fill=var(--g-accent), opacity 0.15.
		// Wir pruefen, dass im SVG mindestens ein <rect> mit dieser Opacity vorhanden ist
		// (im Gegensatz zum Initialzustand ohne aktive Stage).
		const fills = await page.evaluate(() => {
			const profile = document.querySelector('[data-testid="trip-full-profile"]');
			if (!profile) return [];
			const rects = Array.from(profile.querySelectorAll('rect'));
			return rects.map((r) => ({
				fill: r.getAttribute('fill'),
				opacity: r.getAttribute('opacity'),
				stroke: r.getAttribute('stroke')
			}));
		});
		const hasActiveFill = fills.some(
			(f) =>
				f.fill !== null &&
				f.fill !== 'none' &&
				f.opacity !== null &&
				parseFloat(f.opacity) > 0 &&
				parseFloat(f.opacity) < 1
		);
		expect(hasActiveFill).toBe(true);
	});

	test('AC-6: Klick auf Hit-Area Stage 2 → Selected-Outline an Stage 2', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId(`trip-full-profile-stage-${STAGE_2}`).click();

		// Selected-Outline ist ein <rect> mit fill=none und stroke=var(--g-accent).
		const hasOutline = await page.evaluate(() => {
			const profile = document.querySelector('[data-testid="trip-full-profile"]');
			if (!profile) return false;
			const rects = Array.from(profile.querySelectorAll('rect'));
			return rects.some((r) => {
				const fill = r.getAttribute('fill');
				const stroke = r.getAttribute('stroke');
				return (fill === 'none' || fill === '') && stroke !== null && stroke !== 'none';
			});
		});
		expect(hasOutline).toBe(true);

		// Card der Stage 2 ist data-selected="true"
		await expect(page.getByTestId(`trip-stage-row-${STAGE_2}`)).toHaveAttribute(
			'data-selected',
			'true'
		);
	});

	test('AC-7: StageList rendert 3 Cards für 3 Stages in Reihenfolge', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId(`trip-stage-row-${STAGE_1}`)).toBeVisible();
		await expect(page.getByTestId(`trip-stage-row-${STAGE_2}`)).toBeVisible();
		await expect(page.getByTestId(`trip-stage-row-${STAGE_3}`)).toBeVisible();

		// Reihenfolge im DOM
		const order = await page.evaluate(
			({ s1, s2, s3 }) => {
				const r1 = document.querySelector(`[data-testid="trip-stage-row-${s1}"]`);
				const r2 = document.querySelector(`[data-testid="trip-stage-row-${s2}"]`);
				const r3 = document.querySelector(`[data-testid="trip-stage-row-${s3}"]`);
				if (!r1 || !r2 || !r3) return false;
				const r1ToR2 = (r1.compareDocumentPosition(r2) & 4) !== 0;
				const r2ToR3 = (r2.compareDocumentPosition(r3) & 4) !== 0;
				return r1ToR2 && r2ToR3;
			},
			{ s1: STAGE_1, s2: STAGE_2, s3: STAGE_3 }
		);
		expect(order).toBe(true);
	});

	test('AC-8: Stage-Card zeigt Code + Datum + km + Hm + Waypoint-Count + Stage-Name', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const card2 = page.getByTestId(`trip-stage-row-${STAGE_2}`);
		await expect(card2).toBeVisible();

		// Code-Pill T02 (zweite reguläre Stage)
		const pill = page.getByTestId(`trip-stage-row-code-${STAGE_2}`);
		await expect(pill).toBeVisible();
		await expect(pill).toContainText(/T0?2/);

		// Stage-Name "Heute"
		await expect(card2).toContainText('Heute');

		// Datum-Format "DD.MM." gemaess Spec — heutiges Datum dynamisch
		// berechnen, weil global.setup.ts STAGE_2 immer auf `today` setzt.
		// Hartes Datum (z.B. "12.05.") wuerde nur am Spec-Erstelltag passen
		// und ist Test-Drift, kein realer Verhaltensvertrag.
		const today = new Date();
		const todayDdMm =
			String(today.getDate()).padStart(2, '0') +
			'.' +
			String(today.getMonth() + 1).padStart(2, '0') +
			'.';
		await expect(card2).toContainText(todayDdMm);

		// km-Wert (Distanz STAGE_2 ≈ 11 km zwischen wp-2 und wp-3 → "km" sichtbar)
		await expect(card2).toContainText(/km/);

		// Hm (Aufstieg/Abstieg) sichtbar
		await expect(card2).toContainText(/Hm/);

		// Waypoint-Count = 2
		await expect(card2).toContainText('2');
	});

	test('AC-9: Klick auf Card 1 → data-selected="true", Outline im Profil bei Stage 1', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId(`trip-stage-row-${STAGE_1}`).click();

		// Card 1 selected, andere nicht
		await expect(page.getByTestId(`trip-stage-row-${STAGE_1}`)).toHaveAttribute(
			'data-selected',
			'true'
		);
		await expect(page.getByTestId(`trip-stage-row-${STAGE_2}`)).toHaveAttribute(
			'data-selected',
			'false'
		);
		await expect(page.getByTestId(`trip-stage-row-${STAGE_3}`)).toHaveAttribute(
			'data-selected',
			'false'
		);

		// Selected-Outline im SVG sichtbar
		const hasOutline = await page.evaluate(() => {
			const profile = document.querySelector('[data-testid="trip-full-profile"]');
			if (!profile) return false;
			const rects = Array.from(profile.querySelectorAll('rect'));
			return rects.some((r) => {
				const fill = r.getAttribute('fill');
				const stroke = r.getAttribute('stroke');
				return (fill === 'none' || fill === '') && stroke !== null && stroke !== 'none';
			});
		});
		expect(hasOutline).toBe(true);
	});

	test('AC-10: Bidirektional — Klick im Profil dann auf Card → Card-Status in Sync', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);

		// 1) Klick im Profil auf Stage 2
		await page.getByTestId(`trip-full-profile-stage-${STAGE_2}`).click();
		await expect(page.getByTestId(`trip-stage-row-${STAGE_2}`)).toHaveAttribute(
			'data-selected',
			'true'
		);

		// 2) Klick auf Card von Stage 1
		await page.getByTestId(`trip-stage-row-${STAGE_1}`).click();

		// Card 1 selected, Card 2 nicht mehr selected
		await expect(page.getByTestId(`trip-stage-row-${STAGE_1}`)).toHaveAttribute(
			'data-selected',
			'true'
		);
		await expect(page.getByTestId(`trip-stage-row-${STAGE_2}`)).toHaveAttribute(
			'data-selected',
			'false'
		);
	});

	test('AC-15: Empty-State bei stages = []', async ({ page, request }) => {
		// Eigenen Trip ohne Stages anlegen
		const EMPTY_TRIP_ID = 'e2e-empty-trip';
		await request.post('/api/trips', {
			data: {
				id: EMPTY_TRIP_ID,
				name: 'E2E Empty Trip',
				stages: []
			}
		});

		await page.goto(`/trips/${EMPTY_TRIP_ID}`);

		// Empty-States sichtbar
		await expect(page.getByTestId('trip-full-profile-empty')).toBeVisible();
		await expect(page.getByTestId('trip-stage-empty')).toBeVisible();

		// Kein SVG mit Polyline
		const polylineCount = await page
			.getByTestId('trip-full-profile')
			.locator('polyline')
			.count();
		expect(polylineCount).toBe(0);

		// Kein "undefined"-Text im Overview-Bereich
		const overviewText = await page.getByTestId('trip-overview').innerText();
		expect(overviewText).not.toContain('undefined');
	});

	test('AC-16: Step-3 TestIDs bleiben sichtbar (Regression-Guard)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-hero')).toBeVisible();
		await expect(page.getByTestId('trip-hero-title')).toBeVisible();
		await expect(page.getByTestId('trip-hero-stat-active-stage')).toBeVisible();
		await expect(page.getByTestId('trip-hero-stat-next-briefing')).toBeVisible();
		await expect(page.getByTestId('trip-hero-stat-days')).toBeVisible();
	});

	test('AC-17: Step-1 Tab-Liste + Step-2 Breadcrumb sichtbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		// Step 1: Tab-Liste
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
		for (const tab of ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview']) {
			await expect(page.getByTestId(`trip-detail-tab-${tab}`)).toBeVisible();
		}
		// Step 2: Breadcrumb (Issue #699: innere nav entfernt → äußere Bar)
		await expect(page.getByTestId('trip-detail-breadcrumb-bar')).toBeVisible();
	});

	test('AC-18: Active + Selected gleichzeitig möglich (heutige Stage angeklickt)', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		// Klick auf die heutige Stage (STAGE_2)
		await page.getByTestId(`trip-stage-row-${STAGE_2}`).click();

		const card = page.getByTestId(`trip-stage-row-${STAGE_2}`);
		await expect(card).toHaveAttribute('data-selected', 'true');
		await expect(card).toHaveAttribute('data-active', 'true');

		// Im SVG sind Active-Fill (opacity zwischen 0 und 1) UND Selected-Outline (stroke != none) sichtbar
		const both = await page.evaluate(() => {
			const profile = document.querySelector('[data-testid="trip-full-profile"]');
			if (!profile) return { activeFill: false, selectedOutline: false };
			const rects = Array.from(profile.querySelectorAll('rect'));
			const activeFill = rects.some((r) => {
				const fill = r.getAttribute('fill');
				const opacity = r.getAttribute('opacity');
				return (
					fill !== null &&
					fill !== 'none' &&
					opacity !== null &&
					parseFloat(opacity) > 0 &&
					parseFloat(opacity) < 1
				);
			});
			const selectedOutline = rects.some((r) => {
				const fill = r.getAttribute('fill');
				const stroke = r.getAttribute('stroke');
				return (fill === 'none' || fill === '') && stroke !== null && stroke !== 'none';
			});
			return { activeFill, selectedOutline };
		});
		expect(both.activeFill).toBe(true);
		expect(both.selectedOutline).toBe(true);
	});
});
