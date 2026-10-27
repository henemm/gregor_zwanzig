// Waechter (#1480): kein NEUER lokaler Nachbau der Gewitter-Stufenskala
// (ThunderLevel: NONE/LOW/MED/HIGH) in frontend/src/.
//
// #1474 gab der Gewitterstaerke eine vierte Stufe. Neun Stellen hatten die
// Zuordnung lokal nachgebaut; die NEUNTE entstand beim Reparieren der
// vierten (['NONE','MED','HIGH','LOW'] -- alle vier Stufen da, falsche
// Position). Dieser Waechter verhindert die NAECHSTE Kopie (Spec
// docs/specs/modules/thunder_scale_guard.md). Backend-Pendant:
// tests/tdd/test_thunder_scale_local_copy_guard.py -- beide Waechter sind
// bewusst GETRENNT (kein TS-Parsing aus Python, kein Python-Parsing aus TS,
// s. tests/unit/test_compare_metric_catalog_consistency.py:19-21).
//
// TDD RED: Vertrag und Tests stehen in dieser Datei, die Implementierung des
// Erkennungs-Kerns (scanThunderScaleCopies) folgt in GREEN unterhalb der
// Tests -- Bauform-Vorbild thunderThresholdCatalogGuard.test.ts (svelte AST)
// und thunderThresholdLevels.test.ts (Live-Read per execFileSync). Bis dahin
// ist jeder Test unten ein absichtlicher ReferenceError auf das noch nicht
// existierende Kern-Symbol.
//
// Vertrag der Modul-Symbole (GREEN faellig)
// ------------------------------------------
// `EXPORT const EXPIRY = '2026-11-01'` -- ISO-Pruefdatum (bereits gesetzt,
// kein Kern-Symbol, reine Konstante ohne Verhalten).
//
// `scanThunderScaleCopies(source: string, filename: string, opts?: { order?:
// string[]; rules?: string[] }): Finding[]` scannt EINEN Quelltext (TS ODER
// Svelte, je nach `filename`-Endung). `opts.rules` waehlt aus ('A'|'P'|'C'|
// 'D'), Default ('A','P','C'). `opts.order` injiziert die kanonische
// Stufenordnung fuer Regel P (Default: Live-Read per `execFileSync('uv',
// ['run','python3','-c', ...])` gegen src/app/thunder_scale.py -- NIE eine
// hartkodierte Erwartungsliste im Kern selbst, Praezedenz #1424 F001/#1351
// F003).
//
// `Finding` traegt mindestens `.file`, `.line` (1-basiert), `.rule`
// ('A'|'P'|'C'|'D') und `.symbol`.
//
// Duldung: `// gz-thunder-scale: <Begruendung>` (>= 15 sinnvolle Zeichen) an
// der Fundstelle laesst den Fund durch. "Sinnvoll" = Buchstaben/Ziffern;
// Interpunktion, Leerraum und Unterstriche zaehlen nicht, eine reine
// Zeichen-Wiederholung ebenfalls nicht.
//
// Scanflaeche des Produktionswaechters (GREEN, unterhalb dieser Tests):
// `frontend/src/**/*.{ts,svelte}` fuer Regel A/P/C, zusaetzlich
// `frontend/**/*.test.ts` fuer Regel D. Fixture-Quelltexte liegen
// AUSSERHALB davon in
// frontend/src/lib/components/shared/weather-metrics-tab/__tests__/fixtures/thunder_scale_guard_cases.ts.txt
// (Endung `.ts.txt`, kein `*.ts`/`*.svelte`).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve, extname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import ts from 'typescript';
import { parse as svelteParse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = join(here, 'fixtures');
const FAELLE_DATEI = join(FIXTURE_DIR, 'thunder_scale_guard_cases.ts.txt');

// Pruefdatum des Regel-Budgets. Kein Kern-Symbol, darf schon in RED
// existieren -- reine Konstante ohne Verhalten.
export const EXPIRY = '2026-11-01';

interface Finding {
	file: string;
	line: number;
	rule: string;
	symbol: string;
}

function fall(name: string): string {
	const text = readFileSync(FAELLE_DATEI, 'utf-8');
	const parts = text.split(/^# === (\S+) ===$\n/m);
	const vorrat = new Map<string, string>();
	for (let i = 1; i < parts.length; i += 2) {
		vorrat.set(parts[i], parts[i + 1]);
	}
	const quelle = vorrat.get(name);
	assert.ok(quelle !== undefined, `Fall "${name}" fehlt in ${FAELLE_DATEI}: ${[...vorrat.keys()].join(', ')}`);
	return quelle as string;
}

function lineOf(source: string, needle: string): number {
	const lines = source.split('\n');
	for (let i = 0; i < lines.length; i++) {
		if (lines[i].includes(needle)) return i + 1;
	}
	throw new Error(`Ankertext "${needle}" fehlt im Fixture-Quelltext`);
}

function refs(findings: Finding[]): string {
	return findings.length ? findings.map((f) => `${f.file}:${f.line}`).join(', ') : '(keine)';
}

// ---------------------------------------------------------------------------
// Selbstbezug: Fixture-Ablage liegt ausserhalb der Scanflaeche (AC-19)
// ---------------------------------------------------------------------------

describe('Selbstbezug (AC-19): Fixture-Ablage bleibt ausserhalb der Scanflaeche', () => {
	test('Voraussetzung: die Ablage enthaelt keine .ts/.svelte-Datei, obwohl sie den vollen Stufen-Wortschatz fuehrt', () => {
		const alle = readdirSync(FIXTURE_DIR);
		assert.ok(alle.includes('thunder_scale_guard_cases.ts.txt'), 'Fixture-Datei fehlt/umbenannt');
		const scanbar = alle.filter((f) => f.endsWith('.ts') || f.endsWith('.svelte'));
		assert.deepEqual(scanbar, [], `Ablage darf keine .ts/.svelte-Datei enthalten: ${scanbar.join(', ')}`);
		assert.ok(readFileSync(FAELLE_DATEI, 'utf-8').includes('MED'), 'Vorlage ohne echten Verstoss');
	});

	test('Positivkontrolle: derselbe Inhalt MIT .ts-Endung waere ein Fund -- die Ablage entkommt nur ueber die Endung, nicht weil der Kern den Inhalt ignoriert', () => {
		const roh = readFileSync(FAELLE_DATEI, 'utf-8');
		const findings = scanThunderScaleCopies(roh, 'kontrafaktisch.ts', { rules: ['A'] }); // eslint-disable-line
		assert.ok(findings.length > 0, `Positivkontrolle haette Funde liefern muessen: ${refs(findings)}`);
	});
});

// ---------------------------------------------------------------------------
// Regel A, Schwelle 3 (AC-13)
// ---------------------------------------------------------------------------

describe('Regel A, Schwelle 3 (AC-13)', () => {
	test('Array mit drei distinkten Stufen-Woertern wird gemeldet', () => {
		const quelle = fall('a13-fund');
		const findings = scanThunderScaleCopies(quelle, '<a13-fund>', { rules: ['A'] }); // eslint-disable-line
		assert.equal(findings.length, 1, `erwartet 1 Fund, bekommen: ${refs(findings)}`);
		assert.equal(findings[0].line, lineOf(quelle, 'STUFEN = ['));
	});

	test('Array mit nur zwei der vier Woerter (fremde Skala, Muster alertChannelState.ts) bleibt gruen', () => {
		const quelle = fall('a13-kontrolle-alertchannel');
		const findings = scanThunderScaleCopies(quelle, '<a13-kontrolle>', { rules: ['A'] }); // eslint-disable-line
		assert.deepEqual(findings, [], `2-von-4-Woerter darf keinen Fund ausloesen: ${refs(findings)}`);
	});
});

// ---------------------------------------------------------------------------
// Regel P -- Positions-Abgleich (AC-14, AC-15, AC-16)
// ---------------------------------------------------------------------------

describe('Regel P -- Positions-Abgleich (AC-14)', () => {
	test('alle vier Stufen vorhanden, MED an falscher Position (reale neunte #1474-Stelle) wird gemeldet', () => {
		const quelle = fall('p14-falsche-position');
		const findings = scanThunderScaleCopies(quelle, '<p14-fund>', { rules: ['P'] }); // eslint-disable-line
		assert.equal(findings.length, 1, `erwartet 1 Fund, bekommen: ${refs(findings)}`);
	});

	test('Gegenprobe: dieselbe Laenge, dieselben vier Stufen, korrekte Reihenfolge bleibt gruen', () => {
		const quelle = fall('p14-korrekte-position');
		const findings = scanThunderScaleCopies(quelle, '<p14-ok>', { rules: ['P'] }); // eslint-disable-line
		assert.deepEqual(findings, [], `Korrekte Reihenfolge darf keinen Fund ausloesen: ${refs(findings)}`);
	});
});

describe('Regel P -- kein Fund ausserhalb der Bei-NONE-beginnenden Folge (AC-15)', () => {
	test('Array, das ausdruecklich nicht bei NONE beginnt (Muster thunderThresholdLevels.test.ts::slice(1)), bleibt gruen', () => {
		const quelle = fall('p15-nicht-bei-none');
		const findings = scanThunderScaleCopies(quelle, '<p15>', { rules: ['P'] }); // eslint-disable-line
		assert.deepEqual(findings, [], `Nicht-bei-NONE-startendes Array darf keinen P-Fund ausloesen: ${refs(findings)}`);
	});
});

describe('Regel P -- injizierte Ordnung entscheidet, nicht eine hartkodierte Liste (AC-16)', () => {
	test('mit untergeschobener Ordnung [NONE,MED,LOW,HIGH]: die Fixture, die dieser Ordnung folgt, bleibt gruen -- die der ECHTEN Ordnung folgende wird rot', () => {
		const injiziert = ['NONE', 'MED', 'LOW', 'HIGH'];
		const folgtInjiziert = fall('p16-matches-injizierte-ordnung');
		const folgtEcht = fall('p16-matches-echte-ordnung');

		const grundlage = scanThunderScaleCopies(folgtInjiziert, '<p16-injiziert>', { // eslint-disable-line
			rules: ['P'],
			order: injiziert
		});
		assert.deepEqual(
			grundlage,
			[],
			`Fixture, die der UNTERGESCHOBENEN Ordnung folgt, muss unter dieser Ordnung gruen sein: ${refs(grundlage)}`
		);

		const umkehr = scanThunderScaleCopies(folgtEcht, '<p16-echt>', { rules: ['P'], order: injiziert }); // eslint-disable-line
		assert.equal(
			umkehr.length,
			1,
			`Fixture, die der ECHTEN Ordnung folgt, muss unter der UNTERGESCHOBENEN Ordnung rot werden: ${refs(umkehr)}`
		);
	});

	test('mit der echten (live gelesenen) Ordnung dreht sich das Ergebnis um -- kein hartkodierter Kern', () => {
		const folgtInjiziert = fall('p16-matches-injizierte-ordnung');
		const folgtEcht = fall('p16-matches-echte-ordnung');

		const echtFolgtEcht = scanThunderScaleCopies(folgtEcht, '<p16-echt-default>', { rules: ['P'] }); // eslint-disable-line
		assert.deepEqual(
			echtFolgtEcht,
			[],
			`Unter der ECHTEN (Default-)Ordnung muss die echt-folgende Fixture gruen sein: ${refs(echtFolgtEcht)}`
		);

		const echtFolgtInjiziert = scanThunderScaleCopies(folgtInjiziert, '<p16-injiziert-default>', { // eslint-disable-line
			rules: ['P']
		});
		assert.equal(
			echtFolgtInjiziert.length,
			1,
			`Unter der ECHTEN (Default-)Ordnung muss die der untergeschobenen Ordnung folgende Fixture rot werden: ${refs(echtFolgtInjiziert)}`
		);
	});
});

// ---------------------------------------------------------------------------
// Regel C (AC-17)
// ---------------------------------------------------------------------------

describe('Regel C -- Zahlen-Schwellenkette im thunder/gewitter-Namens-Scope (AC-17)', () => {
	test('Zahlen-Schwellenkette in einer Funktion mit thunder im Namen (rekonstruiert aus alertMetricLabels.ts, 46ff82c2) wird gemeldet', () => {
		const quelle = fall('c17-zahlen-schwelle-thunder');
		const findings = scanThunderScaleCopies(quelle, '<c17-fund>', { rules: ['C'] }); // eslint-disable-line
		assert.equal(findings.length, 1, `erwartet 1 Fund, bekommen: ${refs(findings)}`);
	});

	test('Gegenprobe: strukturell identische Kette ausserhalb des thunder/gewitter-Namensraums (Windstaerke) bleibt gruen', () => {
		const quelle = fall('c17-kontrolle-windstaerke');
		const findings = scanThunderScaleCopies(quelle, '<c17-kontrolle>', { rules: ['C'] }); // eslint-disable-line
		assert.deepEqual(findings, [], `Windstaerke-Formatierung darf keinen Fund ausloesen: ${refs(findings)}`);
	});

	test('Der Namens-Scope traegt die Gegenprobe wirklich: DIESELBE Fixture, nur umbenannt, wird still', () => {
		// Die Kontroll-Fixture oben unterscheidet sich nicht nur im Namen,
		// sondern auch in den Woertern ('stark'/'still' sind keine Stufen) --
		// sie bliebe also auch bei voellig fehlendem Scope-Filter gruen. Hier
		// wird die FUND-Fixture umbenannt: gleiche Woerter, gleiche Struktur,
		// nur der thunder-Bezug im Namen faellt weg.
		const quelle = fall('c17-zahlen-schwelle-thunder').replace(/thunderLevelLabel/g, 'gustLevelLabel');
		const findings = scanThunderScaleCopies(quelle, '<c17-umbenannt>', { rules: ['C'] }); // eslint-disable-line
		assert.deepEqual(
			findings,
			[],
			`Ohne thunder/gewitter im Namen darf Regel C nicht melden: ${refs(findings)}`
		);
	});
});

describe('Regel C -- verschachtelte Funktionen erben den Namens-Scope nicht (AC-9, Frontend-Pendant)', () => {
	// Alle DREI Funktionsformen, die der Kern kennt: Deklaration,
	// Arrow-Function und Function-Expression. Nur mit allen dreien faellt eine
	// Verengung der Sperre (etwa auf `ts.isFunctionDeclaration`) auf.
	const formen = [
		{ label: 'Function-Deklaration', slug: 'func' },
		{ label: 'Arrow-Function', slug: 'arrow' },
		{ label: 'Function-Expression', slug: 'funcexpr' }
	];

	for (const { label, slug } of formen) {
		test(`Innere ${label} OHNE eigenen thunder/gewitter-Namensbezug bleibt gruen, auch wenn die aeussere im Scope liegt`, () => {
			// Dieselbe Vererbungssperre wie im Backend (AC-9): ohne sie zoege eine
			// beliebige Zahlen-Schwellenkette in einer Hilfsfunktion den Scope der
			// umgebenden Funktion an sich -- genau der Fehlalarm, an dem im Backend
			// html.py::_confidence_dot_color haengt.
			const quelle = fall(`c9-innere-${slug}-ohne-vererbten-scope`);
			const findings = scanThunderScaleCopies(quelle, `<c9-kein-erbe-${slug}>`, { rules: ['C'] }); // eslint-disable-line
			assert.deepEqual(
				findings,
				[],
				`Innere ${label} ohne eigenen Namensbezug darf keinen Fund erben: ${refs(findings)}`
			);
		});

		test(`Umkehrprobe (${label}): traegt die innere Funktion den Namensteil SELBST, wird sie gemeldet`, () => {
			// Ohne diese Umkehrprobe waere der Test darueber auch von einer
			// Implementierung erfuellt, die verschachtelte Funktionen pauschal
			// uebergeht -- die Sperre soll aber nur die VERERBUNG unterbinden, nicht
			// den eigenen Scope-Check der inneren Funktion.
			const quelle = fall(`c9-innere-${slug}-mit-eigenem-scope`);
			const findings = scanThunderScaleCopies(quelle, `<c9-eigener-scope-${slug}>`, { rules: ['C'] }); // eslint-disable-line
			assert.equal(findings.length, 1, `erwartet 1 Fund, bekommen: ${refs(findings)}`);
			assert.equal(findings[0].symbol, 'thunderZahl');
		});
	}
});

// ---------------------------------------------------------------------------
// Regel D -- Paritaets-Behauptung (AC-18)
// ---------------------------------------------------------------------------

describe('Regel D -- Paritaets-Behauptung in Testdatei-Kommentaren (AC-18)', () => {
	test('Kommentar behauptet Uebereinstimmung ("1:1 aus ..."), Inhalt weicht ab -> Fund', () => {
		const quelle = fall('d18-behauptet-und-abweichend');
		const findings = scanThunderScaleCopies(quelle, '<d18-behauptet>', { rules: ['D'] }); // eslint-disable-line
		assert.equal(findings.length, 1, `erwartet 1 Fund, bekommen: ${refs(findings)}`);
	});

	test('Gegenprobe: dieselbe Abweichung OHNE Paritaetsbehauptung bleibt gruen', () => {
		const quelle = fall('d18-unbehauptet-gleiche-abweichung');
		const findings = scanThunderScaleCopies(quelle, '<d18-unbehauptet>', { rules: ['D'] }); // eslint-disable-line
		assert.deepEqual(findings, [], `Ohne Behauptung darf Regel D nicht melden: ${refs(findings)}`);
	});

	test('mehrzeilige Paritaetsbehauptung wird erkannt (Zeilenumbruch-Normalisierung)', () => {
		const quelle = fall('d18-mehrzeiliger-kommentar');
		const findings = scanThunderScaleCopies(quelle, '<d18-mehrzeilig>', { rules: ['D'] }); // eslint-disable-line
		assert.equal(findings.length, 1, `Mehrzeilige Behauptung nicht erkannt: ${refs(findings)}`);
	});
});

// ---------------------------------------------------------------------------
// Wirkungsnachweis (AC-20)
// ---------------------------------------------------------------------------

describe('Wirkungsnachweis (AC-20)', () => {
	test('der Waechter behauptet seine eigene Trefferzahl > 0 gegen eine Fixture mit bekanntem Verstoss', () => {
		const quelle = fall('a13-fund');
		const findings = scanThunderScaleCopies(quelle, '<ac20>', { rules: ['A'] }); // eslint-disable-line
		assert.ok(findings.length > 0, 'Bekannter Verstoss haette > 0 Funde liefern muessen');
	});
});

// ---------------------------------------------------------------------------
// Marker-Duldung (AC-21)
// ---------------------------------------------------------------------------

describe('Marker-Duldung (AC-21)', () => {
	test('Marker mit >= 15 sinnvollen Zeichen laesst den Fund durch', () => {
		const quelle = fall('e21-marker-ausreichend');
		const findings = scanThunderScaleCopies(quelle, '<e21-ok>', { rules: ['A'] }); // eslint-disable-line
		assert.deepEqual(findings, [], `Ausreichender Marker muss durchlassen: ${refs(findings)}`);
	});

	test('Gegenprobe: Marker mit Alibi-Begruendung ("x") unter 15 Zeichen zaehlt nicht', () => {
		const quelle = fall('e21-marker-unzureichend');
		const findings = scanThunderScaleCopies(quelle, '<e21-alibi>', { rules: ['A'] }); // eslint-disable-line
		assert.equal(findings.length, 1, `Alibi-Marker darf nicht durchlassen: ${refs(findings)}`);
	});

	// Fuellzeichen haben Laenge 15, aber null sinnvolle Zeichen; 15 gleiche
	// Buchstaben nur ein einziges verschiedenes. Waere der Notausgang der
	// Ratsche so zu oeffnen, stellte ihn jeder unter Zeitdruck still, ohne
	// eine Begruendung zu formulieren.
	for (const [name, was] of [
		['e21-marker-nur-punkte', '15 Punkte'],
		['e21-marker-nur-striche', '15 Bindestriche'],
		['e21-marker-nur-wiederholung', '15 gleiche Buchstaben'],
		['e21-marker-grenze-14', '14 sinnvolle Zeichen']
	]) {
		test(`Gegenprobe: ${was} sind keine Begruendung`, () => {
			const findings = scanThunderScaleCopies(fall(name), `<${name}>`, { rules: ['A'] }); // eslint-disable-line
			assert.equal(findings.length, 1, `${name} darf nicht durchlassen: ${refs(findings)}`);
		});
	}

	// Umlaute zaehlen als sinnvolle Zeichen -- unsere Begruendungen sind auf
	// Deutsch, ein zu scharfer Filter wiese echte Duldungen ab.
	for (const [name, was] of [
		['e21-marker-umlaute', 'deutsche Begruendung mit Umlauten (16 Zeichen)'],
		['e21-marker-grenze-15', 'exakt 15 sinnvolle Zeichen']
	]) {
		test(`${was} laesst durch`, () => {
			const findings = scanThunderScaleCopies(fall(name), `<${name}>`, { rules: ['A'] }); // eslint-disable-line
			assert.deepEqual(findings, [], `${name} muss durchlassen: ${refs(findings)}`);
		});
	}
});

// ---------------------------------------------------------------------------
// Pruefdatum (AC-22, Frontend-seitiger Anteil)
// ---------------------------------------------------------------------------

describe('Pruefdatum (AC-22)', () => {
	// doc-compliance-test: Abwesenheits-/Praesenz-Nachweis reiner Metadaten,
	// kein Laufzeitverhalten -- ausdrueckliche CLAUDE.md-Ausnahme, wie beim
	// Backend-Pendant.
	test('# doc-compliance-test: EXPIRY ist als Text in dieser Datei auffindbar (grep -n "2026-11-01")', () => {
		assert.equal(EXPIRY, '2026-11-01');
		const text = readFileSync(fileURLToPath(import.meta.url), 'utf-8');
		assert.ok(text.includes('2026-11-01'), 'Pruefdatum 2026-11-01 fehlt als Text in dieser Datei');
	});
});

// ---------------------------------------------------------------------------
// Die eigentliche Scanflaeche: frontend/src/**/*.{ts,svelte}
// ---------------------------------------------------------------------------

describe('Fehlalarm-Obergrenze gegen den echten Frontend-Baum', () => {
	test('frontend/src ist unter Regel A/P/C frei von unbegruendeten Funden', () => {
		const findings = scanThunderScaleTree([FRONTEND_SRC], { rules: ['A', 'P', 'C'] }); // eslint-disable-line
		assert.deepEqual(
			findings.map((f) => `${f.file}:${f.line} ${f.rule} (${f.symbol})`),
			[],
			'Fehlalarm auf dem echten Frontend-Baum -- erwartet 0 unbegruendete Funde'
		);
	});

	test('Die Whitelist kanonischer Quellen hat keinen Leerlauf-Eintrag', () => {
		// Wie im Backend: jeder Eintrag muss heute noch einen echten Fund
		// erzeugen. Ein umbenanntes/entfallenes Symbol macht ROT statt still --
		// sonst stellt die Whitelist irgendwann etwas anderes stumm als gedacht.
		const ohne = scanThunderScaleTree([FRONTEND_SRC], { // eslint-disable-line
			rules: ['A', 'P', 'C'],
			canonicalSymbols: []
		});
		const gefunden = new Set(ohne.map((f) => `${f.file.replace(/\\/g, '/')}|${f.symbol}`));
		const tot = CANONICAL_SYMBOLS.filter(
			([datei, symbol]) => ![...gefunden].some((g) => g.endsWith(`/${datei}|${symbol}`))
		);
		assert.deepEqual(
			tot,
			[],
			`Whitelist-Eintraege ohne echten Fund (umbenannt/verschoben/entfallen?): ${JSON.stringify(tot)}`
		);
	});

	test('Die Whitelist wirkt symbolscharf, nicht dateiweit', () => {
		// Der eigentliche Punkt: eine Kopie IN der kanonischen Datei, aber unter
		// ANDEREM Symbolnamen, wird gemeldet. Bei dateiweiter Whitelist bliebe
		// dieser Test gruen -- er unterscheidet die Bauweisen am Verhalten.
		// Die eingeschmuggelte Kopie stammt aus der ausgelagerten
		// Vorlagendatei (a13-fund -> STUFEN), damit diese Datei kein eigenes
		// Stufen-Literal zusammensetzt.
		const [kanonischRel] = CANONICAL_SYMBOLS[0];
		const tmp = mkdtempSync(join(tmpdir(), 'gz-1480-'));
		try {
			const ziel = join(tmp, kanonischRel);
			mkdirSync(dirname(ziel), { recursive: true });
			const original = readFileSync(join(FRONTEND_ROOT, kanonischRel), 'utf-8');
			writeFileSync(ziel, `${original}\n\n${fall('a13-fund')}`, 'utf-8');

			const funde = scanThunderScaleTree([tmp], { rules: ['A'] }); // eslint-disable-line
			assert.deepEqual(
				funde.map((f) => f.symbol).sort(),
				['STUFEN'],
				`Erwartet: die fremde Kopie STUFEN wird gemeldet, ORDINAL_ENUM nicht. Bekommen: ${refs(funde)}`
			);
		} finally {
			rmSync(tmp, { recursive: true, force: true });
		}
	});

	test('Regel D ueber die Frontend-Testdateien meldet keine unerfuellte Paritaets-Behauptung', () => {
		const findings = scanThunderScaleTree([FRONTEND_ROOT], { rules: ['D'], includeTests: true }); // eslint-disable-line
		assert.deepEqual(
			findings.map((f) => `${f.file}:${f.line} (${f.symbol})`),
			[],
			'Behauptete Paritaet ohne Deckung in den Frontend-Testdateien'
		);
	});

	test('Positivkontrolle zum Nullbefund: derselbe Lauf mit Regel A trifft sehr wohl -- der Baumlauf erreicht die Testdateien wirklich', () => {
		// Ohne diese Kontrolle waere der Nullbefund oben auch dann wahr, wenn
		// der Walk gar keine Datei besucht haette. Regel A auf Testdateien ist
		// genau das Dauerfeuer, wegen dem dort NUR Regel D laeuft.
		const treffer = scanThunderScaleTree([FRONTEND_ROOT], { rules: ['A'], includeTests: true }); // eslint-disable-line
		assert.ok(
			treffer.length > 0,
			'Der Testdatei-Lauf hat keine einzige Datei erreicht -- der Nullbefund oben waere wertlos'
		);
	});
});

// ===========================================================================
// Erkennungs-Kern (#1480) -- GREEN
//
// Bewusst NUR im Frontend-Sprachraum: kein Python-Parsing hier, kein
// TS-Parsing im Backend-Waechter (tests/unit/test_compare_metric_catalog_
// consistency.py:19-21 -- TS-Parsing aus Python heraus hat am 2026-07-24 die
// gesamte pytest-Collection zerstoert). Die kanonische Stufenordnung wird
// LIVE gelesen (execFileSync gegen src/app/thunder_scale.py) und ist ueber
// `opts.order` injizierbar -- eine hartkodierte Erwartungsliste waere kein
// Drift-Waechter (Praezedenz #1424 F001, #1351 F003).
// ===========================================================================

// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src
const FRONTEND_SRC = resolve(here, ...Array(5).fill('..'));
// Regel D laeuft auf `frontend/**/*.test.ts` -- also eine Ebene weiter oben
// als A/P/C, damit auch Testdateien ausserhalb von `src/` erfasst sind.
const FRONTEND_ROOT = resolve(FRONTEND_SRC, '..');
// ... -> frontend -> Repo-Wurzel (relativ zur eigenen Datei, damit ein
// Worktree seinen EIGENEN Baum misst und nicht den des Hauptcheckouts).
const REPO_ROOT = resolve(here, ...Array(7).fill('..'));

// Kanonische Quellen des Frontends als [Datei, Symbol]-Paare: die Stellen,
// die die Stufenskala fuehren DUERFEN. Keine Duldung eines Verstosses,
// sondern die Bezugsquelle selbst -- deshalb Whitelist im Waechter statt
// Marker im Produktivcode (Entscheid Team-Lead 2026-08-20; Backend-Pendant:
// ScaleSpec.canonical_symbols).
//
// SYMBOLscharf, nicht dateiweit: eine dateiweite Whitelist liesse die
// kanonischen Dateien vollstaendig unbewacht, und die naechste Kopie entsteht
// erfahrungsgemaess NEBEN der Quelle (die neunte #1474-Stelle entstand beim
// Reparieren der vierten).
//
// NICHT enthalten, obwohl in der Kontextanalyse als kanonische Quelle
// gefuehrt: `types.ts::ThunderLevel` (Typ-Union, kein Array-Literal) und
// `compareMetricCatalogLoader.ts::deriveThunderThresholdLevels` /
// `thunderThresholdLevelsFromCatalog` (leiten zur Laufzeit ab). Beide
// erzeugen heute KEINEN Fund -- ein Eintrag dafuer waere ein Leerlauf-Eintrag
// (gemessen 2026-08-20), und schluege einer kuenftig doch an, waere das ein
// echtes Signal (Rueckfall hinter #1911).
//
// Eine Altlasten-Basislinie wie im Backend braucht das Frontend NICHT: der
// Bestand ist seit #1488/#1911 frei von aktiven Kopien.
const CANONICAL_SYMBOLS: Array<[string, string]> = [
	['src/lib/components/shared/corridor-editor/corridorEditorState.ts', 'ORDINAL_ENUM']
];

const MARKER = 'gz-thunder-scale';
// Sinnvolle Zeichen = Buchstaben/Ziffern. `\p{L}` haelt deutsche Umlaute
// drin (unsere Begruendungen sind auf Deutsch), Interpunktion, Leerraum und
// Unterstriche fallen weg -- Pendant zu `_UNWORT` im Backend-Waechter und in
// tests/tdd/test_repo_path_hardcoding_ratchet.py.
const NON_WORD_RE = /[^\p{L}\p{N}]+/gu;
const MARKER_MIN_LENGTH = 15;
// Zusaetzlich: eine Wiederholung EINES Zeichens ueberlebt die Filterung mit
// voller Laenge, ist aber genauso wenig eine Begruendung wie 15 Punkte.
const MARKER_MIN_DISTINCT = 5;
// Schwelle 3, nicht 2: Schwelle 2 erzeugte drei Fehlalarme auf
// alertChannelState.ts (['LOW','MODERATE','HIGH'] -- fremde Skala).
const RULE_A_THRESHOLD = 3;
const NAME_SCOPE_TOKENS = ['thunder', 'gewitter'];

// Belegte Wortlaute aus dem Bestand (Regel D), keine erfundenen.
const PARITY_CLAIM_RE = /1:1|wortw(oe|ö)rt|identische reihenfolge|eingefroren aus dem|unver(ae|ä)ndert (aus|uebernommen)/i;

// Deutsche und englische Schreibweisen zeigen auf denselben Enum-Namen; die
// RANGFOLGE steckt ausschliesslich in der uebergebenen `order`.
const ALIASES: Record<string, string> = {
	none: 'NONE',
	kein: 'NONE',
	keine: 'NONE',
	keins: 'NONE',
	low: 'LOW',
	leicht: 'LOW',
	med: 'MED',
	medium: 'MED',
	mittel: 'MED',
	'mäßig': 'MED',
	maessig: 'MED',
	high: 'HIGH',
	hoch: 'HIGH'
};

const PY_SCRIPT =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from app.thunder_scale import thunder_ordinal\n' +
	'from app.models import ThunderLevel\n' +
	'print(json.dumps([l.name for l in sorted(ThunderLevel, key=thunder_ordinal)]))\n';

let canonicalOrderCache: string[] | null = null;

/** Kanonische Stufenordnung, LIVE aus src/app/thunder_scale.py gelesen. */
function canonicalOrder(): string[] {
	if (canonicalOrderCache === null) {
		const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], {
			cwd: REPO_ROOT,
			encoding: 'utf-8'
		});
		canonicalOrderCache = JSON.parse(stdout.trim()) as string[];
	}
	return canonicalOrderCache;
}

