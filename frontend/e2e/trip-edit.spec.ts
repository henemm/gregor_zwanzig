import { test, expect, devices } from '@playwright/test';
import { login } from './helpers.js';

const SEED_TRIP_NAME = 'EditView-Seed-Trip';

async function seedTrip(page: import('@playwright/test').Page) {
	await page.goto('/trips/new');
	await page.locator('[data-testid="trip-name-input"]').fill(SEED_TRIP_NAME);
	await page.locator('button', { hasText: /[Mm]anuell/ }).click();
	await page.locator('[data-testid="wizard-next"]').click();
	await page.locator('button', { hasText: /[Ww]egpunkt/ }).click();
	await page.locator('input[name="lat"]').first().fill('47.0');
	await page.locator('input[name="lon"]').first().fill('11.0');
	await page.locator('[data-testid="wizard-next"]').click();
	await page.locator('[data-testid="wizard-next"]').click();
	await page.locator('[data-testid="wizard-save"]').click();
	await page.waitForURL('/trips', { timeout: 10000 });
}

async function gotoSeedEdit(page: import('@playwright/test').Page) {
	await page.goto('/trips');
	const row = page.locator(`tr:has-text("${SEED_TRIP_NAME}")`).first();
	await expect(row).toBeVisible();
	await row.locator('[data-testid="trip-edit-btn"]').click();
	await page.waitForURL(/\/trips\/[^/]+\/edit/);
}

