// TDD — Issue #1231, Slice 5: CorridorEditorMobile — Struktur-Nachweise.
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks, kein Playwright —
// Praezedenz: lib/components/edit/issue_542_mobile_editor.test.ts). Reine
// Svelte-Komponenten-Struktur ist ohne Rendering-Harness (kein
// @testing-library/svelte im Projekt) nur so pruefbar; AC-14 (Touch-Target-
// Masse per getBoundingClientRect) bleibt laut Spec Live-E2E-Schicht
// (Playwright gegen Staging).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { openBoundValue } from './corridorEditorState.ts';

const here = dirname(fileURLToPath(import.meta.url));
const MOBILE = join(here, 'CorridorEditorMobile.svelte');
const TRIP_TABS = join(here, '..', '..', 'trip-detail', 'TripTabs.svelte');
const COMPARE_EDITOR = join(here, '..', '..', 'compare', 'CompareEditor.svelte');

// ────────────────────────────────────────────────────────────────────────────
// F001-Fix (Adversary HIGH): openBound() muss den 25%/75%-Fallback gegen die
// Gegenseite clampen (kein Crossing) — analog dem Stepper-/Manuell-Eingabepfad.
// ────────────────────────────────────────────────────────────────────────────

describe('F001-Fix: openBoundValue() clampt gegen die Gegenseite (kein Crossing)', () => {
	test('Repro: min öffnen bei restriktivem max liefert einen Wert <= max, nicht den ungebremsten 25%-Fallback', () => {
		const row = { scale: [0, 20] as [number, number], step: 1, min: null, max: 1 };
		const result = openBoundValue(row, 'min');
		assert.equal(result, 1, `min-Fallback muss gegen max=1 geclampt werden, war aber ${result}`);
	});

	test('analog: max öffnen bei restriktivem min liefert einen Wert >= min', () => {
		const row = { scale: [0, 20] as [number, number], step: 1, min: 18, max: null };
		const result = openBoundValue(row, 'max');
		assert.equal(result, 18, `max-Fallback muss gegen min=18 geclampt werden, war aber ${result}`);
	});

	test('ohne Gegenseite bleibt der unclampte 25%/75%-Fallback erhalten', () => {
		const row = { scale: [0, 20] as [number, number], step: 1, min: null, max: null };
		assert.equal(openBoundValue(row, 'min'), 5);
		assert.equal(openBoundValue(row, 'max'), 15);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-15: CorridorEditorMobile importiert Daten/Logik aus dem Desktop-Modul —
// kein zweites Datenmodell, keine eigene corridorInside-Implementierung.
// ────────────────────────────────────────────────────────────────────────────

describe('AC-15: CorridorEditorMobile importiert aus corridorEditorState.ts/corridorMatch.ts', () => {
	test('CorridorEditorMobile.svelte existiert', () => {
		assert.ok(existsSync(MOBILE), 'CorridorEditorMobile.svelte fehlt');
	});

	test('importiert Row-/Pool-Builder aus corridorEditorState.ts (Single-Source)', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /from '\.\/corridorEditorState\.ts'/, 'muss aus corridorEditorState.ts importieren');
		for (const fn of ['buildRoutePool', 'buildComparePool', 'patchRow', 'validateCorridorRows', 'buildCorridorSavePayload', 'buildCompareCorridorSavePayload']) {
			assert.ok(src.includes(fn), `muss ${fn} aus dem Desktop-Modul importieren`);
		}
	});

	test('importiert corridorFmt aus corridorMatch.ts', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /from '\.\/corridorMatch\.ts'/, 'muss aus corridorMatch.ts importieren');
	});

	test('enthaelt KEINE eigene corridorInside-Funktionsdefinition', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.ok(
			!/function\s+corridorInside\s*\(/.test(src) && !/const\s+corridorInside\s*=/.test(src),
			'CorridorEditorMobile.svelte darf corridorInside nicht selbst definieren'
		);
	});

	test('confidence_pct taucht nirgends auf (ADR-0005, #710)', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.ok(!src.includes('confidence_pct'), 'confidence_pct darf im Mobile-Organism nicht vorkommen');
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-14 (Struktur-Teil): beide notify/mark-Effekt-Buttons min-height 44px,
// alarmCapable===false sperrt "Warnen" (Team-Lead-Vorgabe, Desktop-Praezedenz).
// ────────────────────────────────────────────────────────────────────────────

describe('AC-14: Effekt-Buttons erfuellen 44px-Touch-Mindestmass (Struktur)', () => {
	test('.cem-effect hat min-height: 44px im Style-Block', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /\.cem-effect\s*\{[^}]*min-height:\s*44px/, '.cem-effect muss min-height 44px setzen');
	});

	// Tech-Lead-Entscheidung (AC-14 gewinnt ueber JSX-Pixelwerte 40/24px):
	// Hit-Area-Technik — die interaktive Trefffläche wird 44x44, die JSX-Optik
	// (Glyph 40px, Handle-Kreis 24px) bleibt unveraendert innen/als Punkt erhalten.
	test('.cem-step-btn (Stepper-Trefffläche) ist 44x44, Glyph-Optik bleibt 40px', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /\.cem-step-btn\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/, '.cem-step-btn muss 44x44 Trefffläche haben');
		assert.match(src, /\.cem-step-btn-glyph\s*\{[^}]*width:\s*40px[^}]*height:\s*40px/, '.cem-step-btn-glyph muss die JSX-Optik (40px) behalten');
	});

	test('.cem-ordinal-btn und .cem-open-btn erfuellen min-height 44px', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /\.cem-ordinal-btn\s*\{[^}]*min-height:\s*44px/, '.cem-ordinal-btn muss min-height 44px setzen');
		assert.match(src, /\.cem-open-btn\s*\{[^}]*min-height:\s*44px/, '.cem-open-btn muss min-height 44px setzen');
	});

	// Staging-Fund F001 (Adversary BROKEN): .cem-ordinal-btn hatte min-height
	// aber kein min-width — 3 Ordinal-Buttons + Clear-Button teilten sich eine
	// ~175px-Spalte (Von/Bis nebeneinander), real gemessen 34-41px Breite.
	// Fix: Ordinal-Gruppe bekommt eine eigene volle Zeile (cem-bound-full),
	// dort erfuellt min-width:44px die 44x44-Flaeche real.
	test('.cem-ordinal-btn hat min-width: 44px (Staging-Fund F001)', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /\.cem-ordinal-btn\s*\{[^}]*min-width:\s*44px/, '.cem-ordinal-btn muss min-width 44px setzen');
	});

	test('Ordinal-Zeile bekommt eine eigene volle Breite statt der Von/Bis-Spaltenteilung', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.ok(src.includes('cem-bound-full'), 'Ordinal-Bound braucht eine Vollbreiten-Modifier-Klasse');
		assert.match(src, /\.cem-bound-full\s*\{[^}]*flex:\s*1\s+1\s+100%/, '.cem-bound-full muss flex-basis 100% setzen (eigene Zeile)');
		assert.match(src, /\.cem-bounds\s*\{[^}]*flex-wrap:\s*wrap/, '.cem-bounds muss flex-wrap:wrap erlauben, damit Vollbreiten-Zeilen umbrechen');
	});

	test('.cem-handle hat eine 44x44 ::before-Trefffläche (Touch-Zone um den 24px-Punkt)', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.match(src, /\.cem-handle::before\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/, '.cem-handle::before muss 44x44 Trefffläche haben');
	});

	test('alarmCapable===false sperrt den Warnen-Button (disabled + Hinweistext)', () => {
		const src = readFileSync(MOBILE, 'utf-8');
		assert.ok(src.includes("row.alarmCapable === false"), 'muss alarmCapable===false pruefen');
		assert.ok(src.includes('nur Markieren'), 'muss den Sperr-Hinweistext zeigen');
	});
});

