// Issue #2400 (Staging-Messlauf 2026-11-10): aktiver Eintrag der Desktop-Seitenleiste
// muss in hell UND dunkel >= 4,5:1 erreichen. Staging-Befund: Schrift --g-accent-deep
// (#e07a4a) auf hart kodierter Hell-Toenung rgba(196,90,42,0.10) ueber --g-paper-deep
// (#2a2a26) = 4,38:1.
//
// Gerechnet wird mit den Ausdruecken, die Sidebar.svelte TATSAECHLICH setzt (aktiver Zweig
// von background/color der Nav-Links, Grund der <aside>), aufgeloest gegen app.css
// (heller :root bzw. Dark-Block; fehlt ein Token im Dark-Block, gilt der helle Wert).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/sidebar_aktiv_kontrast.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const CSS = readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');
const SIDEBAR = readFileSync(join(FRONTEND_SRC, 'lib/components/ui/sidebar/Sidebar.svelte'), 'utf-8');
const MIN = 4.5;

type Modus = 'hell' | 'dunkel';
type Rgba = [number, number, number, number];

function blockAb(kopf: RegExp): string {
	const m = kopf.exec(CSS);
	assert.ok(m, `Block ${kopf} fehlt in app.css`);
	const auf = CSS.indexOf('{', m!.index);
	let tiefe = 0;
	for (let i = auf; i < CSS.length; i++) {
		if (CSS[i] === '{') tiefe++;
		else if (CSS[i] === '}' && --tiefe === 0) return CSS.slice(auf + 1, i);
	}
	throw new Error('Block ohne Ende');
}
const HELL = blockAb(/:root\s*\{/);
const DUNKEL = blockAb(/:root\[data-theme=(["'])dark\1\]\s*\{/);
const decl = (block: string, name: string) =>
	block.match(new RegExp(`(?:^|[;{\\s])--${name}\\s*:\\s*([^;]+);`))?.[1].trim() ?? null;

function farbe(wert: string, modus: Modus, tiefe = 0): Rgba {
	assert.ok(tiefe < 8, `var()-Kette zu tief: ${wert}`);
	const w = wert.trim().toLowerCase();
	const v = w.match(/^var\(--([a-z0-9-]+)\)$/);
	if (v) {
		const roh = (modus === 'dunkel' ? decl(DUNKEL, v[1]) : null) ?? decl(HELL, v[1]);
		assert.ok(roh, `Token --${v[1]} nicht definiert`);
		return farbe(roh!, modus, tiefe + 1);
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

/** Aktiver Zweig `prop: {active ? '<wert>' : …}` des Nav-Links in Sidebar.svelte. */
function aktiverWert(prop: 'background' | 'color'): string {
	const m = SIDEBAR.match(new RegExp(`(?:^|[\\s;])${prop}\\s*:\\s*\\{active\\s*\\?\\s*'([^']+)'`, 'm'));
	assert.ok(m, `Sidebar.svelte: aktiver Zweig fuer ${prop} nicht gefunden`);
	return m![1];
}
/** Grund der <aside> (Inline-Style). */
function seitenleistenGrund(): string {
	const aside = SIDEBAR.slice(SIDEBAR.indexOf('<aside'), SIDEBAR.indexOf('>', SIDEBAR.indexOf('<aside')));
	const m = aside.match(/background\s*:\s*([^;]+);/);
	assert.ok(m, 'Sidebar.svelte: <aside> ohne background');
	return m![1].trim();
}

describe('#2400: aktiver Seitenleisten-Eintrag >= 4,5:1 (hell und dunkel)', () => {
	for (const modus of ['hell', 'dunkel'] as Modus[]) {
		test(modus, () => {
			const grund = farbe(seitenleistenGrund(), modus);
			const flaeche = ueber(farbe(aktiverWert('background'), modus), grund);
			const schrift = farbe(aktiverWert('color'), modus);
			assert.equal(schrift[3], 1, 'Schrift nicht deckend');
			const k = kontrast(schrift, flaeche);
			assert.ok(k >= MIN, `${modus}: ${k.toFixed(2)}:1 < ${MIN}:1`);
		});
	}
	test('Hell-Aussehen unveraendert: 10-%-Akzenttoenung, Schrift --g-accent-deep', () => {
		assert.deepEqual(farbe(aktiverWert('background'), 'hell'), [196, 90, 42, 0.1]);
		assert.deepEqual(farbe(aktiverWert('color'), 'hell'), farbe('var(--g-accent-deep)', 'hell'));
	});
});
