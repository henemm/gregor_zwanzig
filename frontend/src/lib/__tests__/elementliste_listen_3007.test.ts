// TDD RED — Issue #3007 (Epic #2913), AC-19: Listen-Einträge der Elementliste (Etappen, Orte) nachgezogen.
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md.
// doc-compliance-test — Datentest über docs/context/einstellungen_neu/elementliste.json: jeder Eintrag in
// `trip/etappen/liste` und `orte/orte/liste` (76 = 10 + 9 je vier Zustände) trägt i18n_key, text_de, text_en,
// ist keine Lücke mehr; Einträge ohne Muster stimmen mit dem Katalog überein, Einträge mit Muster
// (Beispieldaten des Mockups) verweisen auf einen Katalogschlüssel mit Platzhalter in DE und EN.
// Die 76 IDs bleiben unverändert.
//
//   cd frontend && npm test -- src/lib/__tests__/elementliste_listen_3007.test.ts

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
	reiter: string;
	abschnitt: string | null;
	muster: string | null;
	i18n_key: string | null;
	text_de: string | null;
	text_en: string | null;
	luecke: boolean;
}
const listenEintraege = (): Eintrag[] =>
	(JSON.parse(readFileSync(LISTE, 'utf8')).elemente as Eintrag[]).filter(
		(e) => (e.reiter === 'etappen' || e.reiter === 'orte') && e.abschnitt === 'liste'
	);

// Stand vor #3007 (IDs dürfen sich nicht ändern).
const IDS = [
	'orte.orte.fehler.-.liste.2257f80170',
	'orte.orte.fehler.-.liste.565856252f',
	'orte.orte.fehler.-.liste.580e520640',
	'orte.orte.fehler.-.liste.59337f6bfd',
	'orte.orte.fehler.-.liste.77590a54c5',
	'orte.orte.fehler.-.liste.8197c25333',
	'orte.orte.fehler.-.liste.adf6532fcb',
	'orte.orte.fehler.-.liste.b26206f245',
	'orte.orte.fehler.-.liste.c082da9f6d',
	'orte.orte.laedt.-.liste.23d9c2c10f',
	'orte.orte.laedt.-.liste.47ccdf44a2',
	'orte.orte.laedt.-.liste.4db5b5b350',
	'orte.orte.laedt.-.liste.567ffe9952',
	'orte.orte.laedt.-.liste.60d471a2fb',
	'orte.orte.laedt.-.liste.a752740f4f',
	'orte.orte.laedt.-.liste.d7aebe4f7b',
	'orte.orte.laedt.-.liste.e00446552b',
	'orte.orte.laedt.-.liste.ef3ca91a06',
	'orte.orte.luecken.-.liste.20375067bf',
	'orte.orte.luecken.-.liste.51b2fd4f98',
	'orte.orte.luecken.-.liste.658c0024d7',
	'orte.orte.luecken.-.liste.a21006a2c1',
	'orte.orte.luecken.-.liste.caca302367',
	'orte.orte.luecken.-.liste.de12502657',
	'orte.orte.luecken.-.liste.e5711a9f5e',
	'orte.orte.luecken.-.liste.e892b6e2d2',
	'orte.orte.luecken.-.liste.fdebc6693e',
	'orte.orte.normal.-.liste.02a58a4406',
	'orte.orte.normal.-.liste.123ca32e56',
	'orte.orte.normal.-.liste.31be045962',
	'orte.orte.normal.-.liste.4760791422',
	'orte.orte.normal.-.liste.63a7f413c0',
	'orte.orte.normal.-.liste.9c3c1d1eb2',
	'orte.orte.normal.-.liste.a2205af060',
	'orte.orte.normal.-.liste.a410470cea',
	'orte.orte.normal.-.liste.bf4a0cfd79',
	'trip.etappen.fehler.-.liste.08723778e3',
	'trip.etappen.fehler.-.liste.08beec735f',
	'trip.etappen.fehler.-.liste.149704c4bb',
	'trip.etappen.fehler.-.liste.1969ce724e',
	'trip.etappen.fehler.-.liste.21128cb1fa',
	'trip.etappen.fehler.-.liste.3d4cfab5c2',
	'trip.etappen.fehler.-.liste.79bc834b3d',
	'trip.etappen.fehler.-.liste.c413f3e67a',
	'trip.etappen.fehler.-.liste.d06561e349',
	'trip.etappen.fehler.-.liste.fb7f6d659f',
	'trip.etappen.laedt.-.liste.02cdd77b11',
	'trip.etappen.laedt.-.liste.0853ab711f',
	'trip.etappen.laedt.-.liste.1b86fd63a8',
	'trip.etappen.laedt.-.liste.3adef15b4c',
	'trip.etappen.laedt.-.liste.3e3e4e03dc',
	'trip.etappen.laedt.-.liste.4470d60542',
	'trip.etappen.laedt.-.liste.570392019a',
	'trip.etappen.laedt.-.liste.583c7ceb84',
	'trip.etappen.laedt.-.liste.839ad75c6d',
	'trip.etappen.laedt.-.liste.a95b684cb4',
	'trip.etappen.luecken.-.liste.04d595eae4',
	'trip.etappen.luecken.-.liste.0a0fb61481',
	'trip.etappen.luecken.-.liste.134e3304f0',
	'trip.etappen.luecken.-.liste.1e5e7ce839',
	'trip.etappen.luecken.-.liste.2654066eb3',
	'trip.etappen.luecken.-.liste.31c40d3e0b',
	'trip.etappen.luecken.-.liste.473b743534',
	'trip.etappen.luecken.-.liste.a57b959036',
	'trip.etappen.luecken.-.liste.aefbd3fd74',
	'trip.etappen.luecken.-.liste.deaf47045a',
	'trip.etappen.normal.-.liste.0a303a184d',
	'trip.etappen.normal.-.liste.215b8fdc26',
	'trip.etappen.normal.-.liste.2a613e9cef',
	'trip.etappen.normal.-.liste.2e4760e8f5',
	'trip.etappen.normal.-.liste.3893722373',
	'trip.etappen.normal.-.liste.3afc78acef',
	'trip.etappen.normal.-.liste.3dd383a647',
	'trip.etappen.normal.-.liste.9eb6ae6e66',
	'trip.etappen.normal.-.liste.b24b3f85da',
	'trip.etappen.normal.-.liste.da7b42920f'
];

