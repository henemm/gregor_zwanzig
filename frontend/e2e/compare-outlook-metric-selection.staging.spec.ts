// gz-eigenstaendig: Ausblick des Ortsvergleichs im Hub (Spalte „3-Tages-Ausblick“ der Karte „Was steht wo“, Orte-Antwort des Endpoints mit Paar-Altform) -- Trip-Pendant: trip-outlook-metric-selection.staging.spec.ts, ausblick-erbt-grundauswahl.staging.spec.ts
// Staging-Validierung — Ortsvergleich-Ausblick (Issue #1406 Scheibe A, #1848 A2).
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die gruppierte Ausblick-Auswahl
// (Katalog-Liste mit Reihenfolge-Block und „Aus“-Gruppe) ist aus dem Reiter Zustellung des Hubs entfernt.
// Im Hub schaltet der Nutzer den Ausblick je Metrik in der Spalte „3-Tages-Ausblick“ der Karte im Reiter
// Wetter; gespeichert wird die Tabelle (`display_config.placements`, Stelle `outlook`). Die Faelle laufen
// dort; das Altfeld `display_config.outlook_metrics` bleibt beim Speichern unberuehrt (Read-Modify-Write).
//   AC-1/AC-8 (Katalog gruppiert 26 Eintraege zu 24 Groessen, keine doppelten Testids im Panel): gestrichen —
//     die Katalog-Liste gibt es im Hub nicht mehr (Zeilen der Karte = Grundauswahl, Spalten = Stellen).
//   AC-5 (Reihenfolge-Block: Ziehen + Aus): gestrichen — Ersatz was-steht-wo-karte.spec.ts WS-2 (eine
//     Reihenfolge fuer alle Stellen, Tastatur und Maus) und WS-8 (Ausblick-Haken bei Orten, gespeichert).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/compare-outlook-metric-selection.staging.spec.ts
//   npx playwright test --config=playwright.compare-outlook.staging.config.ts

import { test, expect } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, stand, tabelle, tabelleGespeichert, type Abo } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.describe('Ortsvergleich-Ausblick in der Karte „Was steht wo“ (#1406 A, #3154)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-4 (#1406 A): gespeicherte Ausblick-Auswahl ueberlebt Reload — neu UND an einem Bestand mit Paar-Altform', async ({ page }) => {
		for (const bestand of [false, true]) {
			// Bestand: gespeicherte Ausblick-Auswahl in der Paar-ALTFORM (#1848 A2), muss gelesen und erhalten werden.
			const dc = bestand ? { outlook_metrics: [{ metric_id: 'temperature', aggregation: 'max' }] } : {};
			const abo = await seedAbo(page.request, 'vergleich', { dc });
			abos.push(abo);
			const vorher = (await stand(page.request, 'vergleich', abo.id)).display_config.outlook_metrics;
			let karte = await oeffneKarte(page, 'vergleich', abo.id);
			const m = await ersteAngehakte(karte, 'outlook');
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, m, 'outlook').click();
			await gespeichert;
			expect(gespeichertAn((await tabelle(page.request, 'vergleich', abo.id)).placements, m, 'outlook'), `${bestand ? 'Bestand' : 'neu'}: Abwahl gespeichert`).toBe(false);
			expect((await stand(page.request, 'vergleich', abo.id)).display_config.outlook_metrics, 'Altfeld outlook_metrics unveraendert').toEqual(vorher);

			await page.reload();
			karte = await oeffneKarte(page, 'vergleich', abo.id);
			await expect(haken(karte, m, 'outlook'), `${bestand ? 'Bestand' : 'neu'}: nach dem Neuladen wieder angehakt`).not.toBeChecked();
		}
	});

	test('Adversary (#1406 A): schnelles Ein/Aus derselben Groesse bleibt konsistent', async ({ page }) => {
		const abo = await seedAbo(page.request, 'vergleich');
		abos.push(abo);
		const karte = await oeffneKarte(page, 'vergleich', abo.id);
		const m = await ersteAngehakte(karte, 'outlook');
		const h = haken(karte, m, 'outlook');
		await h.click();
		await h.click();
		await h.click();
		await expect(h).not.toBeChecked();
		await expect
			.poll(async () => {
				const a = await tabelle(page.request, 'vergleich', abo.id);
				return a.stored ? gespeichertAn(a.placements, m, 'outlook') : 'nicht gespeichert';
			}, { timeout: 20_000, message: 'Server-Stand folgt dem letzten Klick nicht' })
			.toBe(false);
		await page.reload();
		await expect(haken(await oeffneKarte(page, 'vergleich', abo.id), m, 'outlook')).not.toBeChecked();
	});

	test('Adversary (#1406 A): alle Ausblick-Groessen abgewaehlt — jede Zeile bleibt da und ist zurueckholbar', async ({ page }) => {
		const abo = await seedAbo(page.request, 'vergleich');
		abos.push(abo);
		let karte = await oeffneKarte(page, 'vergleich', abo.id);
		const alle: string[] = [];
		for (;;) {
			const m = await ersteAngehakte(karte, 'outlook').catch(() => null);
			if (!m) break;
			alle.push(m);
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, m, 'outlook').click();
			await gespeichert;
		}
		expect(alle.length, 'Messaufbau: mindestens eine Ausblick-Zelle').toBeGreaterThan(0);
		await page.reload();
		karte = await oeffneKarte(page, 'vergleich', abo.id);
		for (const m of alle) await expect(haken(karte, m, 'outlook'), `${m}: Zeile mit Ausblick-Zelle bleibt`).toHaveCount(1);
		const gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, alle[0], 'outlook').click();
		await gespeichert;
		expect(gespeichertAn((await tabelle(page.request, 'vergleich', abo.id)).placements, alle[0], 'outlook'), 'Rueckweg wirkt').toBe(true);
	});
});
