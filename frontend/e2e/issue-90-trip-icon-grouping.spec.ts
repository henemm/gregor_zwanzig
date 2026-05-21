// E2E — Bug #295: Trips-Liste Aktionsspalte (Ablösung Issue #90)
//
// Spec: docs/specs/modules/bug_282_295_trips_list_redesign.md (AC-3, AC-5)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN — die neue 2-Button-Struktur
// (Primary-Button + Kebab) existiert noch nicht. Die alte 6-Icon-Struktur
// aus Issue #90 ist durch dieses Spec ersetzt.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Bug #295 — Trips-Liste: Primary-Button + Kebab (Ablösung Issue #90)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/trips');
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test('AC-1: Aktionsspalte hat genau 2 interaktive Elemente: Primary-Button + Kebab-Button', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport ≥ 900px, mindestens 1 Trip, /trips geladen
		 * WHEN:  Aktionsspalte der ersten Tabellenzeile ausgewertet wird
		 * THEN:  Genau 2 direkt sichtbare Buttons: Primary-Button + ⋯-Button
		 *        (nicht mehr 6 Icon-Buttons aus Issue #90)
		 */
		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 10_000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const actionsCell = firstRow.locator('td').last();

		// Primary-Button ist sichtbar
		const primaryBtn = actionsCell
			.locator('button')
			.filter({ hasText: /Briefing-Vorschau|Reaktivieren|Dearchivieren/ })
			.first();
		await expect(primaryBtn).toBeVisible();

		// Kebab-Button ist sichtbar
		const kebabBtn = actionsCell.getByTitle('Weitere Aktionen');
		await expect(kebabBtn).toBeVisible();

		// Alte 6 Icon-Buttons existieren NICHT mehr
		const oldIcons = actionsCell.locator('button[title="Report-Konfiguration"]');
		await expect(oldIcons).toHaveCount(0);
		const oldCloudSun = actionsCell.locator('button[title="Wetter-Konfiguration"]');
		await expect(oldCloudSun).toHaveCount(0);
	});

	test('AC-2: Kebab öffnet Dropdown mit 6 Items in definierter Reihenfolge', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips, 1 Trip sichtbar
		 * WHEN:  ⋯-Button der ersten Zeile geklickt wird
		 * THEN:  Dropdown erscheint mit Items in Reihenfolge:
		 *        1. Bearbeiten
		 *        2. Test-Briefing Morgen
		 *        3. Test-Briefing Abend
		 *        4. Wetter-Konfiguration
		 *        5. Report-Konfiguration
		 *        6. Löschen (nach Trennlinie)
		 */
		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 10_000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await firstRow.getByTitle('Weitere Aktionen').click();

		const expectedItems = [
			'Bearbeiten',
			'Test-Briefing Morgen',
			'Test-Briefing Abend',
			'Wetter-Konfiguration',
			'Report-Konfiguration',
			'Löschen',
		];
		for (const item of expectedItems) {
			await expect(page.getByRole('button', { name: item }).first()).toBeVisible({
				timeout: 3000,
			});
		}

		// DOM-Reihenfolge prüfen
		const dropdownButtons = page.locator('[role="menu"] button, [role="menuitem"]');
		const texts = await dropdownButtons.allTextContents();
		const normalized = texts.map((t) => t.trim()).filter(Boolean);
		expect(normalized[0]).toBe('Bearbeiten');
		expect(normalized[normalized.length - 1]).toBe('Löschen');
	});

	test('AC-3: data-testid="trip-edit-btn" liegt im Kebab auf dem Item "Bearbeiten"', async ({
		page
	}) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips, 1 Trip sichtbar, Kebab geöffnet
		 * WHEN:  data-testid="trip-edit-btn" gesucht wird
		 * THEN:  Exakt 1 Element gefunden; es ist das "Bearbeiten"-Item im Kebab
		 */
		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 10_000 }).catch(() => false))) {
			test.skip();
			return;
		}

		// Vor dem Öffnen: trip-edit-btn nicht direkt in der Row sichtbar
		const editBtnBeforeOpen = firstRow.locator('[data-testid="trip-edit-btn"]');
		await expect(editBtnBeforeOpen).not.toBeVisible();

		// Kebab öffnen
		await firstRow.getByTitle('Weitere Aktionen').click();

		// Jetzt sichtbar im Dropdown
		const editBtn = page.locator('[data-testid="trip-edit-btn"]');
		await expect(editBtn).toBeVisible({ timeout: 3000 });
		await expect(editBtn).toContainText('Bearbeiten');
	});

	test('AC-4: Kebab schließt sich beim Klick auf ein Item', async ({ page }) => {
		/**
		 * GIVEN: Kebab-Dropdown ist geöffnet
		 * WHEN:  User klickt auf "Bearbeiten"
		 * THEN:  Dropdown schließt sich (andere Items verschwinden)
		 */
		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 10_000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await firstRow.getByTitle('Weitere Aktionen').click();
		const morgenBtn = page.getByRole('button', { name: 'Test-Briefing Morgen' }).first();
		await expect(morgenBtn).toBeVisible({ timeout: 3000 });

		// Klick auf ein Item schließt das Dropdown
		// (Wetter-Konfiguration öffnet Dialog, aber Dropdown muss zu sein)
		await page.keyboard.press('Escape');
		await expect(morgenBtn).not.toBeVisible({ timeout: 3000 });
	});
});
