// TDD RED — Issue #2794 S3a Teil-PR 4a: Struktur-Waechter fuer das Entfernen
// der alten Wertebereiche-Oberflaeche und den Umzug der Logikmodule.
//
//   AC-31  keine Quelle importiert mehr aus `corridor-editor/`; die entfernten
//          Oberflaechen existieren nicht mehr; die Bausteine des
//          Uebergangsreiters Zustellung existieren weiter.
//   AC-47  die drei Logikmodule (+ Pruefstand, Test) liegen unter `shared/wetter-tab/`.
//   AC-45  TripNewEditor und CompareNewEditor betten keinen CorridorEditor mehr
//          ein; die Vorbelegung haengt an GENAU EINEM `$effect` je Editor
//          (AST-Auswahl, kein Textmuster).
//   AC-46  kein `"default"`-Fallback fuer eine user_id in den geaenderten Dateien.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/wetter-tab/__tests__/s3a2794_teil4a_umzug_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { findeKomponenten, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';

// Pfadregel #1409: relativ zur eigenen Datei.
const HIER = dirname(fileURLToPath(import.meta.url));
const KOMPONENTEN = resolve(HIER, '../../..'); // frontend/src/lib/components
const FRONTEND = resolve(KOMPONENTEN, '../../..'); // frontend
const SHARED = join(KOMPONENTEN, 'shared');
const WETTER_TAB = join(SHARED, 'wetter-tab');

function dateienUnter(wurzel: string): string[] {
	const out: string[] = [];
	if (!existsSync(wurzel)) return out;
	for (const name of readdirSync(wurzel)) {
		if (name === 'node_modules' || name.startsWith('.')) continue;
		const p = join(wurzel, name);
		if (statSync(p).isDirectory()) out.push(...dateienUnter(p));
		else if (/\.(ts|js|svelte)$/.test(name)) out.push(p);
	}
	return out;
}

// Import-Quellen (static import/export-from, dynamic import()) — ein Pfad, der
// `corridor-editor/` enthaelt, ist ein toter Import nach dem Umzug.
const IMPORT_QUELLE = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)['"]([^'"]+)['"]/g;

describe('AC-31/AC-47 Umzug: niemand importiert mehr aus corridor-editor/', () => {
	test('keine Quell- oder Testdatei unter src/ und e2e/ importiert einen corridor-editor/-Pfad', () => {
		const selbst = fileURLToPath(import.meta.url);
		const treffer: string[] = [];
		for (const datei of [...dateienUnter(join(FRONTEND, 'src')), ...dateienUnter(join(FRONTEND, 'e2e'))]) {
			if (datei === selbst) continue;
			const quelle = readFileSync(datei, 'utf-8');
			for (const m of quelle.matchAll(IMPORT_QUELLE)) {
				if (m[1].includes('corridor-editor/')) treffer.push(`${relative(FRONTEND, datei)} → ${m[1]}`);
			}
		}
		assert.deepEqual(treffer, [], `Toter Import nach dem Umzug (${treffer.length}):\n  ${treffer.join('\n  ')}`);
	});

	test('der Ordner shared/corridor-editor/ existiert nicht mehr', () => {
		assert.equal(existsSync(join(SHARED, 'corridor-editor')), false, 'shared/corridor-editor/ steht noch — Altcode lebt weiter');
	});

	for (const modul of [
		'corridorEditorState.ts',
		'compareMetricCatalogLoader.ts',
		'wertebereicheVergleichSpeicherung.ts',
		'corridorEditorState.test.ts',
		'__tests__/wertebereicheVergleichPruefstand.ts',
		'anlegeVorbelegung.ts',
	]) {
		test(`Logikmodul liegt am neuen Ort: shared/wetter-tab/${modul}`, () => {
			assert.ok(existsSync(join(WETTER_TAB, modul)), `fehlt: shared/wetter-tab/${modul}`);
		});
	}
});

describe('AC-31 entfernte Oberflaechen sind weg, Zustellungs-Bausteine bleiben', () => {
	for (const weg of [
		'trip-detail/MetricCheckbox.svelte',
		'trip-detail/MetricGroup.svelte',
		'ui/horizon-chip',
		'molecules/HorizonChips.svelte',
		'organisms/MetricsEditorContextBar.svelte',
	]) {
		test(`entfernt: ${weg}`, () => {
			assert.equal(existsSync(join(KOMPONENTEN, weg)), false, `${weg} existiert noch`);
		});
	}

	test('kein Barrel exportiert noch eine entfernte Komponente', () => {
		const namen = /\b(MetricCheckbox|MetricGroup|HorizonChips?|MetricsEditorContextBar|CorridorEditor(?:Mobile)?)\b/;
		const treffer: string[] = [];
		for (const barrel of ['organisms/index.ts', 'trip-detail/index.ts', 'molecules/index.ts', 'shared/index.ts']) {
			const p = join(KOMPONENTEN, barrel);
			if (!existsSync(p)) continue;
			for (const zeile of readFileSync(p, 'utf-8').split('\n')) {
				if (/^\s*export\b/.test(zeile) && namen.test(zeile)) treffer.push(`${barrel}: ${zeile.trim()}`);
			}
		}
		assert.deepEqual(treffer, []);
	});

	for (const bleibt of [
		'shared/AlarmeTab.svelte',
		'shared/alarme-tab',
		'trip-detail/AlarmeScheduleTab.svelte',
		'shared/WeatherMetricsTab.svelte',
		'shared/weather-metrics-tab',
		'shared/layout-tab',
		'alerts-tab',
	]) {
		test(`bleibt (Uebergangsreiter Zustellung bis S3b): ${bleibt}`, () => {
			assert.ok(existsSync(join(KOMPONENTEN, bleibt)), `${bleibt} wurde entfernt — der Reiter Zustellung braucht es bis S3b (#2795)`);
		});
	}
});

