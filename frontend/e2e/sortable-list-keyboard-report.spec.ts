// #2288 / ADR-0024 AC-4: der geteilte Sortier-Baustein meldet Tastatur-Umsortierungen
// ERST beim Ablegen und genau einmal (die Bibliothek feuert `finalize` nach jedem
// Pfeilschritt). Gemessen an der Wirkung: Anzahl und Zeitpunkt der gespeicherten
// Reihenfolge (PUT) — nicht am DOM-Ereignis. Escape bricht ab: nichts gespeichert,
// Ausgangsreihenfolge sichtbar. Der Etappen-Strip ist hier der Konsument des Bausteins.

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-2288-kbd';
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });
const stages = Array.from({ length: 4 }, (_, i) => ({
	id: `s${i + 1}`,
	name: `Tag ${i + 1}`,
	date: `2026-08-${String(i + 1).padStart(2, '0')}`,
	waypoints: [wp(`a${i}`, 42 + i * 0.1), wp(`b${i}`, 42.04 + i * 0.1)]
}));

async function open(page: Page) {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: { id: TRIP_ID, name: 'E2E #2288 Tastatur', region: 'Korsika', stages }
	});
	expect(res.ok()).toBeTruthy();
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('etappen-strip')).toBeVisible();
}

const stored = async (page: Page): Promise<string[]> =>
	(await (await page.request.get(`/api/trips/${TRIP_ID}`)).json()).stages.map(
		(s: { id: string }) => s.id
	);
const names = (page: Page) =>
	page.getByTestId('etappen-strip').locator('[data-testid^="stage-card-"]').allInnerTexts();

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

test('mehrere Pfeilschritte: genau EIN Speichern, erst beim Ablegen, mit der Endreihenfolge', async ({
	page
}) => {
	test.setTimeout(60_000);
	await open(page);
	let puts = 0;
	page.on('request', (r) => {
		if (r.method() === 'PUT' && r.url().includes(`/api/trips/${TRIP_ID}`)) puts++;
	});

	await page.getByTestId('etappen-strip').getByTestId('drag-handle').first().focus();
	await page.keyboard.press('Space');
	await page.keyboard.press('ArrowRight');
	await page.keyboard.press('ArrowRight');
	await page.waitForTimeout(1500);
	expect(puts, 'Zwischenschritt darf nichts speichern').toBe(0);
	expect(await stored(page)).toEqual(['s1', 's2', 's3', 's4']);

	await page.keyboard.press('Space');
	await expect.poll(() => stored(page), { timeout: 15_000 }).toEqual(['s2', 's3', 's1', 's4']);
	await page.waitForTimeout(1500);
	expect(puts, 'genau ein Speichern fuer die ganze Tastatur-Geste').toBe(1);
});

test('Escape bricht ab: nichts gespeichert, Ausgangsreihenfolge sichtbar', async ({ page }) => {
	test.setTimeout(60_000);
	await open(page);
	let puts = 0;
	page.on('request', (r) => {
		if (r.method() === 'PUT' && r.url().includes(`/api/trips/${TRIP_ID}`)) puts++;
	});

	await page.getByTestId('etappen-strip').getByTestId('drag-handle').first().focus();
	await page.keyboard.press('Space');
	await page.keyboard.press('ArrowRight');
	await page.keyboard.press('Escape');
	await page.waitForTimeout(1500);

	expect(puts).toBe(0);
	expect(await stored(page)).toEqual(['s1', 's2', 's3', 's4']);
	const texts = await names(page);
	expect(texts[0]).toContain('Tag 1');
	expect(texts[1]).toContain('Tag 2');
});

test('Griffwechsel mitten in der Geste meldet den Zwischenstand des ersten Griffs (M26)', async ({
	page
}) => {
	test.setTimeout(60_000);
	await open(page);
	let puts = 0;
	page.on('request', (r) => {
		if (r.method() === 'PUT' && r.url().includes(`/api/trips/${TRIP_ID}`)) puts++;
	});

	const handles = page.getByTestId('etappen-strip').getByTestId('drag-handle');
	await handles.first().focus();
	await page.keyboard.press('Space');
	await page.keyboard.press('ArrowRight');
	// Klick auf ein anderes Item: die Bibliothek beendet die erste Geste ohne
	// consider/dragStopped und startet eine neue (handleClick -> handleDragStart).
	await handles.nth(3).click();
	await expect.poll(() => stored(page), { timeout: 10_000 }).toEqual(['s2', 's1', 's3', 's4']);
	expect(puts, 'genau ein Speichern fuer die erste Geste').toBe(1);
	await page.keyboard.press('Escape'); // zweite Geste ohne Bewegung beenden
	await page.waitForTimeout(500);
	expect(await stored(page)).toEqual(['s2', 's1', 's3', 's4']);
	expect(puts).toBe(1);
});

test('Fokusverlust mitten im Griff meldet den Zwischenstand nach der Frist (M15)', async ({
	page
}) => {
	test.setTimeout(60_000);
	await open(page);
	let puts = 0;
	page.on('request', (r) => {
		if (r.method() === 'PUT' && r.url().includes(`/api/trips/${TRIP_ID}`)) puts++;
	});

	await page.getByTestId('etappen-strip').getByTestId('drag-handle').first().focus();
	await page.keyboard.press('Space');
	await page.keyboard.press('ArrowRight');
	await page.waitForTimeout(500);
	expect(puts, 'vor dem Fokusverlust noch nichts gespeichert').toBe(0);
	await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
	await expect.poll(() => stored(page), { timeout: 10_000 }).toEqual(['s2', 's1', 's3', 's4']);
	expect(puts).toBe(1);
});
