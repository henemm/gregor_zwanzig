// Fix-Loop 1 — Issue #3007 (Epic #2913), Adversary F002 (AC-11, AC-12): die reinen Funktionen
// der Etappen-Listenzeile (`edit/etappenListe.ts`) mit den Randfällen, die der SSR-Test nicht abdeckt.
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md — AC-10 bis AC-12.
//
// Geprüft wird das ECHTE Modul mit dem ECHTEN Katalog (trFor) und der ECHTEN Gehzeit-Rechnung
// (computeArrivalTimes/activityToSpeed). Kein Mock. Die Sollwerte entstehen unabhängig:
//   - Gehzeit über Mitternacht = dieselbe Etappe mit Start 00:00 (dort kein Übertrag nötig);
//   - Tempo = activityToSpeed der Aktivität (Fahrrad ≠ Wandern).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/edit/__tests__/etappenListe_3007.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { etappenZeile, gehzeitMinuten, dauerText, etappenAufteilung } from '../etappenListe.ts';
import { computeArrivalTimes, activityToSpeed } from '../../../utils/naismith.ts';
import { computeHeaderStats } from '../../email-preview/headerStats.ts';
import { trFor } from '../../../i18n/index.ts';
import type { Stage } from '../../../types.ts';

type Lang = 'de' | 'en';
const katalog = (lang: Lang) => (key: any, params?: Record<string, string | number>) => trFor(lang, key, params);
const wp = (id: string, name: string, lat: number, lon: number, elevation_m: number) => ({ id, name, lat, lon, elevation_m });
const minuten = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3));
const zahl = (lang: Lang, v: number, n: number) =>
	new Intl.NumberFormat(lang === 'en' ? 'en-GB' : 'de-DE', { minimumFractionDigits: n, maximumFractionDigits: n }).format(v);

/** Gehzeit unabhängig: Start 00:00, letzte Ankunft = Dauer (Etappe < 24 h, kein Übertrag). */
function dauerAbMitternacht(stage: Stage, tempo: number): number {
	const arr = computeArrivalTimes({ ...stage, start_time: '00:00' } as Stage, '00:00', tempo);
	return minuten(arr[arr.length - 1]);
}

// ~11 km mit Aufstieg — zu Fuß gut 3 h, mit Start 23:00 also über Mitternacht.
const LANG: Stage = {
	id: 'm1',
	name: 'Nachtetappe',
	date: '2026-08-01',
	start_time: '23:00',
	waypoints: [wp('a', 'Start', 39.54, 2.39, 100), wp('b', 'Mitte', 39.58, 2.42, 500), wp('c', 'Ziel', 39.62, 2.44, 300)]
} as Stage;
// Flach: Aufstieg 0.
const FLACH: Stage = {
	id: 'f1',
	name: 'Flach',
	date: '2026-08-02',
	start_time: '08:00',
	waypoints: [wp('a', 'Deich', 53.5, 8.1, 2), wp('b', 'Siel', 53.55, 8.15, 2)]
} as Stage;
// Nur Abstieg: Aufstieg ebenfalls 0, Abstieg > 0.
const BERGAB: Stage = {
	id: 'b1',
	name: 'Bergab',
	date: '2026-08-03',
	start_time: '09:00',
	waypoints: [wp('a', 'Hütte', 47.0, 11.0, 2200), wp('b', 'Tal', 47.03, 11.02, 900)]
} as Stage;

// Fix-Loop AC-12: gleiche Koordinate, nur Höhe ändert sich — Distanz 0, Aufstieg 400 + 850 = 1250 m.
const STEIL: Stage = {
	id: 's1',
	name: 'Steil',
	date: '2026-08-05',
	start_time: '07:00',
	waypoints: [wp('a', 'Fuß', 46.5, 8.0, 1000), wp('b', 'Mitte', 46.5, 8.0, 1400), wp('c', 'Gipfel', 46.5, 8.0, 2250)]
} as Stage;
// ~33 m Luftlinie (0,0003° Breite) — gerundet „0,0 km“ gilt als fehlend; Aufstieg 40 m.
const KURZ_STEIL: Stage = {
	id: 'k1',
	name: 'Kurz',
	date: '2026-08-06',
	start_time: '07:00',
	waypoints: [wp('a', 'Unten', 46.5, 8.0, 1000), wp('b', 'Oben', 46.5003, 8.0, 1040)]
} as Stage;
// Zwei Wegpunkte, gleiche Koordinate und Höhe — Distanz 0, Aufstieg 0.
const STILL: Stage = {
	id: 'h1',
	name: 'Still',
	date: '2026-08-07',
	start_time: '07:00',
	waypoints: [wp('a', 'Hof', 46.5, 8.0, 500), wp('b', 'Hof', 46.5, 8.0, 500)]
} as Stage;

