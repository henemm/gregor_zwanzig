// TDD RED: Issue #390 — Compare-Screen auf Atomic-Bibliothek migrieren
//
// Spec:  docs/specs/modules/issue_390_compare_atomic_migration.md
//
// Source-Inspection-Tests (wie contrast-audit.test.ts): lesen echte .svelte-Dateien
// und pruefen, dass die Migration vollstaendig durchgefuehrt wurde.
//
// RED-Erwartung (vor Implementation):
//   - +page.svelte hat kein Pill-Import und noch alte rounded-full-Klassen → FAIL
//   - PresetHeader.svelte hat kein Field-Import und noch alte label-Markup → FAIL
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url)); // -> frontend/

const PAGE = join(ROOT, 'src/routes/compare/+page.svelte');

// ── AC-1 + AC-5: +page.svelte — ChipBtn → Pill ────────────────────────────
//
// Issue #439: routes/compare/+page.svelte ist nicht mehr der interaktive
// Vergleichsrechner, sondern eine Tabellen-Übersicht aller Orts-Vergleiche.
// Es gibt keine Mobile-Chip-Row mehr (compare-mobile-chip-row: 0 Treffer in
// frontend/src). Die drei AC-1-Tests (Pill-Import, <Pill> in der Chip-Row,
// aria-pressed der Chip-Buttons) waren seither test.skip und sind mit #3207
// entfernt (abgelöste Funktion ⇒ Tests mitentfernen). Es bleibt der
// Abwesenheits-Wächter AC-5.

test('AC-5: Alte inline-Button-Klassen aus Mobile Chip-Row entfernt', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// "rounded-full border border-border bg-muted" darf in der Chip-Row nicht mehr vorkommen
	// Wir pruefen im gesamten File, da diese Kombination nur in der Chip-Row vorkam
	assert.doesNotMatch(
		src,
		/rounded-full border border-border bg-muted/,
		'Alte inline Chip-Button-Klassen (rounded-full border border-border bg-muted) muessen entfernt sein'
	);
});

// ── AC-2 + AC-5: PresetHeader.svelte-Tests entfernt ───────────────────────
// PresetHeader.svelte wurde mit Issue #1215 (Dead-Code Scheibe 3) gelöscht —
// die zugehörigen Migrations-Tests (Field-Import, <Field>-Wrapper, Label-
// Klasse, beide data-testids) entfallen mit der Komponente.

// ── AC-6: Page-lokale Komposita unveraendert ───────────────────────────────
// Issue #1256 Scheibe 1 (2026-07-13): AutoReportsOverview.svelte wurde als
// verifizierter Totcode gelöscht (kein produktiver Import, Spec Zeilen 303-305)
// — Eintrag entfernt.
// Issue #1350 Teil 3 (2026-07-24): CompareMatrix.svelte + HourlyMatrix.svelte
// wurden als bestaetigter Totcode geloescht (AC-20,
// compare_matrix_dead_code.test.ts, jetzt ebenfalls entfernt) — die
// Existenz-Pruefung unten entfaellt ersatzlos.
