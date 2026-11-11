// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 2.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-13, AC-14, Klarstellungen K-4, K-5.
//
// Vertrag (hier festgelegt, /50 baut danach):
//   atoms/Input.svelte     Prop `ampel?: 'green'|'yellow'|'orange'|'red'` → Attribut data-ampel="<farbe>" am
//                          <input>; ohne Prop KEIN data-ampel und Markup wie heute (gleich dem ui/input).
//                          Das Prop wird nie als rohes Attribut `ampel=` durchgereicht.
//                          app.css: Regel je Farbe `[data-ampel="<farbe>"]` mit var(--g-ampel-<de>) und eine
//                          data-ampel-Regel mit der Unterkanten-Stärke var(--g-size-3px); --g-size-3px = 3px.
//   atoms/Segmented.svelte Option/Item `farbe?` → Farbpunkt-Element mit data-farbe="<farbe>" im Segment
//                          (data-slot="segmented-punkt"); die `items`-API reicht testid, badge_testid und farbe
//                          durch (heute verworfen). app.css färbt den Punkt aus --g-ampel-*.
//   atoms/Skelett.svelte   Prop `label?: string` (Beschriftung vom Aufrufer, aus dem Katalog) → role="status",
//                          aria-busy="true", aria-label=<label>; ohne label ein Standardtext „wird geladen“ aus dem
//                          Allgemein-Katalog (nicht wetter.json), nie leer; <style> nur aus Tokens (Regel b);
//                          Export im Barrel atoms/index.ts.
//   Btn size="tap"         data-size="tap"; BtnSize kennt 'tap'; app.css `[data-slot="btn"][data-size="tap"]` mit
//                          var(--g-tap-min).
//
// Verhalten per Server-Render (svelte/server); Quellregeln (app.css, Barrel, BtnSize-Union, Regel b) als
// doc-compliance-test.
//
// RED heute: kein ampel-Prop, kein Farbpunkt, items-API verwirft Testids, kein Skelett, keine Btn-Größe tap.
//
//   cd frontend && npm test -- src/lib/components/atoms/__tests__/ampel_atome.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

import { zaehleTokenVerstoesse } from '../../../__tests__/bausteine_waechter_regeln.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> atoms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const SRC = path.join(FRONTEND, 'src');
const ATOMS = path.resolve(HERE, '..');
const UI = path.resolve(ATOMS, '..', 'ui');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

