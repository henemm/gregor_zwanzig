// E2E-Tests fuer Epic #136 Sub-Spec #160 (Wizard-Shell + Stepper).
//
// Spec-Referenz: docs/specs/modules/epic_136_step0_shell.md
//   - Acceptance #1, #3, #4, #5, #5a, #6, #7, #8, #11
//
// TestID-Inventar (Sub-Spec §7):
//   trip-wizard-shell, trip-wizard-stepper,
//   trip-wizard-step-1..4 mit data-state="done|active|pending",
//   trip-wizard-step1-profile, trip-wizard-step2-stages,
//   trip-wizard-step3-waypoints, trip-wizard-step4-briefings,
//   trip-wizard-back, trip-wizard-cancel, trip-wizard-next, trip-wizard-save.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Trip-Wizard Shell (#160)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC#1: /trips/new rendert TripWizardShell', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-shell')).toBeVisible();
	});

	test('AC#3+#4: Stepper rendert 4 Indikatoren, Step 1 aktiv', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-stepper')).toBeVisible();
		for (let i = 1; i <= 4; i++) {
			await expect(page.getByTestId(`trip-wizard-step-${i}`)).toBeVisible();
		}
		await expect(page.getByTestId('trip-wizard-step-1')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-wizard-step-2')).toHaveAttribute('data-state', 'pending');
		await expect(page.getByTestId('trip-wizard-step-3')).toHaveAttribute('data-state', 'pending');
		await expect(page.getByTestId('trip-wizard-step-4')).toHaveAttribute('data-state', 'pending');
	});

	test('AC#5+#6: Weiter wechselt zu Step 2, Indikatoren updaten data-state', async ({ page }) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step-1')).toHaveAttribute('data-state', 'done');
		await expect(page.getByTestId('trip-wizard-step-2')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();
	});

	test('AC#5: Zurueck wechselt zu Step 1 von Step 2', async ({ page }) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-next').click();
		await page.getByTestId('trip-wizard-back').click();
		await expect(page.getByTestId('trip-wizard-step-1')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();
	});

	test('AC#5a: Weiter-Button in Steps 1-3 enabled', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
		await page.getByTestId('trip-wizard-next').click(); // -> Step 2
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
		await page.getByTestId('trip-wizard-next').click(); // -> Step 3
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	test('AC#7: Cancel navigiert zu /', async ({ page }) => {
		await page.goto('/trips/new');
		await page.getByTestId('trip-wizard-cancel').click();
		await page.waitForURL('/');
	});

	test('AC#8: Speichern-Button erscheint nur in Step 4', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-save')).not.toBeVisible();
		await page.getByTestId('trip-wizard-next').click(); // 2
		await page.getByTestId('trip-wizard-next').click(); // 3
		await page.getByTestId('trip-wizard-next').click(); // 4
		await expect(page.getByTestId('trip-wizard-save')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-next')).not.toBeVisible();
	});

	test('AC#11: alle 4 Step-Slot-Container sind in den jeweiligen Steps sichtbar', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step3-waypoints')).toBeVisible();
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step4-briefings')).toBeVisible();
	});

	test('Step 1 hat keinen Zurueck-Button', async ({ page }) => {
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-shell')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-back')).not.toBeVisible();
	});
});
