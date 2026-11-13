// Issue #2961 (FE1) — Wegpunktnamen erscheinen in der Karten-Sprechblase als Text.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-1)
//
// Wegpunktnamen kommen aus Nutzereingaben und importierten GPX-Dateien. Die
// Karte (Leaflet) muss sie in der Sprechblase woertlich zeigen; eine im Namen
// enthaltene Auszeichnung darf kein Element erzeugen und kein Skript ausfuehren.
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/karte-wegpunktname-als-text.spec.ts

import { test, expect } from '@playwright/test';
import { createTestTrip } from './helpers';

const DESKTOP_MAP_CANVAS = '[data-testid="map-card"] [data-testid="map-canvas"]';
const NAME_MIT_AUSZEICHNUNG = '<img src="x" data-gz-probe="1" onerror="window.__gzProbe=1">Gipfel';

test('AC-1: ein Wegpunktname mit Auszeichnung erscheint in der Sprechblase als Text', async ({
	page
}) => {
	const heute = new Date().toISOString().slice(0, 10);
	const trip = await createTestTrip(page.request, {
		stages: [
			{
				id: `stage-${Date.now()}`,
				name: 'Etappe',
				date: heute,
				waypoints: [
					{ id: 'wp-1', name: 'Start', lat: 47.27, lon: 11.4, elevation_m: 600 },
					{ id: 'wp-2', name: NAME_MIT_AUSZEICHNUNG, lat: 47.28, lon: 11.42, elevation_m: 900 }
				]
			}
		]
	});

	await page.goto(`/trips/${trip.id}`);
	await page.getByTestId('trip-detail-tab-etappen').click();
	const karte = page.locator(DESKTOP_MAP_CANVAS);
	await expect(karte).toBeVisible({ timeout: 15_000 });
	const marker = karte.locator('.leaflet-marker-icon');
	await expect(marker).toHaveCount(2, { timeout: 15_000 });

	// Klick-Ereignis direkt am Marker: ein Maus-Klick per Playwright erreichte
	// Leaflets Marker-Handler in Chromium nicht (beobachtet 2026-11-12); fuer
	// die Zusicherung zaehlt der Inhalt der geoeffneten Sprechblase.
	await marker.nth(1).dispatchEvent('click');
	const blase = karte.locator('.leaflet-popup-content');
	await expect(blase).toBeVisible();
	await expect(blase).toHaveText(`2. ${NAME_MIT_AUSZEICHNUNG}`);

	expect(
		await blase.locator('img, [data-gz-probe]').count(),
		'die Auszeichnung im Namen wurde als Element eingesetzt'
	).toBe(0);
	expect(
		await page.evaluate(() => (window as unknown as { __gzProbe?: number }).__gzProbe),
		'ein Ereignis-Attribut aus dem Namen wurde ausgefuehrt'
	).toBeUndefined();
});

// Issue #2961 (F003): eigener Zweig in MapCanvas.svelte fuer eine Etappe mit
// GENAU EINEM Wegpunkt — auch dort erscheint der Name als Text.
test('AC-1: einziger Wegpunkt einer Etappe — Name mit Auszeichnung erscheint als Text', async ({ page }) => {
	const heute = new Date().toISOString().slice(0, 10);
	const trip = await createTestTrip(page.request, {
		stages: [
			{
				id: `stage-${Date.now()}`,
				name: 'Etappe',
				date: heute,
				waypoints: [{ id: 'wp-1', name: NAME_MIT_AUSZEICHNUNG, lat: 47.28, lon: 11.42, elevation_m: 900 }]
			}
		]
	});

	await page.goto(`/trips/${trip.id}`);
	await page.getByTestId('trip-detail-tab-etappen').click();
	const karte = page.locator(DESKTOP_MAP_CANVAS);
	await expect(karte).toBeVisible({ timeout: 15_000 });
	const marker = karte.locator('.leaflet-marker-icon');
	await expect(marker).toHaveCount(1, { timeout: 15_000 });

	await marker.first().dispatchEvent('click');
	const blase = karte.locator('.leaflet-popup-content');
	await expect(blase).toBeVisible();
	await expect(blase).toHaveText(`1. ${NAME_MIT_AUSZEICHNUNG}`);
	expect(
		await blase.locator('img, [data-gz-probe]').count(),
		'die Auszeichnung im Namen wurde als Element eingesetzt'
	).toBe(0);
	expect(
		await page.evaluate(() => (window as unknown as { __gzProbe?: number }).__gzProbe),
		'ein Ereignis-Attribut aus dem Namen wurde ausgefuehrt'
	).toBeUndefined();
});
