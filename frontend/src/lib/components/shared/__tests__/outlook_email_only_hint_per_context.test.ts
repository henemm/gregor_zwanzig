// TDD RED — Issue #1720 Scheibe 2, AC-6.
//
// Spec: docs/specs/modules/feat_1720_s2_ausblick_kompakt_telegram.md
//   § Implementation Details 5, AC-6, Mutations-Gegenprobe 7
//
// Der Abschnitt „3-Tages-Vorschau" traegt heute in BEIDEN Kontexten den
// Hinweis „Erscheint nur in der E-Mail". Nach dieser Scheibe wirkt die Auswahl
// im TRIP in allen vier Ausgabeorten — der Hinweis waere dort falsch. Im
// ORTSVERGLEICH bleibt er richtig (der Compare-Ausblick existiert weiterhin
// nur in `render_compare_email()`).
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom
// (package.json "test": node --test). Geprueft wird mit dem ECHTEN
// Svelte-5-Compiler am Template-/Instance-AST — kein Dateiinhalt-Vergleich.
//
// Ausfuehrung: cd frontend && npm test -- <diese Datei>

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const CONTROLS = join(here, '..', 'CompareOutlookLayoutControls.svelte');
const TAB = join(here, '..', 'WeatherMetricsTab.svelte');

const HINT_TESTID = 'compare-layout-outlook-email-only-hint';
const PROP = 'showEmailOnlyHint';
const TRIP_TITLE = '3-Tages-Vorschau';

function parseComponent(path: string): any {
	return parse(readFileSync(path, 'utf-8'), { modern: true });
}

function walk(subtree: unknown, visitor: (n: Record<string, any>) => void): void {
	if (subtree === null || typeof subtree !== 'object') return;
	if (Array.isArray(subtree)) {
		subtree.forEach((child) => walk(child, visitor));
		return;
	}
	const n = subtree as Record<string, any>;
	visitor(n);
	for (const key of Object.keys(n)) {
		if (key === 'parent') continue;
		walk(n[key], visitor);
	}
}

function findComponentsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	walk(subtree, (n) => {
		if (n.type === 'Component' && n.name === name) found.push(n);
	});
	return found;
}

function findAttr(node: any, name: string): any {
	return (node?.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === name);
}

/** Statischer Text eines Attributwerts (`title="…"`) oder undefined. */
function staticAttrText(node: any, name: string): string | undefined {
	const attr = findAttr(node, name);
	if (!attr) return undefined;
	const value = Array.isArray(attr.value) ? attr.value[0] : attr.value;
	return value?.type === 'Text' ? value.data : undefined;
}

/** Der `{#if}`-Block, in dessen Rumpf das Element mit `data-testid` steht. */
function ifBlockRenderingTestid(fragment: unknown, testid: string): any {
	let treffer: any;
	walk(fragment, (n) => {
		if (n.type !== 'IfBlock') return;
		let enthalten = false;
		walk(n.consequent, (inner) => {
			if (inner.type !== 'Attribute' || inner.name !== 'data-testid') return;
			const value = Array.isArray(inner.value) ? inner.value[0] : inner.value;
			if (value?.type === 'Text' && value.data === testid) enthalten = true;
		});
		// Der INNERSTE passende Block gewinnt: er traegt die eigentliche Bedingung.
		if (enthalten) treffer = n;
	});
	return treffer;
}

function identifiersIn(node: unknown): string[] {
	const namen: string[] = [];
	walk(node, (n) => {
		if (n.type === 'Identifier' && typeof n.name === 'string') namen.push(n.name);
	});
	return namen;
}

