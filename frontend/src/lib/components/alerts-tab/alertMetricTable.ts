// Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle Helper.
//
// Spec: docs/specs/modules/issue_180_alert_metric_table.md
//
// Pure-Function Helpers, getrennt von der Svelte-Komponente, damit sie
// unter `node --test` ohne Svelte-Compiler laufen koennen.
//
// Inhalt:
//  - METRIC_DEFAULTS:        Default-Schwellwerte pro AlertMetric.
//  - ALL_ALERT_METRICS:      Geordnete Liste der 9 Metriken (Anzeige-Reihenfolge).
//  - MetricRowState:         interner UI-Zustand einer Zeile.
//  - alertRulesToRowState(): mappt persistierte AlertRule[] -> Row-State.
//  - rowStateToAlertRules(): mappt Row-State -> AlertRule[] (Save-Pfad).

import type { AlertMetric, AlertRule, AlertSeverity, SensLevel } from '../../types.ts';
import { DELTA_ONLY_METRICS } from '../alert-rules-editor/alertRuleDefaults.ts';
import { ALERT_METRIC_LABELS } from '../../utils/alertMetricLabels.ts';

export const METRIC_DEFAULTS: Record<AlertMetric, number> = {
	wind_gust: 50,
	precipitation_sum: 10,
	thunder_level: 1,
	snow_line: 2000,
	temperature_min: -5,
	temperature_max: 35,
	temperature_change: 10,
	wind_change: 20,
	precipitation_change: 5,
	// Issue #846: 4 neue Metriken (Epic #813 Slice 3) — Fallback-Defaults
	fresh_snow: 8,
	cape: 600,
	visibility: 1000,
	humidity: 15,
	// Issue #946: Nullgradgrenze (freezing_level).
	freezing_level: 200,
};

// Issue #846: Preset-Schwellwert-Tabelle (alle 13 Metriken × 3 Presets).
// Wert null = Metrik im Preset "deaktiviert" nicht aktiv.
export type PresetName = 'deaktiviert' | 'entspannt' | 'standard' | 'sensibel';

export const METRIC_PRESETS: Record<
	PresetName,
	Record<AlertMetric, number> | null
> = {
	deaktiviert: null,
	entspannt: {
		wind_gust: 35,
		precipitation_sum: 20,
		thunder_level: 1,
		snow_line: 600,
		temperature_min: 8,
		temperature_max: 10,
		temperature_change: 14,
		wind_change: 35,
		precipitation_change: 15,
		fresh_snow: 20,
		cape: 1200,
		visibility: 500,
		humidity: 25,
		freezing_level: 400,
	},
	standard: {
		wind_gust: 20,
		precipitation_sum: 10,
		thunder_level: 1,
		snow_line: 400,
		temperature_min: 5,
		temperature_max: 6,
		temperature_change: 10,
		wind_change: 25,
		precipitation_change: 7,
		fresh_snow: 8,
		cape: 600,
		visibility: 1000,
		humidity: 15,
		freezing_level: 200,
	},
	sensibel: {
		wind_gust: 12,
		precipitation_sum: 5,
		thunder_level: 1,
		snow_line: 200,
		temperature_min: 3,
		temperature_max: 4,
		temperature_change: 6,
		wind_change: 15,
		precipitation_change: 3,
		fresh_snow: 2,
		cape: 200,
		visibility: 3000,
		humidity: 10,
		freezing_level: 100,
	},
};

// Anzeige-Reihenfolge der Zeilen — siehe Spec §Reihenfolge.
export const ALL_ALERT_METRICS: readonly AlertMetric[] = [
	'wind_gust',
	'precipitation_sum',
	'thunder_level',
	'snow_line',
	'temperature_min',
	'temperature_max',
	'temperature_change',
	'wind_change',
	'precipitation_change',
];

export interface MetricRowState {
	absEnabled: boolean;
	absThreshold: number;
	deltaEnabled: boolean;
	deltaThreshold: number;
	severity: AlertSeverity;
}

export type RowStateMap = Record<AlertMetric, MetricRowState>;

/**
 * Wandelt eine Liste persistierter AlertRules in den UI-Row-State um.
 * Fehlende Regeln -> Defaults aus METRIC_DEFAULTS, Severity-Default 'warning'.
 */
