// TDD RED: Issue #416 — Mobile Kennzahlen-Kacheln im Trip-Detail-Header.
//
// Spec: docs/specs/modules/issue_416_mobile_trip_kennzahlen.md
//
// Drei mobile-only Stat-Kacheln (ETAPPE, BRIEFING, START IN / TAG) werden
// unterhalb des Status-Badges in TripHeader.svelte ergänzt.
// Sichtbar nur auf Viewport ≤ 899px (display:none auf Desktop).
//
// Test-Pattern: Source-Inspection — liest TripHeader.svelte als String und
// prüft Markup-Struktur + CSS. Identisch zu TripHeader.spacing.test.ts.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/TripHeader.mobile-metrics.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'TripHeader.svelte');
const source = readFileSync(COMPONENT, 'utf8');

// ---------------------------------------------------------------------------
// AC-1 / AC-5: data-testid-Attribute vorhanden
// ---------------------------------------------------------------------------

test('AC-5: Container-Wrapper mit data-testid="trip-header-mobile-metrics" vorhanden', () => {
	assert.ok(
		source.includes('data-testid="trip-header-mobile-metrics"'),
		'Erwarte data-testid="trip-header-mobile-metrics" in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-5: ETAPPE-Kachel mit data-testid="metric-etappe" vorhanden', () => {
	assert.ok(
		source.includes('data-testid="metric-etappe"'),
		'Erwarte data-testid="metric-etappe" in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-5: BRIEFING-Kachel mit data-testid="metric-briefing" vorhanden', () => {
	assert.ok(
		source.includes('data-testid="metric-briefing"'),
		'Erwarte data-testid="metric-briefing" in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-5: START IN / TAG-Kachel mit data-testid="metric-start" vorhanden', () => {
	assert.ok(
		source.includes('data-testid="metric-start"'),
		'Erwarte data-testid="metric-start" in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// AC-4: Mobile-Breakpoint und Desktop-Versteckung im CSS
// ---------------------------------------------------------------------------

test('AC-4: @media (max-width: 899px) für Kacheln im CSS-Block vorhanden', () => {
	// Prüft: es gibt eine .mobile-metrics-Klasse UND einen 899px-Breakpoint.
	// Konsistenter Breakpoint im gesamten Projekt.
	assert.ok(
		source.includes('mobile-metrics') && source.includes('max-width: 899px'),
		'Erwarte ".mobile-metrics" + "@media (max-width: 899px)" in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-4: .mobile-metrics per display:none auf Desktop versteckt', () => {
	// Der Block muss "display: none" als Default enthalten, damit die Kacheln
	// auf Desktop (≥900px) nicht sichtbar sind.
	const hasMobileMetrics = source.includes('mobile-metrics');
	const hasDisplayNone = source.includes('display: none');
	assert.ok(
		hasMobileMetrics && hasDisplayNone,
		'Erwarte ".mobile-metrics" + "display: none" in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// AC-1 / AC-2 / AC-3: Imports der benötigten Utilities und Komponente
// ---------------------------------------------------------------------------

test('Import von Stat-Komponente (molecules/Stat) vorhanden', () => {
	assert.ok(
		source.includes('Stat') && source.includes('molecules'),
		'Erwarte Import von Stat aus molecules in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('Import von getReportSchedule für BRIEFING-Kachel vorhanden', () => {
	assert.ok(
		source.includes('getReportSchedule'),
		'Erwarte Import von getReportSchedule in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('Import von todayStageIndex für ETAPPE-Kachel vorhanden', () => {
	assert.ok(
		source.includes('todayStageIndex'),
		'Erwarte Import von todayStageIndex in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('Import von deriveTripStatus für Status-abhängige Logik vorhanden', () => {
	// deriveTripStatus ist bereits importiert über tripHero (getDaysLabel ruft es auf),
	// aber muss direkt in TripHeader für etappeValue / startLabel verfügbar sein.
	assert.ok(
		source.includes('deriveTripStatus'),
		'Erwarte direkten Import von deriveTripStatus in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// AC-1: ETAPPE-Logik — abgeleiteter Wert im Script-Block
// ---------------------------------------------------------------------------

test('AC-1: etappeValue als $derived-Block vorhanden', () => {
	assert.ok(
		source.includes('etappeValue'),
		'Erwarte "etappeValue" als $derived-Variable in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// AC-2: BRIEFING-Logik — abgeleiteter Wert im Script-Block
// ---------------------------------------------------------------------------

test('AC-2: briefingValue als $derived-Block vorhanden', () => {
	assert.ok(
		source.includes('briefingValue'),
		'Erwarte "briefingValue" als $derived-Variable in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// AC-3: START IN / TAG-Logik — abgeleiteter Wert und Label im Script-Block
// ---------------------------------------------------------------------------

test('AC-3: startValue als $derived-Block vorhanden', () => {
	assert.ok(
		source.includes('startValue'),
		'Erwarte "startValue" als $derived-Variable in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-3: startLabel als $derived-Block vorhanden', () => {
	assert.ok(
		source.includes('startLabel'),
		'Erwarte "startLabel" als $derived-Variable in TripHeader.svelte — ' +
			'fehlt noch (TDD RED erwartet Fehler).'
	);
});
