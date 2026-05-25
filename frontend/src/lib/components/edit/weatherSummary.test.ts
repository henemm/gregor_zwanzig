// TDD RED: Issue #345 (Wetter-Editor-Konsolidierung, Touren-Teil).
//
// Spec: docs/specs/modules/issue_345_weather_editor_consolidation.md (AC-1).
//
// Die Tour-Bearbeiten-Maske zeigt künftig eine read-only Wetter-Zusammenfassung
// (Profilname/Preset + Anzahl Spalten/Detail/aktive Metriken aus display_config).
// Die reine Funktion summarizeTripWeather() aggregiert diese Zahlen aus dem
// gespeicherten display_config — bucket-bewusst (#360/#364) UND legacy-fähig.
//
// Diese Importe zielen auf ein NOCH NICHT existierendes Modul
// (edit/weatherSummary.ts) → in der RED-Phase schlägt der Import fehl
// (ERR_MODULE_NOT_FOUND), jeder Test ist rot. KEINE Mocks (pure function,
// echte display_config-Beispiele wie sie WeatherMetricsTab.svelte lädt/speichert).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/weatherSummary.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { summarizeTripWeather } from './weatherSummary.ts';

// =============================================================================
// Hilfs-Konstruktoren für realistische display_config-Beispiele.
// Shape deckt sich mit BucketWeatherConfigMetric in trip-detail/metricsEditor.ts
// und mit dem Round-Trip, den WeatherMetricsTab.svelte schreibt/liest.
// =============================================================================

const HORIZONS_ALL = { today: true, tomorrow: true, day_after: true };

function metric(
	metric_id: string,
	opts: {
		enabled?: boolean;
		bucket?: 'primary' | 'secondary';
		order?: number;
		use_friendly_format?: boolean;
	} = {},
) {
	return {
		metric_id,
		enabled: opts.enabled ?? true,
		use_friendly_format: opts.use_friendly_format ?? true,
		horizons: { ...HORIZONS_ALL },
		...(opts.bucket ? { bucket: opts.bucket } : {}),
		order: opts.order ?? 0,
	};
}

// =============================================================================
// AC-1 Fall 1: leeres / undefiniertes display_config → alles 0, presetName null
// =============================================================================

test('summarizeTripWeather > undefiniertes display_config → alle 0, presetName null', () => {
	const s = summarizeTripWeather(undefined);
	assert.equal(s.presetName, null);
	assert.equal(s.spalten, 0);
	assert.equal(s.detail, 0);
	assert.equal(s.aktiv, 0);
});

test('summarizeTripWeather > leeres display_config (keine metrics) → alle 0, presetName null', () => {
	const s = summarizeTripWeather({});
	assert.equal(s.presetName, null);
	assert.equal(s.spalten, 0);
	assert.equal(s.detail, 0);
	assert.equal(s.aktiv, 0);
});

test('summarizeTripWeather > display_config mit leerer metrics-Liste → alle 0', () => {
	const s = summarizeTripWeather({ metrics: [] });
	assert.equal(s.presetName, null);
	assert.equal(s.spalten, 0);
	assert.equal(s.detail, 0);
	assert.equal(s.aktiv, 0);
});

// =============================================================================
// AC-1 Fall 2: Altformat (nur enabled, keine buckets) → aktiv zählt enabled=true
// =============================================================================

test('summarizeTripWeather > Altformat ohne buckets → aktiv zählt nur enabled=true', () => {
	// Legacy-Stand wie ihn der #360-Loader vorfindet: kein bucket, kein order.
	const displayConfig = {
		metrics: [
			{ metric_id: 'temperature', enabled: true, use_friendly_format: false },
			{ metric_id: 'wind', enabled: true, use_friendly_format: false },
			{ metric_id: 'cloud_total', enabled: false, use_friendly_format: true },
			{ metric_id: 'humidity', enabled: false, use_friendly_format: true },
		],
	};
	const s = summarizeTripWeather(displayConfig);
	// 2 aktive Metriken (temperature, wind), 2 sind off.
	assert.equal(s.aktiv, 2);
	// Ohne bucket/order kann nicht zwischen Spalte/Detail unterschieden werden:
	// keine Metrik ist explizit als secondary markiert → detail 0.
	assert.equal(s.detail, 0);
	// Alle aktiven gelten mangels Bucket-Markierung als Spalte.
	assert.equal(s.spalten, 2);
});

