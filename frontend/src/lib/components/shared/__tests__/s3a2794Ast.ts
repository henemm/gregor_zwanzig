// Pruefstand-Helfer fuer Issue #2794 S3a, Teil-PR 2 (Leiste und Umleitung).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md (AC-2.T1, AC-2.T2, AC-2.T3, AC-2.T4)
//
// Struktur-Waechter nach Repo-Muster (compare_wetter_metriken_wertprops.test.ts,
// trip_new_mail_inhalt_karte_genau_eine_instanz.test.ts): AST der echten Komponente
// ueber `svelte/compiler.parse`, keine Textmuster-Suche im Quelltext. Gemessen wird,
// WELCHE Einbettung unter WELCHER Weiche steht, und ob sich zwei Einbettungen
// gegenseitig ausschliessen (nie zwei WeatherMetricsTab-Instanzen zugleich).
//
// Keine .test.ts-Datei: wird nur von den s3a2794_*-Tests importiert.

import { readFileSync, existsSync } from 'node:fs';
import { parse } from 'svelte/compiler';

export type Knoten = Record<string, any>;

export interface Weiche {
	/** Das IfBlock-Element, unter dem die Einbettung steht. */
	block: Knoten;
	/** 'dann' = im {#if}-Zweig, 'sonst' = im {:else}-/{:else if}-Zweig. */
	zweig: 'dann' | 'sonst';
	/** Quelltext der Bedingung. */
	test: string;
}

export interface Einbettung {
	knoten: Knoten;
	name: string;
	weichen: Weiche[];
	/** Alle Vorfahren (aeusserster zuerst). */
	ahnen: Knoten[];
}

export function svelteAst(datei: string): { ast: Knoten; quelle: string } {
	const quelle = readFileSync(datei, 'utf-8');
	return { ast: parse(quelle, { modern: true }) as Knoten, quelle };
}

/** Eine reine .ts-Datei als AST (ueber den Svelte-Parser, eingebettet in ein TS-Skript).
 *  Offsets beziehen sich auf den eingebetteten Text — `quelle` ist entsprechend versetzt. */
export function tsAst(datei: string): { programm: Knoten; quelle: string } {
	const roh = readFileSync(datei, 'utf-8');
	const quelle = `<script lang="ts">\n${roh}\n</script>\n`;
	const ast = parse(quelle, { modern: true }) as Knoten;
	return { programm: ast.instance.content as Knoten, quelle };
}

export function existiert(datei: string): boolean {
	return existsSync(datei);
}

/** Alle Einbettungen der Komponenten `namen` mit ihren Weichen (IfBlock + Zweig). */
export function einbettungenMitWeichen(ast: Knoten, quelle: string, namen: string[]): Einbettung[] {
	const out: Einbettung[] = [];
	function lauf(n: unknown, weichen: Weiche[], ahnen: Knoten[]): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			for (const x of n) lauf(x, weichen, ahnen);
			return;
		}
		const k = n as Knoten;
		if (k.type === 'Component' && namen.includes(k.name)) {
			out.push({ knoten: k, name: k.name, weichen, ahnen });
		}
		const neueAhnen = typeof k.type === 'string' ? [...ahnen, k] : ahnen;
		if (k.type === 'IfBlock') {
			const test = quelle.slice(k.test.start, k.test.end).trim();
			lauf(k.consequent, [...weichen, { block: k, zweig: 'dann', test }], neueAhnen);
			if (k.alternate) lauf(k.alternate, [...weichen, { block: k, zweig: 'sonst', test }], neueAhnen);
			return;
		}
		for (const [feld, v] of Object.entries(k)) {
			if (feld === 'parent' || feld === 'loc' || feld === 'metadata') continue;
			lauf(v, weichen, neueAhnen);
		}
	}
	lauf(ast.fragment, [], []);
	return out;
}

const TAB_LITERAL = /(?:activeTab|tab\.value)\s*===\s*'([^']+)'/;

/** Reiter-Kennungen, unter deren positiver Weiche (`activeTab === 'x'` bzw. `tab.value === 'x'`) die Einbettung steht. */
export function reiterVon(e: Einbettung): string[] {
	const out: string[] = [];
	for (const w of e.weichen) {
		if (w.zweig !== 'dann') continue;
		const m = TAB_LITERAL.exec(w.test);
		if (m) out.push(m[1]);
	}
	return out;
}

/** Steht die Einbettung unter einer Weiche, die `activeTab` nennt (= nicht dauerhaft gemountet)? */
export function haengtAnActiveTabWeiche(e: Einbettung): boolean {
	return e.weichen.some((w) => /\bactiveTab\b/.test(w.test));
}

/** Viewport-Zweig: 'mobil' (`isMobileViewport`), 'desktop' (`!isMobileViewport` oder else-Zweig davon), sonst null. */
export function viewportVon(e: Einbettung): 'mobil' | 'desktop' | null {
	for (const w of e.weichen) {
		const t = w.test.replace(/\s+/g, '');
		if (t === 'isMobileViewport') return w.zweig === 'dann' ? 'mobil' : 'desktop';
		if (t === '!isMobileViewport') return w.zweig === 'dann' ? 'desktop' : 'mobil';
	}
	return null;
}

