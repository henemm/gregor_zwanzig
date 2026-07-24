// Issue #568 — Startseite-Redesign (Cockpit + Planungs-/Leerzustand)
//
// Spec: docs/specs/modules/issue_568_home_redesign.md
//
// Verhaltens-Tests für die reinen Helper-Funktionen in cockpitHelpers568.ts
// (dayProgress, setupStepTrip, setupStepCompare, nextPlannedTrip,
// firstIncompleteCompare). Die ursprünglichen Source-Inspection-Tests
// (readFileSync/existsSync gegen QuickAction.svelte/SetupResumeCard.svelte/
// molecules/index.ts/+page.svelte) wurden entfernt — Dateiinhalt-Checks sind
// laut CLAUDE.md verboten (Präzedenz #893).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_568_home_redesign.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	dayProgress,
	setupStepTrip,
	setupStepCompare,
	nextPlannedTrip,
	firstIncompleteCompare
} from './utils/cockpitHelpers568.ts';

import type { Trip, ComparePreset } from './types.ts';

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function trip(overrides: Partial<Trip> = {}): Trip {
	return { id: 't1', name: 'Test', stages: [], ...overrides } as Trip;
}

function comparePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return { id: 'c1', name: 'Test', locations: [], ...overrides } as ComparePreset;
}

const NOW = new Date('2026-06-10T09:00:00Z');

// ─── Helper-Tests (pure functions) ────────────────────────────────────────────

test('#568 dayProgress: Tag 3 von 12 → 25 %', () => {
	const result = dayProgress(3, 12);
	assert.strictEqual(result, 25, 'dayProgress(3, 12) muss 25 % sein');
});

test('#568 dayProgress: erster Tag (1 von 1) → 100 %', () => {
	assert.strictEqual(dayProgress(1, 1), 100);
});

test('#568 dayProgress: 0 von 0 → 0 % (kein Division-by-zero)', () => {
	assert.strictEqual(dayProgress(0, 0), 0);
});

test('#568 setupStepTrip: leerer Trip → alle 5 Schritte offen', () => {
	const steps = setupStepTrip(trip());
	assert.strictEqual(steps.length, 5);
	assert.ok(steps.every((s) => !s.done), 'Alle Schritte sollten offen sein');
});

test('#568 setupStepTrip: Trip mit 1 Stage ohne Datum → nur Schritt 1 done', () => {
	const t = trip({ stages: [{ id: 's1', name: 'D1', waypoints: [] } as unknown as import('./types.ts').Stage] });
	const steps = setupStepTrip(t);
	assert.strictEqual(steps[0].done, true, 'Route-Schritt: ≥1 Stage → done');
	assert.strictEqual(steps[1].done, false, 'Etappen-Schritt: kein Datum → offen');
});

test('#568 setupStepTrip: vollständiger Trip → alle 5 Schritte done', () => {
	const t = trip({
		stages: [{ id: 's1', name: 'D1', date: '2026-07-01', waypoints: [] }],
		display_config: {
			metrics: [{ metric_id: 'wind_speed', enabled: true, use_friendly_format: false }],
			preset_name: 'Sommer-Trekking'
		},
		report_config: {
			morning_enabled: true,
			evening_enabled: false
		}
	});
	const steps = setupStepTrip(t);
	assert.ok(steps.every((s) => s.done), 'Vollständiger Trip: alle Schritte done');
});

test('#568 setupStepCompare: leerer Vergleich → alle 5 Schritte offen (außer Step 1)', () => {
	const steps = setupStepCompare(comparePreset());
	// Step 1 (Vergleich) ist immer done
	assert.strictEqual(steps[0].done, true, 'Vergleich-Schritt: immer done');
	assert.strictEqual(steps[1].done, false, 'Orte-Schritt: 0 Locations → offen');
});

test('#568 setupStepCompare: 2 location_ids → Orte-Schritt done', () => {
	const steps = setupStepCompare(comparePreset({
		location_ids: ['l1', 'l2']
	}));
	assert.strictEqual(steps[1].done, true, 'Orte-Schritt: 2 location_ids → done');
});

// #1351 Fix-Loop (Adversary F006, HIGH): channel_layouts/preset_name sind seit
// #1351 (AC-6) kein Compare-Feld mehr — der "Layout"-Schritt muss auf ein
// tatsächlich vom Nutzer bedientes Signal (active_metrics) umgestellt sein,
// sonst bleibt er für JEDEN Vergleich für immer offen.
test('#1351 F006 setupStepCompare: ausgewählte active_metrics → Layout-Schritt done', () => {
	const steps = setupStepCompare(comparePreset({
		display_config: { active_metrics: ['wind_speed', 'temp_max_c'] }
	}));
	assert.strictEqual(steps[3].label, 'Layout');
	assert.strictEqual(steps[3].done, true, 'Layout-Schritt: gesetzte active_metrics → done');
});

test('#1351 F006 setupStepCompare: frischer, unkonfigurierter Vergleich → Layout-Schritt offen', () => {
	const steps = setupStepCompare(comparePreset());
	assert.strictEqual(steps[3].label, 'Layout');
	assert.strictEqual(steps[3].done, false, 'Layout-Schritt: keine active_metrics → offen');
});

test('#568 nextPlannedTrip: gibt ersten Trip mit zukünftigem Startdatum zurück', () => {
	const future = trip({
		id: 'future',
		stages: [{ id: 's1', name: 'D1', date: '2026-07-01', waypoints: [] }]
	});
	const past = trip({
		id: 'past',
		stages: [{ id: 's1', name: 'D1', date: '2026-05-01', waypoints: [] }]
	});
	const result = nextPlannedTrip([past, future], NOW);
	assert.strictEqual(result?.id, 'future');
});

test('#568 nextPlannedTrip: gibt null zurück wenn kein zukünftiger Trip', () => {
	const result = nextPlannedTrip([], NOW);
	assert.strictEqual(result, null);
});

test('#568 firstIncompleteCompare: Vergleich ohne Versand → nicht vollständig', () => {
	const preset = comparePreset({
		location_ids: ['l1', 'l2'],
		display_config: { ideal_ranges: { wind_speed: { min: 0, max: 20 } }, channel_layouts: {} }
		// kein report_config.morning_enabled → unvollständig
	});
	const result = firstIncompleteCompare([preset]);
	assert.strictEqual(result?.id, 'c1');
});

test('#568 firstIncompleteCompare: vollständiger Vergleich → null', () => {
	const preset = comparePreset({
		location_ids: ['l1', 'l2'],
		// #1351 F006-Fix: channel_layouts ist kein Compare-Signal mehr (AC-6) —
		// active_metrics (tatsächlich vom Nutzer im Wetter-Metriken-Tab gepflegt)
		// steht jetzt für den "Layout"-Schritt.
		display_config: { ideal_ranges: { wind_speed: { min: 0, max: 20 } }, active_metrics: ['wind_speed'] }
	}) as unknown as import('./types.ts').ComparePreset;
	(preset as unknown as Record<string, unknown>)['report_config'] = { morning_enabled: true };
	const result = firstIncompleteCompare([preset]);
	assert.strictEqual(result, null);
});
