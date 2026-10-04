// Playwright E2E — Compare-Detail Tab-Leiste auf dem MTabBar-Baustein
//
// Spec: docs/specs/modules/mobile_tab_leisten_mtabbar.md (Iteration 2)
// Soll: docs/design-requests/mobile_usability_tab_leisten_soll.md (Option a,
// AP-006 — CompareTabs rendert denselben Baustein wie TripTabs).
//
// Verhalten: Auf Mobile (<900px) ist der aktive Tab nach Deep-Link und nach
// jedem Wechsel am Anfang des sichtbaren Bandbereichs positioniert; Semantik
// tablist/tab mit roving tabindex; Trigger >= 44px; Orte-Badge sichtbar mit
// korrekter Zahl. Desktop >=900px: Optik 1:1 (13px, 12/16px, neutraler
// Badge) — kein visueller Unterschied zur bisherigen Compare-Leiste.
//
// Ausfuehrung:
//   cd frontend && npx playwright test compare-tab-bar.spec.ts

import { test, expect } from '@playwright/test';

async function seedPreset(page: import('@playwright/test').Page): Promise<string> {
	// Eindeutiger Name je Lauf (Muster compare-hub-name-region-profil.spec.ts) —
	// vermeidet 409-Altbestand-Konflikte; Aufraeumen ueber afterEach-Delete +
	// global.teardown (E2E-GZ-Praefix).
	const body = {
		name: `E2E-GZ MTabBar Compare ${Date.now()}`,
		location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai', 'e2e-loc-zillertal'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 7,
		hour_to: 16,
		empfaenger: []
	};
	const res0 = await page.request.post('/api/compare/presets', { data: body });
	let res = res0;
	if (res.status() === 409) {
		// Quota: max. 2 aktive Vergleiche je User. E2E-Altbestand (z.B. abgebrochene
		// Laeufe) raeumen — gleiche Philosophie wie global.teardown (E2E-GZ-Praefix)
		// — und einmal erneut versuchen.
		const list = await page.request.get('/api/compare/presets');
		if (list.ok()) {
			const presets = (await list.json()) as { id?: string; name?: string }[];
			for (const p of presets.filter((p) => (p.name ?? '').startsWith('E2E-GZ'))) {
				await page.request.delete(`/api/compare/presets/${p.id}`).catch(() => {});
			}
		}
		res = await page.request.post('/api/compare/presets', { data: body });
	}
	expect(res.ok(), `Preset-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
	return ((await res.json()) as { id: string }).id;
}

async function openCompare(page: import('@playwright/test').Page, presetId: string, width: number, height: number, tab = 'uebersicht') {
	await page.setViewportSize({ width, height });
	await page.goto(`/compare/${presetId}?tab=${tab}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });
}

async function expectActiveTabVisible(page: import('@playwright/test').Page) {
	// Scope auf den MTabBar-Baustein (.mtabbar) — das Panel-Segmented im
	// Versand-Tab rendert ebenfalls role="tab" mit aria-selected.
	const active = page.locator('.mtabbar').getByRole('tab', { selected: true });
	await expect(active).toBeVisible();
	const box = await active.boundingBox();
	expect(box).not.toBeNull();
	expect(box!.x).toBeGreaterThanOrEqual(0);
	expect(box!.x + box!.width).toBeLessThanOrEqual(390 + 1);
}

let presetId: string;

test.beforeEach(async ({ page }) => {
	presetId = await seedPreset(page);
});

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
});

// =============================================================================
// Mobile (<900px): aktiver Tab immer sichtbar + A11y + 44px
// =============================================================================

test('Mobile Compare: Deep-Link ?tab=versand positioniert aktiven Tab sichtbar', async ({ page }) => {
	await openCompare(page, presetId, 390, 844, 'versand');
	await expectActiveTabVisible(page);
});

test('Mobile Compare: A11y — tablist/tab, aria-selected, roving tabindex, Pfeiltasten', async ({ page }) => {
	await openCompare(page, presetId, 390, 844, 'uebersicht');

	const tablist = page.getByRole('tablist');
	await expect(tablist).toBeVisible();
	expect(await tablist.getByRole('tab').count()).toBe(7);

	await expect(page.getByTestId('compare-detail-tab-uebersicht')).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByTestId('compare-detail-tab-uebersicht')).toHaveAttribute('tabindex', '0');
	await expect(page.getByTestId('compare-detail-tab-orte')).toHaveAttribute('tabindex', '-1');

	await page.getByTestId('compare-detail-tab-uebersicht').focus();
	await page.keyboard.press('ArrowRight');
	await expect(page.getByTestId('compare-detail-tab-orte')).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByTestId('compare-detail-tab-orte')).toBeFocused();
});

test('Mobile Compare: Trigger >= 44px, Orte-Badge mit korrekter Zahl', async ({ page }) => {
	await openCompare(page, presetId, 390, 844, 'uebersicht');

	const tabs = page.getByRole('tablist').getByRole('tab');
	expect(await tabs.count()).toBe(7);
	for (let i = 0; i < 7; i++) {
		const box = await tabs.nth(i).boundingBox();
		expect(box!.height).toBeGreaterThanOrEqual(44);
	}

	// Orte-Badge: 3 geseedete Locations
	const badge = page.getByTestId('compare-detail-tab-orte').locator('[data-slot="segmented-badge"]');
	await expect(badge).toBeVisible();
	await expect(badge).toHaveText('3');
});

// =============================================================================
// Desktop (>=900px): Optik 1:1 — Smoke
// =============================================================================

test('Desktop Compare: Leiste ohne Band-Scroll, neutraler Badge, Optik unveraendert', async ({ page }) => {
	await openCompare(page, presetId, 1280, 900, 'uebersicht');

	const tabs = page.getByRole('tablist').getByRole('tab');
	expect(await tabs.count()).toBe(7);
	for (let i = 0; i < 7; i++) {
		const box = await tabs.nth(i).boundingBox();
		expect(box!.x + box!.width).toBeLessThanOrEqual(1280);
	}

	// Neutraler Badge (paper-deep/ink-3) wie bisheriger Compare-Stil —
	// KEIN Accent-Fill (Badges neutral, Design-Doc Paket 2).
	const badge = page.getByTestId('compare-detail-tab-orte').locator('[data-slot="segmented-badge"]');
	const bg = await badge.evaluate((el) => getComputedStyle(el).backgroundColor);
	expect(bg).toBe('rgb(236, 234, 217)'); // --g-paper-deep

	// 13px-Schrift der Trigger wie bisher (0.8125rem)
	const fontSize = await page.getByTestId('compare-detail-tab-uebersicht').evaluate(
		(el) => getComputedStyle(el).fontSize
	);
	expect(fontSize).toBe('13px');
});
