// #2988 S1, AC-3: „Als eigene Vorlage speichern“ sendet denselben Rumpf wie vor dem Umbau;
// einziger Unterschied: `modus`/`sektoren` der Windrichtung bleiben erhalten.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Grundlage: zaehlerFaelle2988.ts.
//
// Vertrag: wetterZustand.ts exportiert
//   aboAmpelVon(stand, vorlagen, context, alt = {}) -> Ampel
// (aufgeloeste Ampel + Auswahl, `template` = Vorlage im Kontext, offene Grenzen als leere Seite).
// Eine Zeile, die die Vorlage nicht hat und die nichts sagt (aus, leer, Alarm nie), steht wie
// bisher nicht im Rumpf (Fall `alarm_ab_never_ohne_vorlagenzeile`).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { eigeneVorlagePayload } from '../ampelSchreiben.ts';
import * as Z from '../wetterZustand.ts';
import { alleFaelle, entpacke, normal, referenz, type Fall } from './zaehlerFaelle2988.ts';
import type { Json } from './wetterTabDaten.ts';
import { reiter2988 } from './reiter2988.ts';

const R = referenz();
const FAELLE = alleFaelle(R);

function aboAmpel(f: Fall, vorlagen: Json = R.vorlagen): Json {
	const fn = (Z as Json).aboAmpelVon;
	assert.equal(typeof fn, 'function', 'TDD RED: wetterZustand.aboAmpelVon fehlt');
	return fn(f.stand, vorlagen, f.context, f.alt);
}
const rumpf = (ampel: Json, kind: 'route' | 'vergleich'): Json =>
	eigeneVorlagePayload({ name: 'Meine', beschreibung: 'x', alsStandard: false, kind, ampel, herkunft: { id: 't', name: 'T' } });
const soll = (f: Fall): Json => entpacke(R.faelle[f.name].aboAmpel, R.vorlagen[f.stand.vorlageId]);
const eingeschaltet = (ampel: Json): string[] =>
	Object.entries(ampel.metrics as Json).filter(([, e]) => (e as Json).enabled).map(([id]) => id).sort();
const ohneRichtung = (ampel: Json): Json => {
	const k = normal(ampel);
	for (const e of Object.values(k.metrics) as Json[]) {
		delete e.modus;
		delete e.sektoren;
	}
	return k;
};

describe('AC-3 (#2988): Rumpf der eigenen Vorlage', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}_rumpf_gleich_referenz_bis_auf_windrichtung`, () => {
			for (const f of FAELLE.filter((x) => x.context === context)) {
				const ist = rumpf(aboAmpel(f), context);
				const ref = rumpf(soll(f), context);
				assert.deepEqual(ohneRichtung(ist.ampel), ohneRichtung(ref.ampel), f.name);
				const liste = (r: Json) => r.metrics.map((m: Json) => JSON.stringify(m)).sort();
				assert.deepEqual(liste(ist), liste(ref), f.name);
				const rest = ({ ampel: _a, metrics: _m, ...uebrig }: Json) => uebrig;
				assert.deepEqual(rest(ist), rest(ref), f.name);
			}
		});
		test(`${context}_eingeschaltete_metriken_sind_die_auswahl`, () => {
			for (const f of FAELLE.filter((x) => x.context === context)) {
				assert.deepEqual(eingeschaltet(aboAmpel(f)), [...f.stand.auswahl].sort(), f.name);
			}
		});
		test(`${context}_modus_und_sektoren_bleiben_erhalten`, () => {
			const f = structuredClone(FAELLE.find((x) => x.name === `${context}|allgemein|unveraendert`)!);
			const zeile = f.stand.ampel.metrics!.wind_direction as Json;
			Object.assign(zeile, { modus: 'sektoren', sektoren: ['N', 'NO'] });
			const ist = aboAmpel(f).metrics.wind_direction;
			assert.equal(ist.modus, 'sektoren');
			assert.deepEqual(ist.sektoren, ['N', 'NO']);
			ist.sektoren.push('S');
			assert.deepEqual(zeile.sektoren, ['N', 'NO'], 'Sektoren sind keine Kopie');
		});
		test(`${context}_vorlage_mit_modus_behaelt_ihn`, () => {
			const f = FAELLE.find((x) => x.name === `${context}|radtour|unveraendert`)!;
			assert.equal(aboAmpel(f).metrics.wind_direction.modus, 'gegenwind');
		});
	}
	test('offene_grenzen_als_leere_seite', () => {
		for (const f of FAELLE.filter((x) => x.name.endsWith('|unveraendert') || x.name.endsWith('|grenze_teilweise_offen'))) {
			for (const [id, e] of Object.entries(aboAmpel(f).metrics as Json)) {
				for (const seite of ['lower', 'upper']) {
					const s = (e as Json)[seite];
					assert.ok(s && typeof s === 'object', `${f.name} ${id}.${seite}: Seite fehlt`);
					assert.ok(!Object.values(s).includes(null), `${f.name} ${id}.${seite}: ${JSON.stringify(s)}`);
				}
			}
		}
	});
	test('baut_kopien_und_veraendert_weder_vorlagen_noch_stand', () => {
		for (const f of FAELLE) {
			const vorlagen = structuredClone(R.vorlagen);
			const stand = structuredClone(f.stand);
			const a = aboAmpel({ ...f, stand }, vorlagen);
			for (const e of Object.values(a.metrics) as Json[]) {
				e.enabled = 'x';
				e.lower.x = 1;
				e.upper.x = 1;
			}
			a.thunder.x = 1;
			assert.deepEqual(vorlagen, R.vorlagen, f.name);
			assert.deepEqual(stand, f.stand, f.name);
		}
	});
});

describe('AC-3 (#2988): im Reiter kommt die Ampel genau so beim Dialog an', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}_reiter_gibt_modus_und_sektoren_an_den_dialog`, async () => {
			const r = await reiter2988(context, {
				template: 'allgemein',
				metrics: { wind_direction: { enabled: true, modus: 'sektoren', sektoren: ['N', 'NO'] } }
			});
			const ist = r.aboAmpel();
			assert.equal(ist.template, 'allgemein');
			assert.equal(ist.metrics.wind_direction.modus, 'sektoren');
			assert.deepEqual(ist.metrics.wind_direction.sektoren, ['N', 'NO']);
		});
		test(`${context}_reiter_aendert_grenze_und_auswahl_im_dialog`, async () => {
			const r = await reiter2988(context, { template: 'wandern' });
			r.grenze('gust', 'upper', 'yellow', 41);
			r.u.entfernen('wind');
			const ist = r.aboAmpel();
			assert.equal(ist.metrics.gust.upper.yellow, 41);
			assert.equal(ist.metrics.wind.enabled, false);
			assert.deepEqual(eingeschaltet(ist), [...r.u.stand.auswahl].sort());
		});
	}
});
