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
	// trip-edit-btn liegt im Kebab-Menü (#295)
	await row.getByTitle('Weitere Aktionen').click();
	await row.locator('[data-testid="trip-edit-btn"]').click();
	await page.waitForURL(/\/trips\/[^/]+\/edit/);
}

function tabByValue(page: import('@playwright/test').Page, value: string) {
	return page
		.getByTestId('edit-tabs')
		.locator(`[data-value="${value}"], [role="tab"]:has-text("${value}")`)
		.first();
}

test.describe('Trip Edit View (Issue #91 / #494)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/trips');
		const seedRow = page.locator(`tr:has-text("${SEED_TRIP_NAME}")`).first();
		if (!(await seedRow.isVisible({ timeout: 2000 }).catch(() => false))) {
			await seedTrip(page);
		}
	});

	// AC-1: Edit zeigt TripEditView, kein Wizard-Stepper
	test('AC-1: edit page renders TripEditView, not wizard stepper', async ({ page }) => {
		await gotoSeedEdit(page);

		await expect(page.locator('[data-testid="trip-edit-view"]')).toBeVisible();

		const stepper = page.locator('[data-testid="wizard-stepper"]');
		await expect(stepper).not.toBeVisible();

		const nextBtn = page.locator('[data-testid="wizard-next"]');
		await expect(nextBtn).not.toBeVisible();
	});

	// AC-2 (Issue #494): Fünf horizontale Tabs, "Etappen" initial aktiv
	test('AC-2: five horizontal tabs, "Etappen" initially active', async ({ page }) => {
		await gotoSeedEdit(page);

		await expect(page.getByTestId('edit-tabs')).toBeVisible();

		for (const id of ['route', 'etappen', 'wetter', 'reports', 'alarmregeln']) {
			await expect(tabByValue(page, id)).toBeVisible();
		}

		// Default-Tab "etappen" zeigt seinen Inhalt (Stage-Cards) sofort
		await expect(page.locator('[data-testid^="stage-card-"]').first()).toBeVisible();

		// Andere Tab-Inhalte sind nicht sichtbar (Route-Input erscheint erst beim Tab-Wechsel)
		await expect(page.locator('[data-testid="trip-name-input"]')).toHaveCount(0);
	});

	// Tab-Verhalten: Klick auf anderen Tab zeigt neuen Inhalt
	test('tabs: clicking another tab shows its content', async ({ page }) => {
		await gotoSeedEdit(page);

		await tabByValue(page, 'wetter').click();

		// Wetter-Tab: Stage-Cards aus dem Etappen-Tab sind nun weg
		await expect(page.locator('[data-testid^="stage-card-"]')).toHaveCount(0);

		// Stats-Karte bleibt sichtbar (Tab-übergreifend)
		await expect(page.getByTestId('edit-stats-card')).toBeVisible();
	});

	// Tab-Verhalten: Wechsel zurück auf Etappen
	test('tabs: switching back to Etappen restores its content', async ({ page }) => {
		await gotoSeedEdit(page);

		await tabByValue(page, 'route').click();
		await expect(page.locator('[data-testid="trip-name-input"]')).toBeVisible();

		await tabByValue(page, 'etappen').click();
		await expect(page.locator('[data-testid^="stage-card-"]').first()).toBeVisible();
	});

	// AC-3: Bestehende Trip-Daten sind vorgeladen (im Route-Tab)
	test('AC-3: existing trip data is prefilled', async ({ page }) => {
		await gotoSeedEdit(page);

		await tabByValue(page, 'route').click();

		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await expect(nameInput).toBeVisible();
		await expect(nameInput).toHaveValue(SEED_TRIP_NAME);

		await tabByValue(page, 'etappen').click();
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

	// AC-6: Mobile-Viewport (375px) — Tabs bleiben tappable
	test('AC-6: works on mobile viewport (375x667)', async ({ browser }) => {
		const context = await browser.newContext({
			...devices['iPhone SE'],
			viewport: { width: 375, height: 667 },
		});
		const page = await context.newPage();
		await login(page);

		// Auf Mobile zeigt /trips Card-Stack statt Tabelle.
		await page.goto('/trips');
		const card = page.locator(`[data-testid="trip-card"]:has-text("${SEED_TRIP_NAME}")`).first();
		await expect(card).toBeVisible();
		await card.locator('[data-testid="trip-card-menu-btn"]').click();
		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible();
		await sheet.getByRole('button', { name: /Bearbeiten/i }).click();
		await page.waitForURL(/\/trips\/[^/]+\/edit/);

		await expect(page.getByTestId('edit-tabs')).toBeVisible();

		// Tab-Buttons sind tappable
		for (const id of ['route', 'etappen', 'wetter', 'reports', 'alarmregeln']) {
			await expect(tabByValue(page, id)).toBeVisible();
		}

		await tabByValue(page, 'wetter').tap();
		// Nach Tap auf Wetter-Tab: keine Stage-Cards mehr sichtbar
		await expect(page.locator('[data-testid^="stage-card-"]')).toHaveCount(0);

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
