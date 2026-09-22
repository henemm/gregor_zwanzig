// Issue #2276 Scheibe S5 (Epic #2345), AC-1 + AC-5 (Verdrahtungs-Teil): der
// Versand-Reiter meldet seine Änderungen REAKTIV — über einen `$effect`, der
// alle 10 Versandfelder liest und bei einem Unterschied `aenderungMelden()`
// ruft. Er ersetzt damit den entfallenen Wrapper-Div samt seiner drei
// Sammel-Ereignisse, insbesondere das `onclick` für „Bis auf Weiteres"
// (VTLaufzeitVergleich mutiert `wiz.endDate` per reinem Button-Klick, ohne
// change-/focusout-Ereignis — Fix-Loop 1 / F001).
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-1, AC-5
//
// WARUM AST statt Ausführung des Effekts: der Frontend-Harness ist SSR-only
// (`node --test` + `svelte/server`, test-svelte-ssr-hooks.mjs kompiliert mit
// `generate: 'server'`). Es gibt kein DOM-Paket und keine Client-Kompilierung,
// ein `$effect` läuft dort NIE. Ohne diesen Test bliebe der Effekt komplett
// ungewacht: seine ersatzlose Löschung ließ die gesamte S5-Testreihe grün
// (gemessene Mutations-Gegenprobe) — die Zusicherung wäre nur dort geprüft, wo
// der Code steht, nicht dort, wo er wirkt. Statt eines nach CLAUDE.md
// verbotenen Dateiinhalt-Greps parst dieser Test mit dem ECHTEN
// Svelte-5-Compiler und inspiziert den Instance-Script-AST — Muster
// compare/__tests__/versand_panel_ohne_wrapper_div.test.ts.
//
// Was er NICHT leisten kann: den Klickpfad im Browser. Den misst
// frontend/e2e/compare-versand-speichert-selbst.spec.ts (AC-1, AC-5).
//
// Mutations-Gegenproben (Spec AC-1/AC-5):
//   - `$effect`-Block ersatzlos löschen ⇒ rot (nichts meldet mehr).
//   - `untrack()`-Erzeugung der Orchestrierung löschen ⇒ rot.
//   - `versandSnapshotAus(wiz)` im Effekt durch eine engere Leseliste ohne
//     `endDate` ersetzen ⇒ rot (die Lesequelle aller 10 Felder fehlt).
//   - den Lesezugriff in `untrack(...)` einschließen ⇒ rot (dann entstünde
//     keine Abhängigkeit, der Effekt liefe nie wieder).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_tab_meldet_aenderungen_reaktiv.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const VERSAND_TAB = join(here, '..', 'VersandTab.svelte');

/** Instance-Script (`<script lang="ts">`) als ESTree-Programm. */
function instanceAst(file: string): unknown {
	const ast = parse(readFileSync(file, 'utf-8'), { modern: true }) as unknown as {
		instance?: { content: unknown };
	};
	assert.ok(ast.instance, 'Vorbedingung: VersandTab.svelte muss ein Instance-Script haben');
	return ast.instance.content;
}

