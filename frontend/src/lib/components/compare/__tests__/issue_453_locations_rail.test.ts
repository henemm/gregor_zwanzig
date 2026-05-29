// Issue #453 — Locations-Rail Erweiterungen fuer die Compare-Hauptbuehne
// Spec: docs/specs/modules/issue_453_locations_rail_hauptbuehne.md
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
// Alle Tests muessen im TDD-RED-Zustand FEHLSCHLAGEN.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const RAIL = resolve('src/lib/components/compare/LocationsRail.svelte');
const GROUP = resolve('src/lib/components/compare/GroupSection.svelte');

// Vorbedingung: Dateien existieren
test('Voraussetzung: LocationsRail.svelte existiert', () => {
	assert.ok(existsSync(RAIL), `Datei nicht gefunden: ${RAIL}`);
});

test('Voraussetzung: GroupSection.svelte existiert', () => {
	assert.ok(existsSync(GROUP), `Datei nicht gefunden: ${GROUP}`);
});

// AC-Breite: width: 240px gesetzt, 320px nicht mehr vorhanden
test('AC-Breite: Rail ist 240px breit (nicht mehr 320px)', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /240px/, 'Rail muss width: 240px enthalten');
	assert.doesNotMatch(src, /width:\s*320px/, 'Rail darf kein width: 320px mehr enthalten');
});

// AC-Zaehler: data-testid compare-rail-counter vorhanden
test('AC-Zaehler: compare-rail-counter TestID vorhanden', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /compare-rail-counter/, 'Rail muss data-testid="compare-rail-counter" enthalten');
});

// AC-Zaehler-Farben: alle drei Design-Tokens referenziert
test('AC-Zaehler-Farben: --g-danger fuer < 2 Orte referenziert', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /--g-danger/, 'Rail muss --g-danger fuer Danger-Zustand referenzieren');
});

test('AC-Zaehler-Farben: --g-success fuer 2-8 Orte referenziert', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /--g-success/, 'Rail muss --g-success fuer gueltigen Bereich referenzieren');
});

test('AC-Zaehler-Farben: --g-ink-muted fuer > 8 Orte referenziert', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /--g-ink-muted/, 'Rail muss --g-ink-muted fuer Obergrenze referenzieren');
});

// AC-5: Leerzustand — EmptyState Import und TestID
test('AC-5: EmptyState-Import vorhanden (empty-state)', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /empty-state/, 'Rail muss EmptyState aus $lib/components/ui/empty-state importieren');
});

test('AC-5: compare-rail-empty TestID vorhanden', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /compare-rail-empty/, 'Rail muss data-testid="compare-rail-empty" enthalten');
});

test('AC-5: Leerzustand prueft locations.length === 0', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /locations\.length\s*===\s*0/, 'Rail muss auf locations.length === 0 pruefen');
});

// AC-DnD: onReorder-Prop in LocationsRail
test('AC-DnD: LocationsRail deklariert onReorder-Prop', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /onReorder/, 'Rail muss onReorder-Prop im Props-Interface deklarieren');
});

test('AC-DnD: LocationsRail haelt internen dragSourceId-State', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /dragSourceId/, 'Rail muss dragSourceId als lokalen $state halten');
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

// Smoke: bestehende Funktionalitaet aus #249 unveraendert
test('Smoke AC-1: LocationsRail importiert GroupSection (Gruppen-Render unveraendert)', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /GroupSection/, 'Rail muss GroupSection importieren (AC-1 aus #249)');
});

test('Smoke AC-3: Suche-TestID compare-rail-search vorhanden', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /compare-rail-search/, 'Rail muss data-testid="compare-rail-search" enthalten (AC-3 aus #249)');
});

test('Smoke AC-4: NEU-Button TestID compare-rail-new-btn vorhanden', () => {
	const src = readFileSync(RAIL, 'utf-8');
	assert.match(src, /compare-rail-new-btn/, 'Rail muss data-testid="compare-rail-new-btn" enthalten (AC-4 aus #249)');
});