interface ScanOptions {
	order?: string[];
	rules?: string[];
	includeTests?: boolean;
	canonicalSymbols?: Array<[string, string]>;
}

/** Pfadvergleich ueber das Repo-relative Ende -- ein Worktree misst so seinen
 *  EIGENEN Baum, ohne dass irgendwo ein absoluter Pfad steht. */
function istPfad(kandidat: string, relativ: string): boolean {
	return kandidat.replace(/\\/g, '/').endsWith('/' + relativ.replace(/^\//, ''));
}

function canonIndex(raw: string, order: string[]): number {
	const name = ALIASES[String(raw).trim().toLowerCase()];
	return name === undefined ? -1 : order.indexOf(name);
}

function distinctIndices(values: string[], order: string[]): number[] {
	const set = new Set<number>();
	for (const v of values) {
		const idx = canonIndex(v, order);
		if (idx >= 0) set.add(idx);
	}
	return [...set].sort((a, b) => a - b);
}

/** Regel P: Positions-Abgleich. Greift NUR, wenn die Folge beansprucht, beim
 *  ersten Rang (NONE/"kein") zu beginnen -- eine bewusste Teilfolge ab "leicht"
 *  (thunderThresholdLevels.test.ts::slice(1)) ist kein Positionsfehler. */
function positionVerdict(values: string[], order: string[]): 'n/a' | 'ok' | 'mismatch' {
	const idxs = values.map((v) => canonIndex(v, order)).filter((i) => i >= 0);
	if (idxs.length < 2 || idxs[0] !== 0) return 'n/a';
	return idxs.every((v, i) => v === i) ? 'ok' : 'mismatch';
}

function hasParityClaim(comment: string): boolean {
	// Zeilenumbrueche und Kommentarmarker normalisieren, sonst zerreisst ein
	// mehrzeiliger Wortlaut mitten in der Formulierung.
	const normalized = (comment ?? '')
		.replace(/\/\/|\/\*|\*\//g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
	return PARITY_CLAIM_RE.test(normalized);
}

/** Traegt der Text genug SINNVOLLE Zeichen fuer eine Duldung (AC-21)?
 *  Fuellzeichen ("..............." ) fallen auf 0, eine Zeichen-Wiederholung
 *  ("aaaaaaaaaaaaaaa") auf ein einziges verschiedenes Zeichen. */
function istBegruendung(text: string): boolean {
	const kern = text.replace(NON_WORD_RE, '');
	return kern.length >= MARKER_MIN_LENGTH && new Set(kern.toLowerCase()).size >= MARKER_MIN_DISTINCT;
}

/** Duldung an der Fundstelle -- nie ueber eine zentrale Liste, nie ueber
 *  Zeilennummern (#1466). Eine Alibi-Begruendung unter 15 Zeichen zaehlt nicht. */
function markerCovers(lines: string[], line: number): boolean {
	const re = new RegExp(`//\\s*${MARKER}\\s*:(.*)`);
	const candidates: string[] = [];
	let idx = line - 1;
	if (idx >= 0 && idx < lines.length) candidates.push(lines[idx]);
	idx -= 1;
	while (idx >= 0 && lines[idx].trim().startsWith('//')) {
		candidates.push(lines[idx]);
		idx -= 1;
	}
	return candidates.some((l) => {
		const m = re.exec(l);
		return m !== null && istBegruendung(m[1]);
	});
}

// --- TypeScript-Adapter ----------------------------------------------------

function tsStringValue(node: ts.Node): string | undefined {
	return ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) ? node.text : undefined;
}

function tsSymbolOf(node: ts.Node): string {
	let cur: ts.Node | undefined = node;
	while (cur) {
		if (ts.isVariableDeclaration(cur) && ts.isIdentifier(cur.name)) return cur.name.text;
		if (ts.isFunctionDeclaration(cur) && cur.name) return cur.name.text;
		if (ts.isPropertyAssignment(cur) && ts.isIdentifier(cur.name)) return cur.name.text;
		cur = cur.parent;
	}
	return '<anonym>';
}

function tsFunctionName(node: ts.Node): string | undefined {
	if (ts.isFunctionDeclaration(node) && node.name) return node.name.text;
	if (ts.isMethodDeclaration(node) && ts.isIdentifier(node.name)) return node.name.text;
	const eltern = node.parent;
	if (eltern && ts.isVariableDeclaration(eltern) && ts.isIdentifier(eltern.name)) return eltern.name.text;
	return undefined;
}

function inNameScope(name: string | undefined): boolean {
	if (!name) return false;
	const klein = name.toLowerCase();
	return NAME_SCOPE_TOKENS.some((t) => klein.includes(t));
}

/** Beschriftungen aus Verzweigungs-/switch-Zweigen EINER Funktion -- ohne die
 *  Koerper verschachtelter Funktionen (die bekommen ihren eigenen Scope-Check,
 *  Vererbungssperre analog zum Backend, AC-9). */
function tsBranchWords(body: ts.Node): { words: string[]; anchor: ts.Node | undefined } {
	const words: string[] = [];
	let anchor: ts.Node | undefined;
	const sammle = (n: ts.Node) => {
		const wert = tsStringValue(n);
		if (wert !== undefined) words.push(wert);
		ts.forEachChild(n, sammle);
	};
	const gehe = (n: ts.Node) => {
		if (n !== body && (ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n))) {
			return;
		}
		if (ts.isIfStatement(n) || ts.isSwitchStatement(n)) {
			if (anchor === undefined) anchor = n;
			sammle(n);
			return;
		}
		ts.forEachChild(n, gehe);
	};
	gehe(body);
	return { words, anchor };
}

function scanTsSource(
	source: string,
	filename: string,
	order: string[],
	rules: string[],
	out: Finding[]
): void {
	const sf = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
	const melde = (node: ts.Node, rule: string) =>
		out.push({ file: filename, line: lineOf(node), rule, symbol: tsSymbolOf(node) });

	const visit = (node: ts.Node) => {
		if (ts.isArrayLiteralExpression(node)) {
			const values = node.elements
				.map((el) => tsStringValue(el))
				.filter((v): v is string => v !== undefined);
			if (rules.includes('A') && distinctIndices(values, order).length >= RULE_A_THRESHOLD) {
				melde(node, 'A');
			}
			if (rules.includes('P') && positionVerdict(values, order) === 'mismatch') melde(node, 'P');
			if (rules.includes('D')) {
				const ranges = ts.getLeadingCommentRanges(sf.text, tsDeclStart(node)) ?? [];
				const kommentar = ranges.map((r) => sf.text.slice(r.pos, r.end)).join('\n');
				if (hasParityClaim(kommentar) && positionVerdict(values, order) === 'mismatch') {
					melde(node, 'D');
				}
			}
		}
		if (ts.isObjectLiteralExpression(node) && rules.includes('A')) {
			const keys: string[] = [];
			for (const prop of node.properties) {
				if (!ts.isPropertyAssignment(prop)) continue;
				if (ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name)) keys.push(prop.name.text);
			}
			if (distinctIndices(keys, order).length >= RULE_A_THRESHOLD) melde(node, 'A');
		}
		if (
			rules.includes('C') &&
			(ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node) || ts.isMethodDeclaration(node)) &&
			node.body &&
			inNameScope(tsFunctionName(node))
		) {
			const { words, anchor } = tsBranchWords(node.body);
			if (anchor && distinctIndices(words, order).length >= 2) {
				out.push({
					file: filename,
					line: lineOf(anchor),
					rule: 'C',
					symbol: tsFunctionName(node) ?? '<anonym>'
				});
			}
		}
		ts.forEachChild(node, visit);
	};
	visit(sf);
}

