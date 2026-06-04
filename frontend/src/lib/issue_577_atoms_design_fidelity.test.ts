// TDD RED: Issue #577 — Atoms 1:1 nach atoms.jsx (Design-Fidelity Rework)
//
// Spec: docs/specs/modules/issue_577_atoms_design_fidelity.md
//
// Source-Inspection-Tests (statische Datei-Analyse, kein Render, keine Mocks):
//   AC-1:  WIcon — kein Lucide-Import, enthält custom SVG-Pfade (sun/headlamp/thunder/snow)
//   AC-2:  Pill tone "good" — semi-transparenter Hintergrund rgba(61,107,58,0.10)
//   AC-3:  Pill tone "warn" — rgba(192,138,26,0.12) + --g-warn-deep Token
//   AC-4:  Pill Basis-Typografie — font-mono, 11px, 0.04em tracking, uppercase
//   AC-5:  Eyebrow Typografie — 11px, font-weight 500, var(--g-track-caps)
//   AC-6:  Btn ghost — border-color var(--g-rule) statt transparent
//   AC-7:  Card (non-accent) — vollständiger 4-seitiger Border, kein overflow:hidden
//   AC-8:  Card (accent) — border-left 3px accent, Rest 1px rule
//   AC-9:  QuickAction "route" — SVG statt ASCII-String
//   AC-10: QuickAction clock/metrics/bell — unterschiedliche SVG-Pfade
//   AC-11: Build erfolgreich (via TypeScript-Import-Check)
//
// RED vor Implementierung: aktuelle IST-Implementierung weicht von SOLL ab.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_577_atoms_design_fidelity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

const WICON      = join(root, 'lib/components/ui/wicon/WIcon.svelte');
const APP_CSS    = join(root, 'app.css');
const CARD       = join(root, 'lib/components/atoms/Card.svelte');
const QA         = join(root, 'lib/components/molecules/QuickAction.svelte');

const read = (f: string) => readFileSync(f, 'utf-8');

// ─── AC-1: WIcon — kein Lucide, custom SVG ────────────────────────────────────

test('#577 AC-1 WIcon enthält keinen Lucide-Import', () => {
	const src = read(WICON);
	assert.ok(
		!/@lucide/.test(src),
		'WIcon.svelte importiert noch Lucide — muss durch custom Inline-SVG ersetzt werden'
	);
});

test('#577 AC-1 WIcon enthält custom SVG für kind="sun" (circle r=3.5)', () => {
	const src = read(WICON);
	assert.ok(
		/r="3\.5"/.test(src) || /r={[^}]*3\.5[^}]*}/.test(src),
		'WIcon sun-Pfad fehlt: erwartet <circle ... r="3.5"/> aus atoms.jsx'
	);
});

test('#577 AC-1 WIcon enthält custom SVG für kind="headlamp" (rect+path)', () => {
	const src = read(WICON);
	assert.ok(
		/rx="1\.5"/.test(src),
		'WIcon headlamp fehlt: erwartet <rect rx="1.5"/> aus atoms.jsx'
	);
});

test('#577 AC-1 WIcon enthält custom SVG für kind="thunder" (Blitz-Pfad)', () => {
	const src = read(WICON);
	assert.ok(
		/M12 14l-2 4h3l-2 4/.test(src),
		'WIcon thunder-Pfad fehlt: erwartet d="M12 14l-2 4h3l-2 4" aus atoms.jsx'
	);
});

test('#577 AC-1 WIcon enthält custom SVG für kind="snow" (Schneeflocke)', () => {
	const src = read(WICON);
	assert.ok(
		/M5 7l14 10/.test(src),
		'WIcon snow-Pfad fehlt: erwartet d="M5 7l14 10" aus atoms.jsx'
	);
});

// ─── AC-2: Pill tone "good" — semi-transparente Farbe ─────────────────────────

test('#577 AC-2 Pill[good] hat semi-transparenten Hintergrund rgba(61,107,58,0.10)', () => {
	const src = read(APP_CSS);
	assert.ok(
		/rgba\(61,\s*107,\s*58,\s*0\.10?\)/.test(src),
		'Pill[good] nutzt noch opakes var(--g-success) — SOLL: rgba(61,107,58,0.10)'
	);
});

