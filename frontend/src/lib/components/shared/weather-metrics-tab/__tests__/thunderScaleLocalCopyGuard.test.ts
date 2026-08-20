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
// der Fundstelle laesst den Fund durch.
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
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

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
