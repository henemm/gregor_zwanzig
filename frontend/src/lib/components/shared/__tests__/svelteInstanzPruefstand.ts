// Pruefstand: wertet das Instanz-Skript einer .svelte-Datei gegen eine
// gesaete Prop-Umgebung aus und liest die Attribut-Ausdruecke ECHTER
// Einbettungen.
//
// Herkunft: wortgleich aus dem F007-Abschnitt von `metricKuerzelLegende.test.ts`
// (Issue #1888 E6b) herausgezogen, dort als lokale Hilfsfunktionen entstanden.
// Issue #2276 S6b braucht denselben Mechanismus fuer eine ZWEITE Zusicherung
// (Wertprop-Verdrahtung des Stundenverlaufs) — deshalb hier als eigenes Modul
// statt ein zweites Mal abgeschrieben. Die Fassung in metricKuerzelLegende.test.ts
// bleibt unangetastet (eine Testdatei aus einer anderen zu importieren wuerde
// deren Tests ein zweites Mal ausfuehren).
//
// WARUM ueberhaupt so: die Frontend-Kernsuite ist SSR-only (`node --test` +
// `svelte/server`, kein DOM). Ereignisse und `$effect` laufen dort nie. Was
// sich trotzdem deterministisch messen laesst, ist die ECHTE Herleitung des
// Instanz-Skripts: seine Importe, seine Funktionsdeklarationen, seine
// `$derived`-Ausdruecke — ausgefuehrt mit gesaeten Props. Damit wird nicht
// geprueft, ob ein Bezeichner im Quelltext steht, sondern was der Code mit
// den Props TUT.
//
// Pfadregel #1409: Aufrufer loesen Dateipfade relativ zur EIGENEN Testdatei
// auf, nie ueber einen festen Hauptrepo-Pfad.

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';

export type Knoten = Record<string, any>;

/** Wertet einen Quelltext-Ausdruck gegen eine Umgebung aus. */
export function werte(ausdruck: string, umgebung: Knoten): unknown {
	return new Function('u', `with (u) { return (${ausdruck}); }`)(umgebung);
}

/** Der Quelltext eines Knotens OHNE TypeScript-Annotationen — `new Function`
 *  versteht kein TS, und die Herleitungen der Komponenten sind typisiert.
 *  Ausgeblendet wird per AST (Zeichen durch Leerzeichen ersetzt, Offsets
 *  bleiben gueltig), nicht per Textmuster — geraten wird hier nichts. */
export function ohneTypen(quelle: string, knoten: Knoten): string {
	const loecher: [number, number][] = [];
	function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(lauf);
			return;
		}
		const k = n as Knoten;
		for (const feld of ['typeAnnotation', 'returnType', 'typeParameters', 'typeArguments']) {
			const t = k[feld] as Knoten | undefined;
			if (t && typeof t.start === 'number') loecher.push([t.start, t.end]);
		}
		if (
			(k.type === 'TSAsExpression' || k.type === 'TSSatisfiesExpression') &&
			k.expression &&
			k.typeAnnotation
		) {
			loecher.push([k.expression.end, k.typeAnnotation.end]);
		}
		if (k.type === 'TSNonNullExpression' && k.expression) loecher.push([k.expression.end, k.end]);
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(knoten);
	const zeichen = [...quelle];
	for (const [a, b] of loecher) for (let i = a; i < b && i < zeichen.length; i++) zeichen[i] = ' ';
	return zeichen.slice(knoten.start, knoten.end).join('');
}

/** Baut die Umgebung einer Komponentendatei: Runen-Attrappen, ihre ECHTEN
 *  Modul-Importe und ihre eigenen Deklarationen, der Reihe nach ausgewertet.
 *  Was sich nicht auswerten laesst, bleibt weg — fehlt es spaeter, scheitert
 *  der Ausdruck LAUT (keine stille Entwarnung). */
