// TDD RED: Issue #568 — Startseite-Redesign (Cockpit + Planungs-/Leerzustand)
//
// Spec: docs/specs/modules/issue_568_home_redesign.md
//
// Source-Inspection-Tests (kein Render, keine Mocks):
//   1) QuickAction.svelte — Existenz, Props, Touch-Target, Glyph-Mapping
//   2) SetupResumeCard.svelte — Existenz, Props, Fortschrittsbalken, CTA
//   3) molecules/index.ts — beide neuen Exports vorhanden
//   4) cockpitHelpers.ts — neue Helper: dayProgress, setupStepTrip,
//      setupStepCompare, nextPlannedTrip, firstIncompleteCompare
//   5) +page.svelte — kein ElevSparkline/StagePill-Pillstreifen, QuickAction
//      verwendet, Planungs-Leerzustand vorhanden
//
// RED vor Implementierung: Dateien und Exporte fehlen → Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_568_home_redesign.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

import {
	dayProgress,
	setupStepTrip,
	setupStepCompare,
	nextPlannedTrip,
	firstIncompleteCompare
} from './utils/cockpitHelpers568.ts';

import type { Trip, ComparePreset } from './types.ts';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const MOLECULES = join(root, 'lib/components/molecules');
const HELPERS = join(root, 'lib/utils/cockpitHelpers568.ts');
const PAGE = join(root, 'routes/+page.svelte');

const read = (f: string) => readFileSync(f, 'utf-8');
const has = (f: string) => existsSync(f);

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function trip(overrides: Partial<Trip> = {}): Trip {
	return { id: 't1', name: 'Test', stages: [], ...overrides } as Trip;
}

function comparePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return { id: 'c1', name: 'Test', locations: [], ...overrides } as ComparePreset;
}

const NOW = new Date('2026-06-10T09:00:00Z');

// ─── AC-1 / AC-2: QuickAction Molecule ────────────────────────────────────────

test('#568 QuickAction.svelte existiert in molecules/', () => {
	assert.ok(has(join(MOLECULES, 'QuickAction.svelte')), 'QuickAction.svelte fehlt');
});

test('#568 QuickAction nutzt href (kein onClick API)', () => {
	const src = read(join(MOLECULES, 'QuickAction.svelte'));
	assert.ok(/href/.test(src), 'QuickAction braucht href-Prop');
	assert.ok(/glyph/.test(src), 'QuickAction braucht glyph-Prop');
	assert.ok(/label/.test(src), 'QuickAction braucht label-Prop');
	assert.ok(/sub/.test(src), 'QuickAction braucht sub-Prop (Ziel-Sublabel)');
});

test('#568 QuickAction Touch-Target ≥ 44px (Mobile AC-7)', () => {
	const src = read(join(MOLECULES, 'QuickAction.svelte'));
	assert.ok(/44px|min-height.*44|44.*min-height/.test(src),
		'QuickAction Touch-Target min-height 44px fehlt');
});

test('#568 QuickAction tone accent/default + size md/lg', () => {
	const src = read(join(MOLECULES, 'QuickAction.svelte'));
	assert.ok(/accent/.test(src), 'QuickAction tone accent fehlt');
	assert.ok(/\bmd\b/.test(src), 'QuickAction size md fehlt');
	assert.ok(/\blg\b/.test(src), 'QuickAction size lg fehlt');
});

// ─── AC-3 / AC-4: SetupResumeCard Molecule ────────────────────────────────────

test('#568 SetupResumeCard.svelte existiert in molecules/', () => {
	assert.ok(has(join(MOLECULES, 'SetupResumeCard.svelte')), 'SetupResumeCard.svelte fehlt');
});

test('#568 SetupResumeCard Props: eyebrow, title, steps, ctaLabel, ctaHref', () => {
	const src = read(join(MOLECULES, 'SetupResumeCard.svelte'));
	assert.ok(/eyebrow/.test(src), 'SetupResumeCard eyebrow-Prop fehlt');
	assert.ok(/title/.test(src), 'SetupResumeCard title-Prop fehlt');
	assert.ok(/steps/.test(src), 'SetupResumeCard steps-Prop fehlt');
	assert.ok(/ctaLabel/.test(src), 'SetupResumeCard ctaLabel-Prop fehlt');
	assert.ok(/ctaHref/.test(src), 'SetupResumeCard ctaHref-Prop fehlt');
});

test('#568 SetupResumeCard zeigt Fortschrittsbalken', () => {
	const src = read(join(MOLECULES, 'SetupResumeCard.svelte'));
	// Fortschrittsbalken via width-Prozentsatz
	assert.ok(/width.*%|%.*width|progress/.test(src),
		'SetupResumeCard Fortschrittsbalken (width %) fehlt');
});

