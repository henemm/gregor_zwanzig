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

import type { AlertMetric, AlertRule, AlertSeverity } from '../../types.ts';
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