describe('#1720 S2 AC-6 — der E-Mail-only-Hinweis haengt am Kontext', () => {
	test('Gegeben der geteilte Baustein, dann kennt er die optionale Prop showEmailOnlyHint mit Vorgabe true', () => {
		const ast = parseComponent(CONTROLS);
		let vorgabe: unknown;
		let gefunden = false;
		walk(ast.instance?.content, (n) => {
			if (n.type !== 'Property') return;
			if (n.key?.type !== 'Identifier' || n.key.name !== PROP) return;
			gefunden = true;
			if (n.value?.type === 'AssignmentPattern') vorgabe = n.value.right?.value;
		});
		assert.ok(
			gefunden,
			`AC-6 FAIL: CompareOutlookLayoutControls.svelte kennt die Prop \`${PROP}\` nicht — ` +
				'ohne sie kann der Trip-Kontext den Hinweis nicht abschalten, ohne den ' +
				'Ortsvergleich mitzureissen (Spec Implementation Details 5).'
		);
		assert.equal(
			vorgabe,
			true,
			`AC-6 FAIL: \`${PROP}\` hat nicht die Vorgabe \`true\` — nur mit ihr bleibt die ` +
				'Compare-Einbindung ohne eigene Uebergabe unveraendert.'
		);
	});

	test('Gegeben der Hinweis-Block, dann steht er unter der Bedingung showEmailOnlyHint', () => {
		const ast = parseComponent(CONTROLS);
		const block = ifBlockRenderingTestid(ast.fragment, HINT_TESTID);
		assert.ok(
			block,
			`REGRESSION: kein {#if}-Block rendert data-testid="${HINT_TESTID}" — ` +
				'der Hinweis ist ganz verschwunden statt kontextabhaengig zu werden.'
		);
		assert.ok(
			identifiersIn(block.test).includes(PROP),
			`AC-6 FAIL: die Bedingung des Hinweis-Blocks nennt \`${PROP}\` nicht — ` +
				'der Hinweis erscheint damit in JEDEM Kontext, auch im Trip.'
		);
	});

	test('Gegeben die Trip-Einbindung, dann schaltet sie den Hinweis mit showEmailOnlyHint={false} ab', () => {
		const ast = parseComponent(TAB);
		const mounts = findComponentsNamed(ast.fragment, 'CompareOutlookLayoutControls');
		assert.equal(
			mounts.length,
			2,
			`REGRESSION: erwartet genau zwei Einbindungen (Trip + Vergleich), gefunden ${mounts.length}.`
		);
		const trip = mounts.find((m) => staticAttrText(m, 'title') === TRIP_TITLE);
		assert.ok(
			trip,
			`REGRESSION: keine Einbindung mit title="${TRIP_TITLE}" — an ihr haengt die ` +
				'Unterscheidung Trip/Vergleich in dieser Datei.'
		);
		const attr = findAttr(trip, PROP);
		assert.ok(
			attr,
			`AC-6 FAIL (Mutation 7): die Trip-Einbindung uebergibt \`${PROP}\` nicht — ` +
				'die Vorgabe `true` bleibt wirksam und der Hinweis erscheint im Trip, ' +
				'obwohl die Auswahl dort jetzt in allen vier Kanaelen wirkt.'
		);
		const value = Array.isArray(attr.value) ? attr.value[0] : attr.value;
		assert.equal(
			value?.expression?.value,
			false,
			`AC-6 FAIL: die Trip-Einbindung uebergibt \`${PROP}\` nicht als \`false\`.`
		);
	});

	test('Gegeben die Ortsvergleich-Einbindung, dann laesst sie die Vorgabe unangetastet', () => {
		const ast = parseComponent(TAB);
		const mounts = findComponentsNamed(ast.fragment, 'CompareOutlookLayoutControls');
		const vergleich = mounts.filter((m) => staticAttrText(m, 'title') !== TRIP_TITLE);
		assert.equal(
			vergleich.length,
			1,
			`REGRESSION: erwartet genau eine Vergleichs-Einbindung, gefunden ${vergleich.length}.`
		);
		assert.equal(
			findAttr(vergleich[0], PROP),
			undefined,
			`AC-6 FAIL: die Ortsvergleich-Einbindung uebergibt \`${PROP}\` — der Compare-` +
				'Ausblick erscheint weiterhin ausschliesslich in der E-Mail, der Hinweis ' +
				'ist dort richtig und muss unveraendert stehen bleiben.'
		);
	});
});
