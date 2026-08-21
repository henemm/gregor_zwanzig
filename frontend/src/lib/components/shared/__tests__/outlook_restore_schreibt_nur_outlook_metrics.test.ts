// #1848 A3, AC-9 — Unit auf dem SPEICHERWEG.
//
// Spec: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md
//   AC-9: "Given der Nutzer holt eine Groesse ueber 'Ein' zurueck / When
//   danach die Grundauswahl betrachtet wird / Then ist sie dort unveraendert
//   — Zurueckholen schreibt ausschliesslich in `outlook_metrics`, nie in die
//   Grundauswahl.  Test: Unit auf dem Speicherweg + E2E-Ablesen der
//   Grundauswahl."
//
// Das E2E-Ablesen liegt in ausblick-erbt-grundauswahl.staging.spec.ts (AC-9).
// DIESE Datei liefert die zweite, von der Spec ausdruecklich verlangte
// Haelfte: den Speicherweg, ohne DOM und ohne Staging.
//
// 🔴 Warum das nicht dasselbe ist wie der E2E-Test: der Staging-Lauf liest
// die Grundauswahl NACH einem Neuladen ab und kann deshalb nur sagen "sie
// sieht noch gleich aus". Er kann nicht sagen, ob der Umschaltweg die
// geerbte Liste UNTERWEGS angefasst hat. Genau das ist hier die Gefahr: seit
// A3 ist `materializedOutlookKeys` bei `metricKeys === null` inhaltlich die
// GRUNDAUSWAHL selbst (`splitChannelMetricsForDisplay(grund, grund).active`).
// Eine In-place-Mutation im Umschaltweg wuerde damit die Grundauswahl des
// Aufrufers beschaedigen — ein Fehler, der im DOM erst Klicks spaeter oder
// gar erst nach dem naechsten Speichern auffaellt.
//
// Grenze, ausdruecklich: geprueft wird der Speicherweg (die reinen
// Funktionen, aus denen `toggleOutlookKey()` besteht) und die Verdrahtung
// des Rueckhol-Knopfes im Instance-Script. NICHT geprueft wird, ob der
// Aufrufer die gemeldete Liste danach richtig persistiert — das ist der
// E2E-Teil.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/outlook_restore_schreibt_nur_outlook_metrics.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { toggleCompareMetricKey } from '../weather-metrics-tab/compareMetricOrder.ts';
import { splitChannelMetricsForDisplay } from '../weather-metrics-tab/channelMetricLayouts.ts';

const here = dirname(fileURLToPath(import.meta.url));
const OUTLOOK_COMPONENT = join(here, '..', 'CompareOutlookLayoutControls.svelte');

/** Die Grundauswahl einer Flaeche, wie sie als Prop hereinkommt. */
const GRUNDAUSWAHL = ['temperature', 'precipitation', 'wind', 'gust', 'thunder'];

function instanceBody(ast: any): any[] {
	return (ast?.instance?.content?.body as any[]) ?? [];
}

function walk(node: unknown, visit: (n: Record<string, any>) => void): void {
	if (node === null || typeof node !== 'object') return;
	if (Array.isArray(node)) {
		node.forEach((n) => walk(n, visit));
		return;
	}
	const n = node as Record<string, any>;
	visit(n);
	for (const key of Object.keys(n)) {
		if (key === 'parent' || key === 'loc') continue;
		walk(n[key], visit);
	}
}

/** Der Rumpf einer benannten Funktionsdeklaration im Instance-Script. */
function funktionsRumpf(ast: any, name: string): any | null {
	for (const stmt of instanceBody(ast)) {
		if (stmt.type === 'FunctionDeclaration' && stmt.id?.name === name) return stmt.body;
	}
	return null;
}

/** Alle Bezeichner, die im Subtree AUFGERUFEN werden. */
function aufgerufeneNamen(subtree: unknown): Set<string> {
	const namen = new Set<string>();
	walk(subtree, (n) => {
		if (n.type === 'CallExpression') {
			if (n.callee?.type === 'Identifier') namen.add(n.callee.name);
			// `onOutlookCommit?.()` ist eine ChainExpression um den Aufruf.
			if (n.callee?.type === 'MemberExpression' && n.callee.object?.type === 'Identifier') {
				namen.add(n.callee.object.name);
			}
		}
	});
	return namen;
}

