// Issue #2999 — Tipp-Protokoll des Bausteins DatumFeld: ein vollständig getipptes Datum (acht
// Ziffern) wird nie still verändert; ein Datum, das es nicht gibt, wird als ungültig erkannt.
// Echte Klasse/Funktion, kein Mock. Die Wirkstelle im Browser prüft
// e2e/s2999-datumfeld-tag-31.spec.ts (Uhr eingefroren auf November und Februar).
// Spec: docs/specs/modules/fix_2999_datumfeld_tag_31.md (AC-1 bis AC-5, AC-8, AC-10)
//
// Vertrag (datumTipp.ts):
//   type Segment = 'day' | 'month' | 'year'
//   pruefeTipp(ziffern: string, reihenfolge: Segment[]): { ok: true, iso } | { ok: false }
//   new DatumTipp()
//     .taste(key, reihenfolge?)  -> null solange unvollständig; beim 8. Ziffern-Tastendruck das
//                                   Ergebnis von pruefeTipp (danach beginnt der Strom neu)
//     .laeuft                    -> true, sobald mindestens eine Ziffer im Strom steht
//     .zuruecksetzen()           -> Fokuswechsel/Klick: Strom beginnt neu
//   Reihenfolge-Standard: ['day', 'month', 'year'] (de-DE und en-GB).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/molecules/__tests__/datum_tipp.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { DatumTipp, pruefeTipp, type Segment } from '../datumTipp.ts';

const TMJ: Segment[] = ['day', 'month', 'year'];
const MTJ: Segment[] = ['month', 'day', 'year'];

/** Tippt eine Ziffernfolge in einen frischen Strom und liefert das Ergebnis der letzten Taste. */
function tippe(tipp: DatumTipp, ziffern: string, reihenfolge: Segment[] = TMJ) {
	let letztes: ReturnType<DatumTipp['taste']> = null;
	for (const z of ziffern) letztes = tipp.taste(z, reihenfolge);
	return letztes;
}

describe('pruefeTipp — gültige Daten kommen unverändert an', () => {
	for (const [ziffern, iso] of [
		['31032027', '2027-03-31'],
		['29022028', '2028-02-29'],
		['31122026', '2026-12-31'],
		['01012027', '2027-01-01'],
		['30042027', '2027-04-30'],
		['31052027', '2027-05-31'],
		['29022000', '2000-02-29']
	] as const) {
		test(`${ziffern} → ${iso}`, () => {
			assert.deepEqual(pruefeTipp(ziffern, TMJ), { ok: true, iso });
		});
	}

	test('Reihenfolge Monat zuerst wird beachtet (03312027 → 2027-03-31)', () => {
		assert.deepEqual(pruefeTipp('03312027', MTJ), { ok: true, iso: '2027-03-31' });
	});
});

describe('pruefeTipp — Daten, die es nicht gibt, sind ungültig (nie geklemmt)', () => {
	for (const [ziffern, grund] of [
		['31042027', 'April hat 30 Tage'],
		['29022027', '2027 ist kein Schaltjahr'],
		['30022028', 'Februar hat auch im Schaltjahr nur 29 Tage'],
		['00012027', 'Tag 0'],
		['32012027', 'Tag 32'],
		['15132027', 'Monat 13'],
		['15002027', 'Monat 0'],
		['29022100', '2100 ist kein Schaltjahr (durch 100, nicht durch 400 teilbar)'],
		['31062027', 'Juni hat 30 Tage'],
		['31092027', 'September hat 30 Tage'],
		['31112026', 'November hat 30 Tage'],
		['01010000', 'Jahr 0000 (nur vierstellige Jahre ab 1000)'],
		['01010999', 'Jahr 0999 (nur vierstellige Jahre ab 1000)']
	] as const) {
		test(`${ziffern} ungültig (${grund})`, () => {
			assert.deepEqual(pruefeTipp(ziffern, TMJ), { ok: false });
		});
	}

	test('Monat zuerst: 04312027 ist ungültig (31. April)', () => {
		assert.deepEqual(pruefeTipp('04312027', MTJ), { ok: false });
	});
});

describe('DatumTipp — segmentübergreifender Ziffernstrom', () => {
	test('erst die 8. Ziffer liefert das Ergebnis, davor null; laeuft ab der ersten Ziffer', () => {
		const tipp = new DatumTipp();
		assert.equal(tipp.laeuft, false);
		for (const [i, z] of [...'3103202'].entries()) {
			assert.equal(tipp.taste(z, TMJ), null, `Ziffer ${i + 1} darf noch kein Ergebnis liefern`);
			assert.equal(tipp.laeuft, true);
		}
		assert.deepEqual(tipp.taste('7', TMJ), { ok: true, iso: '2027-03-31' });
	});

	test('Standard-Reihenfolge ohne Angabe ist Tag-Monat-Jahr', () => {
		const tipp = new DatumTipp();
		let letztes: ReturnType<DatumTipp['taste']> = null;
		for (const z of '31032027') letztes = tipp.taste(z);
		assert.deepEqual(letztes, { ok: true, iso: '2027-03-31' });
	});

	test('ungültiges Datum über den Strom → { ok: false }', () => {
		assert.deepEqual(tippe(new DatumTipp(), '31042027'), { ok: false });
		assert.deepEqual(tippe(new DatumTipp(), '29022027'), { ok: false });
	});

	test('nach dem Ergebnis beginnt der Strom neu (nächstes Datum direkt dahinter)', () => {
		const tipp = new DatumTipp();
		assert.deepEqual(tippe(tipp, '31042027'), { ok: false });
		assert.equal(tipp.laeuft, false, 'nach dem 8. Zeichen ist der Strom abgeschlossen');
		assert.deepEqual(tippe(tipp, '30042027'), { ok: true, iso: '2027-04-30' });
	});

	for (const taste of ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Tab', '.', '/', 'a', ' ']) {
		test(`halber Strom + „${taste}" → Strom beginnt neu`, () => {
			const tipp = new DatumTipp();
			tippe(tipp, '3103');
			assert.equal(tipp.taste(taste, TMJ), null);
			assert.equal(tipp.laeuft, false, `„${taste}" muss den Strom zurücksetzen`);
			// Die alten vier Ziffern zählen nicht mehr: erst acht neue liefern ein Ergebnis.
			assert.equal(tippe(tipp, '3105202'), null, 'alte Ziffern dürfen nicht mitzählen');
			assert.deepEqual(tipp.taste('7', TMJ), { ok: true, iso: '2027-05-31' });
		});
	}

	test('Fokuswechsel/Klick (zuruecksetzen) → Strom beginnt neu', () => {
		const tipp = new DatumTipp();
		tippe(tipp, '310320');
		tipp.zuruecksetzen();
		assert.equal(tipp.laeuft, false);
		assert.equal(tippe(tipp, '12'), null);
		assert.deepEqual(tippe(tipp, '122026'), { ok: true, iso: '2026-12-12' });
	});
});