export function alertRulesToRowState(
	rules: readonly AlertRule[],
	_existing?: readonly AlertRule[],
): RowStateMap {
	const state = {} as RowStateMap;
	for (const metric of ALL_ALERT_METRICS) {
		const absRule = rules.find((r) => r.metric === metric && r.kind === 'absolute');
		const deltaRule = rules.find((r) => r.metric === metric && r.kind === 'delta');
		state[metric] = {
			absEnabled: absRule?.enabled ?? false,
			absThreshold: absRule?.threshold ?? METRIC_DEFAULTS[metric],
			deltaEnabled: deltaRule?.enabled ?? false,
			deltaThreshold: deltaRule?.threshold ?? METRIC_DEFAULTS[metric],
			severity: absRule?.severity ?? deltaRule?.severity ?? 'warning',
		};
	}
	return state;
}

function newId(): string {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	// Fallback fuer Node-Test-Umgebungen ohne globales crypto.
	return `rule-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Wandelt den Row-State zurueck in AlertRule[]. Deaktivierte Zeilen werden
 * weggelassen. Vorhandene IDs aus `existing` bleiben pro Metric+Kind erhalten,
 * neue Regeln bekommen eine UUID. Delta-only-Metriken liefern keine absolute Rule.
 */
export function rowStateToAlertRules(
	state: RowStateMap,
	existing: readonly AlertRule[] = [],
): AlertRule[] {
	const result: AlertRule[] = [];
	for (const metric of ALL_ALERT_METRICS) {
		const row = state[metric];
		if (!row) continue;
		const unit = ALERT_METRIC_LABELS[metric]?.unit || undefined;
		const isDeltaOnly = DELTA_ONLY_METRICS.has(metric);

		if (row.absEnabled && !isDeltaOnly) {
			const prev = existing.find((r) => r.metric === metric && r.kind === 'absolute');
			result.push({
				id: prev?.id ?? newId(),
				kind: 'absolute',
				metric,
				threshold: row.absThreshold,
				...(unit ? { unit } : {}),
				severity: row.severity,
				enabled: true,
			});
		}
		if (row.deltaEnabled) {
			const prev = existing.find((r) => r.metric === metric && r.kind === 'delta');
			result.push({
				id: prev?.id ?? newId(),
				kind: 'delta',
				metric,
				threshold: row.deltaThreshold,
				...(unit ? { unit } : {}),
				severity: row.severity,
				enabled: true,
			});
		}
	}
	return result;
}

// ─── Issue #864/#859: Per-Metrik-Alert-Levels ─────────────────────────────

export type { SensLevel }; // re-export from types.ts

/** Alle 13 alertable Metriken in Anzeige-Reihenfolge. */
export const ALERTABLE_METRICS: readonly AlertMetric[] = [
	'wind_gust',
	'precipitation_sum',
	'thunder_level',
	'snow_line',
	'temperature_min',
	'temperature_max',
	'temperature_change',
	'wind_change',
	'precipitation_change',
	'fresh_snow',
	'cape',
	'visibility',
	'humidity',
	'freezing_level',
];

/** Metriken die THRESHOLD_CROSSING verwenden (absoluter Schwellwert, nicht Delta). */
export const THRESHOLD_CROSSING_METRICS: ReadonlySet<AlertMetric> = new Set<AlertMetric>([
	'visibility',
]);

const _METRIC_UNITS: Record<AlertMetric, string> = {
	wind_gust: 'km/h',
	precipitation_sum: 'mm',
	thunder_level: '',
	snow_line: 'm',
	temperature_min: '°C',
	temperature_max: '°C',
	temperature_change: '°C',
	wind_change: 'km/h',
	precipitation_change: 'mm',
	fresh_snow: 'cm',
	cape: 'J/kg',
	visibility: 'm',
	humidity: '%',
	freezing_level: 'm',
};

/**
 * Gibt den Schwellwert-Text für Metrik+Stufe zurück.
 * Delta-Metriken: "Δ ≥ X unit"; THRESHOLD_CROSSING: "< X unit"; off: null.
 */
export function levelToThreshold(metric: AlertMetric, level: SensLevel): string | null {
	if (level === 'off') return null;
	const presetData = METRIC_PRESETS[level as PresetName];
	if (!presetData) return null;
	const value = presetData[metric];
	if (value === undefined) return null;
	const unit = _METRIC_UNITS[metric] ?? '';
	if (THRESHOLD_CROSSING_METRICS.has(metric)) {
		return unit ? `< ${value} ${unit}` : `< ${value}`;
	}
	return unit ? `Δ ≥ ${value} ${unit}` : `Δ ≥ ${value}`;
}

/**
 * Wandelt globalen Preset-String in per-Metrik SensLevel-Record um.
 * "deaktiviert" → alle 'off'. Unbekannte Presets → 'standard'.
 */
export function migrateAlertPreset(
	preset: string,
	activeMetrics: readonly AlertMetric[],
): Record<AlertMetric, SensLevel> {
	const level: SensLevel =
		preset === 'deaktiviert' ? 'off'
		: preset === 'entspannt' ? 'entspannt'
		: preset === 'sensibel' ? 'sensibel'
		: 'standard';
	return Object.fromEntries(
		activeMetrics.map((m) => [m, level]),
	) as Record<AlertMetric, SensLevel>;
}

// ─── Issue #864: Catalog-ID → AlertMetric Mapping ─────────────────────────

import type { WeatherConfigMetric } from '../../types.ts';

/** Catalog metric_id → AlertMetric(s) die davon aktiviert werden. */
const CATALOG_TO_ALERT_METRICS: Record<string, readonly AlertMetric[]> = {
	// Direkte Treffer (falls Catalog bereits AlertMetric-Namen nutzt)
	wind_gust:            ['wind_gust'],
	precipitation_sum:    ['precipitation_sum'],
	precipitation_change: ['precipitation_change'],
	wind_change:          ['wind_change'],
	temperature_min:      ['temperature_min'],
	temperature_max:      ['temperature_max'],
	temperature_change:   ['temperature_change'],
	fresh_snow:           ['fresh_snow'],
	snow_line:            ['snow_line'],
	cape:                 ['cape'],
	visibility:           ['visibility'],
	humidity:             ['humidity'],
	thunder_level:        ['thunder_level'],
	freezing_level:       ['freezing_level'],
	// Kurz-IDs aus dem Catalog
	gust:          ['wind_gust'],
	wind:          ['wind_change'],
	precipitation: ['precipitation_sum', 'precipitation_change'],
	thunder:       ['thunder_level'],
	snowfall_limit: ['snow_line'],
	temperature:   ['temperature_min', 'temperature_max', 'temperature_change'],
};

/**
 * Gibt die alertable AlertMetrics zurück, die dem aktiven Wetter-Metriken-Set entsprechen.
 * Fallback auf ALERTABLE_METRICS wenn keine Übereinstimmung.
 */
export function activeAlertableMetrics(
	configMetrics: readonly WeatherConfigMetric[] | undefined | null,
): readonly AlertMetric[] {
	if (!configMetrics || configMetrics.length === 0) return ALERTABLE_METRICS;
	const enabled = configMetrics.filter((m) => m.enabled);
	if (enabled.length === 0) return ALERTABLE_METRICS;

	const seen = new Set<AlertMetric>();
	for (const m of enabled) {
		const mapped = CATALOG_TO_ALERT_METRICS[m.metric_id];
		if (mapped) mapped.forEach((a) => seen.add(a));
	}
	if (seen.size === 0) return ALERTABLE_METRICS;
	// Reihenfolge aus ALERTABLE_METRICS beibehalten
	return ALERTABLE_METRICS.filter((a) => seen.has(a));
}

// Issue #414 — Modus aus persistierten Rules ableiten.
export function deriveAlertMode(rules: readonly AlertRule[]): 'absolute' | 'delta' | 'both' {
	const hasAbs = rules.some((r) => r.kind === 'absolute' && r.enabled);
	const hasDelta = rules.some((r) => r.kind === 'delta' && r.enabled);
	if (hasAbs && hasDelta) return 'both';
	if (hasDelta) return 'delta';
	return 'both'; // Default: 'both' (auch bei leerem Array und nur-absolute)
}

// Issue #414 — Modus auf RowStateMap anwenden; mutiert in-place.
// Threshold-Werte (absThreshold, deltaThreshold) werden NICHT geaendert.
export function applyModeToRowState(
	state: RowStateMap,
	mode: 'absolute' | 'delta' | 'both',
): void {
	for (const metric of ALL_ALERT_METRICS) {
		const row = state[metric];
		if (!row) continue;
		const isDeltaOnly = DELTA_ONLY_METRICS.has(metric);
		switch (mode) {
			case 'absolute':
				row.absEnabled = !isDeltaOnly;
				row.deltaEnabled = false;
				break;
			case 'delta':
				row.absEnabled = false;
				row.deltaEnabled = true;
				break;
			case 'both':
				row.absEnabled = !isDeltaOnly;
				row.deltaEnabled = true;
				break;
		}
	}
}
