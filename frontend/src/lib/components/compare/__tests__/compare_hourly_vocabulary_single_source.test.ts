// RATSCHE (Frontend-Haelfte) — Issue #1406 Scheibe B, AC-10.
// Pruefdatum: 2026-10-30 (Regel-Budget, CLAUDE.md).
// Spec: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md
//
// Die Python-Haelfte derselben Ratsche liegt in
// tests/unit/test_compare_hourly_vocabulary_single_source.py und haelt fest,
// dass es im Server-Baum genau EINE Alias-Tabelle gibt. Diese Datei haelt
// fest, dass der Frontend-Baum KEINE zweite hat — zusammen: genau eine Quelle
// repo-weit.
//
// Geprueft werden zwei Dinge:
//   1. Kein Objekt-Literal im Produktivteil des Frontends bildet einen
//      historischen Stundenverlaufs-Kurzschluessel auf eine Wettergroesse ab.
//   2. Die drei Bezeichner des alten Compare-eigenen Vokabulars
//      (ALL_HOURLY_METRICS, HOURLY_KEY_TO_CATALOG_ID, resolveHourlyMetricLabel)
//      werden nirgends mehr deklariert oder importiert.
//
// Bauart gegen die bekannten Faulheitsfallen:
//   * Syntaxbaum statt Textsuche: .ts ueber den echten TypeScript-Parser,
//     .svelte ueber den echten Svelte-Compiler (Skript-Block) + TypeScript.
//     Ein Kommentar wie "temp_c -> temperature" kann keinen Treffer erzeugen.
//   * Kein Nichtstun-Gruen: der Sucher wird an absichtlich gestellten Funden
//     geprueft (Scharfschaltungs-Tests); die Zahl geparster Dateien wird
//     ausgesprochen behauptet und muss > 0 sein.
//   * Keine handgepflegte Groessen-Liste: die Alias-Tabelle wird aus der
//     KANONISCHEN Quelle (compare_hourly_metric_ids.py) gelesen, nicht
//     abgeschrieben; die Extraktion behauptet ihre eigene Trefferzahl.
//
// Adversary-Befund F002 (2026-08-01): Die erste Fassung wertete PRO
// OBJEKT-LITERAL und verlangte zwei Paare darin. Damit blieb das VOLLSTAENDIGE
// Vokabular unentdeckt, sobald man es auf lauter Ein-Paar-Literale verteilte —
// also genau der fuenfte Vokabular-Ort, gegen den AC-10 antritt. Seitdem gilt:
// JEDE Alias-Fundstelle ist ein Fund, egal wie klein ihr Literal ist. Damit die
// legitimen Nachbarn (Alarm-Vokabular, teils gleiche Schluesselnamen) nicht
// fehlschlagen, tragen sie einen begruendeten Eintrag im Register
// BEKANNTE_KOLLISIONEN — sichtbar und einzeln, statt statistisch verdeckt.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hourly_vocabulary_single_source.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
// frontend/src/lib/components/compare/__tests__ -> Repo-Wurzel (Pfadregel #1409:
// relativ zur eigenen Testdatei, nie ueber einen festen Hauptrepo-Pfad).
const REPO = join(here, '..', '..', '..', '..', '..', '..');
const FRONTEND_SRC = join(REPO, 'frontend', 'src');
const KANONISCHE_QUELLE = join(
	REPO, 'src', 'output', 'renderers', 'compare_hourly_metric_ids.py'
);

const ABGESCHAFFTE_BEZEICHNER = [
	'ALL_HOURLY_METRICS',
	'HOURLY_KEY_TO_CATALOG_ID',
	'resolveHourlyMetricLabel'
];

/** Die historische Alias-Tabelle (Kurzschluessel -> Register-ID), gelesen aus
 *  der kanonischen Quelle. Bewusst KEINE Abschrift: waechst oder schrumpft sie
 *  dort, zieht dieser Waechter automatisch mit. Die Extraktion behauptet ihre
 *  eigene Trefferzahl — findet sie nichts, faellt der Test durch. */
