// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 1.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-2 (Teil 1), AC-3, AC-4, AC-8, AC-19 (Importpfad).
//
// Soll (Teil 1):
//   - Die neun .svelte-Dateien des Wetter-Reiters liegen unter organisms/wetter-tab/.
//   - Die acht .ts-Logikmodule bleiben im Ordner shared/wetter-tab/; dort liegt keine .svelte mehr.
//   - Regel b des Bausteine-Wächters (ADR-0112) meldet für die neun Dateien 0 Verstöße — ohne
//     AUSNAHMEN-Eintrag, ohne BESTAND-Eintrag, ohne Marker audit:exempt.
//   - Die vier Importeure (TripTabs, CompareTabs, TripNewEditor, CompareNewEditor) importieren WetterTab
//     aus demselben Pfad organisms/wetter-tab/WetterTab.svelte (Trip und Vergleich teilen den Baustein).
//   - Kein Quell- oder Testtext unter frontend/src und frontend/e2e zeigt mehr auf eine .svelte-Datei im
//     alten Ordner.
//
// Messweise: Dateisystem + Wächter-Regelfunktion (zaehleTokenVerstoesse) + Svelte-AST der Importeure.
// Quellregeln sind hier Gegenstand der Prüfung (Wächter-Stil):
// doc-compliance-test
//
// RED heute: Die neun Dateien liegen noch unter shared/wetter-tab/ und enthalten rohe px-Werte.
//
// Teil 2 (Workflow feature-2913-teil2), Spec AC-17, AC-19, Klarstellung K-1 — überholt bewusst die Teil-1-Fassung
// „Importeure zeigen auf organisms/wetter-tab/WetterTab.svelte“:
//   - organisms/wetter-tab/WetterTab.svelte wird per git mv zu organisms/wetter-tab/WetterTabInhalt.svelte (einer
//     der neun Organismen; die AC-3/AC-4-Zusicherungen gelten für ihn unverändert weiter).
//   - Neue dünne Seite lib/components/shared/WetterTab.svelte bindet WetterTabInhalt ein; die vier Importeure
//     importieren WetterTab aus $lib/components/shared/WetterTab.svelte (Trip und Vergleich teilen weiter
//     denselben Pfad).
//   - AC-17: die Seite steht in SEITEN_SCOPE und die Regel-a-Prüfung des Wächters (pruefeSeitenDatei) meldet
//     0 Verstöße.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_ort.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { zaehleTokenVerstoesse, pruefeSeitenDatei, KONFIG } from '../../../__tests__/bausteine_waechter_regeln.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..'); // src/lib/components
const SRC = join(KOMP, '..', '..'); // src
const FRONTEND = join(SRC, '..');

const NEU = join(KOMP, 'organisms', 'wetter-tab');
const ALT = join(KOMP, 'shared', 'wetter-tab');

const SEITE = join(KOMP, 'shared', 'WetterTab.svelte');

// Teil 2 (K-1): WetterTab.svelte ist per git mv zu WetterTabInhalt.svelte geworden.
const NEUN = [
	'WetterTabInhalt',
	'VorlageKarte',
	'MetrikZeile',
	'GrenzenEditor',
	'WarnungenRadarKarte',
	'AmpelLeiste',
	'AlarmAbKopf',
	'NichtImBriefing',
	'AnpassenKarte'
];
const ACHT_TS = [
	'ampelModell',
	'ampelLeiste',
	'ampelSchreiben',
	'amtlicheWarnungen',
	'klon',
	'wetterTabLaden',
	'wetterTabSpeicherung',
	'wetterZustand'
];

const IMPORTEURE = {
	TripTabs: join(KOMP, 'trip-detail', 'TripTabs.svelte'),
	CompareTabs: join(KOMP, 'compare', 'CompareTabs.svelte'),
	TripNewEditor: join(KOMP, 'trip-new', 'TripNewEditor.svelte'),
	CompareNewEditor: join(KOMP, 'compare-new', 'CompareNewEditor.svelte')
};

const relSrc = (p: string) => relative(SRC, p).split('\\').join('/');

