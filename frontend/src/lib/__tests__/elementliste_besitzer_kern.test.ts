// TDD RED — Issue #3008 F001 (Epic #2913), Workflow feat-3008-abgleich-waechter.
// Spec: docs/specs/modules/feat_3008_abgleich_waechter.md — AC-1, AC-2, AC-3.
//
// Kern-Test der Besitzerliste: verwaiste Einträge fallen sonst erst im Staging-Lauf auf (ladeRegeln ruft
// leseBesitzer(text, liste)). Geprüft wird mit derselben Funktion, die der Staging-Lauf nutzt, auf den
// echten Dateien aus docs/context/einstellungen_neu/. Verfälschung nur an Kopien im Speicher, kein Mock.
//
// Vertrag (vom Developer in e2e/elementliste_abgleich_logik.ts umzusetzen):
//   leseBesitzer(jsonText, elemente) wirft zusätzlich, wenn ein Besitzer `art: 'abschnitt'` ein Tripel
//   (ctx, reiter, abschnitt) nennt, das in `elemente` nicht vorkommt; der Fehlertext nennt den Abschnitt.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/__tests__/elementliste_besitzer_kern.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as logik from '../../../e2e/elementliste_abgleich_logik.ts';
import type { ListenElement } from '../../../e2e/elementliste_abgleich_logik.ts';

// Namespace-Import: fehlende Exporte machen jeden Test einzeln rot statt das ganze Modul zu sprengen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const L = logik as any;

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const KONTEXT = join(FRONTEND, '..', 'docs/context/einstellungen_neu');

const BESITZER_TEXT = readFileSync(join(KONTEXT, 'elementliste_besitzer.json'), 'utf8');
const LISTE: ListenElement[] = (JSON.parse(readFileSync(join(KONTEXT, 'elementliste.json'), 'utf8')) as { elemente: ListenElement[] }).elemente;
type RohBesitzer = Record<string, unknown> & { art: string };
const ROH = (): { besitzer: RohBesitzer[] } & Record<string, unknown> => JSON.parse(BESITZER_TEXT);

/** Kopie der echten Besitzerliste, deren Eintrag `index` durch `aendern` verfälscht wurde. */
function verfaelscht(index: number, aendern: (b: RohBesitzer) => void): string {
	const daten = ROH();
	aendern(daten.besitzer[index]);
	return JSON.stringify(daten);
}

const ersterIndex = (art: string): number => {
	const i = ROH().besitzer.findIndex((b) => b.art === art);
	assert.ok(i >= 0, `kein Besitzer der Art „${art}“ im echten Bestand`);
	return i;
};

describe('#3008 F001: Besitzerliste gegen die Elementliste (Kern)', () => {
	test('AC-1: echter Bestand — leseBesitzer wirft nicht und liefert alle Besitzer-Einträge', () => {
		const besitzer = L.leseBesitzer(BESITZER_TEXT, LISTE);
		assert.equal(besitzer.length, ROH().besitzer.length, 'nicht alle Besitzer-Einträge geliefert');
		const arten = new Set(besitzer.map((b: { art: string }) => b.art));
		for (const art of ['element', 'abschnitt', 'zusaetzlich']) assert.ok(arten.has(art), `Art „${art}“ fehlt im Ergebnis`);
	});

	test('AC-1 (F001 wörtlich): jede Element-ID mit Verweis „#2913“ steht in der Elementliste', () => {
		const ids = new Set(LISTE.map((e) => e.id));
		const mit2913 = ROH().besitzer.filter((b) => b.art === 'element' && b.verweis === '#2913');
		assert.ok(mit2913.length > 0, 'keine element-Besitzer mit Verweis #2913 im Bestand');
		const verwaist = mit2913.map((b) => String(b.id)).filter((id) => !ids.has(id));
		assert.deepEqual(verwaist, [], `verwaiste Element-IDs (#2913): ${verwaist.join(', ')}`);
	});

	test('AC-2: Kopie mit erfundener Element-ID ⇒ Fehler nennt die ID', () => {
		const erfunden = 'trip.wetter.normal.-.kopf.gibtesnicht3008';
		const text = verfaelscht(ersterIndex('element'), (b) => {
			b.id = erfunden;
		});
		assert.throws(() => L.leseBesitzer(text, LISTE), (err: Error) => err.message.includes(erfunden));
	});

	test('AC-3: Kopie mit erfundenem Abschnitt ⇒ Fehler nennt den Abschnitt', () => {
		const erfunden = 'abschnitt-gibt-es-nicht-3008';
		const text = verfaelscht(ersterIndex('abschnitt'), (b) => {
			b.abschnitt = erfunden;
		});
		assert.throws(() => L.leseBesitzer(text, LISTE), (err: Error) => err.message.includes(erfunden));
	});

	test('AC-3: Abschnitt existiert, aber nicht in diesem Reiter ⇒ Fehler (Tripel zählt, nicht der Name allein)', () => {
		const i = ersterIndex('abschnitt');
		const b = ROH().besitzer[i];
		// Ein Reiter desselben ctx, in dem der Abschnitt NICHT vorkommt.
		const reiterMitAbschnitt = new Set(LISTE.filter((e) => e.ctx === b.ctx && e.abschnitt === b.abschnitt).map((e) => e.reiter));
		const fremd = [...new Set(LISTE.filter((e) => e.ctx === b.ctx).map((e) => e.reiter))].find((r) => !reiterMitAbschnitt.has(r));
		assert.ok(fremd, `kein Reiter ohne Abschnitt „${String(b.abschnitt)}“ in ctx ${String(b.ctx)}`);
		const text = verfaelscht(i, (x) => {
			x.reiter = fremd;
		});
		assert.throws(() => L.leseBesitzer(text, LISTE), (err: Error) => err.message.includes(String(b.abschnitt)));
	});

	test('AC-3: Kopie mit erfundenem ctx im Abschnitts-Besitzer ⇒ Fehler', () => {
		const i = ersterIndex('abschnitt');
		const abschnitt = String(ROH().besitzer[i].abschnitt);
		const text = verfaelscht(i, (b) => {
			b.ctx = 'gibtesnicht';
		});
		assert.throws(() => L.leseBesitzer(text, LISTE), (err: Error) => err.message.includes(abschnitt));
	});

	test('AC-3: alle Abschnitts-Besitzer des echten Bestands nennen ein vorhandenes Tripel', () => {
		const tripel = new Set(LISTE.map((e) => `${e.ctx}|${e.reiter}|${e.abschnitt}`));
		const abschnitte = ROH().besitzer.filter((b) => b.art === 'abschnitt');
		assert.ok(abschnitte.length > 0, 'keine Abschnitts-Besitzer im Bestand');
		const verwaist = abschnitte.map((b) => `${String(b.ctx)}|${String(b.reiter)}|${String(b.abschnitt)}`).filter((t) => !tripel.has(t));
		assert.deepEqual(verwaist, []);
	});
});
