// E2E (Staging) — Issue #1719 S2 AC-10 Test B: die Grundauswahl-Abwahl schneidet die SMS-Kopie.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/13/14): die Kanal-Reiter sind aus dem Reiter
// Zustellung entfernt; die „zugestellte SMS-Vorschau“ ist im Hub das SMS-Beispiel der Karte „Was steht wo“ (gleicher
// Reiter Wetter wie die Grundauswahl). Wirkung: nach einer SMS-Bearbeitung in der Karte und der Abwahl von „gust“ in
// der Grundauswahl verschwindet der Böen-Wert aus dem sichtbaren SMS-Beispiel, ohne Neuladen.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/metrik-grundauswahl-schneidet-kanal.staging.spec.ts

import { test, expect } from '@playwright/test';
import { haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert } from './was-steht-wo.helpers';

test.describe('Issue #1719 S2 AC-10 Test B: Grundauswahl-Abwahl schneidet die SMS', () => {
	test('SMS-Bearbeitung + Grundauswahl-Abwahl -> "gust" verschwindet aus dem SMS-Beispiel der Karte', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		const abo = await seedAbo(page.request, 'route');
		try {
			const karte = await oeffneKarte(page, 'route', abo.id);
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, 'thunder', 'sms').click();
			await gespeichert;
			const vorher = await tabelle(page.request, 'route', abo.id);
			const gustSms = (vorher.rows as Array<{ metric_id: string; cells: Record<string, { example: string | null }> }>).find((r) => r.metric_id === 'gust')?.cells.sms.example as string;
			expect(gustSms, 'Messaufbau: Böen haben einen SMS-Wert').toBeTruthy();
			const sms = karte.getByTestId('was-steht-wo-sms-text');
			await expect(sms).toContainText(gustSms);

			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(`/api/trips/${abo.id}`), { timeout: 20_000 });
			await page.locator('[data-testid="wetter-zeile-entfernen-gust"]:visible').first().click();
			expect((await put).ok()).toBeTruthy();
			await expect(sms, 'AC-10 FAIL: Böen stehen weiter im SMS-Beispiel').not.toContainText(gustSms, { timeout: 15_000 });
		} finally {
			await abo.aufraeumen();
		}
	});
});
