// TDD RED — #2288 AC-10: Etappen-Strip per ECHTER Touch-Geste sortieren.
// Spec: docs/specs/modules/etappen_strip_sortable_list.md — AC-10.
//
// Echte Touch-Ereignisse über das Chrome-DevTools-Protokoll
// (`Input.dispatchTouchEvent`, Helfer `dragDndZoneItemTouch`), Kontext
// `hasTouch: true` bei Desktop-Breite — also der Desktop-Strip, nicht der
// Mobil-Zweig. KEINE Mausereignisse (sonst misst der Test nur AC-1 noch einmal).

import { test, expect, type Page } from '@playwright/test';
import { dragDndZoneItemTouch } from './helpers';

const TRIP_ID = 'e2e-2288-touch';
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });
const stages = [1, 2, 3].map((n) => ({
	id: `s${n}`,
	name: `Tag ${n}`,
	date: `2026-08-0${n}`,
	waypoints: [wp(`a${n}`, 42 + n * 0.1), wp(`b${n}`, 42.04 + n * 0.1)]
}));

test.use({ hasTouch: true, viewport: { width: 1280, height: 800 } });

async function storedOrder(page: Page): Promise<string[]> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	return (await res.json()).stages.map((s: { id: string }) => s.id);
}

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: { id: TRIP_ID, name: 'E2E #2288 Touch', region: 'Korsika', stages }
	});
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

test('AC-10: Fingergeste sortiert die Etappen um, speichert nur beim Ablegen, scrollt die Seite nicht', async ({
	page
}) => {
	test.setTimeout(60_000);
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('etappen-strip')).toBeVisible();
	const card = (i: number) => page.getByTestId('etappen-strip').getByTestId(`stage-card-${i}`);

	const { pageScrolledY } = await dragDndZoneItemTouch(page, card(2), card(0));

	await expect(card(0)).toContainText('Tag 3');
	await expect.poll(() => storedOrder(page), { timeout: 15_000 }).toEqual(['s3', 's1', 's2']);
	expect(pageScrolledY, 'die Seite hat gescrollt statt die Karte zu ziehen').toBeLessThan(5);
});
