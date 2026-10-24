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

import { liveTrip } from './utils/cockpitHelpers568.ts';
import { homeCompareTimeline } from '../routes/_home/cockpitHelpers.ts';

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
			{ id: 's1', date: '2026-06-01', name: 'Start', waypoints: [] },
			{ id: 's2', date: '2026-06-10', name: 'Ende', waypoints: [] },
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
			{ id: 's1', date: '2026-06-01', name: 'Start', waypoints: [] },
			{ id: 's2', date: '2026-06-10', name: 'Ende', waypoints: [] },
		],
	});
	const result = liveTrip([trip], now);
	assert.strictEqual(result, null, 'liveTrip muss null zurückgeben wenn kein Trip aktiv');
});

test('AC-1b: liveTrip gibt null für leere Trip-Liste zurück', () => {
	const result = liveTrip([], new Date());
	assert.strictEqual(result, null, 'liveTrip muss null für leere Liste zurückgeben');
});

// ─── AC-4: Nächster Versand (seit #1969 Backend-Wert statt deriveNextSend) ────
// Welcher Termin der nächste ist (heute vs. morgen, manual), entscheidet die
// Backend-Ableitung (tests/tdd/test_next_briefing.py). Hier bewacht: die
// Startseiten-Zeile zeigt genau diesen Termin — Tag aus local_date, Stunde aus
// local_time — und bei manual keinen.

const nb = (local_date: string, local_time: string) => ({
	at: `${local_date}T${local_time}:00+02:00`,
	local_date,
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
});
const naechsteZeile = (preset: ComparePreset, wert: unknown) =>
	homeCompareTimeline(preset, wert as never).find((r) => r.when.startsWith('Nächster · '));

test('AC-4: daily — Backend meldet heute 06:00 → Zeile zeigt Fr 06:00', () => {
	const preset = makeCompare({ schedule: 'daily', morning_time: '06:00:00' });
	const zeile = naechsteZeile(preset, nb('2026-06-05', '06:00'));
	assert.ok(zeile, 'Nächster-Zeile fehlt');
	assert.ok(zeile!.when.includes('Fr 06:00 (CEST)'), zeile!.when);
	assert.strictEqual(zeile!.status, 'planned');
});

test('AC-4b: daily — Backend meldet morgen 06:00 → Zeile zeigt Sa 06:00', () => {
	const preset = makeCompare({ schedule: 'daily', morning_time: '06:00:00' });
	const zeile = naechsteZeile(preset, nb('2026-06-06', '06:00'));
	assert.ok(zeile!.when.includes('Sa 06:00 (CEST)'), zeile!.when);
});

test('AC-4c: manual — Backend meldet keinen Termin → keine Nächster-Zeile', () => {
	const preset = makeCompare({ schedule: 'manual' });
	assert.strictEqual(naechsteZeile(preset, { at: null, reason: 'manual' }), undefined);
});
