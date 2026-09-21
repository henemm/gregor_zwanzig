// Helper fuer neue AlertRules im AlertRulesEditor.
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §2.
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (#1895 Schritt 1)
//
// Default = Aenderungsregel auf Wind-Boeen (Δ 20 km/h ueber 6 h, Warning, enabled).
// Seit #1895 Schritt 1 gibt es nur noch Aenderungsregeln, darum kind='delta'
// (Variante A der zweiten Annahme der Spec: Δ 20 / 6h sind die Werte, die der
// Editor bisher schon im Modus „Aenderung" vorbelegt hat).
// Separate Funktion ist unit-testbar.

import type { AlertMetric, AlertRule } from '$lib/types';

export function newDefaultRule(): AlertRule {
	return {
		id: crypto.randomUUID(),
		kind: 'delta',
		metric: 'wind_gust',
		threshold: 20,
		delta_window: '6h',
		unit: 'km/h',
		severity: 'warning',
		enabled: true
	};
}

// =============================================================================
// #1895 Schritt 1 — expandRules() kennt keinen Modus mehr
// =============================================================================
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md
//
// Bis #1895 nahm expandRules() den im Editor gewaehlten Modus
// ('absolute' | 'delta' | 'both') und lieferte je nachdem eine oder zwei Regeln.
// Der Absolut-Modus loest seit #946 nie mehr einen Alarm aus, und der Go-Store
// schreibt jede Absolut-Regel bei jedem Laden und Speichern still nach
// kind='delta' um (SyncAlertRules). Die Modus-Auswahl ist deshalb aus der
// Bedienflaeche gefallen; hier bleibt der Δ-Zweig als einziger uebrig.
//
// Zusicherung: IMMER genau eine Regel — nie zwei (das alte „Beides" erzeugte ein
// Regel-Paar), nie null. `pair_id` faellt weg, alle uebrigen Felder (`id`,
// `metric`, `enabled`, `channels`, `severity`, `unit`) werden unveraendert
// durchgereicht. `channels` traegt die einzige verbliebene Wirkung der Regel und
// darf hier weder erfunden noch verworfen werden.

export const DELTA_ONLY_METRICS: ReadonlySet<AlertMetric> = new Set<AlertMetric>([
	'temperature_change',
	'wind_change',
	'precipitation_change',
	'thunder_level'
]);

export function expandRules(
	rule: AlertRule,
	deltaThreshold: number = rule.threshold,
	deltaWindow: string = '6h'
): AlertRule[] {
	// pair_id explizit entfernen: eine Alt-Regel aus dem frueheren „Beides"-Modus
	// darf die Paar-Markierung nicht ueber den Rueckbau hinweg mitschleppen.
	const { pair_id: _pid, ...rest } = rule;
	return [{ ...rest, kind: 'delta', threshold: deltaThreshold, delta_window: deltaWindow }];
}
