// #2988 S3, AC-13: eine frisch gespeicherte eigene Vorlage steht sofort mit der Ampel aus der Antwort des
// Speicherns in der Liste, ohne Aufruf der Aufloesung, und laesst sich uebernehmen.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { KONTEXTE, json, oeffne, refVorlagen, type Json } from './laden2988.ts';

const ABO = { id: 'x', name: 'X', display_config: { ampel: { template: 'wandern' } } };
const preset = (rest: Json): Json => ({ id: 'neu', name: 'Meine', is_default: false, created_at: '2026-01-01T00:00:00Z', metrics: [], ...rest });

/** Ampel der Antwort, vollstaendig wie vom Dialog gesendet. */
function ampel(): Json {
	const a = refVorlagen().skitouren;
	for (const z of Object.values(a.metrics) as Json[]) z.enabled = false;
	a.metrics.gust = { enabled: true, lower: {}, upper: { yellow: 33, orange: 44, red: 55 }, alarm_ab: 'red' };
	a.thunder = { mittel: 'red', hoch: 'red' };
	return a;
}

for (const context of KONTEXTE) {
	const andere = { route: 'vergleich', vergleich: 'route' }[context];
	describe(`AC-13 (#2988, ${context}): frisch gespeicherte eigene Vorlage`, () => {
		test(`${context}_sofort_vorn_in_der_liste_mit_der_ampel_der_antwort_ohne_aufruf`, async () => {
			const r = await oeffne(context, structuredClone(ABO), { presets: [preset({ id: 'alt', kind: context, ampel: { template: 'radtour' } })] });
			const n = r.aufrufe.length;
			r.gespeichert(preset({ kind: context, description: 'Text', herkunft: { id: 'x', name: 'X' }, ampel: ampel() }));
			assert.deepEqual(r.eigene().map((e) => e.id), ['neu', 'alt']);
			assert.deepEqual(json(r.eigene()[0]), { id: 'neu', name: 'Meine', ampel: ampel(), beschreibung: 'Text', herkunftName: 'X' });
			assert.equal(r.aufrufe.length, n, 'Aufruf beim Speichern');
			assert.equal(r.geplant(), 0);
		});
		test(`${context}_ampel_der_antwort_gilt_unveraendert_nichts_lokal_gerechnet`, async () => {
			const r = await oeffne(context, structuredClone(ABO));
			const n = r.aufrufe.length;
			const a = ampel();
			delete a.metrics.wind;
			a.metrics.gust.upper = { yellow: 90, orange: 60, red: 30 };
			r.gespeichert(preset({ kind: context, ampel: structuredClone(a) }));
			assert.deepEqual(json(r.eigene()[0].ampel), a);
			assert.equal(r.aufrufe.length, n, 'Aufruf der Auflösung');
		});
		test(`${context}_laesst_sich_uebernehmen`, async () => {
			const r = await oeffne(context, structuredClone(ABO));
			const n = r.aufrufe.length;
			r.gespeichert(preset({ kind: context, ampel: ampel() }));
			r.eigeneUebernehmen('neu');
			assert.equal(r.u.stand.vorlageId, 'skitouren');
			assert.deepEqual(json(r.u.stand.ampel), ampel());
			assert.deepEqual(r.u.stand.auswahl, ['gust']);
			assert.equal(r.geplant(), 1, 'Übernehmen plant das Speichern');
			assert.equal(r.aufrufe.length, n, 'Netzaufruf');
			// Änderungen am Stand färben nicht auf die Vorlage in der Liste ab.
			r.grenze('gust', 'upper', 'yellow', 11);
			assert.deepEqual(json(r.eigene()[0].ampel), ampel());
		});
		test(`${context}_ohne_art_gilt_der_reiter`, async () => {
			const r = await oeffne(context, structuredClone(ABO));
			r.gespeichert(preset({ ampel: ampel() }));
			assert.deepEqual(r.eigene().map((e) => e.id), ['neu']);
		});
		test(`${context}_andere_art_kommt_nicht_in_die_liste`, async () => {
			const r = await oeffne(context, structuredClone(ABO));
			r.gespeichert(preset({ kind: andere, ampel: ampel() }));
			assert.deepEqual(r.eigene(), []);
		});
		for (const ohne of [undefined, null]) {
			test(`${context}_ohne_ampel_erst_beim_naechsten_laden_${ohne}`, async () => {
				const r = await oeffne(context, structuredClone(ABO));
				const n = r.aufrufe.length;
				r.gespeichert(preset({ kind: context, ampel: ohne, metrics: [{ metric_id: 'gust', enabled: true }] }));
				assert.deepEqual(r.eigene(), []);
				assert.equal(r.aufrufe.length, n, 'Aufruf der Auflösung');
			});
		}
	});
}
