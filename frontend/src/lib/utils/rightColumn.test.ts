// TDD RED: Epic #135 Step 5 — Right-Column Pure-Functions (Issues #158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md
//
// Feature #1435 Etappe E3a: `getDefaultMetricsForProfile`, `getActiveMetrics`
// und `prettyLabel` wurden entfernt — ihr einziger Aufrufer war die seit
// Issue #487 tote rechte Vorschau-Karte. `getReportSchedule`/`getActivePreset`/
// `getPresetLabel` bleiben produktiv (TripHeader.svelte, BriefingPreviewCard.svelte,
// TripEditView.svelte) und sind hier unveraendert.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/rightColumn.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	getPresetLabel,
	getActivePreset,
	getReportSchedule,
	type ReportSchedule
} from './rightColumn.ts';

import type { Aggregation, ReportConfig, Trip } from '../types.ts';

// =============================================================================
// Helpers
// =============================================================================

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

// =============================================================================
// getPresetLabel
// =============================================================================

// getPresetLabel

test('getPresetLabel > AC-13a: profile = "wintersport" → "Wintersport-Standard"', () => {
	const trip = tripWith({ aggregation: { profile: 'wintersport' } });
	assert.equal(getPresetLabel(trip), 'Wintersport-Standard');
});

test('getPresetLabel > AC-13b: profile = "wandern" → "Wandern-Standard"', () => {
	const trip = tripWith({ aggregation: { profile: 'wandern' } });
	assert.equal(getPresetLabel(trip), 'Wandern-Standard');
});

test('getPresetLabel > AC-13c: profile = "allgemein" → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: { profile: 'allgemein' } });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13d: unbekanntes Profile → "Standard-Metriken"', () => {
	// Issue #207: Off-Spec-Wert — testet Defensiv-Pfad gegen Fremddaten.
	const trip = tripWith({
		aggregation: { profile: 'mountainbike' } as unknown as Aggregation
	});
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13e: profile = null → "Standard-Metriken"', () => {
	// Issue #207: Off-Spec-Wert — Backend kann null senden, Defensiv-Pfad.
	const trip = tripWith({
		aggregation: { profile: null } as unknown as Aggregation
	});
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13f: profile = undefined → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: {} });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > Trip ohne aggregation → "Standard-Metriken"', () => {
	const trip = tripWith({});
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

// =============================================================================
// getReportSchedule
// =============================================================================

// getReportSchedule

test('getReportSchedule > AC-15a: voll konfiguriert → strukturiertes Schedule-Objekt', () => {
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: '06:00:00',
			evening_time: '18:00:00',
			alert_on_changes: true
		}
	});
	const schedule: ReportSchedule = getReportSchedule(trip);
	assert.deepEqual(schedule, {
		enabled: true,
		morning: '06:00:00',
		evening: '18:00:00',
		morning_enabled: false,
		evening_enabled: false,
		alertOnChanges: true
	});
});

test('getReportSchedule > enabled: false → enabled=false, alertOnChanges=false (Defaults)', () => {
	const trip = tripWith({
		report_config: { enabled: false }
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.enabled, false);
	assert.equal(schedule.alertOnChanges, false);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});

test('getReportSchedule > AC-15b: kein report_config → enabled=false, alertOnChanges=false, morning/evening undefined', () => {
	const trip = tripWith({});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.enabled, false);
	assert.equal(schedule.alertOnChanges, false);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});

test('getReportSchedule > Nur morning_time, kein evening_time → evening: undefined', () => {
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: '07:30:00',
			alert_on_changes: false
		}
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.morning, '07:30:00');
	assert.equal(schedule.evening, undefined);
	assert.equal(schedule.alertOnChanges, false);
	assert.equal(schedule.enabled, true);
});

test('getReportSchedule > alert_on_changes nicht boolean → alertOnChanges=false', () => {
	// Issue #207: Off-Spec — alert_on_changes als String. Defensiver Strict-Compare.
	const trip = tripWith({
		report_config: { enabled: true, alert_on_changes: 'yes' } as unknown as ReportConfig
	});
	// Spec: rc.alert_on_changes === true → exakter Strict-Compare
	assert.equal(getReportSchedule(trip).alertOnChanges, false);
});

test('getReportSchedule > morning_time / evening_time als Non-String → undefined', () => {
	// Issue #207: Off-Spec — Backend liefert Non-String fuer Zeit-Felder.
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: 6,
			evening_time: null
		} as unknown as ReportConfig
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});

