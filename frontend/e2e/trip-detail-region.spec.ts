// TDD RED — Issue #202: Region-Feld am Trip (Hero + Wizard).
// Spec: docs/specs/modules/issue_202_region_feld.md
//
// AC-4: Hero zeigt trip-hero-region wenn trip.region gesetzt
// AC-5: trip-hero-region ist nicht im DOM wenn region fehlt
// AC-6: Wizard Step 1 hat optionales Region-Eingabefeld
// AC-8: Wizard speichert region beim Abschluss

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
const REGION_TRIP_ID = 'e2e-region-test';

test.describe('Issue #202 — Region-Feld: Hero + Wizard', () => {
	test.beforeAll(async ({ request }) => {
		// Seed: Trip MIT region für Hero-Tests (AC-4)
		await request.delete(`/api/trips/${REGION_TRIP_ID}`);
		const today = new Date().toISOString().slice(0, 10);
		await request.post('/api/trips', {
			data: {
				id: REGION_TRIP_ID,
				name: 'Region Test Trip',
				region: 'Korsika',
				stages: [{
					id: 'rg-s1',
					name: 'Tag 1',
					date: today,
					waypoints: [{ id: 'rg-w1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 200 }]
				}]
			}
		});
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${REGION_TRIP_ID}`);
	});

	// AC-4: Trip mit region → trip-hero-region sichtbar und korrekt
	test('AC-4: Hero zeigt Region wenn trip.region gesetzt', async ({ page }) => {
		await page.goto(`/trips/${REGION_TRIP_ID}`);
		const regionEl = page.getByTestId('trip-hero-region');
		await expect(regionEl).toBeVisible();
		await expect(regionEl).toHaveText('Korsika');
	});

	// AC-4b: Region steht unterhalb des Titels und oberhalb des Zeitraums
	test('AC-4b: Region ist zwischen Titel und Zeitraum positioniert', async ({ page }) => {
		await page.goto(`/trips/${REGION_TRIP_ID}`);
		const title = page.getByTestId('trip-hero-title');
		const region = page.getByTestId('trip-hero-region');

		// Beide müssen existieren
		await expect(title).toBeVisible();
		await expect(region).toBeVisible();

		// Region muss unterhalb des Titels liegen (höherer Y-Wert)
		const titleBox = await title.boundingBox();
		const regionBox = await region.boundingBox();
		if (!titleBox || !regionBox) throw new Error('Bounding box fehlt');
		expect(regionBox.y).toBeGreaterThan(titleBox.y);
	});

	// AC-5: Trip ohne region → trip-hero-region nicht im DOM
	test('AC-5: Hero zeigt kein Region-Element wenn trip.region fehlt', async ({ page }) => {
		// TRIP_ID (e2e-cockpit-test) hat kein region-Feld gesetzt
		await page.goto(`/trips/${TRIP_ID}`);
		const regionEl = page.getByTestId('trip-hero-region');
		await expect(regionEl).not.toBeVisible();
	});

	// AC-6: Wizard Step 1 hat optionales Region-Eingabefeld
	test('AC-6: Wizard Step 1 hat Region-Input mit (optional)-Label', async ({ page }) => {
		await page.goto('/trips/new');
		// Wizard-Step-1 sollte sofort sichtbar sein
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();

		const regionInput = page.getByTestId('trip-wizard-step1-region');
		await expect(regionInput).toBeVisible();

		// Label muss "(optional)" enthalten
		const label = page.locator('label:has([data-testid="trip-wizard-step1-region"])');
		await expect(label).toContainText('optional');
	});

	// AC-6b: Wizard kann ohne region-Eingabe fortgesetzt werden (nicht Pflichtfeld)
	test('AC-6b: Wizard-Weiter-Button bleibt aktiv ohne region', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();

		// Name + Startdatum eingeben, region leer lassen
		await page.getByTestId('trip-wizard-step1-name').fill('Test ohne Region');
		const dateInput = page.getByTestId('trip-wizard-step1-startdate');
		await dateInput.fill('2026-08-01');

		// Weiter-Button muss aktiv sein
		const nextBtn = page.getByTestId('wizard-next-btn');
		await expect(nextBtn).not.toBeDisabled();
	});

	// AC-8: Wizard speichert region beim Abschluss
	test('AC-8: Wizard sendet region beim Speichern', async ({ page, request }) => {
		const newTripId = 'e2e-wizard-region-save-test';
		await request.delete(`/api/trips/${newTripId}`);

		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();

		// Aktivitätsprofil wählen
		await page.getByTestId('trip-wizard-step1-chip-trekking').click();
		// Name
		await page.getByTestId('trip-wizard-step1-name').fill('Mallorca Tour');
		// Region setzen
		await page.getByTestId('trip-wizard-step1-region').fill('Mallorca');
		// Startdatum
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-09-01');

		// Wizard durchklicken (Steps 2-4 überspringen via Next)
		const nextBtn = page.getByTestId('wizard-next-btn');
		await nextBtn.click(); // → Step 2
		await nextBtn.click(); // → Step 3
		await nextBtn.click(); // → Step 4
		// Speichern
		await page.getByTestId('wizard-save-btn').click();

		// Kurz warten bis Redirect
		await page.waitForURL(/\/trips\//, { timeout: 5000 });

		// URL enthält Trip-ID → API abfragen
		const url = page.url();
		const match = url.match(/\/trips\/([^/#?]+)/);
		if (!match) throw new Error('Keine Trip-ID in URL: ' + url);
		const createdId = match[1];

		const tripRes = await request.get(`/api/trips/${createdId}`);
		const trip = await tripRes.json();

		expect(trip.region).toBe('Mallorca');

		// Cleanup
		await request.delete(`/api/trips/${createdId}`);
	});
});
