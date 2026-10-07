// TDD RED — #2288 (Epic #2345 P2): Etappen-Strip sortiert über den geteilten
// Baustein `SortableList` (svelte-dnd-action, Pointer-Events + Tastatur).
// Spec: docs/specs/modules/etappen_strip_sortable_list.md — AC-1, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8.
// (AC-10 Touch: etappen-strip-touch-dnd.spec.ts; AC-2 Wächter: no_native_draggable_guard.test.ts)
//
// Auth via storageState (playwright.config 'tests'-Projekt → admin.json).
// Gemessen wird die Browser-Geste, nicht der Quelltext.

import { test, expect, type Page } from '@playwright/test';
import { dragDndZoneItem } from './helpers';

const TRIP_ID = 'e2e-2288-strip';
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const mkStages = (n: number) =>
	Array.from({ length: n }, (_, i) => ({
		id: `s${i + 1}`,
		name: `Tag ${i + 1}`,
		date: `2026-08-${String(i + 1).padStart(2, '0')}`,
		waypoints: [wp(`a${i}`, 42 + i * 0.1), wp(`b${i}`, 42.04 + i * 0.1)]
	}));

async function seed(page: Page, n: number) {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: { id: TRIP_ID, name: 'E2E #2288 Strip', region: 'Korsika', stages: mkStages(n) }
	});
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
}

async function openEditor(page: Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('etappen-strip')).toBeVisible();
}

const strip = (page: Page) => page.getByTestId('etappen-strip');
const card = (page: Page, i: number) => strip(page).getByTestId(`stage-card-${i}`);

async function storedOrder(page: Page): Promise<string[]> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	return (await res.json()).stages.map((s: { id: string }) => s.id);
}

/** Zählt `finalize`/`consider` der Strip-Zone über die gesamte Geste. */
async function watchZone(page: Page) {
	await page.evaluate(() => {
		const z = document.querySelector('[data-testid="etappen-strip"] .sortable-zone') as
			| (HTMLElement & { __c?: { consider: number; finalize: number } })
			| null;
		if (!z) throw new Error('keine .sortable-zone im Strip');
		z.__c = { consider: 0, finalize: 0 };
		z.addEventListener('consider', () => z.__c!.consider++);
		z.addEventListener('finalize', () => z.__c!.finalize++);
	});
	return () =>
		page.evaluate(
			() =>
				(
					document.querySelector('[data-testid="etappen-strip"] .sortable-zone') as HTMLElement & {
						__c: { consider: number; finalize: number };
					}
				).__c
		);
}

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

test('AC-1: Reihenfolge wird erst beim Ablegen gemeldet und gespeichert, nie während des Ziehens', async ({
	page
}) => {
	test.setTimeout(60_000);
	await seed(page, 3);
	await openEditor(page);
	const counts = await watchZone(page);

	const src = await card(page, 1).boundingBox();
	const dst = await card(page, 0).boundingBox();
	if (!src || !dst) throw new Error('Karten ohne BoundingBox');
	await page.mouse.move(src.x + src.width / 2, src.y + src.height / 2);
	await page.mouse.down();
	await page.mouse.move(src.x + src.width / 2 - 12, src.y + src.height / 2, { steps: 6 });
	await page.waitForTimeout(120);
	await page.mouse.move(dst.x + dst.width / 2, dst.y + dst.height / 2, { steps: 15 });
	await page.waitForTimeout(400);

	// Mitten in der Geste: gezogen wird (consider), aber NICHTS gemeldet/gespeichert.
	expect((await counts()).finalize, 'finalize schon vor dem Loslassen').toBe(0);
	expect(await storedOrder(page), 'Reihenfolge schon vor dem Loslassen gespeichert').toEqual([
		's1',
		's2',
		's3'
	]);

	await page.mouse.up();
	await expect.poll(async () => (await counts()).finalize, { timeout: 5_000 }).toBe(1);
	await expect.poll(() => storedOrder(page), { timeout: 15_000 }).toEqual(['s2', 's1', 's3']);
	await expect(card(page, 0)).toContainText('Tag 2');
});

