// TDD RED — Issue #3006 (Epic #2913), AC-19: Kopf-Einträge der Elementliste nachgezogen.
// Spec: docs/specs/modules/feat_3006_bereichskoepfe.md.
// doc-compliance-test — Datentest über docs/context/einstellungen_neu/elementliste.json: jeder Eintrag im
// Abschnitt `abschnittskopf` trägt i18n_key, text_de, text_en, ist keine Lücke mehr, und die Werte stimmen
// mit dem Katalog (DE/EN) überein. Die 52 Eintrags-IDs bleiben unverändert.
//
//   cd frontend && npm test -- src/lib/__tests__/elementliste_bereichskoepfe_3006.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../..');
const LISTE = path.resolve(FRONTEND, '..', 'docs/context/einstellungen_neu/elementliste.json');

function katalog(lang: 'de' | 'en'): Record<string, string> {
	const dir = path.join(FRONTEND, 'src/lib/i18n/messages', lang);
	const out: Record<string, string> = {};
	for (const f of readdirSync(dir).filter((n) => n.endsWith('.json'))) Object.assign(out, JSON.parse(readFileSync(path.join(dir, f), 'utf8')));
	return out;
}
const DE = katalog('de');
const EN = katalog('en');

interface Eintrag {
	id: string;
	abschnitt: string | null;
	i18n_key: string | null;
	text_de: string | null;
	text_en: string | null;
	luecke: boolean;
}
const kopfEintraege = (): Eintrag[] =>
	(JSON.parse(readFileSync(LISTE, 'utf8')).elemente as Eintrag[]).filter((e) => e.abschnitt === 'abschnittskopf');

// Stand vor #3006 (IDs dürfen sich nicht ändern). Ausnahme #3122: Mockup Fassung 4 (ADR-0124 Nr. 10, der Bereich
// heißt „Orte“) hat im Reiter Orte einen neuen Erklärtext; die vier Einträge dazu (je Zustand einer) tragen
// deshalb neue IDs, siehe OFFEN_3122.
const IDS = [
	'trip.wetter.normal.-.abschnittskopf.6bcb913270', 'trip.wetter.normal.-.abschnittskopf.014cfaa802',
	'trip.zustellung.normal.-.abschnittskopf.eb2de3f663', 'trip.zustellung.normal.-.abschnittskopf.4472458afb',
	'trip.etappen.normal.-.abschnittskopf.564c3bfc82', 'trip.etappen.normal.-.abschnittskopf.5095d2c61e',
	'trip.wetter.laedt.-.abschnittskopf.af919500d2', 'trip.wetter.laedt.-.abschnittskopf.e026fc1ad5',
	'trip.zustellung.laedt.-.abschnittskopf.a2a7c31d3a', 'trip.zustellung.laedt.-.abschnittskopf.e84168469c',
	'trip.etappen.laedt.-.abschnittskopf.2fc74c53e2', 'trip.etappen.laedt.-.abschnittskopf.ce7d926c22',
	'trip.wetter.fehler.-.abschnittskopf.b8e54e2d6a', 'trip.wetter.fehler.-.abschnittskopf.743ed3ce2b',
	'trip.zustellung.fehler.-.abschnittskopf.5a2e06f852', 'trip.zustellung.fehler.-.abschnittskopf.d118b49940',
	'trip.etappen.fehler.-.abschnittskopf.19f84af1b4', 'trip.etappen.fehler.-.abschnittskopf.9c2e1a70fc',
	'trip.wetter.luecken.-.abschnittskopf.7103a2ef62', 'trip.wetter.luecken.-.abschnittskopf.579ce0f634',
	'trip.zustellung.luecken.-.abschnittskopf.f1506c0751', 'trip.zustellung.luecken.-.abschnittskopf.110bdf241f',
	'trip.etappen.luecken.-.abschnittskopf.734d9e597e', 'trip.etappen.luecken.-.abschnittskopf.2c82716d03',
	'orte.wetter.normal.-.abschnittskopf.e742f73d7e', 'orte.wetter.normal.-.abschnittskopf.f3d1024d07',
	'orte.zustellung.normal.-.abschnittskopf.12f6e32b2a', 'orte.zustellung.normal.-.abschnittskopf.7c037eafcc',
	'orte.orte.normal.-.abschnittskopf.3c46bf4553', 'orte.orte.normal.-.abschnittskopf.52b9404608',
	'orte.orte.normal.-.abschnittskopf.91a11dce09', 'orte.wetter.laedt.-.abschnittskopf.85ca311eb0',
	'orte.wetter.laedt.-.abschnittskopf.cf459ff99f', 'orte.zustellung.laedt.-.abschnittskopf.5e0cb73ca4',
	'orte.zustellung.laedt.-.abschnittskopf.761366fa43', 'orte.orte.laedt.-.abschnittskopf.3d6c7c7bbd',
	'orte.orte.laedt.-.abschnittskopf.11a0d70022', 'orte.orte.laedt.-.abschnittskopf.d456049fce',
	'orte.wetter.fehler.-.abschnittskopf.abe818d8b9', 'orte.wetter.fehler.-.abschnittskopf.72ee6300eb',
	'orte.zustellung.fehler.-.abschnittskopf.ae5a26a81d', 'orte.zustellung.fehler.-.abschnittskopf.24b36eca5b',
	'orte.orte.fehler.-.abschnittskopf.c9d630e620', 'orte.orte.fehler.-.abschnittskopf.ae19a719ba',
	'orte.orte.fehler.-.abschnittskopf.18f5127a75', 'orte.wetter.luecken.-.abschnittskopf.1d77a0a895',
	'orte.wetter.luecken.-.abschnittskopf.8e1d1f4091', 'orte.zustellung.luecken.-.abschnittskopf.d5de8ddbfc',
	'orte.zustellung.luecken.-.abschnittskopf.923bb4d327', 'orte.orte.luecken.-.abschnittskopf.884ee69bbd',
	'orte.orte.luecken.-.abschnittskopf.3a5fd308ea', 'orte.orte.luecken.-.abschnittskopf.9cd46dac74'
];

