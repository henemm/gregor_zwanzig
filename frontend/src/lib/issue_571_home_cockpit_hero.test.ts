// TDD RED: Issue #571 — Home Cockpit Hero (Compare-Modus + CompareStatusRow + Stretch-Fix)
//
// Spec: docs/specs/modules/issue_571_home_cockpit_hero.md
//
// Source-Inspection-Tests (kein Render, keine Mocks):
//   1) cockpitHelpers568.ts — neue Exports: liveTrip, deriveNextSend
//   2) CompareStatusRow.svelte — Existenz, Props, Touch-Target
//   3) molecules/index.ts — CompareStatusRow exportiert
//   4) +page.svelte — mode="compare"-Logik, align-items:start, kein CompareKachel-Grid,
//      "Was geht raus · <name>"-Titel, CompareStatusRow verwendet
//
// RED vor Implementierung: Funktionen und Komponenten fehlen → Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_571_home_cockpit_hero.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

import {
	liveTrip,
	deriveNextSend,
} from './utils/cockpitHelpers568.ts';

import type { Trip, ComparePreset } from './types.ts';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const MOLECULES = join(root, 'lib/components/molecules');
const HELPERS = join(root, 'lib/utils/cockpitHelpers568.ts');
const PAGE = join(root, 'routes/+page.svelte');

function read(rel: string): string {
	return readFileSync(join(root, rel), 'utf-8');
}

// ─── Hilfs-Fixtures ──────────────────────────────────────────────────────────

function makeTrip(overrides: Partial<Trip> = {}): Trip {
	return {
		id: 'trip-1',
		name: 'GR20',
		stages: [
			{ date: '2026-06-01', name: 'Calenzana', waypoints: [] },
			{ date: '2026-06-10', name: 'Conca', waypoints: [] },
		],
		report_config: {} as never,
		display_config: {} as never,
		...overrides,
	} as Trip;
}

function makeCompare(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-1',
		name: 'Skigebiet Vergleich',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		hour_from: 6,
		hour_to: 8,
		empfaenger: ['test@henemm.com'],
		profil: 'winter_skiing' as never,
		created_at: '2026-01-01T00:00:00Z',
		...overrides,
	} as ComparePreset;
}

// ─── AC-1/AC-2/AC-3: liveTrip() ──────────────────────────────────────────────

test('AC-1: liveTrip gibt den aktiven Trip zurück wenn heute im Reise-Zeitraum liegt', () => {
	const now = new Date('2026-06-05T10:00:00Z');
	const trip = makeTrip({
		stages: [
			{ date: '2026-06-01', name: 'Start', waypoints: [] },
			{ date: '2026-06-10', name: 'Ende', waypoints: [] },
		],
	});
	const result = liveTrip([trip], now);
	assert.ok(result !== null, 'liveTrip muss den aktiven Trip zurückgeben');
	assert.strictEqual(result!.id, 'trip-1');
});

test('AC-2: liveTrip gibt null zurück wenn kein Trip heute aktiv ist', () => {
	const now = new Date('2026-07-01T10:00:00Z');
	const trip = makeTrip({
		stages: [
			{ date: '2026-06-01', name: 'Start', waypoints: [] },
			{ date: '2026-06-10', name: 'Ende', waypoints: [] },
		],
	});
	const result = liveTrip([trip], now);
	assert.strictEqual(result, null, 'liveTrip muss null zurückgeben wenn kein Trip aktiv');
});

test('AC-1b: liveTrip gibt null für leere Trip-Liste zurück', () => {
	const result = liveTrip([], new Date());
	assert.strictEqual(result, null, 'liveTrip muss null für leere Liste zurückgeben');
});

// ─── AC-4: deriveNextSend() ───────────────────────────────────────────────────

test('AC-4: deriveNextSend daily — gibt heute 06:00 zurück wenn es 04:00 ist (Versand noch nicht erreicht)', () => {
	const now = new Date('2026-06-05T04:00:00');
	const preset = makeCompare({ schedule: 'daily', hour_from: 6 });
	const result = deriveNextSend(preset, now);
	assert.ok(result !== null, 'deriveNextSend muss einen Timestamp zurückgeben');
	assert.strictEqual(result!.getDate(), now.getDate(), 'Datum muss heute sein');
	assert.strictEqual(result!.getHours(), 6, 'Stunde muss 6 sein');
});

test('AC-4b: deriveNextSend daily — gibt morgen 06:00 zurück wenn es bereits 07:00 ist', () => {
	const now = new Date('2026-06-05T07:00:00');
	const preset = makeCompare({ schedule: 'daily', hour_from: 6 });
	const result = deriveNextSend(preset, now);
	assert.ok(result !== null, 'deriveNextSend muss einen Timestamp zurückgeben');
	assert.strictEqual(result!.getDate(), now.getDate() + 1, 'Datum muss morgen sein');
	assert.strictEqual(result!.getHours(), 6, 'Stunde muss 6 sein');
});