/** Position, an der ein Paritaets-Kommentar haengen wuerde: der naechste
 *  deklarationsartige Vorfahre (``const X = [...]``). */
function tsDeclStart(node: ts.Node): number {
	let n: ts.Node | undefined = node;
	while (n && !ts.isVariableStatement(n) && !ts.isExpressionStatement(n) && !ts.isSourceFile(n)) {
		n = n.parent;
	}
	return n ? n.getFullStart() : node.getFullStart();
}

/** Svelte: der echte Compiler bestimmt die Script-Bereiche, alles ausserhalb
 *  wird zeilentreu ausmaskiert -- so bleiben Zeilennummern exakt und der
 *  TS-Parser sieht nur echtes Script. (Template-Ausdruecke bleiben damit
 *  ausserhalb der Reichweite; Stufen-Kataloge stehen im Script-Block.) */
function svelteScriptOnly(source: string): string {
	const ast = svelteParse(source, { modern: true }) as unknown as {
		instance?: { content: { start: number; end: number } };
		module?: { content: { start: number; end: number } };
	};
	const zeichen: string[] = source.split('').map((c) => (c === '\n' ? '\n' : ' '));
	for (const block of [ast.instance, ast.module]) {
		if (!block) continue;
		for (let i = block.content.start; i < block.content.end; i++) zeichen[i] = source[i];
	}
	return zeichen.join('');
}

