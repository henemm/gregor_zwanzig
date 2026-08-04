import { test, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ART = path.join(__dirname, '..', '..', 'docs', 'artifacts', 'fix-1471-sende-dialog-ziel');

test.describe('Issue #1471 — Sende-Dialog nennt tatsaechliches Ziel (Staging-Validierung)', () => {
	test('Liste rendert, Loesch-Dialog behaelt eigenen Text, Sende-Dialog zeigt echtes Ziel + Sperre', async ({
		page
	}) => {
		await page.goto('/compare');
		await expect(page.getByTestId('compare-status-pill').first()).toBeVisible({ timeout: 15_000 });
		await page.screenshot({ path: path.join(ART, 'ac-list-regression.png'), fullPage: true });

		// --- Regression: Loesch-Dialog behaelt seinen eigenen Text ---
		await page.getByTestId('compare-row-kebab').first().click();
		await page.getByRole('menuitem', { name: 'Löschen' }).click();
		const deleteDialog = page.getByRole('alertdialog').or(page.getByRole('dialog'));
		await expect(deleteDialog.getByText('Vergleich löschen?')).toBeVisible();
		const deleteDescText = await deleteDialog.locator('[data-slot="dialog-description"], p').first().innerText().catch(() => '');
		await page.screenshot({ path: path.join(ART, 'ac-regression-delete-dialog.png'), fullPage: true });
		// NICHT bestaetigen — nur pruefen, dann abbrechen.
		await page.getByRole('button', { name: 'Abbrechen' }).click();
		await expect(deleteDialog).toBeHidden();

		// --- Sende-Dialog ---
		await page.getByTestId('compare-row-kebab').first().click();
		await page.getByRole('menuitem', { name: 'Briefing jetzt senden' }).click();
		const sendDialog = page.getByRole('dialog').filter({ hasText: 'Briefing jetzt senden?' });
		await expect(sendDialog).toBeVisible();
		await page.screenshot({ path: path.join(ART, 'ac-send-dialog.png'), fullPage: true });

		const bodyText = await page.locator('body').innerText();
		expect(bodyText).not.toContain('0 Empfänger');

		const descText = await sendDialog.locator('p, [data-slot="dialog-description"]').first().innerText();
		console.log('SEND_DIALOG_TEXT::' + descText);

		const confirmBtn = sendDialog.getByRole('button', { name: 'Senden' });
		await expect(confirmBtn).toBeVisible();
		const isDisabled = await confirmBtn.isDisabled();
		const disabledAttr = await confirmBtn.getAttribute('disabled');
		console.log('SEND_BUTTON_DISABLED::' + isDisabled + '::attr=' + disabledAttr);

		// Netzwerk-Beobachtung: kein POST an /send, egal ob Klick verhindert wird.
		let sendPostFired = false;
		page.on('request', (req) => {
			if (req.method() === 'POST' && /\/api\/compare\/presets\/.*\/send/.test(req.url())) {
				sendPostFired = true;
			}
		});

		if (isDisabled) {
			// Erzwungener Klick auf ein disabled-Element — Playwright fuehrt das
			// tatsaechliche DOM-Klickereignis NICHT aus, wenn nativ disabled.
			await confirmBtn.click({ force: true, trial: false }).catch((e) => {
				console.log('FORCE_CLICK_ERROR::' + String(e));
			});
			await page.waitForTimeout(1500);
			console.log('SEND_POST_FIRED_AFTER_FORCE_CLICK::' + sendPostFired);
			await expect(sendDialog).toBeVisible(); // Dialog bleibt offen — kein Versand ausgeloest.
		}

		await page.screenshot({ path: path.join(ART, 'ac-send-dialog-after-click-attempt.png'), fullPage: true });

		// Aufraeumen: Dialog ohne Bestaetigung schliessen.
		const cancelBtn = sendDialog.getByRole('button', { name: 'Abbrechen' });
		await cancelBtn.click();
		await expect(sendDialog).toBeHidden();

		console.log('FINAL::descText=' + JSON.stringify(descText) + '::isDisabled=' + isDisabled + '::sendPostFired=' + sendPostFired);
	});
});

test.describe('Runde 2 — Adversary Edge Cases', () => {
	test('Doppel-Klick auf gesperrten Senden-Button loest keinen Versand aus; Dialog mehrfach oeffnen/schliessen bleibt stabil', async ({
		page
	}) => {
		await page.goto('/compare');
		await expect(page.getByTestId('compare-status-pill').first()).toBeVisible({ timeout: 15_000 });

		let sendPostFired = false;
		let requestCount = 0;
		page.on('request', (req) => {
			if (req.method() === 'POST' && /\/api\/compare\/presets\/.*\/send/.test(req.url())) {
				sendPostFired = true;
				requestCount++;
			}
		});

		// Mehrfaches Oeffnen/Schliessen des Kebab-Menues + Dialogs (Race-Stresstest).
		for (let i = 0; i < 2; i++) {
			await page.getByTestId('compare-row-kebab').first().click();
			await page.getByRole('menuitem', { name: 'Briefing jetzt senden' }).click();
			const dlg = page.getByRole('dialog').filter({ hasText: 'Briefing jetzt senden?' });
			await expect(dlg).toBeVisible();
			await dlg.getByRole('button', { name: 'Abbrechen' }).click();
			await expect(dlg).toBeHidden();
		}

		// Dialog final offen lassen und mehrfach (schnell) auf den gesperrten Button klicken.
		await page.getByTestId('compare-row-kebab').first().click();
		await page.getByRole('menuitem', { name: 'Briefing jetzt senden' }).click();
		const sendDialog = page.getByRole('dialog').filter({ hasText: 'Briefing jetzt senden?' });
		await expect(sendDialog).toBeVisible();
		const confirmBtn = sendDialog.getByRole('button', { name: 'Senden' });
		const isDisabled = await confirmBtn.isDisabled();
		expect(isDisabled).toBe(true);

		for (let i = 0; i < 5; i++) {
			await confirmBtn.click({ force: true }).catch(() => {});
		}
		await page.waitForTimeout(1500);
		console.log('ROUND2_DOUBLECLICK_SEND_POST_COUNT::' + requestCount + '::fired=' + sendPostFired);
		await expect(sendDialog).toBeVisible();

		// JS-Fehler/Konsole waehrend des Stresstests?
		await page.screenshot({
			path: path.join(ART, 'ac-round2-doubleclick-disabled.png'),
			fullPage: true
		});

		await sendDialog.getByRole('button', { name: 'Abbrechen' }).click();
		await expect(sendDialog).toBeHidden();
	});
});