test('AC-4c: deriveNextSend manual — gibt null zurück', () => {
	const now = new Date('2026-06-05T04:00:00');
	const preset = makeCompare({ schedule: 'manual' });
	const result = deriveNextSend(preset, now);
	assert.strictEqual(result, null, 'deriveNextSend muss null für manual-Schedule zurückgeben');
});

// ─── AC-8: CompareStatusRow in Molecules-Barrel ───────────────────────────────

test('AC-8: molecules/index.ts exportiert CompareStatusRow', () => {
	const src = readFileSync(join(MOLECULES, 'index.ts'), 'utf-8');
	assert.match(
		src,
		/CompareStatusRow/,
		'molecules/index.ts muss CompareStatusRow exportieren'
	);
});

// ─── AC-8b: CompareStatusRow.svelte existiert ─────────────────────────────────

test('AC-8b: CompareStatusRow.svelte existiert im molecules-Ordner', () => {
	const path = join(MOLECULES, 'CompareStatusRow.svelte');
	assert.ok(existsSync(path), 'CompareStatusRow.svelte muss in molecules/ existieren');
});

// ─── AC-9: Touch-Target ≥ 44px ───────────────────────────────────────────────

test('AC-9: CompareStatusRow.svelte definiert Touch-Target ≥ 44px', () => {
	const src = readFileSync(join(MOLECULES, 'CompareStatusRow.svelte'), 'utf-8');
	assert.match(
		src,
		/44px/,
		'CompareStatusRow.svelte muss min-height: 44px für Touch-Target definieren'
	);
});

// ─── AC-10: align-items: start im cockpit-hero-Grid ─────────────────────────

test('AC-10: .cockpit-hero CSS enthält align-items: start (kein Stretch-Artefakt)', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// Prüft ob im cockpit-hero CSS-Block align-items: start steht
	assert.match(
		src,
		/align-items:\s*start/,
		'.cockpit-hero muss align-items: start enthalten um das Stretch-Artefakt zu beheben'
	);
});

// ─── AC-11: "Was geht raus · <name>"-Titel ───────────────────────────────────

test('AC-11: +page.svelte enthält "Was geht raus ·" mit dynamischem Kontext-Namen', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// Der Titel muss dynamisch mit dem Namen des aktiven Kontexts sein
	assert.match(
		src,
		/Was geht raus\s*[··]\s*\{/,
		'Der Titel "Was geht raus" muss einen dynamischen Namen (Template-Expression) enthalten'
	);
});

// ─── AC-6/AC-7: CompareStatusRow im Home-Screen, kein CompareKachel-Grid ─────

test('AC-7 / AC-12: +page.svelte verwendet CompareStatusRow statt CompareKachel-Grid', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/CompareStatusRow/,
		'+page.svelte muss CompareStatusRow für aktive Vergleiche verwenden'
	);
});

test('AC-12: +page.svelte rendert kein CompareKachel-Grid mehr für aktive Vergleiche', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// CompareKachel darf nicht mehr als aktive-Vergleiche-Loop verwendet werden
	// (Datei kann noch importiert sein, aber nicht mehr im Aktiv-Vergleiche-Abschnitt)
	assert.doesNotMatch(
		src,
		/activePresets[.\s\S]{0,200}CompareKachel/,
		'+page.svelte darf aktive Vergleiche nicht mehr als CompareKachel-Grid rendern'
	);
});

// ─── AC-2: mode="compare"-Logik im Home-Screen ───────────────────────────────

test('AC-2: +page.svelte enthält mode="compare"-Logik (Compare als Hero wenn kein Trip aktiv)', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// Entweder als Variable 'mode' oder als explizite Bedingung für Compare-Hero
	assert.match(
		src,
		/mode\s*===\s*['"]compare['"]|heroMode\s*===\s*['"]compare['"]/,
		'+page.svelte muss Compare-Hero-Modus implementieren'
	);
});

// ─── AC-5: cockpitHelpers568.ts enthält liveTrip und deriveNextSend ───────────

test('AC-5: cockpitHelpers568.ts exportiert liveTrip', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export function liveTrip/,
		'cockpitHelpers568.ts muss liveTrip exportieren'
	);
});

test('AC-5b: cockpitHelpers568.ts exportiert deriveNextSend', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export function deriveNextSend/,
		'cockpitHelpers568.ts muss deriveNextSend exportieren'
	);
});