/** Scannt EINEN Quelltext (TS oder Svelte, je nach `filename`-Endung). */
export function scanThunderScaleCopies(
	source: string,
	filename: string,
	opts: ScanOptions = {}
): Finding[] {
	const order = opts.order ?? canonicalOrder();
	const rules = opts.rules ?? ['A', 'P', 'C'];
	const roh: Finding[] = [];
	let text = source;
	if (filename.endsWith('.svelte')) {
		try {
			text = svelteScriptOnly(source);
		} catch {
			return [];
		}
	}
	scanTsSource(text, filename, order, rules, roh);
	const zeilen = source.split('\n');
	const gesehen = new Set<string>();
	return roh
		.filter((f) => !markerCovers(zeilen, f.line))
		.filter((f) => {
			const key = `${f.line}|${f.rule}|${f.symbol}`;
			if (gesehen.has(key)) return false;
			gesehen.add(key);
			return true;
		})
		.sort((a, b) => a.line - b.line || a.rule.localeCompare(b.rule));
}

const EXCLUDE_DIRS = new Set(['node_modules', '.svelte-kit', 'build', 'dist', '.git']);

function istTestdatei(name: string, voll: string): boolean {
	return name.endsWith('.test.ts') || name.endsWith('.spec.ts') || voll.includes('__tests__');
}

