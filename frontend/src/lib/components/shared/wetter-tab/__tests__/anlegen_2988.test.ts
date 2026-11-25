// #2988 S3, AC-15: im Anlegen (Trip, Ortsvergleich) meldet der Reiter dieselbe Nutzlast wie vor dem Umbau
// und speichert vor dem Anlege-Aufruf nichts.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Referenz: ampel_laden_referenz_2988.json (`anlegen`).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { AUFLOESUNG, json, oeffne, referenzLaden } from './laden2988.ts';

const R = referenzLaden();

describe('AC-15 (#2988): Anlegen meldet dieselbe Nutzlast, speichert nichts', () => {
	for (const f of R.anlegen) {
		test(`vorlage_waehlen_grenze_aendern_${f.name}`, async () => {
			const r = await oeffne(f.context, structuredClone(f.abo), { createMode: true });
			assert.equal(r.gemeldet.length, 1, 'Startmeldung');
			assert.deepEqual(json(r.gemeldet[0]), f.soll.start);
			if (f.vorlage) r.uebernehmen(f.vorlage);
			r.grenze('gust', 'upper', 'yellow', 41);
			assert.deepEqual(json(r.gemeldet.at(-1)), f.soll.ende);
			assert.equal(r.gemeldet.length, f.soll.meldungen);
			assert.equal(r.zahl(), f.soll.zaehler);
			assert.deepEqual(r.u.stand.auswahl, f.soll.auswahl);
			assert.deepEqual(r.schreibend(), [], 'Speicheraufruf vor dem Anlegen');
			assert.equal(r.geplant(), 0);
			assert.deepEqual(r.posts().map((p) => p.pfad), [AUFLOESUNG], 'genau eine Auflösung, beim Laden');
		});
	}
});
