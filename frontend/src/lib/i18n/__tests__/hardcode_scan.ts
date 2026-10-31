// Issue #2649 (i18n S4, Epic #2644) — Test-Hilfsmodul (nicht ausgeliefert):
// findet hartkodierte Nutzertexte in Svelte-Markup (Konventionen Abschnitt 3).
// Aufbereitung erhaelt die Zeilennummern: jeder entfernte Bereich wird durch
// ein Leerzeichen plus genau seine Zeilenumbrueche ersetzt. Svelte-Ausdruecke
// werden durch AUSDRUCK ersetzt, damit gemischte Attributwerte erkennbar bleiben.
// Startstand messen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     src/lib/i18n/__tests__/hardcode_scan.ts --messen
// Spec: docs/specs/modules/i18n_s4_ratsche_frontend_2649.md

import { readdirSync, statSync, readFileSync } from 'node:fs';
import { join, relative, sep, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export type Treffer = { zeile: number; art: 'text' | 'attribut'; text: string };
export type DateiErgebnis = { pfad: string; treffer: Treffer[] };
export type Pruefung = { ohneEintrag: string[]; eintraegeOhneTreffer: string[] };

export const MINDEST_DATEIEN = 150;
const AUSDRUCK = '\u0001';
const BUCHSTABE = /[A-Za-zÄÖÜäöüß]/g;
const ATTRIBUT = /(?<=\s)(title|aria-label|placeholder|alt|label)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;

function leer(bereich: string, ersatz = ' '): string {
	return ersatz + bereich.replace(/[^\n]/g, '');
}

function hatZweiBuchstaben(text: string): boolean {
	return (text.match(BUCHSTABE) ?? []).length >= 2;
}

/** Ende eines String-Literals ab Position `i` (Anfuehrungszeichen), Index nach dem Schluss. */
function stringEnde(q: string, i: number): number {
	const zeichen = q[i];
	for (let j = i + 1; j < q.length; j++) {
		if (q[j] === '\\') j++;
		else if (q[j] === zeichen) return j + 1;
	}
	return q.length;
}

/** Ersetzt jeden Svelte-Ausdruck `{…}` (beliebig geschachtelt, Strings beachtet). */
function ohneAusdruecke(q: string): string {
	let aus = '';
	let i = 0;
	while (i < q.length) {
		if (q[i] !== '{') {
			aus += q[i++];
			continue;
		}
		let tiefe = 0;
		let j = i;
		for (; j < q.length; j++) {
			const c = q[j];
			if (c === '"' || c === "'" || c === '`') j = stringEnde(q, j) - 1;
			else if (c === '{') tiefe++;
			else if (c === '}' && --tiefe === 0) break;
		}
		aus += leer(q.slice(i, j + 1), AUSDRUCK);
		i = j + 1;
	}
	return aus;
}

function aufbereiten(quelltext: string): string {
	const ohneBloecke = quelltext
		.replace(/<!--[\s\S]*?-->/g, (m) => leer(m))
		.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, (m) => leer(m))
		.replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, (m) => leer(m));
	return ohneAusdruecke(ohneBloecke).replace(/&(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);/g, ' ');
}

function zeileBei(q: string, index: number): number {
	let zeile = 1;
	for (let i = 0; i < index; i++) if (q[i] === '\n') zeile++;
	return zeile;
}

/** Textknoten und statische beschriftende Attribute mit mindestens zwei Buchstaben. */
export function scanneMarkup(quelltext: string): Treffer[] {
	const q = aufbereiten(quelltext);
	const treffer: { index: number; t: Treffer }[] = [];
	for (const tag of q.matchAll(/<[^>]*>/g)) {
		for (const a of tag[0].matchAll(ATTRIBUT)) {
			const wert = a[2] ?? a[3];
			if (wert.includes(AUSDRUCK) || !hatZweiBuchstaben(wert)) continue;
			const index = tag.index + a.index;
			treffer.push({ index, t: { zeile: zeileBei(q, index), art: 'attribut', text: wert.trim() } });
		}
	}
	for (const knoten of q.matchAll(/(^|>)([^<]+)/g)) {
		const roh = knoten[2];
		if (!hatZweiBuchstaben(roh)) continue;
		const index = knoten.index + knoten[1].length + roh.search(/\S/);
		const text = roh.replaceAll(AUSDRUCK, ' ').replace(/\s+/g, ' ').trim();
		treffer.push({ index, t: { zeile: zeileBei(q, index), art: 'text', text } });
	}
	return treffer.sort((a, b) => a.index - b.index).map((x) => x.t);
}

