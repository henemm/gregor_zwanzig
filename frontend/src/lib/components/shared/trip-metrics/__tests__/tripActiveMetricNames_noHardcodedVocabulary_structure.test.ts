// TDD RED — Feature #1435 Etappe E3a, AC-8: Ratsche gegen ein neues,
// redaktionell gepflegtes Metrik-Namensvokabular in `tripActiveMetricNames.ts`.
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md
// Implementation Details Punkt 5, AC-8.
//
// Syntaxbaum-Prüfung (TypeScript Compiler API, kein rohes String-Grep) —
// Vorbild: shared/__tests__/alarme_tab_shared_labels.test.ts (Zeilen 44-72),
// hier auf ein reines .ts-Modul statt .svelte übertragen.
//
// RED heute: `tripActiveMetricNames.ts` existiert noch nicht -> readFileSync
// wirft ENOENT, NICHT wegen fehlendem Loader.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNames_noHardcodedVocabulary_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const MODULE_PATH = join(here, '..', 'tripActiveMetricNames.ts');

// Pfadregel #1409: relativ zur Testdatei aufgelöst, NIE ein fester
// Hauptrepo-Pfad — sonst prüft ein Worktree-Lauf das unveränderte
// Hauptrepo-Register statt seiner eigenen Kopie.
const CATALOG_PATH = join(
	here,
	'..',
	'..',
	'..',
	'..',
	'..',
	'..',
	'..',
	'src',
	'app',
	'metric_catalog.py'
);

const MIN_KNOWN_ID_HITS = 3;
const MIN_CATALOG_IDS = 20;

function parseModule(): ts.SourceFile {
	const src = readFileSync(MODULE_PATH, 'utf-8');
	return ts.createSourceFile(MODULE_PATH, src, ts.ScriptTarget.Latest, true);
}

function parseFile(path: string): ts.SourceFile {
	const src = readFileSync(path, 'utf-8');
	return ts.createSourceFile(path, src, ts.ScriptTarget.Latest, true);
}

/**
 * Fix-Loop 2, F004: statt einer handgepflegten Kennungs-Liste IM Wächter
 * (der genau der Widerspruch wäre, den #1435 abstellen will) leitet der
 * Wächter seine Kennungs-Menge aus dem Register selbst ab — den `id="…"`-
 * Werten in `src/app/metric_catalog.py` (einzige Definitionsform dort:
 * Keyword-Argument `id="…"` in `MetricDefinition(...)`-Aufrufen, verifiziert
 * 2026-08-01, 26 Kennungen). `\bid="…"` grenzt bewusst gegen `trip_id="…"`/
 * `location_id="…"` ab (kein Wortgrenzen-Treffer vor "id" bei "_id").
 *
 * Schlägt die Ableitung fehl (Register nicht auffindbar) oder findet sie
 * weniger als `MIN_CATALOG_IDS` Kennungen, bricht die Funktion MIT Meldung
 * ab — die Ratsche darf nie stillschweigend mit einer Rumpfliste weiterlaufen.
 */
function deriveKnownMetricIds(): Set<string> {
	let src: string;
	try {
		src = readFileSync(CATALOG_PATH, 'utf-8');
	} catch (err) {
		throw new Error(
			`AC-8 (Fix-Loop 2, F004): Metrik-Register nicht lesbar unter ${CATALOG_PATH} ` +
				`(${(err as Error).message}). Die Ratsche kann ohne das Register keine Metrik-` +
				'Kennungen ableiten und bricht deshalb ab, statt leer durchzulaufen.'
		);
	}
	const ids = new Set<string>();
	const idPattern = /\bid="([a-zA-Z_][a-zA-Z0-9_]*)"/g;
	let match: RegExpExecArray | null;
	while ((match = idPattern.exec(src)) !== null) {
		ids.add(match[1]);
	}
	if (ids.size < MIN_CATALOG_IDS) {
		throw new Error(
			`AC-8 (Fix-Loop 2, F004): aus dem Metrik-Register (${CATALOG_PATH}) wurden nur ` +
				`${ids.size} Kennungen abgeleitet (erwartet mindestens ${MIN_CATALOG_IDS}). Das deutet ` +
				'auf eine kaputte Ableitung hin (z.B. geänderte Definitionsform), nicht auf ein leeres ' +
				'Register — die Ratsche bricht deshalb ab, statt mit einer Rumpfliste weiterzulaufen.'
		);
	}
	return ids;
}

let cachedKnownIds: Set<string> | undefined;
function knownMetricIds(): Set<string> {
	if (!cachedKnownIds) cachedKnownIds = deriveKnownMetricIds();
	return cachedKnownIds;
}

