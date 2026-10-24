import { test, expect } from '@playwright/test';

/**
 * Issue #294 — Home: Cockpit → Kachel-Übersicht
 * Spec: docs/specs/modules/issue_294_home_kachel.md
 *
 * Tests laufen gegen die aktuelle Implementierung (Cockpit) und müssen ROT sein.
 * Nach der Implementierung müssen alle Tests GRÜN sein.
 */

test.describe('Issue #294 — Home Kachel-Übersicht', () => {
	test.use({ storageState: 'playwright/.auth/admin.json' });

	// AC-1: Keine Cockpit-Elemente im DOM
	test('AC-1: keine Cockpit-Elemente auf der Home-Seite', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN: User öffnet /
		 * THEN: Kein ActiveTripCard, StageStrip, BriefingsTimeline, AlertFeed im DOM
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('[data-testid="active-trip-card"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="stage-strip"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="briefings-timeline"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="alert-feed"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="cockpit-topbar"]')).toHaveCount(0);
	});

	// AC-2: Trip-Kacheln mit Namen werden gerendert
	test('AC-2: Trip-Kacheln mit Name und Etappenanzahl sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt und hat Trips
		 * WHEN: User öffnet /
		 * THEN: data-testid="trip-card" sichtbar mit Trip-Name und "N Etappen"
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		const section = page.locator('section', { hasText: 'Meine Trips' });
		await expect(section).toBeVisible();

		const cards = section.locator('[data-testid^="subscription-card-"][data-kind="trip"]');
		await expect(cards.first()).toBeVisible();
		await expect(cards.first()).toContainText(/\d+ Etappe/);
	});

	// AC-3: Subscription-Kacheln mit Schedule-Label werden gerendert
	test('AC-3: Subscription-Kacheln mit Name und Schedule-Label sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt und hat Subscriptions
		 * WHEN: User öffnet /
		 * THEN: data-testid="subscription-card-<id>" (data-kind="vergleich") sichtbar mit Name und Schedule-Label
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		// #2346 S2: Vergleichs-Kacheln stehen in der Card „Außerdem beobachtet" (div, keine section).
		const cards = page.locator('[data-testid^="subscription-card-"][data-kind="vergleich"]');
		await expect(cards.first()).toBeVisible();
		await expect(cards.first().locator('a[href^="/compare/"]').first()).toBeVisible();
		await expect(cards.first().locator('[data-field="next-send"]')).toHaveText(/^nächster ((Mo|Di|Mi|Do|Fr|Sa|So) \d{2}:\d{2} \(|—$)|pausiert|beendet|manueller Versand|abgeschaltet|kein Termin/);
	});

	// AC-4: Trip-Kachel navigiert zu /trips/{id}
	test('AC-4: Trip-Kachel navigiert zu /trips/{trip.id}', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt und hat Trips
		 * WHEN: User klickt auf eine Trip-Kachel
		 * THEN: Browser navigiert zu /trips/{trip.id} (nicht nur /trips)
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		const card = page.locator('[data-testid^="subscription-card-"][data-kind="trip"]').first();
		await expect(card).toBeVisible();

		// #2346 S2: der Name der Kachel ist ein echter Link auf /trips/{id}
		const href = await card.locator('a').first().getAttribute('href');
		expect(href).toMatch(/^\/trips\/[a-zA-Z0-9_-]+$/);
	});

	// AC-5: Subscription-Kachel navigiert zu /compare
	test('AC-5: Subscription-Kachel navigiert zu /compare', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt und hat Subscriptions
		 * WHEN: User klickt auf eine Subscription-Kachel
		 * THEN: Browser navigiert zu /compare
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		const card = page.locator('[data-testid^="subscription-card-"][data-kind="vergleich"]').first();
		const id = (await card.getAttribute('data-testid'))!.replace('subscription-card-', '');
		// #2346 S2: der Name der Kachel ist ein echter Link auf /compare/{id}
		await card.locator(`a[href="/compare/${id}"]`).click();
		await page.waitForURL(new RegExp(`/compare/${id}(\\?|$)`));
		expect(page.url()).toContain(`/compare/${id}`);
	});

	// AC-6: CTAs sichtbar (+ Neue Trip, + Neuer Vergleich)
	test('AC-6: CTA-Links für neue Trip und neuen Vergleich sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt und hat Daten
		 * WHEN: User öffnet /
		 * THEN: "Neue Trip"- und "Neuer Vergleich"-Links sind sichtbar
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('a', { hasText: /\+ Neue Trip/ })).toBeVisible();
		await expect(page.locator('a', { hasText: /\+ Neuer Vergleich/ })).toBeVisible();
	});

	// AC-7: Kein Forecast-API-Call und kein Scheduler-Status-Call
	test('AC-7: kein /api/forecast- und kein /api/scheduler-API-Call', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN: User öffnet /
		 * THEN: Kein API-Call auf /api/forecast und kein Call auf /api/scheduler/status
		 */
		const forbiddenCalls: string[] = [];

		page.on('request', (req) => {
			const url = req.url();
			if (url.includes('/api/forecast') || url.includes('/api/scheduler/status')) {
				forbiddenCalls.push(url);
			}
		});

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		expect(forbiddenCalls).toHaveLength(0);
	});

	// AC-8: Mobile-Grid — 1-spaltig < 640px, 2-spaltig >= 640px
	test('AC-8: Kacheln 1-spaltig auf Mobile, 2-spaltig ab 640px', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt und hat Trips
		 * WHEN: Viewport auf 390px (Mobile) gesetzt
		 * THEN: Kacheln einspaltig (gleiche X-Position); ab 640px mindestens 2 Spalten
		 */
		// Mobile (390px): alle Kacheln in gleicher X-Spalte
		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		const cards = page.locator('[data-testid^="subscription-card-"][data-kind="trip"]');
		const count = await cards.count();

		if (count >= 2) {
			const box0 = await cards.nth(0).boundingBox();
			const box1 = await cards.nth(1).boundingBox();
			expect(box0).not.toBeNull();
			expect(box1).not.toBeNull();
			// Auf Mobile müssen Kacheln in gleicher Spalte sein (gleicher X-Wert)
			expect(box0!.x).toBeCloseTo(box1!.x, 0);
		}

		// Tablet (640px): mindestens 2 Kacheln nebeneinander
		await page.setViewportSize({ width: 640, height: 900 });
		await page.reload();
		await page.waitForLoadState('networkidle');

		if (count >= 2) {
			const box0 = await cards.nth(0).boundingBox();
			const box1 = await cards.nth(1).boundingBox();
			expect(box0).not.toBeNull();
			expect(box1).not.toBeNull();
			// Ab 640px: Kacheln nebeneinander (unterschiedliche X-Werte)
			expect(box0!.x).not.toBeCloseTo(box1!.x, 0);
		}
	});
});
