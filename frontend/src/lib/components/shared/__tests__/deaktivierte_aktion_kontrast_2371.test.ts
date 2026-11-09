// TDD RED — Issue #2371, AC-3 (+ AC-5 Gleichbehandlung Trip/Vergleich):
// Die deaktivierte Hauptaktion der Anlege-Editoren („Speichern" in /trips/new,
// „Briefing aktivieren" in /compare/new) und der geteilte Knopf
// „Mit Standardwerten speichern" sind gesperrt mit
//   - Text >= 4,5:1 effektiv (keine Zusatz-Opacity, Textfarbe --g-ink-3),
//   - aria-disabled="true",
//   - weiterhin ohne Klick-Wirkung (natives disabled bleibt).
// Spec: docs/specs/modules/ink4_kontrast_2371.md (AC-3)
//
// Messwege (kein Quelltext-Grep als Verhaltensnachweis):
//   - echte SSR-Renderings beider Editoren und des geteilten Knopfs (infoboxSsr.ts);
//   - die Btn-Stilregel für den gesperrten Zustand aus app.css (globale Regel, die
//     der Browser auf [data-slot="btn"][disabled] anwendet) und die Inline-Stile
//     des gerenderten Knopfs; Kontrast nach WCAG-Formel gegen --g-paper und Weiß.
//   Die Browser-Messung (getComputedStyle inkl. Vorfahren-Opacity) macht der
//   Playwright-Lauf gegen Staging.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/deaktivierte_aktion_kontrast_2371.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { FRONTEND, lade, renderKomponente, renderTrip, renderVergleichNeu, attribut } from './infoboxSsr.ts';

const APP_CSS = readFileSync(path.join(FRONTEND, 'src/app.css'), 'utf-8');