/** Durchsucht alle ``*.ts``/``*.svelte`` unter den Wurzeln rekursiv. Regel
 *  A/P/C laufen auf Produktivcode; Testdateien kommen NUR mit `includeTests`
 *  (dort ist allein Regel D sinnvoll -- eine korrekte Fixture fuehrt
 *  zwangslaeufig alle vier Stufen-Woerter und erzeugte 16 Dauerfeuer-Treffer). */
export function scanThunderScaleTree(roots: string[], opts: ScanOptions = {}): Finding[] {
	const kanonisch = opts.canonicalSymbols ?? CANONICAL_SYMBOLS;
	const funde: Finding[] = [];
	const walk = (dir: string) => {
		for (const eintrag of readdirSync(dir).sort()) {
			if (EXCLUDE_DIRS.has(eintrag)) continue;
			const voll = join(dir, eintrag);
			if (statSync(voll).isDirectory()) {
				walk(voll);
				continue;
			}
			const ext = extname(eintrag);
			if (ext !== '.ts' && ext !== '.svelte') continue;
			if (eintrag.endsWith('.d.ts')) continue;
			const test = istTestdatei(eintrag, voll);
			if (test !== Boolean(opts.includeTests)) continue;
			// SYMBOLscharf filtern statt die Datei zu ueberspringen -- die
			// uebrige Datei bleibt bewacht.
			for (const fund of scanThunderScaleCopies(readFileSync(voll, 'utf-8'), voll, opts)) {
				if (kanonisch.some(([datei, symbol]) => fund.symbol === symbol && istPfad(fund.file, datei))) {
					continue;
				}
				funde.push(fund);
			}
		}
	};
	for (const root of roots) walk(root);
	return funde;
}
