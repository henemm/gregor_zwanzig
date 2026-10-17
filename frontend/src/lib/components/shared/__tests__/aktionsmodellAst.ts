// Pruefstand-Helfer fuer die Aktionsmodell-Tests (#2278): liest .svelte-Dateien mit dem
// ECHTEN Svelte-5-Compiler (parse, modern) und beantwortet Struktur-Fragen am AST statt per
// Text-Grep. Hintergrund: die Kernsuite hat kein DOM (kein jsdom); Dialoge/Menues auf bits-ui
// rendern unter `svelte/server` keinen Inhalt. Was sich deterministisch messen laesst, ist die
// Verdrahtung: WELCHE Bausteine eine Seite einbindet, WOHER die Aktionen kommen, und WELCHE
// Funktionen von einem Klick-Handler aus ERREICHBAR sind (Aufrufgraph im Instanz-Skript).
// Das Durchklicken selbst bewacht Playwright (`aktionsmodell-durchklick.spec.ts`).
//
// Pfadregel #1409: Aufrufer loesen Dateipfade relativ zur EIGENEN Testdatei auf.

import { readFileSync } from 'node:fs';
import { parse } from 'svelte/compiler';

export type Knoten = Record<string, any>;

export function ladeSvelte(pfad: string): Knoten {
	return parse(readFileSync(pfad, 'utf-8'), { modern: true }) as Knoten;
}

export function collect(subtree: unknown, pred: (n: Knoten) => boolean): Knoten[] {
	const found: Knoten[] = [];
	(function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) return void node.forEach(visit);
		const n = node as Knoten;
		if (pred(n)) found.push(n);
		for (const key of Object.keys(n)) if (key !== 'parent') visit(n[key]);
	})(subtree);
	return found;
}

export const ids = (t: unknown): Set<string> =>
	new Set(collect(t, (n) => n.type === 'Identifier' && typeof n.name === 'string').map((n) => n.name as string));

/** String-Literale im JS UND statische Attributtexte im Template (`Text.data`). */
export const literale = (t: unknown): Set<string> =>
	new Set([
		...collect(t, (n) => n.type === 'Literal' && typeof n.value === 'string').map((n) => n.value as string),
		...collect(t, (n) => n.type === 'Text' && typeof n.data === 'string').map((n) => (n.data as string).trim()),
		// Template-Literale (`/trips/${id}?tab=alarme`): die festen Teile zaehlen als Literale.
		...collect(t, (n) => n.type === 'TemplateElement' && typeof n.value?.cooked === 'string').map(
			(n) => n.value.cooked as string
		)
	]);

/** Importquellen (`from '…'`) des Instanz-Skripts mit den importierten Namen. */
export function importe(ast: Knoten): Array<{ quelle: string; namen: string[] }> {
	return collect(ast.instance, (n) => n.type === 'ImportDeclaration').map((n) => ({
		quelle: String(n.source.value),
		namen: (n.specifiers ?? []).map((s: Knoten) => String(s.local?.name ?? ''))
	}));
}

/** Alle Einbettungen einer Komponente im Template (`<Name …>`). */
export const komponenten = (ast: Knoten, name: string): Knoten[] =>
	collect(ast.fragment, (n) => n.type === 'Component' && n.name === name);

export const attribut = (einbettung: Knoten, name: string): Knoten | undefined =>
	(einbettung.attributes ?? []).find((a: Knoten) => a.name === name);

/** name -> Rumpf/Initialisierer der Top-Level-Deklarationen des Instanz-Skripts. */
export function lokaleBindungen(ast: Knoten): Map<string, Knoten> {
	const map = new Map<string, Knoten>();
	for (const n of (ast.instance?.content?.body ?? []) as Knoten[]) {
		if (n.type === 'VariableDeclaration') {
			for (const d of n.declarations) if (d.id?.type === 'Identifier' && d.init) map.set(d.id.name, d.init);
		} else if (n.type === 'FunctionDeclaration' && n.id?.name) {
			map.set(n.id.name, n.body);
		}
	}
	return map;
}

/**
 * Transitive Huelle: ab den Startbezeichnern alle lokal deklarierten Funktionen/Werte, die ueber
 * Namensverweise erreichbar sind. Rueckgabe: erreichte Namen, alle Bezeichner und alle
 * String-Literale im erreichten Code (inkl. des Startausdrucks).
 */
export function erreichbar(
	ast: Knoten,
	start: unknown,
	tiefe = 6
): { namen: Set<string>; bezeichner: Set<string>; literale: Set<string>; knoten: Knoten[] } {
	const binds = lokaleBindungen(ast);
	const namen = new Set<string>();
	const knoten: Knoten[] = [start as Knoten];
	let front = ids(start);
	for (let i = 0; i < tiefe; i++) {
		const neu = new Set<string>();
		for (const n of front) {
			if (namen.has(n) || !binds.has(n)) continue;
			namen.add(n);
			const k = binds.get(n)!;
			knoten.push(k);
			for (const x of ids(k)) neu.add(x);
		}
		if (neu.size === 0) break;
		front = neu;
	}
	const bezeichner = new Set<string>();
	const lits = new Set<string>();
	for (const k of knoten) {
		for (const x of ids(k)) bezeichner.add(x);
		for (const x of literale(k)) lits.add(x);
	}
	return { namen, bezeichner, literale: lits, knoten };
}