function aliasTabelleAusKanonischerQuelle(): [string, string][] {
	const src = readFileSync(KANONISCHE_QUELLE, 'utf-8');
	const start = src.indexOf('FRONTEND_TO_HOURLY_METRIC_ID');
	assert.ok(start >= 0, `FRONTEND_TO_HOURLY_METRIC_ID nicht in ${KANONISCHE_QUELLE}`);
	const open = src.indexOf('{', start);
	const close = src.indexOf('\n}', open);
	assert.ok(open >= 0 && close > open, 'Alias-Tabellen-Literal nicht abgrenzbar.');
	const block = src.slice(open, close);
	const paare = [...block.matchAll(/^\s*"([a-z0-9_]+)"\s*:\s*"([a-z0-9_]+)"/gm)].map(
		(m) => [m[1], m[2]] as [string, string]
	);
	assert.ok(
		paare.length >= 5,
		`Nur ${paare.length} Kurzschluessel aus der kanonischen Quelle gelesen — ` +
			'die Suche haette kaum Angriffsflaeche, der Waechter waere stumpf.'
	);
	return paare;
}

function kurzschluesselAusKanonischerQuelle(): string[] {
	return aliasTabelleAusKanonischerQuelle().map(([key]) => key);
}

function dateienSammeln(wurzel: string): string[] {
	const out: string[] = [];
	function ab(pfad: string): void {
		for (const eintrag of readdirSync(pfad)) {
			const voll = join(pfad, eintrag);
			if (statSync(voll).isDirectory()) {
				if (eintrag === 'node_modules' || eintrag === '__tests__') continue;
				ab(voll);
				continue;
			}
			if (eintrag.endsWith('.test.ts') || eintrag.endsWith('.spec.ts')) continue;
			if (eintrag.endsWith('.ts') || eintrag.endsWith('.svelte')) out.push(voll);
		}
	}
	ab(wurzel);
	return out;
}

/** Skript-Quelltext einer Datei — bei .svelte ueber den echten Svelte-Compiler
 *  (Instance- und Module-Block), sonst die Datei selbst. */
function skriptQuelltext(pfad: string): string {
	const src = readFileSync(pfad, 'utf-8');
	if (!pfad.endsWith('.svelte')) return src;
	const ast = parse(src, { modern: true }) as any;
	const teile: string[] = [];
	for (const block of [ast.instance, ast.module]) {
		const inhalt = block?.content;
		if (inhalt && typeof inhalt.start === 'number' && typeof inhalt.end === 'number') {
			teile.push(src.slice(inhalt.start, inhalt.end));
		}
	}
	return teile.join('\n;\n');
}

function tsBaum(quelltext: string, name: string): ts.SourceFile {
	return ts.createSourceFile(name, quelltext, ts.ScriptTarget.Latest, true);
}

// Zielwert-Form: ein Bezeichner in Kleinschreibung mit Unterstrichen, wie ihn
// das Register vergibt (`wind_chill`, `rain_probability`). Anzeigewerte
// („14°C", „4", „teilw. bew.") fallen damit raus, ohne dass der Waechter eine
// Kopie des Registers braeuchte.
const ZIELWERT_FORM = /^[a-z][a-z0-9_]*$/;

/** Eine Fundstelle: Kurzschluessel -> Register-artige Zeichenkette. */
type Fund = { datei: string; zeile: number; schluessel: string; wert: string };

const alsText = (f: Fund): string =>
	`${f.datei}:${f.zeile} ${f.schluessel} -> ${f.wert}`;

// REGISTER der bekannten, begruendeten Einzel-Kollisionen. Nur diese
// (Datei, Kurzschluessel)-Paare duerfen im Produktivteil stehen, ohne als
// zweiter Vokabular-Ort zu gelten. Bewusst als sichtbares Register statt als
// Haeufigkeits-Schwelle: eine Schwelle laesst sich unterlaufen, indem man das
// Vokabular auf viele kleine Literale verteilt (Adversary-Befund F002) — ein
// Register nicht, denn jede neue Fundstelle verlangt eine Zeile mit Begruendung
// und faellt damit im Review auf.
const BEKANNTE_KOLLISIONEN: { datei: string; schluessel: string; grund: string }[] = [
	{
		datei: 'frontend/src/lib/utils/alertMetricCatalogIds.ts',
		schluessel: 'thunder_level',
		grund:
			'Alarm-Crosswalk (#1401 B): AlertMetric -> Register-ID. Eigenes Vokabular ' +
			'der Alarme, das zufaellig denselben Schluesselnamen traegt.'
	},
	{
		datei: 'frontend/src/lib/components/molecules/AlertRow.svelte',
		schluessel: 'thunder_level',
		grund:
			'Ton- und Icon-Zuordnung der Alarmzeile (TONE_MAP/KIND_MAP) — bildet ' +
			'Alarm-Arten auf Darstellung ab, nicht Stundenverlaufs-Schluessel auf Groessen.'
	}
];

