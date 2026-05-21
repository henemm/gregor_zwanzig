// Helper fuer neue AlertRules im AlertRulesEditor.
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §2.
//
// Default = haeufigster Use-Case (Wind-Boeen 50 km/h, Warning, enabled).
// Separate Funktion ist unit-testbar.

import type { AlertMetric, AlertRule } from '$lib/types';

export function newDefaultRule(): AlertRule {
	return {
		id: crypto.randomUUID(),
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 50,
		unit: 'km/h',
		severity: 'warning',
		enabled: true
	};
}

// =============================================================================
// Issue #179 — Modus-Toggle: expandRules()
// Issue #297 — Erweiterung: separate absThreshold / deltaThreshold / deltaWindow
// =============================================================================
// Spec: docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md
// Spec: docs/specs/modules/issue_297_alert_beides_mode.md
//
// Pure-Function-Extraktion der saveEdit()-Logik aus AlertRuleRow.svelte.
// Nimmt eine Rule + den gewaehlten UI-Modus ('absolute' | 'delta' | 'both')
// und liefert das Array, das an AlertRulesEditor.updateRules(index, ...)
// weitergereicht wird.
//
//   mode='absolute'                  -> [rule mit kind='absolute', threshold=absThreshold]
//   mode='delta'                     -> [rule mit kind='delta', threshold=deltaThreshold,
//                                        delta_window=deltaWindow]
//   mode='both' (Standard-Metrik)    -> [absolute (orig-ID, pair_id),
//                                        delta (neue UUID, pair_id, delta_window)]
//   mode='both' (Delta-only Metrik)  -> [rule mit kind='delta'] (Guard greift, kein pair_id)
//
// Delta-only-Metriken (AC-6/AC-8): semantisch keine 'absolute'-Rule moeglich.
//
// Default-Parameter (absThreshold/deltaThreshold/deltaWindow) erhalten die
// Rueckwaertskompatibilitaet: bestehende 2-Param-Aufrufe (`expandRules(rule, mode)`)
// fallen auf `rule.threshold` und das Default-Zeitfenster '6h' zurueck.

export const DELTA_ONLY_METRICS: ReadonlySet<AlertMetric> = new Set<AlertMetric>([
	'temperature_change',
	'wind_change',
	'precipitation_change'
]);

export type AlertRuleMode = 'absolute' | 'delta' | 'both';

export function expandRules(
	rule: AlertRule,
	mode: AlertRuleMode,
	absThreshold: number = rule.threshold,
	deltaThreshold: number = rule.threshold,
	deltaWindow: string = '6h'
): AlertRule[] {
	if (mode === 'absolute') {
		return [{ ...rule, kind: 'absolute', threshold: absThreshold }];
	}
	if (mode === 'delta') {
		return [
			{ ...rule, kind: 'delta', threshold: deltaThreshold, delta_window: deltaWindow }
		];
	}
	// mode === 'both'
	if (DELTA_ONLY_METRICS.has(rule.metric)) {
		// AC-6/AC-8: Delta-only-Metrik bei 'both' fallback auf nur delta, kein pair_id.
		return [
			{ ...rule, kind: 'delta', threshold: deltaThreshold, delta_window: deltaWindow }
		];
	}
	// AC-5/AC-7: zwei Rules mit gemeinsamer pair_id.
	const pairId = crypto.randomUUID();
	return [
		{ ...rule, kind: 'absolute', threshold: absThreshold, pair_id: pairId },
		{
			...rule,
			id: crypto.randomUUID(),
			kind: 'delta',
			threshold: deltaThreshold,
			delta_window: deltaWindow,
			pair_id: pairId
		}
	];
}
