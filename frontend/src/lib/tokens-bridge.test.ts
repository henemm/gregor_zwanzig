// TDD RED: Issue #369 — Token-Bridge (Atomic-Design, Epic #368)
//
// Spec:    docs/specs/modules/issue_369_token_bridge.md
// Mapping: docs/design-requests/issue_15_atomic_design/spec/TOKEN-MAPPING.md
//
// Source-Inspection-Test (Pattern wie HorizonChip.test.ts / *.tokens.test.ts):
// liest src/app.css als String und prueft, dass die Atomic-Design-Bridge-Tokens
// additiv mit den korrekten Sandbox-Werten ergaenzt wurden — und dass die drei
// Kollisions-Tokens NICHT auf Sandbox-Werte umdefiniert werden.
//
// RED: Vor der Implementierung fehlen die Bridge-Tokens → die Bridge-Asserts
// schlagen fehl (Tokens nicht in app.css vorhanden). Nutzt nur Node-Bordmittel
// (kein node_modules noetig).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/tokens-bridge.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../app.css', import.meta.url), 'utf-8');

/** true, wenn `--name: value` (mit beliebigem Whitespace) in app.css vorkommt. */
function hasDecl(name: string, value: string): boolean {
	const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	return new RegExp(esc(name) + '\\s*:\\s*' + esc(value)).test(css);
}

test('Bridge: Surface-Tokens mit Sandbox-Werten (weisse Karte)', () => {
	assert.ok(hasDecl('--g-card', '#ffffff'), '--g-card: #ffffff fehlt');
	assert.ok(hasDecl('--g-card-alt', '#faf8f1'), '--g-card-alt fehlt');
	assert.ok(hasDecl('--g-rule', '#d8d3c2'), '--g-rule fehlt');
});

test('Bridge: Ink-Abstufungen', () => {
	assert.ok(hasDecl('--g-ink-2', '#45433d'), '--g-ink-2 fehlt');
	assert.ok(hasDecl('--g-ink-3', '#6b675c'), '--g-ink-3 fehlt');
	assert.ok(hasDecl('--g-ink-4', '#9a958a'), '--g-ink-4 fehlt');
});

test('Bridge: Accent-Abstufungen', () => {
	assert.ok(hasDecl('--g-accent-deep', '#8c3e1a'), '--g-accent-deep fehlt');
	assert.ok(hasDecl('--g-accent-soft', '#f3d9c8'), '--g-accent-soft fehlt');
	assert.ok(hasDecl('--g-accent-tint', 'rgba(196, 90, 42, 0.08)'), '--g-accent-tint fehlt');
});

test('Bridge: Semantik', () => {
	assert.ok(hasDecl('--g-good', '#3d6b3a'), '--g-good fehlt');
	assert.ok(hasDecl('--g-warn', '#c08a1a'), '--g-warn fehlt');
	assert.ok(hasDecl('--g-bad', '#a83232'), '--g-bad fehlt');
});

test('Bridge: Wetterfarben inkl. cloud + thunder-Alias', () => {
	assert.ok(hasDecl('--g-weather-rain', '#4a7ab8'), '--g-weather-rain fehlt');
	assert.ok(hasDecl('--g-weather-snow', '#8aa4c0'), '--g-weather-snow fehlt');
	assert.ok(hasDecl('--g-weather-sun', '#d99a2a'), '--g-weather-sun fehlt');
	assert.ok(hasDecl('--g-weather-cloud', '#9a958a'), '--g-weather-cloud fehlt');
	assert.ok(hasDecl('--g-weather-thunder', 'var(--g-wx-thunder)'), '--g-weather-thunder Alias fehlt');
});

test('Bridge: Schrift-Aliase (Wert identisch)', () => {
	assert.ok(hasDecl('--g-font-sans', 'var(--g-font-ui)'), '--g-font-sans Alias fehlt');
	assert.ok(hasDecl('--g-font-mono', 'var(--g-font-data)'), '--g-font-mono Alias fehlt');
});

test('Bridge: Radien', () => {
	assert.ok(hasDecl('--g-r-1', 'var(--g-radius-xs)'), '--g-r-1 Alias fehlt');
	assert.ok(hasDecl('--g-r-2', 'var(--g-radius-sm)'), '--g-r-2 Alias fehlt');
	assert.ok(hasDecl('--g-r-3', '6px'), '--g-r-3 fehlt');
	assert.ok(hasDecl('--g-r-4', '10px'), '--g-r-4 fehlt');
	assert.ok(hasDecl('--g-r-pill', 'var(--g-radius-pill)'), '--g-r-pill Alias fehlt');
});