// ── AC-45: je Editor genau ein Vorbelegungs-Effekt, kein versteckter Mount ──

function instanzAst(pfad: string): { ast: Knoten; quelle: string } {
	const quelle = readFileSync(pfad, 'utf-8');
	return { ast: parse(quelle, { modern: true }) as Knoten, quelle };
}

function nennt(knoten: unknown, namen: Set<string>): boolean {
	if (knoten === null || typeof knoten !== 'object') return false;
	if (Array.isArray(knoten)) return knoten.some((k) => nennt(k, namen));
	const k = knoten as Knoten;
	if (k.type === 'Identifier' && namen.has(k.name)) return true;
	for (const key of Object.keys(k)) {
		if (key === 'parent' || key === 'loc') continue;
		if (nennt(k[key], namen)) return true;
	}
	return false;
}

/** Bezeichner, die aus anlegeVorbelegung.ts importiert sind, plus Top-Level-
 *  Variablen, deren Initialisierung einen davon aufruft (z. B. der Lauf). */
function vorbelegungsNamen(ast: Knoten): Set<string> {
	const namen = new Set<string>();
	const body = (ast.instance?.content?.body as Knoten[]) ?? [];
	for (const stmt of body) {
		if (stmt.type === 'ImportDeclaration' && String(stmt.source.value).endsWith('anlegeVorbelegung.ts')) {
			for (const s of stmt.specifiers as Knoten[]) namen.add(s.local.name);
		}
	}
	for (const stmt of body) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type === 'Identifier' && d.init && nennt(d.init, namen)) namen.add(d.id.name);
		}
	}
	return namen;
}

function vorbelegungsEffekte(ast: Knoten, namen: Set<string>): number {
	let n = 0;
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'ExpressionStatement') continue;
		const c = stmt.expression as Knoten;
		if (c?.type !== 'CallExpression') continue;
		const callee = c.callee as Knoten;
		const istEffekt =
			(callee?.type === 'Identifier' && callee.name === '$effect') ||
			(callee?.type === 'MemberExpression' && callee.object?.type === 'Identifier' && callee.object.name === '$effect');
		if (istEffekt && nennt(c.arguments, namen)) n += 1;
	}
	return n;
}

const EDITOREN = [
	{ name: 'TripNewEditor', pfad: join(KOMPONENTEN, 'trip-new/TripNewEditor.svelte') },
	{ name: 'CompareNewEditor', pfad: join(KOMPONENTEN, 'compare-new/CompareNewEditor.svelte') },
];

describe('AC-45 Anlege-Editoren: Vorbelegung als ein Effekt statt versteckter Mounts', () => {
	for (const ed of EDITOREN) {
		test(`${ed.name}: keine CorridorEditor-/CorridorEditorMobile-Einbettung mehr`, () => {
			const { ast } = instanzAst(ed.pfad);
			const n = findeKomponenten(ast, 'CorridorEditor').length + findeKomponenten(ast, 'CorridorEditorMobile').length;
			assert.equal(n, 0, `${ed.name}: ${n} versteckte Corridor-Editor-Mounts`);
		});

		test(`${ed.name}: importiert die Vorbelegung aus shared/wetter-tab/anlegeVorbelegung.ts`, () => {
			const { ast } = instanzAst(ed.pfad);
			assert.ok(vorbelegungsNamen(ast).size > 0, `${ed.name}: kein Import aus anlegeVorbelegung.ts`);
		});

		test(`${ed.name}: genau EIN $effect fuehrt die Vorbelegung aus (Mobil/Desktop-Wechsel belegt nicht doppelt vor)`, () => {
			const { ast } = instanzAst(ed.pfad);
			const n = vorbelegungsEffekte(ast, vorbelegungsNamen(ast));
			assert.equal(n, 1, `${ed.name}: ${n} Vorbelegungs-Effekte (erwartet genau 1)`);
		});
	}
});

describe('AC-46 Mandantentrennung: kein "default"-Fallback als user_id', () => {
	const DEFAULT_FALLBACK = /user_?id[^\n;]*(\?\?|\|\|)\s*['"]default['"]/i;
	for (const pfad of [join(WETTER_TAB, 'anlegeVorbelegung.ts'), ...EDITOREN.map((e) => e.pfad)]) {
		test(`kein Fallback in ${relative(KOMPONENTEN, pfad)}`, () => {
			assert.ok(existsSync(pfad), `fehlt: ${relative(KOMPONENTEN, pfad)}`);
			assert.equal(DEFAULT_FALLBACK.test(readFileSync(pfad, 'utf-8')), false, 'Cross-User-Datenleck: user_id faellt auf "default" zurueck');
		});
	}
});
