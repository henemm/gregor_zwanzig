// Issue #2655 (i18n F6, Adversary F001) — Test-Hilfsmodul (nicht ausgeliefert):
// findet Stellen in Svelte-Komponenten, an denen ein Sprachwechsel OHNE Neuladen
// nicht ankaeme. Hintergrund: `tr()`/`trn()` lesen die Sprache per `get(locale)`;
// das ist KEIN reaktiver Lesezugriff. Ein `$derived(helfer())` oder ein
// Markup-Ausdruck `{helfer()}` mit einem tr()-nutzenden Helfer rechnet nach
// `locale.set('en')` daher nicht neu — es sei denn, der Ausdruck liest `$locale`
// (oder `$t`/`$tn`, die von `locale` abgeleitet sind), z. B. per
// `$derived.by(() => (void $locale, helfer()))`.
// Im Projekt gibt es kein DOM (kein jsdom/happy-dom), ein Client-Mount ist nicht
// moeglich; deshalb wird die Verdrahtung am AST (svelte/compiler `parse`, auch fuer
// .ts-Module: in ein <script lang="ts"> gehuellt) geprueft.
//
// Sprachabhaengig ist (je EXPORT, transitiv ueber relative/$lib-Importe):
//   * `tr`/`trn` aus lib/i18n/index.ts und jeder Aufruf `get(locale)`,
//   * jede Funktion, die Sprachabhaengiges AUFRUFT (oder als Argument weiterreicht)
//     und dabei kein `$locale`/`$t`/`$tn` liest.
// Gemeldet wird in Komponenten:
//   derived      `$derived`/`$derived.by`, der Sprachabhaengiges aufruft, ohne `$locale` zu lesen,
//   markup       Render-Ausdruck im Markup mit demselben Fehler,
//   eingefroren  Skript-Konstante, `$state`-Startwert oder `$props()`-Standardwert,
//                der Sprachabhaengiges beim Erzeugen auswertet.