test('summarizeTripWeather > Altformat: alle enabled=false → aktiv 0', () => {
	const displayConfig = {
		metrics: [
			{ metric_id: 'temperature', enabled: false },
			{ metric_id: 'wind', enabled: false },
		],
	};
	const s = summarizeTripWeather(displayConfig);
	assert.equal(s.aktiv, 0);
	assert.equal(s.spalten, 0);
	assert.equal(s.detail, 0);
});

// =============================================================================
// AC-1 Fall 3: Bucket-Format (primary/secondary/off + order)
//              → spalten/detail korrekt
// =============================================================================

test('summarizeTripWeather > Bucket-Format zählt primary als Spalten, secondary als Detail', () => {
	// So speichert WeatherMetricsTab.svelte via buildWeatherConfigMetrics():
	// primary/secondary mit bucket+order, off als enabled:false ohne bucket.
	const displayConfig = {
		metrics: [
			metric('temperature', { bucket: 'primary', order: 0 }),
			metric('wind', { bucket: 'primary', order: 1 }),
			metric('gust', { bucket: 'primary', order: 2 }),
			metric('cloud_total', { bucket: 'secondary', order: 0 }),
			metric('humidity', { bucket: 'secondary', order: 1 }),
			metric('pressure', { enabled: false, order: 0 }),
		],
	};
	const s = summarizeTripWeather(displayConfig);
	assert.equal(s.spalten, 3, '3 primary-Metriken → Spalten');
	assert.equal(s.detail, 2, '2 secondary-Metriken → Detail');
	// aktiv = primary + secondary (off zählt nicht).
	assert.equal(s.aktiv, 5);
	assert.equal(s.presetName, null);
});

test('summarizeTripWeather > Bucket-Format: enabled aber ohne bucket gilt als Detail (defensiv)', () => {
	// Wie der #360-Loader (looseActive): enabled ohne expliziten bucket → secondary.
	const displayConfig = {
		metrics: [
			metric('temperature', { bucket: 'primary', order: 0 }),
			// kein bucket, aber enabled → defensiv als Detail behandelt.
			{ metric_id: 'wind', enabled: true, use_friendly_format: true, order: 0 },
			metric('cloud_total', { enabled: false }),
		],
	};
	const s = summarizeTripWeather(displayConfig);
	assert.equal(s.spalten, 1, 'nur temperature ist primary');
	assert.equal(s.detail, 1, 'wind ohne bucket aber enabled → Detail');
	assert.equal(s.aktiv, 2, 'temperature + wind aktiv, cloud_total off');
});

test('summarizeTripWeather > Bucket-Format: off-Metriken zählen weder als Spalte/Detail noch aktiv', () => {
	const displayConfig = {
		metrics: [
			metric('temperature', { bucket: 'primary', order: 0 }),
			metric('wind', { enabled: false }),
			metric('gust', { enabled: false }),
			metric('humidity', { enabled: false }),
		],
	};
	const s = summarizeTripWeather(displayConfig);
	assert.equal(s.spalten, 1);
	assert.equal(s.detail, 0);
	assert.equal(s.aktiv, 1, 'nur temperature aktiv, 3 sind off');
});

// =============================================================================
// AC-1 Fall 4: mit preset_name gesetzt → presetName korrekt
// =============================================================================

test('summarizeTripWeather > preset_name wird durchgereicht', () => {
	const displayConfig = {
		preset_name: 'Hochtour Standard',
		metrics: [
			metric('temperature', { bucket: 'primary', order: 0 }),
			metric('wind', { bucket: 'secondary', order: 0 }),
		],
	};
	const s = summarizeTripWeather(displayConfig);
	assert.equal(s.presetName, 'Hochtour Standard');
	assert.equal(s.spalten, 1);
	assert.equal(s.detail, 1);
	assert.equal(s.aktiv, 2);
});

test('summarizeTripWeather > leerer preset_name-String wird als null behandelt', () => {
	const displayConfig = {
		preset_name: '',
		metrics: [metric('temperature', { bucket: 'primary', order: 0 })],
	};
	const s = summarizeTripWeather(displayConfig);
	// Leerer Preset-Name ist kein gesetzter Name → null (Anzeige fällt auf
	// "Eigenes Profil" o.ä. zurück, AC-1).
	assert.equal(s.presetName, null);
	assert.equal(s.spalten, 1);
	assert.equal(s.aktiv, 1);
});
