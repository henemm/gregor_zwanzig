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
	assert.ok(hasDecl('--g-surface-1', '#edeae1'), '--g-surface-1 darf nicht veraendert sein');
	assert.ok(hasDecl('--g-success', '#3a7d44'), '--g-success bleibt');
	assert.ok(hasDecl('--g-wx-thunder', '#c43a2a'), '--g-wx-thunder bleibt');
});

test('Kollisionen NICHT auf Sandbox-Werte umdefiniert', () => {
	assert.ok(!hasDecl('--g-info', '#2c5a8c'), '--g-info darf NICHT auf Sandbox-Wert umdefiniert werden');
	assert.ok(hasDecl('--g-info', '#2a6cb3'), '--g-info behaelt unseren Wert');
});
