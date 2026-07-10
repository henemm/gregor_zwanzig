// TDD RED — Bug #1194: per Kartentipp angelegter Wegpunkt wird nicht gespeichert.
//
// Spec: docs/specs/fast/fix-1194-mapclick-autosave.md
//
// RED-Grund: handleMapClick() in EditStagesPanelNew.svelte legt den neuen
// Wegpunkt bisher nur im UI-State an (siehe #1158-Test, der das explizit als
// "separates Folge-Issue" markiert) — anders als alle anderen Mutations-Handler
// (handleStartTimeChange, handleStageDateChange, ...) ruft er nie scheduleSave()/
// save() auf. Ohne den Fix bleibt der dritte Wegpunkt im GET nach dem Kartentipp
// unsichtbar (Backend kennt weiterhin nur die zwei Seed-Wegpunkte). Nach dem Fix
// (eine Zeile am Ende von handleMapClick) beweist dieser Test die Persistenz per
// Backend-GET — nicht bloß UI-Sichtbarkeit.
//
// Ausführen: cd frontend && npx playwright test e2e/waypoint-mapclick-autosave.spec.ts

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-mapclick-autosave';
const TRIP_NAME = 'E2E #1194 Mapclick Autosave';
const MOBILE = { width: 390, height: 844 };

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
	await page.setViewportSize(MOBILE);
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('mobile-editor')).toBeVisible();
}

test.describe('Bug #1194 — Kartentipp-Wegpunkt wird persistiert', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});
	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('Kartentipp legt Wegpunkt an und speichert ihn ans Backend (Reload-fest)', async ({
		page
	}) => {
		await openMobileStagesEditor(page);

		const map = page.getByTestId('mobile-editor').getByTestId('map-canvas');
		const box = await map.boundingBox();
		if (!box) throw new Error('map-canvas nicht gefunden');

		const [saveResponse] = await Promise.all([
			page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${TRIP_ID}`) && r.request().method() === 'PUT'
			),
			map.click({ position: { x: box.width * 0.05, y: box.height * 0.5 } })
		]);
		expect(saveResponse.ok(), `Save HTTP ${saveResponse.status()}`).toBeTruthy();

		// Backend-Nachweis statt reiner UI-Sichtbarkeit: die Etappe muss jetzt
		// 3 Wegpunkte haben (Seed hatte 2).
		const getRes = await page.request.get(`/api/trips/${TRIP_ID}`);
		expect(getRes.ok(), `GET HTTP ${getRes.status()}`).toBeTruthy();
		const trip = await getRes.json();
		expect(trip.stages[0].waypoints.length, 'Wegpunkt fehlt im Backend nach Kartentipp').toBe(3);
	});
});
