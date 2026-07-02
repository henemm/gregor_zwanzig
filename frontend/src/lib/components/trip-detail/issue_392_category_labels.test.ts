// Issue #392 — CATEGORY_LABELS in metricsEditor.ts zentralisieren
//
// Spec: docs/specs/modules/issue_392_category_labels_centralize.md
//
// Die ursprünglichen AC-2/AC-3/AC-5-Tests (readFileSync-Source-Inspection gegen
// WeatherMetricsTab.svelte/WeatherConfigDialog.svelte) wurden entfernt —
// Dateiinhalt-Checks sind laut CLAUDE.md verboten (Präzedenz #893). Die
// Verhaltens-Tests unten (AC-1: echter Import aus metricsEditor.ts) bleiben.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/issue_392_category_labels.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

// AC-1: CATEGORY_LABELS muss aus metricsEditor.ts importierbar sein.
// RED: schlaegt fehl weil CATEGORY_LABELS noch nicht exportiert ist.
import * as editor from './metricsEditor.ts';

// =============================================================================
// AC-1 + AC-4 — CATEGORY_LABELS exportiert und korrekt befuellt
// =============================================================================

test('AC-1: CATEGORY_LABELS ist aus metricsEditor.ts exportiert', () => {
	assert.ok(
		'CATEGORY_LABELS' in editor,
		'CATEGORY_LABELS fehlt als Export in metricsEditor.ts',
	);
});

test('AC-1: CATEGORY_LABELS hat genau 5 Schluessel', () => {
	const labels = (editor as Record<string, unknown>)['CATEGORY_LABELS'] as Record<string, string>;
	assert.equal(
		Object.keys(labels).length,
		5,
		`Erwartet 5 Schluessel, gefunden: ${Object.keys(labels).join(', ')}`,
	);
});

test('AC-1: CATEGORY_LABELS enthaelt alle fuenf Kategorie-IDs', () => {
	const labels = (editor as Record<string, unknown>)['CATEGORY_LABELS'] as Record<string, string>;
	const expected = ['temperature', 'wind', 'precipitation', 'atmosphere', 'winter'];
	for (const key of expected) {
		assert.ok(key in labels, `Schluessel '${key}' fehlt in CATEGORY_LABELS`);
	}
});

test('AC-4: CATEGORY_LABELS[winter] ist "Winter / Schnee" (mit Leerzeichen um den Slash)', () => {
	const labels = (editor as Record<string, unknown>)['CATEGORY_LABELS'] as Record<string, string>;
	assert.equal(
		labels['winter'],
		'Winter / Schnee',
		`winter-Label divergiert: erwartet "Winter / Schnee", erhalten: "${labels['winter']}"`,
	);
});

test('AC-1: CATEGORY_LABELS enthaelt deutsche Anzeige-Labels', () => {
	const labels = (editor as Record<string, unknown>)['CATEGORY_LABELS'] as Record<string, string>;
	assert.equal(labels['temperature'], 'Temperatur');
	assert.equal(labels['wind'], 'Wind');
	assert.equal(labels['precipitation'], 'Niederschlag');
	assert.equal(labels['atmosphere'], 'Atmosphäre');
});
