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

const istLiteral = (t: Knoten | undefined, wert: boolean): boolean => t?.type === 'Literal' && t.value === wert;
const BEDINGT = new Set(['IfBlock', 'IfStatement', 'ConditionalExpression']);

/**
 * Kinder eines Knotens, die ERREICHBAR sind (Fix-Loop 2, F019): der Zweig hinter einer Bedingung
 * `false` bzw. der else-Zweig hinter `true` und Anweisungen nach einem unbedingten return/throw
 * gelten als tot und werden nie gesammelt — sonst „findet" ein Test Code, der nie laeuft.
 */
function lebendeKinder(n: Knoten): Array<[string, unknown]> {
	return Object.keys(n)
		.filter((key) => key !== 'parent')
		.filter((key) => {
			if (!BEDINGT.has(n.type)) return true;
			if (key === 'consequent' && istLiteral(n.test, false)) return false;
			if (key === 'alternate' && istLiteral(n.test, true)) return false;
			return true;
		})
		.map((key): [string, unknown] => {
			const wert = n[key];
			if ((n.type === 'BlockStatement' || n.type === 'Program') && key === 'body' && Array.isArray(wert)) {
				const ende = wert.findIndex((s: Knoten) => s?.type === 'ReturnStatement' || s?.type === 'ThrowStatement');
				return [key, ende < 0 ? wert : wert.slice(0, ende + 1)];
			}
			return [key, wert];
		});
}

export function collect(subtree: unknown, pred: (n: Knoten) => boolean): Knoten[] {
	const found: Knoten[] = [];
	(function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) return void node.forEach(visit);
		const n = node as Knoten;
		if (pred(n)) found.push(n);
		for (const [, kind] of lebendeKinder(n)) visit(kind);
	})(subtree);
	return found;
}

/**
 * Bedingungen, unter denen `ziel` steht (aeusserste zuerst), als Kurzschrift: `{#if t}` -> `t`,
 * `{:else}` -> `!(t)`, ebenso if-Anweisung und `a ? b : c`; `a && ziel` -> `a`. `null`, wenn `ziel`
 * unterhalb von `wurzel` nicht (erreichbar) vorkommt. Tests verlangen damit nicht nur DASS die
 * Bindung im Code steht, sondern unter WELCHER Bedingung sie wirkt (`[]` = unbedingt).
 */
