// TDD RED — Issue #300 Step 3 Wetter: Aktivitätsprofil + Metriken-Tabelle
//
// Spec: docs/specs/modules/issue_300_wizard_redesign.md (AC-5, AC-6, AC-7)
//
// ALLE TESTS MÜSSEN FEHLSCHLAGEN:
//   - Step3Weather.svelte existiert noch nicht
//   - data-testid="step3-weather" existiert nicht
//   - data-testid="activity-dropdown" existiert nicht
//
// Nach Implementierung werden diese Tests grün.

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';
import * as path from 'node:path';

const FIXTURE_DIR = path.resolve('./e2e/fixtures');
const TEST_GPX = path.resolve(FIXTURE_DIR, 'test-trip.gpx');

/**
 * Navigiert zu Schritt 3 (Wetter).
 * Schritt 1: Name + Startdatum (kein Activity-Chip — neue Logik).
 * Schritt 2: GPX-Upload aus Schritt 1 hat bereits Etappen erzeugt.
 */
async function gotoStep3Wetter(page: Page): Promise<void> {
	await page.goto('/trips/new');

	// Schritt 1: Route — Name + Startdatum, kein Activity-Chip
	await page.getByTestId('trip-wizard-step1-name').fill('Step3-Wetter-Test');
	await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');

	// GPX-Drop in Schritt 1 (neue Position)
	const fileInput = page.locator('input[type="file"][accept=".gpx"]');
	await fileInput.setInputFiles(TEST_GPX);
	const commit = page.getByTestId('trip-wizard-step1-gpx-commit');
	await commit.waitFor({ state: 'visible' });
	await commit.click();

	// Weiter zu Schritt 2 (Etappen)
	await page.getByTestId('trip-wizard-next').click();
	await page.getByTestId('trip-wizard-next').click();

	// Schritt 3 (Wetter) muss sichtbar sein
	await expect(page.getByTestId('step3-weather')).toBeVisible();
}

test.describe('Trip-Wizard Schritt 3 — Wetter (Issue #300)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-5: Step3-Wetter-Container mit TestID step3-weather ist sichtbar', async ({ page }) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Wetter-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		// Schritt 3: step3-weather muss sichtbar sein (statt altem trip-wizard-step3-container)
		await expect(page.getByTestId('step3-weather')).toBeVisible();
	});

	test('AC-5: Aktivitätsprofil-Dropdown ist in Schritt 3 sichtbar', async ({ page }) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Wetter-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('activity-dropdown')).toBeVisible();
	});

	test('AC-6: Hint "Standard-Metriken werden verwendet" erscheint wenn activity null', async ({
		page
	}) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Wetter-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		// activity ist null → Hint-Text sichtbar
		await expect(page.getByTestId('activity-hint')).toBeVisible();
		await expect(page.getByTestId('activity-hint')).toContainText(
			'Standard-Metriken werden verwendet'
		);
	});

	test('AC-6: Weiter-Button ist in Schritt 3 aktiv auch ohne activity (kein Gate)', async ({
		page
	}) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Wetter-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		// Weiter-Button muss aktiv sein trotz fehlender activity
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	test('AC-7: Nach Auswahl von Aktivitätsprofil verschwindet der Hint-Text', async ({
		page
	}) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Wetter-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		// Dropdown auswählen
		await page.getByTestId('activity-dropdown').selectOption('ski_touring');
		// Hint-Text verschwindet
		await expect(page.getByTestId('activity-hint')).not.toBeVisible();
	});

	test('AC-5: Metriken-Tabelle zeigt Zeilen mit HorizonChips', async ({ page }) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Wetter-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		// Mindestens eine metric-row muss sichtbar sein
		const metricRows = page.locator('[data-testid^="metric-row-"]');
		await expect(metricRows.first()).toBeVisible();
		// Mindestens ein HorizonChip (data-slot="horizon-chip") muss sichtbar sein
		const horizonChip = page.locator('[data-slot="horizon-chip"]').first();
		await expect(horizonChip).toBeVisible();
	});
});
