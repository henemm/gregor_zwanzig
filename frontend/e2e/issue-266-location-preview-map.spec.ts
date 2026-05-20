// E2E — Issue #266: LocationPreviewMap im NewLocationWizard Schritt 1.
//
// Spec: docs/specs/modules/issue_266_location_preview_map.md (AC-1 bis AC-6)
//
// TestID-Inventar (nach Implementierung in LocationPreviewMap.svelte + NewLocationWizard.svelte):
//   location-wizard-map-preview  — Wrapper-div der Kartenvorschau (coordsValid === true)
//
// Ausführen:
//   cd frontend && npx playwright test e2e/issue-266-location-preview-map.spec.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Compare: LocationPreviewMap im NewLocationWizard (#266)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/compare');
		// Wizard öffnen
		await page.getByTestId('compare-rail-new-btn').click();
		await expect(page.getByTestId('location-wizard')).toBeVisible();
	});

	// AC-2: Map erscheint bei Default-Koordinaten (47.0/11.0 — valide, nicht 0/0).
	test('AC-2: Kartenvorschau sichtbar bei Default-Koordinaten (47.0/11.0)', async ({ page }) => {
		const mapPreview = page.getByTestId('location-wizard-map-preview');
		await expect(mapPreview).toBeVisible();
	});

	// AC-1: Komponente rendert korrekten Container und SVG.
	test('AC-1: Kartenvorschau enthält SVG mit role=img und Koordinatentext', async ({ page }) => {
		const mapPreview = page.getByTestId('location-wizard-map-preview');
		await expect(mapPreview).toBeVisible();

		// SVG mit role="img" vorhanden
		const svg = mapPreview.locator('svg[role="img"]');
		await expect(svg).toBeVisible();

		// Koordinatentext mit Default-Werten vorhanden
		const coordText = mapPreview.locator('p');
		await expect(coordText).toBeVisible();
		const text = await coordText.textContent();
		expect(text?.trim()).toMatch(/47\.\d{4},\s*11\.\d{4}/);
	});

	// AC-3: Map verschwindet wenn lat=0 UND lon=0.
	test('AC-3: Kartenvorschau verschwindet wenn lat=0 und lon=0', async ({ page }) => {
		// Erst sicherstellen, dass Preview sichtbar ist
		await expect(page.getByTestId('location-wizard-map-preview')).toBeVisible();

		// Lat und Lon auf 0 setzen
		const latInput = page.getByTestId('location-wizard-lat');
		const lonInput = page.getByTestId('location-wizard-lon');
		await latInput.fill('0');
		await lonInput.fill('0');
		await lonInput.dispatchEvent('input');

		// Map-Preview muss verschwinden
		await expect(page.getByTestId('location-wizard-map-preview')).not.toBeVisible();
	});

	// AC-4: Koordinatentext zeigt 4 Dezimalstellen.
	test('AC-4: Koordinatentext zeigt genau 4 Dezimalstellen', async ({ page }) => {
		const latInput = page.getByTestId('location-wizard-lat');
		const lonInput = page.getByTestId('location-wizard-lon');

		await latInput.fill('46.8523');
		await lonInput.fill('10.7673');
		await lonInput.dispatchEvent('input');

		const mapPreview = page.getByTestId('location-wizard-map-preview');
		await expect(mapPreview).toBeVisible();

		const coordText = mapPreview.locator('p');
		const text = await coordText.textContent();
		// Muss exakt "46.8523, 10.7673" enthalten (4 Nachkommastellen)
		expect(text?.trim()).toMatch(/46\.8523,\s*10\.7673/);
	});

	// AC-6: Koordinatentext aktualisiert sich reaktiv bei Koordinatenänderung.
	test('AC-6: Koordinatentext aktualisiert sich bei manueller Koordinatenänderung', async ({
		page
	}) => {
		const latInput = page.getByTestId('location-wizard-lat');
		const lonInput = page.getByTestId('location-wizard-lon');
		const mapPreview = page.getByTestId('location-wizard-map-preview');

		// Erste Koordinaten setzen
		await latInput.fill('47.1111');
		await lonInput.fill('11.2222');
		await lonInput.dispatchEvent('input');
		await expect(mapPreview).toBeVisible();

		const coordText = mapPreview.locator('p');
		const text1 = await coordText.textContent();
		expect(text1?.trim()).toMatch(/47\.1111,\s*11\.2222/);

		// Koordinaten ändern
		await latInput.fill('48.3333');
		await lonInput.fill('14.4444');
		await lonInput.dispatchEvent('input');

		const text2 = await coordText.textContent();
		expect(text2?.trim()).toMatch(/48\.3333,\s*14\.4444/);
	});

	// AC-5: Map erscheint nach Smart-Import (resolve-Preview).
	test('AC-5: Kartenvorschau erscheint nach Smart-Import-Auflösung', async ({ page }) => {
		// Smart-Import mit einer gültigen Koordinaten-Eingabe simulieren
		const resolveInput = page.getByTestId('location-wizard-resolve-input');
		const resolveBtn = page.getByTestId('location-wizard-resolve-btn');

		await resolveInput.fill('47.0804, 12.7031');
		await resolveBtn.click();

		// Nach erfolgreicher Auflösung muss die Map-Preview erscheinen
		const mapPreview = page.getByTestId('location-wizard-map-preview');
		await expect(mapPreview).toBeVisible({ timeout: 10_000 });

		// Koordinaten aus der Auflösung müssen im Text erscheinen
		const coordText = mapPreview.locator('p');
		const text = await coordText.textContent();
		expect(text?.trim()).toMatch(/\d+\.\d{4},\s*\d+\.\d{4}/);
	});
});