function findRecordStringStringConst(sf: ts.SourceFile): string | undefined {
	let offender: string | undefined;
	function visit(node: ts.Node): void {
		if (ts.isVariableStatement(node)) {
			for (const decl of node.declarationList.declarations) {
				const typeText = decl.type ? decl.type.getText(sf) : '';
				if (/Record\s*<\s*string\s*,\s*string\s*>/.test(typeText)) {
					offender = decl.name.getText(sf);
				}
			}
		}
		ts.forEachChild(node, visit);
	}
	ts.forEachChild(sf, visit);
	return offender;
}

function findStringArrayWithKnownIds(sf: ts.SourceFile, knownIds: Set<string>): string | undefined {
	let offender: string | undefined;
	function visit(node: ts.Node): void {
		if (ts.isVariableStatement(node)) {
			for (const decl of node.declarationList.declarations) {
				if (decl.initializer && ts.isArrayLiteralExpression(decl.initializer)) {
					const stringLiterals = decl.initializer.elements.filter(
						(el): el is ts.StringLiteral => ts.isStringLiteral(el)
					);
					const hits = stringLiterals.filter((el) => knownIds.has(el.text));
					if (hits.length >= MIN_KNOWN_ID_HITS) offender = decl.name.getText(sf);
				}
			}
		}
		ts.forEachChild(node, visit);
	}
	ts.forEachChild(sf, visit);
	return offender;
}

/** Ein Array-Literal, dessen Elemente selbst zweielementige Array-Literale
 *  aus String-Literalen sind — das Tupel-Muster, das `new Map([...])`,
 *  `Object.fromEntries([...])` und ein freistehendes Tupel-Array alle
 *  gemeinsam haben (dieselbe AST-Form, unabhängig vom Aufrufkontext). */
function isTupleArrayLiteral(node: ts.Node): node is ts.ArrayLiteralExpression {
	if (!ts.isArrayLiteralExpression(node) || node.elements.length === 0) return false;
	return node.elements.every(
		(el) =>
			ts.isArrayLiteralExpression(el) &&
			el.elements.length === 2 &&
			ts.isStringLiteral(el.elements[0])
	);
}

function knownIdHitsInTupleArray(node: ts.ArrayLiteralExpression, knownIds: Set<string>): number {
	return node.elements.filter((el) => {
		if (!ts.isArrayLiteralExpression(el)) return false;
		const key = el.elements[0];
		return ts.isStringLiteral(key) && knownIds.has(key.text);
	}).length;
}

function findTupleArrayOffenderHits(sf: ts.SourceFile, knownIds: Set<string>): number {
	let offenderHits = 0;
	function visit(node: ts.Node): void {
		if (isTupleArrayLiteral(node)) {
			const hits = knownIdHitsInTupleArray(node, knownIds);
			if (hits >= MIN_KNOWN_ID_HITS) offenderHits = Math.max(offenderHits, hits);
		}
		ts.forEachChild(node, visit);
	}
	ts.forEachChild(sf, visit);
	return offenderHits;
}

function knownIdHitsInObjectLiteral(node: ts.ObjectLiteralExpression, knownIds: Set<string>): number {
	let hits = 0;
	for (const prop of node.properties) {
		if (!ts.isPropertyAssignment(prop)) continue;
		const name = prop.name;
		const key = ts.isIdentifier(name)
			? name.text
			: ts.isStringLiteral(name)
				? name.text
				: undefined;
		if (key && knownIds.has(key)) hits++;
	}
	return hits;
}

function findObjectLiteralOffenderHits(sf: ts.SourceFile, knownIds: Set<string>): number {
	let offenderHits = 0;
	function visit(node: ts.Node): void {
		if (ts.isObjectLiteralExpression(node)) {
			const hits = knownIdHitsInObjectLiteral(node, knownIds);
			if (hits >= MIN_KNOWN_ID_HITS) offenderHits = Math.max(offenderHits, hits);
		}
		ts.forEachChild(node, visit);
	}
	ts.forEachChild(sf, visit);
	return offenderHits;
}