// ═══════════════════════════════════════════════════════════════════════════
// Teil 1 — der Speicherweg selbst: Zurueckholen fasst die Grundauswahl nicht an
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-9 [#1848 A3]: Zurueckholen schreibt ausschliesslich in outlook_metrics', () => {
	test('der Umschaltweg liefert eine NEUE Liste und laesst die Grundauswahl Zeichen fuer Zeichen unberuehrt', () => {
		// Ausgangslage wie im Editor: "Wind" ist im Ausblick abgewaehlt, alles
		// andere der Grundauswahl ist aktiv.
		const grundauswahl = [...GRUNDAUSWAHL];
		const vorher = JSON.stringify(grundauswahl);
		const gespeicherteAuswahl = grundauswahl.filter((id) => id !== 'wind');

		const { active, off } = splitChannelMetricsForDisplay(grundauswahl, gespeicherteAuswahl);
		assert.deepEqual(off, ['wind'], 'Vorbedingung: "Wind" steht in der Aus-Gruppe');

		// Der Rueckhol-Weg der Komponente: toggleCompareMetricKey(active, key).
		const neueAuswahl = toggleCompareMetricKey(active, 'wind');

		assert.deepEqual(
			neueAuswahl,
			['temperature', 'precipitation', 'gust', 'thunder', 'wind'],
			'AC-9: "Wind" muss zurueckkommen und ans ENDE ruecken (#1359 AC-2)'
		);
		assert.equal(
			JSON.stringify(grundauswahl),
			vorher,
			'AC-9 FAIL: der Rueckhol-Weg hat die GRUNDAUSWAHL veraendert — sie darf ' +
				'ausschliesslich gelesen werden. Seit A3 ist die aktive Ausblick-Liste bei ' +
				'"nie eingestellt" inhaltlich die Grundauswahl selbst; eine In-place-Mutation ' +
				'im Umschaltweg beschaedigt damit die Auswahl der ganzen Flaeche.'
		);
		assert.notEqual(
			neueAuswahl,
			active,
			'AC-9 FAIL: es wurde dieselbe Array-Instanz zurueckgegeben — der Aufrufer haelt ' +
				'dann keine unterscheidbare "vorher/nachher"-Fassung mehr in der Hand.'
		);
	});

	test('auch der "nie eingestellt"-Fall (Auswahl IST die Grundauswahl) laesst sie unberuehrt', () => {
		// Der scharfe Fall: `metricKeys === null` -> die Komponente rechnet
		// `splitChannelMetricsForDisplay(grund, grund)`, `active` ist dann
		// inhaltsgleich zur Grundauswahl. Waehlt der Nutzer hier ab, darf das
		// die Grundauswahl nicht mitnehmen.
		const grundauswahl = [...GRUNDAUSWAHL];
		const vorher = JSON.stringify(grundauswahl);

		const { active, off } = splitChannelMetricsForDisplay(grundauswahl, grundauswahl);
		assert.deepEqual(active, grundauswahl, 'Vorbedingung: alles aktiv, nichts aus');
		assert.deepEqual(off, [], 'Vorbedingung: die Aus-Gruppe ist leer');

		const nachAbwahl = toggleCompareMetricKey(active, 'thunder');

		assert.ok(
			!nachAbwahl.includes('thunder'),
			'Vorbedingung: "Gewitter" ist nach der Abwahl draussen'
		);
		assert.equal(
			JSON.stringify(grundauswahl),
			vorher,
			'AC-9 FAIL: die Abwahl im Ausblick hat die Grundauswahl mitgenommen — genau der ' +
				'Durchschreibe-Fehler, den ADR-0050 Regel 2 ausschliesst.'
		);
		assert.ok(
			grundauswahl.includes('thunder'),
			'AC-9 FAIL: "Gewitter" fehlt jetzt in der Grundauswahl.'
		);
	});

	test('Vakuum-Schutz: splitChannelMetricsForDisplay gibt die Grundauswahl nicht als dieselbe Instanz zurueck', () => {
		// Ohne diese Zusicherung koennten die beiden Tests oben gruen bleiben,
		// obwohl `active` und `grundauswahl` dasselbe Array SIND — dann haette
		// `toggleCompareMetricKey` gar keine Gelegenheit, die Grundauswahl zu
		// treffen, und die Zusicherung waere trivial erfuellt.
		const grundauswahl = [...GRUNDAUSWAHL];
		const { active, off } = splitChannelMetricsForDisplay(grundauswahl, grundauswahl);
		assert.notEqual(active, grundauswahl, '`active` ist dieselbe Instanz wie die Grundauswahl');
		assert.notEqual(off, grundauswahl, '`off` ist dieselbe Instanz wie die Grundauswahl');
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// Teil 2 — die Verdrahtung: der Rueckhol-Knopf meldet NUR outlook_metrics
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-9 [#1848 A3]: der Rueckhol-Knopf meldet ausschliesslich die Ausblick-Auswahl nach oben', () => {
	test('`onOutlookRestore` ruft nichts ausser dem Ausblick-Umschaltweg', () => {
		// Die Komponente kennt genau EINEN Weg nach oben, der schreibt:
		// `onMetricKeys` (die Ausblick-Auswahl). Ein Aufruf, der daneben eine
		// Grundauswahl-Prop bediente, waere hier sichtbar — und genau das ist
		// der Fehler, den AC-9 ausschliesst.
		const src = readFileSync(OUTLOOK_COMPONENT, 'utf-8');
		const ast = parse(src, { modern: true });

		const restoreRumpf = funktionsRumpf(ast, 'onOutlookRestore');
		assert.ok(
			restoreRumpf,
			'AC-9 FAIL: keine Funktion `onOutlookRestore` im Instance-Script — der ' +
				'Rueckhol-Knopf haengt an etwas anderem, dieser Test waere blind.'
		);

		// `onOutlookRestore` delegiert an den gemeinsamen Umschaltweg; geprueft
		// wird die Vereinigung beider Rumpfe.
		const toggleRumpf = funktionsRumpf(ast, 'toggleOutlookKey');
		assert.ok(toggleRumpf, 'AC-9 FAIL: kein gemeinsamer Umschaltweg `toggleOutlookKey`.');

		const gerufen = new Set([
			...aufgerufeneNamen(restoreRumpf),
			...aufgerufeneNamen(toggleRumpf)
		]);
		const erlaubt = new Set(['onMetricKeys', 'toggleCompareMetricKey', 'onOutlookCommit', 'toggleOutlookKey']);
		const unerlaubt = [...gerufen].filter((n) => !erlaubt.has(n));
		assert.deepEqual(
			unerlaubt,
			[],
			`AC-9 FAIL: der Rueckhol-Weg ruft ${JSON.stringify(unerlaubt)} — erlaubt ist nur ` +
				'das Melden der AUSBLICK-Auswahl (`onMetricKeys`) und der Speicherausloeser. ' +
				'Jeder weitere Callback koennte in die Grundauswahl schreiben.'
		);
		assert.ok(
			gerufen.has('onMetricKeys'),
			'AC-9 FAIL: der Rueckhol-Weg meldet gar keine neue Ausblick-Auswahl nach oben — ' +
				'die Abwesenheits-Pruefung oben waere damit trivial erfuellt.'
		);
	});

	test('die Komponente nimmt die Grundauswahl entgegen, ohne einen Schreibweg dafuer zu haben', () => {
		// Gegenstueck zur Zusicherung oben: `grundauswahl` ist eine reine
		// Lese-Prop. Gaebe es daneben ein `onGrundauswahl`-artiges Callback,
		// koennte der Ausblick sehr wohl dorthin schreiben — dann waere AC-9
		// eine Frage der Disziplin statt der Bauart.
		const src = readFileSync(OUTLOOK_COMPONENT, 'utf-8');
		const ast = parse(src, { modern: true });

		const propsDecl = instanceBody(ast).find(
			(stmt) =>
				stmt.type === 'VariableDeclaration' &&
				stmt.declarations?.[0]?.id?.type === 'ObjectPattern'
		);
		assert.ok(propsDecl, 'keine `let { ... } = $props()`-Destrukturierung gefunden');
		const propNamen = (propsDecl.declarations[0].id.properties ?? []).map(
			(p: any) => p.key?.name ?? p.argument?.name
		);
		assert.ok(
			propNamen.includes('grundauswahl'),
			`AC-9 FAIL: die Komponente nimmt gar keine \`grundauswahl\` entgegen: ${JSON.stringify(propNamen)}`
		);
		const schreibwege = propNamen.filter(
			(n: string) => typeof n === 'string' && /^on/.test(n) && /grund|active|metrics$/i.test(n)
		);
		assert.deepEqual(
			schreibwege.filter((n: string) => n !== 'onMetricKeys'),
			[],
			`AC-9 FAIL: es existiert ein Schreibweg neben \`onMetricKeys\`: ${JSON.stringify(schreibwege)}`
		);
	});
});
