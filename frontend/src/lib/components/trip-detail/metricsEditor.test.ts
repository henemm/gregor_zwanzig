// TDD RED: Epic #138 Phase 2 — Metriken-Editor UI-Komponenten (Issues #174–178)
//
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md
//
// Tests scheitern absichtlich (RED): metricsEditor.ts existiert noch nicht.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/metricsEditor.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	INDICATOR_MAP,
	indicatorCapable,
	buildDirtySnapshot,
	isDirty,
	countActiveInCategory,
	buildPresetSummary,
	selectTableColumns,
} from './metricsEditor.ts';

// =============================================================================
// §4 INDICATOR_MAP — 12 Metriken (AC-4)
// =============================================================================

test('INDICATOR_MAP > hat genau 12 Eintraege', () => {
	assert.equal(Object.keys(INDICATOR_MAP).length, 12);
});

test('INDICATOR_MAP > enthaelt die 9 backend-eligible Metriken', () => {
	const backendEligible = [
		'wind_direction', 'thunder', 'cape',
		'cloud_total', 'cloud_low', 'cloud_mid', 'cloud_high',
		'visibility', 'sunshine',
	];
	for (const id of backendEligible) {
		assert.ok(id in INDICATOR_MAP, `${id} fehlt in INDICATOR_MAP`);
	}
});

test('INDICATOR_MAP > enthaelt die 3 frontend-erweiterten Metriken', () => {
	assert.ok('wind' in INDICATOR_MAP, 'wind fehlt');
	assert.ok('gust' in INDICATOR_MAP, 'gust fehlt');
	assert.ok('rain_probability' in INDICATOR_MAP, 'rain_probability fehlt');
});

test('INDICATOR_MAP > wind hat Skala ruhig/maessig/stark/sturm', () => {
	assert.ok(INDICATOR_MAP['wind'].includes('ruhig'), 'erwartet "ruhig" in wind-Skala');
	assert.ok(INDICATOR_MAP['wind'].includes('sturm'), 'erwartet "sturm" in wind-Skala');
});

test('INDICATOR_MAP > temperature ist NICHT enthalten', () => {
	assert.equal('temperature' in INDICATOR_MAP, false);
});

test('INDICATOR_MAP > precipitation ist NICHT enthalten', () => {
	assert.equal('precipitation' in INDICATOR_MAP, false);
});

// =============================================================================
// indicatorCapable — Wrapper ueber INDICATOR_MAP (AC-4)
// =============================================================================

test('indicatorCapable > gibt true fuer wind_direction', () => {
	assert.equal(indicatorCapable('wind_direction'), true);
});

test('indicatorCapable > gibt true fuer wind (frontend-erweitert)', () => {
	assert.equal(indicatorCapable('wind'), true);
});

test('indicatorCapable > gibt false fuer temperature', () => {
	assert.equal(indicatorCapable('temperature'), false);
});

test('indicatorCapable > gibt false fuer unbekannte ID', () => {
	assert.equal(indicatorCapable('nonexistent_metric'), false);
});

// =============================================================================
// dirty-State — buildDirtySnapshot + isDirty (AC-1, AC-2)
// =============================================================================

test('buildDirtySnapshot > serialisiert enabledMap und friendlyMap', () => {
	const enabledMap = { temperature: true, wind: false };
	const friendlyMap = { wind_direction: true };
	const snapshot = buildDirtySnapshot(enabledMap, friendlyMap);
	assert.equal(typeof snapshot, 'string');
	const parsed = JSON.parse(snapshot);
	assert.deepEqual(parsed.enabledMap, enabledMap);
	assert.deepEqual(parsed.friendlyMap, friendlyMap);
});

test('isDirty > false wenn enabledMap und friendlyMap unveraendert', () => {
	const enabledMap = { temperature: true, wind: false };
	const friendlyMap = { wind_direction: true };
	const snapshot = buildDirtySnapshot(enabledMap, friendlyMap);
	assert.equal(isDirty(enabledMap, friendlyMap, snapshot), false);
});

test('isDirty > true wenn enabledMap geaendert', () => {
	const orig = { temperature: true, wind: false };
	const origFriendly = { wind_direction: true };
	const snapshot = buildDirtySnapshot(orig, origFriendly);
	const changed = { temperature: false, wind: false }; // temperature geaendert
	assert.equal(isDirty(changed, origFriendly, snapshot), true);
});

test('isDirty > true wenn friendlyMap geaendert', () => {
	const origEnabled = { temperature: true };
	const origFriendly = { wind_direction: true };
	const snapshot = buildDirtySnapshot(origEnabled, origFriendly);
	const changedFriendly = { wind_direction: false }; // false statt true
	assert.equal(isDirty(origEnabled, changedFriendly, snapshot), true);
});

