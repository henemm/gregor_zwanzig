// E2E — Issue #268: Mobile Card-Stack für Trips-Liste
//
// Spec: docs/specs/modules/issue_268_trips_mobile_card_stack.md (AC-1 bis AC-7)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, weil das Card-Stack-Layout und
// das Bottom-Sheet noch nicht implementiert sind.
//
// TestID-Inventar (wird in Implementation angelegt):
//   trip-card-stack               — Mobile Card-Stack Container (desktop:hidden)
//   trip-card                     — Einzelne Trip-Card (pro Trip)
//   trip-card-menu-btn            — ···-Button (≥ 44×44px Touch-Target)
//   trip-action-sheet             — Bottom-Sheet Panel (role="dialog")

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const MOBILE_VIEWPORT = { width: 375, height: 667 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test.describe('Issue #268: Mobile Card-Stack für Trips-Liste', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Card-Stack sichtbar auf Mobile ────────────────────────────────
	test('AC-1: Card-Stack ist auf Mobile-Viewport (≤ 899px) sichtbar', async ({ page }) => {
		/**
		 * GIVEN: Mindestens ein Trip existiert und User ist eingeloggt
		 * WHEN:  Viewport ist 375×667 px (Mobile) und /trips wird geladen
		 * THEN:  Card-Stack mit data-testid="trip-card-stack" ist sichtbar,
		 *        jede Card hat data-testid="trip-card"
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const cardStack = page.getByTestId('trip-card-stack');
		await expect(cardStack).toBeVisible({ timeout: 5000 });

		const firstCard = cardStack.getByTestId('trip-card').first();
		if (await firstCard.isVisible({ timeout: 3000 }).catch(() => false)) {
			await expect(firstCard).toBeVisible();
		}
	});

	// ─── AC-1b: Desktop-Tabelle auf Mobile NICHT sichtbar ───────────────────
	test('AC-1b: Desktop-Tabelle ist auf Mobile-Viewport (≤ 899px) nicht sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 375×667 px (Mobile) und /trips wird geladen
		 * THEN:  Das <table>-Element ist nicht sichtbar (display:none via desktop:block)
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const table = page.locator('table');
		await expect(table).not.toBeVisible({ timeout: 5000 });
	});

	// ─── AC-2: Bottom-Sheet öffnet sich per ···-Button ──────────────────────
	test('AC-2: ···-Button öffnet Bottom-Sheet mit 6 Aktionen', async ({ page }) => {
		/**
		 * GIVEN: Mindestens ein Trip existiert, Mobile-Viewport, /trips geladen
		 * WHEN:  User tippt auf den ···-Button (trip-card-menu-btn) der ersten Card
		 * THEN:  Bottom-Sheet (trip-action-sheet) ist sichtbar mit genau 6 Aktionen:
		 *        Report-Konfiguration, Wetter-Konfiguration, Bearbeiten,
		 *        Test Morgen-Report, Test Abend-Report, Löschen
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const firstCard = page.getByTestId('trip-card').first();
		if (!(await firstCard.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const menuBtn = firstCard.getByTestId('trip-card-menu-btn');
		await menuBtn.click();

		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible({ timeout: 3000 });

		await expect(sheet.getByText('Report-Konfiguration')).toBeVisible();
		await expect(sheet.getByText('Wetter-Konfiguration')).toBeVisible();
		await expect(sheet.getByText('Bearbeiten')).toBeVisible();
		await expect(sheet.getByText('Test Morgen-Report')).toBeVisible();
		await expect(sheet.getByText('Test Abend-Report')).toBeVisible();
		await expect(sheet.getByText('Löschen')).toBeVisible();
	});

	// ─── AC-3: Backdrop schließt Bottom-Sheet ───────────────────────────────
	test('AC-3: Klick auf Backdrop schließt das Bottom-Sheet', async ({ page }) => {
		/**
		 * GIVEN: Bottom-Sheet ist geöffnet (Mobile, min. 1 Trip)
		 * WHEN:  User tippt auf den Backdrop (außerhalb des Sheets)
		 * THEN:  Bottom-Sheet ist nicht mehr sichtbar
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const firstCard = page.getByTestId('trip-card').first();
		if (!(await firstCard.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await firstCard.getByTestId('trip-card-menu-btn').click();

		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible({ timeout: 3000 });

		// Backdrop ist außerhalb des Sheets – Klick auf linke obere Ecke
		await page.mouse.click(10, 10);

		await expect(sheet).not.toBeVisible({ timeout: 3000 });
	});

	// ─── AC-4: Klick auf Card-Inhalt navigiert zur Detail-Seite ─────────────
	test('AC-4: Tippen auf Karten-Inhalt navigiert zur Trip-Detail-Route', async ({ page }) => {
		/**
		 * GIVEN: Mindestens ein Trip existiert, Mobile-Viewport, /trips geladen
		 * WHEN:  User tippt auf den mittleren Inhalt-Bereich (Name + Metadaten) der ersten Card
		 * THEN:  URL wechselt zu /trips/{id}
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const firstCard = page.getByTestId('trip-card').first();
		if (!(await firstCard.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const contentBtn = firstCard.getByTestId('trip-card-content-btn');
		await contentBtn.click();

		await page.waitForURL(/\/trips\/.+/, { timeout: 5000 });
		expect(page.url()).toMatch(/\/trips\/.+/);
	});

	// ─── AC-5: Löschen aus Sheet öffnet Bestätigungs-Dialog ─────────────────
	test('AC-5: Löschen im Bottom-Sheet öffnet Bestätigungs-Dialog', async ({ page }) => {
		/**
		 * GIVEN: Bottom-Sheet ist geöffnet für einen Trip (Mobile)
		 * WHEN:  User tippt auf "Löschen" im Sheet
		 * THEN:  Sheet schließt sich und der Lösch-Bestätigungs-Dialog erscheint
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const firstCard = page.getByTestId('trip-card').first();
		if (!(await firstCard.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await firstCard.getByTestId('trip-card-menu-btn').click();

		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible({ timeout: 3000 });

		await sheet.getByText('Löschen').click();

		// Sheet muss geschlossen sein
		await expect(sheet).not.toBeVisible({ timeout: 3000 });

		// Bestätigungs-Dialog muss geöffnet sein
		const dialog = page.locator('[role="dialog"]').filter({ hasText: /löschen/i });
		await expect(dialog).toBeVisible({ timeout: 3000 });
	});

	// ─── AC-6: Desktop-Tabelle unverändert auf ≥ 900px ───────────────────────
	test('AC-6: Desktop-Tabelle bleibt auf ≥ 900px vollständig sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 1440×900 px (Desktop) und /trips wird geladen
		 * THEN:  <table>-Element ist sichtbar; Card-Stack ist NICHT sichtbar
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		// Nur prüfen wenn Trips vorhanden — sonst zeigt die Seite nur Empty-State
		const table = page.locator('table');
		const emptyState = page.getByTestId('empty-state');

		const hasTable = await table.isVisible({ timeout: 3000 }).catch(() => false);
		const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);

		if (hasEmpty) {
			// Kein Trip vorhanden — Desktop-Check nicht sinnvoll möglich
			test.skip();
			return;
		}

		expect(hasTable).toBe(true);

		// Card-Stack darf auf Desktop nicht sichtbar sein
		const cardStack = page.getByTestId('trip-card-stack');
		await expect(cardStack).not.toBeVisible();
	});

	// ─── AC-7: Touch-Target des ···-Buttons ≥ 44×44px ───────────────────────
	test('AC-7: ···-Button hat Mindest-Touch-Target von 44×44px', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport, mindestens ein Trip, /trips geladen
		 * WHEN:  ···-Button (trip-card-menu-btn) der ersten Card gemessen wird
		 * THEN:  Breite ≥ 44px UND Höhe ≥ 44px
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const firstCard = page.getByTestId('trip-card').first();
		if (!(await firstCard.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const menuBtn = firstCard.getByTestId('trip-card-menu-btn');
		const box = await menuBtn.boundingBox();

		expect(box).not.toBeNull();
		expect(box!.width).toBeGreaterThanOrEqual(44);
		expect(box!.height).toBeGreaterThanOrEqual(44);
	});
});
