// Prüfstand-Helfer #2980 (Fix-Loop Bildabgleich c2): rechnet für ein Element aus dem
// SSR-Baum (htmlBaum.ts) den berechneten Stil nach — aus den ECHTEN Stilquellen, die der
// Browser für diese Seite lädt:
//   - frontend/src/app.css (Tokens, @layer base/components/utilities, Media-Queries),
//   - das kompilierte CSS (svelte/compiler, dieselben Optionen wie test-svelte-ssr-hooks.mjs,
//     also dieselben Scope-Klassen `svelte-<hash>`) GENAU der Svelte-Dateien, deren Scope-Klasse
//     im gerenderten Markup vorkommt,
//   - Inline-`style`-Attribute des Markups.
// Kaskade: !important > ohne Layer > Layer, dann Spezifität, dann Reihenfolge; Media-Queries
// gegen eine angenommene Viewport-Breite (Handy 390 / Desktop 1280); Hell-/Dunkel-Modus über
// `<html data-theme="dark">` (:root[data-theme="dark"]); Vererbung für Schrift/Farbe.
// Zustände ohne Interaktion: :hover/:focus/:active und Pseudo-Elemente gelten nicht.
//
// Kein DOM, kein Mock: dieselben Regeln, die im Browser greifen, werden hier ausgewertet. Die
// Messung im echten Browser macht frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts.
// doc-compliance-test (liest CSS-Quellen als Daten; Verhalten = Kaskade am gerenderten Markup)

import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import type { Knoten } from './htmlBaum.ts';

export type Theme = 'hell' | 'dunkel';
export interface Kontext {
	/** Viewport-Breite in px (Handy 390, Desktop 1280). */
	breite: number;
	theme: Theme;
}
export const HANDY: Kontext = { breite: 390, theme: 'hell' };
export const DESKTOP: Kontext = { breite: 1280, theme: 'hell' };

interface Regel {
	selektor: string;
	decls: Array<[string, string, boolean]>;
	media: string[];
	layer: boolean;
	ordnung: number;
}

// ── CSS lesen ────────────────────────────────────────────────────────────────────────

const ohneKommentare = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '');

/** Selektorliste an Kommas der obersten Ebene trennen (Kommas in :not()/:is() bleiben). */
function trenneListe(s: string): string[] {
	const aus: string[] = [];
	let tiefe = 0;
	let akt = '';
	for (const c of s) {
		if (c === '(' || c === '[') tiefe++;
		else if (c === ')' || c === ']') tiefe--;
		if (c === ',' && tiefe === 0) {
			aus.push(akt.trim());
			akt = '';
		} else akt += c;
	}
	if (akt.trim()) aus.push(akt.trim());
	return aus;
}

function deklarationen(inhalt: string): Array<[string, string, boolean]> {
	const aus: Array<[string, string, boolean]> = [];
	let tiefe = 0;
	let akt = '';
	const teile: string[] = [];
	for (const c of inhalt) {
		if (c === '(') tiefe++;
		else if (c === ')') tiefe--;
		if (c === ';' && tiefe === 0) {
			teile.push(akt);
			akt = '';
		} else akt += c;
	}
	teile.push(akt);
	for (const d of teile) {
		const i = d.indexOf(':');
		if (i <= 0) continue;
		const prop = d.slice(0, i).trim().toLowerCase();
		if (!/^-?-?[a-z][a-z0-9-]*$/.test(prop)) continue;
		let wert = d.slice(i + 1).trim().replace(/\s+/g, ' ');
		const wichtig = /!\s*important$/i.test(wert);
		if (wichtig) wert = wert.replace(/!\s*important$/i, '').trim();
		aus.push([prop, wert, wichtig]);
	}
	return aus;
}

