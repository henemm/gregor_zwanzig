// TDD RED: Issue #594 + #598 — Feedback & Bestätigungs-Dialoge
//
// Spec: docs/specs/modules/bug_594_598_feedback_dialoge.md
//
// Source-Inspection-Tests (kein Render, keine Mocks):
//   AC-1/AC-2: TripHeader.svelte — testBriefingKind State + --g-success/--g-danger CSS
//   AC-3:      trips/+page.svelte — archiveTarget State + ConfirmDialog für Archivieren
//   AC-4/AC-5: trips/+page.svelte — handleArchive Funktion vorhanden
//   AC-6:      trips/+page.svelte — Dearchivieren-Pfad kein separater Dialog
//
// RED vor Implementierung: Patterns fehlen → Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_594_598_feedback_dialoge.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

const TRIP_HEADER = join(root, 'lib/components/trip-detail/TripHeader.svelte');
const TRIPS_PAGE  = join(root, 'routes/trips/+page.svelte');

const read = (f: string) => readFileSync(f, 'utf-8');

// ─── #594: TripHeader.svelte ──────────────────────────────────────────────────

test('#594 AC-1/AC-2: testBriefingKind State-Variable existiert in TripHeader', () => {
	const src = read(TRIP_HEADER);
	assert.ok(
		src.includes('testBriefingKind'),
		'testBriefingKind State fehlt in TripHeader.svelte'
	);
});

test('#594 AC-1: Erfolg-Feedback verwendet --g-success Token', () => {
	const src = read(TRIP_HEADER);
	assert.ok(
		src.includes('--g-success'),
		'--g-success Farbe für Erfolgs-Feedback fehlt in TripHeader.svelte'
	);
});

test('#594 AC-2: Fehler-Feedback verwendet --g-danger Token', () => {
	const src = read(TRIP_HEADER);
	assert.ok(
		src.includes('--g-danger'),
		'--g-danger Farbe für Fehler-Feedback fehlt in TripHeader.svelte'
	);
});

test('#594: briefing-msg verwendet NICHT --g-ink-muted (unzureichender Kontrast)', () => {
	const src = read(TRIP_HEADER);
	// Die .briefing-msg darf --g-ink-muted nicht mehr als Content-Farbe verwenden
	// Prüfung: wenn --g-ink-muted in briefing-msg-Block vorkommt, schlägt der Test fehl
	const briefingMsgBlock = src.match(/\.briefing-msg\s*\{([^}]+)\}/s)?.[1] ?? '';
	assert.ok(
		!briefingMsgBlock.includes('--g-ink-muted'),
		'briefing-msg CSS verwendet noch --g-ink-muted (WCAG-Verstoß für Content-Text)'
	);
});

// ─── #598: trips/+page.svelte ────────────────────────────────────────────────

test('#598 AC-3: archiveTarget State-Variable existiert in trips/+page.svelte', () => {
	const src = read(TRIPS_PAGE);
	assert.ok(
		src.includes('archiveTarget'),
		'archiveTarget State fehlt in trips/+page.svelte'
	);
});

test('#598 AC-5: handleArchive Funktion existiert in trips/+page.svelte', () => {
	const src = read(TRIPS_PAGE);
	assert.ok(
		src.includes('handleArchive'),
		'handleArchive Funktion fehlt in trips/+page.svelte'
	);
});

test('#598 AC-3: ConfirmDialog für Archivieren mit korrektem Titel vorhanden', () => {
	const src = read(TRIPS_PAGE);
	assert.ok(
		src.includes('Trip archivieren'),
		'ConfirmDialog mit "Trip archivieren" Titel fehlt in trips/+page.svelte'
	);
});

test('#598 AC-3: ConfirmDialog für Archivieren zeigt Kontext-Beschreibung', () => {
	const src = read(TRIPS_PAGE);
	assert.ok(
		src.includes('keine Briefings mehr'),
		'Beschreibungstext "keine Briefings mehr" fehlt im Archivieren-Dialog'
	);
});

test('#598 AC-6: Dearchivieren-Pfad hat KEINEN eigenen archiveTarget-Zweig', () => {
	const src = read(TRIPS_PAGE);
	// handlePrimaryAction für Dearchivieren darf direkt die action ausführen
	// Nachweis: handleArchive setzt archiveTarget=null → nur für Archivieren-Confirm
	// Negativ-Test: kein "dearchiveTarget" oder "deArchiveTarget"
	assert.ok(
		!src.includes('dearchiveTarget') && !src.includes('deArchiveTarget'),
		'Unerwarteter dearchiveTarget-State gefunden (Dearchivieren soll keinen Dialog haben)'
	);
});
