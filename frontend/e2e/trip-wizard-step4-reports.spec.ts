// TDD RED — Issue #300 Step 4 Reports: 4 Cards (Abend/Morgen/Warnungen/Trend)
//
// Spec: docs/specs/modules/issue_300_wizard_redesign.md (AC-8, AC-9)
//
// ALLE TESTS MÜSSEN FEHLSCHLAGEN:
//   - Step4Reports.svelte existiert noch nicht
//   - data-testid="step4-reports" existiert nicht
//   - data-testid="card-evening", "card-morning", "card-alerts", "card-trend" existieren nicht
//
// Nach Implementierung werden diese Tests grün.

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

/**
 * Navigiert zu Schritt 4 (Reports).
 * Schritt 1: Name + Startdatum (neues Format — kein Activity-Chip).
 */
async function gotoStep4Reports(page: Page): Promise<void> {
	await page.goto('/trips/new');
	// Schritt 1: Route
	await page.getByTestId('trip-wizard-step1-name').fill('Step4-Reports-Test');
	await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
	// Schritt 1 → Schritt 2 → Schritt 3 → Schritt 4
	await page.getByTestId('trip-wizard-next').click();
	await page.getByTestId('trip-wizard-next').click();
	await page.getByTestId('trip-wizard-next').click();
	// Schritt 4 (Reports) muss sichtbar sein
	await expect(page.getByTestId('step4-reports')).toBeVisible();
}

test.describe('Trip-Wizard Schritt 4 — Reports 4-Cards (Issue #300)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-8: step4-reports Container ist sichtbar (statt altem step4-container)', async ({
		page
	}) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-step1-name').fill('Reports-Test');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('step4-reports')).toBeVisible();
	});

	test('AC-8: Vier Report-Cards vorhanden (card-evening, card-morning, card-alerts, card-trend)', async ({
		page
	}) => {
		await gotoStep4Reports(page);
		await expect(page.getByTestId('card-evening')).toBeVisible();
		await expect(page.getByTestId('card-morning')).toBeVisible();
		await expect(page.getByTestId('card-alerts')).toBeVisible();
		await expect(page.getByTestId('card-trend')).toBeVisible();
	});

	test('AC-8: Trend-Vorschau-Card hat CSS-Klasse disabled und Badge "Demnächst"', async ({
		page
	}) => {
		await gotoStep4Reports(page);
		const trendCard = page.getByTestId('card-trend');
		await expect(trendCard).toBeVisible();
		// Card muss disabled-Klasse haben
		await expect(trendCard).toHaveClass(/disabled/);
		// Badge-Text "Demnächst" muss sichtbar sein
		await expect(trendCard).toContainText('Demnächst');
	});

	test('AC-8: Abend-Briefing-Card hat Checkbox und Uhrzeit-Feld', async ({ page }) => {
		await gotoStep4Reports(page);
		const eveningCard = page.getByTestId('card-evening');
		await expect(eveningCard).toBeVisible();
		// Checkbox aktiv/inaktiv
		await expect(eveningCard.locator('input[type="checkbox"]')).toBeVisible();
		// Uhrzeit-Feld
		await expect(page.getByTestId('evening-time')).toBeVisible();
	});

	test('AC-9: Abend-Briefing Uhrzeit ändern → Input zeigt neuen Wert', async ({ page }) => {
		await gotoStep4Reports(page);
		const timeInput = page.getByTestId('evening-time');
		await timeInput.fill('20:00');
		await expect(timeInput).toHaveValue('20:00');
	});

	test('AC-8: Morgen-Update-Card hat Checkbox und Uhrzeit-Feld', async ({ page }) => {
		await gotoStep4Reports(page);
		const morningCard = page.getByTestId('card-morning');
		await expect(morningCard).toBeVisible();
		await expect(morningCard.locator('input[type="checkbox"]')).toBeVisible();
		await expect(page.getByTestId('morning-time')).toBeVisible();
	});

	test('AC-8: Warnungen-Card zeigt AUTARK-Badge', async ({ page }) => {
		await gotoStep4Reports(page);
		const alertsCard = page.getByTestId('card-alerts');
		await expect(alertsCard).toBeVisible();
		await expect(alertsCard).toContainText('AUTARK');
	});

	test('AC-1: Step-Labels in Stepper sind Route, Etappen, Wetter, Reports', async ({
		page
	}) => {
		await page.goto('/trips/new');
		// Stepper muss auf Schritt 1 zeigen
		await expect(page.getByTestId('trip-wizard-shell')).toBeVisible();
		// Alle vier Labels müssen sichtbar sein
		await expect(page.getByText('Route')).toBeVisible();
		await expect(page.getByText('Etappen')).toBeVisible();
		await expect(page.getByText('Wetter')).toBeVisible();
		await expect(page.getByText('Reports')).toBeVisible();
		// NICHT die alten Labels
		await expect(page.getByText('Profil & Eckdaten')).not.toBeVisible();
		await expect(page.getByText('GPX-Import')).not.toBeVisible();
		await expect(page.getByText('Wegpunkte')).not.toBeVisible();
		await expect(page.getByText('Briefings')).not.toBeVisible();
	});

	test('AC-2: Schritt 1 ohne Activity-Chip — Weiter-Button nach Name+Datum aktiv', async ({
		page
	}) => {
		await page.goto('/trips/new');
		// Weiter-Button initial deaktiviert (kein Name)
		await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
		// Name + Startdatum → Weiter aktiv (ohne Activity-Chip!)
		await page.getByTestId('trip-wizard-step1-name').fill('Test-Tour');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
		// Activity-Chip-Elemente dürfen NICHT mehr vorhanden sein
		await expect(page.locator('[data-testid^="trip-wizard-step1-chip-"]')).toHaveCount(0);
	});
});