const istBekannt = (f: Fund): boolean =>
	BEKANNTE_KOLLISIONEN.some((k) => k.datei === f.datei && k.schluessel === f.schluessel);

/** ALLE Alias-Fundstellen einer Datei — jedes einzelne Paar zaehlt, unabhaengig
 *  davon, wie viele Paare in seinem Objekt-Literal stehen. Genau hier lag
 *  Befund F002: eine Mindestpaar-Schwelle je Literal laesst sich umgehen, indem
 *  man das Vokabular auf lauter Ein-Paar-Literale verteilt.
 *  Identische Paare (`uv_index: 'uv_index'`) zaehlen nicht — sie tragen keine
 *  Uebersetzung. Anzeigewerte ("14°C", "teilw. bew.") fallen ueber
 *  ZIELWERT_FORM heraus. */
/** Der Zeichenketten-Wert eines Ausdrucks, sofern er WOERTLICH dasteht —
 *  `'temperature'` ebenso wie `` `temperature` ``. Alles, was erst zur Laufzeit
 *  eine Zeichenkette wird (Variable, Aufruf, Verkettung), zaehlt nicht. */
function zeichenkette(knoten: ts.Node): string | null {
	if (ts.isStringLiteral(knoten)) return knoten.text;
	if (ts.isNoSubstitutionTemplateLiteral(knoten)) return knoten.text;
	return null;
}

/** Der Schluesselname einer Objekt-Eigenschaft in ALLEN drei Schreibweisen:
 *  `temp_c:`, `'temp_c':` und — Adversary-Befund F004 — die BERECHNETE Form
 *  `["temp_c"]:`. Letztere ist syntaktisch ein `ComputedPropertyName` und ging
 *  an den Pruefungen auf Identifier/StringLiteral vorbei; das vollstaendige
 *  Vokabular blieb so unentdeckt, obwohl es ein ganz gewoehnliches
 *  Objekt-Literal ist. Berechnete Schluessel, deren Ausdruck erst zur Laufzeit
 *  eine Zeichenkette ergibt (`[KONST]:`), bleiben eine dokumentierte Grenze. */
function schluesselName(name: ts.PropertyName): string | null {
	if (ts.isIdentifier(name)) return name.text;
	if (ts.isStringLiteral(name)) return name.text;
	if (ts.isComputedPropertyName(name)) return zeichenkette(name.expression);
	return null;
}

function aliasFunde(quelltext: string, name: string, schluessel: Set<string>): Fund[] {
	const treffer: Fund[] = [];
	const quelle = tsBaum(quelltext, name);
	function ab(knoten: ts.Node): void {
		if (ts.isObjectLiteralExpression(knoten)) {
			for (const eigenschaft of knoten.properties) {
				if (!ts.isPropertyAssignment(eigenschaft)) continue;
				const key = schluesselName(eigenschaft.name);
				const wert = zeichenkette(eigenschaft.initializer);
				if (!key || !wert) continue;
				if (!schluessel.has(key) || key === wert) continue;
				if (!ZIELWERT_FORM.test(wert)) continue;
				const { line } = quelle.getLineAndCharacterOfPosition(
					eigenschaft.getStart(quelle)
				);
				treffer.push({ datei: name, zeile: line + 1, schluessel: key, wert });
			}
		}
		ts.forEachChild(knoten, ab);
	}
	ab(quelle);
	return treffer;
}

/** Rueckwaerts-vertraegliche Kurzform fuer die Scharfschaltungs-Tests. */
function aliasPaare(quelltext: string, name: string, schluessel: Set<string>): string[] {
	return aliasFunde(quelltext, name, schluessel).map(alsText);
}

