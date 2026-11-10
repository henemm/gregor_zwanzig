// Issue #2400 (Staging-Messlauf 2, 2026-11-10): Die Speicheranzeige „Gespeichert" trat nach 3 s
// per opacity 0.5 zurueck (Issue #880) — dunkel 2,9:1 (rgb(67,110,63) auf rgb(22,28,21)), hell
// ebenfalls < 4,5:1. Leitprinzip „Hoher Kontrast = Lesbarkeit" (design_system.md) hat Vorrang:
// Der Ruhezustand tritt weiter zurueck, aber jeder sichtbare Text bleibt >= 4,5:1.
//
// Gerechnet wird mit den Werten, die SaveIndicator.svelte TATSAECHLICH setzt (Zustandsregel +
// Endbild der Keyframes gz-save-fade inkl. opacity), aufgeloest gegen app.css (heller :root
// bzw. Dark-Block). Der Indikator ist ein fixes Overlay: Grund ist die Seite (--g-paper) oder
// eine Karte darunter (--g-surface-1/-2) — alle drei werden geprueft.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/speicheranzeige_ruhe_kontrast.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const ohneKommentare = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '');
const CSS = ohneKommentare(readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8'));
const KOMP = ohneKommentare(readFileSync(join(FRONTEND_SRC, 'lib/components/ui/SaveIndicator.svelte'), 'utf-8'));
const STIL = KOMP.slice(KOMP.indexOf('<style>'), KOMP.indexOf('</style>'));
const MIN = 4.5;
const GRUENDE = ['--g-paper', '--g-surface-1', '--g-surface-2'];

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
	const hex = w.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
	if (hex) {
		const h = hex[1].length === 3 ? hex[1].replace(/./g, (c) => c + c) : hex[1];
		return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).concat(1) as Rgba;
	}
	const r = w.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
	assert.ok(r, `Farbe nicht auswertbar: ${wert}`);
	return [+r![1], +r![2], +r![3], r![4] === undefined ? 1 : +r![4]];
}
const ueber = (f: Rgba, g: Rgba, a = f[3]): Rgba => [0, 1, 2].map((i) => f[i] * a + g[i] * (1 - a)).concat(1) as Rgba;
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

type Bild = { color: string; background: string; opacity: number };
const regel = (sel: RegExp) => blockAb(STIL, sel);
const zustand = (sel: RegExp): Bild => {
	const r = regel(sel);
	return { color: decl(r, 'color')!, background: decl(r, 'background') ?? 'transparent', opacity: +(decl(r, 'opacity') ?? 1) };
};
const IDLE = zustand(/\.save-indicator--idle\s*\{/);
/** Endbild nach gz-save-fade (animation-fill-mode forwards): Keyframe-Werte ueberschreiben. */
function ruheEndbild(): Bild {
	assert.match(regel(/\.save-indicator--idle\s*\{/), /animation\s*:\s*gz-save-fade\b[^;]*forwards/);
	const ende = blockAb(blockAb(STIL, /@keyframes\s+gz-save-fade\s*\{/), /(?:to|100%)\s*\{/);
	assert.doesNotMatch(ende, /display\s*:\s*none|visibility\s*:\s*hidden/, '#880: nie display:none/visibility:hidden');
	return {
		color: decl(ende, 'color') ?? IDLE.color,
		background: decl(ende, 'background') ?? IDLE.background,
		opacity: +(decl(ende, 'opacity') ?? IDLE.opacity)
	};
}

/** Kontrast der Schrift gegen die eigene Flaeche, beides mit Element-Deckkraft ueber dem Grund. */
function bildKontrast(b: Bild, grund: string, modus: Modus): number {
	const g = farbe(`var(${grund})`, modus);
	const flaeche = ueber(ueber(farbe(b.background, modus), g), g, b.opacity);
	const schrift = farbe(b.color, modus);
	assert.equal(schrift[3], 1, 'Schrift nicht deckend');
	return kontrast(ueber(schrift, g, b.opacity), flaeche);
}

describe('#2400/#880: Speicheranzeige — Ruhezustand tritt zurueck, Text bleibt >= 4,5:1', () => {
	const zustaende: Record<string, () => Bild> = {
		'idle (Endbild nach 3 s)': ruheEndbild,
		'idle (frisch gespeichert)': () => IDLE,
		dirty: () => zustand(/\.save-indicator--dirty\s*\{/),
		saving: () => zustand(/\.save-indicator--saving\s*\{/),
		error: () => zustand(/\.save-indicator--error\s*\{/),
		conflict: () => zustand(/\.save-indicator\[data-state='conflict'\]\s*\{/)
	};
	for (const [name, bild] of Object.entries(zustaende)) {
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			test(`${name} — ${modus}`, () => {
				for (const grund of GRUENDE) {
					const k = bildKontrast(bild(), grund, modus);
					assert.ok(k >= MIN, `${name}/${modus} auf ${grund}: ${k.toFixed(2)}:1 < ${MIN}:1`);
				}
			});
		}
	}
	test('Ruhezustand tritt sichtbar zurueck (Toenung weg oder Schrift wechselt)', () => {
		const ende = ruheEndbild();
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			const flaecheWeg = farbe(ende.background, modus)[3] < farbe(IDLE.background, modus)[3];
			const schriftAnders = farbe(ende.color, modus).join() !== farbe(IDLE.color, modus).join();
			assert.ok(flaecheWeg || schriftAnders || ende.opacity < IDLE.opacity, `${modus}: Endbild = Startbild`);
		}
	});
});
