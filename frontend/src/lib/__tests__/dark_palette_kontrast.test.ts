// TDD RED — Issue #2400 (Epic #2508): vollständiger Dark Mode.
// Spec: docs/specs/modules/fix_2400_dark_mode_vollstaendig.md — AC-1 (Token-Teil), AC-2, AC-6,
// AC-7, AC-9, AC-12 (Kern-Schicht, deterministisch, ohne Netz).
//
// Gegenstand ist die Farbpalette in app.css: der helle `:root`-Block und der Dark-Block
// `:root[data-theme="dark"]`. Gerechnet wird der WCAG-Kontrast der Paare, die im gerenderten
// Dunkelmodus nebeneinander stehen (Text auf Fläche, Linie auf Fläche, Schrift auf Akzent- bzw.
// Statusbox). Werte, die im Dark-Block fehlen, erben den hellen Wert (CSS-Kaskade) — genau so
// wird hier aufgelöst, damit ein vergessener Token als heller Wert auf dunklem Grund rot wird.
// Den Browser-Nachweis am DOM liefert e2e/dark-mode-alle-routen.staging.spec.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/dark_palette_kontrast.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const APP_CSS = readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8');
const TEXT_MIN = 4.5;
const LINIE_MIN = 3;

// ─── CSS lesen ────────────────────────────────────────────────────────────────

/** Inhalt des ersten Blocks nach `kopfIndex` (ausbalancierte geschweifte Klammern). */
function blockAb(css: string, kopfIndex: number): string {
	const auf = css.indexOf('{', kopfIndex);
	let tiefe = 0;
	for (let i = auf; i < css.length; i++) {
		if (css[i] === '{') tiefe++;
		else if (css[i] === '}' && --tiefe === 0) return css.slice(auf + 1, i);
	}
	throw new Error('Block ohne schließende Klammer');
}