describe('#3007 F002: Gehzeit (AC-11)', () => {
	test('über Mitternacht: Dauer = dieselbe Etappe ab 00:00, nicht negativ', () => {
		const tempo = activityToSpeed(undefined);
		const arr = computeArrivalTimes(LANG, LANG.start_time, tempo);
		assert.ok(minuten(arr[arr.length - 1]) < minuten(arr[0]), 'Messaufbau: Etappe läuft nicht über Mitternacht');
		const soll = dauerAbMitternacht(LANG, tempo);
		assert.ok(soll > 60, `Messaufbau: Dauer ${soll} min zu kurz`);
		assert.equal(gehzeitMinuten(LANG, tempo), soll);
		const z = etappenZeile(LANG, 0, 'de', katalog('de'), tempo);
		assert.equal(z.meta, `Gehzeit ${dauerText(soll)}`);
	});
	test('Tempo der Aktivität geht ein (Fahrrad 20 km/h ≠ zu Fuß)', () => {
		const fuss = gehzeitMinuten(FLACH, activityToSpeed(undefined));
		const rad = gehzeitMinuten(FLACH, activityToSpeed('fahrrad_20'));
		assert.equal(fuss, dauerAbMitternacht(FLACH, activityToSpeed(undefined)));
		assert.equal(rad, dauerAbMitternacht(FLACH, 20));
		assert.ok(rad !== null && fuss !== null && rad < fuss, `Fahrrad ${rad} min nicht kürzer als zu Fuß ${fuss} min`);
	});
	test('ohne Strecke (unter zwei Wegpunkten) keine Gehzeit', () => {
		const eins = { ...FLACH, waypoints: [FLACH.waypoints[0]] } as Stage;
		assert.equal(gehzeitMinuten(eins, 4), null);
	});
	test('dauerText: h:mm mit führender Null bei Minuten', () => {
		assert.equal(dauerText(190), '3:10');
		assert.equal(dauerText(5), '0:05');
		assert.equal(dauerText(600), '10:00');
	});
});

