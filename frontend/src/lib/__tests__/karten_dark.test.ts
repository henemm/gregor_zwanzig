// Issue #2400 Fix-Loop 2 (AC-14): Karten im Dunklen Design.
//
// 1. Rahmen: die gerenderten Karten-Bausteine (Trip-Karte MapCanvas, Ortsvergleich-Vorschau
//    LocationPreviewMap — ein Muster, #1170) tragen die Rahmen-Klasse; deren Randfarbe wird aus
//    der echten Kaskade von app.css aufgeloest und muss im Dunklen >= 3:1 gegen paper, card und
//    surface-2 liegen (WCAG 1.4.11). Hell bleibt der Rahmen wie bisher (--g-ink-faint zu 20 %).
// 2. Leaflet-Bedienelemente: Kaskade aus node_modules/leaflet/dist/leaflet.css (ungeschichtet,
//    spaeter geladen) UND app.css. Ungeschichtet schlaegt @layer, dann Spezifitaet, bei Gleichstand
//    gewinnt leaflet.css (wird nach app.css geladen). Schrift auf Zoom-Knopf und Attribution
//    >= 4,5:1 auf der gewinnenden Flaeche, Flaeche dunkel, Leisten-Rand >= 3:1.
//
//   cd frontend && npm test -- src/lib/__tests__/karten_dark.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const ohneKommentare = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '');
const APP_CSS = ohneKommentare(readFileSync(path.join(FRONTEND, 'src/app.css'), 'utf-8'));
const LEAFLET_CSS = ohneKommentare(readFileSync(path.join(FRONTEND, 'node_modules/leaflet/dist/leaflet.css'), 'utf-8'));

// ─── Tokens und Farben ────────────────────────────────────────────────────────

type Modus = 'hell' | 'dunkel';
type Rgba = [number, number, number, number];

