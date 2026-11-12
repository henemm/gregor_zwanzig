// doc-compliance-test
// Issue #2913 (Epic #2791) — Regeln des Bausteine-Wächters, ADR-0112
// („Oberflächen nur aus Design-System-Bausteinen und Tokens“).
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md — AC-1 bis AC-7.
// Ausgeführt von bausteine_waechter.test.ts (CI-Job frontend-test); Quellcode ist hier Gegenstand
// der Regel (Ausnahme der Test-Politik wie harte_farben_waechter).
//
// Regel (a) Aufbau — nur für Dateien in SEITEN_SCOPE (Opt-in, wächst mit jeder Scheibe):
//   verboten: <style>, style=, style:-Direktive, Tailwind-Utility-Klassen (statisch, im Ausdruck,
//   per class:-Direktive, auch auf Komponenten), rohe <button|input|select|textarea|table>,
//   Komponenten-Importe außerhalb $lib/components/{atoms,molecules,organisms} bzw.
//   FREIGEGEBENE_KOMPOSITIONEN. Prüfung über den Svelte-AST (svelte/compiler), nicht per Regex.
// Regel (b) Tokens — <style> aller Dateien in atoms/molecules/organisms: Farbe, Abstand, Größe,
//   Radius, Schrift und Schatten nur über var(--g-*). Erlaubt: 0, 1px bei Rahmen/Kontur, %, fr,
//   auto, vh/vw, calc/min/max über Tokens, unitlose Zahlen. AUSNAHMEN = Ist-Stand je Datei
//   (Ratsche, darf nur sinken), neue Baustein-Dateien starten bei 0.
// Neue-Datei-Regel — jede .svelte unter routes/ oder lib/components/** außerhalb der
//   Baustein-Ordner steht in SEITEN_SCOPE oder in BESTAND; BESTAND darf nur sinken
//   (BESTAND_OBERGRENZE = heutige Länge, verwaiste Einträge sind rot).
// Ausnahme: `audit:exempt` mit Begründung in derselben Zeile oder der Zeile davor; ohne
//   Begründung zählt der Verstoß trotzdem und es kommt ein eigener Verstoß (regel 'exempt') hinzu.
//
// Bekannte Restlücken (dokumentiert in docs/reference/gates_und_ratschen.md):
//   - Regel (b) liest CSS-Deklarationen per Regex (kein CSS-Parser); unitlose Zahlen
//     (font-weight, line-height) und ms/s gelten nicht als Verstoß.
//   - Tailwind-Erkennung über Präfixliste: eigene Klassennamen mit Utility-Präfix (z. B. „text-…“)
//     gelten als Utility; Klassen aus Variablen (class={cls}) ohne String-Literal sind unsichtbar.
//   - Dynamische Komponenten (<svelte:component>, {@const C = …}) und dynamische import() sind nicht erfasst.
import { readdirSync, statSync, readFileSync, existsSync } from 'node:fs';
import { join, relative, posix } from 'node:path';
import { parse } from 'svelte/compiler';

export type Verstoss = {
	datei: string;
	regel: 'a' | 'b' | 'neu' | 'exempt' | 'bestand';
	zeile: number;
	art: string;
	meldung: string;
};
export type Ausnahmen = Record<string, { n: number; grund: string }>;
export type Konfig = {
	SEITEN_SCOPE: string[];
	FREIGEGEBENE_KOMPOSITIONEN: string[];
	BESTAND: string[];
	BESTAND_OBERGRENZE: number;
	AUSNAHMEN: Ausnahmen;
};

const BAUSTEIN_ORDNER = /^lib\/components\/(atoms|molecules|organisms)\//;
const ROHE_ELEMENTE = new Set(['button', 'input', 'select', 'textarea', 'table']);

// ------------------------------------------------------------------ audit:exempt

/** Begründung hinter `audit:exempt` (ohne Kommentarzeichen); leer = keine Begründung. */
function exemptBegruendung(zeile: string): string | null {
	const i = zeile.indexOf('audit:exempt');
	if (i < 0) return null;
	const rest = zeile
		.slice(i + 'audit:exempt'.length)
		.replace(/-->|\*\/|<\/?[a-z][^>]*>/gi, ' ')
		.replace(/^[\s:—–-]+/, '')
		.trim();
	return rest;
}

/** Begründung: mindestens 10 Buchstaben, davon ein Wort mit mindestens 3 Buchstaben. */
export function begruendungReicht(b: string): boolean {
	return /\p{L}{3,}/u.test(b) && (b.match(/\p{L}/gu)?.length ?? 0) >= 10;
}

/** 'ok' = begründete Ausnahme, 'ohne' = Marker ohne Begründung, null = kein Marker (Zeile oder Vorzeile). */
function exemptStatus(zeilen: string[], zeile: number): 'ok' | 'ohne' | null {
	let gefunden: 'ok' | 'ohne' | null = null;
	for (const z of [zeile, zeile - 1]) {
		if (z < 1 || z > zeilen.length) continue;
		const b = exemptBegruendung(zeilen[z - 1]);
		if (b === null) continue;
		if (begruendungReicht(b)) return 'ok';
		gefunden = 'ohne';
	}
	return gefunden;
}

function zeileAn(text: string, offset: number): number {
	let n = 1;
	for (let i = 0; i < offset && i < text.length; i++) if (text.charCodeAt(i) === 10) n++;
	return n;
}

