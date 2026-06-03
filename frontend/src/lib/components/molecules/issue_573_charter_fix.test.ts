// TDD RED: Issue #573 — Charter-Compliance-Fix Startseite-Cockpit
//
// Spec: docs/specs/modules/issue_573_charter_fix_cockpit.md
//
// Source-Inspection-Tests (kein Render, keine Mocks): prüfen ob
// Charter-Verstöße in SetupResumeCard.svelte, QuickAction.svelte
// und +page.svelte behoben sind.
//
// RED vor Fix: Bestehende Dateien enthalten Verstöße → Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/molecules/issue_573_charter_fix.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// root = frontend/ (4 Ebenen über molecules/)
const frontendRoot = resolve(here, '../../../../');
const readMol = (f: string) => readFileSync(join(here, f), 'utf-8');
const readRoot = (f: string) => readFileSync(join(frontendRoot, f), 'utf-8');
const hasMol = (f: string) => existsSync(join(here, f));

// ── AC-1: SetupResumeCard — kein ✓/○, stattdessen <Dot> ─────────────────────

test('#573 AC-1: SetupResumeCard nutzt <Dot> statt ✓/○-Symbolen', () => {
	const src = readMol('SetupResumeCard.svelte');
	assert.ok(!src.includes("'✓'") && !src.includes('"✓"'), 'SetupResumeCard enthält noch ✓-Symbol');
	assert.ok(!src.includes("'○'") && !src.includes('"○"'), 'SetupResumeCard enthält noch ○-Symbol');
	assert.ok(/\bDot\b/.test(src), 'SetupResumeCard importiert/nutzt kein <Dot>');
});

// ── AC-2: SetupResumeCard — CTA ist <Btn>, kein hand-styled <a> ─────────────

test('#573 AC-2: SetupResumeCard CTA nutzt <Btn>-Atom, kein ad-hoc-<a>', () => {
	const src = readMol('SetupResumeCard.svelte');
	assert.ok(/\bBtn\b/.test(src), 'SetupResumeCard importiert/nutzt kein <Btn>');
	// Darf keine rohe <a>-CTA mit inline background-style mehr enthalten
	assert.ok(
		!src.includes("style:background={ctaBg}"),
		'SetupResumeCard enthält noch hand-styled CTA (style:background={ctaBg})'
	);
});

// ── AC-3: +page.svelte — PageHeader-Atom vorhanden und genutzt ──────────────

test('#573 AC-3: atoms/index.ts exportiert PageHeader', () => {
	const atomsIdx = readRoot('src/lib/components/atoms/index.ts');
	assert.ok(/PageHeader/.test(atomsIdx), 'atoms/index.ts exportiert PageHeader nicht');
});

test('#573 AC-3b: +page.svelte nutzt PageHeader statt custom <header>', () => {
	const src = readRoot('src/routes/+page.svelte');
	assert.ok(/PageHeader/.test(src), '+page.svelte importiert/nutzt kein PageHeader');
	// Darf kein inline-styled custom-<header> mehr haben
	assert.ok(
		!src.includes('<header\n') && !src.includes('<header '),
		'+page.svelte enthält noch custom <header>-Element'
	);
});

// ── AC-4: Keine Nicht-Token-Schriftgrößen ────────────────────────────────────

test('#573 AC-4: SetupResumeCard — keine Nicht-Token-Schriftgrößen (12px/14px/22px/28px)', () => {
	const src = readMol('SetupResumeCard.svelte');
	// font-size als inline style mit Nicht-Token-Wert
	assert.ok(!/font-size.*["']12px["']/.test(src), 'SetupResumeCard enthält font-size: 12px (kein Token)');
	assert.ok(!/font-size.*["']14px["']/.test(src), 'SetupResumeCard enthält font-size: 14px (kein Token)');
});

test('#573 AC-4b: QuickAction — keine Nicht-Token-Schriftgrößen', () => {
	const src = readMol('QuickAction.svelte');
	assert.ok(!/font-size.*["']12px["']/.test(src), 'QuickAction enthält font-size: 12px (kein Token)');
	assert.ok(!/font-size.*["']14px["']/.test(src), 'QuickAction enthält font-size: 14px (kein Token)');
});

test('#573 AC-4c: +page.svelte — keine Nicht-Token-Schriftgrößen (22px/28px)', () => {
	const src = readRoot('src/routes/+page.svelte');
	assert.ok(!/font-size.*["']22px["']/.test(src), '+page.svelte enthält font-size: 22px (kein Token)');
	assert.ok(!/font-size.*["']28px["']/.test(src), '+page.svelte enthält font-size: 28px (kein Token)');
});

// ── AC-5: Keine falschen/fehlenden Tokens ────────────────────────────────────

test('#573 AC-5: SetupResumeCard — kein --g-success (heißt --g-good)', () => {
	const src = readMol('SetupResumeCard.svelte');
	assert.ok(!src.includes('--g-success'), 'SetupResumeCard enthält noch --g-success (Token heißt --g-good)');
});

test('#573 AC-5b: SetupResumeCard — kein --g-ink-on-accent (Token existiert nicht)', () => {
	const src = readMol('SetupResumeCard.svelte');
	assert.ok(!src.includes('--g-ink-on-accent'), 'SetupResumeCard enthält noch --g-ink-on-accent');
});

test('#573 AC-5c: betroffene Dateien — kein Literal-Hex #ffffff', () => {
	const files = [
		readMol('SetupResumeCard.svelte'),
		readMol('QuickAction.svelte'),
	];
	for (const src of files) {
		assert.ok(!src.includes('#ffffff'), 'Datei enthält noch Literal-Farbe #ffffff');
	}
});

// ── AC-6: Live-Pill — Dot tone="good" (nicht "bad") ─────────────────────────

test('#573 AC-6: +page.svelte Live-Pill nutzt <Dot tone="good">, nicht tone="bad"', () => {
	const src = readRoot('src/routes/+page.svelte');
	// In der Live-Pill darf kein <Dot tone="bad"> sein
	// Kontext: die Pill heißt "Live · Tag X von Y"
	const livePillSection = src.slice(
		Math.max(0, src.indexOf('Live ·') - 200),
		src.indexOf('Live ·') + 500
	);
	assert.ok(
		!livePillSection.includes('tone="bad"'),
		'Live-Pill enthält noch <Dot tone="bad"> (sollte tone="good" sein)'
	);
});

// ── AC-7: QuickAction — keine Unicode-Sonderzeichen als Glyphen ─────────────

test('#573 AC-7: QuickAction — keine problematischen Unicode-Sonderzeichen (◆◷◉◐▸‖)', () => {
	const src = readMol('QuickAction.svelte');
	const forbidden = ['◆', '◷', '◉', '◐', '▸', '‖'];
	for (const char of forbidden) {
		assert.ok(!src.includes(char), `QuickAction enthält noch Unicode-Sonderzeichen: ${char}`);
	}
});

// ── AC-8: Keine freien Letter-Spacing em-Werte ───────────────────────────────

test('#573 AC-8: SetupResumeCard — kein freies letter-spacing 0.08em', () => {
	const src = readMol('SetupResumeCard.svelte');
	assert.ok(!src.includes('0.08em'), 'SetupResumeCard enthält noch letter-spacing: 0.08em (kein Token)');
});

test('#573 AC-8b: +page.svelte — kein freies letter-spacing -0.005em', () => {
	const src = readRoot('src/routes/+page.svelte');
	assert.ok(!src.includes('-0.005em'), '+page.svelte enthält noch letter-spacing: -0.005em (kein Token)');
});
