// Helper fuer neue AlertRules im AlertRulesEditor.
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §2.
//
// Default = haeufigster Use-Case (Wind-Boeen 50 km/h, Warning, enabled).
// Separate Funktion ist unit-testbar.

import type { AlertRule } from '$lib/types';

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