test('#577 AC-2 Pill[good] fg-Farbe ist var(--g-good)', () => {
	const src = read(APP_CSS);
	// Suche nach dem Kontext: data-tone="good" oder neutral:
	const block = src.match(/data-tone="good"\].*?(?=\n\n|\[data-slot)/s)?.[0] ?? '';
	assert.ok(
		/var\(--g-good\)/.test(block) || /data-tone="good"\].*?var\(--g-good\)/s.test(src),
		'Pill[good] fg-Farbe nicht var(--g-good)'
	);
});

// ─── AC-3: Pill tone "warn" + --g-warn-deep Token ─────────────────────────────

test('#577 AC-3 Pill[warn] hat semi-transparenten Hintergrund rgba(192,138,26,0.12)', () => {
	const src = read(APP_CSS);
	assert.ok(
		/rgba\(192,\s*138,\s*26,\s*0\.12?\)/.test(src),
		'Pill[warn] nutzt noch opakes var(--g-warning) — SOLL: rgba(192,138,26,0.12)'
	);
});

test('#577 AC-3 app.css definiert --g-warn-deep Token', () => {
	const src = read(APP_CSS);
	assert.ok(
		/--g-warn-deep/.test(src),
		'Token --g-warn-deep fehlt in app.css'
	);
});

// ─── AC-4: Pill Basis-Typografie ──────────────────────────────────────────────

