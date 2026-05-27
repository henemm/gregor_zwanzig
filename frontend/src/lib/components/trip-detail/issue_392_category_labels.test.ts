// TDD RED: Issue #392 — CATEGORY_LABELS in metricsEditor.ts zentralisieren
//
// Spec: docs/specs/modules/issue_392_category_labels_centralize.md
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/issue_392_category_labels.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

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

// =============================================================================
// AC-2 — WeatherMetricsTab.svelte: keine Inline-Definitionen mehr
// =============================================================================

const __dirname = dirname(fileURLToPath(import.meta.url));

const WEATHER_METRICS_TAB = resolve(__dirname, 'WeatherMetricsTab.svelte');
const tabSource = readFileSync(WEATHER_METRICS_TAB, 'utf-8');

test('AC-2: WeatherMetricsTab.svelte definiert CATEGORY_LABELS NICHT inline', () => {
	const hasInline = /const\s+CATEGORY_LABELS\s*[:=]/.test(tabSource);
	assert.equal(
		hasInline,
		false,
		'WeatherMetricsTab.svelte definiert CATEGORY_LABELS noch inline — muss entfernt und durch Import ersetzt werden',
	);
});

test('AC-2: WeatherMetricsTab.svelte definiert CATEGORY_ORDER NICHT inline', () => {
	const hasInline = /const\s+CATEGORY_ORDER\s*[:=]/.test(tabSource);
	assert.equal(
		hasInline,
		false,
		'WeatherMetricsTab.svelte definiert CATEGORY_ORDER noch inline — muss aus metricsEditor.ts importiert werden',
	);
});

test('AC-2: WeatherMetricsTab.svelte definiert INDICATOR_MAP NICHT inline', () => {
	const hasInline = /const\s+INDICATOR_MAP\s*[:=]/.test(tabSource);
	assert.equal(
		hasInline,
		false,
		'WeatherMetricsTab.svelte definiert INDICATOR_MAP noch inline — muss aus metricsEditor.ts importiert werden',
	);
});

test('AC-2: WeatherMetricsTab.svelte definiert indicatorCapable NICHT inline als function', () => {
	const hasInline = /function\s+indicatorCapable\s*\(/.test(tabSource);
	assert.equal(
		hasInline,
		false,
		'WeatherMetricsTab.svelte definiert indicatorCapable() noch inline — muss aus metricsEditor.ts importiert werden',
	);
});

test('AC-2: WeatherMetricsTab.svelte importiert CATEGORY_LABELS aus metricsEditor.ts', () => {
	const hasImport = /import\s*\{[^}]*CATEGORY_LABELS[^}]*\}\s*from\s*['"]\.\/metricsEditor/.test(tabSource);
	assert.ok(
		hasImport,
		'CATEGORY_LABELS wird nicht aus metricsEditor.ts importiert in WeatherMetricsTab.svelte',
	);
});

// =============================================================================
// AC-3 — WeatherConfigDialog.svelte: keine Inline-Definitionen mehr
// =============================================================================

const WEATHER_CONFIG_DIALOG = resolve(__dirname, '../WeatherConfigDialog.svelte');
const dialogSource = readFileSync(WEATHER_CONFIG_DIALOG, 'utf-8');

test('AC-3: WeatherConfigDialog.svelte definiert CATEGORY_LABELS NICHT inline', () => {
	const hasInline = /const\s+CATEGORY_LABELS\s*[:=]/.test(dialogSource);
	assert.equal(
		hasInline,
		false,
		'WeatherConfigDialog.svelte definiert CATEGORY_LABELS noch inline — muss entfernt und durch Import ersetzt werden',
	);
});

test('AC-3: WeatherConfigDialog.svelte definiert CATEGORY_ORDER NICHT inline', () => {
	const hasInline = /const\s+CATEGORY_ORDER\s*[:=]/.test(dialogSource);
	assert.equal(
		hasInline,
		false,
		'WeatherConfigDialog.svelte definiert CATEGORY_ORDER noch inline — muss aus metricsEditor.ts importiert werden',
	);
});

test('AC-3: WeatherConfigDialog.svelte importiert CATEGORY_LABELS aus metricsEditor.ts', () => {
	const hasImport = /import\s*\{[^}]*CATEGORY_LABELS[^}]*\}\s*from\s*['"].*metricsEditor/.test(dialogSource);
	assert.ok(
		hasImport,
		'CATEGORY_LABELS wird nicht aus metricsEditor.ts importiert in WeatherConfigDialog.svelte',
	);
});

// =============================================================================
// AC-5 — WeatherMetricsTab gibt categoryLabels korrekt als Prop weiter
// (Source-Inspection: sicherstellen dass kein hardcoded Objekt uebergeben wird)
// =============================================================================

test('AC-5: WeatherMetricsTab uebergibt categoryLabels={CATEGORY_LABELS} an BucketSectionOff (nicht inline)', () => {
	// Prueft: Der Prop-Aufruf nutzt CATEGORY_LABELS (die importierte Konstante),
	// kein hardcoded Objekt-Literal mit temperature/wind/...
	const hasInlineProp = /categoryLabels=\{\s*\{/.test(tabSource);
	assert.equal(
		hasInlineProp,
		false,
		'categoryLabels-Prop wird mit inline-Objekt uebergeben statt mit importierter CATEGORY_LABELS-Konstante',
	);
	const hasCorrectProp = /categoryLabels=\{CATEGORY_LABELS\}/.test(tabSource);
	assert.ok(
		hasCorrectProp,
		'categoryLabels={CATEGORY_LABELS} nicht in WeatherMetricsTab.svelte gefunden',
	);
});
