// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 2.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-11, Klarstellung K-3.
//
// Soll: app.css bekommt vier Ampel-Tokens --g-ampel-gruen/-gelb/-orange/-rot,
//   - im ersten (hellen) `:root`-Block UND eigens im Block `:root[data-theme="dark"]` (kein Erben),
//   - je Modus mit WCAG-Kontrast >= 3:1 gegen den Karten-Hintergrund --g-card desselben Modus,
//   - „nahe am Mockup“ (#15803d, #d69500, #d4530a, #a8104a): Farbton ±8°, Light-Helligkeit (HSL)
//     ±8 Punkte, Dark-Helligkeit >= Mockup und höchstens +20 Punkte,
//   - Abweichung vom Mockup nur dort, wo WCAG es verlangt: erreicht der Mockup-Wert im Modus selbst
//     3:1, ist der Token genau der Mockup-Wert.
//
// Messweise: Token-Quelle ist die Stylesheet-Datei selbst (wie dark_palette_kontrast.test.ts):
// doc-compliance-test
//
// RED heute: kein --g-ampel-* in app.css.
//
//   cd frontend && npm test -- src/lib/__tests__/ampel_tokens_kontrast.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const APP_CSS = readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');
const MIN = 3;

// ─── CSS lesen ────────────────────────────────────────────────────────────────

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
const hellBlock = (): string => blockAb(APP_CSS, HELL_KOPF.exec(APP_CSS)!.index);
function darkBlock(): string {
	const m = DARK_KOPF.exec(APP_CSS);
	assert.ok(m, 'app.css hat keinen Dark-Block `:root[data-theme="dark"] { … }`');
	return blockAb(APP_CSS, m!.index);
}

function deklaration(block: string, name: string): string | null {
	const m = block.match(new RegExp(`(?:^|[;{\\s])--${name}\\s*:\\s*([^;]+);`));
	return m ? m[1].trim() : null;
}

type Modus = 'hell' | 'dunkel';
type Rgb = [number, number, number];

/** Roher Wert im Modus. `streng`: der Dark-Wert muss im Dark-Block selbst stehen (kein Erben). */
function roh(name: string, modus: Modus, streng = false): string {
	const dunkel = modus === 'dunkel' ? deklaration(darkBlock(), name) : null;
	if (modus === 'dunkel' && streng) {
		assert.ok(dunkel, `TDD RED: Token --${name} fehlt im Dark-Block :root[data-theme="dark"] (eigener Dark-Wert verlangt)`);
		return dunkel!;
	}
	const wert = dunkel ?? deklaration(hellBlock(), name);
	assert.ok(wert, `TDD RED: Token --${name} fehlt im ersten :root-Block von app.css`);
	return wert!;
}

function hexRgb(w: string): Rgb {
	const hex = w.toLowerCase().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
	assert.ok(hex, `keine deckende Hex-Farbe: ${w}`);
	const h = hex![1].length === 3 ? hex![1].replace(/./g, (c) => c + c) : hex![1];
	return [0, 1, 2].map((i) => parseInt(h.slice(i * 2, i * 2 + 2), 16)) as Rgb;
}

function farbe(name: string, modus: Modus, streng = false, tiefe = 0): Rgb {
	assert.ok(tiefe < 8, `var()-Kette bei --${name} zu tief`);
	const w = roh(name, modus, streng && tiefe === 0).toLowerCase();
	const v = w.match(/^var\(--([a-z0-9-]+)(?:\s*,[^)]*)?\)$/);
	if (v) return farbe(v[1], modus, false, tiefe + 1);
	return hexRgb(w);
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

/** HSL: Farbton in Grad, Helligkeit in Prozentpunkten. */
function hsl([r, g, b]: Rgb): { h: number; l: number } {
	const [rr, gg, bb] = [r / 255, g / 255, b / 255];
	const max = Math.max(rr, gg, bb);
	const min = Math.min(rr, gg, bb);
	const l = ((max + min) / 2) * 100;
	const d = max - min;
	if (d === 0) return { h: 0, l };
	let h: number;
	if (max === rr) h = ((gg - bb) / d) % 6;
	else if (max === gg) h = (bb - rr) / d + 2;
	else h = (rr - gg) / d + 4;
	h *= 60;
	if (h < 0) h += 360;
	return { h, l };
}
const tonAbstand = (a: number, b: number) => {
	const d = Math.abs(a - b) % 360;
	return d > 180 ? 360 - d : d;
};

// ─── Soll ─────────────────────────────────────────────────────────────────────

