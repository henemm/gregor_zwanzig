// Issue #951 — ProfileSheetEmbedded blockiert BottomNav-Klicks (Mobil).
// Spec: docs/specs/modules/issue_951_profile_sheet_pointer.md (AC-1..AC-4).
// Charakterisierungs-/Regressionstests gegen den LIVE-Code (kein Mock).
// Ausführen: cd frontend && npx playwright test e2e/issue-951-sheet-bottomnav.spec.ts --reporter=list

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-951-sheet-bottomnav';
const TRIP_NAME = 'E2E #951 Sheet BottomNav';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] }
	],
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00'
	}
};

async function openMobileStagesEditor(page: Page) {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('mobile-editor')).toBeVisible();
}

test.describe('Issue #951 — Sheet-Panel darf BottomNav nicht blockieren', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});

	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	// AC-1: Echter Klick (kein elementFromPoint-Workaround) auf bottom-nav-item-compare
	// navigiert erfolgreich zu /compare.
	test('AC-1: echter Klick auf BottomNav-Item navigiert trotz Sheet zu /compare', async ({
		page
	}) => {
		await openMobileStagesEditor(page);

		const compareItem = page.getByTestId('bottom-nav-item-compare');
		await expect(compareItem).toBeVisible();
		await compareItem.click({ timeout: 5000 });

		await expect(page).toHaveURL(/\/compare/);
	});

	// AC-2: Auch im kleinsten Snap-Zustand (peek) bleibt die BottomNav klickbar.
	test('AC-2: peek-Snap-Zustand — Klick auf anderes Nav-Item navigiert zu /trips', async ({
		page
	}) => {
		await openMobileStagesEditor(page);

		// Default-Snap ist 'half'; Zyklus half -> full -> peek (2 Klicks).
		const snapCycle = page.getByTestId('snap-cycle');
		await snapCycle.click();
		await snapCycle.click();
		await expect(snapCycle).toContainText('peek');

		const tripsItem = page.getByTestId('bottom-nav-item-trips');
		await expect(tripsItem).toBeVisible();
		await tripsItem.click({ timeout: 5000 });

		await expect(page).toHaveURL(/\/trips/);
	});

	// AC-3: Bestehende Modal-Nutzung (Compare-Editor Bibliotheks-Sheet) bleibt
	// unverändert — Backdrop sichtbar, Klick auf Backdrop schließt das Sheet.
	test('AC-3: Compare-Editor Bibliotheks-Sheet — Backdrop weiterhin sichtbar, schließt bei Klick', async ({
		page
	}) => {
		const resLoc = await page.request.post('/api/locations', {
			data: { name: 'Ort-951', lat: 47.4, lon: 13.0, region: 'Hochkönig' }
		});
		expect(resLoc.ok(), `loc HTTP ${resLoc.status()}`).toBeTruthy();
		const loc = await resLoc.json();

		const resPreset = await page.request.post('/api/compare/presets', {
			data: {
				name: 'Vergleich #951 ' + Date.now(),
				location_ids: [loc.id],
				schedule: 'daily',
				profil: 'wintersport',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['e2e-951@example.com'],
				display_config: {}
			}
		});
		expect(resPreset.ok(), `preset HTTP ${resPreset.status()}`).toBeTruthy();
		const presetId = (await resPreset.json()).id;

		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto(`/compare/${presetId}/edit`);
		await expect(page.getByTestId('compare-editor')).toBeVisible();

		await page.getByTestId('cm-mobile-tab-orte').click();
		await page.getByTestId('compare-step2-mobile-library-btn').click();

		const backdrop = page.getByRole('presentation');
		await expect(backdrop).toBeVisible();

		await backdrop.click({ position: { x: 5, y: 5 } });
		await expect(backdrop).toHaveCount(0);

		await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	});

	// AC-4: ProfileSheetEmbedded zeigt weiterhin Profil + Wegpunktliste, aber
	// ohne Backdrop-Element im DOM.
	test('AC-4: ProfileSheetEmbedded zeigt Profil/Wegpunktliste ohne Backdrop im DOM', async ({
		page
	}) => {
		await openMobileStagesEditor(page);

		await expect(page.getByTestId('profile-row')).toBeVisible();
		await expect(page.getByTestId('waypoint-list')).toBeVisible();

		const host = page.getByTestId('profile-sheet-host');
		await expect(host.getByRole('presentation')).toHaveCount(0);
	});
});
