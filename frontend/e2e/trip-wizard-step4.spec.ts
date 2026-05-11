// E2E-Tests fuer Epic #136 Sub-Spec #164 (Step 4: Briefings & Kanaele).
//
// Spec-Referenz: docs/specs/modules/epic_136_step4_briefings.md
// Issue: #164
//
// TestID-Inventar (Sub-Spec §9):
//   trip-wizard-step4-container
//   trip-wizard-step4-channels-list
//   trip-wizard-step4-channel-email
//   trip-wizard-step4-channel-signal
//   trip-wizard-step4-channel-telegram
//   trip-wizard-step4-channel-sms        (disabled)
//   trip-wizard-step4-channel-sms-hint
//   trip-wizard-step4-reports-list
//   trip-wizard-step4-report-morning-toggle
//   trip-wizard-step4-report-morning-time
//   trip-wizard-step4-report-evening-toggle
//   trip-wizard-step4-report-evening-time
//   trip-wizard-step4-thresholds-list
//   trip-wizard-step4-threshold-gust
//   trip-wizard-step4-threshold-precip
//   trip-wizard-step4-threshold-thunder  (select)
//   trip-wizard-step4-threshold-snow
//
// RED-Phase: Step4Briefings.svelte ist heute ein Stub mit TestID
// `trip-wizard-step4-briefings` (alt). Alle Tests scheitern wie erwartet,
// weil die Implementierung von Toggles/Inputs/Selects noch nicht existiert.

import { test, expect, type Page } from '@playwright/test';
import { login, fillStep1, fillStep2, fillStep3, type Step1Input } from './helpers.js';

const DEFAULT_STEP1: Step1Input = {
	activity: 'trekking',
	name: 'Step4-Test',
	startDate: '2026-06-01'
};

/**
 * Navigiert vom Wizard-Start ueber Step 1, 2, 3 zu Step 4.
 * Default: 1 Etappe aus test-trip.gpx, alle Waypoints unbestaetigt (suggested).
 */
async function gotoStep4(page: Page) {
	await page.goto('/trips/new');
	await fillStep1(page, DEFAULT_STEP1);
	await page.getByTestId('trip-wizard-next').click();
	await fillStep2(page);
	await page.getByTestId('trip-wizard-next').click();
	await fillStep3(page);
	// fillStep3 klickt selbst trip-wizard-next.
	await expect(page.getByTestId('trip-wizard-step4-container')).toBeVisible();
}

test.describe('Trip-Wizard Step 4 — Briefings & Kanaele (#164)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC#1: Step4-Container mit TestID trip-wizard-step4-container ist sichtbar', async ({
		page
	}) => {
		await gotoStep4(page);
		await expect(page.getByTestId('trip-wizard-step4-container')).toBeVisible();
	});

	test('AC#2: 4 Channel-Toggles sind vorhanden (email, signal, telegram, sms)', async ({
		page
	}) => {
		await gotoStep4(page);
		await expect(page.getByTestId('trip-wizard-step4-channels-list')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-channel-email')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-channel-signal')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-channel-telegram')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-channel-sms')).toBeVisible();
	});

	test('AC#5: SMS-Toggle ist disabled (Attribut bzw. property)', async ({ page }) => {
		await gotoStep4(page);
		// Wir suchen den nativen <input type="checkbox"> innerhalb des SMS-Toggle-Containers.
		const smsInput = page
			.getByTestId('trip-wizard-step4-channel-sms')
			.locator('input[type="checkbox"]');
		await expect(smsInput).toBeDisabled();
	});

	test('AC#6: SMS-Hint trip-wizard-step4-channel-sms-hint zeigt Hinweis-Text', async ({
		page
	}) => {
		await gotoStep4(page);
		const hint = page.getByTestId('trip-wizard-step4-channel-sms-hint');
		await expect(hint).toBeVisible();
		const text = (await hint.textContent()) ?? '';
		// Spec §7: "demnaechst verfuegbar" — wir akzeptieren das Wort "demnaechst"
		// (case-insensitive, Umlaut-tolerant).
		expect(text.toLowerCase()).toMatch(/demn(ae|ä)chst/);
	});

	test('AC#7+#8: 2 Report-Rows mit Toggle und Time-Input vorhanden', async ({ page }) => {
		await gotoStep4(page);
		await expect(page.getByTestId('trip-wizard-step4-reports-list')).toBeVisible();
		// Morning
		await expect(page.getByTestId('trip-wizard-step4-report-morning-toggle')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-report-morning-time')).toBeVisible();
		// Evening
		await expect(page.getByTestId('trip-wizard-step4-report-evening-toggle')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-report-evening-time')).toBeVisible();
	});

	test('AC#9: 4 Threshold-Inputs sind vorhanden (gust, precip, thunder, snow)', async ({
		page
	}) => {
		await gotoStep4(page);
		await expect(page.getByTestId('trip-wizard-step4-thresholds-list')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-threshold-gust')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-threshold-precip')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-threshold-thunder')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step4-threshold-snow')).toBeVisible();
	});

	test('AC#10: Thunder-Input ist ein <select> mit Optionen NONE/MED/HIGH', async ({ page }) => {
		await gotoStep4(page);
		const thunder = page.getByTestId('trip-wizard-step4-threshold-thunder');
		await expect(thunder).toBeVisible();
		// Tag-Name pruefen
		const tagName = await thunder.evaluate((el) => el.tagName.toLowerCase());
		expect(tagName).toBe('select');
		// Optionen sammeln (value-Attribute)
		const values = await thunder.evaluate((el) => {
			const sel = el as HTMLSelectElement;
			return Array.from(sel.options).map((o) => o.value);
		});
		expect(values).toContain('NONE');
		expect(values).toContain('MED');
		expect(values).toContain('HIGH');
	});

	test('AC#11: Save-Button ist sichtbar und enabled in Step 4', async ({ page }) => {
		await gotoStep4(page);
		const save = page.getByTestId('trip-wizard-save');
		await expect(save).toBeVisible();
		await expect(save).toBeEnabled();
	});

	test('AC#12: Klick auf email-Toggle deselektiert ihn', async ({ page }) => {
		await gotoStep4(page);
		const emailInput = page
			.getByTestId('trip-wizard-step4-channel-email')
			.locator('input[type="checkbox"]');
		// Initial: aktiviert (defaultBriefingConfig.channels.email = true).
		await expect(emailInput).toBeChecked();
		await emailInput.click();
		await expect(emailInput).not.toBeChecked();
	});
});
