// Issue #3047 Runde 7, Paket p10: Matrixzellen der Einstellungsseite Orte
//   orte.ortsfolge    — Folge der Orte im Orte-Reiter = Folge der Ort-Bloecke in der Orte-Mail
//   orte.orte_auswahl — genau die gewaehlten (und noch vorhandenen) Orte, in beiden
//   orte.ortsnamen    — Ortsnamen (auch mit Sonderzeichen) wortgleich, je Nutzer getrennt
//
// Reiter-Seite: die echte Aufloesung des Reiters (orteAufloesung.ts, von CompareTabs.svelte
// benutzt: Verzeichnis, aufgeloeste Orte, Zeilennummer). Mail-Seite: die echte Python-Kette
// bis zur fertigen Mail (ortsfolgeOrakel.ts). Speicherweg: der echte Nutzlast-Bauer des Reiters
// (buildComparePresetPartialPayload) — denselben Rumpf schickt der Go-Test
// TestOrteReiterReihenfolgeUndEntfernenReadModifyWriteZweiNutzer an den Handler.
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/p10_ortsfolge_reiter_gleich_mail.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { ortsVerzeichnis, orteAufloesen, reiterNummer } from '../orteAufloesung.ts';
import { buildComparePresetPartialPayload } from '../compareEditorSave.ts';
import { orteMailFolge, type Ort, type NutzerEingabe } from './ortsfolgeOrakel.ts';

/** Was der Orte-Reiter zeigt: Zeilen (Nummer + Name) in Listenfolge; leer = Hinweis „keine Orte". */
function reiter(orteDesNutzers: Ort[], ids: string[]) {
	const verz = ortsVerzeichnis(orteDesNutzers, []);
	const aufgeloest = orteAufloesen(ids, verz);
	// Zeilen, wie der SortableList-Ausschnitt sie rendert ({#if loc} … index={reiterNummer(…)}).
	const zeilen = ids.flatMap((id, i) => {
		const loc = verz.get(id);
		return loc ? [{ nummer: reiterNummer(ids, i, verz), name: loc.name }] : [];
	});
	return { aufgeloest, zeilen, leer: aufgeloest.length === 0 };
}

// Nutzer A: Sonderzeichen (Umlaute, ß, Apostroph, &, <>, Anfuehrungszeichen, Gedankenstrich, CJK).
const ORTE_A: Ort[] = [
	{ id: 'loc-alpha', name: `Col d'Ornon & <Pic> "Süd"` },
	{ id: 'loc-mitte', name: 'Ötztal/Sölden – 山小屋' },
	{ id: 'loc-zeta', name: 'Äußere Röt-Spitze (2.418 m)' },
	{ id: 'loc-ungewaehlt-a', name: 'Nicht gewählt A' }
];
// Nutzer B: DIESELBEN Kennungen, eigene Namen (Ortsdaten je Nutzer getrennt).
const ORTE_B: Ort[] = [
	{ id: 'loc-alpha', name: 'Arber' },
	{ id: 'loc-mitte', name: 'Brocken' },
	{ id: 'loc-zeta', name: 'Zugspitze' },
	{ id: 'loc-ungewaehlt-b', name: 'Nicht gewählt B' }
];
// Nutzer C: ein geloeschter Ort mitten in location_ids. Nutzer D: nur geloeschte Orte.
const ORTE_C: Ort[] = [
	{ id: 'loc-c-eins', name: 'Ehrwald' },
	{ id: 'loc-c-zwei', name: 'Davos' }
];

const EINGABE: Record<string, NutzerEingabe> = {
	'p10-nutzer-a': { orte: ORTE_A, location_ids: ['loc-mitte', 'loc-zeta', 'loc-alpha'] },
	'p10-nutzer-b': { orte: ORTE_B, location_ids: ['loc-zeta', 'loc-alpha', 'loc-mitte'] },
	'p10-nutzer-c': { orte: ORTE_C, location_ids: ['loc-c-zwei', 'loc-geloescht', 'loc-c-eins'] },
	'p10-nutzer-d': { orte: ORTE_C, location_ids: ['loc-weg-1', 'loc-weg-2'] }
};
const MAIL = orteMailFolge(EINGABE);

function mailVon(uid: string) {
	const m = MAIL[uid];
	assert.ok(m && m.fehler === undefined, `Vorbedingung: Mail fuer ${uid} versendet, war ${JSON.stringify(m)}`);
	return m as Exclude<typeof m, { fehler: string }> & { fehler?: undefined };
}

