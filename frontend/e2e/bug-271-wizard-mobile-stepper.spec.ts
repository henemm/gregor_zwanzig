// TDD RED — E2E-Tests fuer bug_271_wizard_mobile_stepper.
// Spec: docs/specs/modules/bug_271_wizard_mobile_stepper.md
//
// AC-1: Kompakter Stepper auf Mobile (Step 1)
// AC-2: Stepper-Fortschritt auf Mobile (Step 2)
// AC-3: Desktop-Stepper unverändert (alle 4 Kreise sichtbar)
// AC-4: BottomNav auf Wizard-Route ausgeblendet
// AC-5: Weiter-Button Touch-Target ≥ 44 px

import { test, expect } from '@playwright/test';
import { login, fillStep1 } from './helpers.js';

const MOBILE_VIEWPORT = { width: 375, height: 667 };
const DESKTOP_VIEWPORT = { width: 1280, height: 800 };

const STEP1_INPUT = { activity: 'trekking' as const, name: 'Mobile-Test', startDate: '2026-07-01' };

test.describe('Bug #271 — Trip-Wizard Mobile: Stepper + Footer', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-1: Auf Mobile zeigt Stepper kompakten Text für Step 1
	test('AC-1: Mobile Compact Stepper zeigt "1 / 4 · Profil & Eckdaten" auf Step 1', async ({
		page
	}) => {
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips/new');

		const compact = page.getByTestId('trip-wizard-stepper-compact');
		await expect(compact).toBeVisible();
		await expect(compact).toContainText('1 / 4 · Profil & Eckdaten');
	});

	// AC-2: Compact Stepper wechselt Label bei Step 2
	test('AC-2: Mobile Compact Stepper zeigt "2 / 4 · GPX-Import" nach Navigation auf Step 2', async ({
		page
	}) => {
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips/new');
		await fillStep1(page, STEP1_INPUT);
		await page.getByTestId('trip-wizard-next').click();

		const compact = page.getByTestId('trip-wizard-stepper-compact');
		await expect(compact).toBeVisible();
		await expect(compact).toContainText('2 / 4 · GPX-Import');
	});

	// AC-3: Desktop zeigt alle 4 Kreise (full stepper), kein Compact
	test('AC-3: Desktop Stepper zeigt alle 4 Schritte-Kreise (unverändert)', async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips/new');

		// Full Stepper sichtbar
		const full = page.getByTestId('trip-wizard-stepper-full');
		await expect(full).toBeVisible();

		// Alle 4 Step-Indikatoren vorhanden
		for (let i = 1; i <= 4; i++) {
			await expect(page.getByTestId(`trip-wizard-step-${i}`)).toBeVisible();
		}

		// Compact-Stepper nicht sichtbar auf Desktop
		const compact = page.getByTestId('trip-wizard-stepper-compact');
		await expect(compact).not.toBeVisible();
	});

	// AC-4: BottomNav nicht sichtbar auf /trips/new (Mobile)
	test('AC-4: BottomNav ist auf /trips/new nicht sichtbar', async ({ page }) => {
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips/new');

		const bottomNav = page.getByTestId('bottom-nav');
		await expect(bottomNav).not.toBeVisible();
	});

	// AC-5: Weiter-Button Touch-Target ≥ 44 px auf Mobile
	test('AC-5: Weiter-Button hat Touch-Target-Höhe >= 44 px auf Mobile', async ({ page }) => {
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips/new');

		const nextBtn = page.getByTestId('trip-wizard-next');
		await expect(nextBtn).toBeVisible();

		const box = await nextBtn.boundingBox();
		expect(box).not.toBeNull();
		expect(box!.height).toBeGreaterThanOrEqual(44);
	});
});
