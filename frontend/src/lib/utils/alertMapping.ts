// Pure Function: Wizard-Thresholds → AlertRule[].
// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md §2.
//
// Wird vom Trip-Wizard (`wizardState.svelte.ts`, toTripPayload) verwendet, um
// parallel zu `report_config.alert_thresholds` den neuen `alert_rules`-Block
// am Trip zu schreiben (W1-Architektur: beide Bloecke koexistieren).

import type { AlertRule, AlertSeverity } from '$lib/types';

/**
 * Thresholds-Form aus dem Wizard-State (Type-Equivalent zu
 * `BriefingConfig.thresholds` in wizardState.svelte.ts). Hier inline definiert
 * um Zirkular-Imports zu vermeiden.
 */
export interface Thresholds {
	gust_kmh: number | null;
	precip_mm: number | null;
	thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
	snow_line_m: number | null;
}

/**
 * Mapped die vier Wizard-Schwellwerte auf typisierte AlertRules.
 *
 * Semantik:
 *  - Jeder gesetzte Threshold (!= null) erzeugt genau eine Rule.
 *  - `thunder_level === 'NONE'` ODER `null` → keine Rule (User will keinen
 *    Gewitter-Alarm).
 *  - 'MED' → threshold=1.0, 'HIGH' → threshold=2.0.
 *  - Alle Rules: kind='absolute', severity='warning', enabled=true.
 *  - Reihenfolge: wind_gust, precipitation_sum, thunder_level, snow_line.
 *
 * IDs via `crypto.randomUUID()` — eindeutig pro Aufruf.
 */
export function mapBriefingsToAlertRules(t: Thresholds): AlertRule[] {
	const rules: AlertRule[] = [];
	const baseRule = () => ({
		id: crypto.randomUUID(),
		kind: 'absolute' as const,
		severity: 'warning' as AlertSeverity,
		enabled: true
	});

	// Edge-Case (F003): threshold=0 ergibt sinnlose Rule ("ab 0 km/h alarmieren").
	// Daher: nur Rules anlegen, wenn Wert > 0. Negative Werte werden ebenfalls
	// gefiltert, sind UI-seitig nicht eingebbar, aber Defense-in-Depth.
	if (t.gust_kmh !== null && t.gust_kmh > 0) {
		rules.push({
			...baseRule(),
			metric: 'wind_gust',
			threshold: t.gust_kmh,
			unit: 'km/h'
		});
	}
	if (t.precip_mm !== null && t.precip_mm > 0) {
		rules.push({
			...baseRule(),
			metric: 'precipitation_sum',
			threshold: t.precip_mm,
			unit: 'mm'
		});
	}
	if (t.thunder_level === 'MED') {
		rules.push({
			...baseRule(),
			metric: 'thunder_level',
			threshold: 1.0,
			unit: ''
		});
	} else if (t.thunder_level === 'HIGH') {
		rules.push({
			...baseRule(),
			metric: 'thunder_level',
			threshold: 2.0,
			unit: ''
		});
	}
	// thunder_level === 'NONE' oder null → keine Rule
	if (t.snow_line_m !== null && t.snow_line_m > 0) {
		rules.push({
			...baseRule(),
			metric: 'snow_line',
			threshold: t.snow_line_m,
			unit: 'm'
		});
	}

	return rules;
}