describe('#3007 F002: Zeileninhalt (AC-10, AC-12)', () => {
	for (const lang of ['de', 'en'] as Lang[]) {
		test(`${lang}: Aufstieg 0 (flach) — nur Distanz, kein „↑0 m“, kein verwaistes „·“`, () => {
			const km = zahl(lang, computeHeaderStats(FLACH).distanceKm, 1);
			const z = etappenZeile(FLACH, 1, lang, katalog(lang), 4);
			assert.equal(z.titel, 'E2 · Deich → Siel');
			assert.equal(z.zweitzeile, `${km} km`);
			assert.ok(z.meta && z.meta.length > 0, 'Gehzeit fehlt bei flacher Etappe');
		});
		test(`${lang}: nur Abstieg — Aufstieg fehlt, nur Distanz`, () => {
			const st = computeHeaderStats(BERGAB);
			assert.ok(st.descentM > 0 && st.ascentM === 0, 'Messaufbau: Etappe nicht rein bergab');
			const z = etappenZeile(BERGAB, 0, lang, katalog(lang), 4);
			assert.equal(z.zweitzeile, `${zahl(lang, st.distanceKm, 1)} km`);
		});
		test(`${lang}: mit Aufstieg — „x km · ↑y m“ aus dem Katalog, Zahlen in Sprachformat`, () => {
			const st = computeHeaderStats(LANG);
			const z = etappenZeile(LANG, 2, lang, katalog(lang), 4);
			assert.equal(z.titel, 'E3 · Start → Ziel');
			assert.equal(z.zweitzeile, `${zahl(lang, st.distanceKm, 1)} km · ↑${zahl(lang, Math.round(st.ascentM), 0)} m`);
		});
		test(`${lang}: Pausentag — nur Titel, keine Kennzahlen, keine Gehzeit`, () => {
			const pause = { id: 'p', name: 'Pausentag', date: '2026-08-04', waypoints: [] } as unknown as Stage;
			const z = etappenZeile(pause, 3, lang, katalog(lang), 4);
			assert.equal(z.titel, 'E4 · Pausentag');
			assert.equal(z.zweitzeile, undefined);
			assert.equal(z.meta, undefined);
		});
		test(`${lang}: Pausentag ohne Namen — Titel mit Katalogwort für Pausentag`, () => {
			const pause = { id: 'p', name: '', date: '2026-08-04', waypoints: [] } as unknown as Stage;
			const z = etappenZeile(pause, 0, lang, katalog(lang), 4);
			assert.equal(z.titel, `E1 · ${trFor(lang, 'bausteine.etappe.pausentag' as any)}`);
			assert.equal(z.zweitzeile, undefined);
			assert.equal(z.meta, undefined);
		});
		test(`${lang}: Distanz 0, Aufstieg > 0 — nur „↑y m“, kein „0,0 km“, kein verwaistes „·“`, () => {
			const st = computeHeaderStats(STEIL);
			assert.ok(st.distanceKm === 0 && st.ascentM > 0, 'Messaufbau: Etappe hat Distanz oder keinen Aufstieg');
			const z = etappenZeile(STEIL, 0, lang, katalog(lang), 4);
			assert.equal(z.titel, 'E1 · Fuß → Gipfel');
			assert.equal(z.zweitzeile, `↑${zahl(lang, 1250, 0)} m`);
			assert.equal(z.meta, `${trFor(lang, 'trip.hub.etappe_gehzeit' as any, { dauer: dauerText(dauerAbMitternacht(STEIL, 4)) })}`);
		});
		test(`${lang}: Distanz gerundet 0,0 (≈ 30 m), Aufstieg > 0 — nur „↑y m“`, () => {
			const st = computeHeaderStats(KURZ_STEIL);
			assert.ok(st.distanceKm > 0 && st.distanceKm < 0.05 && st.ascentM > 0, `Messaufbau: Distanz ${st.distanceKm}`);
			const z = etappenZeile(KURZ_STEIL, 0, lang, katalog(lang), 4);
			assert.equal(z.zweitzeile, `↑${zahl(lang, 40, 0)} m`);
		});
		test(`${lang}: Distanz 0 und Aufstieg 0 (zwei Wegpunkte) — keine Zweitzeile, Titel und Gehzeit wie bisher`, () => {
			const st = computeHeaderStats(STILL);
			assert.ok(st.distanceKm === 0 && st.ascentM === 0, 'Messaufbau: Etappe hat Distanz oder Aufstieg');
			const z = etappenZeile(STILL, 1, lang, katalog(lang), 4);
			assert.equal(z.titel, 'E2 · Hof → Hof');
			assert.equal(z.zweitzeile, undefined);
			assert.equal(z.meta, `${trFor(lang, 'trip.hub.etappe_gehzeit' as any, { dauer: dauerText(dauerAbMitternacht(STILL, 4)) })}`);
		});
		test(`${lang}: nur ein Wegpunkt — Titel mit Namen, ohne Kennzahlen und Gehzeit`, () => {
			const eins = { ...FLACH, name: 'Einzeln', waypoints: [FLACH.waypoints[0]] } as Stage;
			const z = etappenZeile(eins, 0, lang, katalog(lang), 4);
			assert.equal(z.titel, 'E1 · Einzeln');
			assert.equal(z.zweitzeile, undefined);
			assert.equal(z.meta, undefined);
		});
	}
});

// Fix-Runde 3 (Adversary F002, AC-13): Zeilen um den offenen Editor. EditStagesPanelNew rendert
// `vor`, dann den Editor-Block, dann `nach`. Sollwert unabhängig: Reihenfolge der Kennungen.
describe('#3007 F002: Aufteilung der Etappenzeilen um den offenen Editor (AC-13)', () => {
	const ids = ['a', 'b', 'c', 'd', 'e'];
	test('keine Etappe offen: alle Zeilen vor dem (fehlenden) Editor, keine danach', () => {
		assert.deepEqual(etappenAufteilung(ids, -1), { vor: ids, nach: [] });
	});
	for (let offen = 0; offen < ids.length; offen++) {
		test(`Etappe ${offen + 1} offen: offene Zeile zuletzt vor dem Editor, alle weiteren danach, vollständig und in Reihenfolge`, () => {
			const { vor, nach } = etappenAufteilung(ids, offen);
			assert.equal(vor[vor.length - 1], ids[offen]);
			assert.deepEqual(nach, ids.filter((_, i) => i > offen));
			assert.deepEqual([...vor, ...nach], ids);
		});
	}
	test('Index außerhalb (Etappe gerade gelöscht): nichts verloren, nichts doppelt', () => {
		assert.deepEqual(etappenAufteilung(ids, ids.length), { vor: ids, nach: [] });
	});
	test('leere Liste', () => {
		assert.deepEqual(etappenAufteilung([], 0), { vor: [], nach: [] });
	});
});
