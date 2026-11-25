// #2988 S3, AC-11: das Öffnen des Reiters speichert nichts; Signatur vor und nach dem Öffnen gleich.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Referenz-Menge aus dem Altbaum.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { json, oeffne, pythonAufloesung, referenzLaden, type Json } from './laden2988.ts';

const R = referenzLaden();
const text = (x: Json) => (typeof x === 'string' ? x : null);
let warm = false;
/** Alle Referenz-Abos in EINEM Python-Lauf. */
function vorwaermen(): void {
	if (!warm) pythonAufloesung(R.abos.map(({ abo }: Json) => ({ ampel: abo.display_config?.ampel ?? null, preset_name: text(abo.display_config?.preset_name), profil: text(abo.profil) })));
	warm = true;
}

describe('AC-11 (#2988): Öffnen speichert nichts, Signatur gleich Referenz', () => {
	for (const f of R.abos) {
		test(`oeffnen_speichert_nichts_${f.name}`, async () => {
			vorwaermen();
			const abo = structuredClone(f.abo);
			const r = await oeffne(f.context, abo);
			const s = f.soll;
			assert.deepEqual(JSON.parse(r.u.gemeldet), json([s.menge, s.auswahl, s.warnungenAn, s.radarAn, s.tagesfenster]), 'Signatur nach dem Öffnen');
			assert.equal(r.u.signatur(r.u.stand), r.u.gemeldet);
			assert.equal(r.zahl(), s.zaehler);

			// Eine Eingabe ohne Wirkung (gleicher Stand) ist keine Änderung.
			r.u.aendern(structuredClone(r.u.stand));
			assert.equal(r.geplant(), 0, 'Speichern geplant');
			assert.deepEqual(r.schreibend(), []);
			assert.deepEqual(r.gemeldet, []);
			assert.deepEqual(abo, f.abo, 'Abo der Seite verändert');
			// Messaufbau: eine echte Änderung plant das Speichern.
			r.u.aendern({ ...r.u.stand, radarAn: !r.u.stand.radarAn });
			assert.equal(r.geplant(), 1, 'Messaufbau: Änderung plant kein Speichern');
		});
	}
});