test('#577 AC-4 Pill nutzt var(--g-font-mono)', () => {
	const src = read(APP_CSS);
	// Im Pill-Block muss var(--g-font-mono) stehen (nicht var(--g-font-ui))
	const pillSection = src.match(/\[data-slot="pill"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/var\(--g-font-mono\)/.test(pillSection),
		'Pill-Basis nutzt noch var(--g-font-ui) statt var(--g-font-mono)'
	);
});

test('#577 AC-4 Pill hat font-size: 11px', () => {
	const src = read(APP_CSS);
	const pillSection = src.match(/\[data-slot="pill"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/font-size:\s*11px/.test(pillSection),
		'Pill-Basis font-size ist noch nicht 11px'
	);
});

test('#577 AC-4 Pill hat text-transform: uppercase', () => {
	const src = read(APP_CSS);
	const pillSection = src.match(/\[data-slot="pill"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/text-transform:\s*uppercase/.test(pillSection),
		'Pill hat kein text-transform: uppercase'
	);
});

test('#577 AC-4 Pill hat letter-spacing: 0.04em', () => {
	const src = read(APP_CSS);
	const pillSection = src.match(/\[data-slot="pill"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/letter-spacing:\s*0\.04em/.test(pillSection),
		'Pill hat kein letter-spacing: 0.04em'
	);
});

// ─── AC-5: Eyebrow Typografie ─────────────────────────────────────────────────

test('#577 AC-5 Eyebrow hat font-size: 11px (nicht 0.625rem)', () => {
	const src = read(APP_CSS);
	const eyebrowSection = src.match(/\[data-slot="eyebrow"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/font-size:\s*11px/.test(eyebrowSection),
		'Eyebrow font-size noch 0.625rem (10px) — SOLL: 11px'
	);
	assert.ok(
		!/0\.625rem/.test(eyebrowSection),
		'Eyebrow hat noch 0.625rem statt 11px'
	);
});

test('#577 AC-5 Eyebrow hat font-weight: 500', () => {
	const src = read(APP_CSS);
	const eyebrowSection = src.match(/\[data-slot="eyebrow"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/font-weight:\s*500/.test(eyebrowSection),
		'Eyebrow font-weight noch 400 — SOLL: 500'
	);
});

test('#577 AC-5 Eyebrow hat letter-spacing: var(--g-track-caps)', () => {
	const src = read(APP_CSS);
	const eyebrowSection = src.match(/\[data-slot="eyebrow"\]\s*\{[^}]+\}/)?.[0] ?? '';
	assert.ok(
		/letter-spacing:\s*var\(--g-track-caps\)/.test(eyebrowSection),
		'Eyebrow letter-spacing noch 0.1em — SOLL: var(--g-track-caps)'
	);
});

// ─── AC-6: Btn ghost border ────────────────────────────────────────────────────

test('#577 AC-6 Btn ghost hat border-color: var(--g-rule)', () => {
	const src = read(APP_CSS);
	// Suche den ghost-Variant-Block
	const ghostMatch = src.match(/data-variant="ghost"\][^}]+\}/)?.[0] ?? '';
	assert.ok(
		/border-color:\s*var\(--g-rule\)/.test(ghostMatch),
		'Btn[ghost] border-color noch transparent — SOLL: var(--g-rule)'
	);
});

// ─── AC-7: Card vollständiger Border + kein overflow:hidden ───────────────────

test('#577 AC-7 Card.svelte hat vollständigen 4-seitigen Border', () => {
	const src = read(CARD);
	// Prüft ob border (alle Seiten) gesetzt ist, nicht nur border-left
	assert.ok(
		/style:border=/.test(src) || /border="/.test(src),
		'Card.svelte hat keinen vollständigen 4-seitigen Border (nur border-left)'
	);
});

test('#577 AC-7 Card.svelte hat kein overflow:hidden', () => {
	const src = read(CARD);
	assert.ok(
		!/overflow.*hidden/.test(src),
		'Card.svelte hat noch overflow:hidden — laut atoms.jsx nicht vorgesehen'
	);
});

// ─── AC-8: Card accent — 3px Akzentstreifen links ─────────────────────────────

test('#577 AC-8 Card accent nutzt 3px accent-Border links', () => {
	const src = read(CARD);
	assert.ok(
		/3px solid var\(--g-accent\)/.test(src),
		'Card accent-Border fehlt: erwartet 3px solid var(--g-accent) für border-left'
	);
});

// ─── AC-9: QuickAction SVG statt ASCII ────────────────────────────────────────

test('#577 AC-9 QuickAction enthält kein ASCII-Glyph-Mapping (->)', () => {
	const src = read(QA);
	assert.ok(
		!/'->'\s*;/.test(src) && !/'->'\s*$/.test(src, ) && !/return '->'/m.test(src),
		'QuickAction gibt noch "->" als ASCII-String zurück'
	);
});

test('#577 AC-9 QuickAction enthält SVG für glyph="route"', () => {
	const src = read(QA);
	// Der route-SVG-Pfad aus molecules.jsx
	assert.ok(
		/cx="6"\s+cy="6"/.test(src) || /M6 8\.5v3/.test(src),
		'QuickAction route-SVG fehlt — erwartet: circle cx=6 cy=6 + M6 8.5v3'
	);
});

// ─── AC-10: QuickAction — unterschiedliche SVG pro Glyph ─────────────────────

test('#577 AC-10 QuickAction clock hat eigenen SVG (Kreis + Zeiger, kein >>)', () => {
	const src = read(QA);
	// clock: <circle cx="12" cy="12" r="8.5"/>
	assert.ok(
		/r="8\.5"/.test(src),
		'QuickAction clock-SVG fehlt: erwartet <circle r="8.5"/> (Ziffernblatt)'
	);
});

test('#577 AC-10 QuickAction metrics hat eigenen SVG (Schieberegler)', () => {
	const src = read(QA);
	// metrics: M4 8h10 ... circle cx="16" cy="8" r="2.2"
	assert.ok(
		/cx="16".*cy="8"/.test(src) || /M4 8h10/.test(src),
		'QuickAction metrics-SVG fehlt: erwartet M4 8h10 + Kreise cx=16/8'
	);
});

test('#577 AC-10 QuickAction bell hat eigenen SVG (Glocke)', () => {
	const src = read(QA);
	// bell: M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z
	assert.ok(
		/M6 9a6 6/.test(src),
		'QuickAction bell-SVG fehlt: erwartet M6 9a6 6 (Glocken-Pfad)'
	);
});
