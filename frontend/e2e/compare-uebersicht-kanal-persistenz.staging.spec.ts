// E2E (Staging) — #1703 Scheibe 8: Persistenz und Wirkung der kanal-eigenen
// Metrikauswahl der Vergleichs-Uebersichtstabelle.
// ACs: AC-S8-4, AC-S8-6, AC-S8-10, AC-S8-11.
//
// 🔴 EINZIGER WAECHTER dreier offline unbewachter Zeilen in CompareTabs.svelte:
// 710 (Einsammeln in den Speicher-Schnappschuss), 737 (Hydrieren nach dem
// Neuladen), 782 (Rollback nach fehlgeschlagenem PUT). Kein Kern-Test erreicht
// sie — sie brauchen den echten Hub-Mount, den echten Go-Merge
// (`config_merge.go` ersetzt `channel_active_metrics` als GANZES und loescht
// nie einen Schluessel) und ein echtes Neuladen. Faellt diese Datei weg,
// faellt die Absicherung dieser drei Zeilen ersatzlos mit.
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md § Testauflage
// (Buendel `compare-uebersicht-persistiert-je-kanal`).
// Aufbau, Selektoren, #1423-Warteregel, Ausfuehrbefehl: ./compare-uebersicht-kanal.helpers.ts

import { test, expect } from '@playwright/test';
import { cleanupTracked } from './helpers';
import {
	aktiveMetriken, ausMetriken, ausSchalten, createUebersichtPreset, einSchalten,
	gespeicherteKanalAuswahl, klickUndSpeichere, oeffneUebersicht, waehleKanal
} from './compare-uebersicht-kanal.helpers';

/** Vier Groessen mit je einer Auswertung — klein genug, um einen Kanal in vier
 *  Klicks vollstaendig zu leeren (AC-S8-11). */
const M = ['wind_max_kmh', 'precip_sum_mm', 'pop_max_pct', 'uv_index_max'];
const fehlt = (weg: string) => M.filter((m) => m !== weg);

