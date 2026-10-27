// Issue #2276 Scheibe S5 (Epic #2345), AC-7 (Verdrahtungs-Teil): pausiert oder
// aktiviert der Nutzer den Ortsvergleich, während eine Änderung eines selbst
// speichernden Reiters noch im Entprell-Fenster wartet, muss sie VOR dem
// Pausier-PUT gesendet werden. Zuständig dafür ist der generische
// `saveController?.flush()` am Anfang von `handleToggleActive`
// (CompareTabs.svelte) — seit S5 trägt er auch den Versand-Reiter, weil der
// über `schedule()` speichert statt über den entfallenen Wrapper-Div.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-7
//
// WARUM AST (Adversary-Befund F002): `handleToggleActive` lebt in einer
// `.svelte`-Datei und ist im SSR-only-Harness (`node --test` +
// `svelte/server`, kein DOM) nicht ausführbar.
// shared/__tests__/versand_vergleich_flush_vor_pausieren.test.ts stellt die
// Abfolge mit den echten Bausteinen NACH und beweist, dass sie trägt — dass
// die Komponente sie auch so aufruft, blieb ungeprüft. Statt eines nach
// CLAUDE.md verbotenen Dateiinhalt-Greps parst dieser Test mit dem ECHTEN
// Svelte-5-Compiler und inspiziert den Instance-Script-AST; Muster
// shared/__tests__/versand_tab_meldet_aenderungen_reaktiv.test.ts bzw.
// versand_panel_ohne_wrapper_div.test.ts.
//
// Geprüft wird nicht nur DASS geflusht wird, sondern auch die REIHENFOLGE:
// ein Flush nach dem eigenen PUT käme zu spät — der Pausier-PUT trüge dann
// den alten Stand und die wartende Änderung ginge verloren.
//
// Den echten Klickpfad misst frontend/e2e/compare-versand-speichert-selbst.spec.ts (AC-7).
//
// Mutations-Gegenproben (Spec AC-7):
//   - `await saveController?.flush();` löschen ⇒ rot.
//   - denselben Aufruf hinter den Pausier-PUT verschieben ⇒ rot.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/compare/__tests__/compare_hub_pausieren_flusht_vorher.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const HUB = join(here, '..', 'CompareTabs.svelte');

/** Instance-Script (`<script lang="ts">`) als ESTree-Programm. */
function instanceAst(file: string): unknown {
	const ast = parse(readFileSync(file, 'utf-8'), { modern: true }) as unknown as {
		instance?: { content: unknown };
	};
	assert.ok(ast.instance, 'Vorbedingung: CompareTabs.svelte muss ein Instance-Script haben');
	return ast.instance.content;
}

function sammle(subtree: unknown, treffer: (n: Record<string, any>) => boolean): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (treffer(n)) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Der Funktionskörper von `handleToggleActive`. */
function handleToggleActive(programm: unknown): any {
	const treffer = sammle(
		programm,
		(n) => n.type === 'FunctionDeclaration' && n.id?.name === 'handleToggleActive'
	);
	assert.equal(
		treffer.length,
		1,
		'Vorbedingung: CompareTabs.svelte muss genau eine handleToggleActive-Funktion haben (Pausieren/Aktivieren, auch fuer den Header-Kebab)'
	);
	return treffer[0];
}

/** Aufrufe `<objekt>.<methode>()` im Teilbaum (auch optional: `a?.b()`). */
function methodenAufrufe(subtree: unknown, objekt: string, methode: string): any[] {
	return sammle(
		subtree,
		(n) =>
			n.type === 'CallExpression' &&
			n.callee?.type === 'MemberExpression' &&
			n.callee.object?.type === 'Identifier' &&
			n.callee.object.name === objekt &&
			n.callee.property?.type === 'Identifier' &&
			n.callee.property.name === methode
	);
}

describe('AC-7: Pausieren/Aktivieren sendet eine wartende Reiter-Aenderung vorher', () => {
	test('handleToggleActive ruft saveController.flush()', () => {
		const fn = handleToggleActive(instanceAst(HUB));
		const flushs = methodenAufrufe(fn, 'saveController', 'flush');

		assert.equal(
			flushs.length,
			1,
			'ohne den generischen Flush bleibt die im Entprell-Fenster wartende Aenderung (Versand, Alarme, Wertebereiche, Wetter-Metriken) liegen und der Pausier-PUT ueberschreibt sie'
		);
	});

	test('der Flush wird abgewartet — ein nicht abgewarteter Flush ist ein Race', () => {
		const fn = handleToggleActive(instanceAst(HUB));
		const flush = methodenAufrufe(fn, 'saveController', 'flush')[0];
		const awaits = sammle(fn, (n) => n.type === 'AwaitExpression');

		assert.ok(
			awaits.some((a) => a.argument?.start === flush.start || a.argument?.argument?.start === flush.start),
			'der Flush muss awaited werden, sonst laeuft der Pausier-PUT los, bevor die wartende Aenderung durch ist'
		);
	});

	test('der Flush steht VOR dem Pausier-PUT, nicht danach', () => {
		const fn = handleToggleActive(instanceAst(HUB));
		const flush = methodenAufrufe(fn, 'saveController', 'flush')[0];
		// Der Pausier-PUT laeuft durch die Hub-Queue; der Payload entsteht drin.
		const putWege = [
			...methodenAufrufe(fn, 'hubPutQueue', 'enqueue'),
			...methodenAufrufe(fn, 'api', 'put')
		];
		assert.ok(putWege.length > 0, 'Vorbedingung: handleToggleActive muss einen PUT ausloesen');

		const fruehesterPut = Math.min(...putWege.map((p) => p.start as number));
		assert.ok(
			(flush.start as number) < fruehesterPut,
			`der Flush muss VOR dem Pausier-PUT laufen — steht er dahinter, traegt der PUT den alten Stand (Flush bei ${flush.start}, erster PUT bei ${fruehesterPut})`
		);
	});
});
