// TDD RED — E2E (Live-Schicht), Issue #2278 (Epic #2345 P3), AC-1 (+ AC-11 Archiv-Ausblendung der Trip-Liste).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md
//
// Desktop-Trip-Liste: das Zeilenmenue beginnt mit "Pausieren" — in derselben Beschriftung und
// Reihenfolge wie beim Ortsvergleich — und die Wahl pausiert den Trip wirklich (Status "pausiert",
// Zustand im Backend). Danach steht dort "Fortsetzen" (setzt fort). Archivierte Trips erscheinen
// nicht in der Liste.
//
// Verdrahtungsvertrag (hier festgelegt): Zeilenmenue = bestehendes `trip-row-menu-btn` (ListTable),
// Zeile `trip-row-{id}`; Menueeintraege role=menuitem mit den Labels aus subscriptionActions.
//
// RED heute: das Trip-Zeilenmenue beginnt mit "Briefing jetzt senden", "Pausieren" fehlt ganz.
//
// Ausfuehren (aus frontend/, lokaler E2E-Stack, siehe e2e/ci-stack.sh):
//   npx playwright test e2e/trips-list-aktionen.spec.ts
// Dieser Spec steht NICHT in ci_e2e_specs.txt; er laeuft in /50-implement und in /e2e-verify.

import { test, expect, type Page } from '@playwright/test';
import { login, createTestTrip, createTestComparePreset, createTestLocation, cleanupTracked } from './helpers.js';

test.use({ viewport: { width: 1280, height: 900 } });

const HEUTE = new Date().toISOString().slice(0, 10);
const neueId = () => `e2e-gz-trip-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
const ETAPPE = (id: string) => ({
	id: `${id}-s1`,
	name: 'Etappe 1',
	date: HEUTE,
	waypoints: [{ id: `${id}-w1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
});

async function tripMenue(page: Page, tripId: string) {
	await page.goto('/trips');
	const zeile = page.getByTestId(`trip-row-${tripId}`);
	await expect(zeile).toBeVisible();
	await zeile.getByTestId('trip-row-menu-btn').click();
	return page.getByRole('menu');
}

test.describe('AC-1: Trip-Liste Desktop — Pausieren im Zeilenmenue', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});
	test.afterEach(async ({ page }) => {
		await cleanupTracked(page.request);
	});

	test('erster Menuepunkt ist "Pausieren"; Wahl pausiert den Trip; danach "Fortsetzen"', async ({ page }) => {
		const id = neueId();
		const trip = await createTestTrip(page.request, { id, stages: [ETAPPE(id)] });

		const menue = await tripMenue(page, trip.id);
		const eintraege = menue.getByRole('menuitem');
		await expect(eintraege.first()).toHaveText('Pausieren');

		const patch = page.waitForRequest(
			(r) => r.method() === 'PATCH' && r.url().endsWith(`/api/trips/${trip.id}/state`)
		);
		await eintraege.first().click();
		expect((await patch).postDataJSON()).toEqual({ paused: true });

		await expect(page.getByTestId(`trip-row-${trip.id}`)).toContainText(/pausiert/i);
		const serverStand = await (await page.request.get(`/api/trips/${trip.id}`)).json();
		expect(serverStand.paused_at, 'Backend-Zustand: paused_at gesetzt').toBeTruthy();
		expect(serverStand.stages, 'Pausieren darf Etappen nicht veraendern').toHaveLength(1);

		const menue2 = await tripMenue(page, trip.id);
		await expect(menue2.getByRole('menuitem').first()).toHaveText('Fortsetzen');
	});

	test('Reihenfolge und Beschriftung des Trip-Menues == Ortsvergleich-Menue', async ({ page }) => {
		const id = neueId();
		const trip = await createTestTrip(page.request, { id, stages: [ETAPPE(id)] });
		const ort = await createTestLocation(page.request, { name: 'Menue-Paritaet', lat: 42.1, lon: 9.0 });
		const preset = await createTestComparePreset(page.request, { locationIds: [ort.id] });

		const tripMenue_ = await tripMenue(page, trip.id);
		const tripLabels = await tripMenue_.getByRole('menuitem').allTextContents();

		await page.goto('/compare');
		await page.getByTestId(`compare-tile-${preset.id}`).getByTestId('compare-row-kebab').click();
		const compareLabels = await page.getByRole('menu').getByRole('menuitem').allTextContents();

		expect(tripLabels.map((t) => t.trim())).toEqual(compareLabels.map((t) => t.trim()));
		expect(tripLabels[0].trim()).toBe('Pausieren');
	});

	test('AC-11: ein archivierter Trip erscheint nicht in der Trip-Liste', async ({ page }) => {
		const id = neueId();
		const trip = await createTestTrip(page.request, { id, stages: [ETAPPE(id)] });
		await page.goto('/trips');
		await expect(page.getByTestId(`trip-row-${trip.id}`)).toBeVisible();

		const res = await page.request.patch(`/api/trips/${trip.id}/state`, { data: { archived: true } });
		expect(res.ok()).toBeTruthy();
		await page.goto('/trips');
		await expect(page.getByTestId(`trip-row-${trip.id}`)).toHaveCount(0);
		// Auffindbar bleibt er auf der Archiv-Seite.
		await page.goto('/archiv');
		await expect(page.getByText(trip.name)).toBeVisible();
	});
});