/** Alle `CallExpression`-Knoten mit `callee.name === name` im Teilbaum. */
function findeAufrufe(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'CallExpression' && n.callee?.type === 'Identifier' && n.callee.name === name) {
			found.push(n);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Alle Aufrufe einer Methode `obj.<name>()` im Teilbaum. */
function findeMethodenAufrufe(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (
			n.type === 'CallExpression' &&
			n.callee?.type === 'MemberExpression' &&
			n.callee.property?.type === 'Identifier' &&
			n.callee.property.name === name
		) {
			found.push(n);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Der EINE `$effect`, der die Versand-Speicherung meldet. */
function meldenderEffect(programm: unknown): any {
	const treffer = findeAufrufe(programm, '$effect').filter(
		(e) => findeMethodenAufrufe(e, 'aenderungMelden').length > 0
	);
	assert.equal(
		treffer.length,
		1,
		'genau EIN reaktiver $effect muss die Versand-Änderungen melden — ohne ihn ersetzt nichts den entfallenen Wrapper-Div'
	);
	return treffer[0];
}

describe('AC-1/AC-5: VersandTab meldet Versand-Änderungen über einen reaktiven $effect', () => {
	test('ein $effect ruft aenderungMelden() — der Wrapper-Div hat keinen Ersatz-Auslöser mehr', () => {
		meldenderEffect(instanceAst(VERSAND_TAB));
	});

	test('der Effekt liest den vollständigen Versandstand über versandSnapshotAus(versandZustand)', () => {
		const effect = meldenderEffect(instanceAst(VERSAND_TAB));
		const lesungen = findeAufrufe(effect, 'versandSnapshotAus');

		assert.equal(
			lesungen.length,
			1,
			'der Effekt muss GENAU EINE Lesequelle haben: versandSnapshotAus(versandZustand) liest alle 10 Versandfelder — eine engere Leseliste ließe „Bis auf Weiteres" (endDate) wieder unsichtbar werden (AC-5)'
		);
		assert.equal(
			lesungen[0].arguments[0]?.name,
			// Issue #2276 S6e: seit dem Wertprop-Umbau ist die Lesequelle die
			// Bruecke `versandZustand` (Proxy ueber die zehn Wertprops), nicht mehr
			// der Wizard-Zustand `wiz`. Die Zusicherung bleibt dieselbe: gelesen
			// wird die LEBENDE Quelle, nie eine eingefrorene Kopie.
			'versandZustand',
			'gelesen werden muss der lebende Versandstand des Ortsvergleichs, nicht eine eingefrorene Kopie'
		);
	});

	test('der Lesezugriff steht AUSSERHALB von untrack() — sonst entsteht keine Abhängigkeit', () => {
		const effect = meldenderEffect(instanceAst(VERSAND_TAB));
		const untrackAufrufe = findeAufrufe(effect, 'untrack');
		const gelesenInUntrack = untrackAufrufe.some(
			(u) => findeAufrufe(u, 'versandSnapshotAus').length > 0
		);

		assert.equal(
			gelesenInUntrack,
			false,
			'in untrack() gelesene Felder werden nicht beobachtet — der Effekt liefe nach dem ersten Lauf nie wieder, keine Änderung würde je gemeldet'
		);
		assert.ok(
			untrackAufrufe.some((u) => findeMethodenAufrufe(u, 'aenderungMelden').length > 0),
			'das Melden selbst gehört in untrack(), damit Zustandswechsel des Speicher-Controllers keinen Neulauf auslösen'
		);
	});

	test('die Orchestrierung entsteht nur unter der geprüften Aktivierungsbedingung', () => {
		const programm = instanceAst(VERSAND_TAB);
		const erzeugungen = findeAufrufe(programm, 'erstelleVersandVergleichSpeicherung');
		assert.equal(erzeugungen.length, 1, 'genau eine Erzeugung der Versand-Orchestrierung erwartet');

		const untrackAufrufe = findeAufrufe(programm, 'untrack').filter(
			(u) => findeAufrufe(u, 'erstelleVersandVergleichSpeicherung').length > 0
		);
		assert.equal(
			untrackAufrufe.length,
			1,
			'die Erzeugung muss in untrack() laufen (Muster AlarmeTab/WeatherMetricsTab) — sonst hinge die Baseline an beobachteten Feldern'
		);
		assert.ok(
			findeAufrufe(untrackAufrufe[0], 'versandVergleichSpeicherungAktiv').length === 1,
			'die Erzeugung muss an versandVergleichSpeicherungAktiv(...) hängen — ohne Kontext-Prüfung speicherten Anlege-Seite (AC-9) und Trip-Zweig (AC-12) mit'
		);
	});
});
