// Issue #2400 Fix-Loop 1 (F001): Schrift auf jedem Pill-Ton >= 4,5:1, hell UND dunkel.
// Gelesen wird die echte Kaskade aus app.css: Pill-Regeln `[data-slot="pill"]…[data-tone="X"]`
// (hell) plus `:root[data-theme="dark"] [data-slot="pill"]…` (Dark-Override); Tokens aus dem
// hellen :root bzw. dem Dark-Block (fehlt ein Token im Dark-Block, gilt der helle Wert —
// CSS-Kaskade). Halbtransparente oder fehlende Flaechen werden ueber Papier und Karte des
// jeweiligen Modus gelegt.
//
//   cd frontend && npm test -- src/lib/__tests__/pill_toene_kontrast.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const CSS = readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');
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

/** Wert eines Ausdrucks im Modus, var() aufgeloest, als RGBA. */
function farbe(wert: string, modus: Modus, tiefe = 0): Rgba {
	assert.ok(tiefe < 8, `var()-Kette zu tief: ${wert}`);
	const w = wert.trim().toLowerCase();
	const v = w.match(/^var\(--([a-z0-9-]+)\)$/);
	if (v) {
		const roh = (modus === 'dunkel' ? decl(DUNKEL, v[1]) : null) ?? decl(HELL, v[1]);
		assert.ok(roh, `Token --${v[1]} nicht definiert`);
		return farbe(roh!, modus, tiefe + 1);
	}
	if (w === 'transparent') return [0, 0, 0, 0];
	if (w === 'white') return [255, 255, 255, 1];
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

// ─── Pill-Regeln aus app.css ──────────────────────────────────────────────────

type Decls = Record<string, string>;
/** Schluessel `tone|outlined` → Deklarationen je Modus (hell: Basis; dunkel: Basis + Override). */
const BASIS = new Map<string, Decls>();
const DARK = new Map<string, Decls>();
/** Dark-Override mit `:not([data-outlined])`: gilt nur fuer die Flaechen-Pill. */
const DARK_NUR_FLAECHE = new Map<string, Decls>();
let outlinedBasis: Decls = {};
const SEL =
	/^(:root\[data-theme=(["'])dark\2\]\s+)?\[data-slot="pill"\](:not\(\[data-outlined\]\))?(\[data-outlined\])?(?:\[data-tone="([a-z]+)"\])?$/;
for (const m of CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
	const d: Decls = {};
	for (const teil of m[2].split(';')) {
		const i = teil.indexOf(':');
		if (i > 0) d[teil.slice(0, i).trim()] = teil.slice(i + 1).trim();
	}
	for (const sel of m[1].split(',').map((s) => s.trim())) {
		const s = sel.match(SEL);
		if (!s) continue;
		const [, dunkel, , nichtUmrandet, outlined, tone] = s;
		if (!tone) {
			if (outlined && !dunkel) outlinedBasis = { ...outlinedBasis, ...d };
			continue;
		}
		const key = `${tone}|${outlined ? 'outlined' : 'flaeche'}`;
		const ziel = dunkel ? (nichtUmrandet ? DARK_NUR_FLAECHE : DARK) : BASIS;
		ziel.set(key, { ...(ziel.get(key) ?? {}), ...d });
	}
}

function fall(key: string, modus: Modus): { fg: string; bg: string } {
	const [tone, art] = key.split('|');
	let d: Decls = { ...(BASIS.get(`${tone}|flaeche`) ?? {}) };
	if (art === 'outlined') d = { ...d, ...outlinedBasis, ...(BASIS.get(key) ?? {}) };
	if (modus === 'dunkel') {
		// Spezifitaet: `:root[data-theme] [data-slot][data-tone]` (0,4,0) schlaegt die
		// umrandete Regel (0,3,0) — ein Dark-Override ohne :not([data-outlined]) wirkt auch dort.
		d = { ...d, ...(DARK.get(`${tone}|flaeche`) ?? {}) };
		if (art === 'flaeche') d = { ...d, ...(DARK_NUR_FLAECHE.get(key) ?? {}) };
		if (art === 'outlined') d = { ...d, ...(DARK.get(key) ?? {}) };
	}
	return { fg: d.color, bg: d.background ?? d['background-color'] ?? 'transparent' };
}

/** Bekannte Altbefunde im HELLMODUS (vor #2400, AC-6 „hell unveraendert"): als todo gemeldet,
 *  nicht still gruen. Die Liste darf nur sinken. */
const BEKANNT: Record<string, string> = {
	'warn|flaeche (hell)': 'Altbefund: --g-warn-deep auf 12-%-Amber ueber Papier = 4,46:1 (eigenes Ticket)'
};

describe('F001: Schrift auf jedem Pill-Ton >= 4,5:1 in hell und dunkel (app.css-Kaskade)', () => {
	test('Messaufbau: Pill-Toene gefunden (Flaeche und umrandet)', () => {
		const toene = [...BASIS.keys()];
		for (const t of ['success|flaeche', 'warning|flaeche', 'danger|flaeche', 'info|flaeche', 'warning|outlined']) {
			assert.ok(toene.includes(t), `Pill-Ton ${t} nicht in app.css gefunden: ${toene.join(', ')}`);
		}
	});
	for (const key of [...BASIS.keys()]) {
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			const bekannt = BEKANNT[`${key} (${modus})`];
			test(`${key} (${modus})`, { todo: bekannt }, () => {
				const { fg, bg } = fall(key, modus);
				assert.ok(fg, `${key}: keine Schriftfarbe`);
				const schrift = farbe(fg, modus);
				assert.equal(schrift[3], 1, `${key}: Schrift nicht deckend (${fg})`);
				for (const grund of ['g-paper', 'g-card']) {
					const unten = farbe(`var(--${grund})`, modus);
					const flaeche = ueber(farbe(bg, modus), unten);
					const k = kontrast(schrift, flaeche);
					assert.ok(k >= MIN, `${key} (${modus}) auf --${grund}: ${fg} auf ${bg} = ${k.toFixed(2)}:1 < ${MIN}`);
				}
			});
		}
	}
});