// =============================================================================
// Issue #232 — summer_trekking-Profil-Behandlung
// Spec: docs/specs/modules/epic_135_step5_right_column.md AC-13 (erweitert),
// AC-19, AC-20, AC-21 (Changelog 2026-05-16).
// =============================================================================

test('getPresetLabel > AC-13g: profile = "summer_trekking" → "Sommer-Trekking-Standard"', () => {
	const trip = tripWith({ aggregation: { profile: 'summer_trekking' } });
	assert.equal(getPresetLabel(trip), 'Sommer-Trekking-Standard');
});

// =============================================================================
// Issue #206 — preset_name in display_config
// Spec: docs/specs/modules/issue_206_weather_config_preset_name.md
// =============================================================================

test('getPresetLabel > #206 AC-3: display_config.preset_name="wandern" → "Wandern" (nicht "Wandern-Standard")', () => {
	const trip = tripWith({
		display_config: { preset_name: 'wandern' },
		aggregation: { profile: 'wintersport' }
	});
	assert.equal(getPresetLabel(trip), 'Wandern');
});

test('getPresetLabel > #206 AC-3b: display_config.preset_name="wintersport" → "Wintersport"', () => {
	const trip = tripWith({
		display_config: { preset_name: 'wintersport' },
		aggregation: { profile: 'wandern' }
	});
	assert.equal(getPresetLabel(trip), 'Wintersport');
});

test('getPresetLabel > #206 AC-8: unbekannter preset_name → Fallback auf profile', () => {
	const trip = tripWith({
		display_config: { preset_name: 'geloeschtes-template-xyz' },
		aggregation: { profile: 'wandern' }
	});
	assert.equal(getPresetLabel(trip), 'Wandern-Standard');
});

// =============================================================================
// Issue #173 — Metriken-Editor: Preset-Liste (getActivePreset)
// Spec: docs/specs/modules/issue_173_metriken_editor_preset_liste.md
//
// PresetRow.svelte braucht eine Helper-Funktion, die aus `trip.display_config`
// den aktiv ausgewählten Template-Key liefert. Single Source of Truth: das
// persistierte `preset_name` aus display_config (Issue #206). Wenn kein Preset
// gespeichert ist, liefert getActivePreset null — keine PresetRow ist aktiv.
//
// TDD RED: getActivePreset existiert noch nicht in rightColumn.ts.
// =============================================================================

test('getActivePreset > #173 AC-4: display_config.preset_name="skitouren" → "skitouren"', () => {
	// AC-4: Trip mit gespeichertem Preset liefert genau diesen Template-Key.
	// WeatherMetricsTab setzt damit selectedTemplate = "skitouren" und die
	// "Skitouren"-PresetRow bekommt class:active.
	const trip = tripWith({
		display_config: { preset_name: 'skitouren' }
	});
	assert.equal(getActivePreset(trip), 'skitouren');
});

test('getActivePreset > #173 AC-4b: display_config.preset_name="wandern" → "wandern"', () => {
	const trip = tripWith({
		display_config: { preset_name: 'wandern' }
	});
	assert.equal(getActivePreset(trip), 'wandern');
});

test('getActivePreset > #173 AC-6: kein preset_name → null (keine Row aktiv)', () => {
	// AC-6: Frischer Trip ohne preset_name → keine PresetRow hat class:active.
	const trip = tripWith({
		display_config: { metrics: [] }
	});
	assert.equal(getActivePreset(trip), null);
});

test('getActivePreset > #173 AC-6b: kein display_config → null', () => {
	const trip = tripWith({});
	assert.equal(getActivePreset(trip), null);
});

test('getActivePreset > #173: leerer String preset_name → null', () => {
	// Defensiv: Backend kann '' liefern statt undefined. Leerer String darf
	// keine Row aktivieren (entspricht "kein Preset").
	const trip = tripWith({
		display_config: { preset_name: '' }
	});
	assert.equal(getActivePreset(trip), null);
});

test('getActivePreset > #173: preset_name Non-String → null (Defensiv-Pfad)', () => {
	// Issue #207-Style Off-Spec-Pfad: Backend liefert Non-String. Defensive
	// Behandlung — kein Crash, sondern null.
	const trip = tripWith({
		display_config: { preset_name: 42 } as unknown as import('../types.ts').DisplayConfig
	});
	assert.equal(getActivePreset(trip), null);
});