const MOCKUP: Record<string, string> = {
	'g-ampel-gruen': '#15803d',
	'g-ampel-gelb': '#d69500',
	'g-ampel-orange': '#d4530a',
	'g-ampel-rot': '#a8104a'
};
const MODI: Modus[] = ['hell', 'dunkel'];

describe('AC-11: Ampel-Tokens existieren in Light und (eigenem) Dark-Block', () => {
	for (const name of Object.keys(MOCKUP)) {
		test(`--${name} im ersten :root-Block`, () => {
			assert.ok(deklaration(hellBlock(), name), `TDD RED: --${name} fehlt im ersten :root-Block von app.css`);
		});
		test(`--${name} im Dark-Block :root[data-theme="dark"]`, () => {
			assert.ok(deklaration(darkBlock(), name), `TDD RED: --${name} fehlt im Dark-Block (eigener Dark-Wert verlangt)`);
		});
	}
});

describe('AC-11: Kontrast >= 3:1 gegen --g-card je Modus', () => {
	for (const modus of MODI) {
		for (const name of Object.keys(MOCKUP)) {
			test(`--${name} (${modus}) gegen --g-card >= ${MIN}:1`, () => {
				const k = kontrast(farbe(name, modus, true), farbe('g-card', modus));
				assert.ok(k >= MIN, `--${name} (${modus}) hat nur ${k.toFixed(2)}:1 gegen --g-card`);
			});
		}
	}
});

describe('AC-11/K-3: nahe am Mockup, Abweichung nur wo WCAG es verlangt', () => {
	for (const modus of MODI) {
		for (const [name, mock] of Object.entries(MOCKUP)) {
			test(`--${name} (${modus}): Farbton ±8°, Helligkeit im Korridor`, () => {
				const ist = hsl(farbe(name, modus, true));
				const soll = hsl(hexRgb(mock));
				const dTon = tonAbstand(ist.h, soll.h);
				assert.ok(dTon <= 8, `--${name} (${modus}): Farbton ${ist.h.toFixed(1)}° weicht ${dTon.toFixed(1)}° vom Mockup ${mock} ab`);
				const dL = ist.l - soll.l;
				if (modus === 'hell') {
					assert.ok(Math.abs(dL) <= 8, `--${name} (hell): Helligkeit ${ist.l.toFixed(1)} weicht ${dL.toFixed(1)} Punkte vom Mockup ab (±8)`);
				} else {
					assert.ok(dL >= 0 && dL <= 20, `--${name} (dunkel): Helligkeit ${ist.l.toFixed(1)} muss zwischen Mockup ${soll.l.toFixed(1)} und +20 liegen`);
				}
			});
			test(`--${name} (${modus}): gleich Mockup, wenn das Mockup selbst 3:1 erreicht`, () => {
				const mockK = kontrast(hexRgb(mock), farbe('g-card', modus));
				const w = roh(name, modus, true).toLowerCase();
				const ist = /^#/.test(w) ? w : null;
				if (mockK >= MIN) {
					assert.equal(ist, mock, `--${name} (${modus}): Mockup ${mock} erreicht ${mockK.toFixed(2)}:1 — keine Abweichung erlaubt`);
				} else {
					assert.notEqual(ist, mock, `--${name} (${modus}): Mockup ${mock} erreicht nur ${mockK.toFixed(2)}:1 — muss angepasst sein`);
				}
			});
		}
	}
});

// #2913 Fix Metrik-Liste, Fix-Runde 1 (F001): „grün: …“ in der Metrik-Zeile ist TEXT (12 px/600), kein Grafik-
// Element — dafür gilt WCAG-AA 4,5:1, nicht 3:1. --g-ampel-gruen erreicht dunkel nur 3,37:1; die Zeile nutzt den
// Text-Token --g-ok-fg (eigener Dark-Wert). Fällt er unter 4,5:1 gegen Karte oder Karten-Alt, wird das hier rot.
const TEXT_MIN = 4.5;
describe('#2913 Fix Metrik-Liste: grüner Text (--g-ok-fg) >= 4,5:1 je Modus', () => {
	for (const modus of MODI) {
		for (const grund of ['g-card', 'g-card-alt']) {
			test(`--g-ok-fg (${modus}) gegen --${grund} >= ${TEXT_MIN}:1`, () => {
				const k = kontrast(farbe('g-ok-fg', modus, true), farbe(grund, modus));
				assert.ok(k >= TEXT_MIN, `--g-ok-fg (${modus}) hat nur ${k.toFixed(2)}:1 gegen --${grund}`);
			});
		}
	}
});