export function bedingungen(wurzel: unknown, ziel: Knoten): string[] | null {
	let ergebnis: string[] | null = null;
	(function lauf(node: unknown, pfad: string[]): void {
		if (ergebnis || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) return void node.forEach((k) => lauf(k, pfad));
		const n = node as Knoten;
		if (n === ziel) {
			ergebnis = pfad;
			return;
		}
		for (const [key, kind] of lebendeKinder(n)) {
			let p = pfad;
			if (BEDINGT.has(n.type) && key === 'consequent') p = [...pfad, kurz(n.test)];
			if (BEDINGT.has(n.type) && key === 'alternate') p = [...pfad, `!(${kurz(n.test)})`];
			if (n.type === 'LogicalExpression' && n.operator === '&&' && key === 'right') p = [...pfad, kurz(n.left)];
			lauf(kind, p);
		}
	})(wurzel, []);
	return ergebnis;
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

// ---------------------------------------------------------------------------------------------
// Fix-Loop 1 (#2278): BINDUNGS-Pruefstand. Die Helfer oben fragen nur "ist Literal/Bezeichner X
// irgendwo erreichbar". Die Zusicherungen der Aktionen wirken aber an der Bindung: WELCHES Argument
// geht in WELCHEN Aufruf, in WELCHEM Zweig, an WELCHEN Baustein. Die Kernsuite hat kein DOM (bits-ui
// rendert unter svelte/server nichts), also wird die Bindung am AST als normalisierter Ausdruck
// verglichen (`kurz`): whitespace-/formatunabhaengig, aber exakt in Argumenten und Zweigen.
// ---------------------------------------------------------------------------------------------

/** Normalisierte Kurzschrift eines Ausdrucks (ESTree/Svelte-AST) fuer exakte Bindungs-Vergleiche. */
export function kurz(n: any): string {
	if (n === null || n === undefined) return 'undefined';
	if (Array.isArray(n)) return n.map(kurz).join('; ');
	switch (n.type) {
		case 'Identifier':
			return n.name;
		case 'Literal':
			return JSON.stringify(n.value);
		case 'Text':
			return JSON.stringify(n.data);
		case 'ExpressionTag':
		case 'RenderTag':
		case 'ChainExpression':
		case 'ParenthesizedExpression':
		case 'TSNonNullExpression':
		case 'TSAsExpression':
			return kurz(n.expression);
		case 'AwaitExpression':
			return `await ${kurz(n.argument)}`;
		case 'UnaryExpression':
			return `${n.operator}${n.operator === 'void' || n.operator === 'typeof' ? ' ' : ''}${kurz(n.argument)}`;
		case 'MemberExpression':
			return n.computed
				? `${kurz(n.object)}${n.optional ? '?.' : ''}[${kurz(n.property)}]`
				: `${kurz(n.object)}${n.optional ? '?.' : '.'}${n.property.name}`;
		case 'CallExpression':
			return `${kurz(n.callee)}${n.optional ? '?.' : ''}(${(n.arguments ?? []).map(kurz).join(', ')})`;
		case 'BinaryExpression':
		case 'LogicalExpression':
		case 'AssignmentExpression':
			return `${kurz(n.left)} ${n.operator} ${kurz(n.right)}`;
		case 'ConditionalExpression':
			return `${kurz(n.test)} ? ${kurz(n.consequent)} : ${kurz(n.alternate)}`;
		case 'TemplateLiteral': {
			let s = '`';
			n.quasis.forEach((q: any, i: number) => {
				s += q.value.cooked;
				if (i < n.expressions.length) s += '${' + kurz(n.expressions[i]) + '}';
			});
			return s + '`';
		}
		case 'ObjectExpression':
			return `{ ${(n.properties ?? []).map((p: any) => (p.type === 'SpreadElement' ? kurz(p) : `${kurz(p.key)}: ${kurz(p.value)}`)).join(', ')} }`;
		case 'ArrowFunctionExpression':
			return `(${(n.params ?? []).map(kurz).join(', ')}) => ${kurz(n.body)}`;
		case 'BlockStatement':
			return `{ ${(n.body ?? []).map(kurz).join('; ')} }`;
		case 'ExpressionStatement':
			return kurz(n.expression);
		case 'IfStatement':
			return `if (${kurz(n.test)}) ${kurz(n.consequent)}`;
		case 'ReturnStatement':
			return `return ${kurz(n.argument)}`;
		case 'ArrayExpression':
			return `[${(n.elements ?? []).map(kurz).join(', ')}]`;
		case 'SpreadElement':
			return `...${kurz(n.argument)}`;
		case 'NewExpression':
			return `new ${kurz(n.callee)}(${(n.arguments ?? []).map(kurz).join(', ')})`;
		case 'VariableDeclaration':
			return `${n.kind} ${n.declarations.map((d: any) => `${kurz(d.id)} = ${kurz(d.init)}`).join(', ')}`;
		case 'TryStatement':
			return `try ${kurz(n.block)}${n.handler ? ` catch ${kurz(n.handler.body)}` : ''}${n.finalizer ? ` finally ${kurz(n.finalizer)}` : ''}`;
		default:
			// F019: nie auf den Typnamen zurueckfallen — verschiedene Ausdruecke wuerden sonst gleich aussehen.
			throw new Error(`kurz(): unbekannter Knotentyp ${n.type} — Kurzschrift erweitern`);
	}
}

/** Alle Aufrufe `name(...)` / `name?.(...)` (Identifier-Callee) unterhalb von `wurzel`. */
export function aufrufe(wurzel: unknown, name: string): Knoten[] {
	return collect(wurzel, (n) => n.type === 'CallExpression' && n.callee?.type === 'Identifier' && n.callee.name === name);
}

/** Argumente aller Aufrufe von `name` als Kurzschrift-Listen. */
export const aufrufArgumente = (wurzel: unknown, name: string): string[][] =>
	aufrufe(wurzel, name).map((c) => (c.arguments ?? []).map(kurz));

/** Zuweisungen `name = …` unterhalb von `wurzel` (rechte Seite als Kurzschrift). */
export function zuweisungen(wurzel: unknown, name: string): string[] {
	return collect(
		wurzel,
		(n) => n.type === 'AssignmentExpression' && n.left?.type === 'Identifier' && n.left.name === name
	).map((n) => kurz(n.right));
}

/** Funktionsknoten (Deklaration oder `const f = (…) => …`) des Instanz-Skripts. */
export function funktion(ast: Knoten, name: string): Knoten {
	for (const roh of (ast.instance?.content?.body ?? []) as Knoten[]) {
		const n = roh.type === 'ExportNamedDeclaration' && roh.declaration ? roh.declaration : roh;
		if (n.type === 'FunctionDeclaration' && n.id?.name === name) return n;
		if (n.type === 'VariableDeclaration')
			for (const d of n.declarations) if (d.id?.name === name && /Function/.test(d.init?.type ?? '')) return d.init;
	}
	throw new Error(`Funktion ${name} nicht im Instanz-Skript gefunden`);
}

/** Initialisierer einer Top-Level-Variable (z. B. der `$derived(...)`-Aufruf). */
export function initialisierer(ast: Knoten, name: string): Knoten {
	const k = lokaleBindungen(ast).get(name);
	if (!k) throw new Error(`Binding ${name} nicht im Instanz-Skript gefunden`);
	return k;
}

function vergleichtMit(test: Knoten, variable: string, lit: string): boolean {
	if (test.type === 'LogicalExpression') return vergleichtMit(test.left, variable, lit) || vergleichtMit(test.right, variable, lit);
	if (test.type !== 'BinaryExpression' || test.operator !== '===') return false;
	const istVar = (x: Knoten) => x.type === 'Identifier' && x.name === variable;
	const istLit = (x: Knoten) => x.type === 'Literal' && x.value === lit;
	return (istVar(test.left) && istLit(test.right)) || (istVar(test.right) && istLit(test.left));
}

/**
 * Die Anweisung, die im `if (variable === 'lit')`-Zweig steht (auch als Teil von `a === x || a === y`),
 * als Kurzschrift — je passendem If. Nur der `consequent`, nie die else-Kette.
 */
export function zweig(wurzel: unknown, variable: string, lit: string): string[] {
	return collect(wurzel, (n) => n.type === 'IfStatement' && vergleichtMit(n.test, variable, lit)).map((n) =>
		kurz(n.consequent)
	);
}

/** Ausdruck eines Attributs: `{expr}` -> Ausdruck, statischer Text -> Literal, sonst undefined. */
export function attrAusdruck(einbettung: Knoten, name: string): Knoten | undefined {
	const a = (einbettung.attributes ?? []).find((x: Knoten) => x.name === name);
	if (!a) return undefined;
	if (a.value === true) return { type: 'Literal', value: true };
	const v = Array.isArray(a.value) ? a.value : [a.value];
	if (v.length === 1 && v[0]?.type === 'ExpressionTag') return v[0].expression;
	if (v.length === 1 && v[0]?.type === 'Text') return { type: 'Literal', value: v[0].data };
	throw new Error(`Attribut ${name}: gemischter Text/Ausdruck — nicht als Kurzschrift darstellbar`);
}

/** Kurzschrift des Attribut-Ausdrucks (`undefined`, wenn das Attribut fehlt). */
export function attrKurz(einbettung: Knoten, name: string): string | undefined {
	const e = attrAusdruck(einbettung, name);
	return e === undefined ? undefined : kurz(e);
}

/** Alle Elemente/Komponenten, die ein statisches Attribut `name="wert"` tragen. */
export function mitAttribut(ast: Knoten, name: string, wert: string): Knoten[] {
	return collect(
		ast.fragment,
		(n) =>
			(n.type === 'RegularElement' || n.type === 'Component') &&
			(n.attributes ?? []).some(
				(a: Knoten) =>
					a.name === name && Array.isArray(a.value) && a.value.some((v: Knoten) => v.type === 'Text' && v.data === wert)
			)
	);
}
