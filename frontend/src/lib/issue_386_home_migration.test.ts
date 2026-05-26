// TDD RED: Issue #386 — Startseite auf Atomic-Bibliothek migrieren (Epic #368 Phase 2)
//
// Spec:  docs/specs/modules/issue_386_home_atomic_migration.md
//
// Source-Inspection-Tests: liest echte .svelte-Quelldateien und prüft, dass die
// Migration durchgeführt wurde. Kein Browser, keine Mocks, keine node_modules.
//
// RED-Erwartungen (vor der Implementierung):
//   AC-1: H1 lautet noch "Startseite" → FAIL
//   AC-2: TripKachel hat kein "Reports ✓" → FAIL
//   AC-3: Kacheln haben kein data-slot="g-card" → FAIL
//   AC-6: +page.svelte hat noch <h2>-Sektions-Header → FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_386_home_migration.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

// ---------------------------------------------------------------------------
// AC-1: H1-Text + Subtext auf Startseite
// ---------------------------------------------------------------------------

test('AC-1a: +page.svelte H1 lautet "Deine Touren & Vergleiche"', () => {
	const src = read('routes/+page.svelte');
	assert.ok(
		src.includes('Deine Touren & Vergleiche'),
		'H1-Text "Deine Touren & Vergleiche" fehlt in routes/+page.svelte'
	);
});

test('AC-1b: +page.svelte enthält Subtext über autarke Briefings', () => {
	const src = read('routes/+page.svelte');
	assert.ok(
		src.includes('autark') || src.includes('Briefings'),
		'Subtext über autarke Briefings fehlt in routes/+page.svelte'
	);
});

// ---------------------------------------------------------------------------
// AC-2: Trip-Kachel zeigt "Reports ✓"
// ---------------------------------------------------------------------------

test('AC-2: TripKachel.svelte enthält "Reports ✓"-Anzeigelogik', () => {
	const src = read('routes/_home/TripKachel.svelte');
	assert.ok(
		src.includes('Reports') && src.includes('report_config'),
		'"Reports ✓"-Logik basierend auf report_config fehlt in TripKachel.svelte'
	);
});

// ---------------------------------------------------------------------------
// AC-3: data-slot="g-card" auf Kachel-<a>-Elementen
// ---------------------------------------------------------------------------

test('AC-3a: TripKachel.svelte <a>-Element hat data-slot="g-card"', () => {
	const src = read('routes/_home/TripKachel.svelte');
	assert.ok(
		src.includes('data-slot="g-card"'),
		'data-slot="g-card" fehlt auf dem <a>-Element in TripKachel.svelte'
	);
});

test('AC-3b: CompareKachel.svelte <a>-Element hat data-slot="g-card"', () => {
	const src = read('routes/_home/CompareKachel.svelte');
	assert.ok(
		src.includes('data-slot="g-card"'),
		'data-slot="g-card" fehlt auf dem <a>-Element in CompareKachel.svelte'
	);
});

test('AC-3c: TripKachel.svelte enthält keine Hex-Farbliterale in Inline-Styles', () => {
	const src = read('routes/_home/TripKachel.svelte');
	// style= mit Hex-Farbwerten (#rrggbb oder #rgb) sind verboten
	const hexInStyle = /#[0-9a-fA-F]{3,6}(?=[^0-9a-fA-F"'])/g;
	const matches = [...src.matchAll(/style[^>]*#[0-9a-fA-F]{3,6}/g)];
	assert.equal(
		matches.length,
		0,
		`Hex-Farbliterale in Inline-Styles gefunden in TripKachel.svelte: ${matches.map((m) => m[0]).join(', ')}`
	);
});

// ---------------------------------------------------------------------------
// AC-6: Keine <h2>-Sektions-Header für "Meine Touren" / "Orts-Vergleiche"
// ---------------------------------------------------------------------------

test('AC-6: +page.svelte hat keinen <h2>-Sektions-Header "Meine Touren"', () => {
	const src = read('routes/+page.svelte');
	assert.ok(
		!src.includes('Meine Touren'),
		'<h2>-Header "Meine Touren" noch vorhanden in +page.svelte — bitte entfernen'
	);
});

test('AC-6: +page.svelte hat keinen <h2>-Sektions-Header "Orts-Vergleiche"', () => {
	const src = read('routes/+page.svelte');
	assert.ok(
		!src.includes('Orts-Vergleiche'),
		'<h2>-Header "Orts-Vergleiche" noch vorhanden in +page.svelte — bitte entfernen'
	);
});

// ---------------------------------------------------------------------------
// AC-3d: TripKachel verwendet data-slot="g-card" STATT eigenem background-CSS
// ---------------------------------------------------------------------------

test('AC-3d: TripKachel.svelte definiert kein eigenes background: var(--g-surface-1) mehr', () => {
	const src = read('routes/_home/TripKachel.svelte');
	// Nach der Migration übernimmt data-slot="g-card" die background-Definition.
	// Das scoped CSS der Kachel darf kein background mehr definieren (würde duplizieren).
	const bgPattern = /background:\s*var\(--g-surface-1\)/;
	assert.ok(
		!bgPattern.test(src),
		'background: var(--g-surface-1) noch im scoped CSS von TripKachel.svelte — nach Migration übernimmt g-card das'
	);
});
