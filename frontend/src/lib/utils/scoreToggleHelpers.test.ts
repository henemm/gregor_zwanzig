// TDD RED — Score-Toggle-Helpers (Issue #362).
//
// Spec: docs/specs/modules/issue_362_score_toggle.md
//
// ERWARTET: Import-Fehler (Cannot find module './scoreToggleHelpers.ts')
// bis die Helper-Datei implementiert ist.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/scoreToggleHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildScoreMap,
	extractScoreMemberFilter,
} from './scoreToggleHelpers.ts';

// Typ-Definition (spiegelt WeatherConfigMetric.score_member)
type MetricEntry = { id: string; default_enabled: boolean };
type MetricCatalog = Record<string, MetricEntry[]>;
type SavedMetric = {
	metric_id: string;
	enabled: boolean;
	use_friendly_format?: boolean;
	score_member?: boolean;
};

function makeCatalog(ids: string[]): MetricCatalog {
	return {
		test_category: ids.map((id) => ({ id, default_enabled: true })),
	};
}

// --- AC-7: buildScoreMap — Default true wenn score_member fehlt ------------

test('AC-7: buildScoreMap defaults to true when score_member missing from config', () => {
	// GIVEN: gespeicherte Config hat Metriken OHNE score_member-Feld
	const catalog = makeCatalog(['wind', 'precipitation', 'temperature']);
	const config: Record<string, unknown> = {
		metrics: [
			{ metric_id: 'wind', enabled: true, use_friendly_format: true },
			{ metric_id: 'precipitation', enabled: true, use_friendly_format: false },
		] satisfies Omit<SavedMetric, 'score_member'>[],
	};

	const scoreMap = buildScoreMap(catalog, config);

	// Alle Einträge aus Catalog müssen true sein (Default)
	assert.strictEqual(scoreMap['wind'], true, 'wind sollte Default true haben');
	assert.strictEqual(scoreMap['precipitation'], true, 'precipitation sollte Default true haben');
	assert.strictEqual(scoreMap['temperature'], true, 'temperature (nur im Catalog, nicht in Config) sollte true haben');
});

// --- AC-1: buildScoreMap — liest score_member:false korrekt aus Config ------

test('AC-1: buildScoreMap reads score_member:false from saved config', () => {
	// GIVEN: gespeicherte Config hat score_member:false für eine Metrik
	const catalog = makeCatalog(['wind', 'precipitation', 'temperature']);
	const config: Record<string, unknown> = {
		metrics: [
			{ metric_id: 'wind', enabled: true, score_member: true },
			{ metric_id: 'precipitation', enabled: true, score_member: false },
		] satisfies SavedMetric[],
	};

	const scoreMap = buildScoreMap(catalog, config);

	assert.strictEqual(scoreMap['wind'], true, 'wind sollte true sein');
	assert.strictEqual(scoreMap['precipitation'], false, 'precipitation sollte false sein (score_member=false)');
	assert.strictEqual(scoreMap['temperature'], true, 'temperature (nur Catalog) sollte Default true sein');
});

// --- AC-7: buildScoreMap — undefined config → alle true --------------------

test('AC-7: buildScoreMap with undefined config returns all true', () => {
	// GIVEN: keine gespeicherte Config (neue Location)
	const catalog = makeCatalog(['wind', 'precipitation']);
	const scoreMap = buildScoreMap(catalog, undefined);

	assert.strictEqual(scoreMap['wind'], true);
	assert.strictEqual(scoreMap['precipitation'], true);
});

// --- AC-6: extractScoreMemberFilter — alle false → gibt null zurück --------

test('AC-6: extractScoreMemberFilter returns null when all metrics excluded (empty intersection fallback)', () => {
	// GIVEN: scoreMap mit allen false
	const scoreMap: Record<string, boolean> = {
		wind: false,
		precipitation: false,
		temperature: false,
	};

	const filter = extractScoreMemberFilter(scoreMap);

	// null = Fallback auf alle aktiv (kein Filter)
	assert.strictEqual(filter, null, 'Wenn alle false: null zurückgeben für Fallback');
});

// --- AC-2: extractScoreMemberFilter — gibt Set der aktiven Metriken zurück --

test('AC-2: extractScoreMemberFilter returns Set of active metric IDs when some are excluded', () => {
	// GIVEN: scoreMap mit gemischten Werten
	const scoreMap: Record<string, boolean> = {
		wind: true,
		precipitation: false,
		temperature: true,
	};

	const filter = extractScoreMemberFilter(scoreMap);

	// Nicht null: genau die true-Einträge sind im Ergebnis
	assert.notEqual(filter, null, 'Wenn nicht alle false: Set zurückgeben');
	if (filter !== null) {
		assert.ok(filter.has('wind'), 'wind sollte im Filter sein');
		assert.ok(!filter.has('precipitation'), 'precipitation sollte NICHT im Filter sein');
		assert.ok(filter.has('temperature'), 'temperature sollte im Filter sein');
	}
});

// --- AC-7: buildScoreMap — score_member:true explizit → true ----------------

test('AC-7: buildScoreMap with explicit score_member:true stays true', () => {
	const catalog = makeCatalog(['wind']);
	const config: Record<string, unknown> = {
		metrics: [{ metric_id: 'wind', enabled: true, score_member: true }] satisfies SavedMetric[],
	};

	const scoreMap = buildScoreMap(catalog, config);
	assert.strictEqual(scoreMap['wind'], true);
});

// --- AC-1: buildScoreMap — Deaktivierte Metrik behält score_member-Wert ----

test('AC-1: buildScoreMap preserves score_member value even for disabled metrics', () => {
	// GIVEN: Metrik ist disabled, hat score_member:false gespeichert
	// THEN:  Wert bleibt erhalten (UI kann Toggle zeigen wenn wieder aktiviert)
	const catalog = makeCatalog(['sunshine']);
	const config: Record<string, unknown> = {
		metrics: [{ metric_id: 'sunshine', enabled: false, score_member: false }] satisfies SavedMetric[],
	};

	const scoreMap = buildScoreMap(catalog, config);
	assert.strictEqual(scoreMap['sunshine'], false, 'score_member:false bleibt auch bei disabled=true erhalten');
});
