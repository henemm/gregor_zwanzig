// Playwright E2E — Mobile Tab-Leisten: MTabBar (aktiver Tab sichtbar + A11y)
//
// Spec: docs/specs/modules/mobile_tab_leisten_mtabbar.md (Iteration 1)
// Soll: docs/design-requests/mobile_usability_tab_leisten_soll.md (Option a)
//
// Verhalten: Auf Mobile (<900px) zeigt die Trip-Detail-Tab-Leiste ein
// horizontales Band mit Fade; der AKTIVE Tab ist nach dem Laden (Deep-Link)
// und nach jedem Wechsel ohne User-Geste am Anfang des sichtbaren Bereichs
// positioniert. Semantik: tablist/tab, aria-selected, roving tabindex,
// Pfeiltasten. Trigger >= 44px. Desktop >=900px unveraendert.
//
// Ausfuehrung:
//   cd frontend && npx playwright test mobile-tab-bar.spec.ts

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

async function openTripDetail(page: import('@playwright/test').Page, width: number, height: number, tab = 'overview') {
	await page.setViewportSize({ width, height });
	await page.goto(`/trips/${TRIP_ID}?tab=${tab}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 10_000 });
}

/** Aktiver Tab vollständig im sichtbaren Viewport (horizontal)? */
async function expectActiveTabVisible(page: import('@playwright/test').Page) {
	const active = page.getByRole('tab', { selected: true });
	await expect(active).toBeVisible();
	const box = await active.boundingBox();
	expect(box).not.toBeNull();
	expect(box!.x).toBeGreaterThanOrEqual(0);
	expect(box!.x + box!.width).toBeLessThanOrEqual(390 + 1);
}

// =============================================================================
// Mobile (<900px): aktiver Tab immer sichtbar
// =============================================================================

test('Mobile: Deep-Link ?tab=alarme positioniert aktiven Tab sichtbar', async ({ page }) => {
	await openTripDetail(page, 390, 844, 'alarme');
	await expectActiveTabVisible(page);
});

test('Mobile: Tab-Wechsel auf letzten Tab positioniert ihn sichtbar', async ({ page }) => {
	await openTripDetail(page, 390, 844, 'overview');
	// Transport: Klick per dispatchEvent — Playwrights Actionability-Scroll
	// kämpft mit Scroll-Snap + Fade-Maske des Bands. Was hier bewiesen wird,
	// ist das Verhalten NACH dem Wechsel, nicht der Klick-Transport selbst.
	await page.getByTestId('trip-detail-tab-preview').dispatchEvent('click');
	await expect(page.getByTestId('trip-detail-tab-preview')).toHaveAttribute('aria-selected', 'true');
	await expectActiveTabVisible(page);
});

test('Mobile: A11y — tablist/tab, aria-selected, roving tabindex, Pfeiltasten', async ({ page }) => {
	await openTripDetail(page, 390, 844, 'overview');

	// Semantik
	const tablist = page.getByRole('tablist');
	await expect(tablist).toBeVisible();
	const tabs = tablist.getByRole('tab');
	expect(await tabs.count()).toBe(7);
	await expect(page.getByTestId('trip-detail-tab-overview')).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByTestId('trip-detail-tab-stages')).toHaveAttribute('aria-selected', 'false');

	// Roving tabindex: nur der aktive Tab ist per Tab erreichbar
	await expect(page.getByTestId('trip-detail-tab-overview')).toHaveAttribute('tabindex', '0');
	await expect(page.getByTestId('trip-detail-tab-stages')).toHaveAttribute('tabindex', '-1');

	// Pfeiltaste rechts aktiviert den Folge-Tab
	await page.getByTestId('trip-detail-tab-overview').focus();
	await page.keyboard.press('ArrowRight');
	await expect(page.getByTestId('trip-detail-tab-stages')).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByTestId('trip-detail-tab-stages')).toBeFocused();
});

test('Mobile: Trigger sind mindestens 44px hoch', async ({ page }) => {
	await openTripDetail(page, 390, 844, 'overview');
	const tabs = page.getByRole('tablist').getByRole('tab');
	const count = await tabs.count();
	expect(count).toBe(7);
	for (let i = 0; i < count; i++) {
		const box = await tabs.nth(i).boundingBox();
		expect(box).not.toBeNull();
		expect(box!.height).toBeGreaterThanOrEqual(44);
	}
});

test('Mobile: Badges sichtbar (Etappen-Zähler)', async ({ page }) => {
	await openTripDetail(page, 390, 844, 'overview');
	const badge = page.getByTestId('trip-detail-tab-badge-stages');
	await expect(badge).toBeVisible();
	await expect(badge).toHaveText('3');
});

// =============================================================================
// Desktop (>=900px): Aussehen/Verhalten unveraendert (Smoke)
// =============================================================================

test('Desktop: Tab-Leiste unveraendert — alle Tabs ohne Band-Scroll sichtbar', async ({ page }) => {
	await openTripDetail(page, 1280, 900, 'overview');

	// Kein horizontales Scrollband: alle 7 Tabs liegen nebeneinander im Viewport
	const tabs = page.getByRole('tablist').getByRole('tab');
	expect(await tabs.count()).toBe(7);
	for (let i = 0; i < 7; i++) {
		const box = await tabs.nth(i).boundingBox();
		expect(box).not.toBeNull();
		expect(box!.x + box!.width).toBeLessThanOrEqual(1280);
	}

	// Unterline-Optik: aktiver Tab transparent mit Accent-Unterstrich
	const active = page.getByTestId('trip-detail-tab-overview');
	const bg = await active.evaluate((el) => getComputedStyle(el).backgroundColor);
	expect(bg).toBe('rgba(0, 0, 0, 0)');
});
