// Issue #453 — Locations-Rail Erweiterungen fuer die Compare-Hauptbuehne
// Spec: docs/specs/modules/issue_453_locations_rail_hauptbuehne.md
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
//
// Issue #1256 Scheibe 1 (2026-07-13): LocationsRail.svelte wurde als
// verifizierter Totcode gelöscht (kein produktiver Import, Spec Zeilen
// 303-305) — alle RAIL-spezifischen Tests (Breite, Zähler, Leerzustand,
// DnD-Props der Rail selbst, Smoke-Checks) wurden entfernt (Test-Politik
// CLAUDE.md: veraltetes Verhalten löschen statt rot liegenlassen). Die
// GroupSection.svelte-Tests bleiben erhalten — diese Komponente ist NICHT
// Teil der Scheibe-1-Löschliste.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const GROUP = resolve('src/lib/components/compare/GroupSection.svelte');

// Vorbedingung: Datei existiert
test('Voraussetzung: GroupSection.svelte existiert', () => {
	assert.ok(existsSync(GROUP), `Datei nicht gefunden: ${GROUP}`);
});

// AC-DnD: GroupSection DnD-Props
test('AC-DnD: GroupSection deklariert onDragStart-Prop', () => {
	const src = readFileSync(GROUP, 'utf-8');
	assert.match(src, /onDragStart/, 'GroupSection muss onDragStart-Prop deklarieren');
});

test('AC-DnD: GroupSection deklariert onDrop-Prop', () => {
	const src = readFileSync(GROUP, 'utf-8');
	assert.match(src, /onDrop/, 'GroupSection muss onDrop-Prop deklarieren');
});

test('AC-DnD: GroupSection setzt draggable auf li-Elementen', () => {
	const src = readFileSync(GROUP, 'utf-8');
	assert.match(src, /draggable/, 'GroupSection muss draggable="true" auf li-Elementen setzen');
});