const DARK_KOPF = /:root\[data-theme=(["'])dark\1\]\s*\{/;
const HELL_KOPF = /:root\s*\{/;

function darkIndex(): number {
	const m = DARK_KOPF.exec(APP_CSS);
	assert.ok(m, 'app.css hat keinen Dark-Block `:root[data-theme="dark"] { … }`');
	return m!.index;
}
const hellBlock = (): string => blockAb(APP_CSS, HELL_KOPF.exec(APP_CSS)!.index);
const darkBlock = (): string => blockAb(APP_CSS, darkIndex());

function deklaration(block: string, name: string): string | null {
	const m = block.match(new RegExp(`(?:^|[;{\\s])--${name}\\s*:\\s*([^;]+);`));
	return m ? m[1].trim() : null;
}

type Modus = 'hell' | 'dunkel';

/** Roher Wert eines Tokens im Modus — Dark erbt den hellen Wert, wenn er fehlt (Kaskade). */
function roh(name: string, modus: Modus): string {
	const wert = (modus === 'dunkel' ? deklaration(darkBlock(), name) : null) ?? deklaration(hellBlock(), name);
	assert.ok(wert, `Token --${name} ist weder im hellen :root noch im Dark-Block definiert`);
	return wert!;
}

type Rgb = [number, number, number];
/** Farbe eines Tokens als deckendes RGB (var() wird im selben Modus aufgelöst). */
function farbe(name: string, modus: Modus, tiefe = 0): Rgb {
	assert.ok(tiefe < 8, `var()-Kette bei --${name} zu tief`);
	const w = roh(name, modus).toLowerCase();
	const v = w.match(/^var\(--([a-z0-9-]+)(?:\s*,[^)]*)?\)$/);
	if (v) return farbe(v[1], modus, tiefe + 1);
	const hex = w.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
	assert.ok(hex, `--${name} (${modus}) ist keine deckende Farbe: ${w}`);
	const h = hex![1].length === 3 ? hex![1].replace(/./g, (c) => c + c) : hex![1];
	return [0, 1, 2].map((i) => parseInt(h.slice(i * 2, i * 2 + 2), 16)) as Rgb;
}

function luminanz([r, g, b]: Rgb): number {
	const k = (c: number) => {
		const s = c / 255;
		return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b);
}
function kontrast(a: Rgb, b: Rgb): number {
	const [h, d] = [luminanz(a), luminanz(b)].sort((x, y) => y - x);
	return (h + 0.05) / (d + 0.05);
}
const k = (vorn: string, grund: string, modus: Modus) => kontrast(farbe(vorn, modus), farbe(grund, modus));
const hexRgb = (h: string): Rgb => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as Rgb;

// ─── Paare aus der Spec ───────────────────────────────────────────────────────

/** Flächen, auf denen Text steht (AC-2: paper, card, card-alt, surface-2 — plus deren Aliase). */
const FLAECHEN = [
	'g-paper',
	'g-card',
	'g-card-alt',
	'g-surface-2',
	'g-surface-0',
	'g-surface-1',
	'g-surface-raised',
	'g-paper-deep'
];

/** Text-Tokens (AC-2) plus ihre hellen Aliase, die heute eigene Hex-Werte tragen. */
const TEXT_TOKENS = [
	'g-ink',
	'g-ink-2',
	'g-ink-3',
	'g-ink-muted',
	'g-accent-text',
	'g-success',
	'g-good',
	'g-warn',
	'g-warning',
	'g-danger',
	'g-bad',
	'g-info'
];

/** Tokens mit hellem Wert, die im Dark-Block einen eigenen Wert brauchen (Flächen, Ink, Rule, Nav, Schatten, Akzent). */
const MUSS_UEBERSCHRIEBEN = [
	...FLAECHEN,
	'g-ink',
	'g-ink-2',
	'g-ink-3',
	'g-ink-4',
	'g-ink-muted',
	'g-ink-faint',
	'g-rule',
	'g-rule-soft',
	'g-success',
	'g-good',
	'g-warn',
	'g-warning',
	'g-danger',
	'g-bad',
	'g-info',
	'g-accent',
	'g-accent-soft',
	'g-accent-tint',
	'g-accent-text',
	'g-nav-glass',
	'g-nav-hairline',
	'g-nav-highlight',
	'g-nav-active',
	'g-shadow-1',
	'g-shadow-2',
	'g-shadow-3',
	'g-elev-1',
	'g-elev-2',
	'g-elev-3'
];

const STATUS = ['ok', 'warn', 'danger'] as const;
const MODI: Modus[] = ['hell', 'dunkel'];

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('Mechanik: Dark-Block steht in app.css hinter dem hellen :root', () => {
	test('Dark-Block existiert und folgt dem hellen :root (Regex-Tests lesen den hellen Treffer zuerst)', () => {
		const hell = HELL_KOPF.exec(APP_CSS);
		assert.ok(hell, 'heller :root-Block fehlt');
		assert.ok(darkIndex() > hell!.index, 'Dark-Block muss HINTER dem hellen :root stehen');
	});
	test('Dark-Block setzt color-scheme: dark (Formularelemente, Scrollleisten)', () => {
		assert.match(darkBlock(), /(?:^|[;{\s])color-scheme\s*:\s*dark\s*;/);
	});
	for (const name of MUSS_UEBERSCHRIEBEN) {
		test(`--${name} hat im Dark-Block einen eigenen Wert`, () => {
			assert.ok(deklaration(darkBlock(), name), `--${name} fehlt im Dark-Block — bliebe im Dunkelmodus hell`);
		});
	}
});

describe('Flächen sind im Dunkelmodus dunkel (keine weißen Karten)', () => {
	for (const f of FLAECHEN) {
		test(`--${f} dunkel: Luminanz < 0,05`, () => {
			const l = luminanz(farbe(f, 'dunkel'));
			assert.ok(l < 0.05, `--${f} im Dark hat Luminanz ${l.toFixed(3)} — helle Fläche auf dunklem Grund`);
		});
	}
});

describe('AC-1 / AC-2: Text-Tokens im Dark ≥ 4,5:1 auf jeder Fläche', () => {
	for (const t of TEXT_TOKENS) {
		for (const f of FLAECHEN) {
			test(`--${t} auf --${f} (dunkel)`, () => {
				const v = k(t, f, 'dunkel');
				assert.ok(v >= TEXT_MIN, `--${t} auf --${f} im Dark = ${v.toFixed(2)}:1 < ${TEXT_MIN}`);
			});
		}
	}
	test('Gegenprobe: --g-ink-3 hell (#6b675c) auf dunklem paper fällt durch', () => {
		const v = kontrast(hexRgb('#6b675c'), farbe('g-paper', 'dunkel'));
		assert.ok(v < TEXT_MIN, `Messlogik zu großzügig: ${v.toFixed(2)}`);
	});
});

describe('AC-6: Hellmodus unverändert', () => {
	const SNAPSHOT: Record<string, string> = {
		'g-paper': '#f6f4ee',
		'g-card': '#ffffff',
		'g-ink': '#1a1a18',
		'g-ink-2': '#45433d',
		'g-ink-3': '#6b675c',
		'g-ink-4': '#9a958a',
		'g-rule': '#d8d3c2'
	};
	for (const [name, hex] of Object.entries(SNAPSHOT)) {
		test(`--${name} hell bleibt ${hex}`, () => {
			assert.equal(roh(name, 'hell').toLowerCase(), hex);
		});
		test(`--${name}: erster Treffer in app.css ist der helle Wert (Bestandstests mit token()-Regex)`, () => {
			const m = APP_CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\b`));
			assert.equal(m?.[1].toLowerCase(), hex);
		});
	}
});

describe('AC-7: Schrift auf Akzentfläche ≥ 4,5:1 in beiden Modi', () => {
	for (const modus of MODI) {
		test(`--g-on-accent auf --g-accent-deep (${modus})`, () => {
			const v = k('g-on-accent', 'g-accent-deep', modus);
			assert.ok(v >= TEXT_MIN, `--g-on-accent auf --g-accent-deep (${modus}) = ${v.toFixed(2)}:1`);
		});
	}
	test('Gegenprobe: Weiß auf --g-accent hell (#c45a2a) fällt durch (4,34:1)', () => {
		const v = kontrast([255, 255, 255], farbe('g-accent', 'hell'));
		assert.ok(v < TEXT_MIN, `Messlogik zu großzügig: ${v.toFixed(2)}`);
	});
});

describe('AC-9: Statusboxen — Schrift auf Box ≥ 4,5:1, Box passt zum Modus', () => {
	for (const s of STATUS) {
		for (const modus of MODI) {
			test(`--g-${s}-fg auf --g-${s}-bg (${modus})`, () => {
				const v = k(`g-${s}-fg`, `g-${s}-bg`, modus);
				assert.ok(v >= TEXT_MIN, `--g-${s}-fg auf --g-${s}-bg (${modus}) = ${v.toFixed(2)}:1`);
			});
		}
		test(`--g-${s}-bg ist im Dark eine dunkle Fläche`, () => {
			const l = luminanz(farbe(`g-${s}-bg`, 'dunkel'));
			assert.ok(l < 0.1, `--g-${s}-bg im Dark hat Luminanz ${l.toFixed(3)} — helle Box auf dunklem Grund`);
		});
	}
});

describe('AC-12: Bedien-Linien und Fokusring im Dark ≥ 3:1 (WCAG 1.4.11)', () => {
	/** --color-border/--color-input: im Dark-Block gesetzt, sonst über @theme = --g-ink-faint. */
	const linie = (name: 'color-border' | 'color-input'): string =>
		deklaration(darkBlock(), name) ? name : 'g-ink-faint';
	const GRUENDE = ['g-paper', 'g-card', 'g-surface-2'];
	for (const l of ['color-border', 'color-input'] as const) {
		for (const g of GRUENDE) {
			test(`--${l} gegen --${g} (dunkel)`, () => {
				const v = k(linie(l), g, 'dunkel');
				assert.ok(v >= LINIE_MIN, `--${l} gegen --${g} im Dark = ${v.toFixed(2)}:1 < ${LINIE_MIN}`);
			});
		}
	}
	for (const g of GRUENDE) {
		test(`Fokusring --g-accent gegen --${g} (dunkel)`, () => {
			const v = k('g-accent', g, 'dunkel');
			assert.ok(v >= LINIE_MIN, `--g-accent gegen --${g} im Dark = ${v.toFixed(2)}:1 < ${LINIE_MIN}`);
		});
	}
});