test('AC-3: Pause-Lücke wandert mit dem Item, „+ Etappe" bleibt am Strip-Ende', async ({ page }) => {
	test.setTimeout(60_000);
	await seed(page, 4);
	await openEditor(page);
	// Vorher: Lücken nach 0,1,2 — nicht nach 3.
	for (const i of [0, 1, 2]) await expect(page.getByTestId(`etappen-strip-pause-after-${i}`)).toHaveCount(1);
	await expect(page.getByTestId('etappen-strip-pause-after-3')).toHaveCount(0);

	await dragDndZoneItem(page, card(page, 0), card(page, 1));
	await expect(card(page, 0)).toContainText('Tag 2');
	await expect(card(page, 1)).toContainText('Tag 1');

	// Nach dem Umsortieren: weiterhin genau n-1 Lücken, keine hinter der letzten Karte.
	for (const i of [0, 1, 2]) await expect(page.getByTestId(`etappen-strip-pause-after-${i}`)).toHaveCount(1);
	await expect(page.getByTestId('etappen-strip-pause-after-3')).toHaveCount(0);

	// „+ Etappe" sichtbar, rechts von der letzten Karte, im selben Strip, klickbar.
	const add = strip(page).getByRole('button', { name: /\+ Etappe/ });
	await expect(add).toBeVisible();
	const last = await card(page, 3).boundingBox();
	const addBox = await add.boundingBox();
	expect(addBox!.x, '„+ Etappe" muss hinter der letzten Karte stehen').toBeGreaterThan(
		last!.x + last!.width - 1
	);
	await add.click();
	await expect(strip(page).locator('[data-testid^="stage-card-"]')).toHaveCount(5);
});

test('AC-3: „+ Pause" nach der umsortierten Position fügt dort die Pause ein', async ({ page }) => {
	test.setTimeout(60_000);
	await seed(page, 3);
	await openEditor(page);
	await dragDndZoneItem(page, card(page, 0), card(page, 1));
	await expect(card(page, 0)).toContainText('Tag 2');

	const gap = page.getByTestId('etappen-strip-pause-after-0');
	await gap.hover();
	await gap.click();
	// Pause steht jetzt an Position 1 (hinter „Tag 2"), nicht am Ende.
	await expect(strip(page).getByTestId('stage-card-pause-1')).toBeVisible();
	await expect(card(page, 0)).toContainText('Tag 2');
});

test('AC-4: Ziehen quer über wachsende Pause-Lücken bricht nicht ab, genau ein finalize', async ({
	page
}) => {
	test.setTimeout(60_000);
	await seed(page, 4);
	await openEditor(page);
	const counts = await watchZone(page);

	const src = await card(page, 0).boundingBox();
	if (!src) throw new Error('keine BoundingBox');
	await page.mouse.move(src.x + src.width / 2, src.y + src.height / 2);
	await page.mouse.down();
	await page.mouse.move(src.x + src.width / 2 + 12, src.y + src.height / 2, { steps: 6 });
	// Zeigerpfad quer durch mindestens zwei Lücken, auf die Mitte der letzten Karte.
	for (const i of [1, 2, 3]) {
		const b = await card(page, i).boundingBox();
		await page.mouse.move(b!.x + b!.width / 2, b!.y + b!.height / 2, { steps: 12 });
		await page.waitForTimeout(200);
	}
	await page.mouse.up();

	await expect.poll(async () => (await counts()).finalize, { timeout: 5_000 }).toBe(1);
	const order = await storedOrder(page);
	// Spec AC-4: „Reihenfolge danach korrekt" — Tag 1 über alle Lücken ans Ende.
	expect(order, 'Endreihenfolge nach Zug über drei Lücken').toEqual(['s2', 's3', 's4', 's1']);
});

test('AC-4 (M12): schnelle Geste ohne Pausen über mehrere Karten landet auf der letzten Station', async ({
	page
}) => {
	// svelte-dnd-action tastet den Zeiger nur alle flipDurationMs*1,07 ab; ohne
	// flipDurationMs=0 am Strip würde die Zwischenstation übersprungen.
	test.setTimeout(60_000);
	await seed(page, 4);
	await openEditor(page);
	const counts = await watchZone(page);

	const c = async (i: number) => {
		const b = await card(page, i).boundingBox();
		return { x: b!.x + b!.width / 2, y: b!.y + b!.height / 2 };
	};
	const start = await c(0);
	await page.mouse.move(start.x, start.y);
	await page.mouse.down();
	await page.mouse.move(start.x, start.y - 12, { steps: 6 });
	for (const station of [3, 1]) {
		const p = await c(station);
		await page.mouse.move(p.x, p.y, { steps: 8 });
		await page.mouse.move(p.x, p.y);
	}
	await page.mouse.up();
	await expect.poll(async () => (await counts()).finalize, { timeout: 5_000 }).toBe(1);
	await expect
		.poll(() => storedOrder(page), { timeout: 15_000 })
		.toEqual(['s2', 's1', 's3', 's4']);
});

