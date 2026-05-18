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
// =============================================================================
// Spec: docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md
//
// Pure-Function-Extraktion der saveEdit()-Logik aus AlertRuleRow.svelte.
// Nimmt eine Rule + den gewaehlten UI-Modus ('absolute' | 'delta' | 'both')
// und liefert das Array, das an AlertRulesEditor.updateRules(index, ...)
// weitergereicht wird.
//
//   mode='absolute'                  -> [rule mit kind='absolute']
//   mode='delta'                     -> [rule mit kind='delta']
//   mode='both' (Standard-Metrik)    -> [absolute (orig-ID), delta (neue UUID)]
//   mode='both' (Delta-only Metrik)  -> [rule mit kind='delta'] (Guard greift)
//
// Delta-only-Metriken (AC-6): semantisch keine 'absolute'-Rule moeglich.

export const DELTA_ONLY_METRICS: ReadonlySet<AlertMetric> = new Set<AlertMetric>([
	'temperature_change',
	'wind_change',
	'precipitation_change'
]);

export type AlertRuleMode = 'absolute' | 'delta' | 'both';

export function expandRules(rule: AlertRule, mode: AlertRuleMode): AlertRule[] {
	if (mode === 'absolute') {
		return [{ ...rule, kind: 'absolute' }];
	}
	if (mode === 'delta') {
		return [{ ...rule, kind: 'delta' }];
	}
	// mode === 'both'
	if (DELTA_ONLY_METRICS.has(rule.metric)) {
		// AC-6: Delta-only-Metrik bei 'both' fallback auf nur delta
		return [{ ...rule, kind: 'delta' }];
	}
	// AC-5: zwei Rules — erste behaelt original-ID (absolute), zweite neue UUID (delta)
	return [
		{ ...rule, kind: 'absolute' },
		{ ...rule, id: crypto.randomUUID(), kind: 'delta' }
	];
}