test.describe('Trip Edit View (Issue #91)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/trips');
		const seedRow = page.locator(`tr:has-text("${SEED_TRIP_NAME}")`).first();
		if (!(await seedRow.isVisible({ timeout: 2000 }).catch(() => false))) {
			await seedTrip(page);
		}
	});

	// AC-1: Edit zeigt EditView, kein Wizard-Stepper
	test('AC-1: edit page renders TripEditView, not wizard stepper', async ({ page }) => {
		await gotoSeedEdit(page);

		await expect(page.locator('[data-testid="trip-edit-view"]')).toBeVisible();

		const stepper = page.locator('[data-testid="wizard-stepper"]');
		await expect(stepper).not.toBeVisible();

		const nextBtn = page.locator('[data-testid="wizard-next"]');
		await expect(nextBtn).not.toBeVisible();
	});

	// AC-2: Vier Akkordeon-Sektionen, "Etappen" initial offen
	test('AC-2: four accordion sections, "Etappen" initially open', async ({ page }) => {
		await gotoSeedEdit(page);

		for (const id of ['route', 'etappen', 'wetter', 'reports']) {
			await expect(page.locator(`[data-testid="edit-section-${id}"]`)).toBeVisible();
		}

		const etappenHeader = page.locator('[data-testid="edit-section-etappen-header"]');
		await expect(etappenHeader).toHaveAttribute('aria-expanded', 'true');

		for (const id of ['route', 'wetter', 'reports']) {
			const header = page.locator(`[data-testid="edit-section-${id}-header"]`);
			await expect(header).toHaveAttribute('aria-expanded', 'false');
		}
	});

	// Akkordeon-Verhalten: Tap auf andere Sektion schließt aktuelle, öffnet neue
	test('accordion: tapping another section closes current, opens new', async ({ page }) => {
		await gotoSeedEdit(page);

		await page.locator('[data-testid="edit-section-wetter-header"]').click();

		await expect(page.locator('[data-testid="edit-section-wetter-header"]'))
			.toHaveAttribute('aria-expanded', 'true');
		await expect(page.locator('[data-testid="edit-section-etappen-header"]'))
			.toHaveAttribute('aria-expanded', 'false');
	});

	// Akkordeon-Verhalten: Tap auf offenen Header schließt ihn
	test('accordion: tapping open header closes it', async ({ page }) => {
		await gotoSeedEdit(page);

		await page.locator('[data-testid="edit-section-etappen-header"]').click();
		await expect(page.locator('[data-testid="edit-section-etappen-header"]'))
			.toHaveAttribute('aria-expanded', 'false');
	});

	// AC-3: Bestehende Trip-Daten sind vorgeladen
	test('AC-3: existing trip data is prefilled', async ({ page }) => {
		await gotoSeedEdit(page);

		await page.locator('[data-testid="edit-section-route-header"]').click();

		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await expect(nameInput).toBeVisible();
		await expect(nameInput).toHaveValue(SEED_TRIP_NAME);

		await page.locator('[data-testid="edit-section-etappen-header"]').click();
		const stageCard = page.locator('[data-testid^="stage-card-"]').first();
		await expect(stageCard).toBeVisible();
	});

	// AC-4: Speichern-Button sendet PUT, Redirect nach /trips
	test('AC-4: save button persists changes via PUT and redirects', async ({ page }) => {
		await gotoSeedEdit(page);

		const putPromise = page.waitForRequest(req =>
			req.method() === 'PUT' && /\/api\/trips\/[^/]+$/.test(req.url())
		);

		const saveBtn = page.locator('[data-testid="edit-save-btn"]');
		await expect(saveBtn).toBeVisible();
		await saveBtn.click();

		const putReq = await putPromise;
		expect(putReq.method()).toBe('PUT');

		await page.waitForURL('/trips', { timeout: 5000 });
	});

	// AC-5: Cancel navigiert ohne API-Call
	test('AC-5: cancel button navigates without PUT', async ({ page }) => {
		await gotoSeedEdit(page);

		let putCalled = false;
		page.on('request', req => {
			if (req.method() === 'PUT' && /\/api\/trips\//.test(req.url())) {
				putCalled = true;
			}
		});

		const cancelBtn = page.locator('[data-testid="edit-cancel-btn"]');
		await expect(cancelBtn).toBeVisible();
		await cancelBtn.click();

		await page.waitForURL('/trips', { timeout: 5000 });
		expect(putCalled).toBe(false);
	});

	// AC-6: Mobile-Viewport (375px)
	test('AC-6: works on mobile viewport (375x667)', async ({ browser }) => {
		const context = await browser.newContext({
			...devices['iPhone SE'],
			viewport: { width: 375, height: 667 },
		});
		const page = await context.newPage();
		await login(page);

		await page.goto('/trips');
		const seedRow = page.locator(`tr:has-text("${SEED_TRIP_NAME}")`).first();
		await expect(seedRow).toBeVisible();
		await seedRow.locator('[data-testid="trip-edit-btn"]').click();
		await page.waitForURL(/\/trips\/[^/]+\/edit/);

		for (const id of ['route', 'etappen', 'wetter', 'reports']) {
			const header = page.locator(`[data-testid="edit-section-${id}-header"]`);
			await expect(header).toBeVisible();
			const box = await header.boundingBox();
			expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
		}

		await page.locator('[data-testid="edit-section-wetter-header"]').tap();
		await expect(page.locator('[data-testid="edit-section-wetter-header"]'))
			.toHaveAttribute('aria-expanded', 'true');

		await context.close();
	});

	// Datenintegrität: Save ohne UI-Änderung darf andere Felder nicht löschen (vs Issue #102)
	test('data integrity: save without changes preserves all fields', async ({ page, request }) => {
		await gotoSeedEdit(page);

		const url = page.url();
		const tripId = url.match(/\/trips\/([^/]+)\/edit/)?.[1];
		expect(tripId).toBeTruthy();

		const before = await request.get(`/api/trips/${tripId}`);
		expect(before.ok()).toBe(true);
		const beforeJson = await before.json();

		await page.locator('[data-testid="edit-save-btn"]').click();
		await page.waitForURL('/trips', { timeout: 5000 });

		const after = await request.get(`/api/trips/${tripId}`);
		expect(after.ok()).toBe(true);
		const afterJson = await after.json();

		expect(afterJson.weather_config).toEqual(beforeJson.weather_config);
		expect(afterJson.report_config).toEqual(beforeJson.report_config);
		expect(afterJson.display_config).toEqual(beforeJson.display_config);
		expect(afterJson.avalanche_regions).toEqual(beforeJson.avalanche_regions);
		expect(afterJson.aggregation).toEqual(beforeJson.aggregation);
		expect(afterJson.stages?.length).toBe(beforeJson.stages?.length);
	});
});
