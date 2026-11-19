// E2E — Issue #1232 Scheibe 3b (LayoutTab, context="route") und #1575 Scheibe 3 (kanal-eigene Metrik-Auswahl, Trip).
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14, ADR-0124): der LayoutTab mit Kanal-Umschalter
// ist aus dem Reiter Zustellung entfernt. Die Kanaele sind im Hub Spalten der Karte „Was steht wo“ (Reiter Wetter),
// es gibt EINE Reihenfolge fuer alle Stellen; gespeichert wird `display_config.placements`.
//   #1575 AC-2/AC-3 (SMS-Edit wirkt nur auf SMS): umgezogen — SMS-Haken ab, E-Mail/Telegram derselben Zeile bleiben.
// Gestrichen (je mit Ersatz):
//   AC-1/AC-2 Kanal-Umschalter Email→Telegram→SMS, keine Vorschau: Wirkort ersatzlos entfallen (alle Kanaele zugleich
//     als Spalten); Ersatz was-steht-wo-karte.spec.ts WS-1 (Spalten je Kontext).
//   AC-3 Drag & Drop mit Auto-Save und Reload: Ersatz WS-2.
//   AC-6 Kanalwechsel loest keinen Auto-Save aus: es gibt keinen Kanalwechsel mehr; „Oeffnen schreibt nichts“ sichert
//     hub-save-chip.spec.ts SC-1b an der Karte.
//   AC-5 „Aus“ legt die Metrik in die Aus-Gruppe statt sie zu loeschen: Ersatz kanal-abwahl-bleibt-reversibel.staging AC-7.
//   AC-7 kein Mobile-FAB, kein horizontaler Scroll: Ersatz WS-8 (390 px).
//   AC-8 SMS-Schwellen, Mail-Inhalt-Karte, Amtliche Warnungen bedienbar: SMS-Schwellen entfallen (Konzept W13), die
//     Mail-Schalter stehen in der Karte (WS-4, WS-13, WS-15), Amtliche Warnungen im Reiter Wetter (WS-11, hub-alarme-wertprops).
//   AC-4/AC-3 Overflow-Trip (Kapplinie Telegram, Ueberlauf-Chip): Wirkort ersatzlos entfallen (keine Kapplinie in der Karte).
//
//   cd frontend && npx playwright test --project=tests e2e/layout-tab-route.spec.ts

import { test, expect } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert } from './was-steht-wo.helpers';

test.describe('Issue #1575 Scheibe 3: kanal-eigene Auswahl (context="route") in der Karte', () => {
	test('AC-2/AC-3: SMS-Edit wirkt nur auf SMS und laesst email/telegram unveraendert', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		const abo = await seedAbo(page.request, 'route');
		try {
			const karte = await oeffneKarte(page, 'route', abo.id);
			const m = await ersteAngehakte(karte, 'sms');
			const vorher = { email: await haken(karte, m, 'email').isChecked(), telegram: await haken(karte, m, 'telegram').isChecked() };
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, m, 'sms').click();
			await gespeichert;
			const p = (await tabelle(page.request, 'route', abo.id)).placements;
			expect(gespeichertAn(p, m, 'sms')).toBe(false);
			expect({ email: gespeichertAn(p, m, 'email'), telegram: gespeichertAn(p, m, 'telegram') }, 'E-Mail/Telegram unveraendert').toEqual(vorher);
			await expect(haken(karte, m, 'email')).toBeChecked({ checked: vorher.email });
			await expect(haken(karte, m, 'telegram')).toBeChecked({ checked: vorher.telegram });
		} finally {
			await abo.aufraeumen();
		}
	});
});
