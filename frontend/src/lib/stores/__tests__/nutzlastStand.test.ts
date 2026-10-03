// Fix-Loop 3, Issue #1433 — Merge-Regel des Seitenstands: Stand ⊕ Nutzlast, einstufig wie
// der Go-Server (`mergeConfigMap`/`mergeBriefingPatch`). Reine Funktionen, kein Netz.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/stores/__tests__/nutzlastStand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { merkeNutzlast, nutzlastVon, wendeNutzlastAn, wendeNutzlastenAn } from '../nutzlastStand.ts';
import { createController } from '../../components/shared/__tests__/versandVergleichPruefstand.ts';

const stand = () => ({
	name: 'A',
	corridors: [{ m: 1 }],
	display_config: { x: 1, y: 2, metric_alert_levels: { wind: 'a', regen: 'b' } },
	report_config: { t: '07:00' }
});

describe('wendeNutzlastAn', () => {
	test('Top-Level ueberschreibt, fehlende Schluessel bleiben', () => {
		const n = wendeNutzlastAn(stand(), { name: 'B' });
		assert.equal(n.name, 'B');
		assert.deepEqual(n.corridors, [{ m: 1 }]);
	});

	test('Objekte auf beiden Seiten werden EINE Ebene tief gemergt; darunter wird ersetzt', () => {
		const n = wendeNutzlastAn(stand(), { display_config: { y: 9, metric_alert_levels: { wind: 'z' } } });
		assert.equal(n.display_config.x, 1, 'Geschwister bleiben');
		assert.equal(n.display_config.y, 9);
		assert.deepEqual(n.display_config.metric_alert_levels, { wind: 'z' }, 'zweite Ebene wird ersetzt, nicht gemergt');
		assert.deepEqual(n.report_config, { t: '07:00' });
	});

	test('Arrays werden ersetzt (auch leere), `undefined` wird uebersprungen, `null`/`false` werden geschrieben', () => {
		const n = wendeNutzlastAn(stand(), { corridors: [], name: undefined, display_config: { x: undefined, y: null } });
		assert.deepEqual(n.corridors, []);
		assert.equal(n.name, 'A');
		assert.equal(n.display_config.x, 1, 'undefined im Unterobjekt wird nie gesendet');
		assert.equal(n.display_config.y, null);
	});

	test('nie in-place: Eingabe unveraendert, Ergebnis eine neue Referenz; ohne Nutzlast dieselbe Referenz', () => {
		const s = stand();
		const kopie = JSON.stringify(s);
		const n = wendeNutzlastAn(s, { name: 'B', display_config: { y: 5 } });
		assert.equal(JSON.stringify(s), kopie);
		assert.notEqual(n, s);
		assert.equal(wendeNutzlastAn(s, undefined), s);
		assert.equal(wendeNutzlastAn(s, 'kein objekt'), s);
	});
});

describe('wendeNutzlastenAn', () => {
	test('Reihenfolge der Liste: spaeter gewinnt; Eintraege ohne Nutzlast zaehlen nicht', () => {
		const n = wendeNutzlastenAn(stand(), [{ nutzlast: { name: 'B' } }, {}, { nutzlast: { name: 'C' } }]);
		assert.equal(n.name, 'C');
	});
	test('leere Liste liefert denselben Stand', () => {
		const s = stand();
		assert.equal(wendeNutzlastenAn(s, []), s);
	});
});

describe('merkeNutzlast / nutzlastVon', () => {
	test('haengt die Nutzlast an die Funktion und gibt sie zurueck', () => {
		const fn = async () => {};
		assert.equal(nutzlastVon(fn), undefined);
		assert.equal(merkeNutzlast(fn, { a: 1 }), fn);
		assert.deepEqual(nutzlastVon(fn), { a: 1 });
	});
});

describe('SaveStatus.registriereAbgelehnt', () => {
	test('meldet die Nutzlast bei einem 412; die Abmeldung des ALTEN Rueckrufs haengt einen neueren nicht ab ({#key}-Neuaufbau)', () => {
		const ctl = createController('x-1');
		const a: unknown[] = [];
		const b: unknown[] = [];
		const abmeldenA = ctl.registriereAbgelehnt((n) => a.push(n));
		const abmeldenB = ctl.registriereAbgelehnt((n) => b.push(n)); // neue Instanz registriert VOR dem Abbau der alten
		abmeldenA(); // der alte Abbau laeuft danach
		const fn = merkeNutzlast(async () => {}, { name: 'N' });
		ctl.meldeKonflikt(fn, { status: 412 });
		assert.deepEqual(a, [], 'der alte Rueckruf bekommt nichts mehr');
		assert.deepEqual(b, [{ name: 'N' }], 'der neuere Rueckruf bleibt aktiv');
		abmeldenB();
		ctl.meldeKonflikt(fn, { status: 412 });
		assert.equal(b.length, 1, 'nach der eigenen Abmeldung kommt nichts mehr an');
	});

	test('ein Eintrag ohne Nutzlast loest keinen Rueckruf aus', () => {
		const ctl = createController('x-2');
		const got: unknown[] = [];
		ctl.registriereAbgelehnt((n) => got.push(n));
		ctl.meldeKonflikt(async () => {}, { status: 412 });
		assert.deepEqual(got, []);
	});
});
