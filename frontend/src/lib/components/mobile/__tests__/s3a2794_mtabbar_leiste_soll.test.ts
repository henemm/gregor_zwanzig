// Issue #2794 S3a, Teil-PR 2 (Fix-Loop 1, Adversary F003): Kern-Waechter fuer AC-3 der
// Reiterleiste. Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-3, §7.
//
// AC-3: Am Desktop hat die Leiste genau eine Grundlinie, der aktive Reiter ist 600 stark mit
// 2px-Unterstrich in der Akzentfarbe, Badges sind kleine neutrale Mono-Marken (10 px), und es
// gibt keine Segmented-Box (die Leistenwurzel traegt KEIN data-slot="segmented" — sonst greift
// die Box aus app.css mit Rahmen und Rundung).
//
// Gemessen an der Wirkstelle:
//   - Markup: MTabBar wird ECHT unter svelte/server gerendert (Wurzel ohne data-slot="segmented",
//     aktiver Reiter data-state="active", Badge mit data-slot="segmented-badge").
//   - Stil: die scoped <style>-Regeln von MTabBar.svelte werden mit dem echten Svelte-Compiler
//     gelesen und die Kaskade fuer den aktiven Reiter bzw. das Badge (Desktop, ohne Media-Query)
//     nachgerechnet — Muster mtabbar_zaehler_neutral.test.ts. Im Browser misst dieselbe Zusicherung
//     die Staging-E2E s3a2794-hub-reiter-wetter-zustellung.spec.ts (AC-3, getComputedStyle).
//
// Mutationen, die rot werden muessen: M14 (data-slot="segmented" wieder an der Wurzel),
// M14b (aktiv font-weight 500), M14c (Badge font-size var(--g-text-xs)).
//
//   cd frontend && npm test -- src/lib/components/mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> mobile -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const DATEI = path.join(HERE, '..', 'MTabBar.svelte');
const QUELLE = readFileSync(DATEI, 'utf-8');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const AST = parse(QUELLE, { modern: true }) as any;

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MTabBar = (await import(pathToFileURL(DATEI).href)).default as any;

function rendern(): string {
	return render(MTabBar, {
		props: {
			items: [
				{ value: 'uebersicht', label: 'Übersicht' },
				{ value: 'orte', label: 'Orte', badge: 3, badge_testid: 'badge-orte' },
				{ value: 'wetter', label: 'Wetter' },
				{ value: 'zustellung', label: 'Zustellung' }
			],
			active: 'uebersicht',
			onChange: () => {},
			ariaLabel: 'Reiter'
		}
	}).body.replace(/<!--.*?-->/g, '');
}

interface Regel {
	selektoren: string[];
	decls: Array<[string, string]>;
	media: string | null;
	ordnung: number;
}

function regeln(): Regel[] {
	const out: Regel[] = [];
	let ordnung = 0;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const lauf = (kinder: any[], media: string | null) => {
		for (const n of kinder) {
			if (n.type === 'Rule') {
				out.push({
					selektoren: QUELLE.slice(n.prelude.start, n.prelude.end).split(',').map((s) => s.replace(/\s+/g, ' ').trim()),
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					decls: n.block.children.filter((d: any) => d.type === 'Declaration').map((d: any) => [d.property, String(d.value).trim()]),
					media,
					ordnung: ordnung++
				});
			} else if (n.type === 'Atrule' && n.block) {
				lauf(n.block.children, `${n.name} ${n.prelude}`);
			}
		}
	};
	lauf(AST.css?.children ?? [], null);
	return out;
}

