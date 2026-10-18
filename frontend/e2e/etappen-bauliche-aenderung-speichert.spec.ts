// TDD RED — Issue #2213: bauliche Aenderungen im Etappen-Tab werden im Auto-Save-Modus
// sofort gespeichert (Spec docs/specs/modules/etappen_bauliche_aenderung_speichern.md).
// Gemessen wird der SERVER-STAND nach der Handlung — ohne Speichern-Knopf und ohne
// Seitenwechsel (ein Seitenwechsel wuerde den vorgemerkten Stand per Flush retten
// und den Befund verdecken). Vorlage: mobile-etappen-sortieren-speichert.spec.ts.

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-2213-bauliche';
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 + lat * 10 });
const stages = Array.from({ length: 3 }, (_, i) => ({
	id: `s${i + 1}`,
	name: `Tag ${i + 1}`,
	date: `2026-08-${String(i + 1).padStart(2, '0')}`,
	waypoints: [wp(`a${i}`, 42 + i * 0.1), wp(`b${i}`, 42.04 + i * 0.1)]
}));

async function serverEtappen(page: Page): Promise<Array<{ id: string; name: string; date: string }>> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()).stages;
}

async function oeffnen(page: Page, mobil = false): Promise<void> {
	if (mobil) await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
}

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: { id: TRIP_ID, name: 'E2E #2213 bauliche Aenderung', region: 'Korsika', stages }
	});
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});
test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

test('AC-1: Desktop „+ Etappe" speichert sofort, nach Neuladen vorhanden', async ({ page }) => {
	await oeffnen(page);
	await page.locator('.add-stage-btn').click();
	await expect.poll(async () => (await serverEtappen(page)).length, { timeout: 10_000 }).toBe(4);
	await page.reload();
	await expect(page.getByTestId('stage-card-3')).toBeVisible();
});

test('AC-1: Desktop Etappe loeschen (Dialog) speichert sofort, nach Neuladen weg', async ({ page }) => {
	await oeffnen(page);
	await page.getByTestId('stage-card-1').getByRole('button', { name: 'Etappe entfernen' }).click();
	await page.getByTestId('confirm-delete-stage').click();
	await expect
		.poll(async () => (await serverEtappen(page)).map((s) => s.id), { timeout: 10_000 })
		.toEqual(['s1', 's3']);
	await page.reload();
	await expect(page.getByTestId('stage-card-2')).toHaveCount(0);
});

test('AC-2: mobil „+ Etappe" → Etappe speichert sofort, nach Neuladen vorhanden', async ({ page }) => {
	await oeffnen(page, true);
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);
	await page.getByTestId('mobile-add-stage').click();
	await page.getByTestId('mobile-add-choice').getByRole('menuitem', { name: 'Etappe' }).click();
	await expect.poll(async () => (await serverEtappen(page)).length, { timeout: 10_000 }).toBe(4);
	await page.reload();
	await expect(page.getByTestId('stage-cardm')).toHaveCount(4);
});

test('AC-8: Datum der letzten Etappe aendern, sofort andere Etappe loeschen ⇒ gespeichert ohne Seitenwechsel', async ({ page }) => {
	await oeffnen(page);
	await page.getByTestId('stage-card-2').click();
	await page.getByTestId('stage-date-field').first().locator('input[type="date"]').fill('2026-08-20');
	await page.getByTestId('stage-card-0').getByRole('button', { name: 'Etappe entfernen' }).click();
	await page.getByTestId('confirm-delete-stage').click();
	await expect
		.poll(async () => (await serverEtappen(page)).map((s) => `${s.id}:${s.date}`), { timeout: 10_000 })
		.toEqual(['s2:2026-08-02', 's3:2026-08-20']);
});

test('AC-9: waehrend die Kaskade geschrieben wird, sind Hoehenprofil und Wegpunkt-Aktionen sichtbar gesperrt', async ({ page }) => {
	await oeffnen(page);
	await page.getByTestId('stage-card-0').click();
	await page.getByTestId('waypoint-card-0').click();
	await expect(page.getByTestId('waypoint-delete-0')).toBeVisible();

	// Kaskaden-PUT zurueckhalten, damit das Fenster `cascadeBusy` messbar offen bleibt.
	let freigeben: () => void = () => {};
	const gehalten = new Promise<void>((r) => { freigeben = r; });
	await page.route(`**/api/trips/${TRIP_ID}`, async (route) => {
		if (route.request().method() === 'PUT') await gehalten;
		await route.continue();
	});

	await page.getByTestId('stage-date-field').first().locator('input[type="date"]').fill('2026-08-05');
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByTestId('cascade-strip').getByRole('button', { name: 'Lückenlos anschließen' }).click();
	await expect(page.getByTestId('cascade-strip').getByRole('button', { name: 'Wird angepasst …' })).toBeVisible();

	const gesperrt = (testId: string) =>
		page.getByTestId(testId).evaluate((el) =>
			el.getAttribute('aria-disabled') === 'true' ||
			el.getAttribute('aria-busy') === 'true' ||
			(el as HTMLButtonElement).disabled === true ||
			el.closest('[aria-busy="true"]') !== null
		);
	expect(await gesperrt('profile-add-area'), 'Hoehenprofil sichtbar gesperrt').toBe(true);
	const keineZeigerEreignisse = (testId: string) =>
		page.getByTestId(testId).evaluate((el) => {
			const gesperrterContainer = el.closest('[aria-busy="true"]') ?? el;
			return getComputedStyle(gesperrterContainer).pointerEvents === 'none';
		});
	expect(await keineZeigerEreignisse('profile-add-area'), 'Hoehenprofil: pointer-events none').toBe(true);
	expect(await keineZeigerEreignisse('waypoint-delete-0'), 'Wegpunkt loeschen: pointer-events none').toBe(true);
	expect(await gesperrt('waypoint-delete-0'), 'Wegpunkt loeschen gesperrt').toBe(true);
	expect(await gesperrt('waypoint-rename-0'), 'Wegpunkt umbenennen gesperrt').toBe(true);

	freigeben();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 10_000 });
	expect(await gesperrt('profile-add-area'), 'nach der Kaskade wieder bedienbar').toBe(false);
	expect(await gesperrt('waypoint-delete-0')).toBe(false);
});
