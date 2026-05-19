// TDD RED — E2E-Tests fuer TemplatePicker (Issue #165, Sub-Spec epic_136_step5_templates.md).
// Erwartet: FAIL bis TemplatePicker.svelte + Step2-Layout-Umbau implementiert sind.
//
// Spec-Referenz: docs/specs/modules/epic_136_step5_templates.md
//
// TestID-Inventar (Sub-Spec §5):
//   trip-wizard-template-picker
//   trip-wizard-template-card-gr20
//   trip-wizard-template-card-khw
//   trip-wizard-template-card-stubai
//   trip-wizard-template-apply-gr20
//   trip-wizard-template-apply-khw
//   trip-wizard-template-apply-stubai
//   trip-wizard-template-confirm-dialog
//   trip-wizard-template-confirm-ok
//   trip-wizard-template-confirm-cancel
//   trip-wizard-step2-layout

import { test, expect } from '@playwright/test';
import { login, fillStep1, type Step1Input } from './helpers.js';

const DEFAULT_STEP1: Step1Input = {
	activity: 'trekking',
	name: 'Template-Test',
	startDate: '2026-07-01'
};

async function gotoStep2(page: import('@playwright/test').Page) {
	await page.goto('/trips/new');
	await fillStep1(page, DEFAULT_STEP1);
	await page.getByTestId('trip-wizard-next').click();
	await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();
}

test.describe('Trip-Wizard Templates -- TemplatePicker (#165)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-1: Alle drei Vorlage-Karten sichtbar
	test('AC-1: TemplatePicker und alle drei Karten sind sichtbar', async ({ page }) => {
		await gotoStep2(page);
		await expect(page.getByTestId('trip-wizard-template-picker')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-template-card-gr20')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-template-card-khw')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-template-card-stubai')).toBeVisible();
	});

	// AC-10: Karten zeigen Region und Etappenanzahl
	test('AC-10: GR20-Karte zeigt "14 Etappen" und "Korsika"', async ({ page }) => {
		await gotoStep2(page);
		const card = page.getByTestId('trip-wizard-template-card-gr20');
		await expect(card).toContainText('14 Etappen');
		await expect(card).toContainText('Korsika');
	});

	test('KHW-Karte zeigt "13 Etappen"', async ({ page }) => {
		await gotoStep2(page);
		const card = page.getByTestId('trip-wizard-template-card-khw');
		await expect(card).toContainText('13 Etappen');
	});

	test('Stubai-Karte zeigt "7 Etappen"', async ({ page }) => {
		await gotoStep2(page);
		const card = page.getByTestId('trip-wizard-template-card-stubai');
		await expect(card).toContainText('7 Etappen');
	});

	// AC-2: Vorlage laden bei leerem stages -- kein Dialog
	test('AC-2: KHW laden (leere Etappenliste) zeigt keinen Dialog und fuegt 13 Etappen ein', async ({
		page
	}) => {
		await gotoStep2(page);
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).not.toBeVisible();
		await page.getByTestId('trip-wizard-template-apply-khw').click();
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).not.toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-12')).toBeVisible();
	});

	// AC-11: Weiter-Button nach Template-Laden aktiv
	test('AC-11: Nach KHW-Laden ist der Weiter-Button aktiv', async ({ page }) => {
		await gotoStep2(page);
		await page.getByTestId('trip-wizard-template-apply-khw').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	// AC-3: Dialog bei vorhandenen Etappen
	test('AC-3: Zweites Template-Laden oeffnet Bestaetigungs-Dialog', async ({ page }) => {
		await gotoStep2(page);
		await page.getByTestId('trip-wizard-template-apply-khw').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
		await page.getByTestId('trip-wizard-template-apply-gr20').click();
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).toBeVisible();
	});

	// AC-4: Dialog abbrechen -- Etappen unveraendert
	test('AC-4: Abbrechen im Dialog laesst KHW-Etappen unveraendert', async ({ page }) => {
		await gotoStep2(page);
		await page.getByTestId('trip-wizard-template-apply-khw').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-12')).toBeVisible();
		await page.getByTestId('trip-wizard-template-apply-gr20').click();
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).toBeVisible();
		await page.getByTestId('trip-wizard-template-confirm-cancel').click();
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).not.toBeVisible();
		// Noch immer 13 Etappen (KHW), nicht 14 (GR20)
		await expect(page.getByTestId('trip-wizard-step2-stage-row-12')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-13')).not.toBeVisible();
	});

	// AC-5: Dialog bestaetigen -- Etappen ersetzen
	test('AC-5: Bestaetigen im Dialog ersetzt KHW (13) durch GR20 (14) Etappen', async ({
		page
	}) => {
		await gotoStep2(page);
		await page.getByTestId('trip-wizard-template-apply-khw').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-12')).toBeVisible();
		await page.getByTestId('trip-wizard-template-apply-gr20').click();
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).toBeVisible();
		await page.getByTestId('trip-wizard-template-confirm-ok').click();
		await expect(page.getByTestId('trip-wizard-template-confirm-dialog')).not.toBeVisible();
		// GR20 hat 14 Etappen (index 0..13)
		await expect(page.getByTestId('trip-wizard-step2-stage-row-13')).toBeVisible();
	});

	// AC-8: Name-Schutz -- bestehender Name wird nicht ueberschrieben
	test('AC-8: Vorlage-Laden ueberschreibt vorhandenen Trip-Namen nicht', async ({ page }) => {
		await gotoStep2(page);
		await page.getByTestId('trip-wizard-template-apply-khw').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
		await page.getByTestId('trip-wizard-back').click();
		const nameInput = page.getByTestId('trip-wizard-step1-name');
		await expect(nameInput).toHaveValue('Template-Test');
	});

	// AC-12: Two-Column-Layout vorhanden
	test('AC-12: Step-2-Grid-Wrapper ist sichtbar und enthaelt beide Spalten', async ({ page }) => {
		await gotoStep2(page);
		await expect(page.getByTestId('trip-wizard-step2-layout')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-template-picker')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-dropzone')).toBeVisible();
	});

	// Stubai laden bei leerer Liste
	test('Stubai laden fuegt genau 7 Etappen ein', async ({ page }) => {
		await gotoStep2(page);
		await page.getByTestId('trip-wizard-template-apply-stubai').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-6')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-7')).not.toBeVisible();
	});
});