let ORDNUNG = 0;
/** Liest Regeln; @layer zählt als Layer, @media wird mitgeführt, andere At-Regeln werden übersprungen. */
export function leseRegeln(cssRoh: string, layerStart = false): Regel[] {
	const css = ohneKommentare(cssRoh);
	const aus: Regel[] = [];
	function block(von: number, bis: number, media: string[], layer: boolean): void {
		let i = von;
		let kopfStart = von;
		while (i < bis) {
			const c = css[i];
			if (c === ';' || c === '}') {
				i++;
				kopfStart = i;
				continue;
			}
			if (c !== '{') {
				i++;
				continue;
			}
			let tiefe = 1;
			let j = i + 1;
			for (; j < bis && tiefe > 0; j++) tiefe += css[j] === '{' ? 1 : css[j] === '}' ? -1 : 0;
			const kopf = css.slice(kopfStart, i).trim();
			const innenVon = i + 1;
			const innenBis = j - 1;
			if (kopf.startsWith('@layer')) block(innenVon, innenBis, media, true);
			else if (kopf.startsWith('@media')) block(innenVon, innenBis, [...media, kopf.slice(6).trim()], layer);
			else if (kopf.startsWith('@')) {
				/* @theme, @custom-variant, @font-face, @supports, @keyframes …: keine Element-Regeln */
			} else {
				const inhalt = css.slice(innenVon, innenBis);
				if (!inhalt.includes('{')) {
					const decls = deklarationen(inhalt);
					for (const sel of trenneListe(kopf)) aus.push({ selektor: sel.replace(/\s+/g, ' '), decls, media, layer, ordnung: ORDNUNG++ });
				}
			}
			i = j;
			kopfStart = j;
		}
	}
	block(0, css.length, [], layerStart);
	return aus;
}

// ── Quellen ──────────────────────────────────────────────────────────────────────────

export interface Quellen {
	appCss: string;
	app: Regel[];
	/** Scope-Hash -> Regeln des kompilierten Komponenten-CSS */
	komponenten: Map<string, { datei: string; regeln: Regel[] }>;
	hell: Record<string, string>;
	dunkel: Record<string, string>;
}

function* svelteDateien(d: string): Generator<string> {
	for (const n of readdirSync(d)) {
		const p = path.join(d, n);
		if (statSync(p).isDirectory()) {
			if (n !== 'node_modules' && n !== '__tests__') yield* svelteDateien(p);
		} else if (n.endsWith('.svelte')) yield p;
	}
}

