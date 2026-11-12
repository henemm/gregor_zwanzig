// TDD RED — Issue #2794 S3a Teil-PR 4a (AC-43, AC-44, AC-45):
// Die Vorbelegung der Wertebereiche (`corridors`) beim Anlegen lief bisher in
// einem unsichtbar gemounteten CorridorEditor (Trip: `vorbelegen()` +
// `onVorbelegungFertig`, Vergleich: `isFreshCompareCreate` -> `syncToWizard`).
// Bevor die Komponente geloescht wird, muss dieselbe Logik als reine Funktion
// unter `shared/wetter-tab/anlegeVorbelegung.ts` stehen (ein Modul fuer beide
// Kontexte, #1170).
//
// Vertrag (von der Implementierung einzuhalten):
//
//   tripVorbelegung({ metrics, extraDefs, vorhandeneCorridors }): Corridor[] | null
//     -> null, wenn schon Korridore stehen, keine Metrik aktiv ist, keine
//        Zeile vorzubelegen ist oder die Zeilen ungueltig waeren
//        (saveGateDecision !== 'schedule'); sonst genau die Korridore, die der
//        alte CorridorEditor per onCorridorsChange gemeldet hat.
//
//   erstelleTripVorbelegungsLauf({ onCorridors, onFertig })
//     .versuchen({ extraDefs, metrics, vorhandeneCorridors }) / .fertig
//     -> wartet, solange `extraDefs === null` (Zusatz-Katalog noch nicht da)
//        oder keine Metrik gemeldet ist; danach GENAU EINMAL: Korridore
//        melden (falls vorhanden), dann `onFertig` — auch wenn nichts
//        vorzubelegen ist. Jeder weitere Versuch ist wirkungslos (Mobil/Desktop-
//        Wechsel belegt nicht doppelt vor).
//
//   vergleichVorbelegung(wiz, defs): { corridors, idealRanges,
//       activeMetricKeys, metricAlertLevels } | null
//     -> null im Bearbeiten-Modus oder wenn `wiz.corridors` nicht leer ist
//        (Nutzereingaben bleiben); sonst das Ergebnis, das der alte Editor per
//        syncToWizard in den Wizard gespiegelt hat.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/wetter-tab/__tests__/anlege_vorbelegung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	tripVorbelegung,
	erstelleTripVorbelegungsLauf,
	vergleichVorbelegung,
} from '../anlegeVorbelegung.ts';
// Referenz „wie vorher": dieselben Bausteine, die der geloeschte Editor
// aufgerufen hat — am NEUEN Ort (Umzug aus corridor-editor/, AC-47).
import {
	buildRoutePrefillRows,
	buildCorridorSavePayload,
	buildComparePrefillRows,
	buildCompareCorridorSavePayload,
	type CompareMetricDef,
} from '../corridorEditorState.ts';
import { buildCompareMetricDefs, buildRouteMetricDefsFromCatalog } from '../compareMetricCatalogLoader.ts';
import type { Corridor } from '../../../../types.ts';

