// TDD RED — Issue #300: Trip-Wizard Redesign Route/Etappen/Wetter/Reports
//
// Spec: docs/specs/modules/issue_300_wizard_redesign.md
//
// Diese Tests decken die AC-1 bis AC-10 der Spec ab (Unit-testbare Teile).
// Alle Tests MÜSSEN in der RED-Phase fehlschlagen:
//   - wizardState hat noch kein `weatherMetrics`-Feld
//   - canAdvanceStep1 prüft noch activity als Pflichtfeld
//   - toTripPayload schreibt noch kein display_config.metrics
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_300_wizard_redesign.test.ts

// --- Globals fuer Svelte-5-Runen einrichten BEFORE Modul-Import ----------
type RuneFn = (v: unknown) => unknown;
const g = globalThis as unknown as Record<string, RuneFn>;
if (typeof g.$state !== 'function') g.$state = (v: unknown) => v;
if (typeof g.$derived !== 'function') g.$derived = (v: unknown) => v;

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WizardState } from '../wizardState.svelte.ts';

// WeatherConfigMetric-Shape inline — kein $lib-Import nötig für Node-Testsuite
interface WCMetric {
	metric_id: string;
	enabled: boolean;
	use_friendly_format?: boolean;
	horizons?: { today: boolean; tomorrow: boolean; day_after: boolean };
}

// ---------------------------------------------------------------------------
// AC-2: canAdvanceStep1 ohne activity (activity ist kein Pflichtfeld mehr)
// ---------------------------------------------------------------------------

test('AC-2: canAdvanceStep1 ohne activity und mit name+startDate → true', () => {
	const s = new WizardState();
	s.name = 'GR20';
	s.startDate = '2026-06-01';
	// activity ist NICHT gesetzt (null)
	assert.equal(s.activity, null, 'Precondition: activity ist null');
	assert.equal(
		s.canAdvanceStep1,
		true,
		'name+startDate reichen — activity ist kein Pflichtfeld mehr'
	);
});

test('AC-2: canAdvanceStep1 ohne activity und ohne startDate → false', () => {
	const s = new WizardState();
	s.name = 'GR20';
	// Weder activity noch startDate gesetzt
	assert.equal(s.canAdvanceStep1, false, 'name allein reicht nicht');
});

test('AC-2: canAdvanceStep1 ohne activity und ohne name → false', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	// Weder activity noch name gesetzt
	assert.equal(s.canAdvanceStep1, false, 'startDate allein reicht nicht');
});

test('AC-2: canAdvanceStep1 mit activity+name+startDate bleibt true (rueckwaertskompatibel)', () => {
	const s = new WizardState();
	s.activity = 'trekking';
	s.name = 'GR20';
	s.startDate = '2026-06-01';
	assert.equal(
		s.canAdvanceStep1,
		true,
		'activity + name + startDate → weiterhin true'
	);
});

test('AC-2: canAdvanceStep1 nur startDate gesetzt → false (name fehlt)', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	// kein name, kein activity
	assert.equal(s.canAdvanceStep1, false);
});

// ---------------------------------------------------------------------------
// AC-10: weatherMetrics Feld existiert in WizardState
// ---------------------------------------------------------------------------

test('AC-10: weatherMetrics Feld existiert als leeres Array im Initialzustand', () => {
	const s = new WizardState();
	assert.ok(
		Object.prototype.hasOwnProperty.call(s, 'weatherMetrics'),
		'weatherMetrics-Feld muss in WizardState existieren'
	);
	assert.ok(Array.isArray(s.weatherMetrics), 'weatherMetrics muss ein Array sein');
	assert.equal(s.weatherMetrics.length, 0, 'Initialzustand: leeres Array');
});

test('AC-10: weatherMetrics ist unabhaengig zwischen WizardState-Instanzen', () => {
	const a = new WizardState();
	const b = new WizardState();
	a.weatherMetrics = [
		{
			metric_id: 'temperature',
			enabled: true,
			horizons: { today: true, tomorrow: false, day_after: false }
		} as WCMetric as never
	];
	assert.equal(
		b.weatherMetrics.length,
		0,
		'weatherMetrics darf nicht zwischen Instanzen geteilt werden'
	);
});

