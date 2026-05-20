// E2E — Issue #269: Mobile Trip-Detail-Tabs Pill-Scroller
//
// Spec: docs/specs/modules/bug_269_mobile_trip_tabs.md (AC-1 bis AC-4)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, weil TripTabs.svelte noch
// kein overflow-x: auto / white-space: nowrap / Pill-Styling auf Mobile hat.
//
// TestID-Inventar (bereits vorhanden):
//   trip-detail-tab-list          — Tabs.List Container
//   trip-detail-tab-{value}       — Tabs.Trigger für jeden Tab

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const MOBILE_VIEWPORT = { width: 375, height: 667 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test.describe('Issue #269: Mobile Trip-Detail-Tabs Pill-Scroller', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Alle 6 Tabs horizontal scrollbar erreichbar ──────────────────
	test('AC-1: Tab-Liste ist auf Mobile horizontal scrollbar (overflow-x: auto)', async ({
		page
	}) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile)
		 * WHEN:  Trip-Detail-Seite geladen
		 * THEN:  .trip-tabs-list hat overflow-x: auto
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const list = page.getByTestId('trip-detail-tab-list');
		await expect(list).toBeVisible();

		const overflowX = await list.evaluate((el) => getComputedStyle(el).overflowX);
		expect(overflowX).toBe('auto');
	});

	test('AC-1b: Alle 6 Tabs sind im DOM und per scrollIntoView erreichbar', async ({ page }) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile)
		 * WHEN:  Trip-Detail-Seite geladen
		 * THEN:  Alle 6 Tab-Trigger sind im DOM vorhanden (nicht display:none)
		 *        und können per scrollIntoView fokussiert werden
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const tabs = ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview'];
		for (const tab of tabs) {
			const trigger = page.getByTestId(`trip-detail-tab-${tab}`);
			// Im DOM vorhanden
			await expect(trigger).toHaveCount(1);
			// Per scrollIntoView erreichbar und dann sichtbar
			await trigger.scrollIntoViewIfNeeded();
			await expect(trigger).toBeVisible();
		}
	});

	// ─── AC-2: Tab-Labels einzeilig (kein Umbruch) ──────────────────────────
	test('AC-2: Tab-Labels sind einzeilig auf Mobile (white-space: nowrap)', async ({ page }) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile)
		 * WHEN:  Trip-Detail-Seite geladen
		 * THEN:  Alle Tab-Trigger haben white-space: nowrap
		 *        (kein Umbruch bei "Etappen & Wegpunkte")
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const tabs = ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview'];
		for (const tab of tabs) {
			const trigger = page.getByTestId(`trip-detail-tab-${tab}`);
			const whiteSpace = await trigger.evaluate((el) => getComputedStyle(el).whiteSpace);
			expect(whiteSpace, `Tab "${tab}" hat keinen white-space: nowrap`).toBe('nowrap');
		}
	});

	test('AC-2b: "Etappen & Wegpunkte" Tab ist nicht höher als eine Zeile auf Mobile', async ({
		page
	}) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile)
		 * WHEN:  Trip-Detail-Seite geladen
		 * THEN:  Höhe des "stages"-Triggers ist < 40px (einzeilig)
		 *        Bei Umbruch wäre er ~44px+ (2 Zeilen à ~14px + Padding)
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const stagesTab = page.getByTestId('trip-detail-tab-stages');
		const height = await stagesTab.evaluate((el) => el.getBoundingClientRect().height);
		// Einzeilig: Padding (0.375rem × 2 = ~12px) + Line-Height (~20px) ≈ 32px
		// Zweizeilig wäre ≈ 44px+
		expect(height, `"Etappen & Wegpunkte"-Tab ist ${height}px hoch (Umbruch?)`).toBeLessThan(40);
	});

	// ─── AC-3: Aktiver Tab als Pill dargestellt ──────────────────────────────
	test('AC-3: Aktiver Tab hat auf Mobile Pill-Hintergrund (--g-accent)', async ({ page }) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile)
		 * WHEN:  Trip-Detail-Seite geladen, "Übersicht" ist aktiv
		 * THEN:  Aktiver Tab-Trigger hat background-color: rgb(196, 90, 42) (#c45a2a)
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const activeTab = page.getByTestId('trip-detail-tab-overview');
		await expect(activeTab).toHaveAttribute('data-state', 'active');

		const bgColor = await activeTab.evaluate((el) => getComputedStyle(el).backgroundColor);
		// --g-accent: #c45a2a = rgb(196, 90, 42)
		expect(bgColor, `Aktiver Tab hat Hintergrund "${bgColor}" statt rgb(196, 90, 42)`).toMatch(
			/rgb\(196,\s*90,\s*42\)/
		);
	});

	test('AC-3b: Aktiver Tab hat auf Mobile hellen Text (--g-paper)', async ({ page }) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile), aktiver Tab = "Übersicht"
		 * WHEN:  Pill-Hintergrund gesetzt
		 * THEN:  Text-Farbe ist helles --g-paper (#f6f4ee = rgb(246, 244, 238))
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const activeTab = page.getByTestId('trip-detail-tab-overview');
		const color = await activeTab.evaluate((el) => getComputedStyle(el).color);
		// --g-paper: #f6f4ee = rgb(246, 244, 238)
		expect(color, `Aktiver Tab hat Textfarbe "${color}" statt hell (g-paper)`).toMatch(
			/rgb\(246,\s*244,\s*238\)/
		);
	});

	test('AC-3c: Inaktiver Tab hat auf Mobile KEINEN Pill-Hintergrund', async ({ page }) => {
		/**
		 * GIVEN: Viewport ist 375×667 px (Mobile), "Übersicht" aktiv
		 * WHEN:  Inaktiver Tab "Etappen & Wegpunkte" betrachtet
		 * THEN:  Hintergrund ist transparent, NICHT --g-accent
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const inactiveTab = page.getByTestId('trip-detail-tab-stages');
		await expect(inactiveTab).toHaveAttribute('data-state', 'inactive');

		const bgColor = await inactiveTab.evaluate((el) => getComputedStyle(el).backgroundColor);
		expect(bgColor, `Inaktiver Tab sollte keinen Akzent-Hintergrund haben`).not.toMatch(
			/rgb\(196,\s*90,\s*42\)/
		);
	});

	// ─── AC-4: Desktop unverändert — Underline-Stil ──────────────────────────
	test('AC-4: Desktop aktiver Tab zeigt orangene Underline (unverändert)', async ({ page }) => {
		/**
		 * GIVEN: Viewport ist 1440×900 px (Desktop)
		 * WHEN:  Trip-Detail-Seite geladen, "Übersicht" aktiv
		 * THEN:  Aktiver Tab hat border-bottom-color: rgb(196, 90, 42) -- Underline
		 *        KEIN gefüllter Pill-Hintergrund
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto(`/trips/${TRIP_ID}`);

		const activeTab = page.getByTestId('trip-detail-tab-overview');
		await expect(activeTab).toHaveAttribute('data-state', 'active');

		const borderBottom = await activeTab.evaluate(
			(el) => getComputedStyle(el).borderBottomColor
		);
		expect(borderBottom).toMatch(/rgb\(196,\s*90,\s*42\)|rgba\(196,\s*90,\s*42/);

		// Desktop: KEIN Pill-Hintergrund
		const bgColor = await activeTab.evaluate((el) => getComputedStyle(el).backgroundColor);
		expect(bgColor, 'Desktop aktiver Tab darf keinen Pill-Hintergrund haben').not.toMatch(
			/rgb\(196,\s*90,\s*42\)/
		);
	});
});