/** Wendet audit:exempt an: begründet ⇒ toleriert; ohne Begründung ⇒ bleibt + eigener Verstoß. */
function mitExempt(datei: string, text: string, roh: Verstoss[]): Verstoss[] {
	const zeilen = text.split('\n');
	const out: Verstoss[] = [];
	for (const v of roh) {
		const s = exemptStatus(zeilen, v.zeile);
		if (s === 'ok') continue;
		out.push(v);
		if (s === 'ohne') {
			out.push({
				datei,
				regel: 'exempt',
				zeile: v.zeile,
				art: 'audit:exempt ohne Begründung',
				meldung: `${datei}:${v.zeile}: audit:exempt ohne Begründung (Regel (${v.regel})) — Begründung ergänzen oder Verstoß beheben (ADR-0112)`
			});
		}
	}
	return out;
}

// ------------------------------------------------------------------ Regel (a) Aufbau

const TW_GENAU = new Set(
	(
		'flex grid block inline inline-block inline-flex inline-grid hidden contents flow-root table table-row table-cell ' +
		'relative absolute fixed sticky static truncate italic not-italic underline overline line-through no-underline ' +
		'uppercase lowercase capitalize normal-case visible invisible collapse grow shrink container sr-only not-sr-only ' +
		'border rounded shadow outline ring transition transform filter resize isolate antialiased subpixel-antialiased ' +
		'tabular-nums ordinal slashed-zero lining-nums oldstyle-nums proportional-nums prose ' +
		'backface-hidden backface-visible transform-gpu transform-cpu transform-none'
	).split(' ')
);
const TW_PRAEFIX = new RegExp(
	'^(?:[mp][trblxyse]?|gap|gap-[xy]|space-[xy]|w|h|min-w|min-h|max-w|max-h|size|text|font|leading|tracking|bg|' +
		'border|rounded|shadow|ring|ring-offset|outline|outline-offset|fill|stroke|opacity|z|top|left|right|bottom|' +
		'inset|inset-[xy]|start|end|items|justify|justify-items|justify-self|content|self|place|order|col|col-span|' +
		'row|row-span|grid-cols|grid-rows|grid-flow|auto-cols|auto-rows|flex|basis|overflow|overflow-[xy]|overscroll|' +
		'whitespace|break|cursor|select|pointer-events|transition|duration|ease|delay|animate|translate|translate-[xy]|' +
		'scale|rotate|skew|origin|aspect|object|decoration|underline-offset|line-clamp|divide|divide-[xy]|from|via|to|' +
		'backdrop|blur|drop-shadow|list|indent|align|columns|scroll|snap|touch|will-change|accent|caret|appearance|' +
		'float|clear|box|hyphens|placeholder|bg-gradient|grayscale|invert|sepia|saturate|contrast|brightness|' +
		'hue-rotate|mix-blend|bg-blend|shrink|grow|sr|table|caption|transform|backface|perspective|mask|' +
		'field-sizing|scheme|wrap|contain|prose|container|inset-ring|inset-shadow|text-shadow|forced-color-adjust|' +
		'break-before|break-after|break-inside|box-decoration|isolation|object|line|tab|counter|font-stretch)-'
);

