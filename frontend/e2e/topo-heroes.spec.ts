import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #220 — Topo-Muster auf Hero-Bereichen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-1: Cockpit-Topbar enthält .g-topo', async ({ page }) => {
		await page.goto('/');
		const topbar = page.getByTestId('cockpit-topbar');
		await expect(topbar).toBeVisible();
		// .g-topo ist Sibling im TopoBg-Outer-Wrapper (div.relative.overflow-hidden).
		// Wrapper ist Großeltern des Headers → wir suchen .g-topo im TopoBg-Outer-Ancestor.
		const hasTopo = await topbar
			.locator('xpath=ancestor::div[contains(@class,"overflow-hidden")]//*[contains(@class,"g-topo")]')
			.count();
		expect(hasTopo).toBeGreaterThan(0);
	});

	test('AC-2: Trip-Hero enthält .g-topo', async ({ page }) => {
		await page.goto('/trips/e2e-cockpit-test');
		const hero = page.getByTestId('trip-hero');
		await expect(hero).toBeVisible();
		const hasTopo = await hero
			.locator('xpath=ancestor::div[contains(@class,"overflow-hidden")]//*[contains(@class,"g-topo")]')
			.count();
		expect(hasTopo).toBeGreaterThan(0);
	});

	test('AC-3: Wizard-Header enthält .g-topo um Stepper', async ({ page }) => {
		await page.goto('/trips/new');
		const stepper = page.getByTestId('trip-wizard-stepper');
		await expect(stepper).toBeVisible();
		const hasTopo = await stepper
			.locator('xpath=ancestor::div[contains(@class,"relative")]//*[contains(@class,"g-topo")]')
			.count();
		expect(hasTopo).toBeGreaterThan(0);
	});

	test('AC-4: Wizard-Topo umschließt NICHT den Step-Slot (Scope-Guard)', async ({ page }) => {
		await page.goto('/trips/new');
		const step1 = page.getByTestId('trip-wizard-step1-profile');
		await expect(step1).toBeVisible();
		// Step1Profile darf keinen .g-topo-Ancestor haben
		const topoAncestors = await step1
			.locator('xpath=ancestor::*[contains(@class,"g-topo")]')
			.count();
		expect(topoAncestors).toBe(0);
	});
});
