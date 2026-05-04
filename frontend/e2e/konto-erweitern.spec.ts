import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Konto erweitern: System-Status auf /account', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/account');
	});

	test('account page has system-status anchor section', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Page renders
		 * THEN: An element with id="system-status" exists
		 */
		await expect(page.locator('#system-status')).toBeVisible();
	});

	test('shows "Deine Reports" section on account page', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: System-Status section renders
		 * THEN: "Deine Reports" card with scheduler jobs is visible
		 */
		const section = page.locator('#system-status');
		await expect(section.getByText('Deine Reports')).toBeVisible();
	});

	test('shows scheduler job names (Morgen/Abend/Trip)', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: "Deine Reports" card renders
		 * THEN: All 3 user-facing job names are shown
		 */
		const section = page.locator('#system-status');
		await expect(section.getByText('Morgen-Report')).toBeVisible();
		await expect(section.getByText('Abend-Report')).toBeVisible();
		await expect(section.getByText('Trip-Checks')).toBeVisible();
	});

	test('shows "Dein Account" section with stats', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: System-Status section renders
		 * THEN: "Dein Account" card with trip/sub/location counters is visible
		 */
		const section = page.locator('#system-status [data-testid="account-section"]');
		await expect(section).toBeVisible();
		await expect(section.getByText('Aktive Trips')).toBeVisible();
	});

	test('shows "Verfügbarkeit" section with health status', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: System-Status section renders
		 * THEN: "Verfügbarkeit" card with health indicator is visible
		 */
		const section = page.locator('#system-status');
		await expect(section.getByText('Verfügbarkeit')).toBeVisible();
		await expect(section.getByText(/System läuft|Eingeschränkt|Nicht erreichbar/)).toBeVisible();
	});
});

test.describe('F76 Konto erweitern: Wetter-Templates Card', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/account');
	});

	test('shows "Wetter-Templates" card', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Page renders
		 * THEN: A card titled "Wetter-Templates" is visible
		 */
		await expect(page.getByText('Wetter-Templates')).toBeVisible();
	});

	test('shows system templates list', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Templates card renders
		 * THEN: At least "Alpen-Trekking" and "Wandern" templates are listed
		 */
		await expect(page.getByText('Alpen-Trekking')).toBeVisible();
		await expect(page.getByText('Wandern')).toBeVisible();
	});

	test('templates are read-only (no edit/delete buttons)', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Templates card renders
		 * THEN: No edit or delete buttons exist in the templates section
		 */
		const templatesCard = page.locator('text=Wetter-Templates').locator('..');
		await expect(templatesCard.getByRole('button')).toHaveCount(0);
	});
});

test.describe('F76 Konto erweitern: SMS/Satellite Platzhalter', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/account');
	});

	test('shows disabled SMS field with "Kommt bald" badge', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Kanäle card renders
		 * THEN: A disabled SMS input with "Kommt bald" badge is visible
		 */
		await expect(page.getByText('SMS-Nummer')).toBeVisible();
		const smsInput = page.locator('input[placeholder*="+43664"]').last();
		await expect(smsInput).toBeDisabled();
	});

	test('shows disabled Satphone field with "Kommt bald" badge', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Kanäle card renders
		 * THEN: A disabled Satphone input with "Kommt bald" badge is visible
		 */
		await expect(page.getByText('Satphone (Iridium)')).toBeVisible();
		const satInput = page.locator('input[placeholder="Iridium-Nummer"]');
		await expect(satInput).toBeDisabled();
	});

	test('"Kommt bald" badges are shown for both placeholders', async ({ page }) => {
		/**
		 * GIVEN: User is on /account
		 * WHEN: Kanäle card renders
		 * THEN: Two "Kommt bald" badges are visible
		 */
		const badges = page.getByText('Kommt bald');
		await expect(badges).toHaveCount(2);
	});
});

test.describe('F76 Konto erweitern: Layout anchor link', () => {
	test('System-Status menu links to /account#system-status', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: User menu dropdown is opened
		 * THEN: "System-Status" link has href="/account#system-status"
		 */
		await login(page);
		await page.goto('/');
		// Open the user dropdown menu in the sidebar footer
		await page.locator('nav button:has(span.rounded-full)').click();
		const link = page.locator('a[href="/account#system-status"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('System-Status');
	});
});