async function lade(datei: string): Promise<any | null> {
	if (!existsSync(datei)) return null;
	return (await import(pathToFileURL(datei).href)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');

const APP_CSS = readFileSync(path.join(SRC, 'app.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
/** Alle Regeln (Selektor, Rumpf) ohne Verschachtelung auf oberster Ebene und in @media/@layer. */
function regeln(css: string): { sel: string; body: string }[] {
	const aus: { sel: string; body: string }[] = [];
	for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) aus.push({ sel: m[1].trim(), body: m[2] });
	return aus;
}
const REGELN = regeln(APP_CSS);

const FARBEN = ['green', 'yellow', 'orange', 'red'] as const;
const DE: Record<(typeof FARBEN)[number], string> = { green: 'gruen', yellow: 'gelb', orange: 'orange', red: 'rot' };
const attrSel = (attr: string, wert: string) => new RegExp(`\\[${attr}=(["'])${wert}\\1\\]`);

// ─── Input mit Ampel (AC-13) ─────────────────────────────────────────────────

describe('AC-13: atoms/Input mit Ampel-Unterkante', () => {
	for (const f of FARBEN) {
		test(`ampel="${f}" → data-ampel="${f}" am <input>, kein rohes ampel=-Attribut`, async () => {
			const Input = await lade(path.join(ATOMS, 'Input.svelte'));
			const h = html(Input, { ampel: f, value: '12' });
			const input = h.match(/<input\b[^>]*>/)?.[0] ?? '';
			assert.match(input, new RegExp(`\\sdata-ampel="${f}"`), `TDD RED: <input> ohne data-ampel="${f}"`);
			assert.doesNotMatch(input, /\sampel=/, 'Prop ampel als rohes HTML-Attribut durchgereicht');
		});
	}
	test('ohne ampel: kein data-ampel, Markup gleich dem ui/input (wie heute)', async () => {
		const Input = await lade(path.join(ATOMS, 'Input.svelte'));
		const UiInput = await lade(path.join(UI, 'input', 'input.svelte'));
		const props = { value: 'x', 'data-testid': 'probe', size: 'md' };
		const a = html(Input, props);
		assert.doesNotMatch(a, /data-ampel/);
		assert.equal(a, html(UiInput, props));
	});
	for (const f of FARBEN) {
		test(`app.css: Regel [data-ampel="${f}"] nutzt var(--g-ampel-${DE[f]})`, () => {
			const treffer = REGELN.filter((r) => attrSel('data-ampel', f).test(r.sel) && r.body.includes(`var(--g-ampel-${DE[f]})`));
			assert.ok(treffer.length > 0, `TDD RED: keine Regel [data-ampel="${f}"] { … var(--g-ampel-${DE[f]}) … } in app.css`);
		});
	}
	test('app.css: Unterkanten-Stärke aus Maß-Token --g-size-3px (= 3px) in einer data-ampel-Regel', () => {
		const def = APP_CSS.match(/--g-size-3px\s*:\s*([^;]+);/);
		assert.ok(def, 'TDD RED: Maß-Token --g-size-3px fehlt in app.css');
		assert.equal(def![1].trim(), '3px');
		const treffer = REGELN.filter((r) => /data-ampel/.test(r.sel) && r.body.includes('var(--g-size-3px)'));
		assert.ok(treffer.length > 0, 'TDD RED: keine data-ampel-Regel mit var(--g-size-3px)');
	});
});

// ─── Segmented mit Farbpunkt (AC-13) ─────────────────────────────────────────

function segmente(h: string): string[] {
	return [...h.matchAll(/<button\b[^>]*data-slot="segmented-item"[^>]*>[\s\S]*?<\/button>/g)].map((m) => m[0]);
}

describe('AC-13: atoms/Segmented mit Farbpunkt', () => {
	test('items-API mit farbe: je Segment ein Farbpunkt data-farbe', async () => {
		const Segmented = await lade(path.join(ATOMS, 'Segmented.svelte'));
		const items = FARBEN.map((f) => ({ id: f, label: f.toUpperCase(), farbe: f }));
		const s = segmente(html(Segmented, { items, value: 'orange', rolle: 'radio', ariaLabel: 'x' }));
		assert.equal(s.length, 4);
		s.forEach((seg, i) => {
			assert.match(seg, new RegExp(`data-farbe="${FARBEN[i]}"`), `TDD RED: Segment ${FARBEN[i]} ohne Farbpunkt: ${seg}`);
			assert.match(seg, /data-slot="segmented-punkt"/, `TDD RED: Segment ${FARBEN[i]} ohne data-slot="segmented-punkt"`);
		});
	});
	test('options-API mit farbe: Farbpunkt nur am Segment mit farbe', async () => {
		const Segmented = await lade(path.join(ATOMS, 'Segmented.svelte'));
		const options = [
			{ value: 'never', label: 'Nie', testid: 't-never' },
			{ value: 'red', label: 'Rot', testid: 't-red', farbe: 'red' }
		];
		const s = segmente(html(Segmented, { options, value: 'never', rolle: 'radio', ariaLabel: 'x' }));
		assert.doesNotMatch(s[0], /data-farbe/);
		assert.match(s[1], /data-farbe="red"/, `TDD RED: options-Segment ohne Farbpunkt: ${s[1]}`);
	});
	test('items-API reicht testid und badge_testid durch (heute verworfen)', async () => {
		const Segmented = await lade(path.join(ATOMS, 'Segmented.svelte'));
		const items = [{ id: 'a', label: 'A', badge: 2, testid: 'seg-a', badge_testid: 'seg-a-badge' }];
		const h = html(Segmented, { items, value: 'a' });
		assert.match(h, /data-testid="seg-a"/, 'TDD RED: items-API verwirft testid');
		assert.match(h, /data-testid="seg-a-badge"/, 'TDD RED: items-API verwirft badge_testid');
	});
	test('ohne farbe: kein Farbpunkt (Markup wie heute)', async () => {
		const Segmented = await lade(path.join(ATOMS, 'Segmented.svelte'));
		const h = html(Segmented, { items: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }], value: 'a' });
		assert.doesNotMatch(h, /data-farbe|segmented-punkt/);
	});
	test('app.css: Farbpunkt-Regel (segmented-punkt) und je Farbe [data-farbe] mit var(--g-ampel-*)', () => {
		assert.ok(REGELN.some((r) => /segmented-punkt/.test(r.sel)), 'TDD RED: keine Regel für [data-slot="segmented-punkt"] in app.css');
		const fehlt = FARBEN.filter((f) => !REGELN.some((r) => attrSel('data-farbe', f).test(r.sel) && r.body.includes(`var(--g-ampel-${DE[f]})`)));
		assert.deepEqual(fehlt, [], `TDD RED: [data-farbe=…]-Regel mit --g-ampel-* fehlt für: ${fehlt.join(', ')}`);
	});
});

// ─── Skelett (AC-14) ─────────────────────────────────────────────────────────

/** Alle Texte der Kataloge DE außer wetter.json (Allgemein-Kataloge). */
function allgemeinTexte(): Set<string> {
	const dir = path.join(SRC, 'lib', 'i18n', 'messages', 'de');
	const aus = new Set<string>();
	const sammle = (x: unknown) => {
		if (typeof x === 'string') aus.add(x);
		else if (x && typeof x === 'object') Object.values(x as Record<string, unknown>).forEach(sammle);
	};
	for (const n of readdirSync(dir)) if (n.endsWith('.json') && n !== 'wetter.json') sammle(JSON.parse(readFileSync(path.join(dir, n), 'utf8')));
	return aus;
}
const decode = (s: string) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');

describe('AC-14: atoms/Skelett', () => {
	const SKELETT = path.join(ATOMS, 'Skelett.svelte');
	test('Datei atoms/Skelett.svelte existiert', () => {
		assert.ok(existsSync(SKELETT), 'TDD RED: atoms/Skelett.svelte fehlt');
	});
	test('SSR: role="status", aria-busy="true", aria-label vom Aufrufer', async () => {
		const Skelett = await lade(SKELETT);
		assert.ok(Skelett, 'TDD RED: atoms/Skelett.svelte fehlt');
		const h = html(Skelett, { label: 'Lade Metriken …' });
		const wurzel = h.match(/<[a-z]+\b[^>]*role="status"[^>]*>/)?.[0];
		assert.ok(wurzel, `kein Element mit role="status": ${h}`);
		assert.match(wurzel!, /aria-busy="true"/);
		assert.match(wurzel!, /aria-label="Lade Metriken …"/);
	});
	test('SSR ohne label: Standardtext aus dem Allgemein-Katalog, nicht leer', async () => {
		const Skelett = await lade(SKELETT);
		assert.ok(Skelett, 'TDD RED: atoms/Skelett.svelte fehlt');
		const h = html(Skelett, {});
		const label = h.match(/role="status"[^>]*aria-label="([^"]*)"|aria-label="([^"]*)"[^>]*role="status"/);
		assert.ok(label, `ohne label kein aria-label am Status-Element: ${h}`);
		const text = decode(label![1] ?? label![2]);
		assert.ok(text.trim().length > 0, 'Standard-Beschriftung ist leer');
		assert.ok(allgemeinTexte().has(text), `Standard-Beschriftung „${text}“ stammt nicht aus dem Allgemein-Katalog (DE, ohne wetter.json)`);
	});
	test('Regel b: <style> nur aus Tokens (keine rohen px/rem, keine Farben)', () => {
		assert.ok(existsSync(SKELETT), 'TDD RED: atoms/Skelett.svelte fehlt');
		const v = zaehleTokenVerstoesse('lib/components/atoms/Skelett.svelte', readFileSync(SKELETT, 'utf8'));
		assert.deepEqual(v.map((x) => x.meldung), []);
	});
	test('Barrel atoms/index.ts exportiert Skelett', () => {
		const barrel = readFileSync(path.join(ATOMS, 'index.ts'), 'utf8').replace(/\/\/.*$/gm, '');
		assert.match(barrel, /export\s*\{\s*default\s+as\s+Skelett\s*\}\s*from\s*['"]\.\/Skelett\.svelte['"]/, 'TDD RED: Skelett fehlt im Barrel atoms/index.ts');
	});
});

// ─── Btn-Größe tap (K-5) ─────────────────────────────────────────────────────

describe('K-5: Btn-Größe tap (Touch-Ziel --g-tap-min)', () => {
	test('SSR: atoms/Btn size="tap" → data-size="tap"', async () => {
		const Btn = await lade(path.join(ATOMS, 'Btn.svelte'));
		const h = html(Btn, { size: 'tap', 'data-testid': 'probe' });
		assert.match(h, /<button\b[^>]*data-slot="btn"[^>]*data-size="tap"/);
	});
	test('BtnSize kennt die Größe tap (ui/btn/Btn.svelte)', () => {
		const q = readFileSync(path.join(UI, 'btn', 'Btn.svelte'), 'utf8');
		const union = q.match(/export\s+type\s+BtnSize\s*=([^;]+);/)?.[1] ?? '';
		assert.match(union, /['"]tap['"]/, 'TDD RED: BtnSize ohne \'tap\'');
	});
	test('app.css: [data-slot="btn"][data-size="tap"] nutzt var(--g-tap-min)', () => {
		const treffer = REGELN.filter((r) => /\[data-slot=(["'])btn\1\]\[data-size=(["'])tap\2\]/.test(r.sel) && r.body.includes('var(--g-tap-min)'));
		assert.ok(treffer.length > 0, 'TDD RED: keine Btn-Regel für data-size="tap" mit var(--g-tap-min) in app.css');
	});
});
