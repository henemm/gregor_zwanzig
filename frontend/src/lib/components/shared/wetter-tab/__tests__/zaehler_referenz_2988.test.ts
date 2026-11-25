// #2988 S1, AC-2: jede Zaehler-Zahl gleich der Referenzzahl aus dem Code vor dem Umbau.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Grundlage: zaehlerFaelle2988.ts.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { abweichungenVon, mengeVon } from '../wetterZustand.ts';
import { alleFaelle, GESTEN, referenz } from './zaehlerFaelle2988.ts';
import { fixture } from './wetterTabDaten.ts';

const R = referenz();
const FAELLE = alleFaelle(R);
const namen = (liste: { name: string }[]): string[] => liste.map((c) => c.name);

describe('AC-2 (#2988): Zaehler gleich Referenz', () => {
	test('referenz_und_faelle_decken_sich_vollstaendig', () => {
		assert.deepEqual(namen(FAELLE).sort(), Object.keys(R.faelle).sort());
		assert.equal(Object.keys(R.vorlagen).length, 7);
		assert.equal(R.abweichungsFaelle.length, 22);
		assert.deepEqual(namen(R.abweichungsFaelle), namen(fixture('ampel_deviation_cases.json').cases));
		assert.equal(FAELLE.length, 2 * 7 * Object.keys(GESTEN).length + 2 * 22 + 1);
	});
	test('messaufbau_traegt_null_eins_und_mehrere', () => {
		const zahlen = new Set(Object.values(R.faelle as Record<string, { zahl: number }>).map((f) => f.zahl));
		for (const z of [0, 1, 4, 5]) assert.ok(zahlen.has(z), `keine Referenz mit Zahl ${z}`);
	});
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}_jede_zahl_gleich_referenz`, () => {
			const anders = FAELLE.filter((f) => f.context === context)
				.map((f) => ({ name: f.name, ist: abweichungenVon(f.stand, R.vorlagen, f.context, f.alt), soll: R.faelle[f.name].zahl }))
				.filter((x) => x.ist !== x.soll);
			assert.deepEqual(anders, []);
		});
	}
	// Der Zaehler ist die Zahl der Eintraege der gespeicherten Menge (+1 Gewitter) — dieselbe Rechnung.
	test('zahl_ist_groesse_der_gespeicherten_menge', () => {
		for (const f of FAELLE) {
			const m = mengeVon(f.stand, R.vorlagen, f.context, f.alt);
			assert.equal(abweichungenVon(f.stand, R.vorlagen, f.context, f.alt), Object.keys(m.metrics ?? {}).length + (m.thunder ? 1 : 0), f.name);
		}
	});
	test('unbekannte_vorlage_zaehlt_null', () => {
		const s = { ...FAELLE[0].stand, vorlageId: 'gibt-es-nicht' };
		assert.equal(abweichungenVon(s, R.vorlagen, 'route', {}), 0);
	});
	test('zaehlen_veraendert_weder_vorlagen_noch_stand', () => {
		for (const f of FAELLE) {
			const vorlagen = structuredClone(R.vorlagen);
			const stand = structuredClone(f.stand);
			abweichungenVon(stand, vorlagen, f.context, f.alt);
			assert.deepEqual(vorlagen, R.vorlagen, f.name);
			assert.deepEqual(stand, f.stand, f.name);
		}
	});
});
