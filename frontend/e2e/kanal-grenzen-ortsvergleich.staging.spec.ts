// gz-eigenstaendig: SMS-Grenze des Orts-Briefings (153 Zeichen, render_compare_sms) -- Trip-Pendant: kanal-grenzen-und-hinweise.staging.spec.ts (160)
// E2E (Staging) — Issue #1719 S3 AC-6 und #2438 AC-2: der Ortsvergleich nennt die echte SMS-Zeichengrenze des
// Briefings (153) ohne Wertung und erklaert, dass ein Kanal nur zeigt, was in der Grundauswahl steht.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/14): Versand-Abschnitt, Alarm-Kanalauswahl und
// Kanal-Reiter der Metrik-Oberflaeche stehen nicht mehr im Reiter Zustellung. Die Zeichengrenze nennt im Hub
// das SMS-Beispiel der Karte „Was steht wo“ (Reiter Wetter), der Abwahl-Hinweis steht im Kartentext.
//   Alarme-Reiter (AlertChannelPicker, Alarm-Grenze 140): gestrichen — der Wirkort ist mit #2795 S3b 1b ersatzlos
//     entfallen (die Kanal-Tabelle des Reiters Zustellung nennt keine Zeichengrenze), die Datei war seitdem rot.
//   #2438 AC-2 je Kanal-Reiter: es gibt keine Kanal-Reiter mehr; EIN Hinweis im Kartentext gilt fuer alle Spalten.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kanal-grenzen-ortsvergleich.staging.spec.ts

import { test, expect } from '@playwright/test';
import { oeffneKarte, seedAbo, tabelle, type Abo } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.beforeEach(async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });
});

test('Issue #1719 S3 AC-6: das SMS-Beispiel des Ortsvergleichs nennt 153, nicht 140, keine Wertung', async ({ page }) => {
	const abo = await seedAbo(page.request, 'vergleich');
	abos.push(abo);
	const karte = await oeffneKarte(page, 'vergleich', abo.id);
	expect((await tabelle(page.request, 'vergleich', abo.id)).sms_example.max_length, 'Endpoint: Grenze des Orts-Briefings').toBe(153);
	const zeichen = karte.getByTestId('was-steht-wo-sms-zeichen');
	await expect(zeichen, 'AC-6 FAIL: die echte Zeichengrenze (153) fehlt').toContainText('von 153 Zeichen');
	await expect(zeichen).not.toContainText('140');
	const text = (await karte.innerText()).toLowerCase();
	for (const w of ['läuft flach', 'wird flach']) expect(text.includes(w), `AC-6 FAIL: Wertung "${w}"`).toBe(false);
});

test('Issue #2438 AC-2: der Ortsvergleich erklaert, dass jede Spalte nur abwaehlt, was die Grundauswahl hat', async ({ page }) => {
	const abo = await seedAbo(page.request, 'vergleich');
	abos.push(abo);
	const karte = await oeffneKarte(page, 'vergleich', abo.id);
	await expect(karte).toContainText('Jede Zeile ist eine Metrik aus der Auswahl oben.');
	await expect(karte).toContainText('Hier wählst du nur ab.');
});
