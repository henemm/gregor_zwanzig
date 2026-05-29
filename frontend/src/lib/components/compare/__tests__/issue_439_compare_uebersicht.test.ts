// TDD RED: Issue #439 — Orts-Vergleich Übersichtsseite /compare
//
// Spec: docs/specs/modules/issue_439_compare_uebersicht.md
//
// Source-Inspection-Tests (wie contrast-audit.test.ts): lesen echte .svelte/.ts-Dateien
// und prüfen, dass die neue Übersichtsseite vollständig implementiert ist.
//
// RED-Erwartung (vor Implementation):
//   - CompareList.svelte existiert nicht → FAIL (ENOENT)
//   - CompareRow.svelte existiert nicht → FAIL (ENOENT)
//   - +page.svelte hat noch alten Inhalt (kein Eyebrow WORKSPACE · ORTS-VERGLEICHE) → FAIL
//   - deriveStatus() nicht in subscriptionHelpers.ts exportiert → FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_439_compare_uebersicht.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url)); // -> frontend/

const PAGE = join(ROOT, 'src/routes/compare/+page.svelte');
const COMPARE_LIST = join(ROOT, 'src/lib/components/compare/CompareList.svelte');
const COMPARE_ROW = join(ROOT, 'src/lib/components/compare/CompareRow.svelte');
const HELPERS = join(ROOT, 'src/lib/components/compare/subscriptionHelpers.ts');

// ── AC-2: Neue Dateien müssen existieren ─────────────────────────────────────

test('AC-2: CompareList.svelte existiert', () => {
	assert.ok(
		existsSync(COMPARE_LIST),
		'CompareList.svelte muss unter frontend/src/lib/components/compare/ existieren'
	);
});

test('AC-2: CompareRow.svelte existiert', () => {
	assert.ok(
		existsSync(COMPARE_ROW),
		'CompareRow.svelte muss unter frontend/src/lib/components/compare/ existieren'
	);
});

// ── AC-2: +page.svelte — neuer Header ────────────────────────────────────────
//
// HINWEIS (Issue #455): Vier Assertions aus dem ursprünglichen #439-Test wurden
// hier entfernt, weil sie durch die neue Compare-Hauptbühne überholt sind:
//   - Eyebrow „WORKSPACE · ORTS-VERGLEICHE" (jetzt nicht mehr in +page.svelte)
//   - H1 „Orts-Vergleiche" (jetzt nicht mehr in +page.svelte)
//   - assert.doesNotMatch LocationsRail-Import (jetzt wieder eingebunden)
//   - assert.doesNotMatch PresetHeader-Import (jetzt wieder eingebunden)
// Die neuen Layout-Assertions kommen in issue_455_compare_main_stage.test.ts.

test('AC-2: +page.svelte hat Button + Neuer Vergleich → /compare/new', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/\/compare\/new/,
		'+page.svelte muss einen Link/CTA zu /compare/new haben'
	);
});

// ── AC-4: Stats-Row ───────────────────────────────────────────────────────────
//
// HINWEIS (Issue #455): Die beiden Stats-Row-Assertions ("Aktiv/Pausiert/Drafts"
// in +page.svelte und --g-accent für Aktiv-Zähler) sind durch die neue
// Compare-Hauptbühne überholt. Die Subscription-Übersicht ist jetzt im rechten
// Sidepanel (AutoReportsOverview), nicht mehr im Haupt-Header. Status-Zähler
// existieren in dieser Form nicht mehr.

// ── AC-3: Suche ───────────────────────────────────────────────────────────────

test('AC-3: CompareList.svelte enthält Search-Input', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/search|suche/i,
		'CompareList.svelte muss einen Search-State oder Search-Input enthalten'
	);
});

test('AC-3: CompareList.svelte filtert case-insensitiv nach name', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/toLowerCase\(\)/,
		'CompareList.svelte muss toLowerCase() für Case-insensitive Suche nutzen'
	);
});

// ── AC-1: Tabellen-Spalten in CompareList ────────────────────────────────────

test('AC-1: CompareList.svelte importiert Table-Primitives', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/from\s+['"]\$lib\/components\/ui\/table/,
		'CompareList.svelte muss Table-Primitives aus $lib/components/ui/table importieren'
	);
});

