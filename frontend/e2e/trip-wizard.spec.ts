import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Trip Wizard W1', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// --- Route Existence ---

	test('wizard create route exists at /trips/new', async ({ page }) => {
		const res = await page.goto('/trips/new');
		// Should NOT return 404
		expect(res?.status()).not.toBe(404);
		// Should show wizard content (stepper or step 1)
		await expect(page.locator('[data-testid="trip-wizard"]')).toBeVisible({ timeout: 5000 });
	});

	// --- Stepper UI ---

	test('wizard shows 4-step stepper with Route as active', async ({ page }) => {
		await page.goto('/trips/new');
		const stepper = page.locator('[data-testid="wizard-stepper"]');
		await expect(stepper).toBeVisible();

		// 4 steps visible
		const steps = stepper.locator('[data-testid^="wizard-step-"]');
		await expect(steps).toHaveCount(4);

		// First step is active
		const step1 = stepper.locator('[data-testid="wizard-step-1"]');
		await expect(step1).toHaveAttribute('data-active', 'true');
	});

	test('stepper labels are Route, Etappen, Wetter, Reports', async ({ page }) => {
		await page.goto('/trips/new');
		const stepper = page.locator('[data-testid="wizard-stepper"]');
		await expect(stepper.locator('text=Route')).toBeVisible();
		await expect(stepper.locator('text=Etappen')).toBeVisible();
		await expect(stepper.locator('text=Wetter')).toBeVisible();
		await expect(stepper.locator('text=Reports')).toBeVisible();
	});

	// --- Step 1: Route ---

	test('step 1 shows GPX upload zone', async ({ page }) => {
		await page.goto('/trips/new');
		const dropZone = page.locator('[data-testid="gpx-drop-zone"]');
		await expect(dropZone).toBeVisible();
	});

	test('step 1 shows trip name input', async ({ page }) => {
		await page.goto('/trips/new');
		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await expect(nameInput).toBeVisible();
	});

	test('step 1 has manual create button', async ({ page }) => {
		await page.goto('/trips/new');
		const manualBtn = page.locator('button', { hasText: /[Mm]anuell/ });
		await expect(manualBtn).toBeVisible();
	});

	test('step 1 weiter button is disabled without trip name', async ({ page }) => {
		await page.goto('/trips/new');
		const weiterBtn = page.locator('[data-testid="wizard-next"]');
		await expect(weiterBtn).toBeVisible();
		await expect(weiterBtn).toBeDisabled();
	});

	test('step 1 weiter button enabled after entering trip name and adding stage', async ({ page }) => {
		await page.goto('/trips/new');

		// Enter trip name
		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await nameInput.fill('Test Tour');

		// Add manual stage
		const manualBtn = page.locator('button', { hasText: /[Mm]anuell/ });
		await manualBtn.click();

		// Weiter should now be enabled
		const weiterBtn = page.locator('[data-testid="wizard-next"]');
		await expect(weiterBtn).toBeEnabled();
	});

	// --- Step 2: Stages ---

	test('step 2 shows stages from step 1', async ({ page }) => {
		await page.goto('/trips/new');

		// Fill step 1
		await page.locator('[data-testid="trip-name-input"]').fill('Wizard Test');
		await page.locator('button', { hasText: /[Mm]anuell/ }).click();

		// Navigate to step 2
		await page.locator('[data-testid="wizard-next"]').click();

		// Step 2 should show stage cards
		const stageCard = page.locator('[data-testid^="stage-card-"]');
		await expect(stageCard).toHaveCount(1);
	});

	test('step 2 allows adding waypoints', async ({ page }) => {
		await page.goto('/trips/new');

		// Fill step 1
		await page.locator('[data-testid="trip-name-input"]').fill('Wizard Test');
		await page.locator('button', { hasText: /[Mm]anuell/ }).click();
		await page.locator('[data-testid="wizard-next"]').click();

		// Add waypoint
		const addWpBtn = page.locator('button', { hasText: /[Ww]egpunkt/ });
		await addWpBtn.click();

		// Waypoint fields should appear
		const wpRow = page.locator('[data-testid^="waypoint-"]');
		await expect(wpRow.first()).toBeVisible();
	});

	test('step 2 allows adding more stages', async ({ page }) => {
		await page.goto('/trips/new');

		// Fill step 1
		await page.locator('[data-testid="trip-name-input"]').fill('Wizard Test');
		await page.locator('button', { hasText: /[Mm]anuell/ }).click();
		await page.locator('[data-testid="wizard-next"]').click();

		// Add another stage
		const addStageBtn = page.locator('button', { hasText: /[Ee]tappe.*hinzu|[Ss]tage.*add/i });
		await addStageBtn.click();

		const stageCards = page.locator('[data-testid^="stage-card-"]');
		await expect(stageCards).toHaveCount(2);
	});

	// --- Navigation ---

	test('back button on step 2 returns to step 1', async ({ page }) => {
		await page.goto('/trips/new');

		// Go to step 2
		await page.locator('[data-testid="trip-name-input"]').fill('Nav Test');
		await page.locator('button', { hasText: /[Mm]anuell/ }).click();
		await page.locator('[data-testid="wizard-next"]').click();

		// Click back
		await page.locator('[data-testid="wizard-back"]').click();

		// Step 1 content should be visible again
		await expect(page.locator('[data-testid="gpx-drop-zone"]')).toBeVisible();

		// Trip name should be preserved
		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await expect(nameInput).toHaveValue('Nav Test');
	});

	test('cancel button navigates to /trips', async ({ page }) => {
		await page.goto('/trips/new');
		const cancelBtn = page.locator('[data-testid="wizard-cancel"]');
		await cancelBtn.click();
		await page.waitForURL('/trips');
	});

	test('step 1 has no back button but wizard is visible', async ({ page }) => {
		await page.goto('/trips/new');
		// Wizard must be present first
		await expect(page.locator('[data-testid="trip-wizard"]')).toBeVisible({ timeout: 5000 });
		// Then check: no back button on step 1
		const backBtn = page.locator('[data-testid="wizard-back"]');
		await expect(backBtn).not.toBeVisible();
	});

	// --- Placeholder Steps 3+4 ---

	test('steps 3 and 4 show placeholder content', async ({ page }) => {
		await page.goto('/trips/new');

		// Go through steps 1 and 2
		await page.locator('[data-testid="trip-name-input"]').fill('Placeholder Test');
		await page.locator('button', { hasText: /[Mm]anuell/ }).click();
		await page.locator('[data-testid="wizard-next"]').click();

		// Add waypoint to pass step 2 validation
		await page.locator('button', { hasText: /[Ww]egpunkt/ }).click();
		const latInput = page.locator('input[name="lat"]').first();
		await latInput.fill('47.0');
		const lonInput = page.locator('input[name="lon"]').first();
		await lonInput.fill('11.0');

		// Go to step 3
		await page.locator('[data-testid="wizard-next"]').click();
		await expect(page.locator('text=/[Kk]ommt.*W2/')).toBeVisible();

		// Go to step 4
		await page.locator('[data-testid="wizard-next"]').click();
		await expect(page.locator('text=/[Kk]ommt.*W3/')).toBeVisible();
	});

	// --- Save (Create) ---

	test('save button visible on last step', async ({ page }) => {
		await page.goto('/trips/new');

		// Navigate to step 4
		await page.locator('[data-testid="trip-name-input"]').fill('Save Test');
		await page.locator('button', { hasText: /[Mm]anuell/ }).click();
		await page.locator('[data-testid="wizard-next"]').click();

		// Add waypoint for validation
		await page.locator('button', { hasText: /[Ww]egpunkt/ }).click();
		await page.locator('input[name="lat"]').first().fill('47.0');
		await page.locator('input[name="lon"]').first().fill('11.0');

		await page.locator('[data-testid="wizard-next"]').click(); // step 3
		await page.locator('[data-testid="wizard-next"]').click(); // step 4

		const saveBtn = page.locator('[data-testid="wizard-save"]');
		await expect(saveBtn).toBeVisible();
	});

	// --- Edit Mode ---

	test('trips page edit button navigates to wizard', async ({ page }) => {
		await page.goto('/trips');

		// Find first edit button
		const editBtn = page.locator('[data-testid="trip-edit-btn"]').first();
		if (!(await editBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await editBtn.click();

		// Should navigate to /trips/{id}/edit
		await expect(page).toHaveURL(/\/trips\/[^/]+\/edit/);
		await expect(page.locator('[data-testid="trip-wizard"]')).toBeVisible();
	});

	test('edit mode pre-fills trip name', async ({ page }) => {
		await page.goto('/trips');

		const editBtn = page.locator('[data-testid="trip-edit-btn"]').first();
		if (!(await editBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await editBtn.click();
		await page.waitForURL(/\/trips\/[^/]+\/edit/);

		// Trip name should be pre-filled
		const nameInput = page.locator('[data-testid="trip-name-input"]');
		const value = await nameInput.inputValue();
		expect(value.length).toBeGreaterThan(0);
	});

	// --- Trips Page Integration ---

	test('trips page "Neuer Trip" navigates to /trips/new', async ({ page }) => {
		await page.goto('/trips');
		const newBtn = page.getByRole('button', { name: /[Nn]euer.*[Tt]rip|[Nn]eue.*[Tt]our/ });
		await expect(newBtn).toBeVisible();
		await newBtn.click();
		await page.waitForURL('/trips/new');
	});
});