test('AC-4 (M13): Lücke wächst NICHT, solange gezogen wird (Maustaste gedrückt)', async ({ page }) => {
	test.setTimeout(60_000);
	await seed(page, 4);
	await openEditor(page);

	const src = await card(page, 0).boundingBox();
	await page.mouse.move(src!.x + src!.width / 2, src!.y + src!.height / 2);
	await page.mouse.down();
	await page.mouse.move(src!.x + src!.width / 2 + 12, src!.y + src!.height / 2, { steps: 6 });
	// Zeiger auf eine Lücke (Mitte der Lücke nach Platz 1) und dort halten.
	const gap = page.getByTestId('etappen-strip-pause-after-1');
	const g = await gap.boundingBox();
	await page.mouse.move(g!.x + g!.width / 2, g!.y + g!.height / 2, { steps: 10 });
	await page.waitForTimeout(500); // länger als die 140-ms-Übergangsanimation
	const w = await page
		.locator('[data-testid="etappen-strip"] [data-testid^="etappen-strip-pause-after-"]')
		.evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().width)));
	await page.mouse.up();
	expect(Math.max(...w), 'Lücke wurde während des Ziehens aufgeweitet').toBeLessThanOrEqual(8);
});

test('AC-6: Strip-Zone läuft als Zeile; Bestandsliste (mobile Etappenliste / Orte) bleibt Spalte', async ({
	page
}) => {
	await seed(page, 3);
	await openEditor(page);
	const dir = await strip(page)
		.locator('.sortable-zone')
		.evaluate((el) => getComputedStyle(el).flexDirection);
	expect(dir).toBe('row');
	// Items schrumpfen nicht (sonst werden Karten bei vielen Etappen gequetscht).
	const shrink = await strip(page)
		.locator('.sortable-item')
		.first()
		.evaluate((el) => getComputedStyle(el).flexShrink);
	expect(shrink).toBe('0');
});

test('AC-7: Tastatur — Griff fokussieren, Leertaste, Pfeil, Leertaste meldet genau einmal', async ({
	page
}) => {
	test.setTimeout(60_000);
	await seed(page, 3);
	await openEditor(page);
	const counts = await watchZone(page);

	await expect(strip(page).locator('.sortable-zone')).toHaveAttribute('aria-label', 'Etappen sortieren');
	const handles = strip(page).getByTestId('drag-handle');
	await expect(handles).toHaveCount(3);
	for (let i = 0; i < 3; i++) await expect(handles.nth(i)).toHaveAttribute('aria-label', /.+/);

	await handles.first().focus();
	await page.keyboard.press('Space');
	await page.keyboard.press('ArrowRight');
	expect((await counts()).finalize, 'finalize vor dem zweiten Leertasten-Druck').toBe(0);
	await page.keyboard.press('Space');

	await expect.poll(async () => (await counts()).finalize, { timeout: 5_000 }).toBe(1);
	await expect.poll(() => storedOrder(page), { timeout: 15_000 }).toEqual(['s2', 's1', 's3']);
});

test('AC-8: Autoscroll — Karte am rechten Rand halten scrollt den Strip, Ablegen am Ende', async ({
	page
}) => {
	test.setTimeout(90_000);
	await seed(page, 14);
	await openEditor(page);

	const z = strip(page);
	const overflow = await z.evaluate((el) => el.scrollWidth - el.clientWidth);
	expect(overflow, 'Strip läuft nicht über — Testaufbau zu klein').toBeGreaterThan(200);
	const scrollBefore = await z.evaluate((el) => el.scrollLeft);

	const src = await card(page, 0).boundingBox();
	const box = await z.boundingBox();
	if (!src || !box) throw new Error('keine BoundingBox');
	await page.mouse.move(src.x + src.width / 2, src.y + src.height / 2);
	await page.mouse.down();
	await page.mouse.move(src.x + src.width / 2 + 12, src.y + src.height / 2, { steps: 6 });
	await page.mouse.move(box.x + box.width - 8, box.y + box.height / 2, { steps: 20 });
	await page.waitForTimeout(2_500);

	const scrollAfter = await z.evaluate((el) => el.scrollLeft);
	expect(scrollAfter - scrollBefore, 'Strip hat nicht automatisch gescrollt').toBeGreaterThan(src.width);

	await page.mouse.up();
	await expect
		.poll(async () => (await storedOrder(page)).indexOf('s1'), { timeout: 15_000 })
		.toBeGreaterThan(3);
});