describe('#3047 p10 orte.ortsfolge / orte.orte_auswahl / orte.ortsnamen: Reiter = Mail', () => {
	test('Vorbedingung: Ortsfolge ungleich alphabetisch (Kennung und Name) und ungleich Anlegefolge', () => {
		for (const uid of ['p10-nutzer-a', 'p10-nutzer-b']) {
			const { orte, location_ids } = EINGABE[uid];
			const gewaehlt = orte.filter((o) => location_ids.includes(o.id));
			assert.notDeepEqual(location_ids, [...location_ids].sort(), uid);
			const namen = location_ids.map((id) => orte.find((o) => o.id === id)!.name);
			assert.notDeepEqual(namen, [...namen].sort((x, y) => x.localeCompare(y, 'de')), uid);
			assert.notDeepEqual(namen, [...namen].sort(), uid);
			assert.notDeepEqual(location_ids, gewaehlt.map((o) => o.id), uid);
		}
	});

	for (const uid of ['p10-nutzer-a', 'p10-nutzer-b']) {
		test(`${uid}: Reihenfolge, Auswahl und Namen im Reiter = Ort-Bloecke der Mail`, () => {
			const { orte, location_ids } = EINGABE[uid];
			const r = reiter(orte, location_ids);
			const m = mailVon(uid);
			const reiterNamen = r.zeilen.map((z) => z.name);
			assert.equal(m.bloecke.length, location_ids.length, `${uid}: jede gewaehlte Ort hat einen Block`);
			assert.deepEqual(reiterNamen, m.bloecke, `${uid}: Klartext-Uebersicht`);
			assert.deepEqual(reiterNamen, m.stunden, `${uid}: Stundenverlauf-Koepfe`);
			assert.deepEqual(reiterNamen, m.html, `${uid}: Ortsnamen im HTML (unescaped)`);
			assert.deepEqual(r.aufgeloest.map((e) => e.loc?.name), reiterNamen, `${uid}: Uebersicht-Orte`);
			assert.deepEqual(r.zeilen.map((z) => z.nummer), [1, 2, 3], `${uid}: Nummern = Position in der Mail`);
			assert.deepEqual(r.aufgeloest.map((e) => e.rank), [1, 2, 3], `${uid}: Rang = Position in der Mail`);
			assert.deepEqual(m.gespeichert, location_ids, `${uid}: der Versand veraendert location_ids nicht`);
		});
	}

	test('zwei Nutzer: gleiche Kennungen, je eigene Namen; keiner sieht Namen des anderen', () => {
		const a = mailVon('p10-nutzer-a');
		const b = mailVon('p10-nutzer-b');
		for (const n of ORTE_B.map((o) => o.name)) assert.ok(!a.bloecke.includes(n) && !a.html.includes(n), `A sieht ${n}`);
		for (const n of ORTE_A.map((o) => o.name)) assert.ok(!b.bloecke.includes(n) && !b.html.includes(n), `B sieht ${n}`);
		assert.deepEqual(reiter(ORTE_B, EINGABE['p10-nutzer-b'].location_ids).zeilen.map((z) => z.name), b.bloecke);
		assert.notDeepEqual(a.bloecke, b.bloecke);
	});

	test('geloeschter Ort mitten in location_ids: Reiter zeigt dieselben Orte, Nummern und Folge wie die Mail', () => {
		const { orte, location_ids } = EINGABE['p10-nutzer-c'];
		const r = reiter(orte, location_ids);
		const m = mailVon('p10-nutzer-c');
		assert.deepEqual(m.bloecke, ['Davos', 'Ehrwald']);
		assert.deepEqual(r.zeilen.map((z) => z.name), m.bloecke);
		assert.deepEqual(r.zeilen.map((z) => z.nummer), [1, 2], 'Nummer = Position des Blocks in der Mail (keine Luecke)');
		assert.deepEqual(r.aufgeloest.map((e) => [e.rank, e.loc?.name]), [[1, 'Davos'], [2, 'Ehrwald']]);
		// Der geloeschte Eintrag bleibt in der Liste des Reiters (kein stilles Verwerfen beim Speichern).
		assert.deepEqual(m.gespeichert, location_ids);
	});

	test('nur geloeschte Orte: Mail wird nicht versendet (orte_geloescht), Reiter zeigt „keine Orte"', () => {
		const { orte, location_ids } = EINGABE['p10-nutzer-d'];
		assert.deepEqual(MAIL['p10-nutzer-d'], { fehler: 'versand.grund.orte_geloescht' });
		const r = reiter(orte, location_ids);
		assert.deepEqual(r.zeilen, []);
		assert.equal(r.leer, true, 'Leerhinweis statt leerer Karte');
	});

	test('Speicherweg des Reiters (Umsortieren/Entfernen) sendet NUR location_ids in neuer Folge', () => {
		const neu = ['loc-alpha', 'loc-mitte'];
		const { url, body } = buildComparePresetPartialPayload('p10-a', { location_ids: neu });
		assert.equal(url, '/api/compare/presets/p10-a');
		// Exakt dieser Rumpf ist im Go-Test (internal/handler/compare_preset_p10_orte_rmw_test.go) verdrahtet.
		assert.equal(JSON.stringify(body), '{"location_ids":["loc-alpha","loc-mitte"]}');
	});
});