// Auszug der Endpoint-Antwort GET /api/compare/metrics (1:1 aus der Fixture in
// corridorEditorState.test.ts, nur die vom Profil ALLGEMEIN/WINTERSPORT und
// vom Trip-Standard benoetigten Eintraege).
const KATALOG = {
	metrics: [
		{ key: 'snow_depth_cm', label: 'Schneehöhe', aggregation_label: 'Maximum', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5, alarmCapable: false },
		{ key: 'snow_new_sum_cm', label: 'Neuschnee', aggregation_label: 'Summe', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 50, step: 1, alarmCapable: true },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden', aggregation_label: 'Summe', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, alarmCapable: false },
		{ key: 'wind_max_kmh', label: 'Wind', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: true },
		{ key: 'cloud_avg_pct', label: 'Bewölkung', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'visibility_min_m', label: 'Sichtweite', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500, alarmCapable: true },
		{ key: 'precip_sum_mm', label: 'Niederschlag', aggregation_label: 'Summe', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5, alarmCapable: true },
		{ key: 'temp_max_c', label: 'Temperatur', aggregation_label: 'Maximum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, alarmCapable: true },
		{ key: 'gust_max_kmh', label: 'Böen', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, alarmCapable: true },
	],
} as never;

const EXTRA_DEFS = buildRouteMetricDefsFromCatalog((KATALOG as { metrics: never[] }).metrics);
const COMPARE_DEFS: CompareMetricDef[] = buildCompareMetricDefs(KATALOG);

// Trip-Anlege-Standard (metric_catalog.py trip_default_rank), wie in
// corridorEditorState.test.ts › buildRoutePrefillRows.
const TRIP_STANDARD = [
	{ metric_id: 'temperature', enabled: true },
	{ metric_id: 'wind', enabled: true },
	{ metric_id: 'gust', enabled: true },
	{ metric_id: 'precipitation', enabled: true },
	{ metric_id: 'freezing_level', enabled: true },
	{ metric_id: 'snowfall_limit', enabled: false },
	{ metric_id: 'thunder', enabled: true },
] as never;

/** Was der alte CorridorEditor (createMode, route) per onCorridorsChange meldete. */
function altTripKorridore(metrics: never, extra = EXTRA_DEFS): Corridor[] {
	return buildCorridorSavePayload(buildRoutePrefillRows(metrics, extra), {}, []).corridors;
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-43 — Trip: corridors im Anlege-POST, Fertig-Signal genau einmal
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-43 tripVorbelegung — reine Funktion', () => {
	test('Trip-Standard ⇒ dieselben fuenf Korridore wie der alte Editor (Startwerte, notify, kein mark)', () => {
		const c = tripVorbelegung({ metrics: TRIP_STANDARD, extraDefs: EXTRA_DEFS, vorhandeneCorridors: [] });
		assert.ok(c, 'Vorbelegung FAIL: Trip-Standard liefert keine Korridore — der Anlege-POST traegt corridors: []');
		assert.deepEqual(
			c.map((k) => [k.metric, k.range, k.notify, k.mark]),
			[
				['wind_gust', [null, 70], true, false],
				['precipitation_sum', [null, 5], true, false],
				['temperature_min', [-5, null], true, false],
				['temperature_max', [null, 28], true, false],
				['snow_line', [1500, null], true, false],
			],
			'Vorbelegung weicht von den PO-freigegebenen Startwerten ab'
		);
		assert.deepEqual(c, altTripKorridore(TRIP_STANDARD), 'Vorbelegung weicht vom Stand vor der Entfernung des Editors ab');
	});

	test('keine aktive Metrik ⇒ null (nichts vorzubelegen)', () => {
		assert.equal(tripVorbelegung({ metrics: [] as never, extraDefs: EXTRA_DEFS, vorhandeneCorridors: [] }), null);
		assert.equal(tripVorbelegung({ metrics: undefined, extraDefs: EXTRA_DEFS, vorhandeneCorridors: [] }), null);
	});

	test('nur Metriken ohne Startwert ⇒ null, nicht leere Liste', () => {
		const ohneStartwert = [{ metric_id: 'thunder', enabled: true }] as never;
		assert.equal(tripVorbelegung({ metrics: ohneStartwert, extraDefs: EXTRA_DEFS, vorhandeneCorridors: [] }), null);
	});

	test('bereits vorhandene Korridore ⇒ null (keine Ueberschreibung)', () => {
		const vorhanden: Corridor[] = [{ metric: 'wind_gust', range: [null, 50], notify: true, mark: false }];
		assert.equal(
			tripVorbelegung({ metrics: TRIP_STANDARD, extraDefs: EXTRA_DEFS, vorhandeneCorridors: vorhanden }),
			null,
			'Vorbelegung FAIL: vorhandene Wertebereiche wuerden ueberschrieben'
		);
	});

	test('Zusatz-Katalog fehlgeschlagen (extraDefs leer) ⇒ trotzdem die fest verdrahteten Startwerte', () => {
		const c = tripVorbelegung({ metrics: TRIP_STANDARD, extraDefs: [], vorhandeneCorridors: [] });
		assert.deepEqual(c, altTripKorridore(TRIP_STANDARD, []));
	});
});