/** Vorkommen der abgeschafften Bezeichner als Deklaration oder Import. */
function abgeschaffteVorkommen(quelltext: string, name: string): string[] {
	const treffer: string[] = [];
	const quelle = tsBaum(quelltext, name);
	function melde(knoten: ts.Node, bezeichner: string, art: string): void {
		const { line } = quelle.getLineAndCharacterOfPosition(knoten.getStart(quelle));
		treffer.push(`${name}:${line + 1} ${art} ${bezeichner}`);
	}
	function ab(knoten: ts.Node): void {
		if (ts.isVariableDeclaration(knoten) && ts.isIdentifier(knoten.name)) {
			if (ABGESCHAFFTE_BEZEICHNER.includes(knoten.name.text)) {
				melde(knoten, knoten.name.text, 'deklariert');
			}
		}
		if (ts.isFunctionDeclaration(knoten) && knoten.name) {
			if (ABGESCHAFFTE_BEZEICHNER.includes(knoten.name.text)) {
				melde(knoten, knoten.name.text, 'deklariert');
			}
		}
		if (ts.isImportSpecifier(knoten)) {
			const importiert = (knoten.propertyName ?? knoten.name).text;
			if (ABGESCHAFFTE_BEZEICHNER.includes(importiert)) {
				melde(knoten, importiert, 'importiert');
			}
		}
		ts.forEachChild(knoten, ab);
	}
	ab(quelle);
	return treffer;
}