test('#568 SetupResumeCard tone accent/default (Trip vs. Vergleich)', () => {
	const src = read(join(MOLECULES, 'SetupResumeCard.svelte'));
	assert.ok(/accent/.test(src), 'SetupResumeCard tone accent fehlt');
});

test('#568 SetupResumeCard Touch-Target CTA ≥ 44px (Mobile AC-7)', () => {
	const src = read(join(MOLECULES, 'SetupResumeCard.svelte'));
	assert.ok(/44px|min-height.*44|44.*min-height/.test(src),
		'SetupResumeCard CTA Touch-Target 44px fehlt');
});

// ─── AC-6: molecules/index.ts exportiert beide neuen Molecules ────────────────

test('#568 molecules/index.ts exportiert QuickAction', () => {
	const idx = read(join(MOLECULES, 'index.ts'));
	assert.ok(/QuickAction/.test(idx), 'index.ts exportiert QuickAction nicht');
});

test('#568 molecules/index.ts exportiert SetupResumeCard', () => {
	const idx = read(join(MOLECULES, 'index.ts'));
	assert.ok(/SetupResumeCard/.test(idx), 'index.ts exportiert SetupResumeCard nicht');
});

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
		display_config: { ideal_ranges: { wind_speed: { min: 0, max: 20 } }, channel_layouts: {} }
	}) as unknown as import('./types.ts').ComparePreset;
	(preset as unknown as Record<string, unknown>)['report_config'] = { morning_enabled: true };
	const result = firstIncompleteCompare([preset]);
	assert.strictEqual(result, null);
});

// ─── AC-1: +page.svelte: kein Sparkline, kein Pillstreifen ───────────────────

test('#568 +page.svelte importiert kein ElevSparkline mehr (Sparkline entfernt)', () => {
	const src = read(PAGE);
	assert.ok(!/ElevSparkline/.test(src),
		'+page.svelte darf ElevSparkline nicht mehr importieren');
});

test('#568 +page.svelte hat keinen Etappen-Pillstreifen (stageStripState entfernt)', () => {
	const src = read(PAGE);
	assert.ok(!/stageStripState/.test(src),
		'+page.svelte darf stageStripState nicht mehr verwenden');
	assert.ok(!/Etappen-Verlauf/.test(src),
		'+page.svelte darf keinen Etappen-Verlauf-Block mehr haben');
});

test('#568 +page.svelte importiert QuickAction', () => {
	const src = read(PAGE);
	assert.ok(/QuickAction/.test(src),
		'+page.svelte muss QuickAction importieren');
});

test('#568 +page.svelte importiert SetupResumeCard', () => {
	const src = read(PAGE);
	assert.ok(/SetupResumeCard/.test(src),
		'+page.svelte muss SetupResumeCard importieren');
});

test('#568 +page.svelte: Fortschrittsbalken Tag X von Y', () => {
	const src = read(PAGE);
	assert.ok(/dayX|Tag.*von|day.*progress|dayProgress/.test(src),
		'+page.svelte muss Tag-X-von-Y-Fortschritt zeigen');
});

test('#568 +page.svelte: Planungs-Leerzustand existiert', () => {
	const src = read(PAGE);
	assert.ok(/kein.*Trip|Planungs|SetupResumeCard/.test(src),
		'+page.svelte muss Planungs-/Leerzustand zeigen');
});

// ─── AC-5: Tab-Routing korrekt ────────────────────────────────────────────────

test('#568 +page.svelte: Schnellaktion verlinkt auf ?tab=stages', () => {
	const src = read(PAGE);
	assert.ok(/tab=stages/.test(src),
		'+page.svelte muss ?tab=stages-Link für Etappen-Tab haben');
});

test('#568 +page.svelte: Schnellaktion verlinkt auf ?tab=weather', () => {
	const src = read(PAGE);
	assert.ok(/tab=weather/.test(src),
		'+page.svelte muss ?tab=weather-Link haben');
});

test('#568 +page.svelte: Schnellaktion verlinkt auf ?tab=briefings', () => {
	const src = read(PAGE);
	assert.ok(/tab=briefings/.test(src),
		'+page.svelte muss ?tab=briefings-Link haben');
});

test('#568 +page.svelte: Schnellaktion verlinkt auf ?tab=preview', () => {
	const src = read(PAGE);
	assert.ok(/tab=preview/.test(src),
		'+page.svelte muss ?tab=preview-Link haben');
});