let CACHE: Quellen | null = null;
export async function ladeQuellen(frontend: string): Promise<Quellen> {
	if (CACHE) return CACHE;
	const { compile } = await import(pathToFileURL(path.join(frontend, 'node_modules', 'svelte', 'src', 'compiler', 'index.js')).href);
	const appCss = readFileSync(path.join(frontend, 'src', 'app.css'), 'utf8');
	const app = leseRegeln(appCss);
	const komponenten = new Map<string, { datei: string; regeln: Regel[] }>();
	for (const datei of svelteDateien(path.join(frontend, 'src'))) {
		const quelle = readFileSync(datei, 'utf8');
		if (!/<style[\s>]/.test(quelle)) continue;
		let code = '';
		try {
			code = compile(quelle, { generate: 'server', filename: datei }).css?.code ?? '';
		} catch {
			continue;
		}
		const hash = code.match(/\.(svelte-[a-z0-9]+)/)?.[1];
		if (hash) komponenten.set(hash, { datei, regeln: leseRegeln(code) });
	}
	// Tokens: :root (Hell) und :root[data-theme="dark"] (Dunkel, überlagert Hell).
	const hell: Record<string, string> = {};
	const dunkelNur: Record<string, string> = {};
	for (const r of app) {
		if (r.media.length) continue;
		const ziel = r.selektor === ':root' ? hell : /^:root\[data-theme=["']dark["']\]$/.test(r.selektor) ? dunkelNur : null;
		if (!ziel) continue;
		for (const [p, v] of r.decls) if (p.startsWith('--')) ziel[p] = v;
	}
	CACHE = { appCss, app, komponenten, hell, dunkel: { ...hell, ...dunkelNur } };
	return CACHE;
}

// ── Selektoren ───────────────────────────────────────────────────────────────────────

const ZUSTAND = /^:(hover|focus|focus-visible|focus-within|active|visited|target|checked|disabled|enabled|invalid|placeholder-shown|has)\b/;

function klassen(k: Knoten): string[] {
	return (k.attrs.class ?? '').split(/\s+/).filter(Boolean);
}
function geschwister(k: Knoten): Knoten[] {
	return k.eltern ? k.eltern.kinder : [k];
}

/** Ein zusammengesetzter Selektor (ohne Kombinatoren) gegen einen Knoten. Liefert [passt, spezifität]. */
function compound(c: string, k: Knoten, ctx: Kontext): [boolean, number] {
	let rest = c;
	let spez = 0;
	const istRoot = k.tag === '#root';
	const attrs: Record<string, string> = istRoot ? (ctx.theme === 'dunkel' ? { 'data-theme': 'dark' } : {}) : k.attrs;
	const tag = /^([a-z][a-z0-9-]*|\*)/i.exec(rest);
	if (tag) {
		if (tag[1] !== '*') {
			if (istRoot ? tag[1].toLowerCase() !== 'html' : tag[1].toLowerCase() !== k.tag) return [false, 0];
			spez += 1;
		}
		rest = rest.slice(tag[0].length);
	}
	while (rest.length) {
		let m: RegExpExecArray | null;
		if ((m = /^::?(before|after|placeholder|marker|selection|-webkit-[a-z-]+|first-line|first-letter)\b/.exec(rest))) return [false, 0];
		if ((m = /^\.([\w-]+)/.exec(rest))) {
			if (istRoot || !klassen(k).includes(m[1])) return [false, 0];
			spez += 100;
		} else if ((m = /^#([\w-]+)/.exec(rest))) {
			if (attrs.id !== m[1]) return [false, 0];
			spez += 10000;
		} else if ((m = /^\[\s*([\w-]+)\s*(?:([~^$*|]?=)\s*(?:"([^"]*)"|'([^']*)'|([^\]\s]+))\s*)?\]/.exec(rest))) {
			const [name, op, w1, w2, w3] = [m[1], m[2], m[3], m[4], m[5]];
			const soll = w1 ?? w2 ?? w3;
			if (!(name in attrs)) return [false, 0];
			const ist = attrs[name];
			if (op === '=' && ist !== soll) return [false, 0];
			if (op === '^=' && !ist.startsWith(soll!)) return [false, 0];
			if (op === '*=' && !ist.includes(soll!)) return [false, 0];
			if (op === '$=' && !ist.endsWith(soll!)) return [false, 0];
			if (op === '~=' && !ist.split(/\s+/).includes(soll!)) return [false, 0];
			spez += 100;
		} else if ((m = /^:root\b/.exec(rest))) {
			if (!istRoot) return [false, 0];
			spez += 100;
		} else if ((m = /^:(not|is|where)\(/.exec(rest))) {
			let tiefe = 1;
			let j = m[0].length;
			for (; j < rest.length && tiefe > 0; j++) tiefe += rest[j] === '(' ? 1 : rest[j] === ')' ? -1 : 0;
			const innen = rest.slice(m[0].length, j - 1);
			const treffer = trenneListe(innen).map((s) => selektorPasst(s, k, ctx));
			const besteSpez = Math.max(0, ...treffer.map((t) => t[1]));
			if (m[1] === 'not') {
				if (treffer.some((t) => t[0])) return [false, 0];
				spez += besteSpez;
			} else {
				if (!treffer.some((t) => t[0])) return [false, 0];
				if (m[1] === 'is') spez += besteSpez;
			}
			rest = rest.slice(j);
			continue;
		} else if ((m = /^:(first-child|last-child|only-child)\b/.exec(rest))) {
			if (istRoot) return [false, 0];
			const g = geschwister(k);
			if (m[1] === 'first-child' && g[0] !== k) return [false, 0];
			if (m[1] === 'last-child' && g[g.length - 1] !== k) return [false, 0];
			if (m[1] === 'only-child' && g.length !== 1) return [false, 0];
			spez += 100;
		} else if (ZUSTAND.test(rest)) {
			return [false, 0];
		} else {
			// unbekannte Pseudo-Klasse: konservativ nicht passend
			return [false, 0];
		}
		rest = rest.slice(m[0].length);
	}
	return [true, spez];
}

/** Selektor in Teile (compound, kombinator) zerlegen. */
function zerlege(sel: string): Array<{ c: string; komb: string }> {
	const teile: Array<{ c: string; komb: string }> = [];
	let tiefe = 0;
	let akt = '';
	let komb = ' ';
	const s = sel.trim();
	for (let i = 0; i < s.length; i++) {
		const ch = s[i];
		if (ch === '(' || ch === '[') tiefe++;
		else if (ch === ')' || ch === ']') tiefe--;
		if (tiefe === 0 && (ch === ' ' || ch === '>' || ch === '+' || ch === '~')) {
			if (akt) {
				teile.push({ c: akt, komb });
				akt = '';
				komb = ' ';
			}
			if (ch !== ' ') komb = ch;
			continue;
		}
		akt += ch;
	}
	if (akt) teile.push({ c: akt, komb });
	return teile;
}

function selektorPasst(selRoh: string, k: Knoten, ctx: Kontext): [boolean, number] {
	const sel = selRoh.replace(/:global\(([^()]*(?:\([^()]*\))*[^()]*)\)/g, '$1').trim();
	if (!sel) return [false, 0];
	const teile = zerlege(sel);
	let gesamt = 0;
	function ab(index: number, knoten: Knoten): boolean {
		const [ok, sp] = compound(teile[index].c, knoten, ctx);
		if (!ok) return false;
		if (index === 0) {
			gesamt += sp;
			return true;
		}
		const komb = teile[index].komb;
		if (komb === '>') {
			if (!knoten.eltern) return false;
			if (ab(index - 1, knoten.eltern)) {
				gesamt += sp;
				return true;
			}
			return false;
		}
		if (komb === '+' || komb === '~') {
			const g = geschwister(knoten);
			const i = g.indexOf(knoten);
			const kandidaten = komb === '+' ? g.slice(Math.max(0, i - 1), i) : g.slice(0, i);
			for (const v of kandidaten.reverse()) if (ab(index - 1, v)) return ((gesamt += sp), true);
			return false;
		}
		for (let v = knoten.eltern; v; v = v.eltern) if (ab(index - 1, v)) return ((gesamt += sp), true);
		return false;
	}
	const ok = ab(teile.length - 1, k);
	return [ok, ok ? gesamt : 0];
}

// ── Media ────────────────────────────────────────────────────────────────────────────

function mediaPasst(q: string, ctx: Kontext): boolean {
	return q.split(',').some((teil) =>
		teil
			.trim()
			.split(/\s+and\s+/)
			.every((bed) => {
				const b = bed.trim().toLowerCase();
				if (b === 'screen' || b === 'all' || b === 'only screen') return true;
				let m: RegExpExecArray | null;
				if ((m = /\(\s*max-width\s*:\s*([\d.]+)px\s*\)/.exec(b))) return ctx.breite <= Number(m[1]);
				if ((m = /\(\s*min-width\s*:\s*([\d.]+)px\s*\)/.exec(b))) return ctx.breite >= Number(m[1]);
				if (/\(\s*pointer\s*:\s*coarse\s*\)/.test(b)) return ctx.breite < 900;
				if (/\(\s*pointer\s*:\s*fine\s*\)/.test(b) || /\(\s*hover\s*:\s*hover\s*\)/.test(b)) return ctx.breite >= 900;
				if ((m = /\(\s*prefers-color-scheme\s*:\s*(dark|light)\s*\)/.exec(b))) return (m[1] === 'dark') === (ctx.theme === 'dunkel');
				return false;
			})
	);
}

// ── Longhands ────────────────────────────────────────────────────────────────────────

function woerter(v: string): string[] {
	const aus: string[] = [];
	let tiefe = 0;
	let akt = '';
	for (const c of v) {
		if (c === '(') tiefe++;
		else if (c === ')') tiefe--;
		if (c === ' ' && tiefe === 0) {
			if (akt) aus.push(akt);
			akt = '';
		} else akt += c;
	}
	if (akt) aus.push(akt);
	return aus;
}
const SEITEN = ['top', 'right', 'bottom', 'left'] as const;
const STILE = /^(none|hidden|solid|dashed|dotted|double|groove|ridge|inset|outset)$/;
const BREITE = /^(-?[\d.]+(px|rem|em)?|thin|medium|thick|calc\(.*\)|var\(--g-[a-z0-9-]*(w|width|border)[a-z0-9-]*\))$/;
function vierWerte(v: string): Record<(typeof SEITEN)[number], string> {
	const w = woerter(v);
	const [t, r = t, b = t, l = r] = w;
	return { top: t, right: r, bottom: b, left: l };
}
function rahmenTeile(v: string): { width: string; style: string; color: string } {
	if (/^(none|0)$/.test(v.trim())) return { width: '0', style: 'none', color: 'currentcolor' };
	let width = 'medium';
	let style = 'none';
	const farbe: string[] = [];
	for (const w of woerter(v)) {
		if (STILE.test(w)) style = w;
		else if (BREITE.test(w)) width = w;
		else farbe.push(w);
	}
	return { width, style, color: farbe.join(' ') || 'currentcolor' };
}
function longhands(p: string, v: string): Array<[string, string]> {
	if (p === 'background') {
		const w = woerter(v);
		const farbe = w.find((x) => !/^(url|linear-gradient|radial-gradient|no-repeat|repeat|center|top|bottom|left|right|cover|contain|\/)/.test(x));
		return [['background-color', w.length === 1 ? v : (farbe ?? 'transparent')]];
	}
	if (p === 'border' || p === 'border-top' || p === 'border-right' || p === 'border-bottom' || p === 'border-left') {
		const t = rahmenTeile(v);
		const seiten = p === 'border' ? SEITEN : [p.slice(7) as (typeof SEITEN)[number]];
		return seiten.flatMap((s) => [
			[`border-${s}-width`, t.width],
			[`border-${s}-style`, t.style],
			[`border-${s}-color`, t.color]
		] as Array<[string, string]>);
	}
	if (p === 'border-color' || p === 'border-width' || p === 'border-style') {
		const art = p.slice(7);
		const w = vierWerte(v);
		return SEITEN.map((s) => [`border-${s}-${art}`, w[s]] as [string, string]);
	}
	if (p === 'padding' || p === 'margin') {
		const w = vierWerte(v);
		return SEITEN.map((s) => [`${p}-${s}`, w[s]] as [string, string]);
	}
	if (p === 'padding-block' || p === 'margin-block') {
		const [a, b = a] = woerter(v);
		const basis = p.split('-')[0];
		return [[`${basis}-top`, a], [`${basis}-bottom`, b]];
	}
	if (p === 'padding-inline' || p === 'margin-inline') {
		const [a, b = a] = woerter(v);
		const basis = p.split('-')[0];
		return [[`${basis}-left`, a], [`${basis}-right`, b]];
	}
	if (p === 'overflow') {
		const [x, y = x] = woerter(v);
		return [['overflow-x', x], ['overflow-y', y]];
	}
	if (p === 'word-wrap') return [['overflow-wrap', v]];
	return [[p, v]];
}

const VERERBT = new Set(['color', 'font-family', 'font-size', 'font-weight', 'text-transform', 'letter-spacing', 'line-height', 'white-space', 'overflow-wrap', 'word-break', 'font-variant-numeric', 'text-align']);

function inlineDecls(k: Knoten): Array<[string, string, boolean]> {
	return k.attrs.style ? deklarationen(k.attrs.style) : [];
}

/** Scope-Hashes, die irgendwo im Baum vorkommen (= Komponenten, deren CSS die Seite lädt). */
function hashesIm(k: Knoten): Set<string> {
	let w: Knoten = k;
	while (w.eltern) w = w.eltern;
	const aus = new Set<string>();
	(function lauf(n: Knoten) {
		for (const c of klassen(n)) if (/^svelte-[a-z0-9]+$/.test(c)) aus.add(c);
		n.kinder.forEach(lauf);
	})(w);
	return aus;
}

/** Eigener (nicht vererbter) Wert aller Longhands dieses Elements nach der Kaskade. */
export function eigeneWerte(q: Quellen, k: Knoten, ctx: Kontext): { werte: Record<string, string>; quellen: Record<string, string> } {
	const regeln: Regel[] = [...q.app];
	for (const h of hashesIm(k)) {
		const komp = q.komponenten.get(h);
		if (komp) regeln.push(...komp.regeln);
	}
	type Treffer = { wichtig: boolean; ebene: number; spez: number; ordnung: number; p: string; v: string; sel: string };
	const treffer: Treffer[] = [];
	for (const r of regeln) {
		if (!r.media.every((m) => mediaPasst(m, ctx))) continue;
		const [ok, spez] = selektorPasst(r.selektor, k, ctx);
		if (!ok) continue;
		for (const [p, v, wichtig] of r.decls) {
			if (p.startsWith('--')) continue;
			treffer.push({ wichtig, ebene: r.layer ? 0 : 1, spez, ordnung: r.ordnung, p, v, sel: r.selektor + (r.media.length ? ` @media ${r.media.join(' & ')}` : '') });
		}
	}
	for (const [p, v, wichtig] of inlineDecls(k)) treffer.push({ wichtig, ebene: 2, spez: 1e9, ordnung: 1e9, p, v, sel: 'style=""' });
	treffer.sort((a, b) => Number(a.wichtig) - Number(b.wichtig) || (a.wichtig ? b.ebene - a.ebene : a.ebene - b.ebene) || a.spez - b.spez || a.ordnung - b.ordnung);
	const werte: Record<string, string> = {};
	const quellen: Record<string, string> = {};
	for (const t of treffer)
		for (const [lp, lv] of longhands(t.p, t.v)) {
			werte[lp] = lv;
			quellen[lp] = t.sel;
		}
	return { werte, quellen };
}

/** Token auflösen (var() mit Ersatzwert, verschachtelt), kleingeschrieben, Leerraum normalisiert. */
export function aufloesen(q: Quellen, wert: string, theme: Theme): string {
	const tok = theme === 'dunkel' ? q.dunkel : q.hell;
	let v = wert;
	for (let i = 0; i < 12 && /var\(/.test(v); i++) {
		v = v.replace(/var\(\s*(--[a-z0-9-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)/gi, (_, n: string, ersatz?: string) => tok[n] ?? ersatz?.trim() ?? `UNDEFINIERT(${n})`);
	}
	return v.replace(/\s+/g, ' ').replace(/\(\s*/g, '(').replace(/\s*\)/g, ')').replace(/\s*,\s*/g, ', ').trim().toLowerCase();
}

/** Berechneter, Token-aufgelöster Wert einer Eigenschaft (mit Vererbung für Schrift/Farbe). */
export function stil(q: Quellen, k: Knoten, prop: string, ctx: Kontext): string | undefined {
	for (let n: Knoten | null = k; n && n.tag !== '#root'; n = n.eltern) {
		const { werte } = eigeneWerte(q, n, ctx);
		let v = werte[prop];
		if (v !== undefined && v.toLowerCase() !== 'inherit') {
			if (/^currentcolor$/i.test(v.trim())) return stil(q, n, 'color', ctx);
			return aufloesen(q, v, ctx.theme);
		}
		if (v === undefined && !VERERBT.has(prop)) return undefined;
	}
	return undefined;
}

/** Woher kommt der Wert? (für Fehlermeldungen) */
export function herkunft(q: Quellen, k: Knoten, prop: string, ctx: Kontext): string {
	for (let n: Knoten | null = k; n && n.tag !== '#root'; n = n.eltern) {
		const { werte, quellen } = eigeneWerte(q, n, ctx);
		if (werte[prop] !== undefined && werte[prop].toLowerCase() !== 'inherit') return `${quellen[prop]} → ${werte[prop]}${n === k ? '' : ` (geerbt von <${n.tag} class="${n.attrs.class ?? ''}">)`}`;
		if (!VERERBT.has(prop)) break;
	}
	return '(kein Wert gesetzt)';
}

export const token = (q: Quellen, name: string, theme: Theme = 'hell') => aufloesen(q, `var(${name})`, theme);

export function px(v: string | undefined): number {
	if (!v) return NaN;
	const m = /^(-?[\d.]+)px$/.exec(v.trim());
	return m ? Number(m[1]) : NaN;
}

// ── Farbe/Kontrast ───────────────────────────────────────────────────────────────────

export type Rgba = [number, number, number, number];
export function farbe(v: string | undefined): Rgba | null {
	if (!v) return null;
	const s = v.trim().toLowerCase();
	if (s === 'transparent') return [0, 0, 0, 0];
	if (s === 'white') return [255, 255, 255, 1];
	if (s === 'black') return [0, 0, 0, 1];
	let m: RegExpExecArray | null;
	if ((m = /^#([0-9a-f]{3,8})$/.exec(s))) {
		let h = m[1];
		if (h.length === 3 || h.length === 4) h = [...h].map((c) => c + c).join('');
		const n = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
		return [n[0], n[1], n[2], h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1];
	}
	if ((m = /^rgba?\(([^)]*)\)$/.exec(s))) {
		const teile = m[1].split(/[\s,/]+/).filter(Boolean).map((x) => (x.endsWith('%') ? (Number(x.slice(0, -1)) / 100) * 255 : Number(x)));
		return [teile[0], teile[1], teile[2], teile[3] ?? 1];
	}
	return null;
}
/** Farbe `oben` (ggf. transparent) über deckender `unten` mischen. */
export function ueber(oben: Rgba, unten: Rgba): Rgba {
	const a = oben[3];
	return [0, 1, 2].map((i) => oben[i] * a + unten[i] * (1 - a)).concat(1) as Rgba;
}
export function kontrast(a: Rgba, b: Rgba): number {
	const lum = (c: Rgba) => {
		const [r, g, bl] = [c[0], c[1], c[2]].map((x) => x / 255).map((s) => (s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
	};
	const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
	return (x + 0.05) / (y + 0.05);
}
