// E2E (Staging) — #1703 Scheibe 8: Bedienung + Kappungs-Aussage der
// kanal-eigenen Metrikauswahl der Vergleichs-Uebersichtstabelle.
// ACs: AC-S8-3, AC-S8-5, AC-S8-9, AC-S8-12, AC-S8-13. AC-S8-7/AC-S8-8
// (zugestellte Ausgabe) laufen BEWUSST ueber den Mail-Validator in
// /e2e-verify, nicht als Klickpfad.
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md § Testauflage
// (Buendel `…kanal-tabs-sichtbar` + `…kappungsaussage`, zusammengezogen).
// Aufbau, Selektoren, #1423-Warteregel, Ausfuehrbefehl: ./compare-uebersicht-kanal.helpers.ts

import { test, expect } from '@playwright/test';
import { cleanupTracked } from './helpers';
import {
	EINFACHE_METRIKEN, aktiveMetriken, ausMetriken, ausSchalten, createUebersichtPreset,
	einSchalten, klickUndSpeichere, oeffneUebersicht, waehleKanal
} from './compare-uebersicht-kanal.helpers';

test.describe('#1703 S8: Kanal-Reiter der Vergleichs-Uebersicht — Bedienung und Kappungs-Aussage', () => {
	test.afterAll(async ({ request }) => await cleanupTracked(request));

	test('AC-S8-12/AC-S8-13: drei Kanal-Reiter, Umschalten wirkt, SMS nennt 153 an Reiter UND Hinweis, Telegram kappt nach der siebten Zeile', async ({
		page, request
	}) => {
		const presetId = await createUebersichtPreset(request, `1703-s8-kappung-${Date.now()}`, EINFACHE_METRIKEN);
		const f = await oeffneUebersicht(page, presetId);
		for (const ch of ['email', 'telegram', 'sms'] as const) {
			await expect(f.layout.getByTestId(`channel-tab-${ch}`), `AC-S8-12 FAIL: Kanal-Reiter "${ch}" fehlt`).toBeVisible();
		}
		// Ohne eigenen Override folgt jeder Kanal der Grundauswahl — in DEREN Reihenfolge.
		await expect.poll(() => aktiveMetriken(f), { timeout: 10_000 }).toEqual(EINFACHE_METRIKEN);

		await waehleKanal(f, 'telegram');
		// Die Kapplinie steht IM Listenfluss: gepruefte Zusicherung ist ihre
		// POSITION (7 Metrik-Zeilen davor), nicht ihr blosses Dasein.
		const folge = await f.reihenfolge
			.locator('[data-testid="wm2-reihenfolge-row"], [data-testid="wm2-cut-line"]')
			.evaluateAll((els) => els.map((e) => e.getAttribute('data-testid')));
		expect(folge.indexOf('wm2-cut-line'), `AC-S8-13 FAIL: Kapplinie nicht nach Zeile 7 — DOM-Folge: ${folge.join(',')}`).toBe(7);
		await expect(
			f.layout.getByTestId('lt-cap-note'),
			'AC-S8-13 FAIL: gezaehlt werden METRIK-ZEILEN (hasLabelColumn=false); "N Spalten (Label + …)" waere ' +
				'der Default des seit #1360 aufgeloesten Layout-Reiters (M6)'
		).toHaveText(/^Telegram: 9 Metriken · /);

		await waehleKanal(f, 'sms');
		const smsReiter = f.layout.getByTestId('channel-tab-sms');
		await expect(
			smsReiter,
			'AC-S8-12 FAIL: der Kanal-Aufkleber muss die Vergleichsgrenze 153 nennen (channel_layout.py:45-54) — ' +
				'160 ist die TRIP-Grenze und hier falsch (M7)'
		).toContainText('153');
		await expect(smsReiter).not.toContainText('160');
		await expect(f.layout.getByTestId('lt-cap-note'), 'AC-S8-12 FAIL: Aufkleber und Hinweis muessen DIESELBE Zahl nennen')
			.toContainText('153 Zeichen');
	});

	test('AC-S8-9/AC-S8-5/AC-S8-3: ein Kanal-Edit loest GENAU EINEN PUT aus, "Aus in diesem Kanal" ist umkehrbar, eine globale Abwahl verschwindet sofort', async ({
		page, request
	}) => {
		const presetId = await createUebersichtPreset(request, `1703-s8-bedienung-${Date.now()}`, EINFACHE_METRIKEN);
		const f = await oeffneUebersicht(page, presetId);
		// AC-S8-9 wird auf der NETZWERK-Ebene gezaehlt: an jedem Klick haengen zwei
		// Commit-Pfade (onCompareCommit + Wrapper-onclick, CompareTabs.svelte) —
		// nur der Diff-Guard verhindert den zweiten PUT.
		const puts: string[] = [];
		page.on('request', (r) => {
			if (r.method() === 'PUT' && r.url().includes('/api/compare/presets/')) puts.push(r.url());
		});

		await waehleKanal(f, 'telegram');
		await waehleKanal(f, 'sms');
		await page.waitForTimeout(1500);
		expect(puts, 'AC-S8-9 FAIL: ein blosser Kanal-WECHSEL ist keine Aenderung und darf nichts speichern').toHaveLength(0);

		await ausSchalten(f, 'pop_max_pct');
		await page.waitForTimeout(1500);
		expect(puts, `AC-S8-9 FAIL: eine Aenderung im SMS-Reiter muss GENAU EINEN PUT ausloesen, gezaehlt: ${puts.length}`).toHaveLength(1);
		await expect.poll(() => aktiveMetriken(f), { timeout: 10_000 }).not.toContain('pop_max_pct');

		// AC-S8-5: "Aus" ist ein Zustand, keine Loeschung — dieselbe Groesse laesst
		// sich im selben Kanal wieder einschalten (ohne Positions-Erinnerung: ans Ende).
		await einSchalten(f, 'pop_max_pct');

		// AC-S8-3: Abwahl in der Grundauswahl, SMS-Reiter bleibt offen, KEIN Reload.
		// Zusicherung POSITIV auf die ganze Liste — ein blosses `not.toContain` waere
		// auch dann gruen, wenn gar nichts gerendert haette.
		await klickUndSpeichere(f, f.grundauswahl.locator('input[data-metric-key="sunny_hours_h"]'));
		await expect.poll(() => aktiveMetriken(f), {
			message: 'AC-S8-3/AC-S8-5 FAIL: der SMS-Reiter muss "sunny_hours_h" SOFORT verlieren (global abgewaehlt) ' +
				'und "pop_max_pct" am Ende wieder fuehren (wieder eingeschaltet)',
			timeout: 10_000
		}).toEqual([
			'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm', 'thunder_level_max',
			'cloud_avg_pct', 'uv_index_max', 'visibility_min_m', 'pop_max_pct'
		]);
		await expect.poll(() => ausMetriken(f), {
			message: 'AC-S8-3 FAIL: eine GLOBAL abgewaehlte Groesse darf auch nicht in der Aus-Gruppe des Kanals ' +
				'stehen — kein Kanal kann sie zurueckholen (ADR-0050 Regel 1)',
			timeout: 10_000
		}).toEqual([]);
	});
});
