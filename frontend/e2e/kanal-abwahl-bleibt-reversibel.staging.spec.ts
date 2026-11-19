// E2E (Staging) — Issue #1719 Scheibe 3, Block C: "Aus" ist ein ZUSTAND, keine Löschung (ADR-0050 Regel 4).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-7, AC-9, AC-11.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die Kanal-Reiter mit „Aus“-Gruppe sind aus
// dem Reiter Zustellung entfernt. Im Hub ist „Aus in diesem Kanal“ ein abgewaehlter Haken in der Spalte des
// Kanals der Karte „Was steht wo“ (Reiter Wetter); die Zeile bleibt stehen. Gespeichert wird `placements`.
//   AC-7: SMS-Haken ab → Zeile bleibt → Neuladen → weiter ab → wieder an (reaktivierbar).
//   AC-9: „−“ der Grundauswahl im selben Reiter nimmt die Zeile SOFORT aus der Karte, ohne Neuladen.
//   AC-11 (Abwahl im Kanal bleibt nach Grundauswahl aus/an erhalten): gestrichen — die freigegebene Spec legt das
//     Gegenteil fest (AC-32: „+“ haengt die Zeile ueberall angehakt an); Ersatz was-steht-wo-karte.spec.ts WS-6, WS-11.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kanal-abwahl-bleibt-reversibel.staging.spec.ts

import { test, expect } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, zeile, type Abo } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.describe('Issue #1719 S3 Block C: "Aus" ist ein Zustand (Karte „Was steht wo“)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test('AC-7: im SMS-Kanal abgewaehlte Metrik bleibt als Zeile stehen und ist reaktivierbar — auch nach Reload', async ({ page }) => {
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		let karte = await oeffneKarte(page, 'route', abo.id);
		const m = await ersteAngehakte(karte, 'sms');
		let gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, m, 'sms').click();
		await gespeichert;
		await expect(zeile(karte, m), 'AC-7 FAIL: die Zeile verschwindet').toHaveCount(1);

		await page.reload();
		karte = await oeffneKarte(page, 'route', abo.id);
		await expect(haken(karte, m, 'sms'), 'AC-7 FAIL: nach Reload wieder an').not.toBeChecked();
		await expect(haken(karte, m, 'email'), 'AC-7 FAIL: andere Stelle mitgeschaltet').toBeChecked();
		gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, m, 'sms').click();
		await gespeichert;
		expect(gespeichertAn((await tabelle(page.request, 'route', abo.id)).placements, m, 'sms'), 'AC-7 FAIL: Reaktivieren nicht gespeichert').toBe(true);
		await page.screenshot({ path: '../docs/artifacts/fix-1719-s3-aus-ist-ein-zustand/ac-7-zeile-bleibt-reaktivierbar.png' });
	});

	test('AC-9: eine globale Abwahl („−“) nimmt die Zeile SOFORT aus der Karte, ohne Reload', async ({ page }) => {
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		const karte = await oeffneKarte(page, 'route', abo.id);
		await expect(zeile(karte, 'gust'), 'Vorbedingung').toHaveCount(1);
		const put = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(`/api/trips/${abo.id}`), { timeout: 20_000 });
		await page.locator('[data-testid="wetter-zeile-entfernen-gust"]:visible').first().click();
		expect((await put).ok()).toBeTruthy();
		await expect(zeile(karte, 'gust'), 'AC-9 FAIL: die global abgewaehlte Metrik steht noch in der Karte').toHaveCount(0, { timeout: 15_000 });
	});
});
