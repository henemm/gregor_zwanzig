// gz-eigenstaendig: Kanal-Spalten der transponierten Vergleichs-Uebersicht (Orte = Spalten) in der Karte „Was steht wo“ -- erlaubte Compare-Eigenheit; Trip-Pendant: kanal-grenzen-und-hinweise.staging.spec.ts, layout-tab-route.spec.ts
// E2E (Staging) — #1703 Scheibe 8: Bedienung der kanal-eigenen Metrikauswahl der Vergleichs-Uebersicht.
// ACs: AC-S8-3, AC-S8-5, AC-S8-9, AC-S8-12, AC-S8-13. Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die Kanal-Reiter der Uebersicht sind aus dem
// Reiter Zustellung entfernt. Die Kanaele sind Spalten der Karte „Was steht wo“ im Reiter Wetter; „Aus in diesem
// Kanal“ ist ein abgewaehlter Haken, gespeichert als `display_config.placements` (PUT auf die Tabelle).
//   AC-S8-9/AC-S8-5/AC-S8-3: umgezogen — ein Kanal-Edit loest GENAU EINEN Tabellen-PUT aus, ist umkehrbar, und eine
//     globale Abwahl („−“) nimmt die Zeile aus allen Spalten.
//   AC-S8-12/AC-S8-13 (drei Kanal-Reiter, Umschalten, SMS nennt 153, Telegram kappt nach der siebten Zeile):
//     gestrichen — Spalten statt Reiter: was-steht-wo-karte.spec.ts WS-1 (Spalten je Kontext); die SMS-Grenze 153
//     prueft kanal-grenzen-ortsvergleich.staging.spec.ts; eine Telegram-Kappung zeigt die Karte nicht mehr (Wirkort
//     ersatzlos entfallen).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/compare-uebersicht-kanal-bedienung.staging.spec.ts

import { test, expect, type Request } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, zeile } from './was-steht-wo.helpers';

test.describe('#1703 S8: Kanal-Spalten der Vergleichs-Uebersicht — Bedienung', () => {
	test('AC-S8-9/AC-S8-5/AC-S8-3: ein Kanal-Edit loest GENAU EINEN PUT aus, ist umkehrbar, eine globale Abwahl nimmt die Zeile ueberall heraus', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		const abo = await seedAbo(page.request, 'vergleich');
		try {
			const karte = await oeffneKarte(page, 'vergleich', abo.id);
			const puts: Request[] = [];
			page.on('request', (r) => {
				if (r.method() === 'PUT' && r.url().includes('/api/')) puts.push(r);
			});
			const m = await ersteAngehakte(karte, 'telegram');
			let gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, m, 'telegram').click();
			await gespeichert;
			await page.waitForTimeout(1_200);
			expect(puts.map((r) => new URL(r.url()).pathname), 'AC-S8-9: genau EIN PUT auf die Tabelle').toEqual([`/api/briefings/${abo.id}/placements`]);
			expect(gespeichertAn((await tabelle(page.request, 'vergleich', abo.id)).placements, m, 'telegram')).toBe(false);

			gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, m, 'telegram').click();
			await gespeichert;
			expect(gespeichertAn((await tabelle(page.request, 'vergleich', abo.id)).placements, m, 'telegram'), 'AC-S8-5: umkehrbar').toBe(true);

			const weg = (await ersteAngehakte(karte, 'email', [m]));
			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(`/api/compare/presets/${abo.id}`), { timeout: 20_000 });
			await page.locator(`[data-testid="wetter-zeile-entfernen-${weg}"]:visible`).first().click();
			expect((await put).ok()).toBeTruthy();
			await expect(zeile(karte, weg), 'AC-S8-3: global abgewaehlt steht in keiner Spalte mehr').toHaveCount(0, { timeout: 15_000 });
		} finally {
			await abo.aufraeumen();
		}
	});
});
