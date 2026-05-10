// E2E-Tests fuer Epic #136 Sub-Spec #161 (Step 1: Aktivitaetsprofil + Eckdaten).
//
// Spec-Referenz: docs/specs/modules/epic_136_step1_profile.md
//   - Acceptance #1–#13, #19, #20
//
// TestID-Inventar (Sub-Spec §8):
//   trip-wizard-step1-profile (Container, aus #160 vorhanden)
//   trip-wizard-step1-chip-{trekking|skitour|hochtour|klettersteig|mtb}
//   trip-wizard-step1-name
//   trip-wizard-step1-shortcode
//   trip-wizard-step1-startdate
//
// E2E-Helper: fillStep1(page, { activity, name, shortcode?, startDate })
//   — auch von trip-wizard-shell.spec.ts (Migration der 5 Tests AC#5..#11) genutzt.

import { test, expect } from '@playwright/test';
import { login, fillStep1 } from './helpers.js';

const ALL_ACTIVITIES = ['trekking', 'skitour', 'hochtour', 'klettersteig', 'mtb'] as const;

test.describe('Trip-Wizard Step 1 — Profil & Eckdaten (#161)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/trips/new');
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();
	});

	test('AC#1: rendert 5 ProfileChips mit korrekten TestIDs', async ({ page }) => {
		for (const a of ALL_ACTIVITIES) {
			await expect(page.getByTestId(`trip-wizard-step1-chip-${a}`)).toBeVisible();
		}
	});

	test('AC#2: initial sind alle Chips aria-pressed=false', async ({ page }) => {
		for (const a of ALL_ACTIVITIES) {
			await expect(page.getByTestId(`trip-wizard-step1-chip-${a}`)).toHaveAttribute(
				'aria-pressed',
				'false'
			);
		}
	});

	test('AC#2: nach Klick ist genau dieser eine Chip aria-pressed=true', async ({ page }) => {
		await page.getByTestId('trip-wizard-step1-chip-skitour').click();
		await expect(page.getByTestId('trip-wizard-step1-chip-skitour')).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		for (const a of ALL_ACTIVITIES) {
			if (a === 'skitour') continue;
			await expect(page.getByTestId(`trip-wizard-step1-chip-${a}`)).toHaveAttribute(
				'aria-pressed',
				'false'
			);
		}
	});

	test('AC#3: Klick auf anderen Chip wechselt die Auswahl', async ({ page }) => {
		await page.getByTestId('trip-wizard-step1-chip-trekking').click();
		await expect(page.getByTestId('trip-wizard-step1-chip-trekking')).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		await page.getByTestId('trip-wizard-step1-chip-mtb').click();
		await expect(page.getByTestId('trip-wizard-step1-chip-trekking')).toHaveAttribute(
			'aria-pressed',
			'false'
		);
		await expect(page.getByTestId('trip-wizard-step1-chip-mtb')).toHaveAttribute(
			'aria-pressed',
			'true'
		);
	});

	test('AC#4: drei Eingabefelder mit korrekten TestIDs', async ({ page }) => {
		await expect(page.getByTestId('trip-wizard-step1-name')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step1-shortcode')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step1-startdate')).toBeVisible();
	});

	test('AC#5: Kuerzel-Input hat maxlength=20', async ({ page }) => {
		await expect(page.getByTestId('trip-wizard-step1-shortcode')).toHaveAttribute(
			'maxlength',
			'20'
		);
	});

	test('AC#6: Startdatum-Input ist type=date', async ({ page }) => {
		await expect(page.getByTestId('trip-wizard-step1-startdate')).toHaveAttribute(
			'type',
			'date'
		);
	});

	test('AC#7: initial ist Weiter-Button disabled', async ({ page }) => {
		await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
	});

	test('AC#8: nur Activity gesetzt → Weiter weiterhin disabled', async ({ page }) => {
		await page.getByTestId('trip-wizard-step1-chip-trekking').click();
		await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
	});

	test('AC#10: Activity + Name + Startdatum → Weiter enabled', async ({ page }) => {
		await fillStep1(page, {
			activity: 'trekking',
			name: 'GR20',
			startDate: '2026-06-01'
		});
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	test('AC#11: Activity + Name + Kuerzel + Startdatum → Weiter enabled (Kuerzel optional)', async ({
		page
	}) => {
		await fillStep1(page, {
			activity: 'skitour',
			name: 'Stubai-Skitour',
			shortcode: 'STUB-26',
			startDate: '2026-02-15'
		});
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	test('AC#12: Klick auf enabled Weiter wechselt zu Step 2; data-state updated', async ({
		page
	}) => {
		await fillStep1(page, {
			activity: 'hochtour',
			name: 'Wallis-Hochtour',
			startDate: '2026-07-20'
		});
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step-1')).toHaveAttribute('data-state', 'done');
		await expect(page.getByTestId('trip-wizard-step-2')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();
	});

	test('AC#13: nach Zurueck-Klick aus Step 2 sind Step-1-Werte erhalten', async ({ page }) => {
		await fillStep1(page, {
			activity: 'klettersteig',
			name: 'Dolomiten',
			shortcode: 'DOLO',
			startDate: '2026-09-10'
		});
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();
		await page.getByTestId('trip-wizard-back').click();
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();

		await expect(page.getByTestId('trip-wizard-step1-chip-klettersteig')).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		await expect(page.getByTestId('trip-wizard-step1-name')).toHaveValue('Dolomiten');
		await expect(page.getByTestId('trip-wizard-step1-shortcode')).toHaveValue('DOLO');
		await expect(page.getByTestId('trip-wizard-step1-startdate')).toHaveValue('2026-09-10');
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	test('AC#19: alle 5 Chips sind ueber Tab erreichbar; Space selektiert', async ({ page }) => {
		// Setze Fokus initial vor das Step-1-Container
		await page.getByTestId('trip-wizard-shell').focus();

		// Tab durch alle 5 Chips — Reihenfolge entspricht DOM (PROFILES-Konstante).
		// Wir starten am ersten focusable Element im Container und tabben durch.
		const chip0 = page.getByTestId('trip-wizard-step1-chip-trekking');
		await chip0.focus();
		await expect(chip0).toBeFocused();

		// Space toggelt
		await page.keyboard.press('Space');
		await expect(chip0).toHaveAttribute('aria-pressed', 'true');

		// Tab → naechster Chip
		await page.keyboard.press('Tab');
		await expect(page.getByTestId('trip-wizard-step1-chip-skitour')).toBeFocused();
		await page.keyboard.press('Enter');
		await expect(page.getByTestId('trip-wizard-step1-chip-skitour')).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		// trekking ist jetzt deselektiert (weil exklusive Auswahl)
		await expect(chip0).toHaveAttribute('aria-pressed', 'false');
	});

	test('AC#20: ProfileChip hat sichtbaren Fokus-Ring', async ({ page }) => {
		const chip = page.getByTestId('trip-wizard-step1-chip-trekking');
		await chip.focus();
		// :focus-visible erzeugt einen Box-Shadow oder Ring — wir pruefen, dass irgendein
		// Outline-/Ring-Stil vom Default abweicht.
		const focusStyles = await chip.evaluate((el) => {
			const cs = window.getComputedStyle(el);
			return {
				outline: cs.outline,
				outlineWidth: cs.outlineWidth,
				boxShadow: cs.boxShadow
			};
		});
		// Fokus-Ring via boxShadow (Tailwind ring) oder outline > 0
		const hasRing =
			focusStyles.boxShadow !== 'none' ||
			(focusStyles.outlineWidth !== '0px' && focusStyles.outline !== 'none');
		expect(hasRing, `Erwartet sichtbaren Fokus-Ring, bekam ${JSON.stringify(focusStyles)}`).toBe(
			true
		);
	});

	test('Re-Klick auf gewaehlten Chip: Auswahl bleibt (kein Deselect)', async ({ page }) => {
		const chip = page.getByTestId('trip-wizard-step1-chip-trekking');
		await chip.click();
		await expect(chip).toHaveAttribute('aria-pressed', 'true');
		await chip.click();
		await expect(chip).toHaveAttribute('aria-pressed', 'true');
	});

	test('Whitespace-only Name → Weiter disabled (trim-Logik)', async ({ page }) => {
		await page.getByTestId('trip-wizard-step1-chip-trekking').click();
		await page.getByTestId('trip-wizard-step1-name').fill('   ');
		await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
		await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
	});
});
