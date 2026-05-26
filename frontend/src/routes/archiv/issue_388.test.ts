// TDD RED: Issue #388 — Archiv-Seite auf Atomic-Bibliothek migrieren
//
// Spec:  docs/specs/modules/issue_388_archiv_atomic.md
// Route: /archiv  →  frontend/src/routes/archiv/
//
// Source-Inspection-Tests (analog zu contrast-audit.test.ts):
// Liest die echten .svelte/.ts-Quelldateien als String und prüft, ob die
// Atomic-Migration korrekt umgesetzt wurde.
//
// RED: Gegen den aktuellen Placeholder (+page.svelte mit EmptyState, kein
// +page.server.ts) schlagen alle Implementierungs-Tests fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/archiv/issue_388.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const ARCHIV_DIR = dirname(fileURLToPath(import.meta.url));
const PAGE_SVELTE  = join(ARCHIV_DIR, '+page.svelte');
const PAGE_SERVER  = join(ARCHIV_DIR, '+page.server.ts');

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

function readFile(path: string): string {
	return readFileSync(path, 'utf-8');
}

// ── AC-1 / AC-6: SSR-Loader ──────────────────────────────────────────────────

test('AC-6: +page.server.ts existiert (SSR-Loader neu erstellt)', () => {
	assert.ok(
		existsSync(PAGE_SERVER),
		`+page.server.ts fehlt unter ${PAGE_SERVER}`
	);
});

test('AC-6: +page.server.ts filtert auf archived_at != null', () => {
	assert.ok(existsSync(PAGE_SERVER), '+page.server.ts fehlt');
	const src = readFile(PAGE_SERVER);
	assert.ok(
		src.includes('archived_at'),
		'Kein archived_at-Filter in +page.server.ts gefunden'
	);
	assert.ok(
		src.includes('null'),
		'archived_at-Vergleich mit null fehlt'
	);
});

test('AC-6: +page.server.ts nutzt AbortSignal.timeout für fail-soft', () => {
	assert.ok(existsSync(PAGE_SERVER), '+page.server.ts fehlt');
	const src = readFile(PAGE_SERVER);
	assert.ok(
		src.includes('AbortSignal.timeout'),
		'AbortSignal.timeout nicht gefunden — Loader ist nicht fail-soft'
	);
});

// ── AC-2 / AC-3: Atom-Importe in +page.svelte ────────────────────────────────

test('AC-3: +page.svelte importiert Segmented (ersetzt ArchiveSortTab)', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes("from '$lib/components/ui/segmented") ||
		src.includes("import Segmented"),
		'Segmented-Import nicht gefunden — ArchiveSortTab wurde nicht durch Atom ersetzt'
	);
});

test('AC-3: +page.svelte importiert Btn (ersetzt ArchiveAction)', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes("from '$lib/components/ui/btn") ||
		src.includes("import { Btn }"),
		'Btn-Import nicht gefunden — ArchiveAction wurde nicht durch Atom ersetzt'
	);
});

test('AC-3: +page.svelte importiert Stat aus molecules (Stats-Strip)', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes("from '$lib/components/molecules") ||
		src.includes("import Stat"),
		'Stat-Import aus molecules nicht gefunden'
	);
});

// ── AC-3: Kein Inline-ArchiveSortTab mehr ────────────────────────────────────

test('AC-3: +page.svelte definiert KEINE Inline-Funktion ArchiveSortTab', () => {
	const src = readFile(PAGE_SVELTE);
	// Inline-function-Definition der alten JSX-Komponente darf nicht portiert werden
	assert.ok(
		!src.includes('ArchiveSortTab'),
		'ArchiveSortTab-Inline-Duplikat gefunden — muss durch Segmented-Atom ersetzt sein'
	);
});

test('AC-3: +page.svelte definiert KEINE Inline-Funktion ArchiveAction', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		!src.includes('ArchiveAction'),
		'ArchiveAction-Inline-Duplikat gefunden — muss durch Btn-Atom ersetzt sein'
	);
});

// ── AC-2: Reaktive State-Variablen ───────────────────────────────────────────

test('AC-2: +page.svelte deklariert sort-State und SORT_OPTIONS', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes('SORT_OPTIONS'),
		'SORT_OPTIONS nicht gefunden — Segmented-Options fehlen'
	);
	assert.ok(
		src.includes("$state(") && src.includes('sort'),
		"sort-State ($state) nicht deklariert — reaktive Sortierung fehlt"
	);
});

test('AC-2: +page.svelte deklariert query-State und filtered-Derived', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes('$state(') && src.includes('query'),
		"query-State ($state) fehlt — reaktive Suche nicht implementiert"
	);
	assert.ok(
		src.includes('$derived(') && src.includes('filtered'),
		"filtered-Derived ($derived) fehlt"
	);
});

// ── AC-5: AccuracyBar-Platzhalter mit Kommentar ───────────────────────────────

test('AC-5: +page.svelte enthält AccuracyBar-Platzhalter-Kommentar', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes('accuracy-Daten ausstehend') ||
		src.includes('AccuracyBar: accuracy'),
		'AccuracyBar-Platzhalter-Kommentar fehlt (Spec-Anforderung: explizit markieren)'
	);
});

// ── AC-4: Kein Hex-Farbliteral in +page.svelte ────────────────────────────────

test('AC-4: +page.svelte enthält keine rohen Hex-Farbliterale als CSS-Farbwert', () => {
	const src = readFile(PAGE_SVELTE);
	// Findet Hex-Literale die als color/stroke/fill direkt eingesetzt werden
	// (nicht als Kommentar oder String-Literal in einem nicht-CSS-Kontext)
	const hexInColor = /(?:color|stroke|fill)\s*[:=]\s*["']?#[0-9a-fA-F]{3,6}\b/g;
	const matches = src.match(hexInColor) ?? [];
	assert.deepEqual(
		matches,
		[],
		`Hex-Farbliterale als CSS-Eigenschaft gefunden: ${matches.join(', ')} — auf Design-Tokens umstellen`
	);
});

// ── AC-1: EmptyState-Placeholder ist ersetzt ─────────────────────────────────

test('AC-1: +page.svelte verwendet nicht mehr den alten EmptyState-Placeholder', () => {
	const src = readFile(PAGE_SVELTE);
	// Der alte Placeholder hatte nur "Noch keine abgeschlossenen Trips im Archiv."
	assert.ok(
		!src.includes('Noch keine abgeschlossenen Trips im Archiv.'),
		'Alter EmptyState-Placeholder noch vorhanden — Seite wurde nicht implementiert'
	);
});

test('AC-1: +page.svelte rendert Tabellen-Struktur (grid, Kopfzeile, ArchiveRow)', () => {
	const src = readFile(PAGE_SVELTE);
	assert.ok(
		src.includes('ArchiveRow') || src.includes('archiveRow'),
		'ArchiveRow-Komponente nicht gefunden — Tabellen-Struktur fehlt'
	);
});