/**
 * Fix-Loop 3, F005: `findRecordStringStringConst` erkennt jede
 * `Record<string,string>`-Konstante allein am TYP — für das Hauptmodul
 * selbst bewusst so belassen (dort hat so eine Konstante keinen legitimen
 * Zweck). Für Nachbardateien ist das ein Falsch-Alarm: eine fachfremde
 * `Record<string,string>`-Konstante (z.B. Wochentags-Labels) wird ebenso
 * gemeldet wie eine ausgelagerte Metrik-Namenstabelle. Diese Variante bindet
 * den Fund deshalb an dieselbe Kennungs-Menge/Schwelle wie die anderen drei
 * Nachbardatei-Prüfungen: nur wenn der Objekt-Initialisierer mindestens
 * `MIN_KNOWN_ID_HITS` bekannte Register-Kennungen als Schlüssel trägt.
 */
function findRecordStringStringConstWithKnownIds(
	sf: ts.SourceFile,
	knownIds: Set<string>
): string | undefined {
	let offender: string | undefined;
	function visit(node: ts.Node): void {
		if (ts.isVariableStatement(node)) {
			for (const decl of node.declarationList.declarations) {
				const typeText = decl.type ? decl.type.getText(sf) : '';
				if (!/Record\s*<\s*string\s*,\s*string\s*>/.test(typeText)) continue;
				if (!decl.initializer || !ts.isObjectLiteralExpression(decl.initializer)) continue;
				const hits = knownIdHitsInObjectLiteral(decl.initializer, knownIds);
				if (hits >= MIN_KNOWN_ID_HITS) offender = decl.name.getText(sf);
			}
		}
		ts.forEachChild(node, visit);
	}
	ts.forEachChild(sf, visit);
	return offender;
}

describe('AC-8: keine lokale Metrik-ID→Name-Tabelle, keine hartkodierte Standardliste', () => {
	// AC-8: jeder Name kommt ausschließlich aus dem übergebenen catalog-Parameter
	// — keine neue, redaktionell gepflegte Zweitquelle (Ratsche gegen #1435).
	test('Keine lokale Record<string,string>-artige Konstante im Modul', () => {
		const sf = parseModule();
		const offender = findRecordStringStringConst(sf);
		assert.equal(
			offender,
			undefined,
			`tripActiveMetricNames.ts deklariert eine lokale Record<string,string>-Konstante ` +
				`(${offender}) — das wäre eine neue Metrik-ID→Name-Zweitquelle. Namen kommen ` +
				`ausschließlich aus dem übergebenen catalog-Parameter (AC-8, #1435).`
		);
	});

	test('Kein Import oder Re-Export von DEFAULT_TRIP_METRIC_IDS', () => {
		const sf = parseModule();
		let referencesDefaultList = false;
		function visit(node: ts.Node): void {
			if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
				if (/DEFAULT_TRIP_METRIC_IDS/.test(node.getText(sf))) referencesDefaultList = true;
			}
			ts.forEachChild(node, visit);
		}
		ts.forEachChild(sf, visit);
		assert.equal(
			referencesDefaultList,
			false,
			'tripActiveMetricNames.ts importiert oder re-exportiert DEFAULT_TRIP_METRIC_IDS — der ' +
				'Altbestand-Zustand darf die sieben Standard-Größen nirgends aufzählen (AC-8/AC-2, Known Limitations).'
		);
	});

	test('Keine lokale String-Array-Konstante mit >= 3 bekannten Register-Kennungen', () => {
		// Zusätzliche Ratsche gegen eine hartkodierte Standard-Metrik-LISTE (statt
		// einer Record<string,string>-Tabelle) — z.B. ein Array-Literal, das
		// Kennungen aus dem vollständigen Register aufzählt. Fix-Loop 2, F004:
		// die Kennungs-Menge kommt aus `deriveKnownMetricIds()` (Register-
		// Ableitung), nicht mehr aus einer siebenteiligen Liste im Wächter selbst.
		const sf = parseModule();
		const offender = findStringArrayWithKnownIds(sf, knownMetricIds());
		assert.equal(
			offender,
			undefined,
			`tripActiveMetricNames.ts deklariert eine Array-Konstante (${offender}), die mehrere ` +
				'bekannte Register-Kennungen aufzählt — das wäre die verbotene lokale ' +
				'DEFAULT_TRIP_METRIC_IDS-Zweitschrift (AC-8).'
		);
	});
});

describe('AC-8 (Fix-Loop 2, F004): Kennungs-Menge kommt aus dem Register, nicht aus einer Liste im Wächter', () => {
	test('Ableitung findet mindestens 20 Kennungen im Register und deckt Nicht-Standard-Größen ab', () => {
		const ids = knownMetricIds();
		assert.ok(
			ids.size >= MIN_CATALOG_IDS,
			`Nur ${ids.size} Kennungen abgeleitet, erwartet mindestens ${MIN_CATALOG_IDS}.`
		);
		// Stichprobe: Größen, die NICHT zu den sieben alten KNOWN_DEFAULT_IDS
		// gehören — genau die Lücke, die Fix-Loop 2 F004 schließt.
		for (const id of ['freezing_level', 'snow_depth', 'fresh_snow', 'cape', 'dewpoint', 'pressure', 'uv_index']) {
			assert.ok(ids.has(id), `Register-Ableitung fehlt bekannte Kennung "${id}".`);
		}
	});
});

