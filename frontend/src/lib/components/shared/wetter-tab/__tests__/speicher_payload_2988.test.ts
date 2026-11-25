// #2988 S1 (wiederholt in S3), AC-14: Speicher-Ruempfe gleich den Ruempfen vor dem Umbau.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Grundlage: zaehlerFaelle2988.ts.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { tripNutzlast, vergleichNutzlast, type SpeicherOptionen } from '../wetterTabSpeicherung.ts';
import { aboMitFremdfeldern, alleFaelle, PAYLOAD_VORLAGEN, referenz } from './zaehlerFaelle2988.ts';

const R = referenz();
const FAELLE = alleFaelle(R).filter((f) => PAYLOAD_VORLAGEN.includes(f.name.split('|')[1]));
const NUTZLAST: Record<string, (o: SpeicherOptionen) => unknown> = { route: tripNutzlast, vergleich: vergleichNutzlast };

describe('AC-14 (#2988): Speicher-Ruempfe gleich Referenz', () => {
	test('referenz_und_faelle_decken_sich', () => {
		assert.deepEqual(FAELLE.map((f) => f.name).sort(), Object.keys(R.ruempfe).sort());
		assert.ok(FAELLE.length > 80, String(FAELLE.length));
	});
	for (const f of FAELLE) {
		test(`rumpf_gleich_${f.name}`, () => {
			const abo = aboMitFremdfeldern(f.context);
			const rumpf = NUTZLAST[f.context]({
				client: null as never,
				stand: () => f.stand,
				vorlagen: () => R.vorlagen,
				abo: () => abo,
				altSchluessel: f.alt
			});
			assert.deepEqual(JSON.parse(JSON.stringify(rumpf)), R.ruempfe[f.name]);
			assert.deepEqual(abo, aboMitFremdfeldern(f.context), 'Abo der Seite verändert');
		});
	}
});