test('isDirty > false bei leerem Snapshot (initialer Zustand)', () => {
	const enabledMap = { temperature: true };
	const friendlyMap = {};
	const snapshot = buildDirtySnapshot(enabledMap, friendlyMap);
	assert.equal(isDirty(enabledMap, friendlyMap, snapshot), false);
});

// =============================================================================
// countActiveInCategory — MetricGroup-Zaehler (AC-3, AC-8)
// =============================================================================

test('countActiveInCategory > zaehlt aktivierte Metriken in einer Kategorie', () => {
	const metricIds = ['temperature', 'wind_chill', 'humidity'];
	const enabledMap = { temperature: true, wind_chill: false, humidity: true };
	assert.equal(countActiveInCategory(metricIds, enabledMap), 2);
});

test('countActiveInCategory > gibt 0 zurueck wenn keine aktiv', () => {
	const metricIds = ['temperature', 'wind_chill'];
	const enabledMap = { temperature: false, wind_chill: false };
	assert.equal(countActiveInCategory(metricIds, enabledMap), 0);
});

test('countActiveInCategory > gibt totalCount zurueck wenn alle aktiv', () => {
	const metricIds = ['temperature', 'wind_chill'];
	const enabledMap = { temperature: true, wind_chill: true };
	assert.equal(countActiveInCategory(metricIds, enabledMap), 2);
});

test('countActiveInCategory > behandelt fehlende Eintraege in enabledMap als false', () => {
	const metricIds = ['temperature', 'wind_chill'];
	const enabledMap = { temperature: true }; // wind_chill nicht in Map
	assert.equal(countActiveInCategory(metricIds, enabledMap), 1);
});

// =============================================================================
// buildPresetSummary — SavePresetDialog-Zusammenfassung (AC-6)
// =============================================================================

test('buildPresetSummary > zaehlt aktive, Rohwert, Indikator korrekt', () => {
	const enabledMap = {
		temperature: true,
		wind: true,
		wind_direction: true,
		precipitation: false,
	};
	const friendlyMap = {
		wind: false,         // Rohwert
		wind_direction: true // Indikator
	};
	const summary = buildPresetSummary(enabledMap, friendlyMap);
	// 3 aktiv (temperature, wind, wind_direction)
	assert.equal(summary.activeCount, 3);
	// wind ist indicatorCapable + friendlyMap[wind]=false → Rohwert
	// wind_direction ist indicatorCapable + friendlyMap[wind_direction]=true → Indikator
	// temperature ist nicht indicatorCapable → weder Roh noch Indikator
	assert.equal(summary.rawCount, 1);
	assert.equal(summary.indicatorCount, 1);
});

test('buildPresetSummary > activeCount 0 bei leerem enabledMap', () => {
	const summary = buildPresetSummary({}, {});
	assert.equal(summary.activeCount, 0);
	assert.equal(summary.rawCount, 0);
	assert.equal(summary.indicatorCount, 0);
});

// =============================================================================
// selectTableColumns — TablePreview Spaltenauswahl (AC-5)
// =============================================================================

test('selectTableColumns > gibt nur aktivierte Metriken zurueck', () => {
	const catalog = {
		temperature: [
			{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, has_friendly_format: false },
			{ id: 'wind_chill', label: 'Gefühlte Temp.', unit: '°C', category: 'temperature', default_enabled: false, has_friendly_format: false },
		],
		wind: [
			{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, has_friendly_format: false },
		],
	};
	const enabledMap = { temperature: true, wind_chill: false, wind: true };
	const cols = selectTableColumns(catalog, enabledMap);
	const ids = cols.map((c: { id: string }) => c.id);
	assert.ok(ids.includes('temperature'), 'temperature sollte enthalten sein');
	assert.ok(ids.includes('wind'), 'wind sollte enthalten sein');
	assert.equal(ids.includes('wind_chill'), false, 'wind_chill sollte nicht enthalten sein');
});

test('selectTableColumns > gibt leeres Array bei leerer enabledMap', () => {
	const catalog = {
		temperature: [
			{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, has_friendly_format: false },
		],
	};
	const cols = selectTableColumns(catalog, { temperature: false });
	assert.equal(cols.length, 0);
});

test('selectTableColumns > respektiert Kategorie-Reihenfolge (temperature vor wind)', () => {
	const catalog = {
		wind: [
			{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, has_friendly_format: false },
		],
		temperature: [
			{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, has_friendly_format: false },
		],
	};
	const enabledMap = { wind: true, temperature: true };
	const cols = selectTableColumns(catalog, enabledMap);
	// temperature (Kategorie index 0) sollte vor wind (index 1) kommen
	assert.equal(cols[0].id, 'temperature');
	assert.equal(cols[1].id, 'wind');
});