// #3122: Der neue Erklärtext des Reiters Orte („Schon ein einzelner Ort ergibt ein vollständiges Briefing. …“)
// steht noch nicht im Katalog (dort der alte Text, vergleich.hub.kopf.orte_erklaer). Genau diese vier Einträge
// sind bis zum Bau zu #3122 eine Lücke. Der Test ist beidseitig streng: Kommt der Katalogtext und wird die
// Elementliste neu erzeugt, wird er rot, dann muss diese Ausnahme entfallen.
const OFFEN_3122 = [
	'orte.orte.normal.-.abschnittskopf.52b9404608',
	'orte.orte.laedt.-.abschnittskopf.11a0d70022',
	'orte.orte.fehler.-.abschnittskopf.ae19a719ba',
	'orte.orte.luecken.-.abschnittskopf.3a5fd308ea'
];

test('AC-19: Kopf-Einträge — IDs unverändert', () => {
	assert.deepEqual(kopfEintraege().map((e) => e.id).sort(), [...IDS].sort());
});

test('AC-19: Kopf-Einträge — keine Lücke, i18n_key/text_de/text_en gesetzt und gleich dem Katalog', () => {
	const fehler: string[] = [];
	for (const e of kopfEintraege()) {
		if (OFFEN_3122.includes(e.id)) {
			if (!e.luecke || e.i18n_key || e.text_en) fehler.push(`${e.id}: keine Lücke mehr — Ausnahme OFFEN_3122 entfernen`);
			if (!e.text_de?.startsWith('Schon ein einzelner Ort')) fehler.push(`${e.id}: unerwarteter Text „${e.text_de}“`);
			continue;
		}
		if (e.luecke) fehler.push(`${e.id}: luecke:true`);
		if (!e.i18n_key) {
			fehler.push(`${e.id}: i18n_key fehlt`);
			continue;
		}
		if (DE[e.i18n_key] !== e.text_de) fehler.push(`${e.id}: DE-Katalog „${DE[e.i18n_key]}“ ≠ text_de „${e.text_de}“`);
		if (!e.text_en) fehler.push(`${e.id}: text_en fehlt`);
		else if (EN[e.i18n_key] !== e.text_en) fehler.push(`${e.id}: EN-Katalog „${EN[e.i18n_key]}“ ≠ text_en „${e.text_en}“`);
	}
	assert.deepEqual(fehler, [], fehler.join('\n'));
});