test('AC-1: CompareList.svelte enthält Tabellenspalten-Header', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(src, /Orte/, 'CompareList muss Spaltenüberschrift "Orte" haben');
	assert.match(src, /Profil/, 'CompareList muss Spaltenüberschrift "Profil" haben');
	assert.match(src, /Kanäle|Kanaele/, 'CompareList muss Spaltenüberschrift "Kanäle" haben');
	assert.match(src, /Versand/, 'CompareList muss Spaltenüberschrift "Versand" haben');
	assert.match(src, /Aktionen/, 'CompareList muss Spaltenüberschrift "Aktionen" haben');
});

// ── AC-9 + AC-10: Empty States ────────────────────────────────────────────────

test('AC-9: CompareList.svelte zeigt EmptyState wenn keine Subscriptions', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/EmptyState/,
		'CompareList.svelte muss EmptyState-Komponente für 0 Subscriptions importieren/nutzen'
	);
});

test('AC-10: CompareList.svelte zeigt „Keine Vergleiche" bei Suche ohne Treffer', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/Keine Vergleiche/,
		'CompareList.svelte muss Text „Keine Vergleiche …" für Suche-Leer-Zustand enthalten'
	);
});

// ── AC-5: Status-Dot mit Inline-Style ────────────────────────────────────────

test('AC-5: CompareRow.svelte verwendet --g-accent für aktiven Status-Dot', () => {
	const src = readFileSync(COMPARE_ROW, 'utf-8');
	assert.match(
		src,
		/--g-accent/,
		'CompareRow.svelte muss --g-accent als Status-Dot-Farbe für aktive Subscriptions verwenden'
	);
});

test('AC-5: CompareRow.svelte verwendet --g-ink-3 für pausierten Status-Dot', () => {
	const src = readFileSync(COMPARE_ROW, 'utf-8');
	assert.match(
		src,
		/--g-ink-3/,
		'CompareRow.svelte muss --g-ink-3 als Status-Dot-Farbe für pausierte Subscriptions verwenden'
	);
});

test('AC-5: CompareRow.svelte verwendet --g-ink-4 für Draft-Status-Dot', () => {
	const src = readFileSync(COMPARE_ROW, 'utf-8');
	assert.match(
		src,
		/--g-ink-4/,
		'CompareRow.svelte muss --g-ink-4 als Status-Dot-Farbe für Draft-Subscriptions verwenden'
	);
});

// ── AC-5: deriveStatus in subscriptionHelpers ─────────────────────────────────

test('AC-5: subscriptionHelpers.ts exportiert deriveStatus-Funktion', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export function deriveStatus/,
		'subscriptionHelpers.ts muss deriveStatus() exportieren'
	);
});

test('AC-5: deriveStatus gibt "draft" zurück wenn name fehlt oder locations leer', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/draft/,
		'subscriptionHelpers.ts deriveStatus muss "draft" als Rückgabewert kennen'
	);
});

// ── AC-6: Pause/Play-Toggle ───────────────────────────────────────────────────

test('AC-6: CompareRow.svelte enthält Pause/Play-Icon-Import', () => {
	const src = readFileSync(COMPARE_ROW, 'utf-8');
	assert.match(
		src,
		/pause|play/i,
		'CompareRow.svelte muss Pause/Play-Icons für den Toggle-Button enthalten'
	);
});

test('AC-6: CompareList.svelte enthält toggleEnabled-Logik mit PUT', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/PUT|put|enabled/,
		'CompareList.svelte muss Toggle-Logik mit PUT /api/subscriptions/{id} enthalten'
	);
});

// ── AC-7: Edit-Aktion ─────────────────────────────────────────────────────────

test('AC-7: CompareRow.svelte verlinkt auf /compare/{id}/edit', () => {
	const src = readFileSync(COMPARE_ROW, 'utf-8');
	assert.match(
		src,
		/\/compare\/.*\/edit|compare.*edit/,
		'CompareRow.svelte muss Edit-Aktion zu /compare/{id}/edit verlinken'
	);
});

// ── AC-8: Delete-Confirm-Dialog ───────────────────────────────────────────────

test('AC-8: CompareList.svelte importiert Dialog für Delete-Confirm', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/Dialog/,
		'CompareList.svelte muss Dialog-Komponente für den Delete-Confirm importieren'
	);
});

test('AC-8: CompareList.svelte hat deleteTarget-State', () => {
	const src = readFileSync(COMPARE_LIST, 'utf-8');
	assert.match(
		src,
		/deleteTarget/,
		'CompareList.svelte muss deleteTarget-State für den Confirm-Dialog haben'
	);
});
