// E2E — Issue #132: Compare-Screen Aktivitätsprofil-Integration
//
// Spec: docs/specs/modules/issue_132_compare_activity_profiles.md (AC-1 bis AC-9)
//
// TestID-Inventar (zu implementieren in LocationsRail.svelte):
//   compare-rail-profile-chip   — Profil-Chip-Button (aria-label=Profilname)
//
// Ausführen: cd frontend && npx playwright test e2e/compare-activity-profiles.spec.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Compare: Aktivitätsprofil-Integration (#132)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		await login(page);
		await page.goto('/compare');
	});

	// AC-1: Profile-Badge sichtbar fuer Nicht-allgemein-Location.
	// Erwartung: Span mit title="Wintersport" erscheint neben dem Location-Namen.
	// Wird FAIL bis LocationsRail.svelte das Badge rendert.
	test('AC-1: Wintersport-Badge mit title-Attribut sichtbar', async ({ page }) => {
		const badge = page.locator('[title="Wintersport"]').first();
		await expect(badge).toBeVisible();
	});

	// AC-2: Kein Badge fuer "allgemein" oder Locations ohne Profil.
	// Erwartung: Locations ohne explizites Nicht-allgemein-Profil zeigen kein Badge.
	// Wir verifizieren, dass der Badge-Selektor mit title="Allgemein" nicht existiert.
	test('AC-2: Kein Profile-Badge fuer allgemein/undefined Locations', async ({ page }) => {
		// Profile-Badges erscheinen NIE fuer 'allgemein' (Spec §4).
		const allgemeinBadges = page.locator('[title="Allgemein"]');
		await expect(allgemeinBadges).toHaveCount(0);
	});

	// AC-3: Profil-Chip-Filter erscheint nur, wenn passende Profile vorhanden.
	// TDD-RED-Variante: Wir assert-en, dass mindestens EIN Chip im DOM existiert
	// (Test-Daten enthalten Locations mit profilen). Wird FAIL bis Chips gerendert sind.
	test('AC-3: Profil-Chip ist vorhanden wenn Profile in Locations existieren', async ({ page }) => {
		const chips = page.getByTestId('compare-rail-profile-chip');
		await expect(chips.first()).toBeVisible();

		// Wenn Chips erscheinen, muessen sie aria-pressed haben (Toggle-State).
		const ariaPressed = await chips.first().getAttribute('aria-pressed');
		expect(ariaPressed).not.toBeNull();
	});

	// AC-4: Wintersport-Chip-Klick filtert Liste auf nur Wintersport-Locations.
	// Wird FAIL bis compare-rail-profile-chip existiert + Filter greift.
	test('AC-4: Profil-Chip "Wintersport" filtert auf Wintersport-Locations', async ({ page }) => {
		// Anzahl sichtbarer Location-Checkboxen vor Filter erfassen.
		const allCheckboxes = page.locator('[data-testid="compare-rail"] input[type="checkbox"]');
		const totalBefore = await allCheckboxes.count();
		expect(totalBefore).toBeGreaterThan(0);

		// Wintersport-Chip klicken.
		const chip = page.locator('[data-testid="compare-rail-profile-chip"][aria-label="Wintersport"]');
		await expect(chip).toBeVisible();
		await chip.click();

		// Nach Filter weniger Locations sichtbar.
		const totalAfter = await allCheckboxes.count();
		expect(totalAfter).toBeLessThan(totalBefore);
		expect(totalAfter).toBeGreaterThan(0);

		// aria-pressed sollte true sein.
		await expect(chip).toHaveAttribute('aria-pressed', 'true');
	});

	// AC-5: Zweiter Klick auf den aktiven Chip hebt Filter auf (Toggle).
	test('AC-5: Profil-Chip zweiter Klick hebt Filter auf', async ({ page }) => {
		const allCheckboxes = page.locator('[data-testid="compare-rail"] input[type="checkbox"]');
		const totalBefore = await allCheckboxes.count();

		const chip = page.locator('[data-testid="compare-rail-profile-chip"][aria-label="Wintersport"]');
		await expect(chip).toBeVisible();

		// Erster Klick: Filter aktiv.
		await chip.click();
		await expect(chip).toHaveAttribute('aria-pressed', 'true');
		const totalFiltered = await allCheckboxes.count();
		expect(totalFiltered).toBeLessThan(totalBefore);

		// Zweiter Klick: Filter aufgehoben, Count zurueck auf Original.
		await chip.click();
		await expect(chip).toHaveAttribute('aria-pressed', 'false');
		const totalAfter = await allCheckboxes.count();
		expect(totalAfter).toBe(totalBefore);
	});

	// AC-6: Auto-Profil-Vorauswahl bei Mehrheit >50% Wintersport.
	// Wird FAIL bis dominantProfile-Derived + $effect implementiert sind.
	test('AC-6: Mehrheit Wintersport setzt Profil-Dropdown automatisch', async ({ page }) => {
		const profileSelect = page.getByTestId('compare-preset-profile-select');
		await expect(profileSelect).toBeVisible();

		// Schritt 1: Alle Locations deselektieren.
		const checkboxes = page.locator('[data-testid="compare-rail"] input[type="checkbox"]');
		const total = await checkboxes.count();
		for (let i = 0; i < total; i++) {
			const cb = checkboxes.nth(i);
			if (await cb.isChecked()) {
				await cb.uncheck();
			}
		}

		// Schritt 2: Mittels Profil-Chip nur Wintersport-Locations einblenden, dann alle selektieren.
		const winterChip = page.locator(
			'[data-testid="compare-rail-profile-chip"][aria-label="Wintersport"]'
		);
		await winterChip.click();
		await expect(winterChip).toHaveAttribute('aria-pressed', 'true');

		// Sichtbare (gefilterte) Wintersport-Checkboxen alle aktivieren.
		const winterCheckboxes = page.locator(
			'[data-testid="compare-rail"] input[type="checkbox"]'
		);
		const winterCount = await winterCheckboxes.count();
		expect(winterCount).toBeGreaterThan(0);
		for (let i = 0; i < winterCount; i++) {
			const cb = winterCheckboxes.nth(i);
			if (!(await cb.isChecked())) {
				await cb.check();
			}
		}

		// Filter wieder loesen — Auswahl bleibt, dominantProfile sollte 100% wintersport sein.
		await winterChip.click();

		// AC-6: Profil-Dropdown muss auf "wintersport" stehen.
		await expect(profileSelect).toHaveValue('wintersport');
	});

	// AC-8: Manuelles Override bleibt bestehen.
	// Wird FAIL bis profileManuallyOverridden + onprofilechange-Callback implementiert sind.
	test('AC-8: Manueller Dropdown-Change ueberschreibt Auto-Select', async ({ page }) => {
		const profileSelect = page.getByTestId('compare-preset-profile-select');
		await expect(profileSelect).toBeVisible();

		// Schritt 1: Auto-Select aktivieren — alle Wintersport selektieren.
		const checkboxes = page.locator('[data-testid="compare-rail"] input[type="checkbox"]');
		const total = await checkboxes.count();
		for (let i = 0; i < total; i++) {
			const cb = checkboxes.nth(i);
			if (await cb.isChecked()) {
				await cb.uncheck();
			}
		}
		const winterChip = page.locator(
			'[data-testid="compare-rail-profile-chip"][aria-label="Wintersport"]'
		);
		await winterChip.click();
		const winterCheckboxes = page.locator(
			'[data-testid="compare-rail"] input[type="checkbox"]'
		);
		const winterCount = await winterCheckboxes.count();
		for (let i = 0; i < winterCount; i++) {
			const cb = winterCheckboxes.nth(i);
			if (!(await cb.isChecked())) await cb.check();
		}
		await winterChip.click();
		await expect(profileSelect).toHaveValue('wintersport');

		// Schritt 2: Manuell auf "allgemein" wechseln.
		await profileSelect.selectOption('allgemein');
		await expect(profileSelect).toHaveValue('allgemein');

		// Schritt 3: Auch nach kurzem Warten bleibt "allgemein" — Auto-Logik darf
		// nicht ohne Auswahl-Aenderung zurueckspringen.
		await page.waitForTimeout(500);
		await expect(profileSelect).toHaveValue('allgemein');
	});
});