const REGELN = regeln();
const spezifitaet = (sel: string): number =>
	(sel.replace(/:global\(([^)]*)\)/g, '$1').match(/\.[a-zA-Z]/g) ?? []).length + (sel.match(/\[/g) ?? []).length;
const istAktivZustand = (sel: string) => /data-state='active'|data-state="active"|data-active='true'|data-active="true"/.test(sel);

/** Desktop-Kaskade (Regeln ohne Media-Query) fuer ein Element, dessen Selektoren `trifft` erfuellen. */
function desktopStil(trifft: (sel: string) => boolean): Record<string, string> {
	const treffer: Array<{ spez: number; ordnung: number; decls: Array<[string, string]> }> = [];
	for (const r of REGELN) {
		if (r.media !== null) continue;
		for (const sel of r.selektoren) if (trifft(sel)) treffer.push({ spez: spezifitaet(sel), ordnung: r.ordnung, decls: r.decls });
	}
	treffer.sort((a, b) => a.spez - b.spez || a.ordnung - b.ordnung);
	const stil: Record<string, string> = {};
	for (const t of treffer) for (const [p, v] of t.decls) stil[p] = v.replace(/\s+/g, ' ');
	return stil;
}

/** Aktiver Reiter: Item-Regeln (ohne Badge, ohne Pseudoklassen) — Grundregel plus Aktiv-Zustaende. */
const aktiverReiter = () =>
	desktopStil((sel) => /segmented-item/.test(sel) && !/segmented-badge/.test(sel) && !/:(focus|hover)/.test(sel));
/** Badge in einem NICHT aktiven Reiter. */
const badge = () => desktopStil((sel) => /segmented-badge/.test(sel) && !istAktivZustand(sel));

describe('AC-3 (F003): Reiterleiste nach Soll — keine Segmented-Box', () => {
	test('s3a2794_f003_wurzel_ohne_data_slot_segmented_ssr', () => {
		const html = rendern();
		const wurzel = /<div\b[^>]*\brole="tablist"[^>]*>/.exec(html);
		assert.ok(wurzel, `Messaufbau: keine tablist-Wurzel im Markup:\n${html.slice(0, 400)}`);
		assert.ok(!/\bdata-slot="segmented"/.test(wurzel![0]), `AC-3: die Leistenwurzel traegt data-slot="segmented" (Segmented-Box aus app.css): ${wurzel![0]}`);
		assert.ok(!/\bdata-slot="segmented"/.test(html), 'AC-3: irgendein Element der Leiste traegt data-slot="segmented"');
	});

	test('s3a2794_f003_markup_aktiv_und_badge_ssr', () => {
		const html = rendern();
		assert.match(html, /<button\b[^>]*data-value="uebersicht"[^>]*data-state="active"/, 'aktiver Reiter nicht als data-state="active" markiert');
		assert.match(html, /<span\b[^>]*data-slot="segmented-badge"[^>]*>3<\/span>/, 'Badge mit der Zahl fehlt');
	});

	test('s3a2794_f003_keine_regel_setzt_rahmen_oder_rundung_an_der_wurzel_desktop', () => {
		const wurzel = desktopStil((sel) => sel === '.mtabbar');
		// #2881 ADR-0111 Punkt 1: Grundlinie --g-rule (löst --g-ink-faint ab).
		assert.equal(wurzel['border-bottom'], '1px solid var(--g-rule)', 'AC-3: die eine Grundlinie fehlt an der Wurzel');
		for (const p of ['border', 'border-radius', 'border-top', 'border-left', 'border-right', 'background', 'box-shadow']) {
			assert.equal(wurzel[p], undefined, `AC-3: die Leistenwurzel setzt ${p}: ${wurzel[p]} (Segmented-Box)`);
		}
	});
});

describe('AC-3 (F003): aktiver Reiter 600 mit 2px-Unterstrich in Akzentfarbe (Desktop)', () => {
	test('s3a2794_f003_aktiv_schriftgewicht_600', () => {
		assert.equal(aktiverReiter()['font-weight'], '600', 'AC-3: aktiver Reiter ist nicht 600 stark');
	});

	test('s3a2794_f003_inaktiv_nicht_600', () => {
		const inaktiv = desktopStil((sel) => /segmented-item/.test(sel) && !/segmented-badge/.test(sel) && !istAktivZustand(sel) && !/:(focus|hover)/.test(sel));
		assert.notEqual(inaktiv['font-weight'], '600', 'Messaufbau: auch inaktive Reiter sind 600 — der Aktiv-Zustand waere nicht unterscheidbar');
	});

	test('s3a2794_f003_aktiv_unterstrich_2px_akzent', () => {
		const s = aktiverReiter();
		const bb = s['border-bottom'] ?? '';
		assert.match(bb, /^2px solid\b/, `AC-3: Unterstrich ist nicht 2px (border-bottom: ${bb})`);
		assert.equal(s['border-bottom-color'], 'var(--g-accent)', `AC-3: Unterstrich nicht in Akzentfarbe (${s['border-bottom-color']})`);
	});
});

// ── F010 (Adversary Runde 3, Mutation M14g): keine senkrechten Segmented-Trenner ─────────
//
// app.css (`@layer components`) setzt `[data-slot="segmented-item"]:not(:last-child)` einen
// Rahmen rechts — die senkrechten Trenner der Segmented-Box. Die Reiter der Leiste tragen
// data-slot="segmented-item", also greift die Regel. Nur MTabBars `border: none` haelt sie fern.
// Gemessen wird die Kaskade fuer einen NICHT letzten, inaktiven Reiter aus BEIDEN Quellen:
// die echten Regeln aus app.css (Layer components, ausserhalb von Media-Queries) und die
// scoped Desktop-Regeln aus MTabBar.svelte (ohne Layer => gewinnen gegen jeden Layer,
// sonst Spezifitaet, sonst Reihenfolge). Im Browser misst dasselbe die Staging-E2E
// (borderRightWidth).

const APP_CSS = readFileSync(path.join(FRONTEND, 'src', 'app.css'), 'utf-8');

interface CssRegel {
	selektor: string;
	decls: Array<[string, string]>;
	/** 0 = in einem @layer (schwaecher), 1 = ohne Layer. */
	ebene: number;
	/** Zusatz-Spezifitaet (Svelte-Scope-Klasse). */
	zusatz: number;
	ordnung: number;
}

/** Minimaler CSS-Leser: liefert Regeln in `@layer …` und ohne Layer; @media/@supports usw. werden uebersprungen. */
function appCssRegeln(css: string): CssRegel[] {
	const text = css.replace(/\/\*[\s\S]*?\*\//g, '');
	const out: CssRegel[] = [];
	let i = 0;
	let ordnung = 0;
	function block(ebene: number | null): void {
		// liest bis zur schliessenden Klammer dieses Blocks
		let prelude = '';
		while (i < text.length) {
			const c = text[i];
			if (c === '}') {
				i++;
				return;
			}
			if (c === ';') {
				prelude = '';
				i++;
				continue;
			}
			if (c === '{') {
				i++;
				const p = prelude.trim();
				prelude = '';
				if (p.startsWith('@layer')) block(0);
				else if (p.startsWith('@')) block(null);
				else {
					const start = i;
					let tiefe = 1;
					while (i < text.length && tiefe > 0) {
						if (text[i] === '{') tiefe++;
						else if (text[i] === '}') tiefe--;
						i++;
					}
					if (ebene === null) continue;
					const inhalt = text.slice(start, i - 1);
					if (inhalt.includes('{')) continue; // verschachtelte Regeln: nicht Gegenstand
					const decls = inhalt
						.split(';')
						.map((d) => d.trim())
						.filter((d) => d.includes(':'))
						.map((d) => [d.slice(0, d.indexOf(':')).trim(), d.slice(d.indexOf(':') + 1).trim().replace(/\s+/g, ' ')] as [string, string]);
					for (const s of p.split(',')) out.push({ selektor: s.replace(/\s+/g, ' ').trim(), decls, ebene, zusatz: 0, ordnung: ordnung++ });
				}
				continue;
			}
			prelude += c;
			i++;
		}
	}
	block(1);
	return out;
}

/** Spezifitaet (b-Anteil: Klassen, Attribute, Pseudoklassen; c: Typen) als Zahl. */
function spez(sel: string): number {
	const s = sel.replace(/:global\(([^()]*(?:\([^()]*\))?[^()]*)\)/g, '$1');
	const ids = (s.match(/#[\w-]+/g) ?? []).length;
	const klassen = (s.match(/\.[a-zA-Z][\w-]*/g) ?? []).length + (s.match(/\[[^\]]*\]/g) ?? []).length;
	const pseudo = (s.replace(/:not\(/g, '(').match(/(?<!:):[a-z-]+/g) ?? []).length;
	const typen = (s.replace(/\[[^\]]*\]/g, '').replace(/[.:#][\w-]+/g, '').match(/(^|[\s>+~(])[a-z]+/g) ?? []).length;
	return ids * 10000 + (klassen + pseudo) * 100 + typen;
}

interface El {
	tag: string;
	klassen: string[];
	attrs: Record<string, string>;
	letztesKind: boolean;
}

/** Passt ein einfacher zusammengesetzter Selektor (Typ, .klasse, [attr], [attr="v"], :not(:last-child)) auf das Element? */
function passtCompound(c: string, el: El): boolean {
	let rest = c;
	const tag = /^[a-z]+/.exec(rest);
	if (tag) {
		if (tag[0] !== el.tag) return false;
		rest = rest.slice(tag[0].length);
	}
	while (rest.length > 0) {
		let m: RegExpExecArray | null;
		if ((m = /^\.([\w-]+)/.exec(rest))) {
			if (!el.klassen.includes(m[1])) return false;
		} else if ((m = /^\[([\w-]+)(?:=["']?([^"'\]]*)["']?)?\]/.exec(rest))) {
			if (!(m[1] in el.attrs)) return false;
			if (m[2] !== undefined && el.attrs[m[1]] !== m[2]) return false;
		} else if ((m = /^:not\(:last-child\)/.exec(rest))) {
			if (el.letztesKind) return false;
		} else {
			return false; // :hover, :focus, Pseudo-Elemente usw.: kein statischer Ruhezustand
		}
		rest = rest.slice(m[0].length);
	}
	return true;
}

/** Selektor mit Nachfahren-Kombinatoren: letzter Teil = Element, alle vorderen = die Leistenwurzel. */
function passt(sel: string, el: El, wurzel: El): boolean {
	const s = sel.replace(/:global\(([^()]*(?:\([^()]*\))?[^()]*)\)/g, '$1').trim();
	if (/[>+~]/.test(s)) return false;
	const teile = s.split(' ').filter(Boolean);
	const letzter = teile.pop()!;
	if (!passtCompound(letzter, el)) return false;
	return teile.every((t) => passtCompound(t, wurzel));
}

/** Zeichnet die Seite einen Strich? (Wert des border-/border-<seite>-Kurzschreibers bzw. der Langformen.) */
function seitenStrich(decls: Array<[string, string]>, seite: 'top' | 'right' | 'left'): boolean {
	let breite = 'medium';
	let stil = 'none';
	for (const [p, v] of decls) {
		const kurz = p === 'border' || p === `border-${seite}`;
		if (kurz) {
			const t = v.split(' ');
			stil = t.find((x) => /^(none|hidden|solid|dashed|dotted|double|groove|ridge|inset|outset)$/.test(x)) ?? 'none';
			breite = t.find((x) => /^(\d|\.|thin|medium|thick)/.test(x)) ?? 'medium';
		} else if (p === 'border-style' || p === `border-${seite}-style`) stil = v.split(' ')[0];
		else if (p === 'border-width' || p === `border-${seite}-width`) breite = v.split(' ')[0];
	}
	if (stil === 'none' || stil === 'hidden') return false;
	return !/^0(px|rem|em)?$/.test(breite);
}

describe('AC-3 (F010): am Desktop keine senkrechten Segmented-Trenner an den Reitern', () => {
	const wurzel: El = { tag: 'div', klassen: ['mtabbar'], attrs: { role: 'tablist', 'aria-label': 'Reiter' }, letztesKind: true };
	const reiter = (aktiv: boolean, letztesKind: boolean): El => ({
		tag: 'button',
		klassen: [],
		attrs: {
			type: 'button',
			role: 'tab',
			'data-slot': 'segmented-item',
			'data-value': 'orte',
			'data-active': aktiv ? 'true' : 'false',
			'data-state': aktiv ? 'active' : 'inactive',
			'aria-selected': aktiv ? 'true' : 'false'
		},
		letztesKind
	});

	function kaskade(el: El): { decls: Array<[string, string]>; quellen: string[] } {
		const app = appCssRegeln(APP_CSS).filter((r) => passt(r.selektor, el, wurzel));
		const komp: CssRegel[] = [];
		for (const r of REGELN) {
			if (r.media !== null) continue;
			for (const sel of r.selektoren) {
				if (passt(sel, el, wurzel)) komp.push({ selektor: sel, decls: r.decls, ebene: 1, zusatz: 100, ordnung: 100000 + r.ordnung });
			}
		}
		const alle = [...app, ...komp].sort(
			(a, b) => a.ebene - b.ebene || spez(a.selektor) + a.zusatz - (spez(b.selektor) + b.zusatz) || a.ordnung - b.ordnung
		);
		return { decls: alle.flatMap((r) => r.decls), quellen: alle.map((r) => r.selektor) };
	}

	test('s3a2794_f010_messaufbau_app_css_setzt_trenner_rechts', () => {
		// Ohne MTabBar-Regeln: die app.css-Kaskade allein zeichnet den Trenner (sonst misst der Test nichts).
		const app = appCssRegeln(APP_CSS).filter((r) => passt(r.selektor, reiter(false, false), wurzel));
		assert.ok(
			app.some((r) => /:not\(:last-child\)/.test(r.selektor)),
			`Messaufbau: die Segmented-Trenner-Regel aus app.css wurde nicht gefunden (${app.map((r) => r.selektor).join(' | ')})`
		);
		const decls = app.sort((a, b) => spez(a.selektor) - spez(b.selektor) || a.ordnung - b.ordnung).flatMap((r) => r.decls);
		assert.equal(seitenStrich(decls, 'right'), true, 'Messaufbau: app.css allein zeichnet keinen Trenner rechts');
	});

	for (const aktiv of [false, true]) {
		test(`s3a2794_f010_reiter_${aktiv ? 'aktiv' : 'inaktiv'}_nicht_letzter_ohne_senkrechten_strich`, () => {
			const { decls, quellen } = kaskade(reiter(aktiv, false));
			for (const seite of ['right', 'left', 'top'] as const) {
				assert.equal(
					seitenStrich(decls, seite),
					false,
					`AC-3/F010: der Reiter traegt am Desktop einen Rahmen ${seite} (Segmented-Trenner); Kaskade: ${quellen.join(' | ')}`
				);
			}
		});
	}
});

describe('AC-3 (F003): Badge klein, neutral, Mono (Desktop)', () => {
	test('s3a2794_f003_badge_mono_10px_neutral', () => {
		const s = badge();
		assert.equal(s['font-family'], 'var(--g-font-mono)', `AC-3: Badge nicht Mono (${s['font-family']})`);
		assert.equal(s['font-size'], '10px', `AC-3: Badge nicht 10 px (${s['font-size']})`);
		assert.equal(s.background ?? s['background-color'], 'var(--g-paper-deep)', 'AC-3: Badge-Grund nicht neutral');
		assert.equal(s.color, 'var(--g-ink-3)', 'AC-3: Badge-Schrift nicht neutral');
	});
});