/** Ist das ein Tailwind-Utility (inkl. Varianten `md:`/`hover:`/`dark:`, `!`, `-`, `[…]`)? */
export function istUtility(klasse: string): boolean {
	let k = klasse.trim();
	if (!k) return false;
	// Varianten abtrennen (Doppelpunkte außerhalb eckiger Klammern)
	let tiefe = 0;
	let letzter = -1;
	for (let i = 0; i < k.length; i++) {
		if (k[i] === '[') tiefe++;
		else if (k[i] === ']') tiefe--;
		else if (k[i] === ':' && tiefe === 0) letzter = i;
	}
	if (letzter >= 0) k = k.slice(letzter + 1);
	k = k.replace(/^!/, '').replace(/^-/, '');
	if (/^\[.+\]$/.test(k)) return true; // beliebige Eigenschaft [mask-type:luminance]
	if (k.startsWith('@')) return true; // Container-Queries (@container, @container/name)
	return TW_GENAU.has(k) || TW_PRAEFIX.test(k);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Knoten = { type: string; start: number; end: number; [k: string]: any };

function* knoten(wert: unknown): Generator<Knoten> {
	if (Array.isArray(wert)) {
		for (const w of wert) yield* knoten(w);
	} else if (wert && typeof wert === 'object') {
		const k = wert as Knoten;
		if (typeof k.type === 'string') yield k;
		for (const [schluessel, w] of Object.entries(k)) {
			if (schluessel === 'parent' || schluessel === 'loc' || schluessel === 'metadata') continue;
			if (w && typeof w === 'object') yield* knoten(w);
		}
	}
}

/** Alle String-Bestandteile eines Klassen-Ausdrucks (Literale, Template-Teile, Objekt-Schlüssel). */
function klassenTexte(ausdruck: unknown): string[] {
	const out: string[] = [];
	for (const n of knoten(ausdruck)) {
		if (n.type === 'Literal' && typeof n.value === 'string') out.push(n.value);
		else if (n.type === 'TemplateElement') out.push(String(n.value?.cooked ?? n.value?.raw ?? ''));
		else if (n.type === 'Property' && !n.computed && n.key?.type === 'Identifier') out.push(String(n.key.name));
	}
	return out;
}

function attributTexte(wert: unknown): string[] {
	if (wert === true || wert == null) return [];
	const teile = Array.isArray(wert) ? wert : [wert];
	const out: string[] = [];
	for (const t of teile as Knoten[]) {
		if (t.type === 'Text') out.push(String(t.data ?? t.raw ?? ''));
		else if (t.type === 'ExpressionTag') out.push(...klassenTexte(t.expression));
	}
	return out;
}

/**
 * Ist `quelle` (aus `datei`, Pfad relativ zu src/) ein Komponenten-Import außerhalb der Baustein-Ordner?
 * Pfade werden normalisiert ($lib/components/atoms/../shared → lib/components/shared), relative Importe
 * gegen die Datei aufgelöst; Komponente = `.svelte`-Datei oder alles unter lib/components/ (auch Barrels).
 * Rückgabe: normalisiertes Ziel bei Verstoß, sonst null.
 */
export function fremderKomponentenImport(datei: string, quelle: string, freigegeben: string[] = []): string | null {
	let ziel: string;
	if (quelle.startsWith('$lib/')) ziel = posix.normalize('lib/' + quelle.slice('$lib/'.length));
	else if (quelle.startsWith('./') || quelle.startsWith('../')) ziel = posix.normalize(posix.join(posix.dirname(datei), quelle));
	else return null; // Pakete, $app/… — keine Komponenten aus dem Projekt (Restlücke: Komponenten aus npm-Paketen)
	ziel = ziel.replace(/\/$/, '');
	const komponente = ziel.endsWith('.svelte') || ziel === 'lib/components' || ziel.startsWith('lib/components/');
	if (!komponente) return null;
	if (/^lib\/components\/(atoms|molecules|organisms)(\/|$)/.test(ziel)) return null;
	if (freigegeben.includes(quelle) || freigegeben.includes(ziel)) return null;
	return ziel;
}

/** Regel (a) Aufbau für eine Seiten-/Reiter-Datei. Pfad relativ zu src/. */
export function pruefeSeitenDatei(datei: string, text: string, freigegeben: string[] = []): Verstoss[] {
	const roh: Verstoss[] = [];
	const v = (zeile: number, art: string) =>
		roh.push({ datei, regel: 'a', zeile, art, meldung: `${datei}:${zeile}: Regel (a) Aufbau — ${art} (ADR-0112: nur Bausteine)` });
	let ast: Knoten;
	try {
		ast = parse(text, { modern: true }) as unknown as Knoten;
	} catch (e) {
		v(1, `Datei nicht parsebar: ${(e as Error).message.split('\n')[0]}`);
		return roh;
	}
	if (ast.css) v(zeileAn(text, ast.css.start), '<style>-Block');
	for (const skript of [ast.instance, ast.module]) {
		for (const s of (skript?.content?.body ?? []) as Knoten[]) {
			if (s.type !== 'ImportDeclaration' && s.type !== 'ExportNamedDeclaration' && s.type !== 'ExportAllDeclaration') continue;
			const quelle = String(s.source?.value ?? '');
			if (!quelle) continue;
			const fremd = fremderKomponentenImport(datei, quelle, freigegeben);
			if (fremd) v(zeileAn(text, s.start), `Komponenten-import außerhalb atoms/molecules/organisms: ${quelle}${fremd === quelle ? '' : ` (→ ${fremd})`}`);
		}
	}
	for (const n of knoten(ast.fragment)) {
		if (n.type === 'HtmlTag') {
			v(zeileAn(text, n.start), '{@html} in einer Seite (Aufbau und Styling nicht prüfbar)');
			continue;
		}
		const element = n.type === 'RegularElement' || n.type === 'Component' || n.type === 'SvelteElement' || n.type === 'SvelteComponent';
		if (!element) continue;
		if (n.type === 'RegularElement' && ROHE_ELEMENTE.has(String(n.name))) {
			v(zeileAn(text, n.start), `rohes <${n.name}> statt Baustein`);
		}
		if (n.type === 'RegularElement' && n.name === 'style') {
			// <style> außerhalb der Top-Ebene, z. B. in <svelte:head> — ast.css sieht das nicht
			v(zeileAn(text, n.start), '<style>-Element (z. B. in <svelte:head>)');
		}
		if (n.type === 'SvelteElement') {
			v(zeileAn(text, n.start), '<svelte:element> statt Baustein (Tag zur Laufzeit, rohe Elemente nicht ausschließbar)');
		}
		for (const a of (n.attributes ?? []) as Knoten[]) {
			const z = zeileAn(text, a.start);
			if (a.type === 'SpreadAttribute') {
				const schluessel = ((a.expression?.type === 'ObjectExpression' ? a.expression.properties : []) as Knoten[])
					.map((p) => String(p.key?.name ?? p.key?.value ?? ''))
					.filter((k) => k === 'class' || k === 'style');
				if (schluessel.length) v(z, `Spread mit ${schluessel.join('/')} (umgeht class/style-Prüfung)`);
			} else if (a.type === 'StyleDirective') v(z, `style:${a.name}-Direktive`);
			else if (a.type === 'Attribute' && a.name === 'style') v(z, 'style=-Attribut');
			else if (a.type === 'ClassDirective' && istUtility(String(a.name))) v(z, `Tailwind-Utility class:${a.name}`);
			else if (a.type === 'Attribute' && a.name === 'class') {
				const utils = attributTexte(a.value)
					.flatMap((t) => t.split(/\s+/))
					.filter(istUtility);
				if (utils.length) v(z, `Tailwind-Utility-Klassen: ${[...new Set(utils)].join(' ')}`);
			}
		}
	}
	return mitExempt(datei, text, roh);
}

// ------------------------------------------------------------------ Regel (b) Tokens

const RAHMEN_EIGENSCHAFT = /^(?:border(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?(?:-width)?|outline(?:-width)?|column-rule(?:-width)?)$/;
const FARBNAMEN = /\b(?:white|black|red|green|blue|gray|grey|orange|yellow|purple|pink|brown|silver|navy)\b/i;
/** Eigenschaften, in denen ein Farbname eine Farbe ist — auch Kurzschreibweisen (border: 1px solid red). */
const FARB_EIGENSCHAFT =
	/^(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?(?:-color)?|outline(?:-color)?|box-shadow|text-shadow|fill|stroke|column-rule(?:-color)?|text-decoration(?:-color)?|caret-color|accent-color)$/;

/** Gründe, warum eine CSS-Deklaration nicht nur über Tokens läuft (leer = in Ordnung). */
function tokenGruende(eigenschaft: string, wertRoh: string): string[] {
	const wert = wertRoh.replace(/var\(\s*--g-[\w-]+\s*\)/g, 'TOKEN');
	const gruende: string[] = [];
	if (/#[0-9a-fA-F]{3,8}\b/.test(wert)) gruende.push('Hex-Farbe');
	if (/\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color-mix)\(/i.test(wert)) gruende.push('Farbfunktion');
	if (FARB_EIGENSCHAFT.test(eigenschaft) && FARBNAMEN.test(wert)) gruende.push('Farbname');
	if (/var\(\s*--(?!g-)/i.test(wert)) gruende.push('Variable außerhalb --g-*');
	const laengen = [...wert.matchAll(/(?<![\w.-])(-?\d*\.?\d+)(px|rem|em|pt)\b/gi)].filter(([, zahl, einheit]) => {
		if (Number(zahl) === 0) return false;
		if (einheit.toLowerCase() === 'px' && Math.abs(Number(zahl)) === 1 && RAHMEN_EIGENSCHAFT.test(eigenschaft)) return false;
		return true;
	});
	if (laengen.length) gruende.push(`Maß ${laengen.map((l) => l[0]).join(' ')}`);
	if (/^font(?:-family)?$/.test(eigenschaft) && !/^(?:TOKEN|inherit|initial|unset)$/.test(wert.trim())) {
		if (eigenschaft === 'font-family' || /['"]|serif|sans|mono|system-ui/i.test(wert)) gruende.push('Schrift ohne Token');
	}
	return gruende;
}

/** Deklarationen `eigenschaft: wert` in einem CSS-Text (Kommentare/@-Präludien bereits neutralisiert). */
function* deklarationen(css: string): Generator<{ index: number; eigenschaft: string; wert: string }> {
	// Name mit Ziffern/Unterstrich, damit auch Custom Properties wie `--g-s-2: 12px` gelesen werden.
	const dekl = /([a-zA-Z0-9_-]+)\s*:\s*([^;{}]+?)\s*(?=[;}]|$)/g;
	for (let d = dekl.exec(css); d; d = dekl.exec(css)) {
		const vor = css[d.index - 1];
		if (vor !== undefined && !/[\s;{"']/.test(vor)) continue; // Selektor-Pseudoklasse, keine Deklaration
		yield { index: d.index, eigenschaft: d[1].toLowerCase(), wert: d[2] };
	}
}

/** Stil-Texte eines Attributwerts; dynamische Teile werden zu „9“ (eine Zahl ohne Token). */
function stilTexte(wert: unknown): string[] {
	if (wert === true || wert == null) return [];
	const teile = (Array.isArray(wert) ? wert : [wert]) as Knoten[];
	let zusammen = '';
	const literale: string[] = [];
	for (const t of teile) {
		if (t.type === 'Text') zusammen += String(t.data ?? t.raw ?? '');
		else if (t.type === 'ExpressionTag') {
			const e = t.expression as Knoten;
			if (e?.type === 'TemplateLiteral') zusammen += (e.quasis as Knoten[]).map((q) => String(q.value?.cooked ?? '')).join('9');
			else if (e?.type === 'Literal' && typeof e.value === 'string') zusammen += e.value;
			else {
				zusammen += '9';
				literale.push(...klassenTexte(e));
			}
		}
	}
	return [zusammen, ...literale];
}

/**
 * Regel (b) Tokens für eine Baustein-Datei, je Deklaration ein Verstoß: <style>-Block,
 * style=-Attribut, style:-Direktiven und Tailwind-Arbitrary-Werte mit Hex/px (z. B. p-[12px]).
 */
export function zaehleTokenVerstoesse(datei: string, text: string): Verstoss[] {
	const roh: Verstoss[] = [];
	const melde = (zeile: number, eigenschaft: string, wert: string, gruende: string[]) =>
		roh.push({
			datei,
			regel: 'b',
			zeile,
			art: `${eigenschaft}: ${gruende.join(', ')}`,
			meldung: `${datei}:${zeile}: Regel (b) Tokens — ${eigenschaft}: ${wert.trim()} (${gruende.join(', ')}; nur var(--g-*), ADR-0112)`
		});
	const re = /<style\b[^>]*>([\s\S]*?)<\/style>/g;
	for (let m = re.exec(text); m; m = re.exec(text)) {
		const basis = m.index + m[0].indexOf('>') + 1;
		// Kommentare und @-Regel-Präludien unschädlich machen, Zeilenumbrüche (Zeilennummern) erhalten.
		const css = m[1]
			.replace(/\/\*[\s\S]*?\*\//g, (s) => s.replace(/[^\n]/g, ' '))
			.replace(/@[a-z-]+[^{;]*/gi, (s) => s.replace(/[^\n]/g, ' '));
		for (const d of deklarationen(css)) {
			const gruende = tokenGruende(d.eigenschaft, d.wert);
			if (gruende.length) melde(zeileAn(text, basis + d.index), d.eigenschaft, d.wert, gruende);
		}
	}
	let ast: Knoten | null = null;
	try {
		ast = parse(text, { modern: true }) as unknown as Knoten;
	} catch {
		ast = null; // nicht parsebar: nur der <style>-Block zählt (svelte-check meldet den Syntaxfehler)
	}
	if (ast) {
		for (const n of knoten(ast.fragment)) {
			for (const a of (n.attributes ?? []) as Knoten[]) {
				const zeile = zeileAn(text, a.start);
				if (a.type === 'Attribute' && a.name === 'style') {
					for (const s of stilTexte(a.value))
						for (const d of deklarationen(s)) {
							const gruende = tokenGruende(d.eigenschaft, d.wert);
							if (gruende.length) melde(zeile, d.eigenschaft, d.wert, gruende);
						}
				} else if (a.type === 'StyleDirective') {
					const eigenschaft = String(a.name).toLowerCase();
					for (const s of stilTexte(a.value)) {
						const gruende = tokenGruende(eigenschaft, s);
						if (gruende.length) {
							melde(zeile, `style:${eigenschaft}`, s, gruende);
							break;
						}
					}
				} else if (a.type === 'Attribute' && a.name === 'class') {
					const willkuer = attributTexte(a.value)
						.flatMap((t) => t.split(/\s+/))
						.filter((k) => /\[[^\]]*(?:#[0-9a-fA-F]{3,8}|\d(?:px|rem|em|pt))[^\]]*\]/.test(k));
					if (willkuer.length) melde(zeile, 'class', willkuer.join(' '), ['Tailwind-Wert ohne Token']);
				}
			}
		}
	}
	return mitExempt(datei, text, roh);
}

// ------------------------------------------------------------------ Ratsche, Neue-Datei-Regel, Bestand

/** Ist-Stand je Baustein-Datei gegen AUSNAHMEN (Obergrenze; fehlender Eintrag = 0). */
export function pruefeRatsche(ist: Record<string, number>, ausnahmen: Ausnahmen): string[] {
	const fehler: string[] = [];
	for (const [datei, n] of Object.entries(ist).sort()) {
		const grenze = ausnahmen[datei]?.n ?? 0;
		if (n > grenze) {
			fehler.push(
				grenze === 0
					? `${datei}: ${n} Token-Verstoß/Verstöße (Regel (b)) — neue Baustein-Dateien starten bei 0, Werte auf var(--g-*) umstellen`
					: `${datei}: ${n} Token-Verstöße > Obergrenze ${grenze} (Regel (b), Ratsche darf nur sinken)`
			);
		}
	}
	return fehler;
}

const istBaustein = (datei: string) => BAUSTEIN_ORDNER.test(datei);
const imGeltungsbereich = (datei: string) => (datei.startsWith('routes/') || datei.startsWith('lib/components/')) && !istBaustein(datei);

/** Jede .svelte unter routes/ bzw. lib/components/** (außer Bausteinen) steht in SEITEN_SCOPE oder BESTAND. */
export function pruefeNeueDateien(svelteDateien: string[], seitenScope: string[], bestand: string[]): string[] {
	const erfasst = new Set([...seitenScope, ...bestand]);
	return svelteDateien
		.filter((d) => d.endsWith('.svelte') && imGeltungsbereich(d) && !erfasst.has(d))
		.sort()
		.map(
			(d) =>
				`${d}: neue Seiten-/Komponenten-Datei außerhalb atoms/molecules/organisms — in SEITEN_SCOPE eintragen (Regel (a) gilt dann) oder als Baustein anlegen (Neue-Datei-Regel, ADR-0112)`
		);
}

/** BESTAND darf nur sinken: höchstens BESTAND_OBERGRENZE Einträge, keine verwaisten, keine doppelten. */
export function pruefeBestandsliste(bestand: string[], vorhandene: string[], obergrenze: number): string[] {
	const fehler: string[] = [];
	if (bestand.length > obergrenze) {
		fehler.push(`BESTAND hat ${bestand.length} Einträge > Obergrenze ${obergrenze} — der Bestand darf nur sinken (neue Dateien in SEITEN_SCOPE)`);
	}
	const da = new Set(vorhandene);
	const gesehen = new Set<string>();
	for (const b of bestand) {
		if (gesehen.has(b)) fehler.push(`${b}: doppelt in BESTAND`);
		gesehen.add(b);
		if (!da.has(b)) fehler.push(`${b}: steht in BESTAND, existiert nicht mehr — Eintrag löschen und BESTAND_OBERGRENZE senken`);
	}
	return fehler;
}

function svelteDateien(wurzel: string, dir = wurzel, out: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		if (statSync(p).isDirectory()) {
			if (name === 'node_modules' || name === '__tests__') continue;
			svelteDateien(wurzel, p, out);
		} else if (name.endsWith('.svelte')) {
			out.push(relative(wurzel, p).split('\\').join('/'));
		}
	}
	return out;
}

/** Alle Regeln über einen Quellbaum (Pfade relativ zu src/). Leere Liste = grün. */
export function waechterLauf(srcWurzel: string, konfig: Konfig): string[] {
	const dateien = svelteDateien(srcWurzel).sort();
	const fehler: string[] = [];
	fehler.push(...pruefeNeueDateien(dateien, konfig.SEITEN_SCOPE, konfig.BESTAND));
	fehler.push(...pruefeBestandsliste(konfig.BESTAND, dateien, konfig.BESTAND_OBERGRENZE));
	for (const s of konfig.SEITEN_SCOPE) {
		if (konfig.BESTAND.includes(s)) fehler.push(`${s}: steht in SEITEN_SCOPE und BESTAND — aus BESTAND streichen`);
		if (istBaustein(s)) fehler.push(`${s}: Baustein-Dateien gehören nicht in SEITEN_SCOPE (für sie gilt Regel (b))`);
		const pfad = join(srcWurzel, s);
		if (!existsSync(pfad)) {
			fehler.push(`${s}: steht in SEITEN_SCOPE, existiert nicht`);
			continue;
		}
		for (const v of pruefeSeitenDatei(s, readFileSync(pfad, 'utf-8'), konfig.FREIGEGEBENE_KOMPOSITIONEN)) fehler.push(v.meldung);
	}
	const ist: Record<string, number> = {};
	for (const d of dateien.filter(istBaustein)) {
		const n = zaehleTokenVerstoesse(d, readFileSync(join(srcWurzel, d), 'utf-8')).length;
		if (n) ist[d] = n;
	}
	fehler.push(...pruefeRatsche(ist, konfig.AUSNAHMEN));
	for (const d of Object.keys(konfig.AUSNAHMEN)) {
		if (!dateien.includes(d)) fehler.push(`${d}: steht in AUSNAHMEN, existiert nicht — Eintrag löschen`);
	}
	return fehler;
}

/** Ist-Stand der Token-Verstöße aller Baustein-Dateien (für die Pflege von AUSNAHMEN). */
export function istStandBausteine(srcWurzel: string): Record<string, number> {
	const ist: Record<string, number> = {};
	for (const d of svelteDateien(srcWurzel).filter(istBaustein).sort()) {
		const n = zaehleTokenVerstoesse(d, readFileSync(join(srcWurzel, d), 'utf-8')).length;
		if (n) ist[d] = n;
	}
	return ist;
}

/** Bestandsliste (Dateien im Geltungsbereich der Neue-Datei-Regel) eines Quellbaums. */
export function bestandImBaum(srcWurzel: string): string[] {
	return svelteDateien(srcWurzel).filter(imGeltungsbereich).sort();
}

// ------------------------------------------------------------------ Konfiguration (Ist-Stand 2026-11-10)

/** Seiten/Reiter, für die Regel (a) gilt. Startet leer; jede Scheibe trägt ihre neuen Dateien ein. */
const SEITEN_SCOPE: string[] = [
	// #2913 Teil 2 (AC-17, K-1): Reiter „Wetter“ (Trip und Orts-Briefing) als dünne Seite.
	'lib/components/shared/WetterTab.svelte'
];

/** Freigegebene Kompositionen außerhalb der Baustein-Ordner (Import-Ausnahme für Regel (a)). */
const FREIGEGEBENE_KOMPOSITIONEN: string[] = [];

/** Heutige Seiten/Komponenten außerhalb der Baustein-Ordner (Stand 2026-11-10). Darf nur sinken. */
const BESTAND: string[] = [
	'lib/components/LocationForm.svelte',
	'lib/components/WeatherConfigDialog.svelte',
	'lib/components/account/PremiumSmsLinkCard.svelte',
	'lib/components/account/SpracheAuswahl.svelte',
	'lib/components/alerts-tab/AlertCooldownCard.svelte',
	'lib/components/alerts-tab/AlertMetricChannelsBlock.svelte',
	'lib/components/alerts-tab/AlertMetricLevelRow.svelte',
	'lib/components/alerts-tab/AlertMetricLevelTable.svelte',
	'lib/components/alerts-tab/AlertPreviewCard.svelte',
	'lib/components/alerts-tab/AlertQuietHoursCard.svelte',
	'lib/components/compare-new/CompareNewEditor.svelte',
	'lib/components/compare/AddReportCard.svelte',
	'lib/components/compare/CompareDetail.svelte',
	'lib/components/compare/CompareHourlyLayoutControls.svelte',
	'lib/components/compare/CompareTabs.svelte',
	'lib/components/compare/CreateGroupDialog.svelte',
	'lib/components/compare/LocationNewModal.svelte',
	'lib/components/compare/LocationPreviewMap.svelte',
	'lib/components/compare/steps/Step2Orte.svelte',
	'lib/components/edit/AccordionSection.svelte',
	'lib/components/edit/EditRouteSection.svelte',
	'lib/components/edit/EditStagesPanelNew.svelte',
	'lib/components/edit/EditStagesSection.svelte',
	'lib/components/edit/EditWeatherSection.svelte',
	'lib/components/edit/StageDateField.svelte',
	'lib/components/edit/StageTimeField.svelte',
	'lib/components/edit/WeatherSummaryCard.svelte',
	'lib/components/email-preview/EmailPreviewHeader.svelte',
	'lib/components/mobile/BottomNav.svelte',
	'lib/components/mobile/Drawer.svelte',
	'lib/components/mobile/DrawerGroup.svelte',
	'lib/components/mobile/DrawerItem.svelte',
	'lib/components/mobile/IconBtn.svelte',
	'lib/components/mobile/MBtn.svelte',
	'lib/components/mobile/MField.svelte',
	'lib/components/mobile/MIcon.svelte',
	'lib/components/mobile/MInput.svelte',
	'lib/components/mobile/MSwitch.svelte',
	'lib/components/mobile/MTab.svelte',
	'lib/components/mobile/MTabBar.svelte',
	'lib/components/mobile/MobileShell.svelte',
	'lib/components/mobile/NavIcon.svelte',
	'lib/components/mobile/ScreenScroll.svelte',
	'lib/components/mobile/Sheet.svelte',
	'lib/components/mobile/StageCardM.svelte',
	'lib/components/mobile/SubscriptionActionSheet.svelte',
	'lib/components/mobile/Toast.svelte',
	'lib/components/shared/AlarmeTab.svelte',
	'lib/components/shared/AlertChannelPicker.svelte',
	'lib/components/shared/AppFooter.svelte',
	'lib/components/shared/BriefingHistory.svelte',
	'lib/components/shared/ChannelToggle.svelte',
	'lib/components/shared/EditorStickyFooter.svelte',
	'lib/components/shared/MailInhaltCard.svelte',
	'lib/components/shared/OfflineSperre.svelte',
	'lib/components/shared/OutlookLayoutControls.svelte',
	'lib/components/shared/OutputLayoutEditor.svelte',
	'lib/components/shared/StandardwerteSpeichernKnopf.svelte',
	'lib/components/shared/TelegramKurzstilToggle.svelte',
	'lib/components/shared/VersandTab.svelte',
	'lib/components/shared/WeatherMetricsTab.svelte',
	'lib/components/shared/WetterMetrikenVersandPanel.svelte',
	'lib/components/shared/anlege-rahmen/AnlegeFortschritt.svelte',
	'lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte',
	'lib/components/shared/anlege-rahmen/AnlegeReiter.svelte',
	'lib/components/shared/dnd/DragHandle.svelte',
	'lib/components/shared/dnd/SortableList.svelte',
	'lib/components/shared/hub-kopf/HubKopf.svelte',
	'lib/components/shared/hub-reiterflaeche/HubReiterflaeche.svelte',
	'lib/components/shared/hub-uebersicht/HubUebersicht.svelte',
	'lib/components/shared/layout-tab/LTCapNote.svelte',
	'lib/components/shared/layout-tab/LTChannelPicker.svelte',
	'lib/components/shared/layout-tab/LTCutLine.svelte',
	'lib/components/shared/layout-tab/LayoutTab.svelte',
	'lib/components/shared/status-schild/StatusSchild.svelte',
	'lib/components/shared/subscription-header/SubscriptionHeader.svelte',
	'lib/components/shared/versand-tab/VTBriefingChannels.svelte',
	'lib/components/shared/versand-tab/VTLaufzeitRoute.svelte',
	'lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte',
	'lib/components/shared/versand-tab/VTNextBriefing.svelte',
	'lib/components/shared/versand-tab/VTSchedulePlan.svelte',
	'lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte',
	'lib/components/shared/weather-metrics-tab/DayWindowCard.svelte',
	'lib/components/shared/weather-metrics-tab/MultiSymbolMetricRow.svelte',
	'lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte',
	'lib/components/shared/weather-metrics-tab/ThresholdMetricRow.svelte',
	'lib/components/shared/weather-metrics-tab/WeatherV2Grundauswahl.svelte',
	'lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte',
	'lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte',
	'lib/components/shared/zustellung-tab/ZustellungTab.svelte',
	'lib/components/trip-detail/AboutOutputLayout.svelte',
	'lib/components/trip-detail/ActiveMetricRow.svelte',
	'lib/components/trip-detail/AlarmeScheduleTab.svelte',
	'lib/components/trip-detail/BriefingScheduleTab.svelte',
	'lib/components/trip-detail/BucketSection.svelte',
	'lib/components/trip-detail/BucketSectionOff.svelte',
	'lib/components/trip-detail/ChannelDot.svelte',
	'lib/components/trip-detail/ChannelLimitMarkers.svelte',
	'lib/components/trip-detail/DetailCard.svelte',
	'lib/components/trip-detail/FullProfile.svelte',
	'lib/components/trip-detail/HubOverview.svelte',
	'lib/components/trip-detail/PresetRow.svelte',
	'lib/components/trip-detail/ReportLine.svelte',
	'lib/components/trip-detail/StageDetailRow.svelte',
	'lib/components/trip-detail/StageList.svelte',
	'lib/components/trip-detail/TablePreview.svelte',
	'lib/components/trip-detail/TripHeader.svelte',
	'lib/components/trip-detail/TripStageRow.svelte',
	'lib/components/trip-detail/TripTabs.svelte',
	'lib/components/trip-detail/WaypointsPanel.svelte',
	'lib/components/trip-detail/WeatherV2Kanaele.svelte',
	'lib/components/trip-detail/waypoints/EtappenStrip.svelte',
	'lib/components/trip-detail/waypoints/MapCanvas.svelte',
	'lib/components/trip-detail/waypoints/PauseStageView.svelte',
	'lib/components/trip-detail/waypoints/ProfileEditor.svelte',
	'lib/components/trip-detail/waypoints/StageCard.svelte',
	'lib/components/trip-detail/waypoints/WaypointCard.svelte',
	'lib/components/trip-detail/waypoints/WaypointPin.svelte',
	'lib/components/trip-new/TripNewEditor.svelte',
	'lib/components/ui/SaveIndicator.svelte',
	'lib/components/ui/SprachUmschalter.svelte',
	'lib/components/ui/badge/badge.svelte',
	'lib/components/ui/btn/Btn.svelte',
	'lib/components/ui/card/card-action.svelte',
	'lib/components/ui/card/card-content.svelte',
	'lib/components/ui/card/card-description.svelte',
	'lib/components/ui/card/card-footer.svelte',
	'lib/components/ui/card/card-header.svelte',
	'lib/components/ui/card/card-title.svelte',
	'lib/components/ui/card/card.svelte',
	'lib/components/ui/checkbox/Checkbox.svelte',
	'lib/components/ui/dialog/dialog-close.svelte',
	'lib/components/ui/dialog/dialog-content.svelte',
	'lib/components/ui/dialog/dialog-description.svelte',
	'lib/components/ui/dialog/dialog-footer.svelte',
	'lib/components/ui/dialog/dialog-header.svelte',
	'lib/components/ui/dialog/dialog-overlay.svelte',
	'lib/components/ui/dialog/dialog-portal.svelte',
	'lib/components/ui/dialog/dialog-title.svelte',
	'lib/components/ui/dialog/dialog-trigger.svelte',
	'lib/components/ui/dialog/dialog.svelte',
	'lib/components/ui/dot/Dot.svelte',
	'lib/components/ui/elev-sparkline/ElevSparkline.svelte',
	'lib/components/ui/empty-state/EmptyState.svelte',
	'lib/components/ui/eyebrow/Eyebrow.svelte',
	'lib/components/ui/g-card/GCard.svelte',
	'lib/components/ui/input/input.svelte',
	'lib/components/ui/label/label.svelte',
	'lib/components/ui/pill/Pill.svelte',
	'lib/components/ui/popover/popover-content.svelte',
	'lib/components/ui/popover/popover-trigger.svelte',
	'lib/components/ui/popover/popover.svelte',
	'lib/components/ui/segmented/Segmented.svelte',
	'lib/components/ui/select/Select.svelte',
	'lib/components/ui/sidebar/BottomNav.svelte',
	'lib/components/ui/sidebar/KontoSheet.svelte',
	'lib/components/ui/sidebar/Sidebar.svelte',
	'lib/components/ui/table/table-body.svelte',
	'lib/components/ui/table/table-caption.svelte',
	'lib/components/ui/table/table-cell.svelte',
	'lib/components/ui/table/table-footer.svelte',
	'lib/components/ui/table/table-head.svelte',
	'lib/components/ui/table/table-header.svelte',
	'lib/components/ui/table/table-row.svelte',
	'lib/components/ui/table/table.svelte',
	'lib/components/ui/topo/TopoBg.svelte',
	'lib/components/ui/wicon/WIcon.svelte',
	'lib/components/ui/wordmark/Wordmark.svelte',
	'routes/+layout.svelte',
	'routes/+page.svelte',
	'routes/_design-system/+page.svelte',
	'routes/_design/+page.svelte',
	'routes/_home/EmptyKachel.svelte',
	'routes/_home/HomeHero.svelte',
	'routes/_home/StartklarCheckliste.svelte',
	'routes/_home/SubscriptionKachel.svelte',
	'routes/_start/Startseite.svelte',
	'routes/account/+page.svelte',
	'routes/admin/+page.svelte',
	'routes/archiv/+page.svelte',
	'routes/compare/+page.svelte',
	'routes/compare/[id]/+page.svelte',
	'routes/compare/[id]/edit/+page.svelte',
	'routes/compare/new/+page.svelte',
	'routes/email-preview-dev/+page.svelte',
	'routes/forgot-password/+page.svelte',
	'routes/gpx-upload/+page.svelte',
	'routes/hilfe/+page.svelte',
	'routes/locations/+page.svelte',
	'routes/login/+page.svelte',
	'routes/magic-link/+page.svelte',
	'routes/magic-link/verify/+page.svelte',
	'routes/register/+page.svelte',
	'routes/reset-password/+page.svelte',
	'routes/trips/+page.svelte',
	'routes/trips/[id]/+page.svelte',
	'routes/trips/[id]/edit/+page.svelte',
	'routes/trips/new/+page.svelte',
	'routes/verify-email/+page.svelte'
];

/** Obergrenze des Bestands (feste Zahl, nicht die Länge): neue Dateien gehen in SEITEN_SCOPE. */
// #2794 S3a Teil-PR 4a: 204 → 199 (CorridorEditor, CorridorEditorMobile, MetricCheckbox,
// MetricGroup, HorizonChip entfernt).
const BESTAND_OBERGRENZE = 199;

/** Token-Verstöße je Baustein-Datei (Ist-Stand 2026-11-10, ADR-0112). Darf nur sinken. */
const AUSNAHMEN: Ausnahmen = {
	'lib/components/atoms/AvatarStack.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/atoms/BackLink.svelte': { n: 8, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/atoms/Card.svelte': { n: 2, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/atoms/KV.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/atoms/SectionH.svelte': { n: 7, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/atoms/Stat.svelte': { n: 17, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/atoms/Switch.svelte': { n: 9, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/AlertRow.svelte': { n: 9, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/BegriffErklaerung.svelte': { n: 9, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/BriefingScheduleRow.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/BriefingTimelineRow.svelte': { n: 11, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/ChannelChip.svelte': { n: 7, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/ChannelRow.svelte': { n: 16, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/CompareLocationRow.svelte': { n: 8, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/CompareStatusRow.svelte': { n: 11, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/DatumFeld.svelte': { n: 41, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/DetailRow.svelte': { n: 9, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/Field.svelte': { n: 8, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/Infobox.svelte': { n: 5, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/QuickAction.svelte': { n: 8, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/ScoreToggle.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/SetupResumeCard.svelte': { n: 17, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/StagePill.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/Stat.svelte': { n: 11, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/StatusFilterPills.svelte': { n: 1, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/SubscriptionKebab.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/ThresholdRow.svelte': { n: 3, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/molecules/UhrzeitFeld.svelte': { n: 10, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/AlertsCard.svelte': { n: 6, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/ListActionsMenu.svelte': { n: 11, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/ListNameCell.svelte': { n: 7, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/ListTable.svelte': { n: 5, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/ListTableRow.svelte': { n: 16, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/MetricOffShelf.svelte': { n: 16, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/OutboxCard.svelte': { n: 5, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	// Fix-Loop 1 (#2913): Neuzählung mit verschärfter Regel (b) 19 → 21.
	'lib/components/organisms/PresetRail.svelte': { n: 21, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' },
	'lib/components/organisms/SubscriptionCard.svelte': { n: 36, grund: 'Bestand vor ADR-0112 (harte Maße/Farben)' }
};

export const KONFIG: Konfig = {
	SEITEN_SCOPE,
	FREIGEGEBENE_KOMPOSITIONEN,
	BESTAND,
	BESTAND_OBERGRENZE,
	AUSNAHMEN
};
