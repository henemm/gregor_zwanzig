// Issue #2954 (ADR-0120): Der Speicherhinweis ist kein festes Overlay unten rechts mehr, sondern
// schlichter Inline-Text in der Kopfleiste (HubKopf .hub-actions, vor dem Drei-Punkte-Menü):
// kein Hintergrund, 12,5 px, Erfolg in --g-good, Fehler/Konflikt in --g-danger-fg. „Gespeichert"
// verschwindet per JS-Timer 5 s nach dem Speichern — die frühere Abblend-Animation gz-save-fade
// (#880/#2400) entfällt. Spec: docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md, AC-9.
//
// Stilvertrag + Kontrast: Gerechnet wird mit den Werten, die SaveIndicator.svelte TATSAECHLICH
// setzt (Zustandsregeln), aufgeloest gegen app.css (heller :root bzw. Dark-Block). Grund ist der
// Kopfgrund — die Kopfleiste ist transparent, darunter liegt die Seite (--g-paper). Leitprinzip
// „Hoher Kontrast = Lesbarkeit" (design_system.md): jeder Zustandstext >= 4,5:1, hell und dunkel.
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
/** Kopfgrund: .hub-kopf-leiste ist transparent, darunter die Seite. */
const KOPFGRUND = '--g-paper';

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
	if (w === 'transparent' || w === 'none') return [0, 0, 0, 0];
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

type Bild = { color: string; background: string | null; opacity: number };
const regel = (sel: RegExp) => blockAb(STIL, sel);
const BASIS_SEL = /\.save-indicator\s*\{/;
const ZUSTAENDE: Record<string, RegExp> = {
	idle: /\.save-indicator--idle\s*\{/,
	dirty: /\.save-indicator--dirty\s*\{/,
	saving: /\.save-indicator--saving\s*\{/,
	error: /\.save-indicator--error\s*\{/,
	conflict: /\.save-indicator\[data-state='conflict'\]\s*\{/
};
const zustand = (sel: RegExp): Bild => {
	const r = regel(sel);
	const color = decl(r, 'color');
	assert.ok(color, `Zustandsregel ${sel} setzt keine Schriftfarbe`);
	return {
		color: color!,
		background: decl(r, 'background') ?? decl(r, 'background-color'),
		opacity: +(decl(r, 'opacity') ?? 1)
	};
};
/** Kein Hintergrund: Deklaration fehlt, oder sie ist transparent/none. */
const ohneHintergrund = (wert: string | null) => wert === null || /^(transparent|none)$/i.test(wert.trim());

/** Kontrast der Schrift (mit Element-Deckkraft) direkt auf dem Kopfgrund. */
function textKontrast(b: Bild, modus: Modus): number {
	const g = farbe(`var(${KOPFGRUND})`, modus);
	const schrift = farbe(b.color, modus);
	assert.equal(schrift[3], 1, 'Schrift nicht deckend');
	return kontrast(ueber(schrift, g, b.opacity), g);
}

describe('#2954 Stilvertrag: Inline-Text in der Kopfleiste statt festes Overlay', () => {
	test('Basisregel .save-indicator: kein position: fixed (kein Overlay mehr)', () => {
		assert.doesNotMatch(regel(BASIS_SEL), /position\s*:\s*fixed/, 'der Hinweis ist noch ein festes Overlay (position: fixed)');
		assert.doesNotMatch(STIL, /position\s*:\s*fixed/, 'irgendeine Regel setzt noch position: fixed');
	});

	test('Basisregel .save-indicator: Schriftgröße 12,5 px', () => {
		assert.equal(decl(regel(BASIS_SEL), 'font-size'), '12.5px');
	});

	test('Basisregel .save-indicator: kein Hintergrund', () => {
		const basis = regel(BASIS_SEL);
		assert.ok(ohneHintergrund(decl(basis, 'background')), `Basis-Hintergrund: ${decl(basis, 'background')}`);
		assert.ok(ohneHintergrund(decl(basis, 'background-color')), `Basis-Hintergrund: ${decl(basis, 'background-color')}`);
	});

	for (const [name, sel] of Object.entries(ZUSTAENDE)) {
		test(`${name}: kein Hintergrund (transparent/none)`, () => {
			const b = zustand(sel);
			assert.ok(ohneHintergrund(b.background), `${name} hat Hintergrund ${b.background}`);
		});
	}

	test('Erfolg (idle) in var(--g-good)', () => {
		assert.equal(zustand(ZUSTAENDE.idle).color, 'var(--g-good)');
	});

	test('Fehler (error) und Konflikt (conflict) in var(--g-danger-fg)', () => {
		assert.equal(zustand(ZUSTAENDE.error).color, 'var(--g-danger-fg)');
		assert.equal(zustand(ZUSTAENDE.conflict).color, 'var(--g-danger-fg)');
	});

	test('keine Abblend-Animation gz-save-fade mehr (Ausblenden per 5-s-Timer)', () => {
		assert.doesNotMatch(STIL, /gz-save-fade/, 'gz-save-fade (Keyframes oder animation) ist noch vorhanden');
	});
});

describe('#2954 AC-9: Zustandsfarben gegen den Kopfgrund >= 4,5:1, hell und dunkel', () => {
	for (const [name, sel] of Object.entries(ZUSTAENDE)) {
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			test(`${name} — ${modus}`, () => {
				const k = textKontrast(zustand(sel), modus);
				assert.ok(k >= MIN, `${name}/${modus} auf ${KOPFGRUND}: ${k.toFixed(2)}:1 < ${MIN}:1`);
			});
		}
	}
	test('Token-Gegenprobe: --g-good und --g-danger-fg selbst >= 4,5:1 auf --g-paper', () => {
		for (const modus of ['hell', 'dunkel'] as Modus[]) {
			for (const t of ['--g-good', '--g-danger-fg']) {
				const k = kontrast(farbe(`var(${t})`, modus), farbe(`var(${KOPFGRUND})`, modus));
				assert.ok(k >= MIN, `${t}/${modus}: ${k.toFixed(2)}:1 < ${MIN}:1`);
			}
		}
	});
});