test.describe('#1703 S8: Kanal-eigene Uebersichts-Auswahl ueberlebt Speichern und Neuladen', () => {
	test.afterAll(async ({ request }) => await cleanupTracked(request));

	test('AC-S8-10/AC-S8-4: drei nacheinander editierte Kanaele bleiben ALLE erhalten, und eine globale Abwahl im E-Mail-Reiter schreibt bis in den gespeicherten SMS-Stand durch', async ({
		page, request
	}) => {
		const presetId = await createUebersichtPreset(request, `1703-s8-drei-kanaele-${Date.now()}`, M);
		const f = await oeffneUebersicht(page, presetId);

		// AC-S8-10: je Kanal eine ANDERE Abwahl. Wuerde nur der zuletzt sichtbare
		// Reiter serialisiert (M4), ersetzte der Go-Merge den ganzen
		// `channel_active_metrics`-Block und die beiden anderen Kanaele gingen
		// lautlos verloren (BUG-DATALOSS-GR221-Muster).
		await waehleKanal(f, 'email');
		await ausSchalten(f, 'wind_max_kmh');
		await waehleKanal(f, 'telegram');
		await ausSchalten(f, 'precip_sum_mm');
		await waehleKanal(f, 'sms');
		await ausSchalten(f, 'pop_max_pct');
		for (const [kanal, weg] of [['email', 'wind_max_kmh'], ['telegram', 'precip_sum_mm'], ['sms', 'pop_max_pct']] as const) {
			expect(
				await gespeicherteKanalAuswahl(request, presetId, kanal),
				`AC-S8-10 FAIL: gespeicherter Stand des Kanals "${kanal}" — nie mitgesendet oder von einem spaeteren PUT ueberschrieben`
			).toEqual(fehlt(weg));
		}

		// Neuladen: jeder Reiter hydriert seinen EIGENEN Stand (Zeile 737).
		const g = await oeffneUebersicht(page, presetId);
		await expect.poll(() => aktiveMetriken(g), {
			message: 'AC-S8-10 FAIL: E-Mail-Reiter nach dem Neuladen', timeout: 10_000
		}).toEqual(fehlt('wind_max_kmh'));
		await waehleKanal(g, 'telegram');
		expect(await aktiveMetriken(g), 'AC-S8-10 FAIL: Telegram-Reiter nach dem Neuladen').toEqual(fehlt('precip_sum_mm'));
		await waehleKanal(g, 'sms');
		expect(await aktiveMetriken(g), 'AC-S8-10 FAIL: SMS-Reiter nach dem Neuladen').toEqual(fehlt('pop_max_pct'));

		// AC-S8-4: der Nutzer steht im E-MAIL-Reiter und waehlt GLOBAL ab. Die
		// Anzeige verriete nichts (sie filtert ohnehin gegen die Grundauswahl) —
		// nur der GESPEICHERTE SMS-Stand zeigt, ob die Durchschreibung lief (M3).
		await waehleKanal(g, 'email');
		await klickUndSpeichere(g, g.grundauswahl.locator('input[data-metric-key="uv_index_max"]'));
		expect(
			await gespeicherteKanalAuswahl(request, presetId, 'sms'),
			'AC-S8-4 FAIL: "uv_index_max" steht nach der GLOBALEN Abwahl noch im gespeicherten SMS-Kanal — ohne die ' +
				'ADR-0050-Regel-3-Durchschreibung traegt der Server einen widerspruechlichen Stand'
		).toEqual(['wind_max_kmh', 'precip_sum_mm']);

		const h = await oeffneUebersicht(page, presetId);
		await waehleKanal(h, 'sms');
		expect(await aktiveMetriken(h), 'AC-S8-4 FAIL: SMS-Reiter nach Abwahl + Neuladen').toEqual(['wind_max_kmh', 'precip_sum_mm']);
		expect(
			await ausMetriken(h),
			'AC-S8-4 FAIL: nur die kanal-eigene Abwahl gehoert in die Aus-Gruppe — eine GLOBAL abgewaehlte Groesse ' +
				'ist nirgends mehr erreichbar (ADR-0050 Regel 1)'
		).toEqual(['pop_max_pct']);
	});

	test('AC-S8-11/AC-S8-6: ein bewusst geleerter SMS-Reiter bleibt leer (kein Rueckfall auf die Grundauswahl), ein wieder eingeschalteter Wert bleibt aktiv', async ({
		page, request
	}) => {
		const presetId = await createUebersichtPreset(request, `1703-s8-leerauswahl-${Date.now()}`, M);
		const f = await oeffneUebersicht(page, presetId);
		await waehleKanal(f, 'sms');
		for (const m of M) await ausSchalten(f, m);
		expect(
			await gespeicherteKanalAuswahl(request, presetId, 'sms'),
			'AC-S8-11 FAIL: die bewusste Leerauswahl muss als [] gespeichert sein. `null` hiesse "Schluessel ' +
				'weggelassen" — der Go-Merge liesse dann den ALTEN Stand stehen (M5)'
		).toEqual([]);

		const g = await oeffneUebersicht(page, presetId);
		await waehleKanal(g, 'sms');
		// Positiver Anker ZUERST: erst damit ist die leere aktive Liste darunter
		// eine Aussage und kein "noch nicht geladen" (#1423-Lehre).
		expect(await ausMetriken(g), 'AC-S8-11 FAIL: Aus-Gruppe nach dem Neuladen').toEqual(M);
		expect(
			await aktiveMetriken(g),
			'AC-S8-11 FAIL: der SMS-Reiter faellt nach dem Neuladen auf die Grundauswahl zurueck — "bewusst leer" ' +
				'ist nicht von "nie eingestellt" unterschieden worden'
		).toEqual([]);

		// AC-S8-6: auch die Umkehrung ueberlebt Speichern + Neuladen.
		await einSchalten(g, 'pop_max_pct');
		const h = await oeffneUebersicht(page, presetId);
		await waehleKanal(h, 'sms');
		expect(await aktiveMetriken(h), 'AC-S8-6 FAIL: wieder eingeschaltete Groesse nach dem Neuladen nicht aktiv').toEqual(['pop_max_pct']);
	});

	test('Rollback (CompareTabs.svelte:782): scheitert der PUT, faellt auch die Kanal-Ebene auf den zuletzt gespeicherten Stand zurueck', async ({
		page, request
	}) => {
		const presetId = await createUebersichtPreset(request, `1703-s8-rollback-${Date.now()}`, M);
		await page.route('**/api/compare/presets/**', async (route) => {
			if (route.request().method() !== 'PUT') return route.continue();
			await route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"E2E-Simulation"}' });
		});
		const f = await oeffneUebersicht(page, presetId);
		await waehleKanal(f, 'sms');
		await f.reihenfolge.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="pop_max_pct"]')
			.getByRole('button', { name: 'Aus', exact: true }).click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', { timeout: 25_000 });
		await expect.poll(() => aktiveMetriken(f), {
			message: 'FAIL: nach gescheitertem Speichern muss die Kanal-Ebene auf den Serverstand zurueckfallen — ' +
				'sonst zeigt der Editor eine Auswahl, die nirgends gespeichert ist',
			timeout: 15_000
		}).toEqual(M);
	});
});