// Fix-Loop 1, F003: die drei Tests oben erkannten nur (a) eine lokale
// `Record<string,string>`-Variable und (b) ein reines String-Array mit
// bekannten Kennungen. Nicht erkannt: `new Map([['temperature',...],...])`,
// ein Tupel-Array `[['temperature','Temperatur'],...]` (auch als Argument
// von `Object.fromEntries([...])` — dieselbe AST-Form), und ein Objekt-
// Literal ohne Typannotation (`const T = { temperature: 'Temperatur', ... }`).
// Alle vier Umgehungen wurden vom Adversary mit einer 7-Einträge-Tabelle
// vorgeführt; die drei Tests oben blieben dabei grün.
//
// Die Regel hängt bewusst an den METRIK-KENNUNGEN (>= 3 Treffer aus dem
// vollständigen, aus dem Register ABGELEITETEN Vokabular — Fix-Loop 2,
// F004), nicht an "irgendeine Map/irgendein Objekt" — sonst würden auch
// legitime kleine, fachfremde Zuordnungen verboten (Gegenprobe unten).
describe('AC-8 (Fix-Loop 1, F003): Ratsche erkennt auch Map/Tupel-Array/fromEntries/Objekt-Literal-Umgehungen', () => {
	test('Kein Tupel-Array-Literal mit >= 3 bekannten Metrik-Kennungen (deckt `new Map([...])`, `Object.fromEntries([...])` und ein freistehendes Tupel-Array ab)', () => {
		const sf = parseModule();
		const offenderHits = findTupleArrayOffenderHits(sf, knownMetricIds());
		assert.equal(
			offenderHits,
			0,
			'tripActiveMetricNames.ts enthält ein Tupel-Array-Literal (Muster [[id, name], ...]) mit ' +
				`${offenderHits} bekannten Metrik-Kennungen als Schlüssel — egal ob als \`new Map([...])\`-` +
				'Argument, `Object.fromEntries([...])`-Argument oder freistehendes Array: das wäre eine neue ' +
				'lokale Metrik-ID→Name-Zweitquelle (AC-8, Fix-Loop 1 F003).'
		);
	});

	test('Kein Objekt-Literal mit >= 3 bekannten Metrik-Kennungen als Schlüsseln — auch ohne Typannotation', () => {
		const sf = parseModule();
		const offenderHits = findObjectLiteralOffenderHits(sf, knownMetricIds());
		assert.equal(
			offenderHits,
			0,
			'tripActiveMetricNames.ts enthält ein Objekt-Literal mit ' +
				`${offenderHits} bekannten Metrik-Kennungen als Schlüssel (z.B. \`{ temperature: 'Temperatur', ... }\`) ` +
				'— unabhängig von einer Typannotation wäre das eine neue lokale Namenstabelle (AC-8, Fix-Loop 1 F003).'
		);
	});

	// Gegenprobe gegen Falsch-Alarm: eine kleine, fachfremde Zuordnung (keine
	// Metrik-Kennungen als Schlüssel) darf NICHT anschlagen — die Regel hängt
	// an den Kennungen selbst, nicht an "irgendeine Map/irgendein Objekt".
	test('Gegenprobe: eine kleine fachfremde Map/Objekt-Literal-Zuordnung ohne Metrik-Kennungen schlägt nicht an', () => {
		const harmlessSource = `
			const WEEKDAY_LABELS = new Map([['mon', 'Montag'], ['tue', 'Dienstag'], ['wed', 'Mittwoch']]);
			const STATUS_LABELS = { ok: 'Erledigt', pending: 'Offen', failed: 'Fehlgeschlagen' };
		`;
		const sf = ts.createSourceFile('harmless.ts', harmlessSource, ts.ScriptTarget.Latest, true);
		const knownIds = knownMetricIds();
		const tupleHits = findTupleArrayOffenderHits(sf, knownIds);
		const objectHits = findObjectLiteralOffenderHits(sf, knownIds);
		assert.equal(tupleHits, 0, 'Die Wochentags-Map wurde fälschlich als Metrik-Namenstabelle erkannt.');
		assert.equal(objectHits, 0, 'Das Status-Objekt-Literal wurde fälschlich als Metrik-Namenstabelle erkannt.');
	});
});