// ────────────────────────────────────────────────────────────────────────────
// Einbau-Stellen: TripTabs.svelte (route) und CompareEditor.svelte (vergleich)
// mounten CorridorEditorMobile statt AlertsTab/Step3Idealwerte im Mobile-Zweig.
// ────────────────────────────────────────────────────────────────────────────

describe('Einbau TripTabs.svelte — Mobile-Zweig context="route"', () => {
	test('mountet CorridorEditorMobile context="route" statt AlertsTab', () => {
		const src = readFileSync(TRIP_TABS, 'utf-8');
		assert.match(src, /<CorridorEditorMobile\s+context="route"/, 'CorridorEditorMobile context="route" fehlt im Mobile-Zweig');
		assert.ok(!/<AlertsTab\b/.test(src), 'AlertsTab darf nicht mehr instanziiert werden');
	});
});

describe('Einbau CompareEditor.svelte — Mobile-Zweig context="vergleich"', () => {
	test('mountet CorridorEditorMobile context="vergleich" statt Step3Idealwerte', () => {
		const src = readFileSync(COMPARE_EDITOR, 'utf-8');
		assert.match(src, /<CorridorEditorMobile\s+context="vergleich"/, 'CorridorEditorMobile context="vergleich" fehlt im Mobile-Zweig');
		assert.ok(!/<Step3Idealwerte\b/.test(src), 'Step3Idealwerte darf nicht mehr instanziiert werden');
	});
});
