// gz-eigenstaendig: Ausblick des Ortsvergleichs im Hub (Spalte „3-Tages-Ausblick“ der Karte „Was steht wo“, Orte-Antwort des Endpoints mit Paar-Altform) -- Trip-Pendant: trip-outlook-metric-selection.staging.spec.ts, ausblick-erbt-grundauswahl.staging.spec.ts
// Staging-Validierung — Ortsvergleich-Ausblick (Issue #1406 Scheibe A, #1848 A2).
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die gruppierte Ausblick-Auswahl
// (Katalog-Liste mit Reihenfolge-Block und „Aus“-Gruppe) ist aus dem Reiter Zustellung des Hubs entfernt.
// Im Hub schaltet der Nutzer den Ausblick je Metrik in der Spalte „3-Tages-Ausblick“ der Karte im Reiter
// Wetter; gespeichert wird die Tabelle (`display_config.placements`, Stelle `outlook`). Die Faelle laufen dort.
// #3359 (Spec fix_3359 AC-8): der Bestand ist eine eigene Tabelle mit eigener Ausblick-Stelle und
// `outlook_reports` (nicht mehr die seit #3277 wirkungslose Paar-Altform); die Karte zeigt genau diesen Stand,
// auch nach dem Neuladen, und eine Abwahl aendert nur diese eine Zelle.
//   AC-1/AC-8 (Katalog gruppiert 26 Eintraege zu 24 Groessen, keine doppelten Testids im Panel): gestrichen —
//     die Katalog-Liste gibt es im Hub nicht mehr (Zeilen der Karte = Grundauswahl, Spalten = Stellen).
//   AC-5 (Reihenfolge-Block: Ziehen + Aus): gestrichen — Ersatz was-steht-wo-karte.spec.ts WS-2 (eine
//     Reihenfolge fuer alle Stellen, Tastatur und Maus) und WS-8 (Ausblick-Haken bei Orten, gespeichert).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/compare-outlook-metric-selection.staging.spec.ts
//   npx playwright test --config=playwright.compare-outlook.staging.config.ts

import { test, expect } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, type Abo, type Json } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.describe('Ortsvergleich-Ausblick in der Karte „Was steht wo“ (#1406 A, #3154)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-4 (#1406 A): gespeicherte Ausblick-Auswahl ueberlebt Reload — neu UND an einem Bestand mit eigener Ausblick-Stelle', async ({ page }) => {
		for (const bestand of [false, true]) {
			// Bestand: eigene Tabelle, die bewusst von der Tabelle aus der Grundauswahl abweicht (Ausblick bei
			// temperature aus, bei wind und precipitation an; Reihenfolge anders), Ausblick nur morgens.
			const dc = bestand
				? {
						placements: {
							version: 1,
							rows: [
								{ metric_id: 'wind', places: { email: true, telegram: true, sms: true, hourly: true, outlook: true } },
								{ metric_id: 'temperature', places: { email: true, telegram: true, sms: true, hourly: true, outlook: false } },
								{ metric_id: 'precipitation', places: { email: true, telegram: false, sms: true, hourly: true, outlook: true } },
								// letzte Metrik der Grundauswahl (seedAbo: ORTE_METRIKEN) -- sonst haengt das Speichern
								// sie als neue Zeile an; Stundenverlauf ist fuer sie gesperrt
								{ metric_id: 'sunshine', places: { email: true, telegram: true, sms: true, hourly: false, outlook: true } }
							],
							outlook_reports: ['morning']
						}
					}
				: {};
			const abo = await seedAbo(page.request, 'vergleich', { dc });
			abos.push(abo);
			const vorher = (await tabelle(page.request, 'vergleich', abo.id)) as { placements: Json; outlook_reports: string[]; rows: Array<{ metric_id: string; cells: Record<string, { state: string }> }> };
			let karte = await oeffneKarte(page, 'vergleich', abo.id);
			const ausblickAn = (rows: typeof vorher.rows) => rows.filter((r) => r.cells?.outlook?.state === 'on').map((r) => r.metric_id);
			const karteAusblick = async () => {
				const an: string[] = [];
				for (const z of vorher.rows) {
					const h = haken(karte, z.metric_id, 'outlook');
					if ((await h.count()) && (await h.isChecked())) an.push(z.metric_id);
				}
				return an;
			};
			if (bestand) {
				expect(vorher.outlook_reports, 'Messaufbau: Bestand Ausblick nur morgens').toEqual(['morning']);
				expect(gespeichertAn(vorher.placements, 'temperature', 'outlook'), 'Messaufbau: Bestand temperature ohne Ausblick').toBe(false);
				expect(await karteAusblick(), 'Bestand: Ausblick-Spalte der Karte = gespeicherte Tabelle').toEqual(ausblickAn(vorher.rows));
			}
			const m = await ersteAngehakte(karte, 'outlook');
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, m, 'outlook').click();
			await gespeichert;
			const nachher = await tabelle(page.request, 'vergleich', abo.id);
			expect(gespeichertAn(nachher.placements, m, 'outlook'), `${bestand ? 'Bestand' : 'neu'}: Abwahl gespeichert`).toBe(false);
			expect(nachher.outlook_reports, `${bestand ? 'Bestand' : 'neu'}: Ausblick-Berichte unveraendert`).toEqual(vorher.outlook_reports);
			if (bestand) {
				// Nur die eine Zelle hat sich geaendert: alle Zeilen gleich dem Stand vorher, bei Zeile m nur die
				// Ausblick-Zelle ausgenommen (Stelle und Form); die Ausblick-Zelle selbst ist oben auf „ab“ geprueft.
				const ohneAusblickVonM = (p: Json) =>
					((p.rows ?? []) as Json[]).map((r) => {
						if (r.metric_id !== m) return r;
						const { outlook: _p, ...places } = (r.places ?? {}) as Json;
						const { outlook: _f, ...formats } = (r.formats ?? {}) as Json;
						return { metric_id: r.metric_id, places, formats };
					});
				expect(ohneAusblickVonM(nachher.placements), 'Bestand: ausser der Ausblick-Zelle von m ist die Tabelle unveraendert').toEqual(ohneAusblickVonM(vorher.placements));
			}

			await page.reload();
			karte = await oeffneKarte(page, 'vergleich', abo.id);
			await expect(haken(karte, m, 'outlook'), `${bestand ? 'Bestand' : 'neu'}: nach dem Neuladen wieder angehakt`).not.toBeChecked();
			expect(await karteAusblick(), `${bestand ? 'Bestand' : 'neu'}: nach dem Neuladen Ausblick-Spalte = gespeicherte Tabelle`).toEqual(ausblickAn(nachher.rows));
			if (bestand) await page.screenshot({ path: '../docs/artifacts/feat-1848-a2-outlook-kennungen/ac-4-existing-preset-untouched.png' });
			else await page.screenshot({ path: '../docs/artifacts/feat-1848-a2-outlook-kennungen/ac-4-persisted-after-reload.png' });
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
		await page.screenshot({ path: '../docs/artifacts/feat-1848-a2-outlook-kennungen/adv-1-rapid-toggle-consistent.png' });
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
		await page.screenshot({ path: '../docs/artifacts/feat-1406a-ausblick-geteiltes-element/adv-2-empty-then-reselect.png' });
	});
});