/**
 * Alle relativen `./…`-Importe von `tripActiveMetricNames.ts` in dieselbe
 * Verzeichnisebene aufgelöst (nur eine Ebene tief, keine Rekursion über den
 * gesamten Abhängigkeitsbaum — s. Spec Known Limitations).
 */
function collectSameDirRelativeImportPaths(entryFilePath: string): string[] {
	const sf = parseFile(entryFilePath);
	const dir = dirname(entryFilePath);
	const resolved: string[] = [];
	function visit(node: ts.Node): void {
		if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
			const spec = node.moduleSpecifier.text;
			if (spec.startsWith('./')) {
				const withExt = spec.endsWith('.ts') ? spec : `${spec}.ts`;
				resolved.push(join(dir, withExt));
			}
		}
		ts.forEachChild(node, visit);
	}
	ts.forEachChild(sf, visit);
	return resolved;
}

// Fix-Loop 2, F004 (zweite Lücke): eine Namenstabelle in einer Nachbardatei
// (z.B. `fallbackNames.ts`), die `tripActiveMetricNames.ts` per relativem
// Import nutzt, wurde von keinem der obigen Tests gesehen — sie prüften nur
// den Syntaxbaum des Bausteins selbst. Der Wächter prüft deshalb zusätzlich
// jede `.ts`-Datei desselben Verzeichnisses, die der Baustein importiert,
// mit denselben Regeln (Record-Typ, String-Array, Tupel-Array/Map/
// fromEntries, Objekt-Literal).
describe('AC-8 (Fix-Loop 2, F004): Auslagerung in eine Nachbardatei desselben Verzeichnisses', () => {
	test('Same-Verzeichnis-Importe von tripActiveMetricNames.ts enthalten keine ausgelagerte Metrik-Namenstabelle', () => {
		const knownIds = knownMetricIds();
		const neighborPaths = collectSameDirRelativeImportPaths(MODULE_PATH);
		for (const path of neighborPaths) {
			let sf: ts.SourceFile;
			try {
				sf = parseFile(path);
			} catch {
				// Datei existiert nicht (z.B. reiner Typ-Import ohne .ts-Gegenstück
				// im selben Verzeichnis) — kein Befund, nichts zu prüfen.
				continue;
			}

			const recordOffender = findRecordStringStringConstWithKnownIds(sf, knownIds);
			assert.equal(
				recordOffender,
				undefined,
				`${path}: lokale Record<string,string>-Konstante (${recordOffender}) mit >= ` +
					`${MIN_KNOWN_ID_HITS} bekannten Register-Kennungen als Schlüssel — ausgelagerte ` +
					'Metrik-Namenstabelle in einer Nachbardatei (AC-8, Fix-Loop 2 F004, Fix-Loop 3 F005).'
			);

			const arrayOffender = findStringArrayWithKnownIds(sf, knownIds);
			assert.equal(
				arrayOffender,
				undefined,
				`${path}: Array-Konstante (${arrayOffender}) mit >= ${MIN_KNOWN_ID_HITS} bekannten Register-` +
					'Kennungen — ausgelagerte Metrik-Namensliste in einer Nachbardatei (AC-8, Fix-Loop 2 F004).'
			);

			const tupleHits = findTupleArrayOffenderHits(sf, knownIds);
			assert.equal(
				tupleHits,
				0,
				`${path}: Tupel-Array-Literal mit ${tupleHits} bekannten Metrik-Kennungen — ausgelagerte ` +
					'Metrik-Namenstabelle in einer Nachbardatei (AC-8, Fix-Loop 2 F004).'
			);

			const objectHits = findObjectLiteralOffenderHits(sf, knownIds);
			assert.equal(
				objectHits,
				0,
				`${path}: Objekt-Literal mit ${objectHits} bekannten Metrik-Kennungen als Schlüssel — ` +
					'ausgelagerte Metrik-Namenstabelle in einer Nachbardatei (AC-8, Fix-Loop 2 F004).'
			);
		}
	});
});

// Bewusst NICHT abgedeckt (Tech-Lead-Entscheidung, Fix-Loop 2): berechnete
// Schlüssel (`{ [ID_TEMP]: 'Temperatur' }`) und Tabellenaufbau in einer
// Schleife aus zwei parallelen Arrays. Beides setzt eine absichtliche
// Umgehung voraus, keinen Unfall — s. Spec Known Limitations.