import { readFileSync, existsSync, statSync, readdirSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { parse } from 'svelte/compiler';

export type Fund = { pfad: string; zeile: number; art: 'derived' | 'markup' | 'eingefroren'; text: string };

type Knoten = { type?: string; start?: number; end?: number; [k: string]: unknown };

const SPRACH_NAMEN_INDEX = new Set(['tr', 'trn']);
const REAKTIV = new Set(['$locale', '$t', '$tn']);

const istI18nIndex = (datei: string) => datei.split(sep).join('/').endsWith('lib/i18n/index.ts');

/** Import-Spezifizierer → .ts-Datei (relativ oder $lib), sonst null (Pakete, Komponenten). */
export function aufloesen(spez: string, vonDatei: string, src: string): string | null {
	let basis: string;
	if (spez.startsWith('$lib/')) basis = join(src, 'lib', spez.slice(5));
	else if (spez === '$lib') basis = join(src, 'lib');
	else if (spez.startsWith('.')) basis = join(dirname(vonDatei), spez);
	else return null;
	if (basis.endsWith('.svelte')) return null;
	const kandidaten = [basis, basis.replace(/\.js$/, '.ts'), `${basis}.ts`, `${basis}.svelte.ts`, join(basis, 'index.ts')];
	for (const k of kandidaten) if (existsSync(k) && statSync(k).isFile() && /\.ts$/.test(k)) return k;
	return null;
}

function besuche(
	knoten: unknown,
	f: (k: Knoten, eltern: Knoten | null, schluessel: string) => boolean | void,
	eltern: Knoten | null = null,
	schluessel = ''
): void {
	if (knoten === null || typeof knoten !== 'object') return;
	if (Array.isArray(knoten)) {
		for (const k of knoten) besuche(k, f, eltern, schluessel);
		return;
	}
	const k = knoten as Knoten;
	if (k.type && f(k, eltern, schluessel) === false) return;
	for (const [s, v] of Object.entries(k)) {
		if (s === 'loc' || s === 'metadata' || s === 'leadingComments' || s === 'trailingComments') continue;
		besuche(v, f, k.type ? k : eltern, s);
	}
}

const istFunktion = (k: Knoten | null | undefined) =>
	!!k && (k.type === 'ArrowFunctionExpression' || k.type === 'FunctionExpression' || k.type === 'FunctionDeclaration');

/** Was ein Teilbaum aufruft (Callees + weitergereichte Argumente) und ob er `$locale`/`$t` liest. */
function liest(baum: unknown, sprach: Set<string>): { sprachabhaengig: boolean; reaktiv: boolean } {
	let sprachabhaengig = false;
	let reaktiv = false;
	besuche(baum, (k, eltern, s) => {
		if (k.type === 'Identifier' && REAKTIV.has(k.name as string)) reaktiv = true;
		if (k.type !== 'CallExpression') return;
		const c = k.callee as Knoten;
		const args = (k.arguments as Knoten[]) ?? [];
		if (c.type === 'Identifier' && c.name === 'get' && args[0]?.type === 'Identifier' && args[0].name === 'locale') sprachabhaengig = true;
		const namen = [c, ...args].filter((x) => x?.type === 'Identifier').map((x) => x.name as string);
		if (c.type === 'MemberExpression' && (c.object as Knoten).type === 'Identifier') namen.push((c.object as Knoten).name as string);
		if (namen.some((n) => sprach.has(n))) sprachabhaengig = true;
		void eltern;
		void s;
	});
	return { sprachabhaengig, reaktiv };
}

type Analyse = { sprach: Set<string>; programm: Knoten[] };

/** Importierte + lokale sprachabhaengige Namen eines Programms (Fixpunkt ueber lokale Funktionen). */
function analysiere(programme: Knoten[], datei: string, src: string): Analyse {
	const sprach = new Set<string>();
	const funktionen: { name: string; rumpf: Knoten }[] = [];
	for (const p of programme) {
		for (const n of (p.body as Knoten[]) ?? []) {
			if (n.type === 'ImportDeclaration' && n.importKind !== 'type') {
				const ziel = aufloesen((n.source as Knoten).value as string, datei, src);
				if (!ziel) continue;
				const exp = istI18nIndex(ziel) ? SPRACH_NAMEN_INDEX : sprachExporte(ziel, src);
				for (const sp of (n.specifiers as Knoten[]) ?? []) {
					if (sp.importKind === 'type') continue;
					const lokal = (sp.local as Knoten).name as string;
					const importiert = sp.type === 'ImportSpecifier' ? (((sp.imported as Knoten).name ?? (sp.imported as Knoten).value) as string) : '*';
					if (importiert === '*' ? exp.size > 0 : exp.has(importiert)) sprach.add(lokal);
				}
			}
		}
		besuche(p, (k) => {
			if (k.type === 'FunctionDeclaration' && k.id) funktionen.push({ name: (k.id as Knoten).name as string, rumpf: k });
			if (k.type === 'VariableDeclarator' && (k.id as Knoten).type === 'Identifier' && istFunktion(k.init as Knoten))
				funktionen.push({ name: (k.id as Knoten).name as string, rumpf: k.init as Knoten });
		});
	}
	for (let neu = true; neu; ) {
		neu = false;
		for (const f of funktionen) {
			if (sprach.has(f.name)) continue;
			const l = liest(f.rumpf, sprach);
			if (l.sprachabhaengig && !l.reaktiv) {
				sprach.add(f.name);
				neu = true;
			}
		}
	}
	return { sprach, programm: programme };
}

const EXPORT_CACHE = new Map<string, Set<string>>();

/** Sprachabhaengige Export-Namen eines .ts-Moduls. */
export function sprachExporte(datei: string, src: string): Set<string> {
	if (EXPORT_CACHE.has(datei)) return EXPORT_CACHE.get(datei)!;
	EXPORT_CACHE.set(datei, new Set()); // Zyklen
	const quelle = readFileSync(datei, 'utf8');
	let prog: Knoten;
	try {
		prog = (parse(`<script lang="ts">${quelle}</script>`, { modern: true }) as unknown as { instance: { content: Knoten } }).instance.content;
	} catch {
		return EXPORT_CACHE.get(datei)!;
	}
	const { sprach } = analysiere([prog], datei, src);
	const aus = new Set<string>();
	for (const n of (prog.body as Knoten[]) ?? []) {
		if (n.type !== 'ExportNamedDeclaration') continue;
		const d = n.declaration as Knoten | null;
		if (d?.type === 'FunctionDeclaration' && sprach.has((d.id as Knoten).name as string)) aus.add((d.id as Knoten).name as string);
		if (d?.type === 'VariableDeclaration')
			for (const v of d.declarations as Knoten[]) {
				const name = (v.id as Knoten).name as string;
				if (name && sprach.has(name)) aus.add(name);
			}
		const quelleExp = n.source ? aufloesen((n.source as Knoten).value as string, datei, src) : null;
		const fremd = quelleExp ? (istI18nIndex(quelleExp) ? SPRACH_NAMEN_INDEX : sprachExporte(quelleExp, src)) : null;
		for (const sp of (n.specifiers as Knoten[]) ?? []) {
			const lokal = ((sp.local as Knoten).name ?? (sp.local as Knoten).value) as string;
			const exportiert = ((sp.exported as Knoten).name ?? (sp.exported as Knoten).value) as string;
			if (fremd ? fremd.has(lokal) : sprach.has(lokal)) aus.add(exportiert);
		}
	}
	EXPORT_CACHE.set(datei, aus);
	return aus;
}

const zeileBei = (q: string, i: number) => q.slice(0, i).split('\n').length;
const ausschnitt = (q: string, k: Knoten) => q.slice(k.start, k.end).replace(/\s+/g, ' ').slice(0, 90);

function istRune(k: Knoten | null | undefined, name: string): boolean {
	if (!k || k.type !== 'CallExpression') return false;
	const c = k.callee as Knoten;
	return (c.type === 'Identifier' && c.name === name) || (c.type === 'MemberExpression' && (c.object as Knoten).name === name);
}

/** Funde einer Svelte-Quelle (`datei` fuer die Import-Aufloesung, `pfad` fuer die Meldung). */
export function scanneKomponente(quelle: string, datei: string, src: string, pfad = datei): Fund[] {
	const ast = parse(quelle, { modern: true }) as unknown as { instance?: { content: Knoten }; module?: { content: Knoten }; fragment: Knoten };
	const programme = [ast.module?.content, ast.instance?.content].filter(Boolean) as Knoten[];
	const { sprach } = analysiere(programme, datei, src);
	const funde: Fund[] = [];
	const melde = (k: Knoten, art: Fund['art']) => funde.push({ pfad, zeile: zeileBei(quelle, k.start!), art, text: ausschnitt(quelle, k) });
	const fehlt = (baum: unknown) => {
		const l = liest(baum, sprach);
		return l.sprachabhaengig && !l.reaktiv;
	};
	for (const p of programme) {
		besuche(p, (k) => {
			if (istRune(k, '$derived')) {
				if (fehlt(k.arguments)) melde(k, 'derived');
				return false;
			}
			if (istFunktion(k)) return false;
			if (k.type === 'VariableDeclarator' && k.init) {
				const init = k.init as Knoten;
				if (istFunktion(init)) return false;
				if (istRune(init, '$derived')) return;
				// Standardwerte in $props() und jeder andere Startwert werden beim Erzeugen ausgewertet.
				const baum = istRune(init, '$props') ? k.id : init;
				if (liest(baum, sprach).sprachabhaengig) melde(k, 'eingefroren');
				return false;
			}
		});
	}
	besuche(ast.fragment, (k, eltern, s) => {
		if (!(s === 'expression' || s === 'test') || k.start === undefined || /Block$|Tag$|Attribute$|Directive$|Fragment$/.test(String(k.type)))
			return;
		// Rueckruf-Funktionen und Ereignis-Attribute (`onclick={…}`, `onAction={…}`)
		// laufen beim Aufruf, nicht beim Rendern.
		void eltern;
		if (istFunktion(k) || /\bon[A-Za-z]+=\{\s*$/.test(quelle.slice(Math.max(0, k.start - 40), k.start))) return false;
		if (fehlt(k)) melde(k, 'markup');
		return false;
	});
	return funde;
}

/** Alle .svelte-Dateien unter den Eintraegen (Verzeichnis mit `/` oder Datei), relativ zu `src`. */
export function dateienUnter(src: string, eintraege: string[]): string[] {
	const aus: string[] = [];
	const lauf = (abs: string) => {
		for (const n of readdirSync(abs)) {
			const p = join(abs, n);
			if (statSync(p).isDirectory()) {
				if (n !== '__tests__') lauf(p);
			} else if (n.endsWith('.svelte')) aus.push(p);
		}
	};
	for (const e of eintraege) {
		const abs = join(src, e);
		if (e.endsWith('/')) lauf(abs);
		else aus.push(abs);
	}
	return [...new Set(aus)].sort().map((p) => relative(src, p).split(sep).join('/'));
}

export function scanneEintraege(src: string, eintraege: string[]): { dateien: string[]; funde: Fund[] } {
	const dateien = dateienUnter(src, eintraege);
	const funde = dateien.flatMap((rel) => scanneKomponente(readFileSync(join(src, rel), 'utf8'), join(src, rel), src, rel));
	return { dateien, funde };
}
