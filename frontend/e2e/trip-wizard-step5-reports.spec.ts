// E2E — Issue #432 Step 5 Reports: 3 Cards (Abend/Morgen/Warnungen) + Trend-Toggle + Kanal-Chips
//
// Spec: docs/specs/modules/issue_432_step3_step5_polish.md (AC-12, AC-13, AC-15, AC-18)
//
// Erwartet:
//   - data-testid="step5-reports" (Reports-Step nach dem #432-Umbau)
//   - data-testid="card-evening", "card-morning", "card-alerts" (drei Cards, vierte Vorschau-Card entfällt)
//   - Mehrtages-Trend ist Toggle in Abend-Card: [data-testid="evening-trend-toggle"], Default checked=true
//   - Pro Card eine Kanal-Chip-Reihe: channel-chips-{evening|morning|alerts}

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

/**
 * Navigiert zu Schritt 5 (Reports).
 * Wizard-Schritte: Route → Etappen → Wetter → Layout → Reports (5 Schritte, 4× Weiter).
 */
async function gotoStep5Reports(page: Page): Promise<void> {
	await page.goto('/trips/new');
	// Schritt 1: Route
	await page.getByTestId('trip-wizard-step1-name').fill('Step5-Reports-Test');
	await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
	// Schritt 1 → 2 → 3 → 4 → 5
	await page.getByTestId('trip-wizard-next').click();
	await page.getByTestId('trip-wizard-next').click();
	await page.getByTestId('trip-wizard-next').click();
	await page.getByTestId('trip-wizard-next').click();
	// Schritt 5 (Reports) muss sichtbar sein
	await expect(page.getByTestId('step5-reports')).toBeVisible();
}

test.describe('Trip-Wizard Schritt 5 — Reports 3-Cards + Trend-Toggle (Issue #432)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-12: step5-reports Container ist sichtbar', async ({ page }) => {
		await gotoStep5Reports(page);
		await expect(page.getByTestId('step5-reports')).toBeVisible();
	});

	test('AC-12: Drei Report-Cards vorhanden (card-evening, card-morning, card-alerts)', async ({
		page
	}) => {
		await gotoStep5Reports(page);
		await expect(page.getByTestId('card-evening')).toBeVisible();
		await expect(page.getByTestId('card-morning')).toBeVisible();
		await expect(page.getByTestId('card-alerts')).toBeVisible();
	});

	test('AC-13: Abend-Briefing-Card hat Checkbox und Uhrzeit-Feld', async ({ page }) => {
		await gotoStep5Reports(page);
		const eveningCard = page.getByTestId('card-evening');
		await expect(eveningCard).toBeVisible();
		await expect(eveningCard.locator('input[type="checkbox"]').first()).toBeVisible();
		await expect(page.getByTestId('evening-time')).toBeVisible();
	});

	test('AC-13: Abend-Briefing Uhrzeit ändern → Input zeigt neuen Wert', async ({ page }) => {
		await gotoStep5Reports(page);
		const timeInput = page.getByTestId('evening-time');
		await timeInput.fill('20:00');
		await expect(timeInput).toHaveValue('20:00');
	});

	test('AC-13: Morgen-Update-Card hat Checkbox und Uhrzeit-Feld', async ({ page }) => {
		await gotoStep5Reports(page);
		const morningCard = page.getByTestId('card-morning');
		await expect(morningCard).toBeVisible();
		await expect(morningCard.locator('input[type="checkbox"]').first()).toBeVisible();
		await expect(page.getByTestId('morning-time')).toBeVisible();
	});

	test('AC-18: Mehrtages-Trend ist Toggle in Abend-Card, Default checked=true', async ({
		page
	}) => {
		await gotoStep5Reports(page);
		const trendToggle = page.getByTestId('evening-trend-toggle');
		await expect(trendToggle).toBeVisible();
		// Default true (AC-18): Trend ist standardmäßig eingeschaltet
		await expect(trendToggle).toBeChecked();
	});

	test('AC-15: Pro Report-Card eine Kanal-Chips-Reihe (evening, morning, alerts)', async ({
		page
	}) => {
		await gotoStep5Reports(page);
		await expect(page.getByTestId('channel-chips-evening')).toBeVisible();
		await expect(page.getByTestId('channel-chips-morning')).toBeVisible();
		await expect(page.getByTestId('channel-chips-alerts')).toBeVisible();
	});

	test('AC-1: Step-Labels in Stepper sind Route, Etappen, Wetter, Layout, Reports', async ({
		page
	}) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-shell')).toBeVisible();
		// Alle fünf Labels müssen sichtbar sein
		await expect(page.getByText('Route')).toBeVisible();
		await expect(page.getByText('Etappen')).toBeVisible();
		await expect(page.getByText('Wetter')).toBeVisible();
		await expect(page.getByText('Layout')).toBeVisible();
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