/** Pfad relativ zu frontend/src/ mit Schraegstrichen. */
export function wirdGescannt(pfad: string): boolean {
	return (
		pfad.endsWith('.svelte') &&
		!pfad.split('/').includes('__tests__') &&
		!pfad.startsWith('routes/_design') &&
		!pfad.startsWith('routes/email-preview-dev')
	);
}

function svelteDateien(wurzel: string, verzeichnis = wurzel): string[] {
	let namen: string[];
	try {
		namen = readdirSync(verzeichnis);
	} catch {
		return [];
	}
	const dateien: string[] = [];
	for (const name of namen) {
		const voll = join(verzeichnis, name);
		if (statSync(voll).isDirectory()) dateien.push(...svelteDateien(wurzel, voll));
		else dateien.push(relative(wurzel, voll).split(sep).join('/'));
	}
	return dateien;
}

/** Alle gescannten Svelte-Dateien unter `wurzel` (auch ohne Treffer), sortiert. */
export function scanneVerzeichnis(wurzel: string): DateiErgebnis[] {
	return svelteDateien(wurzel)
		.filter(wirdGescannt)
		.sort()
		.map((pfad) => ({ pfad, treffer: scanneMarkup(readFileSync(join(wurzel, pfad), 'utf8')) }));
}

function deckt(eintrag: string, pfad: string): boolean {
	return eintrag.endsWith('/') ? pfad.startsWith(eintrag) : pfad === eintrag;
}

/** Beide Richtungen: Treffer ohne Eintrag und Eintrag ohne Treffer. */
export function pruefeGegenAllowlist(ergebnisse: DateiErgebnis[], allowlist: string[]): Pruefung {
	const belastet = ergebnisse.filter((e) => e.treffer.length > 0).map((e) => e.pfad);
	const ohneEintrag = ergebnisse
		.filter((e) => !allowlist.some((a) => deckt(a, e.pfad)))
		.flatMap((e) => e.treffer.map((t) => `${e.pfad}:${t.zeile}  "${t.text}"`));
	const eintraegeOhneTreffer = allowlist
		.filter((a) => !belastet.some((p) => deckt(a, p)))
		.map((a) => `Eintrag ohne Treffer: ${a} – aus hardcode_allowlist.json streichen`);
	return { ohneEintrag, eintraegeOhneTreffer };
}

/** Scan + Pruefung; bricht ab, wenn der Messaufbau leer ist (gegen vakuum-gruen). */
export function pruefeVerzeichnis(
	wurzel: string,
	allowlist: string[],
	mindestDateien = MINDEST_DATEIEN
): Pruefung {
	const ergebnisse = scanneVerzeichnis(wurzel);
	if (ergebnisse.length < mindestDateien) {
		throw new Error(
			`Messaufbau leer: nur ${ergebnisse.length} Svelte-Dateien unter ${wurzel} (mindestens ${mindestDateien})`
		);
	}
	return pruefeGegenAllowlist(ergebnisse, allowlist);
}

/** Granularitaet des Startstands: routes/<ordner>/ bzw. lib/components/<ordner>/, sonst die Datei. */
export function allowlistEintrag(pfad: string): string {
	const teile = pfad.split('/');
	if (teile[0] === 'routes' && teile.length > 2) return `routes/${teile[1]}/`;
	if (teile[0] === 'lib' && teile[1] === 'components' && teile.length > 3) {
		return `lib/components/${teile[2]}/`;
	}
	return pfad;
}

function messen(wurzel: string): void {
	const belastet = scanneVerzeichnis(wurzel).filter((e) => e.treffer.length > 0);
	const eintraege = [...new Set(belastet.map((e) => allowlistEintrag(e.pfad)))].sort();
	const zeilen = belastet.reduce((n, e) => n + e.treffer.length, 0);
	console.error(
		`gescannt: ${scanneVerzeichnis(wurzel).length} · Dateien mit Treffern: ${belastet.length}` +
			` · Trefferzeilen: ${zeilen} · Eintraege: ${eintraege.length}`
	);
	console.log(JSON.stringify(eintraege, null, '\t'));
}

if (process.argv.includes('--messen') && import.meta.url === pathToFileURL(process.argv[1]).href) {
	messen(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..'));
}
