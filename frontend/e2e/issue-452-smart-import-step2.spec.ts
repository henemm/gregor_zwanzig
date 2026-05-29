// E2E — Issue #452: Smart-Import Vervollständigung — Step2Orte Preview + Fallback-Felder.
//
// Spec: docs/specs/modules/issue_452_smart_import_step2.md (AC-1 bis AC-5)
//
// TestID-Inventar (zu implementieren in Step2Orte.svelte):
//   compare-step2-smart-import-input  — Texteingabe für URL/Koordinaten (vorhanden)
//   compare-step2-resolve-btn         — "Auflösen"-Button (vorhanden)
//   compare-step2-library             — Liste gespeicherter Orte (vorhanden)
//   compare-step2-counter             — Auswahl-Counter (vorhanden)
//   compare-step2-fallback-lat        — NEU: Breitengrad-Fallback-Input bei Fehler
//   compare-step2-fallback-lon        — NEU: Längengrad-Fallback-Input bei Fehler
//   compare-step2-fallback-add-btn    — NEU: "Hinzufügen"-Button für manuellen Fallback

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Smart-Import Step2Orte: Preview + Fallback-Felder (#452)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/compare');
		// Compare-Wizard öffnen (Step 1 → Step 2)
		const newCompareBtn = page.getByTestId('compare-wizard-open-btn');
		await expect(newCompareBtn).toBeVisible({ timeout: 10000 });
		await newCompareBtn.click();
		// Zu Step 2 navigieren
		const step2 = page.getByTestId('compare-wizard-step-2');
		await expect(step2).toBeVisible({ timeout: 10000 });
	});

	// AC-3: Dezimalkoordinaten auflösen → Vorschau zeigt Zeitzone (AC-5).
	// Dieser Test schlägt fehl weil Step2Orte die Zeitzone noch nicht anzeigt.
	test('AC-3+AC-5: Dezimalkoordinaten auflösen → Vorschau zeigt Zeitzone', async ({ page }) => {
		const importInput = page.getByTestId('compare-step2-smart-import-input');
		const resolveBtn = page.getByTestId('compare-step2-resolve-btn');

		await importInput.fill('47.2692, 11.4041');
		await resolveBtn.click();

		// Vorschau muss Zeitzone anzeigen — FEHLT aktuell in Step2Orte.svelte
		const step2 = page.getByTestId('compare-wizard-step-2');
		await expect(step2).toContainText('Europe/', { timeout: 15000 });
	});

	// AC-5: Vorschau zeigt Höhe wenn vorhanden.
	// Dieser Test schlägt fehl weil Step2Orte elevation_m noch nicht anzeigt.
	test('AC-5: Dezimalkoordinaten auflösen → Vorschau zeigt Höhe wenn vorhanden', async ({
		page
	}) => {
		const importInput = page.getByTestId('compare-step2-smart-import-input');
		const resolveBtn = page.getByTestId('compare-step2-resolve-btn');

		// Innsbruck — bekannte Koordinaten mit Höhe via Open-Elevation
		await importInput.fill('47.2692, 11.4041');
		await resolveBtn.click();

		// Wenn elevation_m vorhanden → "Höhe: X m" sichtbar
		// Dieser Test prüft das Vorhandensein des Höhe-Labels im Preview-Block
		const step2 = page.getByTestId('compare-wizard-step-2');
		// Erst warten bis Resolve-Ergebnis erscheint (name oder koordinaten)
		await expect(step2).toContainText('47.2692', { timeout: 15000 });
		// Dann Höhe prüfen — FEHLT aktuell
		await expect(step2).toContainText('Höhe:', { timeout: 5000 });
	});

	// AC-4: Unbekanntes Format → Fallback-Felder erscheinen.
	// Dieser Test schlägt fehl weil compare-step2-fallback-lat noch nicht existiert.
	test('AC-4: Unbekanntes Format → Fallback-Felder für lat/lon erscheinen', async ({ page }) => {
		const importInput = page.getByTestId('compare-step2-smart-import-input');
		const resolveBtn = page.getByTestId('compare-step2-resolve-btn');

		// Eingabe die kein Format trifft
		await importInput.fill('Gasthof Zum Löwen Mayrhofen');
		await resolveBtn.click();

		// Fallback-Felder müssen erscheinen — FEHLEN aktuell in Step2Orte.svelte
		const fallbackLat = page.getByTestId('compare-step2-fallback-lat');
		const fallbackLon = page.getByTestId('compare-step2-fallback-lon');
		const fallbackAddBtn = page.getByTestId('compare-step2-fallback-add-btn');

		await expect(fallbackLat).toBeVisible({ timeout: 10000 });
		await expect(fallbackLon).toBeVisible({ timeout: 10000 });
		await expect(fallbackAddBtn).toBeVisible({ timeout: 10000 });
	});

	// AC-4: Manuelles Hinzufügen via Fallback-Felder.
	// Dieser Test schlägt fehl weil die Fallback-Felder noch nicht existieren.
	test('AC-4: Fallback-Felder → manuelles Hinzufügen fügt Ort zur Auswahl hinzu', async ({
		page
	}) => {
		const importInput = page.getByTestId('compare-step2-smart-import-input');
		const resolveBtn = page.getByTestId('compare-step2-resolve-btn');

		// Fehler auslösen
		await importInput.fill('kein_gueltiges_format_xyz');
		await resolveBtn.click();

		// Fallback-Felder befüllen
		const fallbackLat = page.getByTestId('compare-step2-fallback-lat');
		const fallbackLon = page.getByTestId('compare-step2-fallback-lon');
		const fallbackAddBtn = page.getByTestId('compare-step2-fallback-add-btn');

		await expect(fallbackLat).toBeVisible({ timeout: 10000 });
		await fallbackLat.fill('47.5162');
		await fallbackLon.fill('11.9749');
		await fallbackAddBtn.click();

		// Counter muss nach Hinzufügen gestiegen sein (min. 1 Ort ausgewählt)
		const counter = page.getByTestId('compare-step2-counter');
		await expect(counter).toContainText('1', { timeout: 10000 });

		// Fallback-Felder werden zurückgesetzt
		await expect(fallbackLat).toHaveValue('');
	});
});