function token(name: string): string {
	const m = APP_CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\b`));
	assert.ok(m, `Token --${name} nicht in app.css`);
	return m![1];
}
function luminanz(hex: string): number {
	const k = (i: number) => {
		const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
		return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * k(0) + 0.7152 * k(1) + 0.0722 * k(2);
}
function kontrast(a: string, b: string): number {
	const [h, d] = [luminanz(a), luminanz(b)].sort((x, y) => y - x);
	return (h + 0.05) / (d + 0.05);
}
/** Löst `var(--g-xyz)` bzw. #hex in einen #rrggbb-Wert auf. */
function farbe(wert: string): string {
	const v = wert.trim();
	const m = v.match(/^var\(--([\w-]+)\)$/);
	if (m) return token(m[1]);
	assert.match(v, /^#[0-9a-fA-F]{6}$/, `Farbe nicht auflösbar: ${v}`);
	return v;
}

function knopfTag(html: string, testid: string): string {
	const m = new RegExp(`<button\\b[^>]*data-testid="${testid}"[^>]*>`).exec(html);
	assert.ok(m, `kein <button data-testid="${testid}">`);
	return m![0];
}
const istNativDisabled = (tag: string) => /\sdisabled(=|\s|>)/.test(tag);

/** Deklarationen des Blocks für den gesperrten Btn-Zustand aus app.css. */
function btnDisabledRegel(): Record<string, string> {
	const m = APP_CSS.match(/\[data-slot="btn"\]\[disabled\][^{]*\{([^}]*)\}/);
	assert.ok(m, 'app.css: keine Regel für [data-slot="btn"][disabled]');
	const out: Record<string, string> = {};
	for (const d of m![1].split(';')) {
		const [k, ...v] = d.split(':');
		if (k?.trim() && v.length) out[k.trim()] = v.join(':').trim();
	}
	return out;
}
function inlineStil(tag: string): Record<string, string> {
	const s = attribut(tag, 'style') ?? '';
	const out: Record<string, string> = {};
	for (const d of s.split(';')) {
		const [k, ...v] = d.split(':');
		if (k?.trim() && v.length) out[k.trim()] = v.join(':').trim();
	}
	return out;
}

function pruefeLesbar(stil: Record<string, string>, wo: string) {
	const op = stil['opacity'];
	assert.ok(op === undefined || Number(op) === 1, `${wo}: Zusatz-Opacity ${op} verdünnt den Text`);
	assert.ok(stil['color'], `${wo}: keine eigene Textfarbe im gesperrten Zustand`);
	const fg = farbe(stil['color']);
	for (const hg of ['g-paper', 'g-card']) {
		const k = kontrast(fg, token(hg));
		assert.ok(k >= 4.5, `${wo}: Kontrast ${k.toFixed(2)}:1 auf --${hg} < 4,5:1`);
	}
	const bg = stil['background-color'] ?? stil['background'];
	assert.ok(bg === undefined || bg === 'transparent' || kontrast(fg, farbe(bg)) >= 4.5, `${wo}: Hintergrund ${bg} zu dunkel`);
}

describe('AC-3: gesperrte Hauptaktion (Btn im AnlegeRahmen) — Trip und Vergleich', () => {
	test('Btn-Regel für den gesperrten Zustand: keine Opacity, Text >= 4,5:1', () => {
		pruefeLesbar(btnDisabledRegel(), 'app.css [data-slot="btn"][disabled]');
	});
	test('/trips/new ohne Namen: trip-new-save-btn gesperrt, aria-disabled="true"', async () => {
		const html = await renderTrip({ name: '', isMobileViewport: false });
		const tag = knopfTag(html, 'trip-new-save-btn');
		assert.ok(istNativDisabled(tag), 'Klick-Sperre (disabled) fehlt — Verhalten muss unverändert bleiben');
		assert.equal(attribut(tag, 'aria-disabled'), 'true');
	});
	test('/compare/new frisch: compare-editor-activate gesperrt, aria-disabled="true"', async () => {
		const html = await renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false });
		const tag = knopfTag(html, 'compare-editor-activate');
		assert.ok(istNativDisabled(tag), 'Klick-Sperre (disabled) fehlt');
		assert.equal(attribut(tag, 'aria-disabled'), 'true');
	});
});

describe('AC-3/AC-5: geteilter Knopf „Mit Standardwerten speichern" (tn-/cm-mobile-standardwerte)', () => {
	for (const [fall, props] of [
		['enabled=false', { enabled: false, saving: false }],
		['saving=true', { enabled: true, saving: true }]
	] as const) {
		test(`${fall}: gesperrt, aria-disabled="true", ohne Opacity, Text >= 4,5:1`, async () => {
			const K = await lade('shared/StandardwerteSpeichernKnopf.svelte');
			const tag = knopfTag(renderKomponente(K, { ...props, onclick: () => {}, testid: 'x-std' }), 'x-std');
			assert.ok(istNativDisabled(tag), 'Klick-Sperre (disabled) fehlt');
			assert.equal(attribut(tag, 'aria-disabled'), 'true');
			const stil = inlineStil(tag);
			assert.equal(stil['cursor'], 'not-allowed');
			pruefeLesbar(stil, `StandardwerteSpeichernKnopf ${fall}`);
		});
	}
	test('enabled=true: nicht gesperrt, kein aria-disabled', async () => {
		const K = await lade('shared/StandardwerteSpeichernKnopf.svelte');
		const tag = knopfTag(renderKomponente(K, { enabled: true, saving: false, onclick: () => {}, testid: 'x-std' }), 'x-std');
		assert.ok(!istNativDisabled(tag));
		assert.equal(attribut(tag, 'aria-disabled'), null);
		assert.equal(farbe(inlineStil(tag)['color']), token('g-ink'));
	});
	test('/trips/new mobil mit Namen: tn-mobile-standardwerte trägt aria-disabled="true"', async () => {
		const html = await renderTrip({ name: 'Trip X', startDate: '2026-07-01', isMobileViewport: true });
		assert.equal(attribut(knopfTag(html, 'tn-mobile-standardwerte'), 'aria-disabled'), 'true');
	});
	test('/compare/new mobil: cm-mobile-standardwerte trägt aria-disabled="true"', async () => {
		const html = await renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: true });
		assert.equal(attribut(knopfTag(html, 'cm-mobile-standardwerte'), 'aria-disabled'), 'true');
	});
});