describe('AC-10 (Frontend): keine zweite Zuordnung Stundenverlauf-Schluessel -> Wettergroesse', () => {
	test('Scharfschaltung: der Sucher erkennt eine absichtlich gestellte Alias-Tabelle', () => {
		const schluessel = kurzschluesselAusKanonischerQuelle();
		const gestellt =
			`export const ALIAS = { ${schluessel[0]}: 'temperature', ` +
			`${schluessel[1]}: 'humidity' };`;

		const treffer = aliasPaare(gestellt, 'gestellt.ts', new Set(schluessel));

		assert.equal(
			treffer.length,
			2,
			`Der Sucher erkennt eine offensichtliche Alias-Tabelle nicht: ${JSON.stringify(treffer)}`
		);
	});

	test('Scharfschaltung: das VERTEILTE Vokabular (je ein Paar pro Literal) wird gefangen', () => {
		// Adversary-Befund F002: genau dieser Fall blieb unter der alten
		// Mindestpaar-Schwelle gruen — das vollstaendige Vokabular, aufgeteilt
		// auf lauter Ein-Paar-Objekte. Er MUSS rot sein, sonst ist die Ratsche
		// mit drei Zeilen Umschreiben zu umgehen.
		const tabelle = aliasTabelleAusKanonischerQuelle().filter(([k, v]) => k !== v);
		assert.ok(
			tabelle.length >= 5,
			`Nur ${tabelle.length} uebersetzende Paare — der gestellte Angriff waere zu klein.`
		);

		const gestellt = tabelle
			.map(([key, wert], i) => `export const ALIAS_${i} = { ${key}: '${wert}' };`)
			.join('\n');

		const treffer = aliasPaare(
			gestellt,
			'verteilt.ts',
			new Set(tabelle.map(([key]) => key))
		);

		assert.equal(
			treffer.length,
			tabelle.length,
			`Das auf ${tabelle.length} Ein-Paar-Literale verteilte Vokabular wurde nur ` +
				`${treffer.length}-mal gefunden — die Ratsche ist wieder umgehbar:\n` +
				treffer.join('\n')
		);
	});

	test('Scharfschaltung: die BERECHNETE Schreibweise ["temp_c"] wird gefangen', () => {
		// Adversary-Befund F004: `{ ["temp_c"]: "temperature" }` ist ein ganz
		// gewoehnliches Objekt-Literal, sein Schluessel aber ein
		// ComputedPropertyName — die Pruefung auf Identifier/StringLiteral ging
		// daran vorbei, das volle Vokabular blieb 6/6 gruen. Der harmloseste
		// Umgehungsweg von allen, weil man ihn auch versehentlich trifft.
		const tabelle = aliasTabelleAusKanonischerQuelle().filter(([k, v]) => k !== v);
		const gestellt =
			'export const ALIAS = {\n' +
			tabelle.map(([key, wert]) => `\t["${key}"]: "${wert}",`).join('\n') +
			'\n};';

		const treffer = aliasPaare(
			gestellt,
			'berechnet.ts',
			new Set(tabelle.map(([key]) => key))
		);

		assert.equal(
			treffer.length,
			tabelle.length,
			`Das Vokabular in berechneter Schreibweise wurde nur ${treffer.length} von ` +
				`${tabelle.length} Paaren gefunden — die Ratsche ist an eckigen Klammern ` +
				`vorbei umgehbar:\n${treffer.join('\n')}`
		);
	});

	test('Scharfschaltung: ein Kommentar mit derselben Zuordnung erzeugt KEINEN Treffer', () => {
		const schluessel = kurzschluesselAusKanonischerQuelle();
		const nurKommentar = `// ${schluessel[0]}: 'temperature' — nur Prosa\nexport const X = 1;`;

		assert.deepEqual(aliasPaare(nurKommentar, 'prosa.ts', new Set(schluessel)), []);
	});

	test('im Produktivteil des Frontends gibt es keine solche Zuordnung', () => {
		const schluessel = new Set(kurzschluesselAusKanonischerQuelle());
		const dateien = dateienSammeln(FRONTEND_SRC);
		assert.ok(
			dateien.length > 0,
			`Keine Quelldatei unter ${FRONTEND_SRC} eingesammelt — die Ratsche laeuft ins Leere.`
		);

		const funde: Fund[] = [];
		for (const pfad of dateien) {
			const name = relative(REPO, pfad);
			funde.push(...aliasFunde(skriptQuelltext(pfad), name, schluessel));
		}

		const unangemeldet = funde.filter((f) => !istBekannt(f)).map(alsText);
		assert.deepEqual(
			unangemeldet,
			[],
			`${dateien.length} Frontend-Dateien geprueft, ${unangemeldet.length} nicht ` +
				'angemeldete Zuordnungs-Fundstellen gefunden — erwartet 0 (die einzige ' +
				'erlaubte Quelle ist src/output/renderers/compare_hourly_metric_ids.py).\n' +
				'JEDES Paar zaehlt, auch allein stehend: das Vokabular auf viele kleine ' +
				'Literale zu verteilen ist kein Ausweg (Adversary-Befund F002). Ist eine ' +
				'Fundstelle wirklich ein fremdes Vokabular, gehoert sie mit Begruendung ' +
				'in BEKANNTE_KOLLISIONEN — sichtbar, nicht stillschweigend:\n' +
				unangemeldet.join('\n')
		);
	});

	test('das Register der bekannten Kollisionen traegt keine Karteileichen', () => {
		// Ein Register, dessen Eintraege nichts mehr abdecken, weicht die Ratsche
		// unbemerkt auf: es wuerde eine spaeter neu gepflanzte Zuordnung an
		// derselben Stelle decken. Deshalb muss jeder Eintrag heute greifen.
		const schluessel = new Set(kurzschluesselAusKanonischerQuelle());
		const funde: Fund[] = [];
		for (const pfad of dateienSammeln(FRONTEND_SRC)) {
			funde.push(...aliasFunde(skriptQuelltext(pfad), relative(REPO, pfad), schluessel));
		}

		const tot = BEKANNTE_KOLLISIONEN.filter(
			(k) => !funde.some((f) => f.datei === k.datei && f.schluessel === k.schluessel)
		).map((k) => `${k.datei} (${k.schluessel})`);

		assert.deepEqual(
			tot,
			[],
			'Register-Eintraege ohne Fundstelle — bitte entfernen, sonst decken sie ' +
				'kuenftig eine neue Zuordnung an derselben Stelle:\n' + tot.join('\n')
		);
		assert.ok(
			BEKANNTE_KOLLISIONEN.every((k) => k.grund.trim().length >= 30),
			'Jeder Register-Eintrag braucht eine ausgeschriebene Begruendung.'
		);
	});

	test('die Bezeichner des alten Compare-eigenen Vokabulars existieren nicht mehr', () => {
		const dateien = dateienSammeln(FRONTEND_SRC);
		assert.ok(dateien.length > 0, 'Keine Quelldatei eingesammelt.');

		const treffer: string[] = [];
		for (const pfad of dateien) {
			const name = relative(REPO, pfad);
			treffer.push(...abgeschaffteVorkommen(skriptQuelltext(pfad), name));
		}

		assert.deepEqual(
			treffer,
			[],
			`${dateien.length} Frontend-Dateien geprueft; die abgeschafften Bezeichner ` +
				`(${ABGESCHAFFTE_BEZEICHNER.join(', ')}) leben noch:\n` +
				treffer.join('\n')
		);
	});
});
