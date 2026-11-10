// Issue #1831 (Epic #2508): Der Wechsel des Danger-Rots #b33a2a -> #a83232 blieb halb stehen.
// Der Loeschen-Knopf (Btn variant="destructive") zeigte zwei Rottoene: Flaeche aus dem rgba-Literal
// rgba(179,58,42,.10/.18) (altes Rot, zudem theme-blind), Schrift und Rand aus var(--g-danger).
// Hover hell auf --g-paper lag damit bei 4,11:1 (< WCAG AA 4,5:1).
//
// Gerechnet wird mit den Werten, die app.css TATSAECHLICH setzt (Destructive-Regel, aufgeloest
// gegen den hellen :root bzw. den Dark-Block). Die Flaeche muss per
// color-mix(in oklab, var(--g-danger) N%, transparent) aus dem Token kommen — dann ist sie die
// Token-Farbe mit Deckkraft N % und in jedem Modus aus dem jeweiligen Rot getoent.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/danger_flaeche_kontrast.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const ohneKommentare = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '');
const CSS = ohneKommentare(readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8'));
const MIN = 4.5;
const GRUENDE = ['--g-surface-1', '--g-paper'];

type Modus = 'hell' | 'dunkel';
type Rgba = [number, number, number, number];

function blockAb(quelle: string, kopf: RegExp): string {
	const m = kopf.exec(quelle);
	assert.ok(m, `Block ${kopf} fehlt`);
	const auf = quelle.indexOf('{', m!.index);
	let tiefe = 0;
	for (let i = auf; i < quelle.length; i++) {
		if (quelle[i] === '{') tiefe++;
		else if (quelle[i] === '}' && --tiefe === 0) return quelle.slice(auf + 1, i);
	}
	throw new Error('Block ohne Ende');
}
const HELL = blockAb(CSS, /:root\s*\{/);
const DUNKEL = blockAb(CSS, /:root\[data-theme=(["'])dark\1\]\s*\{/);
const decl = (block: string, name: string) =>
	block.match(new RegExp(`(?:^|[;{\\s])${name}\\s*:\\s*([^;]+);`))?.[1].trim() ?? null;

function farbe(wert: string, modus: Modus, tiefe = 0): Rgba {
	assert.ok(tiefe < 8, `var()-Kette zu tief: ${wert}`);
	const w = wert.trim().toLowerCase();
	if (w === 'transparent') return [0, 0, 0, 0];
	const v = w.match(/^var\((--[a-z0-9-]+)\)$/);
	if (v) {
		const roh = (modus === 'dunkel' ? decl(DUNKEL, v[1]) : null) ?? decl(HELL, v[1]);
		assert.ok(roh, `Token ${v[1]} nicht definiert`);
		return farbe(roh!, modus, tiefe + 1);
	}
	// color-mix(in oklab, <farbe> N%, transparent) == <farbe> mit Deckkraft N % (premultiplied).
	const mix = w.match(/^color-mix\(\s*in\s+oklab\s*,\s*(.+?)\s+([\d.]+)%\s*,\s*transparent\s*\)$/);
	if (mix) {
		const f = farbe(mix[1], modus, tiefe + 1);
		return [f[0], f[1], f[2], f[3] * (+mix[2] / 100)];
	}
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
function kontrast(a: Rgba, b: Rgba): number {
	const lum = (c: Rgba) => {
		const k = c.slice(0, 3).map((x) => {
			const s = x / 255;
			return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
		});
		return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
	};
	const [h, d] = [lum(a), lum(b)].sort((x, y) => y - x);
	return (h + 0.05) / (d + 0.05);
}

const RUHE = blockAb(CSS, /\[data-slot="btn"\]\[data-variant="destructive"\]\s*\{/);
const HOVER = blockAb(CSS, /\[data-slot="btn"\]\[data-variant="destructive"\]:hover\s*\{/);
const flaecheVon = (regel: string) => decl(regel, 'background-color') ?? decl(regel, 'background');
const gleich = (a: Rgba, b: Rgba) => a.every((x, i) => Math.abs(x - b[i]) < 1e-6);

describe('#1831: Loeschen-Knopf — Flaeche, Schrift und Rand aus demselben Danger-Rot', () => {
	test('AC-1: Web-CSS enthaelt das alte Rot #b33a2a / rgb(179, 58, 42) nirgends mehr', () => {
		assert.doesNotMatch(CSS, /#b33a2a/i, 'altes Hex #b33a2a noch in app.css');
		assert.doesNotMatch(CSS, /179\s*,\s*58\s*,\s*42/, 'altes rgb(179, 58, 42) noch in app.css');
	});

	test('AC-1: Schrift und Rand kommen aus var(--g-danger)', () => {
		assert.equal(decl(RUHE, 'color'), 'var(--g-danger)');
		assert.match(decl(RUHE, 'border') ?? decl(RUHE, 'border-color') ?? '', /var\(--g-danger\)/);
	});

	for (const [name, regel, anteil] of [
		['Ruhe', RUHE, 0.1],
		['Hover', HOVER, 0.18]
	] as const) {
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			test(`AC-1/AC-2: Flaeche ${name} ${modus} = --g-danger mit ${anteil * 100} % Deckkraft`, () => {
				const roh = flaecheVon(regel);
				assert.ok(roh, `${name}: keine Flaechenfarbe gesetzt`);
				assert.match(roh!, /var\(--g-danger\)/, `${name}: Flaeche nicht aus var(--g-danger) gemischt: ${roh}`);
				const f = farbe(roh!, modus);
				const danger = farbe('var(--g-danger)', modus);
				assert.ok(
					gleich(f, [danger[0], danger[1], danger[2], anteil]),
					`${name}/${modus}: Flaeche ${f.join(',')} != Danger ${danger.slice(0, 3).join(',')} @ ${anteil}`
				);
			});
		}
	}

	test('AC-2: Dunkel-Flaeche ist aus #ee7a7a getoent (nicht aus dem Hell-Rot)', () => {
		const f = farbe(flaecheVon(RUHE)!, 'dunkel');
		assert.deepEqual(f.slice(0, 3), [0xee, 0x7a, 0x7a]);
	});

	for (const [name, regel] of [
		['Ruhe 10 %', RUHE],
		['Hover 18 %', HOVER]
	] as const) {
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			test(`AC-3: Schrift auf Flaeche ${name} ${modus} >= 4,5:1 (card und paper)`, () => {
				const schrift = farbe(decl(RUHE, 'color')!, modus);
				for (const grund of GRUENDE) {
					const g = farbe(`var(${grund})`, modus);
					const k = kontrast(schrift, ueber(farbe(flaecheVon(regel)!, modus), g));
					assert.ok(k >= MIN, `${name}/${modus} auf ${grund}: ${k.toFixed(2)}:1 < ${MIN}:1`);
				}
			});
		}
	}

	test('AC-4: @property-Fallback von --color-destructive == helles --g-danger (rgb(168, 50, 50))', () => {
		const m = CSS.match(/@property\s+--color-destructive\s*\{[^}]*initial-value\s*:\s*([^;]+);/);
		assert.ok(m, '@property --color-destructive fehlt');
		const fallback = farbe(m![1], 'hell');
		assert.deepEqual(fallback, farbe('var(--g-danger)', 'hell'));
		assert.deepEqual(fallback, [168, 50, 50, 1]);
	});
});
