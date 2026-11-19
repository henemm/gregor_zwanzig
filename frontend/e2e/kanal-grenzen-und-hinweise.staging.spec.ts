// E2E (Staging) — Issue #1719 S3 (echte Platzgrenzen im Trip-Editor) und #2438 (Abwahl-Hinweis im Trip-Editor).
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/14): die Kanal-Reiter der Metrik-Oberflaeche sind
// aus dem Reiter Zustellung entfernt. Im Hub zeigt die Karte „Was steht wo“ (Reiter Wetter) die Kanaele als Spalten:
//   AC-4: das SMS-Beispiel nennt die Zeichengrenze 160 (nicht „—“, nicht 140).
//   #2438 AC-1: der Hinweis, dass ein Kanal nur abwaehlt, was die Grundauswahl hat, steht im Kartentext.
// Gestrichen:
//   AC-3 (Telegram-Kapplinie nach der 7. Zeile, Ueberlauf-Chip): Wirkort ersatzlos entfallen — die Karte hat keine
//     Spaltenliste je Kanal und keine Kapplinie; die SMS-Kappung zeigt die Marke „passt nicht mehr“ (WS-2).
//   AC-8 (global abgewaehlte Metrik erscheint im Kanal weder aktiv noch in der „Aus“-Gruppe): Ersatz
//     kanal-abwahl-bleibt-reversibel.staging.spec.ts AC-9 und ausblick-erbt-grundauswahl.staging.spec.ts AC-5
//     (keine Zeile ausserhalb der Grundauswahl).
//   #2438 AC-5 (320/375 px ohne Ueberlauf, Kontrast >= 4.5:1): Ersatz was-steht-wo-karte.spec.ts WS-8 (390 px,
//     keine seitliche Seite, jede Spalte erreichbar, Kontrast der Karte).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kanal-grenzen-und-hinweise.staging.spec.ts

import { test, expect } from '@playwright/test';
import { oeffneKarte, seedAbo, tabelle, type Abo } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.beforeEach(async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
});

test('AC-4: das SMS-Beispiel nennt die Zeichengrenze 160, nicht "—" und nicht "140"', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route');
	abos.push(abo);
	const karte = await oeffneKarte(page, 'route', abo.id);
	expect((await tabelle(page.request, 'route', abo.id)).sms_example.max_length).toBe(160);
	const zeichen = karte.getByTestId('was-steht-wo-sms-zeichen');
	await expect(zeichen).toContainText('von 160 Zeichen');
	await expect(zeichen).not.toContainText('140');
	await expect(zeichen).not.toContainText('—');
});

test('#2438 AC-1: der Kartentext erklaert, dass jede Spalte nur abwaehlt, was die Grundauswahl hat', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route');
	abos.push(abo);
	const karte = await oeffneKarte(page, 'route', abo.id);
	await expect(karte).toContainText('Jede Zeile ist eine Metrik aus der Auswahl oben.');
	await expect(karte).toContainText('Hier wählst du nur ab.');
});
