// E2E (Staging) — Issue #1719 S3 AC-10: eine globale Abwahl schreibt auch einen bereits eigenstaendigen SMS-Kanal durch.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14, AC-32): die Kanal-Reiter sind aus dem Reiter
// Zustellung entfernt. „Eigenstaendiger SMS-Kanal“ heisst heute: die Tabelle ist gespeichert (`placements`, hier
// durch eine SMS-Abwahl einer anderen Metrik). Wirkung heute: „−“ der Grundauswahl entfernt die Zeile aus der
// gespeicherten Tabelle im selben Speichervorgang, und das SMS-Beispiel der Endpoint-Antwort enthaelt ihren Wert nicht mehr.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/metrik-abwahl-schreibt-alle-kanaele-durch.staging.spec.ts

import { test, expect } from '@playwright/test';
import { haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, zeile } from './was-steht-wo.helpers';

test.describe('Issue #1719 S3 AC-10: globale Abwahl schreibt eine gespeicherte Tabelle durch', () => {
	test('SMS gespeichert (Tabelle existiert) -> global „−“ -> Reload: Zeile weg, SMS-Beispiel ohne die Metrik', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		const abo = await seedAbo(page.request, 'route');
		try {
			let karte = await oeffneKarte(page, 'route', abo.id);
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, 'thunder', 'sms').click();
			await gespeichert;
			const vorher = await tabelle(page.request, 'route', abo.id);
			expect(vorher.stored, 'Messaufbau: Tabelle gespeichert').toBe(true);
			const gustSms = (vorher.rows as Array<{ metric_id: string; cells: Record<string, { example: string | null }> }>).find((r) => r.metric_id === 'gust')?.cells.sms.example;
			expect(gustSms, 'Messaufbau: Böen haben einen SMS-Wert').toBeTruthy();
			expect(vorher.sms_example.text, 'Messaufbau: Böen stehen im SMS-Beispiel').toContain(gustSms);

			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(`/api/trips/${abo.id}`), { timeout: 20_000 });
			await page.locator('[data-testid="wetter-zeile-entfernen-gust"]:visible').first().click();
			expect((await put).ok()).toBeTruthy();
			await page.reload();
			karte = await oeffneKarte(page, 'route', abo.id);
			await expect(zeile(karte, 'gust')).toHaveCount(0);
			const nachher = await tabelle(page.request, 'route', abo.id);
			expect((nachher.placements.rows as Array<{ metric_id: string }>).map((r) => r.metric_id), 'Zeile aus der gespeicherten Tabelle entfernt').not.toContain('gust');
			expect(nachher.sms_example.text, 'SMS-Beispiel ohne Böen').not.toContain(gustSms);
			await expect(haken(karte, 'thunder', 'sms'), 'die fruehere SMS-Abwahl bleibt').not.toBeChecked();
		} finally {
			await abo.aufraeumen();
		}
	});
});
