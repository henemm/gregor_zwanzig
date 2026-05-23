// TDD RED Issue #301 Lieferung A — wird post-push gegen Staging ausgeführt.
//
// E2E — Compare Gruppen-Sidebar: Group-Entity ins Frontend verdrahtet.
// Spec: docs/specs/modules/issue_301_sidebar_groups.md (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7, AC-9)
//
// Diese Datei ist RED-by-construction: die referenzierten data-testids
// (group-section-*, ungroup-section, loc-name-*, create-group-name,
//  create-group-error, wizard-group-select, location-form-group) existieren
// im Frontend noch nicht. Wird NICHT lokal ausgeführt, sondern post-push gegen
// https://staging.gregor20.henemm.com.
//
// TestID-Inventar (laut Spec):
//   group-section-{group.id}     — eine klappbare Gruppen-Sektion
//   group-count-{group.id}       — Zähler-Badge der Gruppe
//   ungroup-section              — "Ungruppiert"-Bucket (nur wenn Orte ohne group_id)
//   loc-name-{loc.id}            — klickbarer Ortsname → Edit-Dialog
//   location-form-group          — Group-<select> im LocationForm-Edit-Dialog
//   create-group-name            — Name-Input im CreateGroupDialog
//   create-group-profile         — Profil-<select> im CreateGroupDialog
//   create-group-error           — Fehler-State (z.B. Duplikat)
//   wizard-group-select          — Group-<select> in NewLocationWizard Step 2

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #301 Lieferung A: Compare Gruppen-Sidebar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
	});

	// AC-1: Sidebar ist <aside>, Breite 320px, Gruppen aus /api/groups sortiert nach order.
	test('AC-1: Sidebar ist <aside> mit 320px Breite und Gruppen-Sektionen', async ({ page }) => {
		const sidebar = page.locator('aside');
		await expect(sidebar).toBeVisible();

		// Breite exakt 320px.
		const box = await sidebar.boundingBox();
		expect(box).not.toBeNull();
		expect(box!.width).toBe(320);

		// Mindestens eine Gruppen-Sektion (data-testid="group-section-...").
		const sections = sidebar.locator('[data-testid^="group-section-"]');
		await expect(sections.first()).toBeVisible();

		// Sektionen erscheinen nach order sortiert: top-Position monoton steigend.
		const count = await sections.count();
		let prevTop = -Infinity;
		for (let i = 0; i < count; i++) {
			const b = await sections.nth(i).boundingBox();
			expect(b).not.toBeNull();
			expect(b!.y).toBeGreaterThanOrEqual(prevTop);
			prevTop = b!.y;
		}
	});

	// AC-2: Profil-Dot trägt eine --g-profile-*-Farbe (kein Hex-Literal).
	test('AC-2: Profil-Dot nutzt --g-profile-*-Token statt Hex', async ({ page }) => {
		const sidebar = page.locator('aside');
		const dot = sidebar.locator('[data-slot="dot"]').first();
		await expect(dot).toBeVisible();

		// Inline-style trägt eine var(--g-profile-*)-Referenz (kein Hex-Literal #rrggbb).
		const styleAttr = await dot.getAttribute('style');
		expect(styleAttr).toBeTruthy();
		expect(styleAttr).toMatch(/--g-profile-/);
		expect(styleAttr).not.toMatch(/#[0-9a-fA-F]{3,6}/);
	});

	// AC-3: "Ungruppiert"-Sektion nur wenn Orte ohne Gruppe existieren.
	test('AC-3: Ungruppiert-Sektion erscheint nur bei Orten ohne Gruppe', async ({ page }) => {
		const ungroup = page.getByTestId('ungroup-section');
		const ungroupCount = await ungroup.count();
		if (ungroupCount === 0) {
			// Alle Orte gruppiert → Bucket darf nicht existieren. Test passt trivial.
			expect(ungroupCount).toBe(0);
			return;
		}
		// Bucket vorhanden → muss sichtbar und am Ende der Sidebar (nach allen Gruppen) sein.
		await expect(ungroup).toBeVisible();
		const sidebar = page.locator('aside');
		const lastGroup = sidebar.locator('[data-testid^="group-section-"]').last();
		if ((await lastGroup.count()) > 0) {
			const groupBox = await lastGroup.boundingBox();
			const ungroupBox = await ungroup.boundingBox();
			expect(ungroupBox!.y).toBeGreaterThanOrEqual(groupBox!.y);
		}
	});

	// AC-5: Klick auf Ortsnamen öffnet Edit-Dialog mit Gruppen-Select.
	test('AC-5: Klick auf Ortsname öffnet Edit-Dialog mit Gruppen-Select', async ({ page }) => {
		const sidebar = page.locator('aside');
		const locName = sidebar.locator('[data-testid^="loc-name-"]').first();
		await expect(locName).toBeVisible();
		await locName.click();

		// Edit-Dialog mit LocationForm öffnet sich.
		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();

		// Group-Select sichtbar und ein <select>.
		const groupSelect = page.getByTestId('location-form-group');
		await expect(groupSelect).toBeVisible();
		expect(await groupSelect.evaluate((el) => el.tagName.toLowerCase())).toBe('select');
	});

	// AC-6: "+ Gruppe" öffnet CreateGroupDialog; POST legt Gruppe an; Duplikat → Fehler.
	test('AC-6: "+ Gruppe" legt neue Gruppe an; Duplikat zeigt Fehler', async ({ page }) => {
		const sidebar = page.locator('aside');
		await sidebar.getByRole('button', { name: /\+ Gruppe/i }).click();

		const nameInput = page.getByTestId('create-group-name');
		await expect(nameInput).toBeVisible();

		const uniqueName = `E2E Gruppe ${Date.now()}`;
		await nameInput.fill(uniqueName);
		await page.getByRole('button', { name: /Anlegen|Erstellen|Speichern/i }).click();

		// Dialog geschlossen, Gruppe erscheint in der Sidebar.
		await expect(sidebar).toContainText(uniqueName);

		// Zweites Anlegen mit demselben Namen (gleiche kebab-ID) → Fehler-State.
		await sidebar.getByRole('button', { name: /\+ Gruppe/i }).click();
		await page.getByTestId('create-group-name').fill(uniqueName);
		await page.getByRole('button', { name: /Anlegen|Erstellen|Speichern/i }).click();
		await expect(page.getByTestId('create-group-error')).toBeVisible();
	});

	// AC-7: NewLocationWizard Step 2 hat Gruppen-<select>; Anlegen ordnet in Gruppe ein.
	test('AC-7: NewLocationWizard Step 2 Gruppen-Select ordnet Ort in Gruppe ein', async ({
		page
	}) => {
		const uniqueName = `Wizard-Ort ${Date.now()}`;

		// Wizard öffnen (bestehender "+ NEU"-Button).
		await page.getByTestId('compare-rail-new-btn').click();
		await expect(page.getByTestId('location-wizard')).toBeVisible();

		// Step 1: Koordinaten.
		await page.getByTestId('location-wizard-lat').fill('47.3');
		await page.getByTestId('location-wizard-lon').fill('11.4');
		await page.getByTestId('location-wizard-next').click();

		// Step 2: Name + Gruppen-Select.
		await page.getByTestId('location-wizard-name').fill(uniqueName);
		const groupSelect = page.getByTestId('wizard-group-select');
		await expect(groupSelect).toBeVisible();
		expect(await groupSelect.evaluate((el) => el.tagName.toLowerCase())).toBe('select');

		// Erste echte Gruppe (Option-Wert != '') auswählen.
		const groupValue = await groupSelect
			.locator('option')
			.nth(1)
			.getAttribute('value');
		expect(groupValue).toBeTruthy();
		await groupSelect.selectOption(groupValue!);
		await page.getByTestId('location-wizard-next').click();

		// Step 3: Speichern.
		await page.getByTestId('location-wizard-save').click();
		await expect(page.getByTestId('location-wizard')).not.toBeVisible();

		// Ort erscheint in der Sektion der gewählten Gruppe.
		const section = page.getByTestId(`group-section-${groupValue}`);
		await expect(section).toContainText(uniqueName);
	});

	// AC-9: Alle Gruppen initial aufgeklappt; Header-Klick klappt ein/aus.
	test('AC-9: Gruppen initial aufgeklappt, Header-Klick toggelt', async ({ page }) => {
		const sidebar = page.locator('aside');
		const section = sidebar.locator('[data-testid^="group-section-"]').first();
		await expect(section).toBeVisible();

		// Initial aufgeklappt: Ortsliste sichtbar (mindestens ein loc-name oder Header aria-expanded=true).
		const header = section.getByRole('button').first();
		await expect(header).toHaveAttribute('aria-expanded', 'true');

		const locNames = section.locator('[data-testid^="loc-name-"]');
		const hasLocs = (await locNames.count()) > 0;
		if (hasLocs) {
			await expect(locNames.first()).toBeVisible();
		}

		// Einklappen.
		await header.click();
		await expect(header).toHaveAttribute('aria-expanded', 'false');
		if (hasLocs) {
			await expect(locNames.first()).not.toBeVisible();
		}

		// Wieder ausklappen.
		await header.click();
		await expect(header).toHaveAttribute('aria-expanded', 'true');
		if (hasLocs) {
			await expect(locNames.first()).toBeVisible();
		}
	});
});