test('AC-19: Listen-Einträge Etappen/Orte — 76 IDs unverändert', () => {
	assert.deepEqual(listenEintraege().map((e) => e.id).sort(), [...IDS].sort());
});

test('AC-19: Listen-Einträge — keine Lücke, i18n_key/text_de/text_en gesetzt und aus dem Katalog', () => {
	const fehler: string[] = [];
	for (const e of listenEintraege()) {
		if (e.luecke) fehler.push(`${e.id}: luecke:true`);
		if (!e.text_de) fehler.push(`${e.id}: text_de fehlt`);
		if (!e.text_en) fehler.push(`${e.id}: text_en fehlt`);
		if (!e.i18n_key) {
			fehler.push(`${e.id}: i18n_key fehlt`);
			continue;
		}
		const de = DE[e.i18n_key];
		const en = EN[e.i18n_key];
		if (typeof de !== 'string' || typeof en !== 'string') {
			fehler.push(`${e.id}: Schlüssel ${e.i18n_key} fehlt in DE oder EN`);
			continue;
		}
		if (/\{\w+\}/.test(de)) {
			// Muster-Eintrag: Platzhalter in beiden Sprachen, Festtext des Schlüssels steht im Beispieltext.
			if (!/\{\w+\}/.test(en)) fehler.push(`${e.id}: EN-Wert „${en}“ ohne Platzhalter`);
			for (const [wert, beispiel, sp] of [[de, e.text_de, 'DE'], [en, e.text_en, 'EN']] as const) {
				const teile = wert.split(/\{\w+\}/).filter((t) => t.trim() !== '');
				for (const t of teile) if (beispiel && !beispiel.includes(t.trim())) fehler.push(`${e.id}: ${sp}-Beispiel „${beispiel}“ passt nicht zu „${wert}“`);
			}
		} else {
			if (de !== e.text_de) fehler.push(`${e.id}: DE-Katalog „${de}“ ≠ text_de „${e.text_de}“`);
			if (en !== e.text_en) fehler.push(`${e.id}: EN-Katalog „${en}“ ≠ text_en „${e.text_en}“`);
		}
	}
	assert.deepEqual(fehler, [], fehler.join('\n'));
});