describe('AC-43/AC-45 erstelleTripVorbelegungsLauf — Fertig-Signal genau einmal', () => {
	function lauf() {
		const gemeldet: Corridor[][] = [];
		let fertig = 0;
		const l = erstelleTripVorbelegungsLauf({
			onCorridors: (c: Corridor[]) => gemeldet.push(c),
			onFertig: () => { fertig += 1; },
		});
		return { l, gemeldet, anzahlFertig: () => fertig };
	}

	test('Katalog noch nicht geladen ⇒ kein Signal, keine Korridore', () => {
		const { l, gemeldet, anzahlFertig } = lauf();
		l.versuchen({ extraDefs: null, metrics: TRIP_STANDARD, vorhandeneCorridors: [] });
		assert.equal(anzahlFertig(), 0);
		assert.equal(gemeldet.length, 0);
		assert.equal(l.fertig, false);
	});

	test('Metriken noch nicht gemeldet ⇒ wartet, danach genau ein Lauf', () => {
		const { l, gemeldet, anzahlFertig } = lauf();
		l.versuchen({ extraDefs: EXTRA_DEFS, metrics: [] as never, vorhandeneCorridors: [] });
		assert.equal(anzahlFertig(), 0, 'Race FAIL: Fertig gemeldet, bevor die Metrik-Auswahl vorliegt');
		l.versuchen({ extraDefs: EXTRA_DEFS, metrics: TRIP_STANDARD, vorhandeneCorridors: [] });
		assert.equal(anzahlFertig(), 1);
		assert.deepEqual(gemeldet, [altTripKorridore(TRIP_STANDARD)]);
	});

	test('Korridore werden VOR dem Fertig-Signal gemeldet (Standardwerte-Knopf speichert sie mit)', () => {
		const reihenfolge: string[] = [];
		const l = erstelleTripVorbelegungsLauf({
			onCorridors: () => reihenfolge.push('corridors'),
			onFertig: () => reihenfolge.push('fertig'),
		});
		l.versuchen({ extraDefs: EXTRA_DEFS, metrics: TRIP_STANDARD, vorhandeneCorridors: [] });
		assert.deepEqual(reihenfolge, ['corridors', 'fertig']);
		assert.equal(l.fertig, true);
	});

	test('nichts vorzubelegen ⇒ trotzdem genau ein Fertig-Signal, keine Korridore', () => {
		const { l, gemeldet, anzahlFertig } = lauf();
		l.versuchen({ extraDefs: EXTRA_DEFS, metrics: [{ metric_id: 'thunder', enabled: true }] as never, vorhandeneCorridors: [] });
		assert.equal(anzahlFertig(), 1, 'Race FAIL: ohne Vorbelegung bleibt der Standardwerte-Knopf fuer immer gesperrt');
		assert.equal(gemeldet.length, 0);
	});

	test('wiederholte Versuche (Effekt laeuft erneut, Mobil/Desktop-Wechsel) ⇒ kein zweiter Lauf', () => {
		const { l, gemeldet, anzahlFertig } = lauf();
		for (let i = 0; i < 4; i++) {
			l.versuchen({ extraDefs: EXTRA_DEFS, metrics: TRIP_STANDARD, vorhandeneCorridors: [] });
		}
		assert.equal(anzahlFertig(), 1, 'AC-45 FAIL: Fertig-Signal mehrfach');
		assert.equal(gemeldet.length, 1, 'AC-45 FAIL: Vorbelegung doppelt ausgefuehrt');
	});

	test('Nutzer hat vor dem Katalog schon Korridore gesetzt ⇒ Fertig, aber keine Ueberschreibung', () => {
		const { l, gemeldet, anzahlFertig } = lauf();
		const eigen: Corridor[] = [{ metric: 'wind_gust', range: [null, 40], notify: true, mark: false }];
		l.versuchen({ extraDefs: EXTRA_DEFS, metrics: TRIP_STANDARD, vorhandeneCorridors: eigen });
		assert.equal(anzahlFertig(), 1);
		assert.equal(gemeldet.length, 0);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-44 — Vergleich: nur bei leeren Wertebereichen, Nutzereingaben bleiben
// ═══════════════════════════════════════════════════════════════════════════

/** Was der alte CorridorEditor (vergleich, isFreshCompareCreate) per syncToWizard spiegelte. */
function altVergleich(profil: Parameters<typeof buildComparePrefillRows>[0], wiz: { idealRanges?: object; activeMetricKeys?: string[]; metricAlertLevels?: object }) {
	return buildCompareCorridorSavePayload(buildComparePrefillRows(profil, COMPARE_DEFS), [], {
		idealRanges: (wiz.idealRanges ?? {}) as never,
		activeMetricKeys: wiz.activeMetricKeys ?? [],
		metricAlertLevels: (wiz.metricAlertLevels ?? {}) as never,
	}, []);
}

describe('AC-44 vergleichVorbelegung — reine Funktion', () => {
	test('leere Wertebereiche, Profil wintersport ⇒ Profil-Vorbelegung wie vorher (alle vier Felder)', () => {
		const wiz = { corridors: [], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: 'wintersport' as const, isEditMode: false };
		const r = vergleichVorbelegung(wiz, COMPARE_DEFS);
		assert.ok(r, 'Vorbelegung FAIL: frisches Orts-Briefing bekommt keine Wertebereiche');
		assert.deepEqual(r, altVergleich('WINTERSPORT', wiz));
		assert.deepEqual(
			r.corridors.map((c) => c.metric),
			['snow_depth_cm', 'snow_new_sum_cm', 'sunny_hours_h', 'wind_max_kmh', 'cloud_avg_pct']
		);
		assert.deepEqual(r.idealRanges.wind_max_kmh, { min: 0, max: 40 });
	});

	test('ohne Profil ⇒ ALLGEMEIN', () => {
		const wiz = { corridors: [], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: null, isEditMode: false };
		assert.deepEqual(vergleichVorbelegung(wiz, COMPARE_DEFS), altVergleich('ALLGEMEIN', wiz));
	});

	test('bestehende idealRanges/activeMetricKeys/metricAlertLevels werden per Read-Modify-Write uebernommen', () => {
		const wiz = {
			corridors: [], activityProfile: 'allgemein' as const, isEditMode: false,
			idealRanges: { gust_max_kmh: { max: 60 } },
			activeMetricKeys: ['gust_max_kmh'],
			metricAlertLevels: { gust_max_kmh: 'high' },
		};
		const r = vergleichVorbelegung(wiz, COMPARE_DEFS);
		assert.ok(r);
		assert.deepEqual(r.idealRanges.gust_max_kmh, { max: 60 }, 'RMW FAIL: vorhandener Idealwert verloren');
		assert.ok(r.activeMetricKeys.includes('gust_max_kmh'));
		assert.equal(r.metricAlertLevels.gust_max_kmh, 'high');
	});

	test('Nutzer hat Wertebereiche geaendert ⇒ null (Reiterwechsel ueberschreibt nichts)', () => {
		const eigen: Corridor[] = [{ metric: 'wind_max_kmh', range: [0, 25], notify: true, mark: true }];
		const wiz = { corridors: eigen, idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: 'wintersport' as const, isEditMode: false };
		assert.equal(vergleichVorbelegung(wiz, COMPARE_DEFS), null, 'AC-44 FAIL: Nutzereingabe wuerde ueberschrieben');
	});

	test('Bearbeiten-Modus ⇒ null', () => {
		const wiz = { corridors: [], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: 'wintersport' as const, isEditMode: true };
		assert.equal(vergleichVorbelegung(wiz, COMPARE_DEFS), null);
	});

	test('Katalog ohne Profil-Metriken ⇒ null', () => {
		const wiz = { corridors: [], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: 'wintersport' as const, isEditMode: false };
		assert.equal(vergleichVorbelegung(wiz, []), null);
	});

	test('AC-45 Idempotenz: Ergebnis in den Wizard schreiben, zweiter Aufruf ⇒ null, Zustand unveraendert', () => {
		const wiz: Record<string, unknown> = { corridors: [], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: 'wintersport', isEditMode: false };
		const erst = vergleichVorbelegung(wiz as never, COMPARE_DEFS);
		assert.ok(erst);
		Object.assign(wiz, erst);
		const vorher = JSON.stringify(wiz);
		assert.equal(vergleichVorbelegung(wiz as never, COMPARE_DEFS), null, 'AC-45 FAIL: zweite Vorbelegung');
		assert.equal(JSON.stringify(wiz), vorher);
	});

	test('reine Funktion: Eingabe wird nicht veraendert', () => {
		const wiz = { corridors: [], idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {}, activityProfile: 'wintersport' as const, isEditMode: false };
		const vorher = JSON.stringify(wiz);
		vergleichVorbelegung(wiz, COMPARE_DEFS);
		assert.equal(JSON.stringify(wiz), vorher, 'Seiteneffekt: vergleichVorbelegung schreibt in den Wizard-Zustand');
	});
});
