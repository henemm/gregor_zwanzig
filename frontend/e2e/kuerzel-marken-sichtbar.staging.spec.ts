// E2E (Staging) — Issue #1719 S4: die Kuerzel-Marken sind lesbar, in jeder Fensterbreite.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/12/14): die Reihenfolge-Listen je Kanal (Zeilen mit
// Roh/Kurzform-Marke, „Aus“-Zeile, Steuerung neben/unter dem Label) sind aus dem Reiter Zustellung entfernt. Im Hub
// zeigt die Karte „Was steht wo“ (Reiter Wetter) je Zeile und Stelle Haken, Roh/Einfach und Beispielwert; die
// Kuerzel stehen im SMS-Beispiel und unter „Kürzel erklärt“. Je Fall:
//   AC-14 (Ziehgeste sortiert und speichert, je Breite): umgezogen — Griff der Karte per Tastatur bei 390 und 901 px.
//   AC-5 (jede Zeile traegt Roh- und Kurzform-Marke mit allen Kuerzeln): gestrichen — die Kurzform-Marke gibt es nicht
//     mehr; Ersatz kuerzel-legende-lesbar.staging.spec.ts AC-1 (jedes Kuerzel einer SMS-Metrik erklaert) und
//     was-steht-wo-karte.spec.ts WS-2 (SMS-Beispiel folgt der Reihenfolge).
//   AC-10/AC-11 (14 Aufloesungen), AC-12 (Bruchzone kuerzt den Namen, nie eine Marke), AC-13 (Vergleichs-Editor):
//     gestrichen — Ersatz was-steht-wo-karte.spec.ts WS-8 (390 px: keine seitliche Seite, jede Spalte erreichbar,
//     Kontrast) und kuerzel-legende-lesbar.staging.spec.ts AC-6 (320 bis 899 px, Trip und Orte).
//   AC-3/AC-5/AC-6 (Steuerung unter/neben dem Label, einzeilige „Aus“-Zeile): Wirkort ersatzlos entfallen (das
//     Zeilen-Layout der Kanal-Liste gibt es nicht mehr; „Aus“ ist ein Haken in der Spalte).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kuerzel-marken-sichtbar.staging.spec.ts

import { test, expect } from '@playwright/test';
import { folge, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, zeile, type Abo } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

for (const breite of [390, 901]) {
	test(`AC-14: die Ziehgeste (Griff, Tastatur) sortiert weiterhin um und speichert (${breite}px)`, async ({ page }) => {
		await page.setViewportSize({ width: breite, height: 900 });
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		const karte = await oeffneKarte(page, 'route', abo.id);
		const start = await folge(karte);
		const gespeichert = tabelleGespeichert(page, abo.id);
		await zeile(karte, start[0]).getByTestId('drag-handle').focus();
		await page.keyboard.press('Space');
		await page.keyboard.press('ArrowDown');
		await page.keyboard.press('Space');
		await gespeichert;
		const soll = [start[1], start[0], ...start.slice(2)];
		await expect.poll(() => folge(karte)).toEqual(soll);
		expect(((await tabelle(page.request, 'route', abo.id)).placements.rows as Array<{ metric_id: string }>).map((r) => r.metric_id)).toEqual(soll);
	});
}
