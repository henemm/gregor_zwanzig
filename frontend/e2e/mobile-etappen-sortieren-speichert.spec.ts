// #2288 F006: die mobile Etappenliste (SortableList, vertikal) teilt `handleReorderEnd`
// mit dem Desktop-Strip und speichert seit #2288 beim Ablegen. Gemessen: Ziehen per
// Pointer-Geste -> genau EIN Speichern mit der neuen Reihenfolge, nichts bricht.

import { test, expect } from '@playwright/test';
import { dragDndZoneItem } from './helpers';

const TRIP_ID = 'e2e-2288-mobile';
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });
const stages = Array.from({ length: 3 }, (_, i) => ({
	id: `s${i + 1}`,
	name: `Tag ${i + 1}`,
	date: `2026-08-${String(i + 1).padStart(2, '0')}`,
	waypoints: [wp(`a${i}`, 42 + i * 0.1), wp(`b${i}`, 42.04 + i * 0.1)]
}));

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

test('Mobile: Etappe ziehen speichert die neue Reihenfolge genau einmal', async ({ page }) => {
	test.setTimeout(60_000);
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: { id: TRIP_ID, name: 'E2E #2288 Mobil', region: 'Korsika', stages }
	});
	expect(res.ok()).toBeTruthy();
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);

	let puts = 0;
	page.on('request', (r) => {
		if (r.method() === 'PUT' && r.url().includes(`/api/trips/${TRIP_ID}`)) puts++;
	});
	const items = page.locator('.sortable-item');
	await dragDndZoneItem(page, items.nth(0), items.nth(1));

	await expect
		.poll(
			async () =>
				(await (await page.request.get(`/api/trips/${TRIP_ID}`)).json()).stages.map(
					(s: { id: string }) => s.id
				),
			{ timeout: 15_000 }
		)
		.toEqual(['s2', 's1', 's3']);
	await page.waitForTimeout(1_000);
	expect(puts).toBe(1);
});