export async function umgebungFuer(
	datei: string,
	saat: Knoten
): Promise<{ ast: Knoten; quelle: string; u: Knoten }> {
	const quelle = readFileSync(datei, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });
	const u: Knoten = { ...saat };
	const derived = ((v: unknown) => v) as Knoten;
	derived.by = (fn: () => unknown) => fn();
	u.$derived = derived;
	u.$state = (v: unknown) => v;
	u.$props = () => ({});
	u.$effect = () => {};

	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'ImportDeclaration') continue;
		const q = String(stmt.source?.value ?? '');
		if (q.endsWith('.svelte')) continue;
		const spec = q.startsWith('.')
			? pathToFileURL(resolve(dirname(datei), q)).href
			: q.startsWith('$lib/')
				? q
				: null;
		if (!spec) continue;
		// Gebunden wird NUR, was diese Deklaration wirklich nennt — und Typ-Importe
		// binden zur Laufzeit gar nichts (Adversary F008 aus #1888: sonst liefert
		// der Typ-Import die Bindung nach, die der gebrochene Wert-Import verlor).
		if (stmt.importKind === 'type') continue;
		let mod: Knoten | null = null;
		try {
			mod = (await import(spec)) as Knoten;
		} catch {
			mod = null;
		}
		if (!mod) continue;
		for (const s of (stmt.specifiers ?? []) as Knoten[]) {
			if (s.importKind === 'type') continue;
			const lokal = s.local?.name as string | undefined;
			if (!lokal || lokal in u) continue;
			if (s.type === 'ImportNamespaceSpecifier') {
				u[lokal] = mod;
				continue;
			}
			const her = s.type === 'ImportDefaultSpecifier' ? 'default' : (s.imported?.name ?? lokal);
			if (her in mod) u[lokal] = mod[her];
		}
	}
	// Funktionsdeklarationen zuerst — sie werden in JS gehoben, und die
	// Herleitungen rufen sie auf.
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'FunctionDeclaration' || stmt.id?.type !== 'Identifier') continue;
		if (stmt.id.name in u) continue;
		try {
			u[stmt.id.name] = new Function(
				'u',
				`with (u) { ${ohneTypen(quelle, stmt)}\n return ${stmt.id.name}; }`
			)(u);
		} catch {
			/* s.o. */
		}
	}
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'Identifier' || !d.init || d.id.name in u) continue;
			try {
				u[d.id.name] = werte(ohneTypen(quelle, d.init), u);
			} catch {
				/* s.o. */
			}
		}
	}
	return { ast, quelle, u };
}

/** Alle Einbettungen der Komponente `name` im Markup — in Quelltext-Reihenfolge. */
export function findeKomponenten(ast: Knoten, name: string): Knoten[] {
	const treffer: Knoten[] = [];
	function lauf(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(lauf);
			return;
		}
		const n = node as Knoten;
		if (n.type === 'Component' && n.name === name) treffer.push(n);
		for (const key of Object.keys(n)) {
			if (key !== 'parent' && key !== 'loc') lauf(n[key]);
		}
	}
	lauf(ast.fragment);
	return treffer;
}

/** Der Quelltext des Attribut-Ausdrucks `name` an einer Einbettung, oder
 *  `null`, wenn das Attribut fehlt. */
export function attributAusdruck(einbettung: Knoten, quelle: string, name: string): string | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute' || a.name !== name) continue;
		const v = a.value;
		if (v?.type === 'ExpressionTag') return quelle.slice(v.expression.start, v.expression.end);
		// Kurzform `{metricById}` — der Wert IST der Bezeichner.
		return name;
	}
	return null;
}

/** Alle gesetzten Attributnamen einer Einbettung (fuer Abwesenheits-Aussagen). */
export function attributNamen(einbettung: Knoten): string[] {
	return ((einbettung.attributes ?? []) as Knoten[])
		.filter((a) => a.type === 'Attribute')
		.map((a) => String(a.name));
}