/** Schliessen sich zwei Einbettungen gegenseitig aus (nie zugleich gemountet)? */
export function schliessenSichAus(a: Einbettung, b: Einbettung): boolean {
	// (1) gemeinsamer IfBlock, verschiedene Zweige
	for (const wa of a.weichen) {
		for (const wb of b.weichen) {
			if (wa.block === wb.block && wa.zweig !== wb.zweig) return true;
		}
	}
	// (2) verschiedene Reiter-Literale derselben Weichenform
	const ra = reiterVon(a);
	const rb = reiterVon(b);
	if (ra.length > 0 && rb.length > 0 && !ra.some((x) => rb.includes(x))) return true;
	// (3) Viewport-XOR
	const va = viewportVon(a);
	const vb = viewportVon(b);
	if (va !== null && vb !== null && va !== vb) return true;
	return false;
}

/** Wert eines Attributs: Literal (Text oder `{'x'}`) oder Ausdrucks-Quelltext; null = fehlt. */
export function attribut(e: Knoten, quelle: string, name: string): { literal?: string; ausdruck?: string } | null {
	for (const a of (e.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute' || a.name !== name) continue;
		const v = a.value;
		if (v === true) return { literal: 'true' };
		if (Array.isArray(v)) {
			if (v.length === 1 && v[0].type === 'Text') return { literal: v[0].data as string };
			if (v.length === 1 && v[0].type === 'ExpressionTag') {
				const ex = v[0].expression as Knoten;
				if (ex.type === 'Literal' && typeof ex.value === 'string') return { literal: ex.value };
				return { ausdruck: quelle.slice(ex.start, ex.end) };
			}
			return { ausdruck: v.map((x: Knoten) => quelle.slice(x.start, x.end)).join('') };
		}
		if (v?.type === 'ExpressionTag') {
			const ex = v.expression as Knoten;
			if (ex.type === 'Literal' && typeof ex.value === 'string') return { literal: ex.value };
			return { ausdruck: quelle.slice(ex.start, ex.end) };
		}
	}
	return null;
}

/** `style:display`-Ausdruck des naechsten Vorfahren-Elements, das einen traegt (sonst null). */
export function displayAusdruck(e: Einbettung, quelle: string): string | null {
	for (let i = e.ahnen.length - 1; i >= 0; i--) {
		const a = e.ahnen[i];
		for (const attr of (a.attributes ?? []) as Knoten[]) {
			if (attr.type === 'StyleDirective' && attr.name === 'display') {
				const v = attr.value;
				const tag = Array.isArray(v) ? v[0] : v;
				if (tag?.type === 'ExpressionTag') return quelle.slice(tag.expression.start, tag.expression.end);
			}
		}
	}
	return null;
}

/** Alle regulaeren Elemente `tag` mit Attribut id=`id` (Literal), samt Weichen. */
export function elementeMitId(ast: Knoten, quelle: string, tag: string, id: string): Array<{ knoten: Knoten; weichen: Weiche[] }> {
	const out: Array<{ knoten: Knoten; weichen: Weiche[] }> = [];
	function lauf(n: unknown, weichen: Weiche[]): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			for (const x of n) lauf(x, weichen);
			return;
		}
		const k = n as Knoten;
		if (k.type === 'RegularElement' && k.name === tag) {
			const a = attribut(k, quelle, 'id');
			if (a?.literal === id) out.push({ knoten: k, weichen });
		}
		if (k.type === 'IfBlock') {
			const test = quelle.slice(k.test.start, k.test.end).trim();
			lauf(k.consequent, [...weichen, { block: k, zweig: 'dann', test }]);
			if (k.alternate) lauf(k.alternate, [...weichen, { block: k, zweig: 'sonst', test }]);
			return;
		}
		for (const [feld, v] of Object.entries(k)) {
			if (feld === 'parent' || feld === 'loc' || feld === 'metadata') continue;
			lauf(v, weichen);
		}
	}
	lauf(ast.fragment, []);
	return out;
}

/** Namen der per `$props()` destrukturierten Props einer Komponente. */
export function propNamen(ast: Knoten): string[] {
	const namen: string[] = [];
	for (const stmt of (ast.instance?.content?.body ?? []) as Knoten[]) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			const init = d.init as Knoten | null;
			if (init?.type !== 'CallExpression' || init.callee?.name !== '$props') continue;
			if (d.id?.type !== 'ObjectPattern') continue;
			for (const p of d.id.properties as Knoten[]) {
				if (p.type === 'Property' && p.key?.type === 'Identifier') namen.push(p.key.name);
			}
		}
	}
	return namen;
}

/** Alle CallExpressions in einem Teilbaum. */
export function aufrufe(wurzel: unknown): Knoten[] {
	const out: Knoten[] = [];
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'CallExpression') out.push(k);
		for (const [feld, v] of Object.entries(k)) {
			if (feld === 'parent' || feld === 'loc' || feld === 'metadata') continue;
			lauf(v);
		}
	})(wurzel);
	return out;
}

/** Quelltext des Aufgerufenen (`saveController.schedule`, `baueTripSpeicherung` …). */
export function aufgerufener(aufruf: Knoten, quelle: string): string {
	const c = aufruf.callee as Knoten;
	return quelle.slice(c.start, c.end).replace(/\s+/g, '').replace(/\?\./g, '.');
}

/** Letztes Argument als String-Literal (sonst null). */
export function letztesStringArgument(aufruf: Knoten): string | null {
	const args = (aufruf.arguments ?? []) as Knoten[];
	const l = args[args.length - 1];
	return l?.type === 'Literal' && typeof l.value === 'string' ? l.value : null;
}