function blockAb(kopf: RegExp): string {
	const m = kopf.exec(APP_CSS);
	assert.ok(m, `Block ${kopf} fehlt`);
	const auf = APP_CSS.indexOf('{', m!.index);
	let t = 0;
	for (let i = auf; i < APP_CSS.length; i++) {
		if (APP_CSS[i] === '{') t++;
		else if (APP_CSS[i] === '}' && --t === 0) return APP_CSS.slice(auf + 1, i);
	}
	throw new Error('Block ohne Ende');
}
const HELL = blockAb(/:root\s*\{/);
const DUNKEL = blockAb(/:root\[data-theme=(["'])dark\1\]\s*\{/);
const decl = (b: string, n: string) => b.match(new RegExp(`(?:^|[;{\\s])--${n}\\s*:\\s*([^;]+);`))?.[1].trim() ?? null;

function farbe(wert: string, modus: Modus, tiefe = 0): Rgba {
	assert.ok(tiefe < 8, `zu tief: ${wert}`);
	const w = wert.trim().toLowerCase();
	const v = w.match(/^var\(--([a-z0-9-]+)\)$/);
	if (v) {
		const roh = (modus === 'dunkel' ? decl(DUNKEL, v[1]) : null) ?? decl(HELL, v[1]);
		assert.ok(roh, `Token --${v[1]} fehlt`);
		return farbe(roh!, modus, tiefe + 1);
	}
	const mix = w.match(/^color-mix\(in [a-z]+,\s*(.+?)\s+(\d+)%,\s*transparent\)$/);
	if (mix) {
		const f = farbe(mix[1], modus, tiefe + 1);
		return [f[0], f[1], f[2], f[3] * (+mix[2] / 100)];
	}
	if (w === 'transparent') return [0, 0, 0, 0];
	if (w === 'white') return [255, 255, 255, 1];
	if (w === 'black') return [0, 0, 0, 1];
	const hex = w.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
	if (hex) {
		const h = hex[1].length === 3 ? hex[1].replace(/./g, (c) => c + c) : hex[1];
		return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).concat(1) as Rgba;
	}
	const r = w.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
	assert.ok(r, `Farbe nicht auswertbar: ${wert}`);
	return [+r![1], +r![2], +r![3], r![4] === undefined ? 1 : +r![4]];
}
const ueber = (f: Rgba, g: Rgba): Rgba => [0, 1, 2].map((i) => f[i] * f[3] + g[i] * (1 - f[3])).concat(1) as Rgba;
function lum(c: Rgba): number {
	const k = c.slice(0, 3).map((x) => {
		const s = x / 255;
		return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	});
	return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
}
function kontrast(a: Rgba, b: Rgba): number {
	const [h, d] = [lum(a), lum(b)].sort((x, y) => y - x);
	return (h + 0.05) / (d + 0.05);
}
const WEISS: Rgba = [255, 255, 255, 1];

// ─── Kaskade ──────────────────────────────────────────────────────────────────

interface Regel {
	sel: string;
	decls: Record<string, string>;
	geschichtet: boolean;
	quelle: number; // 0 = app.css, 1 = leaflet.css (spaeter geladen)
	nr: number;
}

/** Blattregeln einer CSS-Datei mit der Angabe, ob sie in einem @layer liegen. */
function regeln(css: string, quelle: number): Regel[] {
	const out: Regel[] = [];
	const stapel: string[] = [];
	let start = 0;
	let nr = 0;
	for (let i = 0; i < css.length; i++) {
		if (css[i] === '{') {
			const kopf = css.slice(start, i).trim();
			const zu = css.indexOf('}', i);
			const auf = css.indexOf('{', i + 1);
			if (!kopf.startsWith('@') && zu >= 0 && (auf < 0 || zu < auf)) {
				const decls: Record<string, string> = {};
				for (const teil of css.slice(i + 1, zu).split(';')) {
					const k = teil.indexOf(':');
					if (k > 0) decls[teil.slice(0, k).trim()] = teil.slice(k + 1).trim();
				}
				const geschichtet = stapel.some((s) => s.startsWith('@layer'));
				for (const sel of kopf.split(',').map((s) => s.trim().replace(/\s+/g, ' '))) out.push({ sel, decls, geschichtet, quelle, nr: nr++ });
				i = zu;
				start = zu + 1;
				continue;
			}
			stapel.push(kopf);
			start = i + 1;
		} else if (css[i] === '}') {
			stapel.pop();
			start = i + 1;
		}
	}
	return out;
}
const ALLE = [...regeln(APP_CSS, 0), ...regeln(LEAFLET_CSS, 1)];

function spezifitaet(sel: string): number {
	const ohne = sel.replace(/:not\(([^)]*)\)/g, ' $1 ');
	const ids = (ohne.match(/#[\w-]+/g) ?? []).length;
	const klassen = (ohne.match(/\.[\w-]+|\[[^\]]+\]|:(?!:)[\w-]+/g) ?? []).length;
	const typen = (ohne.replace(/\[[^\]]+\]|\.[\w-]+|#[\w-]+|::?[\w-]+(\([^)]*\))?/g, ' ').match(/(?:^|[\s>+~])[a-z][\w-]*/gi) ?? []).length;
	return ids * 10000 + klassen * 100 + typen;
}

const DARK_PRAEFIX = /^:root\[data-theme=(["'])dark\1\] /;
/** Gewinnender Wert von `props` (erste vorhandene) fuer ein Element, auf das `passend` zutrifft. */
function gewinner(passend: string[], props: string[], modus: Modus): { wert: string; sel: string } | null {
	const kandidaten = ALLE.filter((r) => {
		const dunkel = DARK_PRAEFIX.test(r.sel);
		if (dunkel && modus !== 'dunkel') return false;
		return passend.includes(r.sel.replace(DARK_PRAEFIX, '')) && props.some((p) => p in r.decls);
	}).sort((a, b) => Number(b.geschichtet) - Number(a.geschichtet) || spezifitaet(a.sel) - spezifitaet(b.sel) || a.quelle - b.quelle || a.nr - b.nr);
	const r = kandidaten.at(-1);
	if (!r) return null;
	const p = props.find((x) => x in r.decls)!;
	return { wert: r.decls[p], sel: r.sel };
}
/** Farbanteil einer border-/background-Kurzschreibweise. */
function farbteil(wert: string): string {
	const m = wert.match(/(color-mix\([^)]*\([^)]*\)[^)]*\)|var\([^)]*\)|rgba?\([^)]*\)|#[0-9a-fA-F]{3,6}\b|\btransparent\b|\bwhite\b|\bblack\b)/);
	assert.ok(m, `keine Farbe in: ${wert}`);
	return m![1];
}

// ─── 1. Kartenrahmen ──────────────────────────────────────────────────────────

const MapCanvas = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-detail/waypoints/MapCanvas.svelte')).href)).default;
const LocationPreviewMap = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/compare/LocationPreviewMap.svelte')).href)).default;

function wurzelKlassen(html: string): string[] {
	const m = html.match(/<div\b[^>]*\bclass="([^"]*)"/);
	assert.ok(m, `kein Wurzel-div mit class: ${html.slice(0, 200)}`);
	return m![1].split(/\s+/);
}

const KARTEN = {
	'Trip-Karte (MapCanvas)': () =>
		render(MapCanvas, { props: { stage: { id: 's1', name: 'E1', date: '2026-07-01', waypoints: [] }, activeWaypointId: null, onWaypointActivate: () => {} } }).body,
	'Ortsvergleich-Vorschau (LocationPreviewMap)': () => render(LocationPreviewMap, { props: { lat: 47.1, lon: 11.2 } }).body
};

describe('AC-14: Kartenrahmen im Dunklen >= 3:1, hell unveraendert, ein Muster (#1170)', () => {
	const randklasse = (m: Modus) => gewinner(['.g-karten-rahmen'], ['border-color', 'border'], m);
	for (const [name, html] of Object.entries(KARTEN)) {
		test(`${name}: gerenderte Karte traegt die Rahmen-Klasse`, () => {
			const k = wurzelKlassen(html());
			assert.ok(k.includes('g-karten-rahmen'), `${name}: Klassen ${k.join(' ')}`);
			assert.ok(k.includes('border'), `${name}: ohne Rahmenbreite`);
		});
	}
	for (const grund of ['g-paper', 'g-card', 'g-surface-2']) {
		test(`Rand dunkel gegen --${grund} >= 3:1`, () => {
			const g = randklasse('dunkel');
			assert.ok(g, 'keine Randfarbe fuer .g-karten-rahmen in app.css');
			const unten = farbe(`var(--${grund})`, 'dunkel');
			const k = kontrast(ueber(farbe(farbteil(g!.wert), 'dunkel'), unten), unten);
			assert.ok(k >= 3, `Rand ${g!.wert} (${g!.sel}) gegen --${grund} = ${k.toFixed(2)}:1`);
		});
	}
	test('hell unveraendert: --g-ink-faint zu 20 %', () => {
		const g = randklasse('hell');
		assert.ok(g);
		const f = farbe(farbteil(g!.wert), 'hell');
		assert.deepEqual(f, [...farbe('var(--g-ink-faint)', 'hell').slice(0, 3), 0.2]);
	});
});

// ─── 2. Leaflet-Bedienelemente ────────────────────────────────────────────────

const ZOOM = ['.leaflet-bar a', '.leaflet-container a', '.leaflet-touch .leaflet-bar a'];
const ATTRIBUTION = ['.leaflet-control-attribution', '.leaflet-container .leaflet-control-attribution'];
const ATTRIBUTION_LINK = ['.leaflet-container a', '.leaflet-control-attribution a', '.leaflet-container .leaflet-control-attribution a'];
const LEISTE = ['.leaflet-bar', '.leaflet-touch .leaflet-bar'];

function flaeche(passend: string[], modus: Modus): Rgba {
	const g = gewinner(passend, ['background-color', 'background'], modus);
	assert.ok(g, `keine Flaeche fuer ${passend[0]}`);
	return ueber(farbe(farbteil(g!.wert), modus), WEISS); // ueber heller Kachel (schlechtester Fall)
}
function schrift(passend: string[], modus: Modus): Rgba {
	const g = gewinner(passend, ['color'], modus);
	assert.ok(g, `keine Schrift fuer ${passend[0]}`);
	return farbe(g!.wert, modus);
}

describe('AC-14: Leaflet-Bedienelemente im Dunklen auf Tokens (leaflet.css + app.css)', () => {
	test('Messaufbau: hell gewinnt Leaflets weisser Zoom-Knopf (Standard bleibt)', () => {
		assert.deepEqual(flaeche(ZOOM, 'hell'), WEISS);
	});
	test('Zoom-Knopf dunkel: dunkle Flaeche, Schrift >= 4,5:1', () => {
		const f = flaeche(ZOOM, 'dunkel');
		assert.ok(lum(f) < 0.1, `Zoom-Knopf-Flaeche hell (L=${lum(f).toFixed(2)})`);
		const k = kontrast(schrift(ZOOM, 'dunkel'), f);
		assert.ok(k >= 4.5, `Zoom-Knopf ${k.toFixed(2)}:1`);
	});
	test('Attribution dunkel: dunkle Flaeche, Text und Link >= 4,5:1', () => {
		const f = flaeche(ATTRIBUTION, 'dunkel');
		assert.ok(lum(f) < 0.1, `Attributions-Flaeche hell (L=${lum(f).toFixed(2)})`);
		const kText = kontrast(schrift(ATTRIBUTION, 'dunkel'), f);
		const kLink = kontrast(schrift(ATTRIBUTION_LINK, 'dunkel'), f);
		assert.ok(kText >= 4.5, `Attribution-Text ${kText.toFixed(2)}:1`);
		assert.ok(kLink >= 4.5, `Attribution-Link ${kLink.toFixed(2)}:1`);
	});
	test('Zoom-Leiste dunkel: Rand >= 3:1 gegen den dunklen Seitengrund', () => {
		const g = gewinner(LEISTE, ['border-color', 'border'], 'dunkel');
		assert.ok(g, 'kein Leisten-Rand');
		const unten = farbe('var(--g-paper)', 'dunkel');
		const k = kontrast(ueber(farbe(farbteil(g!.wert), 'dunkel'), unten), unten);
		assert.ok(k >= 3, `Leisten-Rand ${g!.wert} (${g!.sel}) = ${k.toFixed(2)}:1`);
	});
});