test('Bridge: Elevation-Shadows vorhanden', () => {
	assert.ok(/--g-shadow-1\s*:/.test(css), '--g-shadow-1 fehlt');
	assert.ok(/--g-shadow-2\s*:/.test(css), '--g-shadow-2 fehlt');
	assert.ok(/--g-shadow-3\s*:/.test(css), '--g-shadow-3 fehlt');
});

test('Regression: bestehende Tokens unveraendert vorhanden', () => {
	assert.ok(hasDecl('--g-surface-1', '#ffffff'), '--g-surface-1 ist nach #378 reinweiss (Surface-Stack-Migration)');
	assert.ok(hasDecl('--g-success', '#3a7d44'), '--g-success bleibt');
	assert.ok(hasDecl('--g-wx-thunder', '#c43a2a'), '--g-wx-thunder bleibt');
});

test('Kollisionen NICHT auf Sandbox-Werte umdefiniert', () => {
	assert.ok(!hasDecl('--g-info', '#2c5a8c'), '--g-info darf NICHT auf Sandbox-Wert umdefiniert werden');
	assert.ok(hasDecl('--g-info', '#2a6cb3'), '--g-info behaelt unseren Wert');
});

// --- Issue #378: Surface-Stack-Migration (weisse Karten auf warmer Off-White-Page) ---
// RED vor der app.css-Aenderung: surface-1/2/raised + rule-soft tragen noch die alten
// beigen Werte → diese Asserts schlagen fehl, bis der Werte-Tausch erfolgt ist.

test('#378 AC-1: --g-surface-1 ist reinweiss (#ffffff) — der Knackpunkt', () => {
	assert.ok(hasDecl('--g-surface-1', '#ffffff'), '--g-surface-1 muss #ffffff sein (Karten reinweiss)');
});

test('#378 AC-2: restliche Surface-/Rule-Werte auf Sandbox-Zielwerte getauscht', () => {
	assert.ok(hasDecl('--g-surface-2', '#ecead9'), '--g-surface-2 muss #ecead9 sein');
	assert.ok(hasDecl('--g-surface-raised', '#faf8f1'), '--g-surface-raised muss #faf8f1 sein (direkter Hex, kein var-Verweis)');
	assert.ok(hasDecl('--g-rule-soft', '#e7e2d3'), '--g-rule-soft muss #e7e2d3 sein (opak, ersetzt rgba)');
});

test('#378 AC-2b: --g-surface-raised verweist NICHT mehr auf var(--g-surface-1)', () => {
	assert.ok(!hasDecl('--g-surface-raised', 'var(--g-surface-1)'), '--g-surface-raised darf nicht mehr auf surface-1 verweisen');
});

test('#378 AC-4: nicht-migrierte Tokens bleiben unveraendert', () => {
	assert.ok(hasDecl('--g-surface-0', '#f6f4ee'), '--g-surface-0 bleibt #f6f4ee');
	assert.ok(hasDecl('--g-rule', '#d8d3c2'), '--g-rule bleibt #d8d3c2');
	assert.ok(hasDecl('--g-paper-deep', '#ede9df'), '--g-paper-deep bleibt #ede9df (nicht im #378-Scope, C1)');
});

test('#378 AC-7: keine alten beigen Surface-Fallbacks in @property (rgb-Form, F002)', () => {
	// Die @property-initial-values der Surface-Aliase (--color-card/-muted/-sidebar/-sidebar-accent)
	// trugen die alten beigen Werte in rgb()-Form als Fallback — die muessen mit-migriert sein.
	assert.ok(!/rgb\(237,\s*234,\s*225\)/.test(css), 'alter surface-1-Fallback rgb(237,234,225)=#edeae1 entfernt');
	assert.ok(!/rgb\(227,\s*223,\s*212\)/.test(css), 'alter surface-2-Fallback rgb(227,223,212)=#e3dfd4 entfernt');
	assert.ok(/initial-value:\s*rgb\(255,\s*255,\s*255\)/.test(css), 'weisser Surface-Fallback rgb(255,255,255) vorhanden');
	assert.ok(/initial-value:\s*rgb\(236,\s*234,\s*217\)/.test(css), 'neuer surface-2-Fallback rgb(236,234,217)=#ecead9 vorhanden');
});
