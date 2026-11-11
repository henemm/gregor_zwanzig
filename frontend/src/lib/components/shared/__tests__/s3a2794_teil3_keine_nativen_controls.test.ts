// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2. AC-40 (Kern-Haelfte).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-40, Implementation Details §4 (Design, ADR-0111)
//
// Im Reiter-Ordner organisms/wetter-tab/ (WetterTab + acht Bausteine), in DayWindowCard.svelte und in
// SavePresetDialog.svelte gibt es kein natives <select>, keine native Checkbox und kein natives
// Datum-/Zeitfeld (<input type="checkbox|date|time|datetime-local|month|week">, auch kein dynamisches
// type={…}). DayWindowCard nutzt fuer von/bis das Select-Atom ui/select/Select.svelte.
// Der Test ist bei fehlendem Ordner/fehlenden Bausteinen ROT, nicht leer-gruen.
// Kontrast, Touch-Ziel, Panel-Rahmen misst Playwright (s3a2794-teil3-design.spec.ts).
//
// RED heute: Ordner organisms/wetter-tab/ fehlt; DayWindowCard hat zwei native <select>.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_teil3_keine_nativen_controls.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import { svelteAst, existiert, attribut, type Knoten } from './s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const ORDNER = join(SHARED, '..', 'organisms', 'wetter-tab');
const DAY_WINDOW = join(SHARED, 'weather-metrics-tab', 'DayWindowCard.svelte');
const DIALOG = join(SHARED, 'weather-metrics-tab', 'SavePresetDialog.svelte');

/** Bausteine laut Spec (Source, Trip/Ortsvergleich-Teilung). */
// #2913 Teil 2 (K-1): der Organismus mit Zustand heißt WetterTabInhalt; die Seite shared/WetterTab.svelte
// wird unten zusätzlich geprüft.
const SEITE = join(SHARED, 'WetterTab.svelte');
const BAUSTEINE = [
	'WetterTabInhalt', 'VorlageKarte', 'AlarmAbKopf', 'MetrikZeile', 'AmpelLeiste',
	'GrenzenEditor', 'NichtImBriefing', 'WarnungenRadarKarte', 'AnpassenKarte'
];
const VERBOTENE_TYPEN = new Set(['checkbox', 'date', 'time', 'datetime-local', 'month', 'week']);

function svelteDateien(ordner: string): string[] {
	const out: string[] = [];
	for (const n of readdirSync(ordner)) {
		if (n === '__tests__') continue;
		const p = join(ordner, n);
		if (statSync(p).isDirectory()) out.push(...svelteDateien(p));
		else if (n.endsWith('.svelte')) out.push(p);
	}
	return out;
}

/** Native Controls einer Datei (Zeile + Art). */
function nativeControls(datei: string): string[] {
	const { ast, quelle } = svelteAst(datei);
	const funde: string[] = [];
	const zeile = (k: Knoten) => quelle.slice(0, k.start).split('\n').length;
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'RegularElement' && k.name === 'select') funde.push(`<select> Zeile ${zeile(k)}`);
		if (k.type === 'RegularElement' && k.name === 'input') {
			const t = attribut(k, quelle, 'type');
			if (t?.ausdruck) funde.push(`<input type={${t.ausdruck}}> Zeile ${zeile(k)} (dynamischer Typ nicht pruefbar)`);
			else if (t?.literal && VERBOTENE_TYPEN.has(t.literal)) funde.push(`<input type="${t.literal}"> Zeile ${zeile(k)}`);
		}
		for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
	})(ast.fragment);
	return funde;
}

describe('AC-40: keine nativen Controls im Reiter Wetter und im Dialog', () => {
	test('s3a2794_t3_reiter_ordner_mit_allen_bausteinen_vorhanden', () => {
		assert.ok(existiert(ORDNER), 'TDD RED: Ordner organisms/wetter-tab/ fehlt');
		const da = svelteDateien(ORDNER).map((p) => p.split('/').pop()!.replace(/\.svelte$/, ''));
		const fehlt = BAUSTEINE.filter((b) => !da.includes(b));
		assert.deepEqual(fehlt, [], `Bausteine fehlen unter organisms/wetter-tab/: ${fehlt.join(', ')}`);
	});

	test('s3a2794_t3_reiter_ordner_ohne_native_controls', () => {
		assert.ok(existiert(ORDNER), 'TDD RED: Ordner organisms/wetter-tab/ fehlt');
		const dateien = svelteDateien(ORDNER);
		assert.ok(dateien.length >= BAUSTEINE.length, `nur ${dateien.length} .svelte-Dateien gefunden — Pruefung waere leer-gruen`);
		const funde = dateien.flatMap((d) => nativeControls(d).map((f) => `${relative(SHARED, d)}: ${f}`));
		assert.deepEqual(funde, [], 'AC-40: native Controls im Reiter Wetter');
	});

	for (const [name, datei] of [['DayWindowCard', DAY_WINDOW], ['SavePresetDialog', DIALOG], ['WetterTab', SEITE]] as const) {
		test(`s3a2794_t3_${name}_ohne_native_controls`, () => {
			assert.ok(existiert(datei), `${name}.svelte fehlt`);
			assert.deepEqual(nativeControls(datei), [], `AC-40: native Controls in ${name}.svelte`);
		});
	}

	test('s3a2794_t3_daywindowcard_nutzt_select_atom_fuer_von_und_bis', () => {
		const { ast } = svelteAst(DAY_WINDOW);
		let lokal: string | null = null;
		for (const s of (ast.instance?.content?.body ?? []) as Knoten[]) {
			if (s.type !== 'ImportDeclaration') continue;
			if (!/components\/ui\/select(\/Select\.svelte|\/index(\.ts|\.js)?)?$|^(\.\.\/)+ui\/select(\/Select\.svelte)?$/.test(s.source.value)) continue;
			for (const sp of s.specifiers as Knoten[]) {
				if (sp.type === 'ImportDefaultSpecifier' || sp.imported?.name === 'Select') lokal = sp.local.name;
			}
		}
		assert.ok(lokal, 'DayWindowCard importiert das Select-Atom ui/select nicht');
		let anzahl = 0;
		(function lauf(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'Component' && k.name === lokal) anzahl++;
			for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
		})(ast.fragment);
		assert.ok(anzahl >= 2, `DayWindowCard: Select-Atom ${anzahl}× eingebettet, erwartet von UND bis`);
	});
});
