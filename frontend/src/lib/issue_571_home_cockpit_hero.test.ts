// Issue #571 — Home Cockpit Hero (Compare-Modus + CompareStatusRow + Stretch-Fix)
//
// Spec: docs/specs/modules/issue_571_home_cockpit_hero.md
//
// Verhaltens-Tests für die reinen Helper-Funktionen liveTrip und deriveNextSend
// in cockpitHelpers568.ts. Die ursprünglichen Source-Inspection-Tests
// (readFileSync/existsSync gegen molecules/index.ts, CompareStatusRow.svelte,
// +page.svelte) wurden entfernt — Dateiinhalt-Checks sind laut CLAUDE.md
// verboten (Präzedenz #893).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_571_home_cockpit_hero.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	liveTrip,
	deriveNextSend,
} from './utils/cockpitHelpers568.ts';

import type { Trip, ComparePreset } from './types.ts';

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
