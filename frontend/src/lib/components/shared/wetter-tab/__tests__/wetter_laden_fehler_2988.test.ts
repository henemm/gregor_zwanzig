// #2988 S3, AC-10: scheitert die Aufloesung beim Laden, erscheint „Erneut laden“ und nichts wird gespeichert.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Gemessen im echten Reiter (laden2988.ts).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { AUFLOESUNG, KONTEXTE, aufgeloestVon, baue, echterPost, json, tick, tor, type Json, type Reiter } from './laden2988.ts';

const ABO = { id: 'x', name: 'X', display_config: { ampel: { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } } } };
const werfe = (e: unknown) => async (): Promise<Json> => {
	throw e;
};
const FEHLER: Record<string, (pfad: string, rumpf: Json) => Promise<Json>> = {
	netzfehler: werfe(new TypeError('Failed to fetch')),
	status_503: werfe({ status: 503, error: 'upstream_unreachable' }),
	status_400: werfe({ status: 400, code: 'bad_request' }),
	antwort_null: async () => null,
	antwort_leer: async () => ({}),
	zu_wenige_ergebnisse: async () => ({ ergebnisse: [] }),
	ergebnis_ohne_ampel: async (pfad, rumpf) => ({ ergebnisse: (await echterPost(pfad, rumpf)).ergebnisse.map((e: Json) => ({ vorlage_id: e.vorlage_id })) })
};

function nichtsPassiert(r: Reiter, wo: string): void {
	assert.deepEqual(r.schreibend(), [], `${wo}: schreibender Aufruf`);
	assert.equal(r.geplant(), 0, `${wo}: Speichern geplant`);
	assert.deepEqual(r.gemeldet, [], `${wo}: Stand an die Anlege-Seite gemeldet`);
	assert.deepEqual(r.updates, [], `${wo}: Übernahme an die Seite`);
}

for (const context of KONTEXTE) {
	for (const createMode of [false, true]) {
		const wo = `${context}_${createMode ? 'anlegen' : 'hub'}`;
		describe(`AC-10 (#2988, ${wo}): Auflösung scheitert beim Laden`, () => {
			for (const [art, post] of Object.entries(FEHLER)) {
				test(`${wo}_${art}_fehlerzustand_ohne_speichern_dann_erneut_laden`, async () => {
					const r = await baue(context, structuredClone(ABO), { createMode, post });
					await r.laden();
					assert.deepEqual(r.posts().map((p) => p.pfad), [AUFLOESUNG], 'die Auflösung wird nicht gefragt');
					assert.equal(r.u.phase, 'fehler');
					assert.equal(r.u.stand, null, 'Reiter hydriert trotz Fehler');
					nichtsPassiert(r, art);

					await r.laden();
					assert.equal(r.u.phase, 'fehler', 'zweiter Fehlversuch');
					assert.equal(r.u.stand, null);
					nichtsPassiert(r, `${art}, zweiter Versuch`);

					r.setzePost(echterPost);
					await r.laden();
					assert.equal(r.u.phase, 'bereit', '„Erneut laden“ fragt die Auflösung nicht neu');
					assert.deepEqual(json((r.u as Json)['stand'].ampel), aufgeloestVon(ABO).ampel);
					assert.equal(r.posts().length, 3);
					assert.deepEqual(r.schreibend(), []);
					assert.equal(r.geplant(), 0);
					assert.equal(r.gemeldet.length, createMode ? 1 : 0, 'Anlegen meldet genau den geladenen Stand');
				});
			}
			test(`${wo}_zweites_paket_scheitert`, async () => {
				const presets = Array.from({ length: 40 }, (_, i) => ({ id: `v${i}`, name: 'V', is_default: false, created_at: '', kind: context, metrics: [], ampel: { template: 'wandern' } }));
				const r = await baue(context, structuredClone(ABO), {
					createMode,
					presets,
					post: async (pfad, rumpf) => {
						if (rumpf.eintraege.length < 32) throw { status: 502 };
						return echterPost(pfad, rumpf);
					}
				});
				await r.laden();
				assert.equal(r.u.phase, 'fehler');
				assert.equal(r.u.stand, null);
				assert.equal(r.u.daten, null, 'halbe Daten');
				nichtsPassiert(r, 'zweites Paket');
			});
			test(`${wo}_bis_zur_antwort_kein_stand_und_kein_speichern`, async () => {
				const halt = tor();
				const r = await baue(context, structuredClone(ABO), {
					createMode,
					post: async (pfad, rumpf) => {
						await halt.versprechen;
						return echterPost(pfad, rumpf);
					}
				});
				const fertig = r.laden();
				for (let i = 0; i < 100 && r.posts().length === 0 && r.u.phase === 'laedt'; i++) await tick();
				assert.equal(r.posts().length, 1, 'die Auflösung wird nicht gefragt');
				await tick(30);
				assert.equal(r.u.phase, 'laedt', 'bereit ohne Antwort der Auflösung');
				assert.equal(r.u.stand, null);
				nichtsPassiert(r, 'vor der Antwort');
				halt.auf();
				await fertig;
				assert.equal(r.u.phase, 'bereit');
			});
		});
	}
}