function importQuelle(datei: string, name: string): string | null {
	const ast = parse(readFileSync(datei, 'utf8'), { modern: true }) as unknown as Record<string, any>;
	for (const s of (ast.instance?.content?.body ?? []) as Array<Record<string, any>>) {
		if (s.type !== 'ImportDeclaration') continue;
		if ((s.specifiers as Array<Record<string, any>>).some((sp) => sp.local?.name === name)) return s.source.value as string;
	}
	return null;
}

function dateienUnter(wurzel: string, endungen: string[]): string[] {
	if (!existsSync(wurzel)) return [];
	const aus: string[] = [];
	for (const n of readdirSync(wurzel)) {
		if (n === 'node_modules' || n === '.svelte-kit' || n === 'fixtures') continue;
		const p = join(wurzel, n);
		if (statSync(p).isDirectory()) aus.push(...dateienUnter(p, endungen));
		else if (endungen.some((e) => n.endsWith(e))) aus.push(p);
	}
	return aus;
}

describe('AC-3: neun Organismen unter organisms/wetter-tab/, Logik bleibt in shared/wetter-tab/', () => {
	for (const n of NEUN) {
		test(`${n}.svelte liegt unter organisms/wetter-tab/`, () => {
			assert.ok(existsSync(join(NEU, `${n}.svelte`)), `TDD RED: organisms/wetter-tab/${n}.svelte fehlt`);
		});
	}
	test('unter shared/wetter-tab/ liegt keine .svelte-Datei mehr', () => {
		const rest = readdirSync(ALT).filter((n) => n.endsWith('.svelte'));
		assert.deepEqual(rest, [], `noch im alten Ordner: ${rest.join(', ')}`);
	});
	test('die acht .ts-Module liegen weiterhin unter shared/wetter-tab/', () => {
		const fehlt = ACHT_TS.filter((n) => !existsSync(join(ALT, `${n}.ts`)));
		assert.deepEqual(fehlt, [], `Logikmodule fehlen am alten Ort: ${fehlt.join(', ')}`);
	});
	test('unter organisms/wetter-tab/ liegt kein .ts-Logikmodul (keine Verschiebung der Logik)', () => {
		const ts = existsSync(NEU) ? readdirSync(NEU).filter((n) => ACHT_TS.some((t) => n === `${t}.ts`)) : [];
		assert.deepEqual(ts, []);
	});
});