// ---------------------------------------------------------------------------
// AC-10: toTripPayload schreibt display_config.metrics
// ---------------------------------------------------------------------------

test('AC-10: toTripPayload mit leerem weatherMetrics → kein display_config.metrics im Payload', () => {
	const s = new WizardState();
	s.name = 'Test-Tour';
	s.startDate = '2026-06-01';
	// weatherMetrics ist leer (Default)
	const trip = s.toTripPayload();
	// Wenn display_config gesetzt, darf .metrics nicht leer sein
	if (trip.display_config !== undefined) {
		const dc = trip.display_config as Record<string, unknown>;
		assert.ok(
			!Array.isArray(dc['metrics']) || (dc['metrics'] as unknown[]).length === 0,
			'Leere weatherMetrics → kein metrics-Array im display_config'
		);
	}
	// Test gilt als bestanden wenn display_config schlicht nicht gesetzt ist
});

test('AC-10: toTripPayload mit weatherMetrics-Eintraegen → display_config.metrics im Payload', () => {
	const s = new WizardState();
	s.name = 'Test-Tour';
	s.startDate = '2026-06-01';
	s.weatherMetrics = [
		{
			metric_id: 'temperature',
			enabled: true,
			use_friendly_format: false,
			horizons: { today: true, tomorrow: true, day_after: false }
		} as WCMetric as never,
		{
			metric_id: 'wind_speed',
			enabled: true,
			use_friendly_format: false,
			horizons: { today: true, tomorrow: false, day_after: false }
		} as WCMetric as never
	];
	const trip = s.toTripPayload();
	assert.ok(
		trip.display_config !== undefined,
		'display_config muss im Payload vorhanden sein wenn weatherMetrics nicht leer'
	);
	const dc = trip.display_config as Record<string, unknown>;
	assert.ok(
		Array.isArray(dc['metrics']),
		'display_config.metrics muss ein Array sein'
	);
	const metrics = dc['metrics'] as unknown[];
	assert.equal(metrics.length, 2, 'Beide Metriken muessen im Payload sein');
	const first = metrics[0] as Record<string, unknown>;
	assert.equal(first['metric_id'], 'temperature');
});

test('AC-10: toTripPayload mit weatherMetrics — Horizonte bleiben erhalten', () => {
	const s = new WizardState();
	s.name = 'Horizont-Test';
	s.startDate = '2026-07-01';
	s.weatherMetrics = [
		{
			metric_id: 'precipitation',
			enabled: true,
			horizons: { today: true, tomorrow: true, day_after: false }
		} as WCMetric as never
	];
	const trip = s.toTripPayload();
	const dc = trip.display_config as Record<string, unknown>;
	const metrics = dc['metrics'] as Array<Record<string, unknown>>;
	const horizons = metrics[0]['horizons'] as Record<string, boolean> | undefined;
	assert.ok(horizons !== undefined, 'horizons muss im Payload-Metrik vorhanden sein');
	assert.equal(horizons['today'], true);
	assert.equal(horizons['tomorrow'], true);
	assert.equal(horizons['day_after'], false);
});

// ---------------------------------------------------------------------------
// Regressions-Schutz: bestehende Felder unverändert
// ---------------------------------------------------------------------------

test('Regression: activity-Feld bleibt in WizardState (wird in Step 3 gesetzt)', () => {
	const s = new WizardState();
	assert.equal(s.activity, null, 'activity Initialwert bleibt null');
	s.activity = 'skitour';
	assert.equal(s.activity, 'skitour');
});

test('Regression: toTripPayload schreibt activity wenn gesetzt', () => {
	const s = new WizardState();
	s.name = 'Regression';
	s.startDate = '2026-06-01';
	s.activity = 'skitour';
	const trip = s.toTripPayload();
	assert.equal(trip.activity, 'skitour');
	assert.ok(trip.aggregation?.profile, 'aggregation.profile weiterhin gesetzt');
});

test('Regression: shortcode-Feld bleibt in WizardState (optional)', () => {
	const s = new WizardState();
	assert.ok(
		Object.prototype.hasOwnProperty.call(s, 'shortcode'),
		'shortcode-Feld bleibt erhalten (backward-compat)'
	);
});