describe('AC-4/AC-2: Regel b meldet 0 Verstöße, ohne Abkürzung über AUSNAHMEN, BESTAND oder audit:exempt', () => {
	for (const n of NEUN) {
		test(`${n}.svelte: Regel b ohne Verstoß`, () => {
			const datei = join(NEU, `${n}.svelte`);
			assert.ok(existsSync(datei), `TDD RED: organisms/wetter-tab/${n}.svelte fehlt`);
			const rel = relSrc(datei);
			const v = zaehleTokenVerstoesse(rel, readFileSync(datei, 'utf8'));
			assert.deepEqual(
				v.map((x) => x.meldung),
				[],
				`${v.length} Verstöße gegen Regel b`
			);
		});
		test(`${n}.svelte: kein AUSNAHMEN-/BESTAND-Eintrag und kein audit:exempt`, () => {
			const datei = join(NEU, `${n}.svelte`);
			assert.ok(existsSync(datei), `TDD RED: organisms/wetter-tab/${n}.svelte fehlt`);
			const rel = relSrc(datei);
			assert.equal(rel in KONFIG.AUSNAHMEN, false, `${rel} steht in AUSNAHMEN`);
			assert.equal(KONFIG.BESTAND.includes(rel), false, `${rel} steht in BESTAND`);
			assert.doesNotMatch(readFileSync(datei, 'utf8'), /audit:exempt/, `${rel} trägt audit:exempt`);
		});
	}
	test('kein Eintrag für den Wetter-Reiter in AUSNAHMEN oder BESTAND (alter oder neuer Ort)', () => {
		const treffer = [...Object.keys(KONFIG.AUSNAHMEN), ...KONFIG.BESTAND].filter((d) => /wetter-tab\//.test(d));
		assert.deepEqual(treffer, []);
	});
});

describe('AC-8/AC-19 (Teil 2, K-1): Importeure zeigen auf die Seite shared/WetterTab.svelte, Trip und Vergleich teilen denselben Pfad', () => {
	const ziel = (datei: string, q: string) => (q.startsWith('.') ? relSrc(join(dirname(datei), q)) : q.replace(/^\$lib\//, 'lib/'));
	for (const [name, datei] of Object.entries(IMPORTEURE)) {
		test(`${name} importiert WetterTab aus $lib/components/shared/WetterTab.svelte`, () => {
			const q = importQuelle(datei, 'WetterTab');
			assert.ok(q, `${name}: kein Import von WetterTab`);
			assert.equal(ziel(datei, q!), 'lib/components/shared/WetterTab.svelte', `TDD RED: ${name}: Import zeigt auf ${q}`);
		});
	}
	test('alle vier Importeure lösen auf DIESELBE Datei auf', () => {
		const ziele = new Set(
			Object.values(IMPORTEURE).map((datei) => {
				const q = importQuelle(datei, 'WetterTab');
				assert.ok(q);
				return ziel(datei, q!);
			})
		);
		assert.deepEqual([...ziele], ['lib/components/shared/WetterTab.svelte']);
	});
	test('organisms/wetter-tab/WetterTab.svelte existiert nicht mehr (git mv zu WetterTabInhalt.svelte)', () => {
		assert.equal(existsSync(join(NEU, 'WetterTab.svelte')), false, 'TDD RED: organisms/wetter-tab/WetterTab.svelte liegt noch dort');
	});
	test('die Seite shared/WetterTab.svelte existiert und bindet organisms/wetter-tab/WetterTabInhalt.svelte ein', () => {
		assert.ok(existsSync(SEITE), 'TDD RED: lib/components/shared/WetterTab.svelte fehlt');
		const q = importQuelle(SEITE, 'WetterTabInhalt');
		assert.ok(q, 'Seite importiert WetterTabInhalt nicht');
		assert.equal(ziel(SEITE, q!), 'lib/components/organisms/wetter-tab/WetterTabInhalt.svelte');
		const markup = parse(readFileSync(SEITE, 'utf8'), { modern: true }) as unknown as Record<string, any>;
		const nutzt = JSON.stringify(markup.fragment, (k, v) => (k === 'parent' ? undefined : v)).includes('"name":"WetterTabInhalt"');
		assert.ok(nutzt, 'Seite rendert <WetterTabInhalt> nicht');
	});
	test('kein Quell- oder Testtext verweist noch auf eine .svelte-Datei im alten Ordner', () => {
		const alt = /shared\/wetter-tab\/[A-Za-z]+\.svelte/;
		const dateien = [
			...dateienUnter(SRC, ['.ts', '.svelte', '.js', '.mjs']),
			...dateienUnter(join(FRONTEND, 'e2e'), ['.ts', '.js', '.mjs'])
		];
		const treffer = dateien
			.filter((d) => d !== fileURLToPath(import.meta.url))
			.filter((d) => alt.test(readFileSync(d, 'utf8')))
			.map((d) => relative(FRONTEND, d));
		assert.deepEqual(treffer, [], `alte Pfade in: ${treffer.join(', ')}`);
	});
});

describe('AC-17 (Teil 2, K-1): die Seite shared/WetterTab.svelte steht in SEITEN_SCOPE, Regel a ohne Verstoß', () => {
	const REL = 'lib/components/shared/WetterTab.svelte';
	test('SEITEN_SCOPE enthält lib/components/shared/WetterTab.svelte', () => {
		assert.ok(KONFIG.SEITEN_SCOPE.includes(REL), `TDD RED: ${REL} fehlt in SEITEN_SCOPE`);
	});
	test('Regel a (pruefeSeitenDatei) meldet 0 Verstöße für die Seite', () => {
		assert.ok(existsSync(SEITE), `TDD RED: ${REL} fehlt`);
		const v = pruefeSeitenDatei(REL, readFileSync(SEITE, 'utf8'), KONFIG.FREIGEGEBENE_KOMPOSITIONEN);
		assert.deepEqual(v.map((x) => x.meldung), []);
	});
	test('die Seite steht nicht in BESTAND oder AUSNAHMEN und trägt kein audit:exempt', () => {
		assert.equal(KONFIG.BESTAND.includes(REL), false);
		assert.equal(REL in KONFIG.AUSNAHMEN, false);
		if (existsSync(SEITE)) assert.doesNotMatch(readFileSync(SEITE, 'utf8'), /audit:exempt/);
	});
});
